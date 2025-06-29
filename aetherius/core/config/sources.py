"""
配置源详细实现

提供全功能的配置源实现，支持：
- 文件配置源（YAML、JSON、TOML）
- 环境变量配置源
- 字典配置源
- 远程配置源
- 监听配置变更
"""

import os
import json
import yaml
import asyncio
import logging
from typing import Any, Dict, Optional, Callable, List, Set
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import fnmatch
import threading
from concurrent.futures import ThreadPoolExecutor

from .interfaces import IConfigSource, ConfigPriority, ConfigChange

logger = logging.getLogger(__name__)


@dataclass
class WatcherConfig:
    """文件监听配置"""
    enabled: bool = True
    poll_interval: float = 1.0  # 秒
    debounce_delay: float = 0.5  # 去抖延迟
    recursive: bool = True
    exclude_patterns: List[str] = field(default_factory=lambda: ['*.swp', '*.tmp', '*~'])


class BaseConfigSource(IConfigSource):
    """配置源基类"""
    
    def __init__(self, priority: ConfigPriority = ConfigPriority.FILE, name: str = "base"):
        self._priority = priority
        self._name = name
        self._data: Dict[str, Any] = {}
        self._last_modified: Optional[datetime] = None
        self._change_callbacks: List[Callable[[ConfigChange], None]] = []
        self._is_loaded = False
        
    @property
    def priority(self) -> ConfigPriority:
        return self._priority
        
    @property  
    def name(self) -> str:
        return self._name
        
    def get_priority(self) -> ConfigPriority:
        return self._priority
        
    def add_change_callback(self, callback: Callable[[ConfigChange], None]):
        """添加变更回调"""
        self._change_callbacks.append(callback)
        
    def remove_change_callback(self, callback: Callable[[ConfigChange], None]):
        """移除变更回调"""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
            
    def _notify_change(self, change: ConfigChange):
        """通知配置变更"""
        for callback in self._change_callbacks:
            try:
                callback(change)
            except Exception as e:
                logger.warning(f"Config change callback failed: {e}")
                
    def is_loaded(self) -> bool:
        """检查是否已加载"""
        return self._is_loaded
        
    def get_last_modified(self) -> Optional[datetime]:
        """获取最后修改时间"""
        return self._last_modified
        
    def save(self, config: Dict[str, Any]) -> bool:
        """保存配置（基类默认不支持）"""
        return False


class DictConfigSource(BaseConfigSource):
    """字典配置源 - 用于测试和运行时配置"""
    
    def __init__(self, data: Dict[str, Any], priority: ConfigPriority = ConfigPriority.RUNTIME):
        super().__init__(priority, f"dict:{id(data)}")
        self._data = data.copy()
        self._is_loaded = True
        self._last_modified = datetime.now()
        
    def load(self) -> Dict[str, Any]:
        """加载配置数据"""
        return self._data.copy()
        
    def reload(self) -> Dict[str, Any]:
        """重新加载配置数据"""
        return self.load()
        
    def update(self, data: Dict[str, Any], notify: bool = True):
        """更新配置数据"""
        old_data = self._data.copy()
        self._data.update(data)
        self._last_modified = datetime.now()
        
        if notify:
            # 通知变更
            for key, new_value in data.items():
                old_value = old_data.get(key)
                if old_value != new_value:
                    change = ConfigChange(
                        key=key,
                        old_value=old_value,
                        new_value=new_value,
                        source=f"dict:{id(self)}",
                        priority=self._priority
                    )
                    self._notify_change(change)


class FileConfigSource(BaseConfigSource):
    """文件配置源 - 支持多种格式和文件监听"""
    
    SUPPORTED_FORMATS = {
        '.yaml': 'yaml',
        '.yml': 'yaml', 
        '.json': 'json',
        '.toml': 'toml',
        '.ini': 'ini'
    }
    
    def __init__(self, 
                 file_path: Path, 
                 priority: ConfigPriority = ConfigPriority.FILE,
                 encoding: str = 'utf-8',
                 auto_reload: bool = True,
                 watcher_config: Optional[WatcherConfig] = None):
        super().__init__(priority, f"file:{file_path}")
        self.file_path = Path(file_path)
        self.encoding = encoding
        self.auto_reload = auto_reload
        self.watcher_config = watcher_config or WatcherConfig()
        
        # 文件监听
        self._watcher_task: Optional[asyncio.Task] = None
        self._stop_watching = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=1)
        
        # 确定文件格式
        self._format = self._detect_format()
        
    def _detect_format(self) -> str:
        """检测文件格式"""
        suffix = self.file_path.suffix.lower()
        return self.SUPPORTED_FORMATS.get(suffix, 'yaml')
        
    def load(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if not self.file_path.exists():
                logger.warning(f"Config file not found: {self.file_path}")
                return {}
                
            with open(self.file_path, 'r', encoding=self.encoding) as f:
                if self._format == 'yaml':
                    data = yaml.safe_load(f) or {}
                elif self._format == 'json':
                    data = json.load(f)
                else:
                    logger.warning(f"Unsupported format: {self._format}")
                    return {}
                    
            self._last_modified = datetime.fromtimestamp(self.file_path.stat().st_mtime)
            self._is_loaded = True
            
            logger.debug(f"Loaded config from {self.file_path}: {len(data)} keys")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load config from {self.file_path}: {e}")
            return {}
            
    def reload(self) -> Dict[str, Any]:
        """重新加载配置文件"""
        if not self.file_path.exists():
            return {}
            
        # 检查文件是否被修改
        try:
            current_mtime = datetime.fromtimestamp(self.file_path.stat().st_mtime)
            if self._last_modified and current_mtime <= self._last_modified:
                return self._data  # 文件未修改，返回缓存数据
        except OSError:
            pass
            
        old_data = self._data.copy()
        new_data = self.load()
        
        # 检测变更并通知
        self._detect_and_notify_changes(old_data, new_data)
        
        self._data = new_data
        return new_data
        
    def _detect_and_notify_changes(self, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        """检测并通知配置变更"""
        all_keys = set(old_data.keys()) | set(new_data.keys())
        
        for key in all_keys:
            old_value = old_data.get(key)
            new_value = new_data.get(key)
            
            if old_value != new_value:
                change = ConfigChange(
                    key=key,
                    old_value=old_value,
                    new_value=new_value,
                    source=str(self.file_path),
                    priority=self._priority
                )
                self._notify_change(change)
                
    async def start_watching(self):
        """开始监听文件变更"""
        if not self.auto_reload or not self.watcher_config.enabled:
            return
            
        if self._watcher_task and not self._watcher_task.done():
            return  # 已在监听
            
        self._stop_watching.clear()
        self._watcher_task = asyncio.create_task(self._watch_file())
        logger.debug(f"Started watching config file: {self.file_path}")
        
    async def stop_watching(self):
        """停止监听文件变更"""
        self._stop_watching.set()
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
        logger.debug(f"Stopped watching config file: {self.file_path}")
        
    async def _watch_file(self):
        """文件监听循环"""
        last_check = 0
        
        while not self._stop_watching.is_set():
            try:
                await asyncio.sleep(self.watcher_config.poll_interval)
                
                if not self.file_path.exists():
                    continue
                    
                current_mtime = self.file_path.stat().st_mtime
                if current_mtime > last_check:
                    # 等待去抖延迟
                    await asyncio.sleep(self.watcher_config.debounce_delay)
                    
                    # 重新检查，确保文件稳定
                    if self.file_path.exists() and self.file_path.stat().st_mtime >= current_mtime:
                        await asyncio.get_event_loop().run_in_executor(
                            self._executor, self.reload
                        )
                        last_check = current_mtime
                        
            except Exception as e:
                logger.error(f"Error watching config file {self.file_path}: {e}")
                await asyncio.sleep(5)  # 出错时等待更长时间


class EnvironmentConfigSource(BaseConfigSource):
    """环境变量配置源"""
    
    def __init__(self, 
                 prefix: str = "AETHERIUS_",
                 priority: ConfigPriority = ConfigPriority.ENVIRONMENT,
                 separator: str = "_",
                 case_sensitive: bool = False):
        super().__init__(priority, f"env:{prefix}")
        self.prefix = prefix
        self.separator = separator
        self.case_sensitive = case_sensitive
        
    def load(self) -> Dict[str, Any]:
        """从环境变量加载配置"""
        data = {}
        prefix_len = len(self.prefix)
        
        for key, value in os.environ.items():
            if not key.startswith(self.prefix):
                continue
                
            # 移除前缀并转换为配置键
            config_key = key[prefix_len:]
            if not self.case_sensitive:
                config_key = config_key.lower()
                
            # 转换分隔符为点号（用于嵌套配置）
            config_key = config_key.replace(self.separator, '.')
            
            # 尝试解析值类型
            parsed_value = self._parse_env_value(value)
            
            # 设置嵌套字典
            self._set_nested_value(data, config_key, parsed_value)
            
        self._is_loaded = True
        self._last_modified = datetime.now()
        
        logger.debug(f"Loaded {len(data)} environment variables with prefix '{self.prefix}'")
        return data
        
    def reload(self) -> Dict[str, Any]:
        """重新加载环境变量"""
        return self.load()
        
    def _parse_env_value(self, value: str) -> Any:
        """解析环境变量值类型"""
        # 布尔值
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
            
        # 数字
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
            
        # JSON
        if value.startswith(('{', '[', '"')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
                
        # 列表（逗号分隔）
        if ',' in value:
            return [item.strip() for item in value.split(',')]
            
        return value
        
    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any):
        """设置嵌套字典值"""
        keys = key.split('.')
        current = data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            elif not isinstance(current[k], dict):
                # 如果不是字典，转换为字典
                current[k] = {'value': current[k]}
            current = current[k]
            
        current[keys[-1]] = value


class RemoteConfigSource(BaseConfigSource):
    """远程配置源 - 从HTTP端点加载配置"""
    
    def __init__(self, 
                 url: str,
                 priority: ConfigPriority = ConfigPriority.FILE,
                 headers: Optional[Dict[str, str]] = None,
                 timeout: float = 30.0,
                 retry_count: int = 3,
                 refresh_interval: Optional[float] = None):
        super().__init__(priority)
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.retry_count = retry_count
        self.refresh_interval = refresh_interval
        
        # 自动刷新任务
        self._refresh_task: Optional[asyncio.Task] = None
        self._stop_refresh = threading.Event()
        
    async def load_async(self) -> Dict[str, Any]:
        """异步加载远程配置"""
        import aiohttp
        
        for attempt in range(self.retry_count):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.get(self.url, headers=self.headers) as response:
                        if response.status == 200:
                            content_type = response.headers.get('content-type', '')
                            
                            if 'application/json' in content_type:
                                data = await response.json()
                            elif 'application/yaml' in content_type or 'text/yaml' in content_type:
                                text = await response.text()
                                data = yaml.safe_load(text)
                            else:
                                text = await response.text()
                                try:
                                    data = yaml.safe_load(text)
                                except:
                                    data = json.loads(text)
                                    
                            self._data = data
                            self._is_loaded = True
                            self._last_modified = datetime.now()
                            
                            logger.debug(f"Loaded remote config from {self.url}: {len(data)} keys")
                            return data
                        else:
                            logger.warning(f"Remote config returned {response.status}: {self.url}")
                            
            except Exception as e:
                logger.warning(f"Failed to load remote config (attempt {attempt + 1}): {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    
        logger.error(f"Failed to load remote config after {self.retry_count} attempts: {self.url}")
        return {}
        
    def load(self) -> Dict[str, Any]:
        """同步加载（使用事件循环）"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.load_async())
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(self.load_async())
            
    def reload(self) -> Dict[str, Any]:
        """重新加载远程配置"""
        return self.load()
        
    async def start_auto_refresh(self):
        """开始自动刷新"""
        if not self.refresh_interval or self.refresh_interval <= 0:
            return
            
        if self._refresh_task and not self._refresh_task.done():
            return
            
        self._stop_refresh.clear()
        self._refresh_task = asyncio.create_task(self._auto_refresh_loop())
        logger.debug(f"Started auto-refresh for remote config: {self.url}")
        
    async def stop_auto_refresh(self):
        """停止自动刷新"""
        self._stop_refresh.set()
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        logger.debug(f"Stopped auto-refresh for remote config: {self.url}")
        
    async def _auto_refresh_loop(self):
        """自动刷新循环"""
        while not self._stop_refresh.is_set():
            try:
                await asyncio.sleep(self.refresh_interval)
                old_data = self._data.copy()
                new_data = await self.load_async()
                
                # 检测变更并通知
                if old_data != new_data:
                    self._detect_and_notify_changes(old_data, new_data)
                    
            except Exception as e:
                logger.error(f"Error in auto-refresh loop for {self.url}: {e}")
                await asyncio.sleep(60)  # 出错时等待1分钟
                
    def _detect_and_notify_changes(self, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        """检测并通知配置变更"""
        all_keys = set(self._flatten_dict(old_data).keys()) | set(self._flatten_dict(new_data).keys())
        
        flat_old = self._flatten_dict(old_data)
        flat_new = self._flatten_dict(new_data)
        
        for key in all_keys:
            old_value = flat_old.get(key)
            new_value = flat_new.get(key)
            
            if old_value != new_value:
                change = ConfigChange(
                    key=key,
                    old_value=old_value,
                    new_value=new_value,
                    source=self.url,
                    priority=self._priority
                )
                self._notify_change(change)
                
    def _flatten_dict(self, data: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """扁平化嵌套字典"""
        items = []
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


class CompositeConfigSource(BaseConfigSource):
    """复合配置源 - 组合多个配置源"""
    
    def __init__(self, sources: List[IConfigSource], priority: ConfigPriority = ConfigPriority.FILE):
        super().__init__(priority)
        self.sources = sorted(sources, key=lambda s: s.get_priority().value)
        
        # 订阅所有源的变更通知
        for source in self.sources:
            if hasattr(source, 'add_change_callback'):
                source.add_change_callback(self._on_source_change)
                
    def load(self) -> Dict[str, Any]:
        """合并所有源的配置"""
        merged_data = {}
        
        for source in self.sources:
            try:
                source_data = source.load()
                merged_data.update(source_data)
            except Exception as e:
                logger.error(f"Failed to load from config source {source}: {e}")
                
        self._data = merged_data
        self._is_loaded = True
        self._last_modified = datetime.now()
        
        logger.debug(f"Merged config from {len(self.sources)} sources: {len(merged_data)} keys")
        return merged_data
        
    def reload(self) -> Dict[str, Any]:
        """重新加载所有配置源"""
        return self.load()
        
    def _on_source_change(self, change: ConfigChange):
        """处理源配置变更"""
        # 重新加载并通知变更
        old_data = self._data.copy()
        new_data = self.load()
        
        # 检查这个特定键是否真的变更了
        old_value = self._get_nested_value(old_data, change.key)
        new_value = self._get_nested_value(new_data, change.key)
        
        if old_value != new_value:
            updated_change = ConfigChange(
                key=change.key,
                old_value=old_value,
                new_value=new_value,
                source=f"composite:{change.source}",
                priority=self._priority
            )
            self._notify_change(updated_change)
            
    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """获取嵌套字典值"""
        keys = key.split('.')
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
                
        return current


# 工厂函数
def create_file_source(file_path: str, **kwargs) -> FileConfigSource:
    """创建文件配置源"""
    return FileConfigSource(Path(file_path), **kwargs)


def create_env_source(prefix: str = "AETHERIUS_", **kwargs) -> EnvironmentConfigSource:
    """创建环境变量配置源"""
    return EnvironmentConfigSource(prefix, **kwargs)


def create_remote_source(url: str, **kwargs) -> RemoteConfigSource:
    """创建远程配置源"""
    return RemoteConfigSource(url, **kwargs)


def create_composite_source(sources: List[IConfigSource], **kwargs) -> CompositeConfigSource:
    """创建复合配置源"""
    return CompositeConfigSource(sources, **kwargs)
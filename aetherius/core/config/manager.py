"""
配置管理器实现

提供功能完整的配置管理实现
"""

import os
import re
import threading
import json
import yaml
from typing import Any, Dict, List, Optional, Union, Callable, Pattern, Set
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .interfaces import (
    IConfigManager, IConfigSource, IConfigValidator, IConfigWatcher,
    IConfigEncryption, IConfigTemplate, ConfigPriority, ConfigFormat,
    ConfigChange, ConfigDescriptor, ConfigError, ConfigValidationError
)

logger = logging.getLogger(__name__)


class ConfigManager(IConfigManager):
    """配置管理器实现"""
    
    def __init__(self, 
                 enable_watching: bool = True,
                 encryption: Optional[IConfigEncryption] = None,
                 template_engine: Optional[IConfigTemplate] = None):
        self._sources: List[IConfigSource] = []
        self._validators: Dict[Pattern, IConfigValidator] = {}
        self._watchers: Dict[Pattern, List[IConfigWatcher]] = defaultdict(list)
        self._config_cache: Dict[str, Any] = {}
        self._descriptors: Dict[str, ConfigDescriptor] = {}
        self._lock = threading.RLock()
        self._enable_watching = enable_watching
        self._encryption = encryption
        self._template_engine = template_engine
        self._watch_tasks: Set[asyncio.Task] = set()
        
        # 配置变更历史
        self._change_history: List[ConfigChange] = []
        self._max_history_size = 1000
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        with self._lock:
            # 检查缓存
            if key in self._config_cache:
                value = self._config_cache[key]
            else:
                value = self._load_value(key)
                if value is not None:
                    self._config_cache[key] = value
            
            if value is None:
                return default
            
            # 解密敏感配置
            if self._encryption and isinstance(value, str):
                if self._encryption.is_encrypted(value):
                    try:
                        value = self._encryption.decrypt(value)
                    except Exception as e:
                        logger.warning(f"Failed to decrypt config {key}: {e}")
                        return default
            
            # 模板渲染
            if self._template_engine and isinstance(value, str):
                try:
                    value = self._template_engine.render(value, self._config_cache)
                except Exception as e:
                    logger.warning(f"Failed to render template for {key}: {e}")
            
            # 验证
            validated_value = self._validate_value(key, value)
            if validated_value != value:
                self._config_cache[key] = validated_value
                value = validated_value
            
            return value
    
    def set(self, key: str, value: Any, priority: ConfigPriority = ConfigPriority.RUNTIME):
        """设置配置值"""
        with self._lock:
            old_value = self._config_cache.get(key)
            
            # 验证新值
            validated_value = self._validate_value(key, value)
            
            # 加密敏感配置
            if self._encryption and self._is_sensitive(key) and isinstance(validated_value, str):
                if not self._encryption.is_encrypted(validated_value):
                    validated_value = self._encryption.encrypt(validated_value)
            
            # 更新缓存
            self._config_cache[key] = validated_value
            
            # 尝试保存到可写的配置源
            self._save_to_source(key, validated_value, priority)
            
            # 记录变更
            change = ConfigChange(
                key=key,
                old_value=old_value,
                new_value=validated_value,
                source="runtime",
                priority=priority
            )
            self._add_change_history(change)
            
            # 通知监听器
            self._notify_watchers(change)
    
    def has(self, key: str) -> bool:
        """检查配置是否存在"""
        return self.get(key) is not None
    
    def delete(self, key: str) -> bool:
        """删除配置"""
        with self._lock:
            if key in self._config_cache:
                old_value = self._config_cache[key]
                del self._config_cache[key]
                
                # 记录变更
                change = ConfigChange(
                    key=key,
                    old_value=old_value,
                    new_value=None,
                    source="runtime",
                    priority=ConfigPriority.RUNTIME
                )
                self._add_change_history(change)
                self._notify_watchers(change)
                
                return True
            return False
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置段"""
        section_config = {}
        prefix = f"{section}."
        
        # 从所有源加载
        all_config = self._load_all_config()
        
        for key, value in all_config.items():
            if key.startswith(prefix):
                section_key = key[len(prefix):]
                section_config[section_key] = self.get(key)
        
        return section_config
    
    def reload(self):
        """重新加载配置"""
        with self._lock:
            logger.info("Reloading configuration...")
            
            old_config = self._config_cache.copy()
            self._config_cache.clear()
            
            # 重新加载所有源
            new_config = self._load_all_config()
            
            # 检测变更
            all_keys = set(old_config.keys()) | set(new_config.keys())
            for key in all_keys:
                old_value = old_config.get(key)
                new_value = new_config.get(key)
                
                if old_value != new_value:
                    change = ConfigChange(
                        key=key,
                        old_value=old_value,
                        new_value=new_value,
                        source="reload",
                        priority=ConfigPriority.FILE
                    )
                    self._add_change_history(change)
                    self._notify_watchers(change)
            
            logger.info(f"Configuration reloaded. {len(all_keys)} keys processed.")
    
    def add_source(self, source: IConfigSource):
        """添加配置源"""
        with self._lock:
            self._sources.append(source)
            # 按优先级排序
            self._sources.sort(key=lambda s: s.priority.value)
            
            # 如果启用监听且源支持，则设置监听
            if self._enable_watching and hasattr(source, 'watch'):
                try:
                    source.watch(self._on_source_changed)
                except Exception as e:
                    logger.warning(f"Failed to setup watching for source {source.name}: {e}")
        
        logger.info(f"Added config source: {source.name} (priority: {source.priority.value})")
    
    def add_validator(self, key_pattern: str, validator: IConfigValidator):
        """添加验证器"""
        pattern = re.compile(key_pattern)
        self._validators[pattern] = validator
        logger.info(f"Added validator for pattern: {key_pattern}")
    
    def add_watcher(self, key_pattern: str, watcher: IConfigWatcher):
        """添加监听器"""
        pattern = re.compile(key_pattern)
        self._watchers[pattern].append(watcher)
        logger.info(f"Added watcher for pattern: {key_pattern}")
    
    def export(self, format: ConfigFormat, file_path: Optional[Path] = None) -> str:
        """导出配置"""
        all_config = self._load_all_config()
        
        if format == ConfigFormat.YAML:
            content = yaml.dump(all_config, default_flow_style=False, allow_unicode=True)
        elif format == ConfigFormat.JSON:
            content = json.dumps(all_config, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        if file_path:
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"Configuration exported to {file_path}")
        
        return content
    
    def register_descriptor(self, descriptor: ConfigDescriptor):
        """注册配置描述符"""
        self._descriptors[descriptor.key] = descriptor
        logger.debug(f"Registered config descriptor: {descriptor.key}")
    
    def get_descriptors(self, section: Optional[str] = None) -> List[ConfigDescriptor]:
        """获取配置描述符"""
        if section:
            prefix = f"{section}."
            return [desc for key, desc in self._descriptors.items() 
                   if key.startswith(prefix)]
        return list(self._descriptors.values())
    
    def validate_all(self) -> List[str]:
        """验证所有配置"""
        errors = []
        all_config = self._load_all_config()
        
        for key, value in all_config.items():
            try:
                self._validate_value(key, value)
            except ConfigValidationError as e:
                errors.append(f"{key}: {e}")
        
        # 检查必需配置
        for descriptor in self._descriptors.values():
            if descriptor.required and not self.has(descriptor.key):
                errors.append(f"{descriptor.key}: Required configuration is missing")
        
        return errors
    
    def get_change_history(self, limit: Optional[int] = None) -> List[ConfigChange]:
        """获取配置变更历史"""
        with self._lock:
            if limit:
                return self._change_history[-limit:]
            return self._change_history.copy()
    
    def _load_value(self, key: str) -> Any:
        """从配置源加载值"""
        # 按优先级从高到低查找
        for source in reversed(self._sources):
            try:
                config = source.load()
                if key in config:
                    return config[key]
                
                # 支持嵌套键查找 (e.g., "database.host")
                value = self._get_nested_value(config, key)
                if value is not None:
                    return value
            except Exception as e:
                logger.warning(f"Error loading from source {source.name}: {e}")
        
        return None
    
    def _load_all_config(self) -> Dict[str, Any]:
        """加载所有配置"""
        merged_config = {}
        
        # 按优先级从低到高合并
        for source in self._sources:
            try:
                config = source.load()
                self._merge_config(merged_config, config)
            except Exception as e:
                logger.warning(f"Error loading from source {source.name}: {e}")
        
        return merged_config
    
    def _get_nested_value(self, config: Dict[str, Any], key: str) -> Any:
        """获取嵌套配置值"""
        keys = key.split('.')
        current = config
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        
        return current
    
    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any], prefix: str = ""):
        """合并配置字典"""
        for key, value in source.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                # 递归合并嵌套字典
                if full_key not in target:
                    target[full_key] = {}
                if isinstance(target[full_key], dict):
                    self._merge_config(target, value, full_key)
                else:
                    target[full_key] = value
            else:
                target[full_key] = value
    
    def _validate_value(self, key: str, value: Any) -> Any:
        """验证配置值"""
        for pattern, validator in self._validators.items():
            if pattern.match(key):
                try:
                    return validator.validate(key, value, self._config_cache)
                except Exception as e:
                    raise ConfigValidationError(f"Validation failed for {key}: {e}")
        
        return value
    
    def _save_to_source(self, key: str, value: Any, priority: ConfigPriority):
        """保存到配置源"""
        # 查找可写的配置源
        for source in self._sources:
            if source.is_writable() and source.priority == priority:
                try:
                    config = source.load()
                    config[key] = value
                    source.save(config)
                    logger.debug(f"Saved {key} to source {source.name}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to save to source {source.name}: {e}")
    
    def _is_sensitive(self, key: str) -> bool:
        """检查配置是否敏感"""
        descriptor = self._descriptors.get(key)
        if descriptor:
            return descriptor.sensitive
        
        # 根据键名判断
        sensitive_patterns = ['password', 'secret', 'key', 'token', 'credential']
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in sensitive_patterns)
    
    def _notify_watchers(self, change: ConfigChange):
        """通知配置监听器"""
        for pattern, watchers in self._watchers.items():
            if pattern.match(change.key):
                for watcher in watchers:
                    try:
                        watcher.on_config_changed(change)
                    except Exception as e:
                        logger.error(f"Error in config watcher: {e}")
    
    def _add_change_history(self, change: ConfigChange):
        """添加变更历史"""
        self._change_history.append(change)
        
        # 限制历史记录大小
        if len(self._change_history) > self._max_history_size:
            self._change_history = self._change_history[-self._max_history_size:]
    
    def _on_source_changed(self, source_config: Dict[str, Any]):
        """配置源变更回调"""
        logger.info("Config source changed, triggering reload...")
        try:
            self.reload()
        except Exception as e:
            logger.error(f"Error during config reload: {e}")


class FileConfigSource(IConfigSource):
    """文件配置源"""
    
    def __init__(self, 
                 file_path: Path, 
                 format: ConfigFormat,
                 priority: ConfigPriority = ConfigPriority.FILE,
                 writable: bool = True,
                 watch: bool = True):
        self.file_path = file_path
        self.format = format
        self._priority = priority
        self._writable = writable
        self._watch = watch
        self._watch_callback: Optional[Callable] = None
        self._watch_task: Optional[asyncio.Task] = None
    
    @property
    def priority(self) -> ConfigPriority:
        return self._priority
    
    @property
    def name(self) -> str:
        return f"file:{self.file_path.name}"
    
    def load(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.file_path.exists():
            return {}
        
        try:
            content = self.file_path.read_text(encoding='utf-8')
            
            if self.format == ConfigFormat.YAML:
                return yaml.safe_load(content) or {}
            elif self.format == ConfigFormat.JSON:
                return json.loads(content) or {}
            else:
                raise ValueError(f"Unsupported format: {self.format}")
        
        except Exception as e:
            logger.error(f"Failed to load config from {self.file_path}: {e}")
            return {}
    
    def save(self, config: Dict[str, Any]) -> bool:
        """保存配置文件"""
        if not self._writable:
            return False
        
        try:
            if self.format == ConfigFormat.YAML:
                content = yaml.dump(config, default_flow_style=False, allow_unicode=True)
            elif self.format == ConfigFormat.JSON:
                content = json.dumps(config, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"Unsupported format: {self.format}")
            
            # 确保目录存在
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 原子写入
            temp_file = self.file_path.with_suffix(f"{self.file_path.suffix}.tmp")
            temp_file.write_text(content, encoding='utf-8')
            temp_file.replace(self.file_path)
            
            logger.debug(f"Saved config to {self.file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save config to {self.file_path}: {e}")
            return False
    
    def watch(self, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """监听文件变化"""
        if not self._watch:
            return False
        
        self._watch_callback = callback
        
        # 启动文件监听任务
        if self._watch_task is None or self._watch_task.done():
            loop = asyncio.get_event_loop()
            self._watch_task = loop.create_task(self._watch_file())
        
        return True
    
    def is_writable(self) -> bool:
        return self._writable
    
    async def _watch_file(self):
        """文件监听任务"""
        import time
        
        last_mtime = 0
        
        while True:
            try:
                if self.file_path.exists():
                    current_mtime = self.file_path.stat().st_mtime
                    if current_mtime != last_mtime:
                        last_mtime = current_mtime
                        if self._watch_callback:
                            config = self.load()
                            self._watch_callback(config)
                
                await asyncio.sleep(1)  # 检查间隔
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in file watcher: {e}")
                await asyncio.sleep(5)


class EnvironmentConfigSource(IConfigSource):
    """环境变量配置源"""
    
    def __init__(self, 
                 prefix: str = "",
                 priority: ConfigPriority = ConfigPriority.ENVIRONMENT):
        self.prefix = prefix.upper()
        self._priority = priority
    
    @property
    def priority(self) -> ConfigPriority:
        return self._priority
    
    @property
    def name(self) -> str:
        return f"env:{self.prefix or 'all'}"
    
    def load(self) -> Dict[str, Any]:
        """加载环境变量"""
        config = {}
        
        for key, value in os.environ.items():
            if not self.prefix or key.startswith(self.prefix):
                config_key = key
                if self.prefix:
                    config_key = key[len(self.prefix):].lstrip('_')
                
                # 转换为小写并替换下划线为点
                config_key = config_key.lower().replace('_', '.')
                
                # 尝试类型转换
                config[config_key] = self._convert_value(value)
        
        return config
    
    def save(self, config: Dict[str, Any]) -> bool:
        """环境变量不支持保存"""
        return False
    
    def watch(self, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """环境变量不支持监听"""
        return False
    
    def is_writable(self) -> bool:
        return False
    
    def _convert_value(self, value: str) -> Any:
        """尝试转换环境变量值的类型"""
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
        
        return value
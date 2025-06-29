"""
配置系统接口定义

提供高度可扩展的配置管理框架，支持：
- 多层级配置源（默认值、文件、环境变量、运行时）
- 配置验证和类型转换
- 热重载和变更通知
- 配置模板和继承
- 加密敏感配置
"""

from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Generic, Protocol
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import asyncio

T = TypeVar('T')


class ConfigPriority(Enum):
    """配置优先级枚举"""
    DEFAULT = 0         # 默认值
    FILE = 100         # 配置文件
    ENVIRONMENT = 200  # 环境变量
    RUNTIME = 300      # 运行时设置
    OVERRIDE = 400     # 强制覆盖


class ConfigFormat(Enum):
    """配置文件格式"""
    YAML = "yaml"
    JSON = "json"
    TOML = "toml"
    INI = "ini"
    XML = "xml"


@dataclass
class ConfigChange:
    """配置变更事件"""
    key: str
    old_value: Any
    new_value: Any
    source: str
    priority: ConfigPriority
    timestamp: float = field(default_factory=lambda: __import__('time').time())


class IConfigSource(Protocol):
    """配置源接口"""
    
    @property
    def priority(self) -> ConfigPriority:
        """配置源优先级"""
        ...
    
    @property
    def name(self) -> str:
        """配置源名称"""
        ...
    
    def load(self) -> Dict[str, Any]:
        """加载配置"""
        ...
    
    def save(self, config: Dict[str, Any]) -> bool:
        """保存配置（如果支持）"""
        ...
    
    def watch(self, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """监听配置变化（如果支持）"""
        ...
    
    def is_writable(self) -> bool:
        """是否支持写入"""
        ...


class IConfigValidator(Protocol):
    """配置验证器接口"""
    
    def validate(self, key: str, value: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """验证并转换配置值"""
        ...
    
    def get_schema(self) -> Dict[str, Any]:
        """获取配置模式"""
        ...


class IConfigWatcher(Protocol):
    """配置监听器接口"""
    
    def on_config_changed(self, change: ConfigChange):
        """配置变更回调"""
        ...


class IConfigEncryption(Protocol):
    """配置加密接口"""
    
    def encrypt(self, value: str) -> str:
        """加密配置值"""
        ...
    
    def decrypt(self, encrypted_value: str) -> str:
        """解密配置值"""
        ...
    
    def is_encrypted(self, value: str) -> bool:
        """检查值是否已加密"""
        ...


class IConfigTemplate(Protocol):
    """配置模板接口"""
    
    def render(self, template: str, context: Dict[str, Any]) -> str:
        """渲染配置模板"""
        ...
    
    def extract_variables(self, template: str) -> List[str]:
        """提取模板变量"""
        ...


class IConfigManager(Protocol):
    """配置管理器接口"""
    
    def get(self, key: str, default: T = None) -> Union[T, Any]:
        """获取配置值"""
        ...
    
    def set(self, key: str, value: Any, priority: ConfigPriority = ConfigPriority.RUNTIME):
        """设置配置值"""
        ...
    
    def has(self, key: str) -> bool:
        """检查配置是否存在"""
        ...
    
    def delete(self, key: str) -> bool:
        """删除配置"""
        ...
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置段"""
        ...
    
    def reload(self):
        """重新加载配置"""
        ...
    
    def add_source(self, source: IConfigSource):
        """添加配置源"""
        ...
    
    def add_validator(self, key_pattern: str, validator: IConfigValidator):
        """添加验证器"""
        ...
    
    def add_watcher(self, key_pattern: str, watcher: IConfigWatcher):
        """添加监听器"""
        ...
    
    def export(self, format: ConfigFormat, file_path: Optional[Path] = None) -> str:
        """导出配置"""
        ...


@dataclass
class ConfigDescriptor:
    """配置描述符"""
    key: str
    description: str
    data_type: type
    default_value: Any = None
    required: bool = False
    sensitive: bool = False  # 敏感信息，需要加密
    validation_rules: List[str] = field(default_factory=list)
    examples: List[Any] = field(default_factory=list)
    deprecated: bool = False
    tags: List[str] = field(default_factory=list)


class ConfigSection(Generic[T]):
    """配置段基类"""
    
    def __init__(self, manager: IConfigManager, section_name: str):
        self._manager = manager
        self._section_name = section_name
    
    def _get_key(self, key: str) -> str:
        """构建完整配置键"""
        return f"{self._section_name}.{key}"
    
    def get(self, key: str, default: T = None) -> T:
        """获取配置值"""
        return self._manager.get(self._get_key(key), default)
    
    def set(self, key: str, value: T, priority: ConfigPriority = ConfigPriority.RUNTIME):
        """设置配置值"""
        self._manager.set(self._get_key(key), value, priority)
    
    def has(self, key: str) -> bool:
        """检查配置是否存在"""
        return self._manager.has(self._get_key(key))


class ConfigError(Exception):
    """配置错误基类"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证错误"""
    pass


class ConfigSourceError(ConfigError):
    """配置源错误"""
    pass


class ConfigWatchError(ConfigError):
    """配置监听错误"""
    pass
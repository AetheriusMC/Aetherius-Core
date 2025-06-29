"""
Aetherius Core 配置管理模块

提供分层配置管理功能，支持：
- 多源配置（文件、环境变量、运行时）
- 配置验证和类型检查
- 热重载和变更通知
- 模板渲染和插值
"""

from .interfaces import (
    IConfigSource, IConfigManager, ConfigPriority,
    ConfigChange, ConfigFormat
)
from .manager import ConfigManager
from .validation import IConfigValidator, SchemaValidator, SimpleTemplateEngine, AETHERIUS_CONFIG_SCHEMA
from .sources import DictConfigSource, FileConfigSource, EnvironmentConfigSource

# 兼容性：导入旧的配置管理器
try:
    from ..config import get_config_manager
except ImportError:
    # 如果旧的配置管理器不可用，提供一个简单的兼容函数
    def get_config_manager(config_path=None):
        """兼容性函数：获取配置管理器"""
        return ConfigManager()

__all__ = [
    'IConfigSource', 'IConfigManager', 'ConfigPriority',
    'ConfigChange', 'ConfigFormat', 'ConfigManager', 'IConfigValidator', 'SchemaValidator', 'SimpleTemplateEngine', 'AETHERIUS_CONFIG_SCHEMA',
    'DictConfigSource', 'FileConfigSource', 'EnvironmentConfigSource', 'get_config_manager'
]
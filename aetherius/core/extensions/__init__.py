"""
Aetherius Core 扩展系统

提供统一的插件和组件接口标准，支持：
- 统一的生命周期管理
- 依赖注入集成
- 事件系统集成
- 配置管理集成
- 热重载支持
- 版本兼容性检查
- 安全沙箱
"""

from typing import Any, Dict, List, Optional, Set, Union, Type, Callable, Protocol
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import asyncio
import inspect
from packaging import version

__all__ = [
    'ExtensionType', 'ExtensionState', 'ExtensionInfo', 'ExtensionContext',
    'IExtension', 'IPlugin', 'IComponent', 'IExtensionLoader', 
    'IExtensionManager', 'ExtensionError', 'extension_info', 
    'plugin', 'component', 'depends_on', 'provides_service'
]


class ExtensionType(Enum):
    """扩展类型枚举"""
    PLUGIN = "plugin"           # 插件：轻量级功能扩展
    COMPONENT = "component"     # 组件：重量级模块化扩展
    MIDDLEWARE = "middleware"   # 中间件：处理管道扩展
    PROVIDER = "provider"       # 提供者：服务提供扩展
    HANDLER = "handler"         # 处理器：事件处理扩展


class ExtensionState(Enum):
    """扩展状态枚举"""
    UNLOADED = "unloaded"       # 未加载
    LOADING = "loading"         # 加载中
    LOADED = "loaded"           # 已加载
    STARTING = "starting"       # 启动中
    RUNNING = "running"         # 运行中
    STOPPING = "stopping"       # 停止中
    STOPPED = "stopped"         # 已停止
    ERROR = "error"             # 错误状态
    DISABLED = "disabled"       # 已禁用


@dataclass
class ExtensionInfo:
    """扩展信息"""
    name: str                                    # 扩展名称
    version: str                                 # 版本号
    display_name: Optional[str] = None           # 显示名称
    description: Optional[str] = None            # 描述
    author: Optional[str] = None                 # 作者
    website: Optional[str] = None                # 网站
    license: Optional[str] = None                # 许可证
    
    # 依赖关系
    dependencies: List[str] = field(default_factory=list)       # 强依赖
    soft_dependencies: List[str] = field(default_factory=list)  # 软依赖
    conflicts: List[str] = field(default_factory=list)          # 冲突
    
    # 兼容性
    aetherius_version: Optional[str] = None      # 支持的Aetherius版本
    python_version: Optional[str] = None         # Python版本要求
    
    # 分类和标签
    category: Optional[str] = None               # 分类
    tags: List[str] = field(default_factory=list)             # 标签
    
    # 权限和安全
    permissions: List[str] = field(default_factory=list)      # 所需权限
    sandbox: bool = False                        # 是否在沙箱中运行
    
    # 元数据
    extension_type: ExtensionType = ExtensionType.PLUGIN
    entry_point: Optional[str] = None            # 入口点
    config_schema: Optional[Dict[str, Any]] = None
    provides: List[str] = field(default_factory=list)         # 提供的服务
    
    # 文件信息
    file_path: Optional[Path] = None
    package_path: Optional[Path] = None


class ExtensionContext:
    """扩展上下文，提供扩展运行时环境"""
    
    def __init__(self, 
                 extension_info: ExtensionInfo,
                 config_manager,
                 event_manager,
                 di_container,
                 logger,
                 data_dir: Path):
        self.info = extension_info
        self.config = config_manager
        self.events = event_manager
        self.services = di_container
        self.logger = logger
        self.data_dir = data_dir
        
        # 扩展私有数据目录
        self.extension_data_dir = data_dir / "extensions" / extension_info.name
        self.extension_data_dir.mkdir(parents=True, exist_ok=True)
    
    def get_config_section(self, section: Optional[str] = None):
        """获取扩展配置段"""
        config_key = f"extensions.{self.info.name}"
        if section:
            config_key += f".{section}"
        return self.config.get_section(config_key)
    
    def get_extension_config(self, key: str, default=None):
        """获取扩展配置"""
        config_key = f"extensions.{self.info.name}.{key}"
        return self.config.get(config_key, default)
    
    def set_extension_config(self, key: str, value):
        """设置扩展配置"""
        config_key = f"extensions.{self.info.name}.{key}"
        self.config.set(config_key, value)


class IExtension(ABC):
    """扩展基接口"""
    
    def __init__(self, context: ExtensionContext):
        self.context = context
        self.state = ExtensionState.UNLOADED
    
    @property
    @abstractmethod
    def info(self) -> ExtensionInfo:
        """扩展信息"""
        pass
    
    @abstractmethod
    async def load(self):
        """加载扩展"""
        pass
    
    @abstractmethod
    async def start(self):
        """启动扩展"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止扩展"""
        pass
    
    @abstractmethod
    async def unload(self):
        """卸载扩展"""
        pass
    
    async def reload(self):
        """重新加载扩展"""
        await self.stop()
        await self.unload()
        await self.load()
        await self.start()
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取扩展健康状态"""
        return {
            "state": self.state.value,
            "name": self.info.name,
            "version": self.info.version,
            "healthy": self.state == ExtensionState.RUNNING
        }


class IPlugin(IExtension):
    """插件接口"""
    
    @abstractmethod
    def get_commands(self) -> Dict[str, Callable]:
        """获取插件提供的命令"""
        pass
    
    @abstractmethod
    def get_event_handlers(self) -> Dict[str, List[Callable]]:
        """获取事件处理器"""
        pass


class IComponent(IExtension):
    """组件接口"""
    
    @abstractmethod
    def get_api_routes(self) -> List[Dict[str, Any]]:
        """获取API路由"""
        pass
    
    @abstractmethod
    def get_web_routes(self) -> List[Dict[str, Any]]:
        """获取Web路由"""
        pass
    
    @abstractmethod
    def get_services(self) -> Dict[Type, Any]:
        """获取提供的服务"""
        pass


class IExtensionLoader(ABC):
    """扩展加载器接口"""
    
    @abstractmethod
    def can_load(self, path: Path) -> bool:
        """检查是否可以加载指定路径的扩展"""
        pass
    
    @abstractmethod
    async def load_extension(self, path: Path, context: ExtensionContext) -> IExtension:
        """加载扩展"""
        pass
    
    @abstractmethod
    def get_extension_info(self, path: Path) -> Optional[ExtensionInfo]:
        """获取扩展信息"""
        pass


class IExtensionManager(ABC):
    """扩展管理器接口"""
    
    @abstractmethod
    async def discover_extensions(self, directories: List[Path]) -> List[ExtensionInfo]:
        """发现扩展"""
        pass
    
    @abstractmethod
    async def load_extension(self, name: str) -> bool:
        """加载扩展"""
        pass
    
    @abstractmethod
    async def unload_extension(self, name: str) -> bool:
        """卸载扩展"""
        pass
    
    @abstractmethod
    async def start_extension(self, name: str) -> bool:
        """启动扩展"""
        pass
    
    @abstractmethod
    async def stop_extension(self, name: str) -> bool:
        """停止扩展"""
        pass
    
    @abstractmethod
    async def reload_extension(self, name: str) -> bool:
        """重新加载扩展"""
        pass
    
    @abstractmethod
    def get_extension(self, name: str) -> Optional[IExtension]:
        """获取扩展实例"""
        pass
    
    @abstractmethod
    def get_extensions(self, 
                      extension_type: Optional[ExtensionType] = None,
                      state: Optional[ExtensionState] = None) -> List[IExtension]:
        """获取扩展列表"""
        pass
    
    @abstractmethod
    def check_dependencies(self, extension_info: ExtensionInfo) -> List[str]:
        """检查依赖关系"""
        pass


class ExtensionError(Exception):
    """扩展错误基类"""
    
    def __init__(self, message: str, extension_name: Optional[str] = None):
        super().__init__(message)
        self.extension_name = extension_name


class ExtensionLoadError(ExtensionError):
    """扩展加载错误"""
    pass


class ExtensionDependencyError(ExtensionError):
    """扩展依赖错误"""
    pass


class ExtensionVersionError(ExtensionError):
    """扩展版本兼容性错误"""
    pass


# 装饰器和注解
def extension_info(**kwargs):
    """扩展信息装饰器"""
    def decorator(cls):
        # 将信息附加到类
        info = ExtensionInfo(**kwargs)
        cls.__extension_info__ = info
        return cls
    return decorator


def plugin(name: str, version: str, **kwargs):
    """插件装饰器"""
    kwargs.update({
        'name': name,
        'version': version,
        'extension_type': ExtensionType.PLUGIN
    })
    return extension_info(**kwargs)


def component(name: str, version: str, **kwargs):
    """组件装饰器"""
    kwargs.update({
        'name': name,
        'version': version,
        'extension_type': ExtensionType.COMPONENT
    })
    return extension_info(**kwargs)


def depends_on(*dependencies):
    """依赖关系装饰器"""
    def decorator(cls):
        if hasattr(cls, '__extension_info__'):
            cls.__extension_info__.dependencies.extend(dependencies)
        else:
            cls.__dependencies__ = list(dependencies)
        return cls
    return decorator


def provides_service(*services):
    """服务提供装饰器"""
    def decorator(cls):
        if hasattr(cls, '__extension_info__'):
            cls.__extension_info__.provides.extend(services)
        else:
            cls.__provides__ = list(services)
        return cls
    return decorator


# 权限和安全相关
class ExtensionPermission:
    """扩展权限定义"""
    
    # 核心权限
    CORE_ACCESS = "aetherius.core.access"
    CORE_MODIFY = "aetherius.core.modify"
    
    # 服务器权限
    SERVER_START = "aetherius.server.start"
    SERVER_STOP = "aetherius.server.stop"
    SERVER_RESTART = "aetherius.server.restart"
    SERVER_COMMAND = "aetherius.server.command"
    
    # 玩家权限
    PLAYER_READ = "aetherius.player.read"
    PLAYER_MANAGE = "aetherius.player.manage"
    PLAYER_BAN = "aetherius.player.ban"
    PLAYER_KICK = "aetherius.player.kick"
    
    # 文件权限
    FILE_READ = "aetherius.file.read"
    FILE_WRITE = "aetherius.file.write"
    FILE_DELETE = "aetherius.file.delete"
    
    # 配置权限
    CONFIG_READ = "aetherius.config.read"
    CONFIG_WRITE = "aetherius.config.write"
    
    # 网络权限
    NETWORK_ACCESS = "aetherius.network.access"
    NETWORK_BIND = "aetherius.network.bind"
    
    # 系统权限
    SYSTEM_EXEC = "aetherius.system.exec"
    SYSTEM_ENV = "aetherius.system.env"


class ExtensionSandbox:
    """扩展沙箱"""
    
    def __init__(self, permissions: Set[str]):
        self.permissions = permissions
        self.restricted_modules = {
            'os', 'sys', 'subprocess', 'shutil', 'tempfile',
            'socket', 'urllib', 'requests', 'httpx'
        }
        self.allowed_modules = {
            'json', 'yaml', 'time', 'datetime', 'uuid',
            'hashlib', 'base64', 'logging'
        }
    
    def check_permission(self, permission: str) -> bool:
        """检查权限"""
        return permission in self.permissions
    
    def check_module_access(self, module_name: str) -> bool:
        """检查模块访问权限"""
        if module_name in self.allowed_modules:
            return True
        
        if module_name in self.restricted_modules:
            # 检查相应的权限
            if module_name in ('os', 'sys', 'subprocess'):
                return self.check_permission(ExtensionPermission.SYSTEM_EXEC)
            elif module_name in ('socket', 'urllib', 'requests', 'httpx'):
                return self.check_permission(ExtensionPermission.NETWORK_ACCESS)
            else:
                return False
        
        # 其他模块默认允许
        return True


# 版本兼容性检查
class VersionChecker:
    """版本兼容性检查器"""
    
    @staticmethod
    def check_compatibility(required_version: str, current_version: str) -> bool:
        """检查版本兼容性"""
        try:
            required = version.parse(required_version)
            current = version.parse(current_version)
            
            # 简单的兼容性规则：主版本号必须相同，次版本号当前版本>=要求版本
            return (required.major == current.major and 
                   current.minor >= required.minor)
        except Exception:
            return False
    
    @staticmethod
    def parse_version_spec(spec: str) -> Dict[str, str]:
        """解析版本规范字符串"""
        # 支持格式：>=1.0.0, >1.0.0, ==1.0.0, ~=1.0.0
        import re
        
        patterns = {
            r'>=(.+)': 'gte',
            r'>(.+)': 'gt', 
            r'==(.+)': 'eq',
            r'~=(.+)': 'compatible',
            r'(.+)': 'eq'  # 默认为精确匹配
        }
        
        for pattern, op in patterns.items():
            match = re.match(pattern, spec.strip())
            if match:
                return {'op': op, 'version': match.group(1).strip()}
        
        return {'op': 'eq', 'version': spec.strip()}
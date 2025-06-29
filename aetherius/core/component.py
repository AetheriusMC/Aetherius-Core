"""
Aetherius组件系统基础
==================

提供组件生命周期管理和基础接口
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ComponentInfo:
    """
    组件信息数据结构

    定义组件的元数据、依赖关系和配置���项
    """

    # 基础信息
    name: str  # 组件唯一标识符
    display_name: str  # 显示名称
    description: str  # 组件描述
    version: str  # 版本号
    author: str  # 作者
    website: str = ""  # 官方网站

    # 依赖关系
    dependencies: list[str] = field(default_factory=list)  # 硬依赖
    soft_dependencies: list[str] = field(default_factory=list)  # 软依赖
    aetherius_version: str = ">=1.0.0"  # 支持的核心版本

    # 分类和权限
    category: str = "general"  # 组件分类
    permissions: list[str] = field(default_factory=list)  # 所需权限

    # 配置定义
    config_schema: dict[str, Any] = field(default_factory=dict)  # 配置架构
    default_config: dict[str, Any] = field(default_factory=dict)  # 默认配置

    # 可选属性
    tags: list[str] = field(default_factory=list)  # 标签
    license: str = "MIT"  # 许可证
    min_ram: int = 0  # 最小内存需求(MB)
    load_order: int = 0  # 加载顺序

    # Web组件特殊属性
    provides_web_interface: bool = False  # 是否提供Web界面
    web_routes: list[str] = field(default_factory=list)  # Web路由列表
    api_endpoints: list[str] = field(default_factory=list)  # API端点列表

    def validate(self) -> bool:
        """验证组件信息的完���性"""
        required_fields = ["name", "display_name", "description", "version", "author"]
        for field_name in required_fields:
            if not getattr(self, field_name):
                logger.error(f"Component info missing required field: {field_name}")
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "website": self.website,
            "dependencies": self.dependencies,
            "soft_dependencies": self.soft_dependencies,
            "aetherius_version": self.aetherius_version,
            "category": self.category,
            "permissions": self.permissions,
            "tags": self.tags,
            "license": self.license,
            "min_ram": self.min_ram,
            "load_order": self.load_order,
            "provides_web_interface": self.provides_web_interface,
            "web_routes": self.web_routes,
            "api_endpoints": self.api_endpoints,
        }


class Component(ABC):
    """
    组件基类

    所有Aetherius组件必须继承此类并实现生命周期方法
    """

    def __init__(self, core_instance, config: Optional[dict[str, Any]] = None):
        """
        初始化组件

        Args:
            core_instance: Aetherius核心实例
            config: 组件配置字典
        """
        self.core = core_instance
        self.config = config or {}
        self.logger = logging.getLogger(f"component.{self.__class__.__name__.lower()}")
        self._enabled: bool = False
        self._loaded: bool = False
        self._start_time: Optional[datetime] = None
        self._data_folder: Optional[Path] = None
        self._component_info: Optional[ComponentInfo] = None

        # 事件处理器注册表
        self._event_handlers: dict[str, Callable] = {}

    @property
    def is_enabled(self) -> bool:
        """组件是否已启用"""
        return self._enabled

    @property
    def is_loaded(self) -> bool:
        """组件是否已加载"""
        return self._loaded

    @property
    def data_folder(self) -> Optional[Path]:
        """组件数据目录"""
        return self._data_folder

    @data_folder.setter
    def data_folder(self, path: str | Path):
        """设置组件数据目录"""
        self._data_folder = Path(path) if isinstance(path, str) else path
        if self._data_folder and not self._data_folder.exists():
            self._data_folder.mkdir(parents=True, exist_ok=True)

    @property
    def component_info(self) -> Optional[ComponentInfo]:
        """组件信息"""
        return self._component_info

    @component_info.setter
    def component_info(self, info: ComponentInfo):
        """设置组件信息"""
        self._component_info = info

    @property
    def uptime(self) -> Optional[float]:
        """组件运行时间（秒）"""
        if self._start_time:
            return (datetime.now() - self._start_time).total_seconds()
        return None

    # 生命周期方法
    @abstractmethod
    async def on_load(self):
        """
        组件加载时调用

        在此方法中进行：
        - 资源初始化
        - 依赖检查
        - 配置验证
        """
        self.logger.info(f"Loading component: {self.__class__.__name__}")
        self._loaded = True

    @abstractmethod
    async def on_enable(self):
        """
        组件启用时调用

        在此方法中进行：
        - 启动服务
        - 注册事件监听器
        - 激活功能
        """
        self.logger.info(f"Enabling component: {self.__class__.__name__}")
        self._enabled = True
        self._start_time = datetime.now()

    @abstractmethod
    async def on_disable(self):
        """
        组件禁用时调用

        在此方法中进行：
        - 停止服务
        - 注销事件监听器
        - 清理临时资源
        """
        self.logger.info(f"Disabling component: {self.__class__.__name__}")
        self._enabled = False

        # 自动注销所有事件处理器
        await self._unregister_all_events()

    @abstractmethod
    async def on_unload(self):
        """
        组件卸载时调用

        在此方法中进行：
        - 释放所有资源
        - 清理配置
        - 关闭连接
        """
        self.logger.info(f"Unloading component: {self.__class__.__name__}")
        self._loaded = False
        self._start_time = None

    async def on_config_change(self, new_config: dict[str, Any]):
        """
        配置变更时调用

        Args:
            new_config: 新的配置字典
        """
        self.config = new_config
        self.logger.info(
            f"Configuration updated for component: {self.__class__.__name__}"
        )

    # 事件系统集成
    def register_event_handler(self, event_name: str, handler_method: str):
        """
        注册事件处理器

        Args:
            event_name: 事件名称
            handler_method: 处理方法名称
        """
        if hasattr(self, handler_method):
            handler = getattr(self, handler_method)
            if self.core and hasattr(self.core, "event_manager"):
                self.core.event_manager.register_handler(event_name, handler)
                self._event_handlers[event_name] = handler
                self.logger.debug(
                    f"Registered event handler: {event_name} -> {handler_method}"
                )

    async def _unregister_all_events(self):
        """注销所有事件处理器"""
        if self.core and hasattr(self.core, "event_manager"):
            for event_name, handler in self._event_handlers.items():
                self.core.event_manager.unregister_handler(event_name, handler)
            self._event_handlers.clear()

    async def emit_event(self, event_name: str, data: Any = None):
        """
        发送事件

        Args:
            event_name: 事件名称
            data: 事件数据
        """
        if (
            self.core
            and hasattr(self.core, "event_manager")
            and self.core.event_manager
        ):
            await self.core.event_manager.emit_event(
                event_name, data, source=self.__class__.__name__
            )

    # 核心服务访问
    def get_server_manager(self):
        """获取服务器管理器"""
        if self.core and hasattr(self.core, "server_manager"):
            return self.core.server_manager
        return None

    def get_player_manager(self):
        """获取玩家管理器"""
        if self.core and hasattr(self.core, "player_manager"):
            return self.core.player_manager
        return None

    def get_config_manager(self):
        """获取配置管理器"""
        if self.core and hasattr(self.core, "config_manager"):
            return self.core.config_manager
        return None

    def get_file_manager(self):
        """获取文件管理器"""
        if self.core and hasattr(self.core, "file_manager"):
            return self.core.file_manager
        return None

    def get_config(self) -> dict[str, Any]:
        """获取组件配置"""
        return self.config or {}

    # 实用方法
    def save_data(self, filename: str, data: Any):
        """
        保存数据到组件数据目录

        Args:
            filename: 文件名
            data: 要保存的数据
        """
        if not self.data_folder:
            raise RuntimeError("Data folder not set")

        import json

        file_path = self.data_folder / filename

        if isinstance(data, (dict, list)):
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(data))

    def load_data(self, filename: str, default=None):
        """
        从组件数据目录加载数据

        Args:
            filename: 文件名
            default: 默认值

        Returns:
            加载的数据或默认值
        """
        if not self.data_folder:
            return default

        file_path = self.data_folder / filename
        if not file_path.exists():
            return default

        try:
            import json

            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # 如果不是JSON，返回文本内容
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Error loading data from {filename}: {e}")
            return default

    def get_status(self) -> dict[str, Any]:
        """
        获取组件状态信息

        Returns:
            包含状态信息的字典
        """
        return {
            "name": self.__class__.__name__,
            "loaded": self.is_loaded,
            "enabled": self.is_enabled,
            "uptime": self.uptime,
            "config_count": len(self.config),
            "event_handlers": len(self._event_handlers),
            "data_folder": str(self.data_folder) if self.data_folder else None,
        }


class WebComponent(Component):
    """
    Web组件基类

    为提供Web界面的组件提供额外功能
    """

    def __init__(self, core_instance, config: Optional[dict[str, Any]] = None):
        super().__init__(core_instance, config)
        self._web_app = None
        self._web_routes: list[dict[str, Any]] = []
        self._api_endpoints: list[dict[str, Any]] = []

    @property
    def web_app(self):
        """Web应用实例"""
        return self._web_app

    @web_app.setter
    def web_app(self, app):
        """设置Web应用实例"""
        self._web_app = app

    def add_route(self, path: str, handler, methods: Optional[list[str]] = None):
        """
        添加Web路由

        Args:
            path: 路由路径
            handler: 处理函数
            methods: HTTP方法列表
        """
        self._web_routes.append(
            {"path": path, "handler": handler, "methods": methods or ["GET"]}
        )

    def add_api_endpoint(self, path: str, handler, methods: Optional[list[str]] = None):
        """
        添加API端点

        Args:
            path: API路径
            handler: 处理函数
            methods: HTTP方法列表
        """
        self._api_endpoints.append(
            {"path": path, "handler": handler, "methods": methods or ["GET"]}
        )

    def get_web_routes(self) -> list[dict[str, Any]]:
        """获取Web路由列表"""
        return self._web_routes

    def get_api_endpoints(self) -> list[dict[str, Any]]:
        """获取API端点列表"""
        return self._api_endpoints

    async def setup_web_interface(self):
        """
        设置Web界面

        子类应重写此方法来设置具体的Web路由和API
        """
        pass

    async def on_enable(self):
        """启用Web组件时同时设置Web界面"""
        await super().on_enable()
        await self.setup_web_interface()

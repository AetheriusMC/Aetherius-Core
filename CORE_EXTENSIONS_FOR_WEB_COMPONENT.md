# Aetherius核心扩展需求文档
# 支持Component-Web集成的核心功能扩展

## 📋 概述

本文档详细说明了为了完全支持Component-Web组件，Aetherius核心系统需要实现的扩展功能。这些扩展将提供完整的组件系统支持、事件驱动架构、Web接口集成和管理功能。

## 🏗️ 1. 组件系统基础架构

### 1.1 Component基类

**文件路径**: `aetherius/core/component.py`

```python
"""
Aetherius组件系统基础
==================

提供组件生命周期管理和基础接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Component(ABC):
    """
    组件基类
    
    所有Aetherius组件必须继承此类并实现生命周期方法
    """
    
    def __init__(self, core_instance, config: Optional[Dict[str, Any]] = None):
        """
        初始化组件
        
        Args:
            core_instance: Aetherius核心实例
            config: 组件配置字典
        """
        self.core = core_instance
        self.config = config or {}
        self.logger = logging.getLogger(f"component.{self.__class__.__name__.lower()}")
        self._enabled = False
        self._loaded = False
        
    @property
    def is_enabled(self) -> bool:
        """组件是否已启用"""
        return self._enabled
    
    @property
    def is_loaded(self) -> bool:
        """组件是否已加载"""
        return self._loaded
    
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
        
    async def on_config_change(self, new_config: Dict[str, Any]):
        """
        配置变更时调用
        
        Args:
            new_config: 新的配置字典
        """
        self.config = new_config
        self.logger.info(f"Configuration updated for component: {self.__class__.__name__}")


@dataclass
class ComponentInfo:
    """
    组件信息数据结构
    
    定义组件的元数据、依赖关系和配置选项
    """
    
    # 基础信息
    name: str                           # 组件唯一标识符
    display_name: str                   # 显示名称
    description: str                    # 组件描述
    version: str                        # 版本号
    author: str                         # 作者
    website: str                        # 官方网站
    
    # 依赖关系
    dependencies: list = field(default_factory=list)           # 硬依赖
    soft_dependencies: list = field(default_factory=list)      # 软依赖
    aetherius_version: str = ">=1.0.0"                        # 支持的核心版本
    
    # 分类和权限
    category: str = "general"                                  # 组件分类
    permissions: list = field(default_factory=list)           # 所需权限
    
    # 配置定义
    config_schema: Dict[str, Any] = field(default_factory=dict)    # 配置架构
    default_config: Dict[str, Any] = field(default_factory=dict)   # 默认配置
    
    # 可选属性
    tags: list = field(default_factory=list)                      # 标签
    license: str = "MIT"                                          # 许可证
    min_ram: int = 0                                              # 最小内存需求(MB)
    load_order: int = 0                                           # 加载顺序
    
    def validate(self) -> bool:
        """验证组件信息的完整性"""
        required_fields = ['name', 'display_name', 'description', 'version', 'author']
        for field in required_fields:
            if not getattr(self, field):
                return False
        return True
```

### 1.2 组件管理器

**文件路径**: `aetherius/core/component_manager.py`

```python
"""
Aetherius组件管理器
=================

负责组件的加载、启用、禁用和卸载
"""

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio
import logging
from .component import Component, ComponentInfo

logger = logging.getLogger(__name__)

class ComponentManager:
    """组件管理器"""
    
    def __init__(self, core_instance):
        """
        初始化组件管理器
        
        Args:
            core_instance: Aetherius核心实例
        """
        self.core = core_instance
        self.components: Dict[str, Component] = {}
        self.component_info: Dict[str, ComponentInfo] = {}
        self.component_paths: Dict[str, Path] = {}
        self._load_order: List[str] = []
        
    async def discover_components(self, components_dir: Path) -> List[str]:
        """
        发现组件目录中的所有组件
        
        Args:
            components_dir: 组件目录路径
            
        Returns:
            发现的组件名称列表
        """
        discovered = []
        
        if not components_dir.exists() or not components_dir.is_dir():
            logger.warning(f"Components directory not found: {components_dir}")
            return discovered
            
        for component_path in components_dir.iterdir():
            if not component_path.is_dir():
                continue
                
            # 查找组件信息文件
            info_files = [
                component_path / "component_info.py",
                component_path / "info.py",
                component_path / "__init__.py"
            ]
            
            for info_file in info_files:
                if info_file.exists():
                    try:
                        component_info = await self._load_component_info(info_file)
                        if component_info:
                            self.component_info[component_info.name] = component_info
                            self.component_paths[component_info.name] = component_path
                            discovered.append(component_info.name)
                            logger.info(f"Discovered component: {component_info.name}")
                            break
                    except Exception as e:
                        logger.error(f"Failed to load component info from {info_file}: {e}")
                        
        return discovered
    
    async def _load_component_info(self, info_file: Path) -> Optional[ComponentInfo]:
        """加载组件信息"""
        try:
            spec = importlib.util.spec_from_file_location("component_info", info_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, 'component_info'):
                return module.component_info
            else:
                logger.warning(f"No component_info found in {info_file}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load component info from {info_file}: {e}")
            return None
    
    async def load_component(self, name: str) -> bool:
        """
        加载组件
        
        Args:
            name: 组件名称
            
        Returns:
            是否加载成功
        """
        if name in self.components:
            logger.warning(f"Component {name} is already loaded")
            return True
            
        if name not in self.component_info:
            logger.error(f"Component info not found for: {name}")
            return False
            
        try:
            # 检查依赖
            if not await self._check_dependencies(name):
                logger.error(f"Dependency check failed for component: {name}")
                return False
                
            # 加载组件类
            component_instance = await self._load_component_class(name)
            if not component_instance:
                return False
                
            # 调用加载方法
            await component_instance.on_load()
            
            self.components[name] = component_instance
            self._load_order.append(name)
            
            logger.info(f"Successfully loaded component: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load component {name}: {e}")
            return False
    
    async def _load_component_class(self, name: str) -> Optional[Component]:
        """加载组件类实例"""
        component_path = self.component_paths[name]
        info = self.component_info[name]
        
        # 尝试多种组件文件位置
        component_files = [
            component_path / f"{name}_component.py",
            component_path / "component.py",
            component_path / "__init__.py"
        ]
        
        for component_file in component_files:
            if component_file.exists():
                try:
                    spec = importlib.util.spec_from_file_location(f"component_{name}", component_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # 查找组件类
                    component_class = None
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, Component) and 
                            attr != Component):
                            component_class = attr
                            break
                    
                    if component_class:
                        # 获取组件配置
                        config = self.core.config_manager.get_component_config(name)
                        return component_class(self.core, config)
                        
                except Exception as e:
                    logger.error(f"Failed to load component class from {component_file}: {e}")
                    continue
                    
        logger.error(f"No valid component class found for: {name}")
        return None
    
    async def _check_dependencies(self, name: str) -> bool:
        """检查组件依赖"""
        info = self.component_info[name]
        
        # 检查硬依赖
        for dep in info.dependencies:
            if dep not in self.components:
                logger.error(f"Hard dependency not satisfied: {dep} for component {name}")
                return False
                
        # 软依赖只警告
        for dep in info.soft_dependencies:
            if dep not in self.components:
                logger.warning(f"Soft dependency not available: {dep} for component {name}")
                
        return True
    
    async def enable_component(self, name: str) -> bool:
        """
        启用组件
        
        Args:
            name: 组件名称
            
        Returns:
            是否启用成功
        """
        if name not in self.components:
            logger.error(f"Component not loaded: {name}")
            return False
            
        component = self.components[name]
        if component.is_enabled:
            logger.warning(f"Component {name} is already enabled")
            return True
            
        try:
            await component.on_enable()
            logger.info(f"Successfully enabled component: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable component {name}: {e}")
            return False
    
    async def disable_component(self, name: str) -> bool:
        """
        禁用组件
        
        Args:
            name: 组件名称
            
        Returns:
            是否禁用成功
        """
        if name not in self.components:
            logger.error(f"Component not loaded: {name}")
            return False
            
        component = self.components[name]
        if not component.is_enabled:
            logger.warning(f"Component {name} is already disabled")
            return True
            
        try:
            await component.on_disable()
            logger.info(f"Successfully disabled component: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable component {name}: {e}")
            return False
    
    async def unload_component(self, name: str) -> bool:
        """
        卸载组件
        
        Args:
            name: 组件名称
            
        Returns:
            是否卸载成功
        """
        if name not in self.components:
            logger.warning(f"Component not loaded: {name}")
            return True
            
        component = self.components[name]
        
        try:
            # 先禁用
            if component.is_enabled:
                await self.disable_component(name)
                
            # 再卸载
            await component.on_unload()
            
            # 从管理器中移除
            del self.components[name]
            if name in self._load_order:
                self._load_order.remove(name)
                
            logger.info(f"Successfully unloaded component: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload component {name}: {e}")
            return False
    
    async def reload_component(self, name: str) -> bool:
        """
        重新加载组件
        
        Args:
            name: 组件名称
            
        Returns:
            是否重载成功
        """
        was_enabled = name in self.components and self.components[name].is_enabled
        
        # 卸载组件
        if not await self.unload_component(name):
            return False
            
        # 重新加载组件
        if not await self.load_component(name):
            return False
            
        # 如果之前是启用状态，重新启用
        if was_enabled:
            return await self.enable_component(name)
            
        return True
    
    def get_component(self, name: str) -> Optional[Component]:
        """获取组件实例"""
        return self.components.get(name)
    
    def get_component_list(self) -> List[Dict[str, Any]]:
        """
        获取组件列表
        
        Returns:
            组件信息列表
        """
        result = []
        
        for name, info in self.component_info.items():
            component = self.components.get(name)
            result.append({
                "name": name,
                "display_name": info.display_name,
                "description": info.description,
                "version": info.version,
                "author": info.author,
                "category": info.category,
                "loaded": component is not None,
                "enabled": component.is_enabled if component else False,
                "dependencies": info.dependencies,
                "permissions": info.permissions
            })
            
        return result
    
    def get_component_info(self, name: str) -> Optional[ComponentInfo]:
        """获取组件信息"""
        return self.component_info.get(name)
    
    async def load_all_components(self, components_dir: Path) -> List[str]:
        """
        加载所有发现的组件
        
        Args:
            components_dir: 组件目录
            
        Returns:
            成功加载的组件列表
        """
        # 发现组件
        discovered = await self.discover_components(components_dir)
        
        # 按加载顺序排序
        sorted_components = sorted(
            discovered, 
            key=lambda x: self.component_info[x].load_order
        )
        
        loaded = []
        for name in sorted_components:
            if await self.load_component(name):
                loaded.append(name)
                
        logger.info(f"Loaded {len(loaded)} components: {loaded}")
        return loaded
    
    async def enable_all_components(self) -> List[str]:
        """
        启用所有已加载的组件
        
        Returns:
            成功启用的组件列表
        """
        enabled = []
        for name in self._load_order:
            if await self.enable_component(name):
                enabled.append(name)
                
        logger.info(f"Enabled {len(enabled)} components: {enabled}")
        return enabled
    
    async def shutdown_all_components(self):
        """关闭所有组件"""
        # 按相反顺序卸载
        for name in reversed(self._load_order.copy()):
            await self.unload_component(name)
        
        logger.info("All components have been shut down")
```

## 🎯 2. 事件系统架构

### 2.1 事件管理器

**文件路径**: `aetherius/core/event_manager.py`

```python
"""
Aetherius事件管理系统
==================

提供组件间的事件通信机制
"""

import asyncio
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging
import inspect

logger = logging.getLogger(__name__)

@dataclass
class Event:
    """事件数据结构"""
    name: str                           # 事件名称
    data: Any = None                    # 事件数据
    timestamp: datetime = None          # 时间戳
    source: str = None                  # 事件源
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class EventManager:
    """事件管理器"""
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._async_handlers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        
    def register_handler(self, event_name: str, handler: Callable, is_async: bool = None):
        """
        注册事件处理器
        
        Args:
            event_name: 事件名称
            handler: 处理函数
            is_async: 是否为异步处理器（自动检测）
        """
        if is_async is None:
            is_async = asyncio.iscoroutinefunction(handler)
            
        if is_async:
            if event_name not in self._async_handlers:
                self._async_handlers[event_name] = []
            self._async_handlers[event_name].append(handler)
        else:
            if event_name not in self._handlers:
                self._handlers[event_name] = []
            self._handlers[event_name].append(handler)
            
        logger.debug(f"Registered {'async ' if is_async else ''}handler for event: {event_name}")
    
    def unregister_handler(self, event_name: str, handler: Callable):
        """注销事件处理器"""
        if event_name in self._handlers and handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)
            
        if event_name in self._async_handlers and handler in self._async_handlers[event_name]:
            self._async_handlers[event_name].remove(handler)
            
        logger.debug(f"Unregistered handler for event: {event_name}")
    
    async def emit_event(self, event_name: str, data: Any = None, source: str = None):
        """
        触发事件
        
        Args:
            event_name: 事件名称
            data: 事件数据
            source: 事件源
        """
        event = Event(event_name, data, source=source)
        
        # 记录事件历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
            
        logger.debug(f"Emitting event: {event_name} from {source}")
        
        # 执行同步处理器
        sync_handlers = self._handlers.get(event_name, [])
        for handler in sync_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in sync event handler for {event_name}: {e}")
        
        # 执行异步处理器
        async_handlers = self._async_handlers.get(event_name, [])
        tasks = []
        for handler in async_handlers:
            try:
                task = asyncio.create_task(handler(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error creating task for async event handler {event_name}: {e}")
        
        # 等待所有异步处理器完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def event_handler(self, event_name: str):
        """
        事件处理器装饰器
        
        Usage:
            @event_manager.event_handler("player.join")
            async def on_player_join(event):
                print(f"Player joined: {event.data}")
        """
        def decorator(func):
            self.register_handler(event_name, func)
            return func
        return decorator
    
    def get_event_history(self, event_name: Optional[str] = None, limit: int = 100) -> List[Event]:
        """
        获取事件历史
        
        Args:
            event_name: 事件名称过滤
            limit: 返回数量限制
            
        Returns:
            事件列表
        """
        events = self._event_history
        
        if event_name:
            events = [e for e in events if e.name == event_name]
            
        return events[-limit:] if limit else events
    
    def get_registered_events(self) -> List[str]:
        """获取所有已注册的事件名称"""
        events = set()
        events.update(self._handlers.keys())
        events.update(self._async_handlers.keys())
        return list(events)
    
    def get_handler_count(self, event_name: str) -> int:
        """获取指定事件的处理器数量"""
        sync_count = len(self._handlers.get(event_name, []))
        async_count = len(self._async_handlers.get(event_name, []))
        return sync_count + async_count
```

### 2.2 标准事件定义

**文件路径**: `aetherius/core/events.py`

```python
"""
Aetherius标准事件定义
==================

定义系统和组件使用的标准事件名称
"""

# 服务器生命周期事件
SERVER_STARTING = "server.starting"        # 服务器正在启动
SERVER_START = "server.start"              # 服务器已启动
SERVER_STOPPING = "server.stopping"       # 服务器正在停止
SERVER_STOP = "server.stop"                # 服务器已停止
SERVER_CRASH = "server.crash"              # 服务器崩溃
SERVER_RESTART = "server.restart"          # 服务器重启

# 服务器状态事件
SERVER_STATUS_CHANGE = "server.status_change"      # 状态变更
SERVER_PERFORMANCE_UPDATE = "server.performance"   # 性能更新
SERVER_TPS_UPDATE = "server.tps"                  # TPS更新

# 玩家事件
PLAYER_JOIN = "player.join"                # 玩家加入
PLAYER_QUIT = "player.quit"                # 玩家退出
PLAYER_CHAT = "player.chat"                # 玩家聊天
PLAYER_DEATH = "player.death"              # 玩家死亡
PLAYER_RESPAWN = "player.respawn"          # 玩家重生
PLAYER_KICK = "player.kick"                # 玩家被踢出
PLAYER_BAN = "player.ban"                  # 玩家被封禁
PLAYER_UNBAN = "player.unban"              # 玩家解封
PLAYER_OP = "player.op"                    # 玩家获得OP
PLAYER_DEOP = "player.deop"                # 玩家失去OP

# 玩家行为事件
PLAYER_MOVE = "player.move"                # 玩家移动
PLAYER_INTERACT = "player.interact"        # 玩家交互
PLAYER_BREAK_BLOCK = "player.break_block"  # 玩家破坏方块
PLAYER_PLACE_BLOCK = "player.place_block"  # 玩家放置方块

# 控制台事件
CONSOLE_LOG = "console.log"                # 控制台日志
CONSOLE_COMMAND = "console.command"        # 控制台命令
CONSOLE_OUTPUT = "console.output"          # 控制台输出

# 组件事件
COMPONENT_LOAD = "component.load"          # 组件加载
COMPONENT_ENABLE = "component.enable"      # 组件启用
COMPONENT_DISABLE = "component.disable"    # 组件禁用
COMPONENT_UNLOAD = "component.unload"      # 组件卸载
COMPONENT_ERROR = "component.error"        # 组件错误

# 配置事件
CONFIG_CHANGE = "config.change"            # 配置变更
CONFIG_RELOAD = "config.reload"            # 配置重载

# 文件系统事件
FILE_CHANGE = "file.change"                # 文件变更
FILE_CREATE = "file.create"                # 文件创建
FILE_DELETE = "file.delete"                # 文件删除

# 世界事件
WORLD_LOAD = "world.load"                  # 世界加载
WORLD_UNLOAD = "world.unload"              # 世界卸载
WORLD_SAVE = "world.save"                  # 世界保存

# 网络事件
NETWORK_CONNECT = "network.connect"        # 网络连接
NETWORK_DISCONNECT = "network.disconnect"  # 网络断开
NETWORK_ERROR = "network.error"            # 网络错误

# 系统事件
SYSTEM_SHUTDOWN = "system.shutdown"        # 系统关闭
SYSTEM_ERROR = "system.error"              # 系统错误
SYSTEM_WARNING = "system.warning"          # 系统警告

# Web组件专用事件
WEB_CLIENT_CONNECT = "web.client.connect"      # Web客户端连接
WEB_CLIENT_DISCONNECT = "web.client.disconnect" # Web客户端断开
WEB_REQUEST = "web.request"                     # Web请求
WEB_RESPONSE = "web.response"                   # Web响应
WEB_WEBSOCKET_MESSAGE = "web.websocket.message" # WebSocket消息

# 事件数据结构示例
EVENT_DATA_SCHEMAS = {
    SERVER_START: {
        "version": "str",
        "startup_time": "float",
        "port": "int"
    },
    PLAYER_JOIN: {
        "uuid": "str",
        "name": "str",
        "ip": "str",
        "timestamp": "datetime"
    },
    PLAYER_CHAT: {
        "uuid": "str",
        "name": "str",
        "message": "str",
        "timestamp": "datetime"
    },
    CONSOLE_LOG: {
        "level": "str",  # INFO, WARN, ERROR
        "message": "str",
        "timestamp": "datetime",
        "source": "str"
    }
}
```

## 🖥️ 3. 服务器管理扩展

### 3.1 ServerProcessWrapper增强

**文件路径**: `aetherius/core/server.py`

```python
"""
Aetherius服务器进程管理
====================

扩展的服务器进程包装器，支持Web组件需要的所有功能
"""

import asyncio
import psutil
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import logging
from .events import *
from .event_manager import EventManager

logger = logging.getLogger(__name__)

class ServerProcessWrapper:
    """服务器进程包装器 - 增强版"""
    
    def __init__(self, server_jar_path: Path, event_manager: EventManager):
        self.server_jar_path = server_jar_path
        self.event_manager = event_manager
        self.process: Optional[asyncio.subprocess.Process] = None
        self.start_time: Optional[datetime] = None
        self.performance_history: List[Dict[str, Any]] = []
        self._output_buffer: List[str] = []
        self._max_buffer_size = 1000
        self._running = False
        
        # 性能监控
        self._psutil_process: Optional[psutil.Process] = None
        self._monitor_task: Optional[asyncio.Task] = None
        
        # 玩家数据缓存
        self._online_players: Dict[str, Dict[str, Any]] = {}
        self._player_count = 0
        self._max_players = 20
        
        # TPS监控
        self._current_tps = 20.0
        self._tps_history: List[float] = []
        
    async def start_server(self, java_args: List[str] = None, server_args: List[str] = None) -> bool:
        """
        启动服务器
        
        Args:
            java_args: Java虚拟机参数
            server_args: 服务器参数
            
        Returns:
            是否启动成功
        """
        if self._running:
            logger.warning("Server is already running")
            return True
            
        try:
            await self.event_manager.emit_event(SERVER_STARTING, source="server")
            
            # 构建命令
            cmd = ["java"]
            if java_args:
                cmd.extend(java_args)
            cmd.extend(["-jar", str(self.server_jar_path)])
            if server_args:
                cmd.extend(server_args)
            
            # 启动进程
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.server_jar_path.parent
            )
            
            self.start_time = datetime.now()
            self._running = True
            
            # 获取psutil进程对象用于性能监控
            self._psutil_process = psutil.Process(self.process.pid)
            
            # 启动输出监控任务
            asyncio.create_task(self._monitor_output())
            
            # 启动性能监控任务
            self._monitor_task = asyncio.create_task(self._monitor_performance())
            
            await self.event_manager.emit_event(
                SERVER_START, 
                {
                    "pid": self.process.pid,
                    "startup_time": time.time() - self.start_time.timestamp(),
                    "command": " ".join(cmd)
                },
                source="server"
            )
            
            logger.info(f"Server started with PID: {self.process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            self._running = False
            return False
    
    async def stop_server(self, timeout: int = 30) -> bool:
        """
        停止服务器
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否停止成功
        """
        if not self._running or not self.process:
            logger.warning("Server is not running")
            return True
            
        try:
            await self.event_manager.emit_event(SERVER_STOPPING, source="server")
            
            # 发送stop命令
            await self.send_command("stop")
            
            # 等待进程结束
            try:
                await asyncio.wait_for(self.process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Server didn't stop gracefully, terminating...")
                self.process.terminate()
                await self.process.wait()
            
            # 清理
            self._running = False
            self._psutil_process = None
            
            if self._monitor_task:
                self._monitor_task.cancel()
                self._monitor_task = None
            
            await self.event_manager.emit_event(SERVER_STOP, source="server")
            
            logger.info("Server stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop server: {e}")
            return False
    
    async def restart_server(self, java_args: List[str] = None, server_args: List[str] = None) -> bool:
        """
        重启服务器
        
        Args:
            java_args: Java虚拟机参数
            server_args: 服务器参数
            
        Returns:
            是否重启成功
        """
        logger.info("Restarting server...")
        
        if not await self.stop_server():
            return False
            
        # 等待一段时间确保完全停止
        await asyncio.sleep(2)
        
        success = await self.start_server(java_args, server_args)
        
        if success:
            await self.event_manager.emit_event(SERVER_RESTART, source="server")
            
        return success
    
    async def send_command(self, command: str) -> bool:
        """
        发送命令到服务器
        
        Args:
            command: 要发送的命令
            
        Returns:
            是否发送成功
        """
        if not self._running or not self.process:
            logger.error("Cannot send command: server is not running")
            return False
            
        try:
            command_line = command.strip() + "\n"
            self.process.stdin.write(command_line.encode())
            await self.process.stdin.drain()
            
            await self.event_manager.emit_event(
                CONSOLE_COMMAND,
                {
                    "command": command,
                    "timestamp": datetime.now()
                },
                source="console"
            )
            
            logger.debug(f"Sent command: {command}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send command '{command}': {e}")
            return False
    
    async def send_command_with_output(self, command: str, timeout: int = 30) -> Optional[str]:
        """
        发送命令并等待输出
        
        Args:
            command: 要发送的命令
            timeout: 超时时间
            
        Returns:
            命令输出或None
        """
        if not await self.send_command(command):
            return None
            
        # 简单的输出捕获实现
        # 实际实现需要更复杂的输出关联逻辑
        start_time = time.time()
        output_lines = []
        
        while time.time() - start_time < timeout:
            if len(self._output_buffer) > 0:
                # 获取最近的输出
                recent_output = self._output_buffer[-10:]  # 最近10行
                output_lines.extend(recent_output)
                break
            await asyncio.sleep(0.1)
            
        return "\n".join(output_lines) if output_lines else None
    
    def is_running(self) -> bool:
        """检查服务器是否运行"""
        return self._running and self.process is not None and self.process.returncode is None
    
    def get_uptime(self) -> int:
        """获取运行时间（秒）"""
        if not self.start_time:
            return 0
        return int((datetime.now() - self.start_time).total_seconds())
    
    async def get_server_status(self) -> Dict[str, Any]:
        """
        获取服务器详细状态
        
        Returns:
            服务器状态字典
        """
        status = {
            "is_running": self.is_running(),
            "uptime": self.get_uptime(),
            "version": await self._get_server_version(),
            "player_count": self._player_count,
            "max_players": self._max_players,
            "tps": self._current_tps,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "process_id": self.process.pid if self.process else None
        }
        
        # 添加性能信息
        if self._psutil_process:
            try:
                performance = await self.get_current_performance()
                status.update(performance)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.warning("Failed to get performance data")
                
        return status
    
    async def get_current_performance(self) -> Dict[str, Any]:
        """
        获取当前性能指标
        
        Returns:
            性能指标字典
        """
        if not self._psutil_process:
            return {}
            
        try:
            # CPU使用率
            cpu_percent = self._psutil_process.cpu_percent()
            
            # 内存使用
            memory_info = self._psutil_process.memory_info()
            memory_percent = self._psutil_process.memory_percent()
            
            # 线程数
            num_threads = self._psutil_process.num_threads()
            
            # 打开的文件描述符数
            try:
                num_fds = self._psutil_process.num_fds()
            except AttributeError:
                # Windows不支持
                num_fds = 0
            
            # 网络连接数
            try:
                connections = len(self._psutil_process.connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                connections = 0
            
            return {
                "cpu_usage": cpu_percent,
                "memory_usage": {
                    "rss": memory_info.rss,  # 常驻内存
                    "vms": memory_info.vms,  # 虚拟内存
                    "percent": memory_percent
                },
                "threads": num_threads,
                "file_descriptors": num_fds,
                "network_connections": connections,
                "timestamp": datetime.now().isoformat()
            }
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Failed to get performance metrics: {e}")
            return {}
    
    async def get_metrics_history(self, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        获取历史性能数据
        
        Args:
            duration_minutes: 时间范围（分钟）
            
        Returns:
            性能历史数据列表
        """
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        
        return [
            metric for metric in self.performance_history
            if datetime.fromisoformat(metric.get("timestamp", "")) > cutoff_time
        ]
    
    async def get_online_players(self) -> List[Dict[str, Any]]:
        """
        获取在线玩家列表
        
        Returns:
            在线玩家信息列表
        """
        # 发送list命令获取玩家列表
        # 这里需要解析服务器输出来获取玩家信息
        # 实际实现需要根据服务器类型调整
        
        return list(self._online_players.values())
    
    async def get_recent_logs(self, lines: int = 100) -> List[Dict[str, Any]]:
        """
        获取最近的日志
        
        Args:
            lines: 行数
            
        Returns:
            日志条目列表
        """
        recent_logs = []
        buffer_lines = self._output_buffer[-lines:] if lines else self._output_buffer
        
        for line in buffer_lines:
            log_entry = self._parse_log_line(line)
            if log_entry:
                recent_logs.append(log_entry)
                
        return recent_logs
    
    async def _monitor_output(self):
        """监控服务器输出"""
        if not self.process:
            return
            
        try:
            async for line in self.process.stdout:
                line_str = line.decode('utf-8', errors='ignore').strip()
                
                # 添加到缓冲区
                self._output_buffer.append(line_str)
                if len(self._output_buffer) > self._max_buffer_size:
                    self._output_buffer.pop(0)
                
                # 解析日志
                log_entry = self._parse_log_line(line_str)
                if log_entry:
                    await self.event_manager.emit_event(
                        CONSOLE_LOG,
                        log_entry,
                        source="server"
                    )
                
                # 解析特殊事件
                await self._parse_special_events(line_str)
                
        except Exception as e:
            logger.error(f"Error monitoring server output: {e}")
    
    async def _monitor_performance(self):
        """监控服务器性能"""
        while self._running:
            try:
                performance = await self.get_current_performance()
                if performance:
                    self.performance_history.append(performance)
                    
                    # 限制历史数据大小
                    if len(self.performance_history) > 1440:  # 24小时的分钟数
                        self.performance_history.pop(0)
                    
                    # 触发性能更新事件
                    await self.event_manager.emit_event(
                        SERVER_PERFORMANCE_UPDATE,
                        performance,
                        source="server"
                    )
                
                await asyncio.sleep(60)  # 每分钟更新一次
                
            except Exception as e:
                logger.error(f"Error monitoring performance: {e}")
                await asyncio.sleep(60)
    
    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        解析日志行
        
        Args:
            line: 日志行
            
        Returns:
            解析后的日志条目
        """
        # Minecraft服务器日志格式: [时间] [线程/级别]: 消息
        pattern = r'\[(\d{2}:\d{2}:\d{2})\] \[([^/]+)/([^\]]+)\]: (.+)'
        match = re.match(pattern, line)
        
        if match:
            time_str, thread, level, message = match.groups()
            return {
                "timestamp": datetime.now().replace(
                    hour=int(time_str[:2]),
                    minute=int(time_str[3:5]),
                    second=int(time_str[6:8])
                ).isoformat(),
                "thread": thread,
                "level": level,
                "message": message,
                "raw_line": line
            }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": line,
            "raw_line": line
        }
    
    async def _parse_special_events(self, line: str):
        """解析特殊事件（玩家加入/退出等）"""
        # 玩家加入
        if " joined the game" in line:
            match = re.search(r'(\w+) joined the game', line)
            if match:
                player_name = match.group(1)
                await self.event_manager.emit_event(
                    PLAYER_JOIN,
                    {
                        "name": player_name,
                        "timestamp": datetime.now().isoformat()
                    },
                    source="server"
                )
                self._player_count += 1
        
        # 玩家退出
        elif " left the game" in line:
            match = re.search(r'(\w+) left the game', line)
            if match:
                player_name = match.group(1)
                await self.event_manager.emit_event(
                    PLAYER_QUIT,
                    {
                        "name": player_name,
                        "timestamp": datetime.now().isoformat()
                    },
                    source="server"
                )
                self._player_count = max(0, self._player_count - 1)
        
        # 聊天消息
        elif "<" in line and ">" in line:
            match = re.search(r'<(\w+)> (.+)', line)
            if match:
                player_name, message = match.groups()
                await self.event_manager.emit_event(
                    PLAYER_CHAT,
                    {
                        "name": player_name,
                        "message": message,
                        "timestamp": datetime.now().isoformat()
                    },
                    source="server"
                )
        
        # TPS信息（需要插件支持）
        elif "TPS:" in line or "tps" in line.lower():
            tps_match = re.search(r'TPS:\s*([\d.]+)', line, re.IGNORECASE)
            if tps_match:
                tps = float(tps_match.group(1))
                self._current_tps = tps
                self._tps_history.append(tps)
                if len(self._tps_history) > 60:  # 保留最近60个TPS值
                    self._tps_history.pop(0)
                
                await self.event_manager.emit_event(
                    SERVER_TPS_UPDATE,
                    {"tps": tps, "timestamp": datetime.now().isoformat()},
                    source="server"
                )
    
    async def _get_server_version(self) -> str:
        """获取服务器版本"""
        # 这里应该解析服务器启动日志来获取版本信息
        # 或者通过其他方式获取
        for line in self._output_buffer:
            if "Starting minecraft server version" in line.lower():
                match = re.search(r'version\s+([\d.]+)', line, re.IGNORECASE)
                if match:
                    return match.group(1)
        
        return "Unknown"
```

## 👥 4. 玩家数据管理

### 4.1 PlayerDataManager

**文件路径**: `aetherius/core/player_data.py`

```python
"""
Aetherius玩家数据管理
==================

提供完整的玩家数据管理功能
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
from .events import *
from .event_manager import EventManager

logger = logging.getLogger(__name__)

class PlayerDataManager:
    """玩家数据管理器"""
    
    def __init__(self, server_wrapper, event_manager: EventManager, data_dir: Path):
        self.server = server_wrapper
        self.event_manager = event_manager
        self.data_dir = Path(data_dir)
        self.players_cache: Dict[str, Dict[str, Any]] = {}
        self.online_players: Dict[str, Dict[str, Any]] = {}
        
        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 注册事件监听器
        self._register_event_handlers()
    
    def _register_event_handlers(self):
        """注册事件处理器"""
        
        @self.event_manager.event_handler(PLAYER_JOIN)
        async def on_player_join(event):
            await self._handle_player_join(event.data)
        
        @self.event_manager.event_handler(PLAYER_QUIT)
        async def on_player_quit(event):
            await self._handle_player_quit(event.data)
    
    async def get_player_info(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        获取玩家详细信息
        
        Args:
            identifier: 玩家UUID或用户名
            
        Returns:
            玩家信息字典
        """
        # 首先检查缓存
        player_data = self.players_cache.get(identifier)
        if player_data:
            return player_data
        
        # 尝试从文件加载
        player_file = self.data_dir / f"{identifier}.json"
        if player_file.exists():
            try:
                with open(player_file, 'r', encoding='utf-8') as f:
                    player_data = json.load(f)
                    self.players_cache[identifier] = player_data
                    return player_data
            except Exception as e:
                logger.error(f"Failed to load player data for {identifier}: {e}")
        
        # 如果是在线玩家，获取实时数据
        if identifier in self.online_players:
            return self.online_players[identifier]
        
        # 尝试通过服务器命令获取信息
        player_data = await self._fetch_player_data_from_server(identifier)
        if player_data:
            self.players_cache[identifier] = player_data
            await self._save_player_data(identifier, player_data)
        
        return player_data
    
    async def get_player_stats(self, identifier: str) -> Dict[str, Any]:
        """
        获取玩家统计数据
        
        Args:
            identifier: 玩家UUID或用户名
            
        Returns:
            玩家统计数据
        """
        player_info = await self.get_player_info(identifier)
        if not player_info:
            return {}
        
        # 计算统计数据
        stats = {
            "total_playtime": player_info.get("total_playtime", 0),
            "last_login": player_info.get("last_login"),
            "login_count": player_info.get("login_count", 0),
            "deaths": player_info.get("deaths", 0),
            "blocks_broken": player_info.get("blocks_broken", 0),
            "blocks_placed": player_info.get("blocks_placed", 0),
            "distance_walked": player_info.get("distance_walked", 0),
            "items_crafted": player_info.get("items_crafted", 0),
            "mobs_killed": player_info.get("mobs_killed", 0),
            "achievements": player_info.get("achievements", []),
            "is_online": identifier in self.online_players,
            "is_op": player_info.get("is_op", False),
            "is_banned": player_info.get("is_banned", False),
            "ban_reason": player_info.get("ban_reason"),
            "ban_expires": player_info.get("ban_expires")
        }
        
        return stats
    
    async def get_online_players(self) -> List[Dict[str, Any]]:
        """
        获取在线玩家列表
        
        Returns:
            在线玩家信息列表
        """
        # 发送list命令获取玩家列表
        output = await self.server.send_command_with_output("list")
        if output:
            players = self._parse_player_list(output)
            
            # 更新在线玩家信息
            for player in players:
                if player["name"] not in self.online_players:
                    # 获取详细信息
                    detailed_info = await self.get_player_info(player["name"])
                    if detailed_info:
                        self.online_players[player["name"]] = detailed_info
        
        return list(self.online_players.values())
    
    async def get_all_players(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取所有玩家列表
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            玩家列表
        """
        players = []
        
        # 扫描数据目录
        for player_file in self.data_dir.glob("*.json"):
            if len(players) >= offset + limit:
                break
                
            if len(players) < offset:
                continue
            
            try:
                with open(player_file, 'r', encoding='utf-8') as f:
                    player_data = json.load(f)
                    players.append(player_data)
            except Exception as e:
                logger.error(f"Failed to load player data from {player_file}: {e}")
        
        return players[offset:offset + limit]
    
    async def search_players(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        搜索玩家
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            匹配的玩家列表
        """
        matches = []
        query_lower = query.lower()
        
        # 搜索所有玩家数据
        for player_file in self.data_dir.glob("*.json"):
            if len(matches) >= limit:
                break
                
            try:
                with open(player_file, 'r', encoding='utf-8') as f:
                    player_data = json.load(f)
                    
                # 检查名称匹配
                if (query_lower in player_data.get("name", "").lower() or
                    query_lower in player_data.get("uuid", "").lower()):
                    matches.append(player_data)
                    
            except Exception as e:
                logger.error(f"Failed to search in {player_file}: {e}")
        
        return matches
    
    async def kick_player(self, identifier: str, reason: str = None) -> bool:
        """
        踢出玩家
        
        Args:
            identifier: 玩家UUID或用户名
            reason: 踢出原因
            
        Returns:
            是否操作成功
        """
        command = f"kick {identifier}"
        if reason:
            command += f" {reason}"
        
        success = await self.server.send_command(command)
        
        if success:
            await self.event_manager.emit_event(
                PLAYER_KICK,
                {
                    "player": identifier,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                },
                source="admin"
            )
            
            # 更新玩家数据
            await self._update_player_action(identifier, "kick", reason)
        
        return success
    
    async def ban_player(self, identifier: str, reason: str = None, duration: int = None) -> bool:
        """
        封禁玩家
        
        Args:
            identifier: 玩家UUID或用户名
            reason: 封禁原因
            duration: 封禁时长（秒），None表示永久封禁
            
        Returns:
            是否操作成功
        """
        if duration:
            # 临时封禁
            command = f"ban {identifier} {reason or 'Temporary ban'}"
            # 注意：原版Minecraft不直接支持临时封禁，可能需要插件
        else:
            # 永久封禁
            command = f"ban {identifier}"
            if reason:
                command += f" {reason}"
        
        success = await self.server.send_command(command)
        
        if success:
            ban_data = {
                "player": identifier,
                "reason": reason,
                "duration": duration,
                "banned_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(seconds=duration)).isoformat() if duration else None
            }
            
            await self.event_manager.emit_event(PLAYER_BAN, ban_data, source="admin")
            
            # 更新玩家数据
            await self._update_player_ban_status(identifier, True, reason, duration)
        
        return success
    
    async def unban_player(self, identifier: str) -> bool:
        """
        解封玩家
        
        Args:
            identifier: 玩家UUID或用户名
            
        Returns:
            是否操作成功
        """
        command = f"pardon {identifier}"
        success = await self.server.send_command(command)
        
        if success:
            await self.event_manager.emit_event(
                PLAYER_UNBAN,
                {
                    "player": identifier,
                    "timestamp": datetime.now().isoformat()
                },
                source="admin"
            )
            
            # 更新玩家数据
            await self._update_player_ban_status(identifier, False)
        
        return success
    
    async def set_player_op(self, identifier: str, is_op: bool) -> bool:
        """
        设置玩家OP权限
        
        Args:
            identifier: 玩家UUID或用户名
            is_op: 是否给予OP权限
            
        Returns:
            是否操作成功
        """
        command = "op" if is_op else "deop"
        command += f" {identifier}"
        
        success = await self.server.send_command(command)
        
        if success:
            event_type = PLAYER_OP if is_op else PLAYER_DEOP
            await self.event_manager.emit_event(
                event_type,
                {
                    "player": identifier,
                    "timestamp": datetime.now().isoformat()
                },
                source="admin"
            )
            
            # 更新玩家数据
            await self._update_player_op_status(identifier, is_op)
        
        return success
    
    async def send_player_message(self, identifier: str, message: str) -> bool:
        """
        向玩家发送私人消息
        
        Args:
            identifier: 玩家UUID或用户名
            message: 消息内容
            
        Returns:
            是否发送成功
        """
        command = f"tell {identifier} {message}"
        return await self.server.send_command(command)
    
    async def teleport_player(self, identifier: str, target: str = None, x: float = None, y: float = None, z: float = None) -> bool:
        """
        传送玩家
        
        Args:
            identifier: 玩家UUID或用户名
            target: 目标玩家（可选）
            x, y, z: 目标坐标（可选）
            
        Returns:
            是否传送成功
        """
        if target:
            command = f"tp {identifier} {target}"
        elif x is not None and y is not None and z is not None:
            command = f"tp {identifier} {x} {y} {z}"
        else:
            logger.error("Either target player or coordinates must be specified")
            return False
        
        return await self.server.send_command(command)
    
    async def get_player_inventory(self, identifier: str) -> Dict[str, Any]:
        """
        获取玩家背包信息（需要插件支持）
        
        Args:
            identifier: 玩家UUID或用户名
            
        Returns:
            背包信息
        """
        # 这个功能需要特定的插件支持
        # 这里提供一个基础框架
        player_data = await self.get_player_info(identifier)
        return player_data.get("inventory", {}) if player_data else {}
    
    async def batch_operation(self, operation: str, players: List[str], **kwargs) -> Dict[str, bool]:
        """
        批量操作玩家
        
        Args:
            operation: 操作类型 (kick, ban, unban, op, deop)
            players: 玩家列表
            **kwargs: 操作参数
            
        Returns:
            操作结果字典
        """
        results = {}
        
        for player in players:
            try:
                if operation == "kick":
                    results[player] = await self.kick_player(player, kwargs.get("reason"))
                elif operation == "ban":
                    results[player] = await self.ban_player(
                        player, 
                        kwargs.get("reason"), 
                        kwargs.get("duration")
                    )
                elif operation == "unban":
                    results[player] = await self.unban_player(player)
                elif operation == "op":
                    results[player] = await self.set_player_op(player, True)
                elif operation == "deop":
                    results[player] = await self.set_player_op(player, False)
                else:
                    results[player] = False
                    logger.error(f"Unknown operation: {operation}")
                    
            except Exception as e:
                logger.error(f"Failed to perform {operation} on {player}: {e}")
                results[player] = False
        
        return results
    
    async def _handle_player_join(self, event_data: Dict[str, Any]):
        """处理玩家加入事件"""
        player_name = event_data.get("name")
        if not player_name:
            return
        
        # 获取或创建玩家数据
        player_data = await self.get_player_info(player_name)
        if not player_data:
            player_data = {
                "name": player_name,
                "uuid": event_data.get("uuid", "unknown"),
                "first_login": datetime.now().isoformat(),
                "login_count": 0,
                "total_playtime": 0
            }
        
        # 更新登录信息
        player_data["last_login"] = event_data.get("timestamp", datetime.now().isoformat())
        player_data["login_count"] = player_data.get("login_count", 0) + 1
        player_data["current_session_start"] = datetime.now().isoformat()
        player_data["is_online"] = True
        
        # 添加到在线玩家
        self.online_players[player_name] = player_data
        
        # 保存数据
        await self._save_player_data(player_name, player_data)
    
    async def _handle_player_quit(self, event_data: Dict[str, Any]):
        """处理玩家退出事件"""
        player_name = event_data.get("name")
        if not player_name:
            return
        
        # 更新玩家数据
        if player_name in self.online_players:
            player_data = self.online_players[player_name]
            
            # 计算本次游戏时长
            if "current_session_start" in player_data:
                session_start = datetime.fromisoformat(player_data["current_session_start"])
                session_duration = (datetime.now() - session_start).total_seconds()
                player_data["total_playtime"] = player_data.get("total_playtime", 0) + session_duration
                del player_data["current_session_start"]
            
            player_data["last_logout"] = event_data.get("timestamp", datetime.now().isoformat())
            player_data["is_online"] = False
            
            # 保存数据
            await self._save_player_data(player_name, player_data)
            
            # 从在线玩家列表移除
            del self.online_players[player_name]
    
    async def _fetch_player_data_from_server(self, identifier: str) -> Optional[Dict[str, Any]]:
        """从服务器获取玩家数据"""
        # 这里需要根据服务器类型和可用插件来实现
        # 基础实现只返回基本信息
        return {
            "name": identifier,
            "uuid": "unknown",
            "first_login": datetime.now().isoformat(),
            "login_count": 0,
            "total_playtime": 0,
            "is_online": identifier in self.online_players
        }
    
    def _parse_player_list(self, output: str) -> List[Dict[str, Any]]:
        """解析玩家列表输出"""
        players = []
        lines = output.split('\n')
        
        for line in lines:
            if "online:" in line.lower():
                # 解析类似 "There are 2/20 players online:" 的行
                continue
            
            # 解析玩家名称列表
            if line.strip() and not line.startswith('['):
                names = [name.strip() for name in line.split(',') if name.strip()]
                for name in names:
                    players.append({"name": name})
        
        return players
    
    async def _save_player_data(self, identifier: str, data: Dict[str, Any]):
        """保存玩家数据到文件"""
        player_file = self.data_dir / f"{identifier}.json"
        try:
            with open(player_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save player data for {identifier}: {e}")
    
    async def _update_player_action(self, identifier: str, action: str, reason: str = None):
        """更新玩家操作记录"""
        player_data = await self.get_player_info(identifier)
        if player_data:
            if "actions" not in player_data:
                player_data["actions"] = []
            
            player_data["actions"].append({
                "action": action,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            })
            
            await self._save_player_data(identifier, player_data)
    
    async def _update_player_ban_status(self, identifier: str, is_banned: bool, reason: str = None, duration: int = None):
        """更新玩家封禁状态"""
        player_data = await self.get_player_info(identifier)
        if player_data:
            player_data["is_banned"] = is_banned
            if is_banned:
                player_data["ban_reason"] = reason
                player_data["banned_at"] = datetime.now().isoformat()
                if duration:
                    player_data["ban_expires"] = (datetime.now() + timedelta(seconds=duration)).isoformat()
            else:
                player_data.pop("ban_reason", None)
                player_data.pop("banned_at", None)
                player_data.pop("ban_expires", None)
            
            await self._save_player_data(identifier, player_data)
    
    async def _update_player_op_status(self, identifier: str, is_op: bool):
        """更新玩家OP状态"""
        player_data = await self.get_player_info(identifier)
        if player_data:
            player_data["is_op"] = is_op
            await self._save_player_data(identifier, player_data)
```

## 📁 5. 文件管理系统

### 5.1 FileManager

**文件路径**: `aetherius/core/file_manager.py`

```python
"""
Aetherius文件管理系统
==================

提供安全的文件操作功能
"""

import os
import stat
import shutil
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, BinaryIO
import logging
import asyncio
import aiofiles
from .events import *
from .event_manager import EventManager

logger = logging.getLogger(__name__)

class FileManager:
    """文件管理器"""
    
    def __init__(self, server_path: Path, event_manager: EventManager):
        self.server_path = Path(server_path).resolve()
        self.event_manager = event_manager
        
        # 安全设置
        self.allowed_extensions = {
            '.txt', '.yml', '.yaml', '.json', '.properties', '.cfg', '.conf',
            '.log', '.md', '.xml', '.ini', '.toml'
        }
        
        # 禁止访问的目录
        self.forbidden_dirs = {
            '__pycache__', '.git', '.svn', '.hg', 'node_modules'
        }
        
        # 最大文件大小 (100MB)
        self.max_file_size = 100 * 1024 * 1024
    
    def _is_safe_path(self, path: Path) -> bool:
        """检查路径是否安全"""
        try:
            # 解析路径
            resolved_path = (self.server_path / path).resolve()
            
            # 确保路径在服务器目录内
            if not str(resolved_path).startswith(str(self.server_path)):
                return False
            
            # 检查是否包含禁止的目录
            for part in resolved_path.parts:
                if part in self.forbidden_dirs:
                    return False
            
            return True
            
        except Exception:
            return False
    
    async def list_files(self, path: str = "", show_hidden: bool = False) -> List[Dict[str, Any]]:
        """
        列出文件和目录
        
        Args:
            path: 相对路径
            show_hidden: 是否显示隐藏文件
            
        Returns:
            文件和目录信息列表
        """
        target_path = self.server_path / path if path else self.server_path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this path")
        
        if not target_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        if not target_path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")
        
        files = []
        
        try:
            for item in target_path.iterdir():
                # 跳过隐藏文件（除非明确要求）
                if not show_hidden and item.name.startswith('.'):
                    continue
                
                try:
                    stat_info = item.stat()
                    
                    file_info = {
                        "name": item.name,
                        "path": str(item.relative_to(self.server_path)),
                        "is_directory": item.is_dir(),
                        "size": stat_info.st_size if item.is_file() else None,
                        "modified_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                        "created_time": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                        "permissions": stat.filemode(stat_info.st_mode),
                        "is_readable": os.access(item, os.R_OK),
                        "is_writable": os.access(item, os.W_OK),
                        "mime_type": mimetypes.guess_type(item.name)[0] if item.is_file() else None
                    }
                    
                    files.append(file_info)
                    
                except (OSError, PermissionError) as e:
                    logger.warning(f"Failed to get info for {item}: {e}")
                    continue
        
        except PermissionError:
            raise PermissionError("Permission denied to list directory")
        
        # 按类型和名称排序
        files.sort(key=lambda x: (not x["is_directory"], x["name"].lower()))
        
        return files
    
    async def read_file(self, path: str, encoding: str = "utf-8") -> str:
        """
        读取文件内容
        
        Args:
            path: 文件相对路径
            encoding: 文件编码
            
        Returns:
            文件内容
        """
        file_path = self.server_path / path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this file")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        
        # 检查文件大小
        if file_path.stat().st_size > self.max_file_size:
            raise ValueError("File too large to read")
        
        # 检查文件扩展名
        if file_path.suffix.lower() not in self.allowed_extensions:
            logger.warning(f"Reading file with potentially unsafe extension: {path}")
        
        try:
            async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                content = await f.read()
            
            logger.info(f"Read file: {path}")
            return content
            
        except UnicodeDecodeError:
            # 尝试二进制模式读取
            async with aiofiles.open(file_path, 'rb') as f:
                binary_content = await f.read()
            
            # 返回base64编码的内容
            import base64
            return base64.b64encode(binary_content).decode('ascii')
    
    async def write_file(self, path: str, content: str, encoding: str = "utf-8", backup: bool = True):
        """
        写入文件内容
        
        Args:
            path: 文件相对路径
            content: 文件内容
            encoding: 文件编码
            backup: 是否创建备份
        """
        file_path = self.server_path / path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this file")
        
        # 检查文件扩展名
        if file_path.suffix.lower() not in self.allowed_extensions:
            raise PermissionError(f"Writing files with extension {file_path.suffix} is not allowed")
        
        # 检查内容大小
        if len(content.encode(encoding)) > self.max_file_size:
            raise ValueError("Content too large")
        
        # 创建备份
        if backup and file_path.exists():
            backup_path = file_path.with_suffix(f"{file_path.suffix}.backup.{int(datetime.now().timestamp())}")
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
        
        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
                await f.write(content)
            
            await self.event_manager.emit_event(
                FILE_CHANGE,
                {
                    "path": path,
                    "action": "write",
                    "size": len(content),
                    "timestamp": datetime.now().isoformat()
                },
                source="file_manager"
            )
            
            logger.info(f"Wrote file: {path}")
            
        except Exception as e:
            logger.error(f"Failed to write file {path}: {e}")
            raise
    
    async def create_file(self, path: str, content: str = "", encoding: str = "utf-8"):
        """
        创建新文件
        
        Args:
            path: 文件相对路径
            content: 初始内容
            encoding: 文件编码
        """
        file_path = self.server_path / path
        
        if file_path.exists():
            raise FileExistsError(f"File already exists: {path}")
        
        await self.write_file(path, content, encoding, backup=False)
        
        await self.event_manager.emit_event(
            FILE_CREATE,
            {
                "path": path,
                "timestamp": datetime.now().isoformat()
            },
            source="file_manager"
        )
    
    async def delete_file(self, path: str, permanent: bool = False):
        """
        删除文件
        
        Args:
            path: 文件相对路径
            permanent: 是否永久删除（否则移动到回收站）
        """
        file_path = self.server_path / path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this file")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not permanent:
            # 移动到回收站目录
            trash_dir = self.server_path / ".trash"
            trash_dir.mkdir(exist_ok=True)
            
            timestamp = int(datetime.now().timestamp())
            trash_path = trash_dir / f"{file_path.name}.{timestamp}"
            
            shutil.move(str(file_path), str(trash_path))
            logger.info(f"Moved to trash: {path} -> {trash_path}")
        else:
            # 永久删除
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()
            logger.info(f"Permanently deleted: {path}")
        
        await self.event_manager.emit_event(
            FILE_DELETE,
            {
                "path": path,
                "permanent": permanent,
                "timestamp": datetime.now().isoformat()
            },
            source="file_manager"
        )
    
    async def create_directory(self, path: str):
        """
        创建目录
        
        Args:
            path: 目录相对路径
        """
        dir_path = self.server_path / path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this path")
        
        if dir_path.exists():
            raise FileExistsError(f"Directory already exists: {path}")
        
        dir_path.mkdir(parents=True)
        
        await self.event_manager.emit_event(
            FILE_CREATE,
            {
                "path": path,
                "is_directory": True,
                "timestamp": datetime.now().isoformat()
            },
            source="file_manager"
        )
        
        logger.info(f"Created directory: {path}")
    
    async def copy_file(self, source_path: str, dest_path: str):
        """
        复制文件
        
        Args:
            source_path: 源文件路径
            dest_path: 目标文件路径
        """
        source = self.server_path / source_path
        dest = self.server_path / dest_path
        
        if not self._is_safe_path(Path(source_path)) or not self._is_safe_path(Path(dest_path)):
            raise PermissionError("Access denied")
        
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        if dest.exists():
            raise FileExistsError(f"Destination already exists: {dest_path}")
        
        # 确保目标目录存在
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        if source.is_dir():
            shutil.copytree(source, dest)
        else:
            shutil.copy2(source, dest)
        
        logger.info(f"Copied: {source_path} -> {dest_path}")
    
    async def move_file(self, source_path: str, dest_path: str):
        """
        移动文件
        
        Args:
            source_path: 源文件路径
            dest_path: 目标文件路径
        """
        source = self.server_path / source_path
        dest = self.server_path / dest_path
        
        if not self._is_safe_path(Path(source_path)) or not self._is_safe_path(Path(dest_path)):
            raise PermissionError("Access denied")
        
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        if dest.exists():
            raise FileExistsError(f"Destination already exists: {dest_path}")
        
        # 确保目标目录存在
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.move(str(source), str(dest))
        
        logger.info(f"Moved: {source_path} -> {dest_path}")
    
    async def upload_file(self, path: str, file_data: bytes, overwrite: bool = False):
        """
        上传文件
        
        Args:
            path: 目标文件路径
            file_data: 文件数据
            overwrite: 是否覆盖已存在的文件
        """
        file_path = self.server_path / path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this path")
        
        if file_path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {path}")
        
        # 检查文件大小
        if len(file_data) > self.max_file_size:
            raise ValueError("File too large")
        
        # 检查文件扩展名
        if file_path.suffix.lower() not in self.allowed_extensions:
            raise PermissionError(f"Uploading files with extension {file_path.suffix} is not allowed")
        
        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_data)
        
        await self.event_manager.emit_event(
            FILE_CREATE,
            {
                "path": path,
                "size": len(file_data),
                "upload": True,
                "timestamp": datetime.now().isoformat()
            },
            source="file_manager"
        )
        
        logger.info(f"Uploaded file: {path} ({len(file_data)} bytes)")
    
    async def download_file(self, path: str) -> bytes:
        """
        下载文件
        
        Args:
            path: 文件相对路径
            
        Returns:
            文件数据
        """
        file_path = self.server_path / path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this file")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        
        # 检查文件大小
        if file_path.stat().st_size > self.max_file_size:
            raise ValueError("File too large to download")
        
        async with aiofiles.open(file_path, 'rb') as f:
            data = await f.read()
        
        logger.info(f"Downloaded file: {path} ({len(data)} bytes)")
        return data
    
    async def get_file_info(self, path: str) -> Dict[str, Any]:
        """
        获取文件详细信息
        
        Args:
            path: 文件相对路径
            
        Returns:
            文件信息字典
        """
        file_path = self.server_path / path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this file")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        stat_info = file_path.stat()
        
        return {
            "name": file_path.name,
            "path": path,
            "absolute_path": str(file_path),
            "is_directory": file_path.is_dir(),
            "is_file": file_path.is_file(),
            "size": stat_info.st_size,
            "modified_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "created_time": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
            "accessed_time": datetime.fromtimestamp(stat_info.st_atime).isoformat(),
            "permissions": stat.filemode(stat_info.st_mode),
            "owner_uid": stat_info.st_uid,
            "owner_gid": stat_info.st_gid,
            "is_readable": os.access(file_path, os.R_OK),
            "is_writable": os.access(file_path, os.W_OK),
            "is_executable": os.access(file_path, os.X_OK),
            "mime_type": mimetypes.guess_type(file_path.name)[0],
            "extension": file_path.suffix.lower()
        }
    
    async def search_files(self, query: str, path: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """
        搜索文件
        
        Args:
            query: 搜索关键词
            path: 搜索路径
            limit: 结果限制
            
        Returns:
            匹配的文件列表
        """
        search_path = self.server_path / path if path else self.server_path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this path")
        
        matches = []
        query_lower = query.lower()
        
        def search_recursive(current_path: Path, depth: int = 0):
            if depth > 10 or len(matches) >= limit:  # 限制搜索深度和结果数量
                return
            
            try:
                for item in current_path.iterdir():
                    if len(matches) >= limit:
                        break
                    
                    # 跳过隐藏文件和目录
                    if item.name.startswith('.'):
                        continue
                    
                    # 检查文件名匹配
                    if query_lower in item.name.lower():
                        try:
                            stat_info = item.stat()
                            matches.append({
                                "name": item.name,
                                "path": str(item.relative_to(self.server_path)),
                                "is_directory": item.is_dir(),
                                "size": stat_info.st_size if item.is_file() else None,
                                "modified_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                            })
                        except (OSError, PermissionError):
                            continue
                    
                    # 递归搜索子目录
                    if item.is_dir() and not any(forbidden in item.name for forbidden in self.forbidden_dirs):
                        search_recursive(item, depth + 1)
                        
            except (OSError, PermissionError):
                pass
        
        await asyncio.get_event_loop().run_in_executor(None, search_recursive, search_path)
        
        return matches
    
    def get_disk_usage(self, path: str = "") -> Dict[str, Any]:
        """
        获取磁盘使用情况
        
        Args:
            path: 路径
            
        Returns:
            磁盘使用信息
        """
        target_path = self.server_path / path if path else self.server_path
        
        if not self._is_safe_path(Path(path)):
            raise PermissionError("Access denied to this path")
        
        usage = shutil.disk_usage(target_path)
        
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent_used": (usage.used / usage.total) * 100
        }
```

## ⚙️ 6. 配置管理扩展

### 6.1 ConfigManager增强

**文件路径**: `aetherius/core/config.py`

```python
"""
Aetherius配置管理系统 - 增强版
============================

支持组件配置、验证和热重载
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
import logging
from datetime import datetime
import asyncio
from .events import *
from .event_manager import EventManager

logger = logging.getLogger(__name__)

@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    component: str
    old_value: Any
    new_value: Any
    key_path: str
    timestamp: datetime

class ConfigManager:
    """配置管理器 - 增强版"""
    
    def __init__(self, config_dir: Path, event_manager: EventManager):
        self.config_dir = Path(config_dir)
        self.event_manager = event_manager
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置存储
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._config_schemas: Dict[str, Dict[str, Any]] = {}
        self._change_callbacks: Dict[str, List[Callable]] = {}
        
        # 文件监控
        self._file_watchers: Dict[str, asyncio.Task] = {}
        
        # 加载主配置
        self._load_main_config()
    
    def _load_main_config(self):
        """加载主配置文件"""
        main_config_file = self.config_dir / "config.yaml"
        
        if main_config_file.exists():
            try:
                with open(main_config_file, 'r', encoding='utf-8') as f:
                    self._configs['main'] = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load main config: {e}")
                self._configs['main'] = {}
        else:
            # 创建默认配置
            self._configs['main'] = self._get_default_main_config()
            self._save_config('main')
    
    def _get_default_main_config(self) -> Dict[str, Any]:
        """获取默认主配置"""
        return {
            "server": {
                "jar_path": "server/server.jar",
                "java_args": ["-Xmx2G", "-Xms1G"],
                "auto_start": False,
                "auto_restart": True
            },
            "logging": {
                "level": "INFO",
                "file": "logs/aetherius.log",
                "max_size": "10MB",
                "backup_count": 5
            },
            "components": {
                "enabled": [],
                "disabled": [],
                "auto_load": True
            },
            "security": {
                "allowed_commands": [],
                "restricted_files": [],
                "max_file_size": 104857600  # 100MB
            }
        }
    
    def get_config(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key_path: 配置键路径，如 "server.java_args" 或 "components.web.port"
            default: 默认值
            
        Returns:
            配置值
        """
        parts = key_path.split('.')
        
        # 确定配置域
        if len(parts) >= 2 and parts[0] == "components":
            component_name = parts[1]
            config_key = '.'.join(parts[2:]) if len(parts) > 2 else ""
            return self._get_component_config_value(component_name, config_key, default)
        else:
            # 主配置
            config = self._configs.get('main', {})
            
            for part in parts:
                if isinstance(config, dict) and part in config:
                    config = config[part]
                else:
                    return default
            
            return config
    
    def set_config(self, key_path: str, value: Any, save: bool = True):
        """
        设置配置值
        
        Args:
            key_path: 配置键路径
            value: 配置值
            save: 是否立即保存
        """
        parts = key_path.split('.')
        
        if len(parts) >= 2 and parts[0] == "components":
            component_name = parts[1]
            config_key = '.'.join(parts[2:]) if len(parts) > 2 else ""
            self._set_component_config_value(component_name, config_key, value, save)
        else:
            # 主配置
            config = self._configs.setdefault('main', {})
            
            # 导航到父级配置
            for part in parts[:-1]:
                config = config.setdefault(part, {})
            
            old_value = config.get(parts[-1])
            config[parts[-1]] = value
            
            if save:
                self._save_config('main')
            
            # 触发变更事件
            asyncio.create_task(self.event_manager.emit_event(
                CONFIG_CHANGE,
                {
                    "component": "main",
                    "key_path": key_path,
                    "old_value": old_value,
                    "new_value": value
                },
                source="config_manager"
            ))
    
    def get_component_config(self, component_name: str) -> Dict[str, Any]:
        """
        获取组件配置
        
        Args:
            component_name: 组件名称
            
        Returns:
            组件配置字典
        """
        return self._configs.get(f"component_{component_name}", {})
    
    def set_component_config(self, component_name: str, config: Dict[str, Any], validate: bool = True):
        """
        设置组件配置
        
        Args:
            component_name: 组件名称
            config: 配置字典
            validate: 是否验证配置
        """
        if validate and not self.validate_component_config(component_name, config):
            raise ValueError(f"Invalid configuration for component: {component_name}")
        
        old_config = self._configs.get(f"component_{component_name}", {})
        self._configs[f"component_{component_name}"] = config.copy()
        
        # 保存配置
        self._save_config(f"component_{component_name}")
        
        # 触发变更事件
        asyncio.create_task(self.event_manager.emit_event(
            CONFIG_CHANGE,
            {
                "component": component_name,
                "key_path": "",
                "old_value": old_config,
                "new_value": config
            },
            source="config_manager"
        ))
        
        # 调用变更回调
        callbacks = self._change_callbacks.get(component_name, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(config))
                else:
                    callback(config)
            except Exception as e:
                logger.error(f"Error in config change callback for {component_name}: {e}")
    
    def register_component_config(self, component_name: str, schema: Dict[str, Any], default_config: Dict[str, Any]):
        """
        注册组件配置架构
        
        Args:
            component_name: 组件名称
            schema: 配置架构
            default_config: 默认配置
        """
        self._config_schemas[component_name] = schema
        
        # 如果组件配置不存在，使用默认配置
        if f"component_{component_name}" not in self._configs:
            self.set_component_config(component_name, default_config, validate=False)
        else:
            # 合并默认配置（添加缺失的键）
            existing_config = self._configs[f"component_{component_name}"]
            merged_config = self._merge_configs(default_config, existing_config)
            self._configs[f"component_{component_name}"] = merged_config
            self._save_config(f"component_{component_name}")
    
    def get_config_schema(self, component_name: str) -> Dict[str, Any]:
        """
        获取组件配置架构
        
        Args:
            component_name: 组件名称
            
        Returns:
            配置架构
        """
        return self._config_schemas.get(component_name, {})
    
    def validate_component_config(self, component_name: str, config: Dict[str, Any]) -> bool:
        """
        验证组件配置
        
        Args:
            component_name: 组件名称
            config: 要验证的配置
            
        Returns:
            是否验证通过
        """
        schema = self._config_schemas.get(component_name)
        if not schema:
            return True  # 没有架构则认为有效
        
        return self._validate_config_against_schema(config, schema)
    
    def _validate_config_against_schema(self, config: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """根据架构验证配置"""
        for key, schema_def in schema.items():
            if key not in config:
                # 检查是否为必需字段
                if schema_def.get("required", False):
                    logger.error(f"Required config key missing: {key}")
                    return False
                continue
            
            value = config[key]
            expected_type = schema_def.get("type")
            
            # 类型检查
            if expected_type:
                if not self._check_type(value, expected_type):
                    logger.error(f"Invalid type for {key}: expected {expected_type}, got {type(value).__name__}")
                    return False
            
            # 枚举检查
            enum_values = schema_def.get("enum")
            if enum_values and value not in enum_values:
                logger.error(f"Invalid value for {key}: {value} not in {enum_values}")
                return False
            
            # 范围检查
            min_val = schema_def.get("min")
            max_val = schema_def.get("max")
            if min_val is not None and value < min_val:
                logger.error(f"Value for {key} below minimum: {value} < {min_val}")
                return False
            if max_val is not None and value > max_val:
                logger.error(f"Value for {key} above maximum: {value} > {max_val}")
                return False
        
        return True
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值的类型"""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True
    
    def _merge_configs(self, default: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
        """合并配置，保留现有值，添加缺失的默认值"""
        result = existing.copy()
        
        for key, value in default.items():
            if key not in result:
                result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                result[key] = self._merge_configs(value, result[key])
        
        return result
    
    def _get_component_config_value(self, component_name: str, key_path: str, default: Any) -> Any:
        """获取组件配置值"""
        config = self.get_component_config(component_name)
        
        if not key_path:
            return config
        
        parts = key_path.split('.')
        for part in parts:
            if isinstance(config, dict) and part in config:
                config = config[part]
            else:
                return default
        
        return config
    
    def _set_component_config_value(self, component_name: str, key_path: str, value: Any, save: bool):
        """设置组件配置值"""
        config = self._configs.setdefault(f"component_{component_name}", {})
        
        if not key_path:
            # 替换整个配置
            old_config = config.copy()
            self._configs[f"component_{component_name}"] = value
        else:
            # 设置特定键
            parts = key_path.split('.')
            
            # 导航到父级配置
            for part in parts[:-1]:
                config = config.setdefault(part, {})
            
            old_value = config.get(parts[-1])
            config[parts[-1]] = value
            
            # 触发变更事件
            asyncio.create_task(self.event_manager.emit_event(
                CONFIG_CHANGE,
                {
                    "component": component_name,
                    "key_path": key_path,
                    "old_value": old_value,
                    "new_value": value
                },
                source="config_manager"
            ))
        
        if save:
            self._save_config(f"component_{component_name}")
    
    def _save_config(self, config_name: str):
        """保存配置到文件"""
        config = self._configs.get(config_name, {})
        
        if config_name == "main":
            config_file = self.config_dir / "config.yaml"
        else:
            config_file = self.config_dir / f"{config_name}.yaml"
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            logger.debug(f"Saved config: {config_name}")
            
        except Exception as e:
            logger.error(f"Failed to save config {config_name}: {e}")
    
    def reload_config(self, config_name: str = None):
        """
        重新加载配置
        
        Args:
            config_name: 配置名称，None表示重载所有配置
        """
        if config_name:
            self._reload_single_config(config_name)
        else:
            # 重载所有配置
            self._load_main_config()
            
            for config_file in self.config_dir.glob("component_*.yaml"):
                component_name = config_file.stem.replace("component_", "")
                self._reload_single_config(f"component_{component_name}")
        
        asyncio.create_task(self.event_manager.emit_event(
            CONFIG_RELOAD,
            {"config_name": config_name},
            source="config_manager"
        ))
    
    def _reload_single_config(self, config_name: str):
        """重新加载单个配置"""
        if config_name == "main":
            config_file = self.config_dir / "config.yaml"
        else:
            config_file = self.config_dir / f"{config_name}.yaml"
        
        if not config_file.exists():
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                new_config = yaml.safe_load(f) or {}
            
            old_config = self._configs.get(config_name, {})
            self._configs[config_name] = new_config
            
            # 如果是组件配置，触发回调
            if config_name.startswith("component_"):
                component_name = config_name.replace("component_", "")
                callbacks = self._change_callbacks.get(component_name, [])
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            asyncio.create_task(callback(new_config))
                        else:
                            callback(new_config)
                    except Exception as e:
                        logger.error(f"Error in config reload callback for {component_name}: {e}")
            
            logger.info(f"Reloaded config: {config_name}")
            
        except Exception as e:
            logger.error(f"Failed to reload config {config_name}: {e}")
    
    def register_change_callback(self, component_name: str, callback: Callable):
        """
        注册配置变更回调
        
        Args:
            component_name: 组件名称
            callback: 回调函数
        """
        if component_name not in self._change_callbacks:
            self._change_callbacks[component_name] = []
        
        self._change_callbacks[component_name].append(callback)
    
    def unregister_change_callback(self, component_name: str, callback: Callable):
        """注销配置变更回调"""
        callbacks = self._change_callbacks.get(component_name, [])
        if callback in callbacks:
            callbacks.remove(callback)
    
    def export_config(self, component_name: str = None, format: str = "yaml") -> str:
        """
        导出配置
        
        Args:
            component_name: 组件名称，None表示导出所有配置
            format: 导出格式 (yaml, json)
            
        Returns:
            配置字符串
        """
        if component_name:
            config = self.get_component_config(component_name)
        else:
            config = self._configs.copy()
        
        if format == "json":
            return json.dumps(config, indent=2, ensure_ascii=False)
        else:
            return yaml.dump(config, default_flow_style=False, allow_unicode=True, indent=2)
    
    def import_config(self, config_data: str, component_name: str = None, format: str = "yaml", validate: bool = True):
        """
        导入配置
        
        Args:
            config_data: 配置数据字符串
            component_name: 组件名称，None表示导入主配置
            format: 数据格式 (yaml, json)
            validate: 是否验证配置
        """
        if format == "json":
            config = json.loads(config_data)
        else:
            config = yaml.safe_load(config_data)
        
        if component_name:
            self.set_component_config(component_name, config, validate)
        else:
            # 导入主配置
            if validate:
                # 这里可以添加主配置的验证逻辑
                pass
            
            old_config = self._configs.get('main', {})
            self._configs['main'] = config
            self._save_config('main')
            
            asyncio.create_task(self.event_manager.emit_event(
                CONFIG_CHANGE,
                {
                    "component": "main",
                    "key_path": "",
                    "old_value": old_config,
                    "new_value": config
                },
                source="config_manager"
            ))
    
    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置"""
        return self._configs.copy()
    
    def get_component_list(self) -> List[str]:
        """获取所有已注册组件的列表"""
        components = []
        for config_name in self._configs.keys():
            if config_name.startswith("component_"):
                components.append(config_name.replace("component_", ""))
        return components
    
    def backup_config(self, backup_dir: Path = None) -> str:
        """
        备份配置
        
        Args:
            backup_dir: 备份目录
            
        Returns:
            备份文件路径
        """
        if backup_dir is None:
            backup_dir = self.config_dir / "backups"
        
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"config_backup_{timestamp}.yaml"
        
        all_configs = self.get_all_configs()
        
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                yaml.dump(all_configs, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            logger.info(f"Configuration backed up to: {backup_file}")
            return str(backup_file)
            
        except Exception as e:
            logger.error(f"Failed to backup configuration: {e}")
            raise
    
    def restore_config(self, backup_file: Path):
        """
        从备份恢复配置
        
        Args:
            backup_file: 备份文件路径
        """
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
        
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_configs = yaml.safe_load(f)
            
            # 恢复配置
            for config_name, config_data in backup_configs.items():
                self._configs[config_name] = config_data
                self._save_config(config_name)
            
            # 触发重载事件
            asyncio.create_task(self.event_manager.emit_event(
                CONFIG_RELOAD,
                {"restored_from": str(backup_file)},
                source="config_manager"
            ))
            
            logger.info(f"Configuration restored from: {backup_file}")
            
        except Exception as e:
            logger.error(f"Failed to restore configuration: {e}")
            raise
```

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "create_comprehensive_core_extensions_doc", "content": "\u521b\u5efa\u5b8c\u6574\u7684Aetherius\u6838\u5fc3\u6269\u5c55\u9700\u6c42\u6587\u6863", "status": "completed", "priority": "high"}]
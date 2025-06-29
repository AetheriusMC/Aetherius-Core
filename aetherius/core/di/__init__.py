"""
Aetherius Core 依赖注入框架

提供轻量级、高性能的依赖注入容器，支持：
- 接口-实现分离
- 生命周期管理（单例、瞬态、作用域）
- 自动装配和手动注册
- 循环依赖检测
- 条件注册和动态切换
"""

from typing import TypeVar, Type, Any, Optional, Dict, Set, Callable, Union
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import inspect
from dataclasses import dataclass, field
from weakref import WeakSet

__all__ = [
    'ServiceLifetime', 'ServiceDescriptor', 'IDependencyContainer', 
    'DependencyContainer', 'Injectable', 'inject', 'singleton', 
    'transient', 'scoped', 'conditional'
]

T = TypeVar('T')


class ServiceLifetime(Enum):
    """服务生命周期枚举"""
    SINGLETON = "singleton"      # 单例：整个应用生命周期内唯一
    TRANSIENT = "transient"      # 瞬态：每次请求创建新实例
    SCOPED = "scoped"           # 作用域：在特定作用域内唯一


@dataclass
class ServiceDescriptor:
    """服务描述符，包含服务注册的所有信息"""
    service_type: Type[T]                          # 服务接口类型
    implementation_type: Optional[Type[T]] = None  # 实现类型
    factory: Optional[Callable[..., T]] = None     # 工厂函数
    instance: Optional[T] = None                   # 预创建实例
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    dependencies: Set[Type] = field(default_factory=set)
    conditions: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0                              # 注册优先级
    tags: Set[str] = field(default_factory=set)   # 服务标签


class IDependencyContainer(ABC):
    """依赖注入容器接口"""
    
    @abstractmethod
    def register(self, 
                service_type: Type[T], 
                implementation_type: Optional[Type[T]] = None,
                lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
                factory: Optional[Callable[..., T]] = None,
                conditions: Optional[Dict[str, Any]] = None) -> 'IDependencyContainer':
        """注册服务"""
        pass
    
    @abstractmethod
    def register_instance(self, service_type: Type[T], instance: T) -> 'IDependencyContainer':
        """注册服务实例"""
        pass
    
    @abstractmethod
    def resolve(self, service_type: Type[T]) -> T:
        """解析服务实例"""
        pass
    
    @abstractmethod
    async def resolve_async(self, service_type: Type[T]) -> T:
        """异步解析服务实例"""
        pass
    
    @abstractmethod
    def is_registered(self, service_type: Type[T]) -> bool:
        """检查服务是否已注册"""
        pass
    
    @abstractmethod
    def create_scope(self) -> 'IDependencyScope':
        """创建服务作用域"""
        pass


class IDependencyScope(ABC):
    """依赖注入作用域接口"""
    
    @abstractmethod
    def resolve(self, service_type: Type[T]) -> T:
        """在当前作用域解析服务"""
        pass
    
    @abstractmethod
    async def resolve_async(self, service_type: Type[T]) -> T:
        """在当前作用域异步解析服务"""
        pass
    
    @abstractmethod
    def dispose(self):
        """释放作用域资源"""
        pass


class Injectable:
    """标记类为可注入服务的装饰器"""
    
    def __init__(self, 
                 interface: Optional[Type] = None,
                 lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
                 conditions: Optional[Dict[str, Any]] = None,
                 tags: Optional[Set[str]] = None):
        self.interface = interface
        self.lifetime = lifetime
        self.conditions = conditions or {}
        self.tags = tags or set()
    
    def __call__(self, cls: Type[T]) -> Type[T]:
        """装饰器调用"""
        # 添加元数据到类
        cls.__di_interface__ = self.interface or cls
        cls.__di_lifetime__ = self.lifetime
        cls.__di_conditions__ = self.conditions
        cls.__di_tags__ = self.tags
        return cls


def inject(service_type: Type[T]) -> T:
    """依赖注入装饰器工厂"""
    return service_type  # 类型提示用，实际值由容器在运行时注入


def singleton(interface: Optional[Type] = None, **kwargs):
    """单例服务装饰器"""
    return Injectable(interface=interface, lifetime=ServiceLifetime.SINGLETON, **kwargs)


def transient(interface: Optional[Type] = None, **kwargs):
    """瞬态服务装饰器"""
    return Injectable(interface=interface, lifetime=ServiceLifetime.TRANSIENT, **kwargs)


def scoped(interface: Optional[Type] = None, **kwargs):
    """作用域服务装饰器"""
    return Injectable(interface=interface, lifetime=ServiceLifetime.SCOPED, **kwargs)


def conditional(**conditions):
    """条件注册装饰器"""
    def decorator(cls):
        if not hasattr(cls, '__di_conditions__'):
            cls.__di_conditions__ = {}
        cls.__di_conditions__.update(conditions)
        return cls
    return decorator


# Import concrete implementation
from .container import DependencyContainer
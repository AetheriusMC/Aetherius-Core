"""
依赖注入容器实现

提供高性能、功能完整的依赖注入容器实现
"""

import asyncio
import inspect
import threading
import weakref
from typing import Dict, Set, Type, Any, Optional, List, Callable, TypeVar, get_type_hints
from collections import defaultdict, deque
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

from . import (
    IDependencyContainer, IDependencyScope, ServiceDescriptor, 
    ServiceLifetime, Injectable
)
from ..exceptions import (
    DependencyResolutionError, CircularDependencyError, 
    ServiceNotRegisteredError, InvalidServiceRegistrationError
)

T = TypeVar('T')


class DependencyScope(IDependencyScope):
    """依赖注入作用域实现"""
    
    def __init__(self, container: 'DependencyContainer', scope_id: str):
        self.container = container
        self.scope_id = scope_id
        self._scoped_instances: Dict[Type, Any] = {}
        self._disposed = False
        self._lock = threading.RLock()
    
    def resolve(self, service_type: Type[T]) -> T:
        """在当前作用域解析服务"""
        if self._disposed:
            raise RuntimeError(f"Scope {self.scope_id} has been disposed")
        
        with self._lock:
            # 检查作用域缓存
            if service_type in self._scoped_instances:
                return self._scoped_instances[service_type]
            
            # 从容器解析
            instance = self.container._resolve_with_scope(service_type, self)
            
            # 如果是作用域服务，缓存实例
            descriptor = self.container._get_service_descriptor(service_type)
            if descriptor and descriptor.lifetime == ServiceLifetime.SCOPED:
                self._scoped_instances[service_type] = instance
            
            return instance
    
    async def resolve_async(self, service_type: Type[T]) -> T:
        """异步解析服务"""
        if self._disposed:
            raise RuntimeError(f"Scope {self.scope_id} has been disposed")
        
        # 对于同步解析，在线程池中执行
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.resolve, service_type)
    
    def dispose(self):
        """释放作用域资源"""
        if self._disposed:
            return
        
        with self._lock:
            # 释放实现了 dispose 方法的实例
            for instance in self._scoped_instances.values():
                if hasattr(instance, 'dispose') and callable(instance.dispose):
                    try:
                        instance.dispose()
                    except Exception as e:
                        # 记录但不抛出异常
                        import logging
                        logging.warning(f"Error disposing scoped instance: {e}")
            
            self._scoped_instances.clear()
            self._disposed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()


class DependencyContainer(IDependencyContainer):
    """依赖注入容器实现"""
    
    def __init__(self):
        self._services: Dict[Type, List[ServiceDescriptor]] = defaultdict(list)
        self._singletons: Dict[Type, Any] = {}
        self._building_services: Set[Type] = set()  # 循环依赖检测
        self._lock = threading.RLock()
        self._scope_counter = 0
        self._active_scopes: weakref.WeakSet = weakref.WeakSet()
        
        # 注册容器自身
        self.register_instance(IDependencyContainer, self)
        self.register_instance(DependencyContainer, self)
    
    def register(self, 
                service_type: Type[T], 
                implementation_type: Optional[Type[T]] = None,
                lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
                factory: Optional[Callable[..., T]] = None,
                conditions: Optional[Dict[str, Any]] = None) -> 'DependencyContainer':
        """注册服务"""
        
        if implementation_type is None and factory is None:
            implementation_type = service_type
        
        if implementation_type and factory:
            raise InvalidServiceRegistrationError(
                "Cannot specify both implementation_type and factory"
            )
        
        # 验证实现类型
        if implementation_type:
            if not issubclass(implementation_type, service_type):
                raise InvalidServiceRegistrationError(
                    f"{implementation_type} does not implement {service_type}"
                )
        
        # 分析依赖关系
        dependencies = set()
        if implementation_type:
            dependencies = self._analyze_dependencies(implementation_type)
        elif factory:
            dependencies = self._analyze_function_dependencies(factory)
        
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifetime=lifetime,
            dependencies=dependencies,
            conditions=conditions or {}
        )
        
        with self._lock:
            self._services[service_type].append(descriptor)
            # 按优先级排序
            self._services[service_type].sort(key=lambda x: x.priority, reverse=True)
        
        return self
    
    def register_instance(self, service_type: Type[T], instance: T) -> 'DependencyContainer':
        """注册服务实例"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON
        )
        
        with self._lock:
            self._services[service_type] = [descriptor]  # 替换现有注册
            self._singletons[service_type] = instance
        
        return self
    
    def register_factory(self, 
                        service_type: Type[T], 
                        factory: Callable[..., T],
                        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT) -> 'DependencyContainer':
        """注册工厂函数"""
        return self.register(service_type, factory=factory, lifetime=lifetime)
    
    def register_decorator(self, decorator: Callable[[T], T], service_type: Type[T]) -> 'DependencyContainer':
        """注册装饰器"""
        original_factory = self._get_factory(service_type)
        if not original_factory:
            raise ServiceNotRegisteredError(f"Service {service_type} not registered")
        
        def decorated_factory(*args, **kwargs):
            instance = original_factory(*args, **kwargs)
            return decorator(instance)
        
        return self.register_factory(service_type, decorated_factory)
    
    def resolve(self, service_type: Type[T]) -> T:
        """解析服务实例"""
        return self._resolve_with_scope(service_type, None)
    
    async def resolve_async(self, service_type: Type[T]) -> T:
        """异步解析服务实例"""
        # 对于同步解析，在线程池中执行
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.resolve, service_type)
    
    def resolve_all(self, service_type: Type[T]) -> List[T]:
        """解析所有注册的服务实例"""
        with self._lock:
            descriptors = self._services.get(service_type, [])
            if not descriptors:
                raise ServiceNotRegisteredError(f"No services registered for {service_type}")
            
            instances = []
            for descriptor in descriptors:
                instance = self._create_instance(descriptor, None)
                instances.append(instance)
            
            return instances
    
    def is_registered(self, service_type: Type[T]) -> bool:
        """检查服务是否已注册"""
        return service_type in self._services
    
    def create_scope(self) -> IDependencyScope:
        """创建服务作用域"""
        with self._lock:
            self._scope_counter += 1
            scope = DependencyScope(self, f"scope_{self._scope_counter}")
            self._active_scopes.add(scope)
            return scope
    
    def auto_register_assembly(self, module_or_package):
        """自动注册程序集中的所有标记为Injectable的类"""
        import pkgutil
        import importlib
        
        if hasattr(module_or_package, '__path__'):
            # 包
            for _, name, ispkg in pkgutil.iter_modules(module_or_package.__path__):
                module_name = f"{module_or_package.__name__}.{name}"
                try:
                    module = importlib.import_module(module_name)
                    self._register_module_services(module)
                    if ispkg:
                        self.auto_register_assembly(module)
                except ImportError:
                    continue
        else:
            # 模块
            self._register_module_services(module_or_package)
    
    def _register_module_services(self, module):
        """注册模块中的服务"""
        for name in dir(module):
            obj = getattr(module, name)
            if (inspect.isclass(obj) and 
                hasattr(obj, '__di_interface__') and 
                hasattr(obj, '__di_lifetime__')):
                
                interface = obj.__di_interface__
                lifetime = obj.__di_lifetime__
                conditions = getattr(obj, '__di_conditions__', {})
                
                self.register(
                    service_type=interface,
                    implementation_type=obj,
                    lifetime=lifetime,
                    conditions=conditions
                )
    
    def _resolve_with_scope(self, service_type: Type[T], scope: Optional[DependencyScope]) -> T:
        """在指定作用域内解析服务"""
        with self._lock:
            # 循环依赖检测
            if service_type in self._building_services:
                dependency_chain = " -> ".join([str(t) for t in self._building_services])
                raise CircularDependencyError(
                    f"Circular dependency detected: {dependency_chain} -> {service_type}"
                )
            
            descriptor = self._get_service_descriptor(service_type)
            if not descriptor:
                raise ServiceNotRegisteredError(f"Service {service_type} is not registered")
            
            # 检查单例缓存
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                if service_type in self._singletons:
                    return self._singletons[service_type]
            
            # 检查作用域缓存
            if scope and descriptor.lifetime == ServiceLifetime.SCOPED:
                if service_type in scope._scoped_instances:
                    return scope._scoped_instances[service_type]
            
            # 创建实例
            self._building_services.add(service_type)
            try:
                instance = self._create_instance(descriptor, scope)
                
                # 缓存单例
                if descriptor.lifetime == ServiceLifetime.SINGLETON:
                    self._singletons[service_type] = instance
                
                return instance
            finally:
                self._building_services.discard(service_type)
    
    def _get_service_descriptor(self, service_type: Type) -> Optional[ServiceDescriptor]:
        """获取服务描述符"""
        descriptors = self._services.get(service_type, [])
        if not descriptors:
            return None
        
        # 返回第一个匹配条件的描述符
        for descriptor in descriptors:
            if self._check_conditions(descriptor.conditions):
                return descriptor
        
        return descriptors[0]  # 返回优先级最高的
    
    def _create_instance(self, descriptor: ServiceDescriptor, scope: Optional[DependencyScope]) -> Any:
        """创建服务实例"""
        if descriptor.instance is not None:
            return descriptor.instance
        
        if descriptor.factory:
            return self._invoke_factory(descriptor.factory, scope)
        
        if descriptor.implementation_type:
            return self._create_class_instance(descriptor.implementation_type, scope)
        
        raise DependencyResolutionError(f"Cannot create instance for {descriptor.service_type}")
    
    def _create_class_instance(self, cls: Type, scope: Optional[DependencyScope]) -> Any:
        """创建类实例"""
        constructor = cls.__init__
        sig = inspect.signature(constructor)
        
        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                if param.default == inspect.Parameter.empty:
                    raise DependencyResolutionError(
                        f"Cannot resolve parameter '{param_name}' for {cls}: no type annotation"
                    )
                continue
            
            if param.default != inspect.Parameter.empty:
                # 可选参数，尝试解析，失败则使用默认值
                try:
                    if scope:
                        kwargs[param_name] = scope.resolve(param_type)
                    else:
                        kwargs[param_name] = self.resolve(param_type)
                except ServiceNotRegisteredError:
                    continue
            else:
                # 必需参数
                if scope:
                    kwargs[param_name] = scope.resolve(param_type)
                else:
                    kwargs[param_name] = self.resolve(param_type)
        
        return cls(**kwargs)
    
    def _invoke_factory(self, factory: Callable, scope: Optional[DependencyScope]) -> Any:
        """调用工厂函数"""
        sig = inspect.signature(factory)
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                if param.default == inspect.Parameter.empty:
                    raise DependencyResolutionError(
                        f"Cannot resolve parameter '{param_name}' for factory: no type annotation"
                    )
                continue
            
            if param.default != inspect.Parameter.empty:
                # 可选参数
                try:
                    if scope:
                        kwargs[param_name] = scope.resolve(param_type)
                    else:
                        kwargs[param_name] = self.resolve(param_type)
                except ServiceNotRegisteredError:
                    continue
            else:
                # 必需参数
                if scope:
                    kwargs[param_name] = scope.resolve(param_type)
                else:
                    kwargs[param_name] = self.resolve(param_type)
        
        return factory(**kwargs)
    
    def _analyze_dependencies(self, cls: Type) -> Set[Type]:
        """分析类的依赖关系"""
        dependencies = set()
        
        if hasattr(cls, '__init__'):
            sig = inspect.signature(cls.__init__)
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                if param.annotation != inspect.Parameter.empty:
                    dependencies.add(param.annotation)
        
        return dependencies
    
    def _analyze_function_dependencies(self, func: Callable) -> Set[Type]:
        """分析函数的依赖关系"""
        dependencies = set()
        sig = inspect.signature(func)
        
        for param_name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                dependencies.add(param.annotation)
        
        return dependencies
    
    def _check_conditions(self, conditions: Dict[str, Any]) -> bool:
        """检查注册条件"""
        # 这里可以实现复杂的条件检查逻辑
        # 例如：环境变量、配置值、运行时状态等
        return True  # 简化实现
    
    def _get_factory(self, service_type: Type) -> Optional[Callable]:
        """获取服务工厂函数"""
        descriptor = self._get_service_descriptor(service_type)
        if not descriptor:
            return None
        
        if descriptor.factory:
            return descriptor.factory
        
        if descriptor.implementation_type:
            return lambda: self._create_class_instance(descriptor.implementation_type, None)
        
        return None
    
    def get_registration_info(self) -> Dict[str, Any]:
        """获取注册信息（调试用）"""
        info = {}
        for service_type, descriptors in self._services.items():
            service_info = []
            for desc in descriptors:
                desc_info = {
                    'implementation': desc.implementation_type.__name__ if desc.implementation_type else 'Factory',
                    'lifetime': desc.lifetime.value,
                    'dependencies': [dep.__name__ for dep in desc.dependencies],
                    'conditions': desc.conditions,
                    'tags': list(desc.tags)
                }
                service_info.append(desc_info)
            info[service_type.__name__] = service_info
        
        return info
    
    def validate_registrations(self) -> List[str]:
        """验证所有注册是否有效"""
        errors = []
        
        for service_type, descriptors in self._services.items():
            for descriptor in descriptors:
                # 检查循环依赖
                try:
                    self._check_circular_dependencies(descriptor, set())
                except CircularDependencyError as e:
                    errors.append(str(e))
                
                # 检查依赖是否都已注册
                for dependency in descriptor.dependencies:
                    if not self.is_registered(dependency):
                        errors.append(f"Unresolved dependency: {dependency} for {service_type}")
        
        return errors
    
    def _check_circular_dependencies(self, descriptor: ServiceDescriptor, visited: Set[Type]):
        """检查循环依赖"""
        if descriptor.service_type in visited:
            raise CircularDependencyError(f"Circular dependency detected for {descriptor.service_type}")
        
        visited.add(descriptor.service_type)
        
        for dependency in descriptor.dependencies:
            dep_descriptor = self._get_service_descriptor(dependency)
            if dep_descriptor:
                self._check_circular_dependencies(dep_descriptor, visited.copy())
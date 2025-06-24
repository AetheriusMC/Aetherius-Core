"""Component API for Aetherius heavy-weight components."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..core.config import Config
from ..core.event_manager import EventManager


@dataclass
class ComponentInfo:
    """Information about a component."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "Unknown"
    website: Optional[str] = None
    api_version: str = "1.0.0"
    
    # Component-specific fields
    main_class: Optional[str] = None
    depends: List[str] = field(default_factory=list)
    soft_depends: List[str] = field(default_factory=list)
    load_before: List[str] = field(default_factory=list)
    
    # System requirements
    min_python_version: str = "3.11"
    requires_packages: List[str] = field(default_factory=list)


@dataclass
class ComponentContext:
    """Context provided to components during initialization."""
    config: Config
    event_manager: EventManager
    component_manager: 'ComponentManager'
    data_folder: Path
    logger: logging.Logger


class Component(ABC):
    """
    Base class for all Aetherius components.
    
    Components are heavy-weight extensions that provide major functionality
    and can have complex dependencies and requirements.
    """
    
    def __init__(self):
        self.info: Optional[ComponentInfo] = None
        self.context: Optional[ComponentContext] = None
        self.loaded: bool = False
        self.enabled: bool = False
    
    @abstractmethod
    async def on_load(self) -> None:
        """Called when the component is loaded."""
        pass
    
    @abstractmethod
    async def on_enable(self) -> None:
        """Called when the component is enabled."""
        pass
    
    @abstractmethod
    async def on_disable(self) -> None:
        """Called when the component is disabled."""
        pass
    
    async def on_unload(self) -> None:
        """Called when the component is unloaded."""
        pass
    
    async def on_reload(self) -> None:
        """Called when the component is reloaded."""
        await self.on_disable()
        await self.on_enable()
    
    @property
    def name(self) -> str:
        """Get component name."""
        return self.info.name if self.info else "Unknown"
    
    @property
    def version(self) -> str:
        """Get component version."""
        return self.info.version if self.info else "Unknown"
    
    @property
    def logger(self) -> logging.Logger:
        """Get component logger."""
        return self.context.logger if self.context else logging.getLogger(__name__)
    
    @property
    def data_folder(self) -> Path:
        """Get component data folder."""
        return self.context.data_folder if self.context else Path(".")
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        if not self.context:
            return default
        
        component_config = getattr(self.context.config, 'components', {})
        return component_config.get(self.name, {}).get(key, default)
    
    async def get_dependency(self, component_name: str) -> Optional['Component']:
        """Get a dependency component."""
        if not self.context:
            return None
        return self.context.component_manager.get_component(component_name)


class SimpleComponent(Component):
    """
    Simple component wrapper for function-based components.
    
    Allows components to be defined using simple functions instead of classes.
    """
    
    def __init__(self, info: ComponentInfo):
        super().__init__()
        self.info = info
        self._on_load_func = None
        self._on_enable_func = None
        self._on_disable_func = None
        self._on_unload_func = None
        self._on_reload_func = None
    
    def set_lifecycle_hooks(self, **hooks):
        """Set lifecycle hook functions."""
        self._on_load_func = hooks.get('on_load')
        self._on_enable_func = hooks.get('on_enable')
        self._on_disable_func = hooks.get('on_disable')
        self._on_unload_func = hooks.get('on_unload')
        self._on_reload_func = hooks.get('on_reload')
    
    async def on_load(self) -> None:
        if self._on_load_func:
            if hasattr(self._on_load_func, '__call__'):
                result = self._on_load_func()
                if hasattr(result, '__await__'):
                    await result
    
    async def on_enable(self) -> None:
        if self._on_enable_func:
            if hasattr(self._on_enable_func, '__call__'):
                result = self._on_enable_func()
                if hasattr(result, '__await__'):
                    await result
    
    async def on_disable(self) -> None:
        if self._on_disable_func:
            if hasattr(self._on_disable_func, '__call__'):
                result = self._on_disable_func()
                if hasattr(result, '__await__'):
                    await result
    
    async def on_unload(self) -> None:
        if self._on_unload_func:
            if hasattr(self._on_unload_func, '__call__'):
                result = self._on_unload_func()
                if hasattr(result, '__await__'):
                    await result
    
    async def on_reload(self) -> None:
        if self._on_reload_func:
            if hasattr(self._on_reload_func, '__call__'):
                result = self._on_reload_func()
                if hasattr(result, '__await__'):
                    await result
        else:
            await super().on_reload()


# Decorators for component metadata and lifecycle hooks
def component_info(**kwargs) -> callable:
    """Decorator to set component information."""
    def decorator(cls_or_func):
        if hasattr(cls_or_func, '__dict__'):
            cls_or_func.COMPONENT_INFO = kwargs
        return cls_or_func
    return decorator


def component_hook(hook_name: str) -> callable:
    """Decorator to mark functions as component lifecycle hooks."""
    def decorator(func):
        func._component_hook = hook_name
        return func
    return decorator


# Specific lifecycle hook decorators
def on_load(func):
    """Mark function as component load hook."""
    return component_hook('on_load')(func)


def on_enable(func):
    """Mark function as component enable hook."""
    return component_hook('on_enable')(func)


def on_disable(func):
    """Mark function as component disable hook."""
    return component_hook('on_disable')(func)


def on_unload(func):
    """Mark function as component unload hook."""
    return component_hook('on_unload')(func)


def on_reload(func):
    """Mark function as component reload hook."""
    return component_hook('on_reload')(func)
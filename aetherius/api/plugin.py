"""Plugin API for Aetherius - Base classes and interfaces for plugins."""

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

from ..core.config_models import AetheriusConfig
from ..core.event_manager import EventManager

if TYPE_CHECKING:
    from .plugin_manager import PluginManager

logger = logging.getLogger(__name__)


class PluginInfo(BaseModel):
    """Plugin metadata and information."""

    name: str = Field(description="Plugin name")
    version: str = Field(description="Plugin version")
    description: str = Field(description="Plugin description")
    author: str = Field(description="Plugin author")
    website: str | None = Field(default=None, description="Plugin website")

    # Dependencies
    depends: list[str] = Field(default_factory=list, description="Required plugins")
    soft_depends: list[str] = Field(
        default_factory=list, description="Optional plugins"
    )

    # Compatibility
    api_version: str = Field(
        default="0.1.0", description="Required Aetherius API version"
    )
    minecraft_versions: list[str] = Field(
        default_factory=list, description="Supported MC versions"
    )

    # Technical info
    main_class: Optional[str] = Field(default=None, description="Main plugin class")
    entry_point: Optional[str] = Field(default=None, description="Entry point function")


class PluginContext:
    """Context provided to plugins for accessing Aetherius systems."""

    def __init__(
        self,
        config: AetheriusConfig,
        event_manager: EventManager,
        plugin_manager: "PluginManager",
        data_folder: Path,
        logger: logging.Logger,
    ):
        self.config = config
        self.event_manager = event_manager
        self.plugin_manager = plugin_manager
        self.data_folder = data_folder
        self.logger = logger

        # Ensure data folder exists
        self.data_folder.mkdir(parents=True, exist_ok=True)

    def get_plugin(self, name: str) -> Optional["Plugin"]:
        """Get another plugin by name."""
        return self.plugin_manager.get_plugin(name)

    def is_plugin_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        return self.plugin_manager.is_enabled(name)

    async def send_server_command(self, command: str) -> bool:
        """Send a command to the server."""
        # This would be connected to the server wrapper
        from ..core import get_server_wrapper

        wrapper = get_server_wrapper()
        if wrapper and wrapper.is_alive:
            return await wrapper.send_command(command)
        return False


class Plugin(ABC):
    """Base class for all Aetherius plugins."""

    def __init__(self):
        self.info: Optional[PluginInfo] = None
        self.context: Optional[PluginContext] = None
        self.enabled = False
        self.loaded = False

    @abstractmethod
    async def on_load(self) -> None:
        """Called when the plugin is loaded."""
        pass

    @abstractmethod
    async def on_enable(self) -> None:
        """Called when the plugin is enabled."""
        pass

    @abstractmethod
    async def on_disable(self) -> None:
        """Called when the plugin is disabled."""
        pass

    async def on_unload(self) -> None:
        """Called when the plugin is unloaded."""
        pass

    async def on_reload(self) -> None:
        """Called when the plugin is reloaded."""
        await self.on_disable()
        await self.on_enable()

    def get_data_folder(self) -> Path:
        """Get the plugin's data folder."""
        if not self.context:
            raise RuntimeError("Plugin not initialized")
        return self.context.data_folder

    def get_config_file(self, filename: str = "config.yaml") -> Path:
        """Get path to a config file in the plugin's data folder."""
        return self.get_data_folder() / filename

    def get_logger(self) -> logging.Logger:
        """Get the plugin's logger."""
        if not self.context:
            raise RuntimeError("Plugin not initialized")
        return self.context.logger


class SimplePlugin:
    """Simple plugin class for function-based plugins."""

    def __init__(self, info: PluginInfo):
        self.info = info
        self.context: PluginContext | None = None
        self.enabled = False
        self.loaded = False

        # Lifecycle hooks
        self._on_load = None
        self._on_enable = None
        self._on_disable = None
        self._on_unload = None
        self._on_reload = None

    def set_lifecycle_hooks(self, **hooks):
        """Set lifecycle hook functions."""
        self._on_load = hooks.get("on_load")
        self._on_enable = hooks.get("on_enable")
        self._on_disable = hooks.get("on_disable")
        self._on_unload = hooks.get("on_unload")
        self._on_reload = hooks.get("on_reload")

    async def on_load(self) -> None:
        if self._on_load:
            if asyncio.iscoroutinefunction(self._on_load):
                await self._on_load(self.context)
            else:
                self._on_load(self.context)

    async def on_enable(self) -> None:
        if self._on_enable:
            if asyncio.iscoroutinefunction(self._on_enable):
                await self._on_enable(self.context)
            else:
                self._on_enable(self.context)

    async def on_disable(self) -> None:
        if self._on_disable:
            if asyncio.iscoroutinefunction(self._on_disable):
                await self._on_disable(self.context)
            else:
                self._on_disable(self.context)

    async def on_unload(self) -> None:
        if self._on_unload:
            if asyncio.iscoroutinefunction(self._on_unload):
                await self._on_unload(self.context)
            else:
                self._on_unload(self.context)

    async def on_reload(self) -> None:
        if self._on_reload:
            if asyncio.iscoroutinefunction(self._on_reload):
                await self._on_reload(self.context)
            else:
                self._on_reload(self.context)
        else:
            await self.on_disable()
            await self.on_enable()


# Plugin decorators for simple function-based plugins
def plugin_info(**kwargs) -> PluginInfo:
    """Create plugin info from keyword arguments."""
    return PluginInfo(**kwargs)


def plugin_hook(hook_name: str):
    """Decorator to mark functions as plugin lifecycle hooks."""

    def decorator(func):
        func._plugin_hook = hook_name
        return func

    return decorator


# Convenience decorators
def on_load(func):
    """Mark function to be called on plugin load."""
    return plugin_hook("on_load")(func)


def on_enable(func):
    """Mark function to be called on plugin enable."""
    return plugin_hook("on_enable")(func)


def on_disable(func):
    """Mark function to be called on plugin disable."""
    return plugin_hook("on_disable")(func)


def on_unload(func):
    """Mark function to be called on plugin unload."""
    return plugin_hook("on_unload")(func)


def on_reload(func):
    """Mark function to be called on plugin reload."""
    return plugin_hook("on_reload")(func)

"""Public API interfaces for Aetherius."""

from .plugin import (
    Plugin, SimplePlugin, PluginInfo, PluginContext,
    plugin_info, plugin_hook, on_load, on_enable, on_disable, on_unload, on_reload
)
from .component import (
    Component, SimpleComponent, ComponentInfo, ComponentContext,
    component_info, component_hook
)

__all__ = [
    # Plugin API
    "Plugin", "SimplePlugin", "PluginInfo", "PluginContext",
    "plugin_info", "plugin_hook", "on_load", "on_enable", "on_disable", 
    "on_unload", "on_reload",
    # Component API
    "Component", "SimpleComponent", "ComponentInfo", "ComponentContext",
    "component_info", "component_hook"
]
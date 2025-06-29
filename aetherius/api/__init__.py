"""
Public API interfaces for Aetherius
===================================

This module provides the complete, unified API for Aetherius Core.
The main entry point is the AetheriusCoreAPI class which provides
comprehensive access to all functionality.

Example usage:
    async with AetheriusCoreAPI() as api:
        # Server management
        await api.server.start()

        # Plugin management
        await api.plugins.load("example")

        # Player management
        players = await api.players.list()

        # System monitoring
        health = await api.monitoring.get_system_health()
"""

# Core unified API (recommended)
from .component import (
    Component,
    ComponentContext,
    ComponentInfo,
    SimpleComponent,
    component_hook,
    component_info,
)
from .core import (
    AetheriusCoreAPI,
    ComponentAPI,
    EventAPI,
    MonitoringAPI,
    PlayerAPI,
    PluginAPI,
    ServerAPI,
    create_core_api,
    get_core_api,
    set_global_api,
)
# from .enhanced import EnhancedAetheriusAPI, EnhancedComponent
from .management import AetheriusManagementAPI, ControlLevel, InfoStreamType

# Legacy/specialized APIs (for backward compatibility)
from .plugin import (
    Plugin,
    PluginContext,
    PluginInfo,
    SimplePlugin,
    on_disable,
    on_enable,
    on_load,
    on_reload,
    on_unload,
    plugin_hook,
    plugin_info,
)

__all__ = [
    # Core Unified API (Primary Interface)
    "AetheriusCoreAPI",
    "ServerAPI",
    "PluginAPI",
    "ComponentAPI",
    "PlayerAPI",
    "MonitoringAPI",
    "EventAPI",
    "create_core_api",
    "get_core_api",
    "set_global_api",
    # Plugin Development API
    "Plugin",
    "SimplePlugin",
    "PluginInfo",
    "PluginContext",
    "plugin_info",
    "plugin_hook",
    "on_load",
    "on_enable",
    "on_disable",
    "on_unload",
    "on_reload",
    # Component Development API
    "Component",
    "SimpleComponent",
    "ComponentInfo",
    "ComponentContext",
    "component_info",
    "component_hook",
    # Enhanced/Legacy APIs
    # "EnhancedAetheriusAPI",
    # "EnhancedComponent",
    "AetheriusManagementAPI",
    "ControlLevel",
    "InfoStreamType",
]

# Convenience imports for common use cases
from .core import AetheriusCoreAPI as CoreAPI
from .core import create_core_api as create_api

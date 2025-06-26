"""Core modules for Aetherius engine."""

from .config import Config
from .server import ServerProcessWrapper
from .events import *
from .event_manager import EventManager, get_event_manager, on_event, fire_event
from .log_parser import LogParser

# Enhanced core modules for Web component support
from .component import Component, ComponentInfo, WebComponent
from .component_manager import ComponentManager
from .file_manager import FileManager
from .server_manager_extensions import ServerManagerExtensions, ServerPerformanceMetrics, ServerStatus
from .player_manager_extensions import PlayerManagerExtensions, ExtendedPlayerInfo
from .config_manager_extensions import ConfigManagerExtensions, ConfigSection

# Plugin system
from ..api.plugin_manager import PluginManager, get_plugin_manager as _get_plugin_manager

# Global instances for plugins and components
_global_server_wrapper = None
_global_plugin_manager = None
_global_component_manager = None
_global_file_manager = None
_global_config_manager_extensions = None

def get_server_wrapper():
    """Get the server wrapper instance for plugins and components."""
    return _global_server_wrapper

def set_server_wrapper(wrapper):
    """Set the server wrapper instance."""
    global _global_server_wrapper
    _global_server_wrapper = wrapper

def get_plugin_manager():
    """Get the plugin manager instance."""
    global _global_plugin_manager
    if _global_plugin_manager is None:
        _global_plugin_manager = _get_plugin_manager()
    return _global_plugin_manager

def set_plugin_manager(manager):
    """Set the plugin manager instance."""
    global _global_plugin_manager
    _global_plugin_manager = manager

def get_component_manager():
    """Get the component manager instance."""
    return _global_component_manager

def set_component_manager(manager):
    """Set the component manager instance."""
    global _global_component_manager
    _global_component_manager = manager

def get_file_manager():
    """Get the file manager instance."""
    return _global_file_manager

def set_file_manager(manager):
    """Set the file manager instance."""
    global _global_file_manager
    _global_file_manager = manager

def get_config_manager_extensions():
    """Get the config manager extensions instance."""
    return _global_config_manager_extensions

def set_config_manager_extensions(manager):
    """Set the config manager extensions instance."""
    global _global_config_manager_extensions
    _global_config_manager_extensions = manager

__all__ = [
    # Core modules
    "Config", 
    "ServerProcessWrapper", 
    "EventManager", 
    "get_event_manager", 
    "on_event", 
    "fire_event",
    "LogParser",
    
    # Enhanced core modules
    "Component",
    "ComponentInfo", 
    "WebComponent",
    "ComponentManager",
    "FileManager",
    "ServerManagerExtensions",
    "ServerPerformanceMetrics",
    "ServerStatus",
    "PlayerManagerExtensions",
    "ExtendedPlayerInfo",
    "ConfigManagerExtensions",
    "ConfigSection",
    
    # Plugin system
    "PluginManager",
    
    # Global accessors
    "get_server_wrapper",
    "set_server_wrapper",
    "get_plugin_manager",
    "set_plugin_manager",
    "get_component_manager",
    "set_component_manager",
    "get_file_manager",
    "set_file_manager",
    "get_config_manager_extensions",
    "set_config_manager_extensions"
]
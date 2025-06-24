"""Core modules for Aetherius engine."""

from .config import Config
from .server import ServerProcessWrapper
from .events import *
from .event_manager import EventManager, get_event_manager, on_event, fire_event
from .log_parser import LogParser

# Global instances for plugins and components
_global_server_wrapper = None
_global_plugin_manager = None
_global_component_manager = None

def get_server_wrapper():
    """Get the server wrapper instance for plugins and components."""
    return _global_server_wrapper

def set_server_wrapper(wrapper):
    """Set the server wrapper instance."""
    global _global_server_wrapper
    _global_server_wrapper = wrapper

def get_plugin_manager():
    """Get the plugin manager instance."""
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

__all__ = [
    "Config", 
    "ServerProcessWrapper", 
    "EventManager", 
    "get_event_manager", 
    "on_event", 
    "fire_event",
    "LogParser",
    "get_server_wrapper",
    "set_server_wrapper",
    "get_plugin_manager",
    "set_plugin_manager",
    "get_component_manager",
    "set_component_manager"
]
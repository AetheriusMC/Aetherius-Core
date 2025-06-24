"""Plugin loading system for Aetherius."""

import asyncio
import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import yaml

from ..api.plugin import Plugin, SimplePlugin, PluginInfo, PluginContext
from ..core.event_manager import get_event_manager
from ..core.config import Config
from .state import PluginState

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manages loading, enabling, disabling, and unloading of plugins.
    
    Supports both class-based plugins (inheriting from Plugin) and
    simple function-based plugins with decorators.
    """
    
    def __init__(self, config: Config, plugins_dir: Path = None):
        self.config = config
        self.plugins_dir = plugins_dir or Path("plugins")
        self.plugins: Dict[str, Union[Plugin, SimplePlugin]] = {}
        self.plugin_info: Dict[str, PluginInfo] = {}
        self.load_order: List[str] = []
        self.enabled_plugins: Set[str] = set()
        self.event_manager = get_event_manager()
        self.state = PluginState()
        
        # Ensure plugins directory exists
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        
        # Auto-load plugins if they were previously loaded
        # Note: This will be done lazily when needed since we can't run async in __init__
    
    async def discover_plugins(self) -> List[Path]:
        """Discover all plugin files in the plugins directory."""
        plugin_files = []
        
        # Look for .py files
        for py_file in self.plugins_dir.glob("*.py"):
            if not py_file.name.startswith("_"):
                plugin_files.append(py_file)
        
        # Look for plugin directories with __init__.py
        for plugin_dir in self.plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                init_file = plugin_dir / "__init__.py"
                if init_file.exists():
                    plugin_files.append(init_file)
        
        logger.info(f"Discovered {len(plugin_files)} potential plugins")
        return plugin_files
    
    async def _auto_restore_plugins(self) -> None:
        """Auto-restore previously loaded plugins."""
        try:
            loaded_plugins = self.state.get_loaded_plugins()
            if not loaded_plugins:
                return
            
            logger.info(f"Auto-restoring {len(loaded_plugins)} plugins")
            await self.load_all_plugins()
            
            # Enable previously enabled plugins
            for plugin_name in self.state.get_enabled_plugins():
                if plugin_name in self.plugins:
                    await self.enable_plugin(plugin_name)
                    
        except Exception as e:
            logger.error(f"Error auto-restoring plugins: {e}")
    
    async def load_plugin_from_file(self, plugin_file: Path) -> Optional[str]:
        """Load a single plugin from a file."""
        try:
            plugin_name = plugin_file.stem
            if plugin_file.name == "__init__.py":
                plugin_name = plugin_file.parent.name
            
            # Check if already loaded
            if plugin_name in self.plugins:
                logger.warning(f"Plugin {plugin_name} is already loaded")
                return None
            
            # Import the plugin module
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
            if not spec or not spec.loader:
                logger.error(f"Failed to create spec for plugin {plugin_name}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"aetherius.plugins.{plugin_name}"] = module
            
            spec.loader.exec_module(module)
            
            # Try to find plugin info and main class/function
            plugin_info = self._extract_plugin_info(module, plugin_name)
            plugin_instance = await self._create_plugin_instance(module, plugin_info)
            
            if not plugin_instance:
                logger.error(f"Failed to create plugin instance for {plugin_name}")
                return None
            
            # Set up plugin context
            data_folder = Path("plugins") / plugin_name
            plugin_logger = logging.getLogger(f"aetherius.plugin.{plugin_name}")
            
            context = PluginContext(
                config=self.config,
                event_manager=self.event_manager,
                plugin_manager=self,
                data_folder=data_folder,
                logger=plugin_logger
            )
            
            plugin_instance.context = context
            plugin_instance.info = plugin_info
            
            # Store the plugin
            self.plugins[plugin_name] = plugin_instance
            self.plugin_info[plugin_name] = plugin_info
            
            # Call on_load
            await plugin_instance.on_load()
            plugin_instance.loaded = True
            
            # Update state
            self.state.add_loaded_plugin(plugin_name)
            
            logger.info(f"Loaded plugin: {plugin_name} v{plugin_info.version}")
            return plugin_name
            
        except Exception as e:
            logger.error(f"Error loading plugin from {plugin_file}: {e}", exc_info=True)
            return None
    
    def _extract_plugin_info(self, module: Any, default_name: str) -> PluginInfo:
        """Extract plugin information from module."""
        # Look for PLUGIN_INFO variable
        if hasattr(module, 'PLUGIN_INFO'):
            info_data = module.PLUGIN_INFO
            if isinstance(info_data, dict):
                return PluginInfo(**info_data)
            elif isinstance(info_data, PluginInfo):
                return info_data
        
        # Look for plugin.yaml file
        plugin_yaml = Path(module.__file__).parent / "plugin.yaml"
        if plugin_yaml.exists():
            try:
                with open(plugin_yaml, 'r', encoding='utf-8') as f:
                    yaml_data = yaml.safe_load(f)
                    return PluginInfo(**yaml_data)
            except Exception as e:
                logger.warning(f"Error reading plugin.yaml: {e}")
        
        # Create default info
        return PluginInfo(
            name=default_name,
            version="1.0.0",
            description=f"Plugin {default_name}",
            author="Unknown"
        )
    
    async def _create_plugin_instance(self, module: Any, info: PluginInfo) -> Optional[Union[Plugin, SimplePlugin]]:
        """Create plugin instance from module."""
        # Look for main class
        if info.main_class:
            if hasattr(module, info.main_class):
                plugin_class = getattr(module, info.main_class)
                if inspect.isclass(plugin_class) and issubclass(plugin_class, Plugin):
                    return plugin_class()
        
        # Look for any Plugin subclass
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Plugin) and obj is not Plugin:
                return obj()
        
        # Look for entry point function
        if info.entry_point and hasattr(module, info.entry_point):
            entry_func = getattr(module, info.entry_point)
            if callable(entry_func):
                simple_plugin = SimplePlugin(info)
                simple_plugin.set_lifecycle_hooks(on_enable=entry_func)
                return simple_plugin
        
        # Look for lifecycle functions with decorators
        lifecycle_hooks = {}
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if hasattr(obj, '_plugin_hook'):
                hook_name = obj._plugin_hook
                lifecycle_hooks[hook_name] = obj
        
        if lifecycle_hooks:
            simple_plugin = SimplePlugin(info)
            simple_plugin.set_lifecycle_hooks(**lifecycle_hooks)
            return simple_plugin
        
        # Look for common function names
        common_functions = ['main', 'init', 'setup', 'start']
        for func_name in common_functions:
            if hasattr(module, func_name):
                func = getattr(module, func_name)
                if callable(func):
                    simple_plugin = SimplePlugin(info)
                    simple_plugin.set_lifecycle_hooks(on_enable=func)
                    return simple_plugin
        
        return None
    
    async def enable_plugin(self, name: str) -> bool:
        """Enable a loaded plugin."""
        if name not in self.plugins:
            logger.error(f"Plugin {name} is not loaded")
            return False
        
        if name in self.enabled_plugins:
            logger.warning(f"Plugin {name} is already enabled")
            return True
        
        plugin = self.plugins[name]
        
        try:
            await plugin.on_enable()
            plugin.enabled = True
            self.enabled_plugins.add(name)
            
            # Update state
            self.state.add_enabled_plugin(name)
            
            logger.info(f"Enabled plugin: {name}")
            return True
        except Exception as e:
            logger.error(f"Error enabling plugin {name}: {e}", exc_info=True)
            return False
    
    async def disable_plugin(self, name: str) -> bool:
        """Disable an enabled plugin."""
        if name not in self.plugins:
            logger.error(f"Plugin {name} is not loaded")
            return False
        
        if name not in self.enabled_plugins:
            logger.warning(f"Plugin {name} is not enabled")
            return True
        
        plugin = self.plugins[name]
        
        try:
            await plugin.on_disable()
            plugin.enabled = False
            self.enabled_plugins.discard(name)
            
            # Update state
            self.state.remove_enabled_plugin(name)
            
            logger.info(f"Disabled plugin: {name}")
            return True
        except Exception as e:
            logger.error(f"Error disabling plugin {name}: {e}", exc_info=True)
            return False
    
    async def unload_plugin(self, name: str) -> bool:
        """Unload a plugin."""
        if name not in self.plugins:
            logger.error(f"Plugin {name} is not loaded")
            return False
        
        # Disable first if enabled
        if name in self.enabled_plugins:
            await self.disable_plugin(name)
        
        plugin = self.plugins[name]
        
        try:
            await plugin.on_unload()
            plugin.loaded = False
            
            # Remove from our tracking
            del self.plugins[name]
            del self.plugin_info[name]
            
            # Remove from load order if present
            if name in self.load_order:
                self.load_order.remove(name)
            
            # Update state
            self.state.remove_loaded_plugin(name)
            
            # Remove from sys.modules
            module_name = f"aetherius.plugins.{name}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            logger.info(f"Unloaded plugin: {name}")
            return True
        except Exception as e:
            logger.error(f"Error unloading plugin {name}: {e}", exc_info=True)
            return False
    
    async def reload_plugin(self, name: str) -> bool:
        """Reload a plugin."""
        if name not in self.plugins:
            logger.error(f"Plugin {name} is not loaded")
            return False
        
        plugin = self.plugins[name]
        
        try:
            await plugin.on_reload()
            logger.info(f"Reloaded plugin: {name}")
            return True
        except Exception as e:
            logger.error(f"Error reloading plugin {name}: {e}", exc_info=True)
            return False
    
    async def load_all_plugins(self) -> int:
        """Discover and load all plugins."""
        plugin_files = await self.discover_plugins()
        loaded_count = 0
        
        for plugin_file in plugin_files:
            plugin_name = await self.load_plugin_from_file(plugin_file)
            if plugin_name:
                self.load_order.append(plugin_name)
                loaded_count += 1
        
        logger.info(f"Loaded {loaded_count} plugins")
        return loaded_count
    
    async def enable_all_plugins(self) -> int:
        """Enable all loaded plugins."""
        enabled_count = 0
        
        for plugin_name in self.load_order:
            if await self.enable_plugin(plugin_name):
                enabled_count += 1
        
        logger.info(f"Enabled {enabled_count} plugins")
        return enabled_count
    
    async def disable_all_plugins(self) -> None:
        """Disable all enabled plugins."""
        # Disable in reverse order
        for plugin_name in reversed(self.load_order):
            if plugin_name in self.enabled_plugins:
                await self.disable_plugin(plugin_name)
    
    async def unload_all_plugins(self) -> None:
        """Unload all plugins."""
        # Unload in reverse order
        for plugin_name in reversed(self.load_order):
            await self.unload_plugin(plugin_name)
    
    def get_plugin(self, name: str) -> Optional[Union[Plugin, SimplePlugin]]:
        """Get a plugin by name."""
        return self.plugins.get(name)
    
    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        """Get plugin info by name."""
        return self.plugin_info.get(name)
    
    def is_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded."""
        return name in self.plugins
    
    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        return name in self.enabled_plugins
    
    def list_plugins(self) -> List[str]:
        """Get list of all loaded plugins."""
        # Lazy restore on first access
        if not self.plugins and self.state.get_loaded_plugins():
            # We can't await here, so just return empty for now
            # The CLI will handle auto-loading
            pass
        return list(self.plugins.keys())
    
    def list_enabled_plugins(self) -> List[str]:
        """Get list of enabled plugins."""
        return list(self.enabled_plugins)
    
    def get_plugin_stats(self) -> Dict[str, int]:
        """Get plugin statistics."""
        return {
            "total": len(self.plugins),
            "enabled": len(self.enabled_plugins),
            "disabled": len(self.plugins) - len(self.enabled_plugins)
        }
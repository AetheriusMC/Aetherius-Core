"""Plugin Manager for Aetherius - Manages plugin loading, enabling, and lifecycle."""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from ..core.config import get_config_manager
from ..core.event_manager import get_event_manager
from .plugin import Plugin, PluginContext, PluginInfo, SimplePlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages plugin loading, enabling, disabling and lifecycle."""

    def __init__(self, plugins_directory: str = "plugins"):
        """Initialize plugin manager.

        Args:
            plugins_directory: Directory containing plugins
        """
        self.plugins_dir = Path(plugins_directory)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        self.config_manager = get_config_manager()
        self.event_manager = get_event_manager()

        # Plugin storage
        self._plugins: dict[str, Plugin] = {}
        self._plugin_info: dict[str, PluginInfo] = {}
        self._enabled_plugins: set[str] = set()
        self._loaded_plugins: set[str] = set()

        # Plugin data directories
        self.data_dir = Path("data/plugins")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Plugin manager initialized with directory: {self.plugins_dir}")

    def discover_plugins(self) -> list[str]:
        """Discover available plugins in the plugins directory.

        Returns:
            List of discovered plugin names
        """
        discovered = set()  # Use set to avoid duplicates

        # Look for Python files
        for plugin_file in self.plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            plugin_name = plugin_file.stem
            discovered.add(plugin_name)
            logger.debug(f"Discovered Python plugin: {plugin_name}")

        # Look for plugin directories with __init__.py
        for plugin_dir in self.plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                init_file = plugin_dir / "__init__.py"
                plugin_yaml = plugin_dir / "plugin.yaml"
                if init_file.exists() or plugin_yaml.exists():
                    discovered.add(plugin_dir.name)
                    logger.debug(f"Discovered directory plugin: {plugin_dir.name}")

        return list(discovered)

    def _load_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Load plugin information from plugin.yaml or metadata.

        Args:
            plugin_name: Name of the plugin

        Returns:
            PluginInfo object or None if not found
        """
        # Try plugin directory first
        plugin_dir = self.plugins_dir / plugin_name
        if plugin_dir.is_dir():
            plugin_yaml = plugin_dir / "plugin.yaml"
            if plugin_yaml.exists():
                try:
                    with open(plugin_yaml, encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    return PluginInfo(**data)
                except Exception as e:
                    logger.error(f"Error loading plugin info for {plugin_name}: {e}")

        # Fallback to minimal info
        return PluginInfo(
            name=plugin_name,
            version="1.0.0",
            description=f"Plugin {plugin_name}",
            author="Unknown",
        )

    async def load_plugin(self, plugin_name: str) -> bool:
        """Load a plugin.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            True if loaded successfully
        """
        if plugin_name in self._loaded_plugins:
            logger.warning(f"Plugin {plugin_name} is already loaded")
            return True

        try:
            # Load plugin info
            plugin_info = self._load_plugin_info(plugin_name)
            if not plugin_info:
                logger.error(f"Could not load plugin info for {plugin_name}")
                return False

            # Try to load the plugin module
            plugin_instance = await self._load_plugin_module(plugin_name, plugin_info)
            if not plugin_instance:
                return False

            # Store plugin
            self._plugins[plugin_name] = plugin_instance
            self._plugin_info[plugin_name] = plugin_info
            self._loaded_plugins.add(plugin_name)

            # Set up plugin context
            plugin_data_dir = self.data_dir / plugin_name
            plugin_logger = logging.getLogger(f"plugin.{plugin_name}")

            context = PluginContext(
                config=self.config_manager,
                event_manager=self.event_manager,
                plugin_manager=self,
                data_folder=plugin_data_dir,
                logger=plugin_logger,
            )

            plugin_instance.context = context
            plugin_instance.info = plugin_info

            # Call on_load
            await plugin_instance.on_load()
            plugin_instance.loaded = True

            logger.info(f"Loaded plugin: {plugin_name} v{plugin_info.version}")
            return True

        except Exception as e:
            logger.error(f"Error loading plugin {plugin_name}: {e}")
            return False

    async def _load_plugin_module(
        self, plugin_name: str, plugin_info: PluginInfo
    ) -> Optional[Plugin]:
        """Load the actual plugin module and create instance.

        Args:
            plugin_name: Name of the plugin
            plugin_info: Plugin information

        Returns:
            Plugin instance or None
        """
        try:
            # Try loading from directory first
            plugin_dir = self.plugins_dir / plugin_name
            if plugin_dir.is_dir():
                init_file = plugin_dir / "__init__.py"
                if init_file.exists():
                    spec = importlib.util.spec_from_file_location(
                        f"plugins.{plugin_name}", init_file
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[f"plugins.{plugin_name}"] = module
                        spec.loader.exec_module(module)

                        # Look for plugin class or create simple plugin
                        return self._create_plugin_instance(module, plugin_info)

            # Try loading from single file
            plugin_file = self.plugins_dir / f"{plugin_name}.py"
            if plugin_file.exists():
                spec = importlib.util.spec_from_file_location(
                    f"plugins.{plugin_name}", plugin_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"plugins.{plugin_name}"] = module
                    spec.loader.exec_module(module)

                    return self._create_plugin_instance(module, plugin_info)

            logger.error(f"Could not find plugin module for {plugin_name}")
            return None

        except Exception as e:
            logger.error(f"Error loading plugin module {plugin_name}: {e}")
            return None

    def _create_plugin_instance(
        self, module: Any, plugin_info: PluginInfo
    ) -> Optional[Plugin]:
        """Create plugin instance from module.

        Args:
            module: Loaded plugin module
            plugin_info: Plugin information

        Returns:
            Plugin instance or None
        """
        # Look for main class
        if plugin_info.main_class:
            plugin_class = getattr(module, plugin_info.main_class, None)
            if plugin_class and issubclass(plugin_class, Plugin):
                return plugin_class()

        # Look for any Plugin subclass
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                return attr()

        # Create simple plugin from lifecycle functions
        simple_plugin = SimplePlugin(plugin_info)
        hooks = {}

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and hasattr(attr, "_plugin_hook"):
                hook_name = attr._plugin_hook
                hooks[hook_name] = attr

        if hooks:
            simple_plugin.set_lifecycle_hooks(**hooks)
            return simple_plugin

        logger.warning("No plugin class or hooks found in module")
        return simple_plugin

    async def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin.

        Args:
            plugin_name: Name of the plugin to enable

        Returns:
            True if enabled successfully
        """
        if plugin_name in self._enabled_plugins:
            logger.warning(f"Plugin {plugin_name} is already enabled")
            return True

        if plugin_name not in self._loaded_plugins:
            success = await self.load_plugin(plugin_name)
            if not success:
                return False

        try:
            plugin = self._plugins[plugin_name]
            await plugin.on_enable()
            plugin.enabled = True
            self._enabled_plugins.add(plugin_name)

            logger.info(f"Enabled plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Error enabling plugin {plugin_name}: {e}")
            return False

    async def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin.

        Args:
            plugin_name: Name of the plugin to disable

        Returns:
            True if disabled successfully
        """
        if plugin_name not in self._enabled_plugins:
            logger.warning(f"Plugin {plugin_name} is not enabled")
            return True

        try:
            plugin = self._plugins[plugin_name]
            await plugin.on_disable()
            plugin.enabled = False
            self._enabled_plugins.remove(plugin_name)

            logger.info(f"Disabled plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Error disabling plugin {plugin_name}: {e}")
            return False

    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin.

        Args:
            plugin_name: Name of the plugin to reload

        Returns:
            True if reloaded successfully
        """
        try:
            if plugin_name in self._enabled_plugins:
                await self.disable_plugin(plugin_name)

            if plugin_name in self._loaded_plugins:
                await self.unload_plugin(plugin_name)

            return await self.enable_plugin(plugin_name)

        except Exception as e:
            logger.error(f"Error reloading plugin {plugin_name}: {e}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            True if unloaded successfully
        """
        if plugin_name not in self._loaded_plugins:
            return True

        try:
            if plugin_name in self._enabled_plugins:
                await self.disable_plugin(plugin_name)

            plugin = self._plugins[plugin_name]
            await plugin.on_unload()
            plugin.loaded = False

            # Clean up
            del self._plugins[plugin_name]
            del self._plugin_info[plugin_name]
            self._loaded_plugins.remove(plugin_name)

            # Remove from sys.modules
            module_name = f"plugins.{plugin_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]

            logger.info(f"Unloaded plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}")
            return False

    def list_plugins(self) -> list[str]:
        """List all discovered plugins.

        Returns:
            List of plugin names
        """
        return self.discover_plugins()

    def list_loaded_plugins(self) -> list[str]:
        """List loaded plugins.

        Returns:
            List of loaded plugin names
        """
        return list(self._loaded_plugins)

    def list_enabled_plugins(self) -> list[str]:
        """List enabled plugins.

        Returns:
            List of enabled plugin names
        """
        return list(self._enabled_plugins)

    def is_loaded(self, plugin_name: str) -> bool:
        """Check if a plugin is loaded.

        Args:
            plugin_name: Plugin name

        Returns:
            True if loaded
        """
        return plugin_name in self._loaded_plugins

    def is_enabled(self, plugin_name: str) -> bool:
        """Check if a plugin is enabled.

        Args:
            plugin_name: Plugin name

        Returns:
            True if enabled
        """
        return plugin_name in self._enabled_plugins

    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """Get a plugin instance.

        Args:
            plugin_name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self._plugins.get(plugin_name)

    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get plugin information.

        Args:
            plugin_name: Plugin name

        Returns:
            PluginInfo or None
        """
        return self._plugin_info.get(plugin_name)

    async def enable_all_plugins(self) -> dict[str, bool]:
        """Enable all discovered plugins.

        Returns:
            Dictionary mapping plugin names to success status
        """
        results = {}
        plugins = self.discover_plugins()

        for plugin_name in plugins:
            try:
                results[plugin_name] = await self.enable_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Error enabling plugin {plugin_name}: {e}")
                results[plugin_name] = False

        return results

    async def disable_all_plugins(self) -> dict[str, bool]:
        """Disable all enabled plugins.

        Returns:
            Dictionary mapping plugin names to success status
        """
        results = {}
        enabled_plugins = list(self._enabled_plugins)

        for plugin_name in enabled_plugins:
            try:
                results[plugin_name] = await self.disable_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Error disabling plugin {plugin_name}: {e}")
                results[plugin_name] = False

        return results


# Global plugin manager instance
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance.

    Returns:
        Global PluginManager instance
    """
    global _plugin_manager

    if _plugin_manager is None:
        _plugin_manager = PluginManager()

    return _plugin_manager


def set_plugin_manager(manager: PluginManager) -> None:
    """Set the global plugin manager instance.

    Args:
        manager: PluginManager instance to set
    """
    global _plugin_manager
    _plugin_manager = manager

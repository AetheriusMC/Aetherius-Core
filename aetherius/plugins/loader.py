"""Plugin loading system for Aetherius."""

import inspect
import logging
from pathlib import Path
from typing import Any, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..api.core import AetheriusCoreAPI

import yaml

# Delayed import to avoid circular dependency
# from ..api.core import AetheriusCoreAPI
from ..api.plugin import Plugin, PluginContext, PluginInfo, SimplePlugin
from ..core.asset_manager import AssetManager
from .state import PluginState

logger = logging.getLogger(__name__)


class PluginManager(AssetManager):
    """
    Manages loading, enabling, disabling, and unloading of plugins.

    Supports both class-based plugins (inheriting from Plugin) and
    simple function-based plugins with decorators.
    """

    def __init__(self, core_api: 'AetheriusCoreAPI'):
        super().__init__(core_api, "plugin", "plugins")
        self._state_manager = PluginState()

    def _get_asset_base_class(self) -> type:
        return Plugin

    def _get_asset_info_class(self) -> type:
        return PluginInfo

    def _get_asset_context_class(self) -> type:
        return PluginContext

    def _get_state_manager(self) -> PluginState:
        return self._state_manager

    def _extract_asset_info(
        self, module: Any, default_name: str
    ) -> Optional[PluginInfo]:
        """Extract plugin information from module."""
        # Look for PLUGIN_INFO variable
        if hasattr(module, "PLUGIN_INFO"):
            info_data = module.PLUGIN_INFO
            if isinstance(info_data, dict):
                return PluginInfo(**info_data)
            elif isinstance(info_data, PluginInfo):
                return info_data

        # Look for plugin.yaml file
        plugin_yaml = Path(module.__file__).parent / "plugin.yaml"
        if plugin_yaml.exists():
            try:
                with open(plugin_yaml, encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f)
                    return PluginInfo(**yaml_data)
            except Exception as e:
                self.logger.warning(f"Error reading plugin.yaml: {e}")

        # Create default info
        return PluginInfo(
            name=default_name,
            version="1.0.0",
            description=f"Plugin {default_name}",
            author="Unknown",
        )

    async def _create_asset_instance(
        self, module: Any, info: PluginInfo
    ) -> Optional[Union[Plugin, SimplePlugin]]:
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
            if hasattr(obj, "_plugin_hook"):
                hook_name = obj._plugin_hook
                lifecycle_hooks[hook_name] = obj

        if lifecycle_hooks:
            simple_plugin = SimplePlugin(info)
            simple_plugin.set_lifecycle_hooks(**lifecycle_hooks)
            return simple_plugin

        # Look for common function names
        common_functions = ["main", "init", "setup", "start"]
        for func_name in common_functions:
            if hasattr(module, func_name):
                func = getattr(module, func_name)
                if callable(func):
                    simple_plugin = SimplePlugin(info)
                    simple_plugin.set_lifecycle_hooks(on_enable=func)
                    return simple_plugin

        return None

    async def auto_restore_plugins(self) -> None:
        """Auto-restore previously loaded plugins."""
        try:
            loaded_plugins = self._state_manager.get_loaded_plugins()
            if not loaded_plugins:
                return

            self.logger.info(f"Auto-restoring {len(loaded_plugins)} plugins")
            await self.load_all_assets()  # Use the generic load_all_assets

            # Enable previously enabled plugins
            for plugin_name in self._state_manager.get_enabled_plugins():
                if plugin_name in self._assets:
                    await self.enable_asset(plugin_name)  # Use the generic enable_asset

        except Exception as e:
            self.logger.error(f"Error auto-restoring plugins: {e}")

    # Public methods, now mostly wrappers around AssetManager methods
    async def load_plugin(self, name: str) -> bool:
        """Load a specific plugin."""
        # Need to find the path for the specific plugin
        plugin_path = self.base_dir / name / "__init__.py"  # Default assumption
        if not plugin_path.exists():  # Try direct .py file
            plugin_path = self.base_dir / f"{name}.py"
        if not plugin_path.exists():  # Try .yaml file in folder
            plugin_path = self.base_dir / name / "plugin.yaml"

        if not plugin_path.exists():
            self.logger.error(f"Could not find plugin file for {name}")
            return False

        return await self._load_asset(plugin_path)

    async def enable_plugin(self, name: str) -> bool:
        return await self.enable_asset(name)

    async def disable_plugin(self, name: str) -> bool:
        return await self.disable_asset(name)

    async def unload_plugin(self, name: str) -> bool:
        return await self.unload_asset(name)

    async def reload_plugin(self, name: str) -> bool:
        return await self.reload_asset(name)

    async def load_all_plugins(self) -> int:
        return await self.load_all_assets()

    async def enable_all_plugins(self) -> int:
        return await self.enable_all_assets()

    async def disable_all_plugins(self) -> None:
        return await self.disable_all_assets()

    async def unload_all_plugins(self) -> None:
        return await self.unload_all_assets()

    def get_plugin(self, name: str) -> Optional[Union[Plugin, SimplePlugin]]:
        return self.get_asset(name)

    def get_plugin_info(self, name: str) -> PluginInfo | None:
        return self.get_asset_info(name)

    def is_loaded(self, name: str) -> bool:
        return super().is_loaded(name)

    def is_enabled(self, name: str) -> bool:
        return super().is_enabled(name)

    def list_plugins(self) -> list[str]:
        return self.list_assets()

    def list_enabled_plugins(self) -> list[str]:
        return self.list_enabled_assets()

    def get_plugin_stats(self) -> dict[str, int]:
        return self.get_asset_stats()

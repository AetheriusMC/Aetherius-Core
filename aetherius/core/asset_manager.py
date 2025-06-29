"""
Abstract base class for managing loadable assets (plugins, components, etc.).
"""

import asyncio
import importlib
import importlib.util
import inspect
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..api.core import AetheriusCoreAPI


class AssetManager(ABC):
    """
    Abstract base class for managing loadable assets like plugins or components.
    Provides common functionality for discovery, loading, enabling, disabling,
    and managing the lifecycle of assets.
    """

    def __init__(self, core_api: 'AetheriusCoreAPI', asset_type_name: str, base_dir_name: str):
        """
        Initialize the asset manager.

        Args:
            core_api: The main AetheriusCoreAPI instance.
            asset_type_name: The singular name of the asset type (e.g., "plugin", "component").
            base_dir_name: The name of the directory where assets are located (e.g., "plugins", "components").
        """
        self.core_api = core_api
        self.asset_type_name = asset_type_name
        self.logger = logging.getLogger(f"aetherius.{base_dir_name}")
        self.base_dir = Path(base_dir_name)
        self._assets: Dict[str, Any] = {}
        self._asset_info: Dict[str, Any] = {}
        self._load_order: List[str] = []
        self._enabled_assets: Dict[str, Any] = {}

        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def _get_asset_base_class(self) -> Type:
        """Returns the base class that assets of this type must inherit from."""
        pass

    @abstractmethod
    def _get_asset_info_class(self) -> Type:
        """Returns the Pydantic model for asset information."""
        pass

    @abstractmethod
    def _get_asset_context_class(self) -> Type:
        """Returns the dataclass for asset context."""
        pass

    @abstractmethod
    def _extract_asset_info(self, module: Any, default_name: str) -> Any:
        """Extracts asset information from a loaded module."""
        pass

    @abstractmethod
    async def _create_asset_instance(self, module: Any, info: Any) -> Optional[Any]:
        """Creates an asset instance from a loaded module and its info."""
        pass

    @abstractmethod
    def _get_state_manager(self) -> Any:
        """Returns the state manager for this asset type (e.g., PluginState, ComponentState)."""
        pass

    async def discover_assets(self) -> List[Path]:
        """Discover all asset files/directories in the base directory."""
        asset_paths = []
        # Look for .py files directly in the base directory
        for py_file in self.base_dir.glob("*.py"):
            if not py_file.name.startswith("_"):
                asset_paths.append(py_file)
        
        # Look for asset directories with __init__.py or info file
        for asset_dir in self.base_dir.iterdir():
            if asset_dir.is_dir() and not asset_dir.name.startswith("_"):
                # Check for __init__.py (Python package)
                init_file = asset_dir / "__init__.py"
                if init_file.exists():
                    asset_paths.append(init_file)
                # Or check for a specific info file (e.g., plugin.yaml, component.yaml)
                elif (asset_dir / f"{self.asset_type_name}.yaml").exists():
                    asset_paths.append(asset_dir / f"{self.asset_type_name}.yaml")
        
        self.logger.info(f"Discovered {len(asset_paths)} potential {self.asset_type_name}s")
        return asset_paths

    async def load_all_assets(self) -> int:
        """Load all assets from the base directory."""
        if not self.base_dir.exists():
            self.logger.info(f"{self.asset_type_name.capitalize()} directory not found, creating it")
            self.base_dir.mkdir(parents=True, exist_ok=True)
            return 0

        loaded_count = 0
        asset_paths = await self.discover_assets()

        # Sort assets by dependency order (placeholder for now)
        sorted_assets = self._sort_by_dependencies(asset_paths)

        for asset_path in sorted_assets:
            try:
                if await self._load_asset(asset_path):
                    loaded_count += 1
            except Exception as e:
                self.logger.error(f"Failed to load {self.asset_type_name} from {asset_path}: {e}")

        self._get_state_manager().save()
        return loaded_count

    async def _load_asset(self, asset_path: Path) -> bool:
        """Load a single asset from a file or directory."""
        asset_name = asset_path.stem
        if asset_path.name == "__init__.py":
            asset_name = asset_path.parent.name
        elif asset_path.suffix == ".yaml":
            asset_name = asset_path.parent.name # For component.yaml/plugin.yaml in a folder

        if asset_name in self._assets:
            self.logger.warning(f"{self.asset_type_name.capitalize()} {asset_name} is already loaded")
            return False

        try:
            # Load the asset module
            spec = importlib.util.spec_from_file_location(
                f"{self.asset_type_name}_{asset_name}", asset_path
            )
            if spec is None or spec.loader is None:
                self.logger.error(f"Failed to create spec for {self.asset_type_name} {asset_name}")
                return False

            module = importlib.util.module_from_spec(spec)
            sys.modules[f"aetherius.{self.asset_type_name}s.{asset_name}"] = module
            spec.loader.exec_module(module)

            # Get asset info
            asset_info = self._extract_asset_info(module, asset_name)
            if not asset_info:
                self.logger.error(f"{self.asset_type_name.capitalize()} {asset_name} missing info")
                return False

            # Check dependencies
            missing_deps = self._check_dependencies(asset_info)
            if missing_deps:
                self.logger.error(f"{self.asset_type_name.capitalize()} {asset_name} missing dependencies: {missing_deps}")
                return False

            # Create asset instance
            asset_instance = await self._create_asset_instance(module, asset_info)
            if not asset_instance:
                self.logger.error(f"Failed to create {self.asset_type_name} instance for {asset_name}")
                return False

            # Set up asset context
            data_folder = self.base_dir / asset_name / "data"
            data_folder.mkdir(parents=True, exist_ok=True)
            asset_context = self._get_asset_context_class()(
                core_api=self.core_api,
                data_folder=data_folder,
                logger=logging.getLogger(f"aetherius.{self.asset_type_name}s.{asset_name}")
            )
            asset_instance.context = asset_context
            asset_instance.info = asset_info

            # Call on_load
            await asset_instance.on_load()
            asset_instance.loaded = True

            # Store asset
            self._assets[asset_name] = asset_instance
            self._asset_info[asset_name] = asset_info
            self._load_order.append(asset_name)
            self._get_state_manager().add_loaded(asset_name, asset_info)

            self.logger.info(f"Loaded {self.asset_type_name}: {asset_name} v{asset_info.version}")
            return True

        except Exception as e:
            self.logger.error(f"Error loading {self.asset_type_name} {asset_name}: {e}", exc_info=True)
            return False

    def _check_dependencies(self, asset_info: Any) -> List[str]:
        """Check if asset dependencies are satisfied."""
        missing = []
        for dep in getattr(asset_info, 'depends', []):
            if not self.is_loaded(dep):
                missing.append(dep)
        return missing

    def _sort_by_dependencies(self, asset_paths: List[Path]) -> List[Path]:
        """Sort asset paths by dependency order (placeholder for now)."""
        # TODO: Implement proper topological sort based on asset_info.depends
        return sorted(asset_paths, key=lambda p: p.name)

    async def enable_asset(self, name: str) -> bool:
        """Enable a loaded asset."""
        if not self.is_loaded(name):
            self.logger.error(f"{self.asset_type_name.capitalize()} {name} is not loaded")
            return False

        if self.is_enabled(name):
            self.logger.warning(f"{self.asset_type_name.capitalize()} {name} is already enabled")
            return True

        asset = self._assets[name]

        try:
            await asset.on_enable()
            asset.enabled = True
            self._enabled_assets[name] = asset
            self._get_state_manager().add_enabled(name)
            self._get_state_manager().save()
            self.logger.info(f"Enabled {self.asset_type_name}: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Error enabling {self.asset_type_name} {name}: {e}", exc_info=True)
            return False

    async def disable_asset(self, name: str) -> bool:
        """Disable an enabled asset."""
        if not self.is_enabled(name):
            self.logger.warning(f"{self.asset_type_name.capitalize()} {name} is not enabled")
            return True

        asset = self._assets[name]

        try:
            await asset.on_disable()
            asset.enabled = False
            del self._enabled_assets[name]
            self._get_state_manager().remove_enabled(name)
            self._get_state_manager().save()
            self.logger.info(f"Disabled {self.asset_type_name}: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Error disabling {self.asset_type_name} {name}: {e}", exc_info=True)
            return False

    async def unload_asset(self, name: str) -> bool:
        """Unload an asset."""
        if not self.is_loaded(name):
            self.logger.error(f"{self.asset_type_name.capitalize()} {name} is not loaded")
            return False

        # Disable first if enabled
        if self.is_enabled(name):
            await self.disable_asset(name)

        asset = self._assets[name]

        try:
            await asset.on_unload()
            asset.loaded = False

            # Remove from our tracking
            del self._assets[name]
            del self._asset_info[name]
            if name in self._load_order:
                self._load_order.remove(name)

            self._get_state_manager().remove_loaded(name)

            # Remove from sys.modules
            module_name = f"aetherius.{self.asset_type_name}s.{name}"
            if module_name in sys.modules:
                del sys.modules[module_name]

            self.logger.info(f"Unloaded {self.asset_type_name}: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Error unloading {self.asset_type_name} {name}: {e}", exc_info=True)
            return False

    async def reload_asset(self, name: str) -> bool:
        """Reload an asset."""
        if not self.is_loaded(name):
            self.logger.error(f"{self.asset_type_name.capitalize()} {name} is not loaded")
            return False

        was_enabled = self.is_enabled(name)

        try:
            # Unload the asset
            await self.unload_asset(name)

            # Reload from its original path (need to store this path)
            # For now, we'll assume it's in the base_dir / name / __init__.py or .py
            asset_path = self.base_dir / name / "__init__.py" # Default assumption
            if not asset_path.exists(): # Try direct .py file
                asset_path = self.base_dir / f"{name}.py"
            if not asset_path.exists(): # Try .yaml file in folder
                asset_path = self.base_dir / name / f"{self.asset_type_name}.yaml"
            
            if not asset_path.exists():
                self.logger.error(f"Could not find original path for {self.asset_type_name} {name} to reload.")
                return False

            success = await self._load_asset(asset_path)
            if success and was_enabled:
                await self.enable_asset(name)

            self._get_state_manager().save()
            self.logger.info(f"Reloaded {self.asset_type_name}: {name}")
            return success

        except Exception as e:
            self.logger.error(f"Failed to reload {self.asset_type_name} {name}: {e}", exc_info=True)
            return False

    async def enable_all_assets(self) -> int:
        """Enable all loaded assets."""
        enabled_count = 0
        for asset_name in self._load_order:
            if await self.enable_asset(asset_name):
                enabled_count += 1
        self.logger.info(f"Enabled {enabled_count} {self.asset_type_name}s")
        return enabled_count

    async def disable_all_assets(self) -> None:
        """Disable all enabled assets."""
        # Disable in reverse order of loading
        for asset_name in reversed(self._load_order):
            if self.is_enabled(asset_name):
                await self.disable_asset(asset_name)

    async def unload_all_assets(self) -> None:
        """Unload all assets."""
        # Unload in reverse order of loading
        for asset_name in reversed(self._load_order):
            await self.unload_asset(asset_name)

    def is_loaded(self, name: str) -> bool:
        """Check if an asset is loaded."""
        return name in self._assets

    def is_enabled(self, name: str) -> bool:
        """Check if an asset is enabled."""
        return name in self._enabled_assets

    def get_asset(self, name: str) -> Optional[Any]:
        """Get an asset instance by name."""
        return self._assets.get(name)

    def get_asset_info(self, name: str) -> Optional[Any]:
        """Get asset information by name."""
        return self._asset_info.get(name)

    def list_assets(self) -> List[str]:
        """Get list of all loaded asset names."""
        return list(self._assets.keys())

    def list_enabled_assets(self) -> List[str]:
        """Get list of all enabled asset names."""
        return list(self._enabled_assets.keys())

    def get_asset_stats(self) -> Dict[str, int]:
        """Get asset system statistics."""
        total = len(self._assets)
        enabled = len(self._enabled_assets)
        disabled = total - enabled

        return {
            "total": total,
            "enabled": enabled,
            "disabled": disabled
        }

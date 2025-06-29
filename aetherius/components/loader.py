"""Component loader and manager for Aetherius components."""

import inspect
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from ..api.component import Component, ComponentContext, ComponentInfo
    from ..api.core import AetheriusCoreAPI
from ..core.asset_manager import AssetManager
from .state import ComponentState


class ComponentManager(AssetManager):
    """Manages loading, enabling, and disabling of components."""

    def __init__(self, core_api: 'AetheriusCoreAPI'):
        super().__init__(core_api, "component", "components")
        self._state_manager = ComponentState()

    def _get_asset_base_class(self) -> type:
        from ..api.component import Component
        return Component

    def _get_asset_info_class(self) -> type:
        from ..api.component import ComponentInfo
        return ComponentInfo

    def _get_asset_context_class(self) -> type:
        from ..api.component import ComponentContext
        return ComponentContext

    def _get_state_manager(self) -> ComponentState:
        return self._state_manager

    def _extract_asset_info(
        self, module: Any, default_name: str
    ) -> Optional['ComponentInfo']:
        """Extract component information from module."""
        from ..api.component import ComponentInfo
        
        if hasattr(module, "COMPONENT_INFO"):
            info_data = module.COMPONENT_INFO
            if isinstance(info_data, dict):
                return ComponentInfo(**info_data)
            elif isinstance(info_data, ComponentInfo):
                return info_data

        # Look for component.yaml file
        component_yaml = Path(module.__file__).parent / "component.yaml"
        if component_yaml.exists():
            try:
                with open(component_yaml, encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f)
                    return ComponentInfo(**yaml_data)
            except Exception as e:
                self.logger.warning(f"Error reading component.yaml: {e}")

        return None  # Components must have explicit info

    async def _create_asset_instance(
        self, module: Any, info: 'ComponentInfo'
    ) -> Optional['Component']:
        """Create component instance from module."""
        from ..api.component import Component
        
        component_class = None
        if info.main_class:
            if hasattr(module, info.main_class):
                component_class = getattr(module, info.main_class)
        else:
            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Component)
                    and obj != Component
                ):
                    component_class = obj
                    break

        if component_class is None:
            return None

        return component_class()

    # Public methods, now mostly wrappers around AssetManager methods
    async def load_component(self, name: str) -> bool:
        """Load a specific component."""
        # Need to find the path for the specific component
        component_path = self.base_dir / name / "__init__.py"  # Default assumption
        if not component_path.exists():  # Try direct .py file
            component_path = self.base_dir / f"{name}.py"
        if not component_path.exists():  # Try .yaml file in folder
            component_path = self.base_dir / name / "component.yaml"

        if not component_path.exists():
            self.logger.error(f"Could not find component file for {name}")
            return False

        return await self._load_asset(component_path)

    async def enable_component(self, name: str) -> bool:
        return await self.enable_asset(name)

    async def disable_component(self, name: str) -> bool:
        return await self.disable_asset(name)

    async def unload_component(self, name: str) -> bool:
        return await self.unload_asset(name)

    async def reload_component(self, name: str) -> bool:
        return await self.reload_asset(name)

    async def load_all_components(self) -> int:
        return await self.load_all_assets()

    async def enable_all_components(self) -> int:
        return await self.enable_all_assets()

    def get_component(self, name: str) -> Optional['Component']:
        return self.get_asset(name)

    def get_component_info(self, name: str) -> Optional['ComponentInfo']:
        return self.get_asset_info(name)

    def is_loaded(self, name: str) -> bool:
        return super().is_loaded(name)

    def is_enabled(self, name: str) -> bool:
        return super().is_enabled(name)

    def list_components(self) -> list[str]:
        return self.list_assets()

    def list_enabled_components(self) -> list[str]:
        return self.list_enabled_assets()

    def get_component_stats(self) -> dict[str, int]:
        return self.get_asset_stats()

    def provides_web_interface(self, name: str) -> bool:
        """Check if a component provides a web interface."""
        info = self.get_component_info(name)
        return getattr(info, "provides_web_interface", False)

"""Component loader and manager for Aetherius components."""

import asyncio
import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

from ..api.component import Component, ComponentInfo
from ..core.component import Component as CoreComponent, ComponentInfo as CoreComponentInfo, WebComponent
from ..core.config import Config
from .state import ComponentState


class ComponentManager:
    """Manages loading, enabling, and disabling of components."""
    
    def __init__(self, config: Config):
        """Initialize the component manager.
        
        Args:
            config: The global configuration object
        """
        self.config = config
        self.logger = logging.getLogger("aetherius.components")
        self.components_dir = Path("components")
        self.state = ComponentState()
        self._components: Dict[str, Component] = {}
        self._component_info: Dict[str, ComponentInfo] = {}
        
    async def load_all_components(self) -> int:
        """Load all components from the components directory.
        
        Returns:
            Number of components loaded
        """
        if not self.components_dir.exists():
            self.logger.info("Components directory not found, creating it")
            self.components_dir.mkdir(parents=True, exist_ok=True)
            return 0
        
        loaded_count = 0
        component_dirs = [d for d in self.components_dir.iterdir() if d.is_dir()]
        
        # Sort components by dependency order
        sorted_components = self._sort_by_dependencies(component_dirs)
        
        for component_dir in sorted_components:
            try:
                if await self._load_component(component_dir):
                    loaded_count += 1
            except Exception as e:
                self.logger.error(f"Failed to load component from {component_dir}: {e}")
        
        self.state.save()
        return loaded_count
    
    async def _load_component(self, component_dir: Path) -> bool:
        """Load a single component from directory.
        
        Args:
            component_dir: Path to component directory
            
        Returns:
            True if component was loaded successfully
        """
        component_file = component_dir / "__init__.py"
        if not component_file.exists():
            self.logger.warning(f"No __init__.py found in {component_dir}")
            return False
        
        component_name = component_dir.name
        
        try:
            # Load the component module
            spec = importlib.util.spec_from_file_location(
                f"component_{component_name}", component_file
            )
            if spec is None or spec.loader is None:
                self.logger.error(f"Failed to create spec for {component_name}")
                return False
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"component_{component_name}"] = module
            spec.loader.exec_module(module)
            
            # Get component info
            if not hasattr(module, 'COMPONENT_INFO'):
                self.logger.error(f"Component {component_name} missing COMPONENT_INFO")
                return False
            
            component_info: ComponentInfo = module.COMPONENT_INFO
            
            # Find the component class
            component_class = None
            if hasattr(module, component_info.main_class):
                component_class = getattr(module, component_info.main_class)
            else:
                # Search for Component subclasses
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, Component) and 
                        obj != Component):
                        component_class = obj
                        break
            
            if component_class is None:
                self.logger.error(f"No Component class found in {component_name}")
                return False
            
            # Check dependencies
            missing_deps = self._check_dependencies(component_info)
            if missing_deps:
                self.logger.error(f"Component {component_name} missing dependencies: {missing_deps}")
                return False
            
            # Create component instance
            component = component_class()
            component._component_info = component_info
            component.data_folder = component_dir / "data"
            component.data_folder.mkdir(parents=True, exist_ok=True)
            
            # Load component
            await component.on_load()
            
            # Store component
            self._components[component_name] = component
            self._component_info[component_name] = component_info
            self.state.add_loaded(component_name, component_info)
            
            self.logger.info(f"Loaded component: {component_name} v{component_info.version}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading component {component_name}: {e}")
            return False
    
    def _check_dependencies(self, component_info: ComponentInfo) -> List[str]:
        """Check if component dependencies are satisfied.
        
        Args:
            component_info: Component information
            
        Returns:
            List of missing dependencies
        """
        missing = []
        for dep in component_info.depends:
            if not self.is_loaded(dep):
                missing.append(dep)
        return missing
    
    def _sort_by_dependencies(self, component_dirs: List[Path]) -> List[Path]:
        """Sort component directories by dependency order.
        
        Args:
            component_dirs: List of component directories
            
        Returns:
            Sorted list with dependencies first
        """
        # For now, return as-is. In the future, implement topological sort
        # based on component dependencies
        return sorted(component_dirs, key=lambda p: p.name)
    
    async def enable_all_components(self) -> int:
        """Enable all loaded components.
        
        Returns:
            Number of components enabled
        """
        enabled_count = 0
        for component_name in self._components:
            try:
                if await self.enable_component(component_name):
                    enabled_count += 1
            except Exception as e:
                self.logger.error(f"Failed to enable component {component_name}: {e}")
        
        return enabled_count
    
    async def enable_component(self, name: str) -> bool:
        """Enable a specific component.
        
        Args:
            name: Component name
            
        Returns:
            True if component was enabled successfully
        """
        if not self.is_loaded(name):
            self.logger.error(f"Component {name} is not loaded")
            return False
        
        if self.is_enabled(name):
            self.logger.warning(f"Component {name} is already enabled")
            return True
        
        try:
            component = self._components[name]
            await component.on_enable()
            self.state.add_enabled(name)
            self.state.save()
            self.logger.info(f"Enabled component: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to enable component {name}: {e}")
            return False
    
    async def disable_component(self, name: str) -> bool:
        """Disable a specific component.
        
        Args:
            name: Component name
            
        Returns:
            True if component was disabled successfully
        """
        if not self.is_enabled(name):
            self.logger.warning(f"Component {name} is not enabled")
            return True
        
        try:
            component = self._components[name]
            await component.on_disable()
            self.state.remove_enabled(name)
            self.state.save()
            self.logger.info(f"Disabled component: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to disable component {name}: {e}")
            return False
    
    async def reload_component(self, name: str) -> bool:
        """Reload a specific component.
        
        Args:
            name: Component name
            
        Returns:
            True if component was reloaded successfully
        """
        if not self.is_loaded(name):
            self.logger.error(f"Component {name} is not loaded")
            return False
        
        was_enabled = self.is_enabled(name)
        
        try:
            # Disable if enabled
            if was_enabled:
                await self.disable_component(name)
            
            # Unload
            component = self._components[name]
            await component.on_unload()
            
            # Remove from memory
            component_dir = self.components_dir / name
            del self._components[name]
            del self._component_info[name]
            self.state.remove_loaded(name)
            
            # Reload
            success = await self._load_component(component_dir)
            if success and was_enabled:
                await self.enable_component(name)
            
            self.state.save()
            self.logger.info(f"Reloaded component: {name}")
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to reload component {name}: {e}")
            return False
    
    def is_loaded(self, name: str) -> bool:
        """Check if a component is loaded.
        
        Args:
            name: Component name
            
        Returns:
            True if component is loaded
        """
        return name in self._components
    
    def is_enabled(self, name: str) -> bool:
        """Check if a component is enabled.
        
        Args:
            name: Component name
            
        Returns:
            True if component is enabled
        """
        return self.state.is_enabled(name)
    
    def list_components(self) -> List[str]:
        """Get list of loaded component names.
        
        Returns:
            List of component names
        """
        return list(self._components.keys())
    
    def get_component(self, name: str) -> Optional[Component]:
        """Get a component instance by name.
        
        Args:
            name: Component name
            
        Returns:
            Component instance or None if not found
        """
        return self._components.get(name)
    
    def get_component_info(self, name: str) -> Optional[ComponentInfo]:
        """Get component information by name.
        
        Args:
            name: Component name
            
        Returns:
            Component info or None if not found
        """
        return self._component_info.get(name)
    
    def get_component_stats(self) -> Dict[str, Any]:
        """Get component system statistics.
        
        Returns:
            Dictionary with component statistics
        """
        total = len(self._components)
        enabled = len([name for name in self._components if self.is_enabled(name)])
        disabled = total - enabled
        
        return {
            "total": total,
            "enabled": enabled,
            "disabled": disabled
        }
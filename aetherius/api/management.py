"""Management API for Aetherius Core with comprehensive control capabilities."""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Union, Callable
from pathlib import Path
from datetime import datetime
from enum import Enum

from ..core.server import ServerController
from ..core.config import get_config_manager, ConfigManager
from ..core.player_data import get_player_data_manager, PlayerDataManager
from ..core.event_manager import get_event_manager, EventManager
from ..plugins.loader import PluginManager
from ..components.loader import ComponentManager as ComponentLoader
from ..plugins.state import PluginState
from ..components.state import ComponentState
from .enhanced import EnhancedAetheriusAPI


logger = logging.getLogger(__name__)


class ControlLevel(Enum):
    """Control access levels for management operations."""
    READ_ONLY = "read_only"
    OPERATOR = "operator"
    ADMIN = "admin"
    SYSTEM = "system"


class InfoStreamType(Enum):
    """Information stream types."""
    CONSOLE_OUTPUT = "console_output"
    SERVER_LOGS = "server_logs"
    PERFORMANCE_METRICS = "performance_metrics"
    PLAYER_EVENTS = "player_events"
    SYSTEM_EVENTS = "system_events"
    PLUGIN_EVENTS = "plugin_events"
    COMPONENT_EVENTS = "component_events"


class AetheriusManagementAPI(EnhancedAetheriusAPI):
    """
    Comprehensive management API for Aetherius Core providing advanced control capabilities.
    
    This API extends the enhanced API with:
    - Plugin management and control
    - Component lifecycle management  
    - Advanced server control operations
    - Information stream management and filtering
    - Access control and permission system
    - Batch operations and automation
    """
    
    def __init__(self, server: ServerController, access_level: ControlLevel = ControlLevel.OPERATOR):
        """Initialize management API with access control."""
        super().__init__(server)
        self.access_level = access_level
        self.plugin_manager = PluginManager(get_config_manager())
        self.component_loader = ComponentLoader(get_config_manager())
        
        # Information stream management
        self._info_streams: Dict[str, Dict[str, Any]] = {}
        self._stream_callbacks: Dict[InfoStreamType, List[Callable]] = {}
        self._stream_filters: Dict[InfoStreamType, List[Callable]] = {}
        
        # Initialize stream types
        for stream_type in InfoStreamType:
            self._stream_callbacks[stream_type] = []
            self._stream_filters[stream_type] = []
    
    def _check_permission(self, required_level: ControlLevel) -> bool:
        """Check if current access level permits the operation."""
        levels = [ControlLevel.READ_ONLY, ControlLevel.OPERATOR, ControlLevel.ADMIN, ControlLevel.SYSTEM]
        current_index = levels.index(self.access_level)
        required_index = levels.index(required_level)
        return current_index >= required_index
    
    # Plugin Management API
    
    async def get_plugin_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all plugins with their status.
        
        Returns:
            List of plugin information dictionaries
        """
        plugins = []
        plugin_states = self.plugin_loader.get_plugin_states()
        
        for plugin_name, state in plugin_states.items():
            plugin_info = {
                "name": plugin_name,
                "state": state.value,
                "enabled": state == PluginState.ENABLED,
                "loaded": state in [PluginState.LOADED, PluginState.ENABLED],
                "version": self.plugin_loader.get_plugin_version(plugin_name),
                "description": self.plugin_loader.get_plugin_description(plugin_name),
                "dependencies": self.plugin_loader.get_plugin_dependencies(plugin_name),
                "file_path": str(self.plugin_loader.get_plugin_path(plugin_name)),
                "last_modified": self._get_file_modified_time(
                    self.plugin_loader.get_plugin_path(plugin_name)
                )
            }
            plugins.append(plugin_info)
        
        return plugins
    
    async def load_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Load a plugin.
        
        Args:
            plugin_name: Name of the plugin to load
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            success = await self.plugin_loader.load_plugin(plugin_name)
            return {
                "success": success,
                "message": f"Plugin '{plugin_name}' loaded successfully" if success else f"Failed to load plugin '{plugin_name}'",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error loading plugin {plugin_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def unload_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Unload a plugin.
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            success = await self.plugin_loader.unload_plugin(plugin_name)
            return {
                "success": success,
                "message": f"Plugin '{plugin_name}' unloaded successfully" if success else f"Failed to unload plugin '{plugin_name}'",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def enable_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Enable a plugin.
        
        Args:
            plugin_name: Name of the plugin to enable
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            success = await self.plugin_loader.enable_plugin(plugin_name)
            return {
                "success": success,
                "message": f"Plugin '{plugin_name}' enabled successfully" if success else f"Failed to enable plugin '{plugin_name}'",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error enabling plugin {plugin_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def disable_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Disable a plugin.
        
        Args:
            plugin_name: Name of the plugin to disable
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            success = await self.plugin_loader.disable_plugin(plugin_name)
            return {
                "success": success,
                "message": f"Plugin '{plugin_name}' disabled successfully" if success else f"Failed to disable plugin '{plugin_name}'",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error disabling plugin {plugin_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def reload_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Reload a plugin (unload and load again).
        
        Args:
            plugin_name: Name of the plugin to reload
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            # Unload first
            await self.plugin_loader.unload_plugin(plugin_name)
            # Then load again
            success = await self.plugin_loader.load_plugin(plugin_name)
            return {
                "success": success,
                "message": f"Plugin '{plugin_name}' reloaded successfully" if success else f"Failed to reload plugin '{plugin_name}'",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error reloading plugin {plugin_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def reload_all_plugins(self) -> Dict[str, Any]:
        """
        Reload all loaded plugins.
        
        Returns:
            Operation result with detailed status
        """
        if not self._check_permission(ControlLevel.SYSTEM):
            return {"success": False, "error": "Insufficient permissions"}
        
        results = []
        plugin_states = self.plugin_loader.get_plugin_states()
        
        for plugin_name, state in plugin_states.items():
            if state in [PluginState.LOADED, PluginState.ENABLED]:
                result = await self.reload_plugin(plugin_name)
                results.append({
                    "plugin": plugin_name,
                    "success": result["success"],
                    "message": result.get("message", "")
                })
        
        successful = sum(1 for r in results if r["success"])
        total = len(results)
        
        return {
            "success": successful == total,
            "message": f"Reloaded {successful}/{total} plugins successfully",
            "details": results,
            "timestamp": datetime.now().isoformat()
        }
    
    # Component Management API
    
    async def get_component_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all components with their status.
        
        Returns:
            List of component information dictionaries
        """
        components = []
        component_states = self.component_loader.get_component_states()
        
        for component_name, state in component_states.items():
            component_info = {
                "name": component_name,
                "state": state.value,
                "enabled": state == ComponentState.ENABLED,
                "loaded": state in [ComponentState.LOADED, ComponentState.ENABLED],
                "version": self.component_loader.get_component_version(component_name),
                "description": self.component_loader.get_component_description(component_name),
                "dependencies": self.component_loader.get_component_dependencies(component_name),
                "provides_web_interface": self.component_loader.provides_web_interface(component_name),
                "file_path": str(self.component_loader.get_component_path(component_name)),
                "last_modified": self._get_file_modified_time(
                    self.component_loader.get_component_path(component_name)
                )
            }
            components.append(component_info)
        
        return components
    
    async def load_component(self, component_name: str) -> Dict[str, Any]:
        """
        Load a component.
        
        Args:
            component_name: Name of the component to load
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            success = await self.component_loader.load_component(component_name)
            return {
                "success": success,
                "message": f"Component '{component_name}' loaded successfully" if success else f"Failed to load component '{component_name}'",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error loading component {component_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def unload_component(self, component_name: str) -> Dict[str, Any]:
        """
        Unload a component.
        
        Args:
            component_name: Name of the component to unload
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            success = await self.component_loader.unload_component(component_name)
            return {
                "success": success,
                "message": f"Component '{component_name}' unloaded successfully" if success else f"Failed to unload component '{component_name}'",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error unloading component {component_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def enable_component(self, component_name: str) -> Dict[str, Any]:
        """
        Enable a component.
        
        Args:
            component_name: Name of the component to enable
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            success = await self.component_loader.enable_component(component_name)
            return {
                "success": success,
                "message": f"Component '{component_name}' enabled successfully" if success else f"Failed to enable component '{component_name}'",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error enabling component {component_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def disable_component(self, component_name: str) -> Dict[str, Any]:
        """
        Disable a component.
        
        Args:
            component_name: Name of the component to disable
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            success = await self.component_loader.disable_component(component_name)
            return {
                "success": success,
                "message": f"Component '{component_name}' disabled successfully" if success else f"Failed to disable component '{component_name}'",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error disabling component {component_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    # Advanced Server Control API
    
    async def start_server_advanced(self, 
                                  java_args: Optional[List[str]] = None,
                                  mc_args: Optional[List[str]] = None,
                                  custom_jar: Optional[str] = None) -> Dict[str, Any]:
        """
        Start server with advanced options.
        
        Args:
            java_args: Custom Java arguments
            mc_args: Custom Minecraft server arguments
            custom_jar: Path to custom server JAR
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            # Update configuration if custom options provided
            if java_args:
                self.set_config_value("server.java_args", java_args, save=False)
            if mc_args:
                self.set_config_value("server.mc_args", mc_args, save=False)
            if custom_jar:
                self.set_config_value("server.jar_path", custom_jar, save=False)
            
            success = await self.server.start()
            return {
                "success": success,
                "message": "Server started with advanced options" if success else "Failed to start server",
                "java_args": java_args,
                "mc_args": mc_args,
                "jar_path": custom_jar,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error starting server with advanced options: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def stop_server_graceful(self, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Stop server gracefully with timeout.
        
        Args:
            timeout: Timeout in seconds for graceful shutdown
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            # First try graceful stop with save-all
            await self.send_command("save-all")
            await asyncio.sleep(2)  # Give time for save
            await self.send_command("stop")
            
            # Wait for graceful shutdown
            start_time = asyncio.get_event_loop().time()
            while self.server.is_alive and (asyncio.get_event_loop().time() - start_time) < timeout:
                await asyncio.sleep(1)
            
            if self.server.is_alive:
                # Force stop if still running
                await self.server.stop()
                return {
                    "success": True,
                    "message": f"Server stopped forcefully after {timeout}s timeout",
                    "forced": True,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": True,
                    "message": "Server stopped gracefully",
                    "forced": False,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error stopping server gracefully: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def restart_server_scheduled(self, delay_seconds: float = 60.0, 
                                     warning_intervals: List[float] = None) -> Dict[str, Any]:
        """
        Schedule a server restart with warnings.
        
        Args:
            delay_seconds: Delay before restart
            warning_intervals: List of warning times (seconds before restart)
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        if warning_intervals is None:
            warning_intervals = [60, 30, 10, 5]
        
        try:
            # Send warnings
            for warning_time in sorted(warning_intervals, reverse=True):
                if warning_time <= delay_seconds:
                    wait_time = delay_seconds - warning_time
                    await asyncio.sleep(wait_time)
                    await self.send_command(f"say Server restart in {warning_time} seconds!")
                    delay_seconds = warning_time
            
            # Final countdown
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            
            # Restart
            await self.stop_server_graceful()
            await asyncio.sleep(5)  # Wait a bit before starting
            start_result = await self.start_server_advanced()
            
            return {
                "success": start_result["success"],
                "message": "Server restarted successfully" if start_result["success"] else "Failed to restart server",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error during scheduled restart: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def backup_world(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a world backup.
        
        Args:
            backup_name: Custom backup name
            
        Returns:
            Operation result
        """
        if not self._check_permission(ControlLevel.OPERATOR):
            return {"success": False, "error": "Insufficient permissions"}
        
        try:
            import shutil
            from pathlib import Path
            
            # Save world first if server is running
            if self.server.is_alive:
                await self.send_command("save-all")
                await asyncio.sleep(3)  # Wait for save completion
            
            # Create backup
            world_path = Path(self.get_config_value("server.working_directory", "server")) / "world"
            backup_dir = Path("backups")
            backup_dir.mkdir(exist_ok=True)
            
            if not backup_name:
                backup_name = f"world_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            backup_path = backup_dir / backup_name
            shutil.copytree(world_path, backup_path)
            
            return {
                "success": True,
                "message": f"World backup created: {backup_name}",
                "backup_path": str(backup_path),
                "backup_size": self._get_directory_size(backup_path),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating world backup: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    # Information Stream Management API
    
    def register_stream_callback(self, stream_type: InfoStreamType, callback: Callable) -> None:
        """
        Register a callback for information stream.
        
        Args:
            stream_type: Type of information stream
            callback: Callback function to receive stream data
        """
        self._stream_callbacks[stream_type].append(callback)
        logger.info(f"Registered callback for {stream_type.value} stream")
    
    def unregister_stream_callback(self, stream_type: InfoStreamType, callback: Callable) -> None:
        """
        Unregister a callback from information stream.
        
        Args:
            stream_type: Type of information stream
            callback: Callback function to remove
        """
        if callback in self._stream_callbacks[stream_type]:
            self._stream_callbacks[stream_type].remove(callback)
            logger.info(f"Unregistered callback for {stream_type.value} stream")
    
    def add_stream_filter(self, stream_type: InfoStreamType, filter_func: Callable) -> None:
        """
        Add a filter to an information stream.
        
        Args:
            stream_type: Type of information stream
            filter_func: Filter function that returns True to include data
        """
        self._stream_filters[stream_type].append(filter_func)
        logger.info(f"Added filter to {stream_type.value} stream")
    
    def remove_stream_filter(self, stream_type: InfoStreamType, filter_func: Callable) -> None:
        """
        Remove a filter from an information stream.
        
        Args:
            stream_type: Type of information stream
            filter_func: Filter function to remove
        """
        if filter_func in self._stream_filters[stream_type]:
            self._stream_filters[stream_type].remove(filter_func)
            logger.info(f"Removed filter from {stream_type.value} stream")
    
    async def broadcast_to_stream(self, stream_type: InfoStreamType, data: Dict[str, Any]) -> None:
        """
        Broadcast data to information stream subscribers.
        
        Args:
            stream_type: Type of information stream
            data: Data to broadcast
        """
        # Apply filters
        for filter_func in self._stream_filters[stream_type]:
            try:
                if not filter_func(data):
                    return  # Data filtered out
            except Exception as e:
                logger.error(f"Error in stream filter: {e}")
        
        # Send to all callbacks
        for callback in self._stream_callbacks[stream_type]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in stream callback: {e}")
    
    def get_stream_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered streams.
        
        Returns:
            Dictionary with stream information
        """
        stream_info = {}
        for stream_type in InfoStreamType:
            stream_info[stream_type.value] = {
                "callback_count": len(self._stream_callbacks[stream_type]),
                "filter_count": len(self._stream_filters[stream_type]),
                "active": len(self._stream_callbacks[stream_type]) > 0
            }
        return stream_info
    
    # Utility Methods
    
    def _get_file_modified_time(self, file_path: Path) -> Optional[str]:
        """Get file modification time as ISO string."""
        try:
            if file_path and file_path.exists():
                mtime = file_path.stat().st_mtime
                return datetime.fromtimestamp(mtime).isoformat()
        except Exception:
            pass
        return None
    
    def _get_directory_size(self, directory: Path) -> int:
        """Get total size of directory in bytes."""
        try:
            return sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())
        except Exception:
            return 0
    
    # Batch Operations API
    
    async def batch_plugin_operation(self, operation: str, plugin_names: List[str]) -> Dict[str, Any]:
        """
        Perform batch operation on multiple plugins.
        
        Args:
            operation: Operation to perform ('load', 'unload', 'enable', 'disable', 'reload')
            plugin_names: List of plugin names
            
        Returns:
            Batch operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        operations = {
            'load': self.load_plugin,
            'unload': self.unload_plugin,
            'enable': self.enable_plugin,
            'disable': self.disable_plugin,
            'reload': self.reload_plugin
        }
        
        if operation not in operations:
            return {"success": False, "error": f"Unknown operation: {operation}"}
        
        results = []
        for plugin_name in plugin_names:
            result = await operations[operation](plugin_name)
            results.append({
                "plugin": plugin_name,
                "success": result["success"],
                "message": result.get("message", ""),
                "error": result.get("error")
            })
        
        successful = sum(1 for r in results if r["success"])
        total = len(results)
        
        return {
            "success": successful == total,
            "operation": operation,
            "message": f"{operation.title()} operation completed: {successful}/{total} successful",
            "details": results,
            "timestamp": datetime.now().isoformat()
        }
    
    async def batch_component_operation(self, operation: str, component_names: List[str]) -> Dict[str, Any]:
        """
        Perform batch operation on multiple components.
        
        Args:
            operation: Operation to perform ('load', 'unload', 'enable', 'disable')
            component_names: List of component names
            
        Returns:
            Batch operation result
        """
        if not self._check_permission(ControlLevel.ADMIN):
            return {"success": False, "error": "Insufficient permissions"}
        
        operations = {
            'load': self.load_component,
            'unload': self.unload_component,
            'enable': self.enable_component,
            'disable': self.disable_component
        }
        
        if operation not in operations:
            return {"success": False, "error": f"Unknown operation: {operation}"}
        
        results = []
        for component_name in component_names:
            result = await operations[operation](component_name)
            results.append({
                "component": component_name,
                "success": result["success"],
                "message": result.get("message", ""),
                "error": result.get("error")
            })
        
        successful = sum(1 for r in results if r["success"])
        total = len(results)
        
        return {
            "success": successful == total,
            "operation": operation,
            "message": f"{operation.title()} operation completed: {successful}/{total} successful",
            "details": results,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health information.
        
        Returns:
            System health data
        """
        try:
            import psutil
            import sys
            
            # Get system information
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get Aetherius-specific info
            performance = await self.get_server_performance()
            plugin_list = await self.get_plugin_list()
            component_list = await self.get_component_list()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": (disk.used / disk.total) * 100,
                    "python_version": sys.version,
                    "platform": sys.platform
                },
                "server": {
                    "running": self.server.is_alive,
                    "performance": performance
                },
                "plugins": {
                    "total": len(plugin_list),
                    "enabled": len([p for p in plugin_list if p["enabled"]]),
                    "loaded": len([p for p in plugin_list if p["loaded"]])
                },
                "components": {
                    "total": len(component_list),
                    "enabled": len([c for c in component_list if c["enabled"]]),
                    "loaded": len([c for c in component_list if c["loaded"]])
                },
                "streams": self.get_stream_info()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
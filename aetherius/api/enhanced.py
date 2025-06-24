"""Enhanced API for Aetherius Core with extended functionality for components."""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

from ..core.server import ServerProcessWrapper
from ..core.config import get_config_manager, ConfigManager
from ..core.player_data import get_player_data_manager, PlayerDataManager, PlayerData
from ..core.event_manager import get_event_manager, EventManager
from .component import Component


logger = logging.getLogger(__name__)


class EnhancedAetheriusAPI:
    """
    Enhanced API for Aetherius Core providing extended functionality for official components.
    
    This API extends the base functionality with:
    - Performance monitoring with psutil integration
    - Structured player data with helper plugin support
    - Unified configuration management API
    """
    
    def __init__(self, server: ServerProcessWrapper):
        """Initialize enhanced API."""
        self.server = server
        self.config = get_config_manager()
        self.events = get_event_manager()
        self.players = get_player_data_manager()
        
        # Initialize performance monitoring
        self._performance_monitor_task: Optional[asyncio.Task] = None
        self._performance_data: Dict[str, Any] = {}
        self._monitoring_enabled = False
    
    # Performance Monitoring API
    
    async def get_server_performance(self) -> Dict[str, Any]:
        """
        Get comprehensive server performance metrics.
        
        Returns:
            Dictionary containing detailed performance information
        """
        if not self.server.is_alive:
            return {
                "status": "offline",
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "uptime_seconds": 0.0
            }
        
        # Get basic performance metrics from server
        metrics = await self.server.get_performance_metrics()
        
        # Add additional system information
        metrics.update({
            "java_version": self._get_java_version(),
            "server_jar": str(Path(self.config.get_value("server.jar_path", "server.jar")).name),
            "max_memory": self._parse_memory_setting(
                self.config.get_value("server.java_args", [])
            ),
            "online_players": self.players.get_online_count(),
            "total_players": self.players.get_player_count()
        })
        
        return metrics
    
    def _get_java_version(self) -> str:
        """Get Java version information."""
        try:
            import subprocess
            java_exe = self.config.get_value("server.java_executable", "java")
            result = subprocess.run(
                [java_exe, "-version"], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            if result.stderr:
                # Java version info is typically in stderr
                lines = result.stderr.split('\n')
                for line in lines:
                    if 'version' in line.lower():
                        return line.strip()
            return "Unknown"
        except Exception:
            return "Unknown"
    
    def _parse_memory_setting(self, java_args: List[str]) -> str:
        """Parse memory settings from Java arguments."""
        for arg in java_args:
            if arg.startswith('-Xmx'):
                return arg[4:]  # Remove -Xmx prefix
        return "Unknown"
    
    async def start_performance_monitoring(self, interval: float = 10.0) -> bool:
        """
        Start continuous performance monitoring.
        
        Args:
            interval: Monitoring interval in seconds
            
        Returns:
            True if started successfully
        """
        if self._monitoring_enabled:
            return True
        
        try:
            self._monitoring_enabled = True
            self._performance_monitor_task = asyncio.create_task(
                self._performance_monitor_loop(interval)
            )
            logger.info(f"Started performance monitoring with {interval}s interval")
            return True
        except Exception as e:
            logger.error(f"Failed to start performance monitoring: {e}")
            self._monitoring_enabled = False
            return False
    
    async def stop_performance_monitoring(self) -> None:
        """Stop performance monitoring."""
        self._monitoring_enabled = False
        if self._performance_monitor_task:
            self._performance_monitor_task.cancel()
            try:
                await self._performance_monitor_task
            except asyncio.CancelledError:
                pass
            self._performance_monitor_task = None
        logger.info("Stopped performance monitoring")
    
    async def _performance_monitor_loop(self, interval: float) -> None:
        """Performance monitoring loop."""
        while self._monitoring_enabled:
            try:
                # Get performance data
                perf_data = await self.get_server_performance()
                self._performance_data = perf_data
                
                # Update player data from helper plugin if available
                await self.players.update_from_helper_plugin()
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in performance monitoring loop: {e}")
                await asyncio.sleep(interval)
    
    def get_cached_performance_data(self) -> Dict[str, Any]:
        """Get the last cached performance data."""
        return self._performance_data.copy()
    
    # Configuration Management API
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: Configuration key in dot notation
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
        """
        return self.config.get_value(key, default)
    
    def set_config_value(self, key: str, value: Any, save: bool = True) -> bool:
        """
        Set a configuration value using dot notation.
        
        Args:
            key: Configuration key in dot notation
            value: Value to set
            save: Whether to save to file immediately
            
        Returns:
            True if set successfully
        """
        return self.config.set_value(key, value, save)
    
    def get_config_section(self, section: str) -> Dict[str, Any]:
        """
        Get an entire configuration section.
        
        Args:
            section: Section name
            
        Returns:
            Dictionary containing the section data
        """
        return self.config.get_section(section)
    
    def set_config_section(self, section: str, data: Dict[str, Any], save: bool = True) -> bool:
        """
        Set an entire configuration section.
        
        Args:
            section: Section name
            data: Section data
            save: Whether to save to file immediately
            
        Returns:
            True if set successfully
        """
        return self.config.set_section(section, data, save)
    
    def delete_config_value(self, key: str, save: bool = True) -> bool:
        """
        Delete a configuration value.
        
        Args:
            key: Configuration key in dot notation
            save: Whether to save to file immediately
            
        Returns:
            True if deleted successfully
        """
        return self.config.delete_value(key, save)
    
    def has_config_value(self, key: str) -> bool:
        """
        Check if a configuration key exists.
        
        Args:
            key: Configuration key in dot notation
            
        Returns:
            True if key exists
        """
        return self.config.has_value(key)
    
    def get_config_keys(self, prefix: str = "") -> List[str]:
        """
        Get all configuration keys with optional prefix filter.
        
        Args:
            prefix: Key prefix to filter by
            
        Returns:
            List of configuration keys
        """
        return self.config.get_keys(prefix)
    
    def add_config_change_callback(self, callback: callable) -> None:
        """
        Add a callback for configuration changes.
        
        Args:
            callback: Function to call with (key, value) arguments
        """
        self.config.add_change_callback(callback)
    
    def remove_config_change_callback(self, callback: callable) -> None:
        """
        Remove a configuration change callback.
        
        Args:
            callback: Callback function to remove
        """
        self.config.remove_change_callback(callback)
    
    # Player Data API
    
    def get_player_data(self, player_name: str) -> Optional[PlayerData]:
        """
        Get detailed player data.
        
        Args:
            player_name: Player name
            
        Returns:
            PlayerData object or None if not found
        """
        return self.players.get_player_data(player_name)
    
    def get_all_players(self) -> Dict[str, PlayerData]:
        """
        Get all known players.
        
        Returns:
            Dictionary mapping player names to PlayerData objects
        """
        return self.players.get_all_players()
    
    def get_online_players(self) -> Dict[str, PlayerData]:
        """
        Get all online players.
        
        Returns:
            Dictionary mapping online player names to PlayerData objects
        """
        return self.players.get_online_players()
    
    def get_player_count(self) -> int:
        """Get total number of known players."""
        return self.players.get_player_count()
    
    def get_online_count(self) -> int:
        """Get number of online players."""
        return self.players.get_online_count()
    
    def update_player_data(self, player_name: str, **kwargs) -> bool:
        """
        Update player data.
        
        Args:
            player_name: Player name
            **kwargs: Player data fields to update
            
        Returns:
            True if updated successfully
        """
        return self.players.update_player_data(player_name, **kwargs)
    
    def set_player_location(
        self, 
        player_name: str, 
        x: float, y: float, z: float, 
        dimension: str = "overworld",
        yaw: float = 0.0, 
        pitch: float = 0.0
    ) -> bool:
        """
        Set player location.
        
        Args:
            player_name: Player name
            x, y, z: Coordinates
            dimension: Dimension name
            yaw, pitch: Rotation
            
        Returns:
            True if set successfully
        """
        return self.players.set_player_location(
            player_name, x, y, z, dimension, yaw, pitch
        )
    
    def set_player_stats(self, player_name: str, **stats) -> bool:
        """
        Set player statistics.
        
        Args:
            player_name: Player name
            **stats: Statistics to update
            
        Returns:
            True if set successfully
        """
        return self.players.set_player_stats(player_name, **stats)
    
    async def refresh_player_data(self) -> bool:
        """
        Refresh player data from helper plugin.
        
        Returns:
            True if refreshed successfully
        """
        return await self.players.refresh_helper_data()
    
    def enable_helper_plugin(self, data_file_path: Optional[str] = None) -> None:
        """
        Enable helper plugin integration.
        
        Args:
            data_file_path: Path to helper plugin data file
        """
        self.players.enable_helper_plugin(data_file_path)
    
    def disable_helper_plugin(self) -> None:
        """Disable helper plugin integration."""
        self.players.disable_helper_plugin()
    
    # Server Control API (enhanced)
    
    async def send_command(self, command: str) -> bool:
        """
        Send command to server.
        
        Args:
            command: Command to send
            
        Returns:
            True if sent successfully
        """
        return await self.server.send_command(command)
    
    async def send_command_with_output(self, command: str, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Send command and capture output.
        
        Args:
            command: Command to send
            timeout: Timeout in seconds
            
        Returns:
            Dictionary containing success status and output
        """
        try:
            success = await self.server.send_command_via_queue(command, timeout)
            return {
                "success": success,
                "command": command,
                "timestamp": asyncio.get_event_loop().time()
            }
        except Exception as e:
            return {
                "success": False,
                "command": command,
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }
    
    def get_server_status(self) -> Dict[str, Any]:
        """
        Get comprehensive server status.
        
        Returns:
            Dictionary containing server status information
        """
        return {
            "running": self.server.is_alive,
            "pid": self.server.get_pid(),
            "jar_path": self.config.get_value("server.jar_path"),
            "working_directory": self.config.get_value("server.working_directory"),
            "auto_restart": self.config.get_value("server.auto_restart"),
            "monitoring_enabled": self._monitoring_enabled,
            "helper_plugin_enabled": self.config.get_value("helper_plugin.enabled", False)
        }


class EnhancedComponent(Component):
    """
    Enhanced component base class with access to extended APIs.
    
    This extends the basic Component class with direct access to enhanced APIs
    for performance monitoring, player data, and configuration management.
    """
    
    def __init__(self):
        super().__init__()
        self._enhanced_api: Optional[EnhancedAetheriusAPI] = None
    
    @property
    def enhanced_api(self) -> Optional[EnhancedAetheriusAPI]:
        """Get enhanced API instance."""
        return self._enhanced_api
    
    def _set_enhanced_api(self, api: EnhancedAetheriusAPI) -> None:
        """Set enhanced API instance (called by component loader)."""
        self._enhanced_api = api
    
    # Convenience methods for enhanced functionality
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get server performance metrics."""
        if self._enhanced_api:
            return await self._enhanced_api.get_server_performance()
        return {}
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value with dot notation."""
        if self._enhanced_api:
            # Try component-specific config first
            component_key = f"components.{self.name}.{key}"
            if self._enhanced_api.has_config_value(component_key):
                return self._enhanced_api.get_config_value(component_key, default)
            # Fall back to global key
            return self._enhanced_api.get_config_value(key, default)
        return default
    
    def set_config(self, key: str, value: Any, save: bool = True) -> bool:
        """Set configuration value with dot notation."""
        if self._enhanced_api:
            # Set as component-specific config
            component_key = f"components.{self.name}.{key}"
            return self._enhanced_api.set_config_value(component_key, value, save)
        return False
    
    def get_player_data(self, player_name: str) -> Optional[PlayerData]:
        """Get player data."""
        if self._enhanced_api:
            return self._enhanced_api.get_player_data(player_name)
        return None
    
    def get_online_players(self) -> Dict[str, PlayerData]:
        """Get online players."""
        if self._enhanced_api:
            return self._enhanced_api.get_online_players()
        return {}
    
    async def send_server_command(self, command: str) -> bool:
        """Send command to server."""
        if self._enhanced_api:
            return await self._enhanced_api.send_command(command)
        return False
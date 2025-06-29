"""
Aetherius Core Unified API
==========================

Unified, comprehensive API system for Aetherius Core providing all functionality
through a single, elegant interface while maintaining core independence.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Union, Callable, Type
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from abc import ABC, abstractmethod
from dataclasses import asdict

from ..core.server import ServerController, ServerState
from ..core.config import get_config_manager, ConfigManager
from ..core.player_data import get_player_data_manager, PlayerDataManager
from ..core.event_manager import get_event_manager, EventManager, BaseEvent
from ..plugins.loader import PluginManager
from ..components.loader import ComponentManager as ComponentLoader


logger = logging.getLogger(__name__)


class APIModule(ABC):
    """Base class for API modules."""
    
    def __init__(self, core_api: 'AetheriusCoreAPI'):
        self.core = core_api
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the API module."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup the API module."""
        pass


class ServerAPI(APIModule):
    """Server management API module, acting as a facade for the ServerController."""

    async def initialize(self) -> bool:
        return True

    async def cleanup(self) -> None:
        if self.core._server and self.core._server.state != ServerState.STOPPED:
            await self.core._server.stop()

    @property
    def state(self) -> ServerState:
        return self.core._server.state if self.core._server else ServerState.STOPPED

    async def start(self) -> Dict[str, Any]:
        """Start the Minecraft server."""
        if not self.core._server:
            await self.core._initialize_server()
        
        success = await self.core._server.start()
        return {
            "success": success,
            "message": "Server started successfully" if success else "Failed to start server",
            "state": self.state.name
        }

    async def stop(self, timeout: float = 30.0) -> Dict[str, Any]:
        """Stop the Minecraft server."""
        if not self.core._server:
            return {"success": False, "message": "Server not initialized"}

        success = await self.core._server.stop(timeout)
        return {
            "success": success,
            "message": "Server stopped successfully" if success else "Failed to stop server",
            "state": self.state.name
        }

    async def restart(self, delay: float = 5.0) -> Dict[str, Any]:
        """Restart the server."""
        stop_result = await self.stop()
        if not stop_result["success"]:
            return {"success": False, "message": "Failed to stop server for restart", "details": stop_result}

        await asyncio.sleep(delay)

        start_result = await self.start()
        return {
            "success": start_result["success"],
            "message": "Server restarted successfully" if start_result["success"] else "Failed to start server after restart",
            "details": {"stop": stop_result, "start": start_result}
        }

    async def send_command(self, command: str) -> Dict[str, Any]:
        """Send a command to the server."""
        if not self.core._server:
            return {"success": False, "message": "Server not initialized"}

        success = await self.core._server.send_command(command)
        return {
            "success": success,
            "command": command,
            "message": "Command sent successfully" if success else "Failed to send command"
        }

    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive server status."""
        if not self.core._server:
            return {"state": ServerState.STOPPED.name, "performance": {}}

        return {
            "state": self.state.name,
            "performance": self.core._server.get_performance_metrics(),
            "config": self.core.config.server.model_dump(),
            "timestamp": datetime.now().isoformat()
        }


class PluginAPI(APIModule):
    """Plugin management API module."""
    
    def __init__(self, core_api: 'AetheriusCoreAPI'):
        super().__init__(core_api)
        self._manager = PluginManager(core_api)
    
    async def initialize(self) -> bool:
        """Initialize plugin API."""
        await self._manager.auto_restore_plugins()
        return True
    
    async def cleanup(self) -> None:
        """Cleanup plugin API."""
        await self._manager.disable_all_assets()
        await self._manager.unload_all_assets()
    
    async def list(self) -> List[Dict[str, Any]]:
        """Get list of all plugins."""
        plugins = []
        for name in self._manager.list_assets():
            info = self._manager.get_asset_info(name)
            plugin = self._manager.get_asset(name)
            if info and plugin:
                plugins.append({
                    "name": name,
                    "version": info.version,
                    "description": info.description,
                    "author": info.author,
                    "enabled": plugin.enabled,
                    "loaded": plugin.loaded,
                    "path": str(self._manager.base_dir / name)
                })
        return plugins
    
    async def load(self, name: str) -> Dict[str, Any]:
        """Load a plugin."""
        success = await self._manager.load_plugin(name)
        return {"success": success, "message": f"Plugin {name} loaded" if success else f"Failed to load plugin {name}"}
    
    async def unload(self, name: str) -> Dict[str, Any]:
        """Unload a plugin."""
        success = await self._manager.unload_plugin(name)
        return {"success": success, "message": f"Plugin {name} unloaded" if success else f"Failed to unload plugin {name}"}
    
    async def enable(self, name: str) -> Dict[str, Any]:
        """Enable a plugin."""
        success = await self._manager.enable_plugin(name)
        return {"success": success, "message": f"Plugin {name} enabled" if success else f"Failed to enable plugin {name}"}
    
    async def disable(self, name: str) -> Dict[str, Any]:
        """Disable a plugin."""
        success = await self._manager.disable_plugin(name)
        return {"success": success, "message": f"Plugin {name} disabled" if success else f"Failed to disable plugin {name}"}
    
    async def reload(self, name: str) -> Dict[str, Any]:
        """Reload a plugin."""
        success = await self._manager.reload_plugin(name)
        return {"success": success, "message": f"Plugin {name} reloaded" if success else f"Failed to reload plugin {name}"}
    
    async def reload_all(self) -> Dict[str, Any]:
        """Reload all loaded plugins."""
        await self._manager.disable_all_assets()
        await self._manager.unload_all_assets()
        loaded_count = await self._manager.load_all_assets()
        enabled_count = await self._manager.enable_all_assets()
        return {"success": True, "message": f"Reloaded {loaded_count} plugins, enabled {enabled_count}"}


class ComponentAPI(APIModule):
    """Component management API module."""
    
    def __init__(self, core_api: 'AetheriusCoreAPI'):
        super().__init__(core_api)
        self._loader = ComponentLoader(core_api)
    
    async def initialize(self) -> bool:
        """Initialize component API."""
        await self._loader.load_all_assets()
        await self._loader.enable_all_assets()
        return True
    
    async def cleanup(self) -> None:
        """Cleanup component API."""
        await self._loader.disable_all_assets()
        await self._loader.unload_all_assets()
    
    async def list(self) -> List[Dict[str, Any]]:
        """Get list of all components."""
        components = []
        for name in self._loader.list_assets():
            info = self._loader.get_asset_info(name)
            component = self._loader.get_asset(name)
            if info and component:
                components.append({
                    "name": name,
                    "version": info.version,
                    "description": info.description,
                    "author": info.author,
                    "enabled": component.enabled,
                    "loaded": component.loaded,
                    "path": str(self._loader.base_dir / name),
                    "provides_web_interface": getattr(info, 'provides_web_interface', False)
                })
        return components
    
    async def load(self, name: str) -> Dict[str, Any]:
        """Load a component."""
        success = await self._loader.load_component(name)
        return {"success": success, "message": f"Component {name} loaded" if success else f"Failed to load component {name}"}
    
    async def unload(self, name: str) -> Dict[str, Any]:
        """Unload a component."""
        success = await self._loader.unload_component(name)
        return {"success": success, "message": f"Component {name} unloaded" if success else f"Failed to unload component {name}"}
    
    async def enable(self, name: str) -> Dict[str, Any]:
        """Enable a component."""
        success = await self._loader.enable_component(name)
        return {"success": success, "message": f"Component {name} enabled" if success else f"Failed to enable component {name}"}
    
    async def disable(self, name: str) -> Dict[str, Any]:
        """Disable a component."""
        success = await self._loader.disable_component(name)
        return {"success": success, "message": f"Component {name} disabled" if success else f"Failed to disable component {name}"}
    
    async def reload(self, name: str) -> Dict[str, Any]:
        """Reload a component."""
        success = await self._loader.reload_component(name)
        return {"success": success, "message": f"Component {name} reloaded" if success else f"Failed to reload component {name}"}


class PlayerAPI(APIModule):
    """Player management API module."""
    
    def __init__(self, core_api: 'AetheriusCoreAPI'):
        super().__init__(core_api)
        self._manager = get_player_data_manager()
    
    async def initialize(self) -> bool:
        """Initialize player API."""
        return True
    
    async def cleanup(self) -> None:
        """Cleanup player API."""
        pass
    
    async def list(self, online_only: bool = False) -> List[Dict[str, Any]]:
        """Get list of players."""
        try:
            if online_only:
                players_data = self._manager.get_online_players()
            else:
                players_data = self._manager.get_all_players()
            
            players = []
            for name, player_data in players_data.items():
                player_info = {
                    "name": name,
                    "uuid": player_data.uuid,
                    "online": player_data.online,
                    "last_seen": player_data.last_seen,
                    "game_mode": player_data.stats.game_mode if player_data.stats else None,
                    "level": player_data.stats.experience_level if player_data.stats else None,
                    "experience": player_data.stats.experience_total if player_data.stats else None,
                    "health": player_data.stats.health if player_data.stats else None,
                    "food_level": player_data.stats.hunger if player_data.stats else None,
                    "location": asdict(player_data.location) if player_data.location else None,
                    "statistics": player_data.custom_data.get("statistics", {})
                }
                players.append(player_info)
            
            return players
            
        except Exception as e:
            self.logger.error(f"Error listing players: {e}")
            return []
    
    async def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Get specific player data."""
        try:
            player_data = self._manager.get_player_data(name)
            if not player_data:
                return None
            
            return {
                "name": name,
                "uuid": player_data.uuid,
                "online": player_data.online,
                "last_seen": player_data.last_seen,
                "game_mode": player_data.stats.game_mode if player_data.stats else None,
                "level": player_data.stats.experience_level if player_data.stats else None,
                "experience": player_data.stats.experience_total if player_data.stats else None,
                "health": player_data.stats.health if player_data.stats else None,
                "food_level": player_data.stats.hunger if player_data.stats else None,
                "location": asdict(player_data.location) if player_data.location else None,
                "statistics": player_data.custom_data.get("statistics", {})
            }
            
        except Exception as e:
            self.logger.error(f"Error getting player {name}: {e}")
            return None
    
    async def kick(self, name: str, reason: str = "Kicked by admin") -> Dict[str, Any]:
        """Kick a player."""
        try:
            result = await self.core.server.send_command(f"kick {name} {reason}")
            return {
                "success": result["success"],
                "message": f"Player {name} kicked: {reason}" if result["success"] else f"Failed to kick player {name}",
                "player": name,
                "reason": reason,
                "action": "kick"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "player": name, "action": "kick"}
    
    async def ban(self, name: str, reason: str = "Banned by admin") -> Dict[str, Any]:
        """Ban a player."""
        try:
            result = await self.core.server.send_command(f"ban {name} {reason}")
            return {
                "success": result["success"],
                "message": f"Player {name} banned: {reason}" if result["success"] else f"Failed to ban player {name}",
                "player": name,
                "reason": reason,
                "action": "ban"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "player": name, "action": "ban"}
    
    async def pardon(self, name: str) -> Dict[str, Any]:
        """Pardon a banned player."""
        try:
            result = await self.core.server.send_command(f"pardon {name}")
            return {
                "success": result["success"],
                "message": f"Player {name} pardoned" if result["success"] else f"Failed to pardon player {name}",
                "player": name,
                "action": "pardon"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "player": name, "action": "pardon"}
    
    async def op(self, name: str) -> Dict[str, Any]:
        """Give operator privileges to a player."""
        try:
            result = await self.core.server.send_command(f"op {name}")
            return {
                "success": result["success"],
                "message": f"Player {name} given OP" if result["success"] else f"Failed to give OP to player {name}",
                "player": name,
                "action": "op"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "player": name, "action": "op"}
    
    async def deop(self, name: str) -> Dict[str, Any]:
        """Remove operator privileges from a player."""
        try:
            result = await self.core.server.send_command(f"deop {name}")
            return {
                "success": result["success"],
                "message": f"Player {name} OP removed" if result["success"] else f"Failed to remove OP from player {name}",
                "player": name,
                "action": "deop"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "player": name, "action": "deop"}

    async def enable_helper_plugin(self, data_file_path: Optional[str] = None) -> Dict[str, Any]:
        """Enable helper plugin integration."""
        try:
            self._manager.enable_helper_plugin(data_file_path)
            return {"success": True, "message": "Helper plugin enabled"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def disable_helper_plugin(self) -> Dict[str, Any]:
        """Disable helper plugin integration."""
        try:
            self._manager.disable_helper_plugin()
            return {"success": True, "message": "Helper plugin disabled"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class MonitoringAPI(APIModule):
    """System monitoring and performance API module."""
    
    def __init__(self, core_api: 'AetheriusCoreAPI'):
        super().__init__(core_api)
        self._monitoring_task: Optional[asyncio.Task] = None
        self._performance_data: Dict[str, Any] = {}
        self._monitoring_enabled = False
    
    async def initialize(self) -> bool:
        """Initialize monitoring API."""
        return True
    
    async def cleanup(self) -> None:
        """Cleanup monitoring API."""
        await self.stop_performance_monitoring()
    
    async def get_performance_data(self) -> Dict[str, Any]:
        """Get current performance data."""
        try:
            if not self.core.server.is_running:
                return {
                    "server_running": False,
                    "cpu_percent": 0.0,
                    "memory_mb": 0.0,
                    "uptime_seconds": 0.0,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Get basic performance metrics
            metrics = await self.core._server.get_performance_metrics()
            
            # Add system information
            import psutil
            system_metrics = {
                "system_cpu_percent": psutil.cpu_percent(),
                "system_memory_percent": psutil.virtual_memory().percent,
                "system_disk_percent": psutil.disk_usage('/').percent,
                "java_version": self._get_java_version(),
                "max_memory_mb": self._parse_max_memory_mb(self.core.config.server.jvm_args),
            }
            
            metrics.update(system_metrics)
            metrics["timestamp"] = datetime.now().isoformat()
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error getting performance data: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

    def _get_java_version(self) -> str:
        """Get Java version information."""
        try:
            import subprocess
            java_exe = "java" # Assumes java is in PATH
            result = subprocess.run(
                [java_exe, "-version"], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            if result.stderr:
                for line in result.stderr.split('\n'):
                    if 'version' in line.lower():
                        return line.strip()
            return "Unknown"
        except Exception:
            return "Unknown"

    def _parse_max_memory_mb(self, java_args: List[str]) -> Optional[int]:
        """Parse max memory in MB from Java arguments."""
        for arg in java_args:
            if arg.startswith('-Xmx'):
                mem_str = arg[4:].lower()
                try:
                    if mem_str.endswith('g'):
                        return int(mem_str[:-1]) * 1024
                    elif mem_str.endswith('m'):
                        return int(mem_str[:-1])
                except ValueError:
                    return None
        return None
    
    async def start_performance_monitoring(self, interval: float = 10.0) -> bool:
        """Start continuous performance monitoring."""
        if self._monitoring_enabled:
            return True
        
        try:
            self._monitoring_enabled = True
            self._monitoring_task = asyncio.create_task(
                self._monitoring_loop(interval)
            )
            self.logger.info(f"Started performance monitoring with {interval}s interval")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start performance monitoring: {e}")
            self._monitoring_enabled = False
            return False
    
    async def stop_performance_monitoring(self) -> None:
        """Stop performance monitoring."""
        self._monitoring_enabled = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        self.logger.info("Stopped performance monitoring")
    
    async def _monitoring_loop(self, interval: float) -> None:
        """Performance monitoring loop."""
        while self._monitoring_enabled:
            try:
                perf_data = await self.get_performance_data()
                self._performance_data = perf_data
                
                # Broadcast to event system
                await self.core.events.emit("performance_update", perf_data)
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval)
    
    def get_cached_performance_data(self) -> Dict[str, Any]:
        """Get cached performance data."""
        return self._performance_data.copy()
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health information."""
        try:
            performance = await self.get_performance_data()
            plugins = await self.core.plugins.list()
            components = await self.core.components.list()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "server": {
                    "running": self.core.server.is_running,
                    "pid": self.core.server.pid,
                    "performance": performance
                },
                "plugins": {
                    "total": len(plugins),
                    "enabled": len([p for p in plugins if p["enabled"]]),
                    "loaded": len([p for p in plugins if p["loaded"]])
                },
                "components": {
                    "total": len(components),
                    "enabled": len([c for c in components if c["enabled"]]),
                    "loaded": len([c for c in components if c["loaded"]])
                },
                "monitoring": {
                    "enabled": self._monitoring_enabled,
                    "last_update": self._performance_data.get("timestamp")
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system health: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


class EventAPI(APIModule):
    """Event system API module."""
    
    def __init__(self, core_api: 'AetheriusCoreAPI'):
        super().__init__(core_api)
        self._manager = get_event_manager()
    
    async def initialize(self) -> bool:
        """Initialize event API."""
        return True
    
    async def cleanup(self) -> None:
        """Cleanup event API."""
        pass
    
    def on(self, event_type: Type[BaseEvent], callback: Callable) -> None:
        """Register event listener."""
        self._manager.register_listener(event_type, callback)
    
    def off(self, event_type: Type[BaseEvent], callback: Callable) -> None:
        """Remove event listener."""
        # This is a simplified version. A real implementation would need to store the listener object.
        listeners = self._manager.get_listeners(event_type)
        for listener in listeners:
            if listener.callback == callback:
                self._manager.unregister_listener(listener)
                break
    
    async def emit(self, event: BaseEvent) -> None:
        """Emit event."""
        await self._manager.fire_event(event)
    
    def get_listeners(self, event_type: Type[BaseEvent]) -> List[Callable]:
        """Get listeners for event."""
        return [l.callback for l in self._manager.get_listeners(event_type)]
    
    def get_events(self) -> List[str]:
        """Get list of all registered events."""
        return list(self._manager._listeners.keys())


class AetheriusCoreAPI:
    """
    Unified Aetherius Core API
    ==========================
    
    The single point of access for all Aetherius Core functionality.
    Provides a clean, organized interface to all server management,
    plugin/component control, player management, monitoring, and configuration.
    
    Designed to be:
    - Self-contained and independently runnable
    - Comprehensive and feature-complete
    - Elegant and easy to use
    - Extensible and modular
    """
    
    def __init__(self, 
                 auto_initialize: bool = True):
        """
        Initialize the unified Core API.
        
        Args:
            auto_initialize: Whether to auto-initialize modules
        """
        self.logger = logging.getLogger(__name__)
        
        # Core components
        self._server: Optional[ServerController] = None
        self._initialized = False
        self._modules: Dict[str, APIModule] = {}
        
        # Initialize config first
        self.config_manager = get_config_manager()
        self.config = self.config_manager.get_config()
        
        # API modules
        self.server = ServerAPI(self)
        self.plugins = PluginAPI(self)
        self.components = ComponentAPI(self)
        self.players = PlayerAPI(self)
        self.monitoring = MonitoringAPI(self)
        self.events = EventAPI(self)
        
        # Register modules
        self._modules = {
            "server": self.server,
            "plugins": self.plugins,
            "components": self.components,
            "players": self.players,
            "monitoring": self.monitoring,
            "events": self.events
        }
        
        if auto_initialize:
            asyncio.create_task(self.initialize())
    
    async def initialize(self) -> bool:
        """
        Initialize the Core API and all modules.
        
        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True
        
        try:
            self.logger.info("Initializing Aetherius Core API")
            
            # Initialize server if not provided
            if not self._server:
                await self._initialize_server()
            
            # Initialize all modules
            for name, module in self._modules.items():
                try:
                    success = await module.initialize()
                    if success:
                        self.logger.debug(f"Initialized {name} API module")
                    else:
                        self.logger.warning(f"Failed to initialize {name} API module")
                except Exception as e:
                    self.logger.error(f"Error initializing {name} API module: {e}")
            
            self._initialized = True
            self.logger.info("Aetherius Core API initialized successfully")
            
            # Emit initialization event
            await self.events.emit("core_api_initialized", self)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Core API: {e}")
            return False
    
    async def cleanup(self) -> None:
        """Cleanup the Core API and all modules."""
        if not self._initialized:
            return
        
        try:
            self.logger.info("Cleaning up Aetherius Core API")
            
            # Emit cleanup event
            await self.events.emit("core_api_cleanup", self)
            
            # Cleanup all modules
            for name, module in self._modules.items():
                try:
                    await module.cleanup()
                    self.logger.debug(f"Cleaned up {name} API module")
                except Exception as e:
                    self.logger.error(f"Error cleaning up {name} API module: {e}")
            
            self._initialized = False
            self.logger.info("Aetherius Core API cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error during Core API cleanup: {e}")
    
    async def _initialize_server(self) -> None:
        """Initialize server instance."""
        if not self._server:
            self._server = ServerController(self.config.server)
            self.logger.debug("Created new ServerController instance")
    
    @asynccontextmanager
    async def managed_context(self):
        """
        Context manager for automatic initialization and cleanup.
        
        Usage:
            async with core_api.managed_context():
                # Use API
                await core_api.server.start()
                # Automatic cleanup when exiting
        """
        try:
            await self.initialize()
            yield self
        finally:
            await self.cleanup()
    
    def is_initialized(self) -> bool:
        """Check if API is initialized."""
        return self._initialized
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all API modules.
        
        Returns:
            Complete status information
        """
        try:
            status = {
                "api_initialized": self._initialized,
                "timestamp": datetime.now().isoformat(),
                "modules": {}
            }
            
            # Get status from each module
            status["modules"]["server"] = await self.server.get_status()
            status["modules"]["plugins"] = {
                "total": len(await self.plugins.list()),
                "enabled": len([p for p in await self.plugins.list() if p["enabled"]])
            }
            status["modules"]["components"] = {
                "total": len(await self.components.list()),
                "enabled": len([c for c in await self.components.list() if c["enabled"]])
            }
            status["modules"]["players"] = {
                "total": len(await self.players.list()),
                "online": len(await self.players.list(online_only=True))
            }
            status["modules"]["monitoring"] = {
                "enabled": self.monitoring._monitoring_enabled,
                "performance": self.monitoring.get_cached_performance_data()
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting API status: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def __repr__(self) -> str:
        """String representation of the API."""
        status = "initialized" if self._initialized else "not initialized"
        server_status = self.server.state.name if self._server else "STOPPED"
        return f"AetheriusCoreAPI(status={status}, server={server_status})"


# Convenience factory function
async def create_core_api(auto_start_monitoring: bool = True) -> AetheriusCoreAPI:
    """
    Factory function to create and initialize Core API.
    
    Args:
        auto_start_monitoring: Whether to start performance monitoring
        
    Returns:
        Initialized Core API instance
    """
    api = AetheriusCoreAPI(auto_initialize=True)
    await api.initialize()
    
    if auto_start_monitoring:
        await api.monitoring.start_performance_monitoring()
    
    return api


# Global API instance for singleton access
_global_api: Optional[AetheriusCoreAPI] = None


async def get_core_api(initialize_if_needed: bool = True) -> AetheriusCoreAPI:
    """
    Get global Core API instance.
    
    Args:
        initialize_if_needed: Whether to initialize if not already done
        
    Returns:
        Global Core API instance
    """
    global _global_api
    
    if _global_api is None:
        _global_api = AetheriusCoreAPI(auto_initialize=False)
        
    if initialize_if_needed and not _global_api.is_initialized():
        await _global_api.initialize()
    
    return _global_api


def set_global_api(api: AetheriusCoreAPI) -> None:
    """Set the global API instance."""
    global _global_api
    _global_api = api
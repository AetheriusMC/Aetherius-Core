"""Console interface singleton manager to prevent duplicate initialization."""

import asyncio
import logging
import threading
from typing import Optional, Dict, Any
from weakref import WeakValueDictionary

from .console_interface import EnhancedConsoleInterface, get_default_rcon_config

logger = logging.getLogger(__name__)


class ConsoleManager:
    """Singleton manager for console interfaces to prevent duplicate initialization."""
    
    _instance: Optional['ConsoleManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the console manager."""
        if self._initialized:
            return
            
        self._interfaces: WeakValueDictionary[str, EnhancedConsoleInterface] = WeakValueDictionary()
        self._initialization_locks: Dict[str, threading.Lock] = {}
        self._initialized = True
        logger.info("Console manager initialized")
    
    def _get_cache_key(self, server_wrapper) -> str:
        """Get a stable cache key for the server wrapper."""
        # First try to use server PID if available
        if hasattr(server_wrapper, 'get_pid') and server_wrapper.get_pid():
            return f"pid_{server_wrapper.get_pid()}"
        elif hasattr(server_wrapper, 'process') and server_wrapper.process and server_wrapper.process.pid:
            return f"pid_{server_wrapper.process.pid}"
        # Fall back to server state if available
        elif hasattr(server_wrapper, 'server_state'):
            try:
                state_info = server_wrapper.server_state.get_server_info()
                if state_info and state_info.get('pid'):
                    return f"pid_{state_info['pid']}"
            except:
                pass
        
        # If no stable key found, use wrapper ID but log warning
        cache_key = f"wrapper_{id(server_wrapper)}"
        logger.warning(f"Using unstable cache key: {cache_key}")
        return cache_key
    
    async def get_console_interface(self, 
                                  server_wrapper, 
                                  config: Optional[Dict[str, Any]] = None) -> Optional[EnhancedConsoleInterface]:
        """Get or create a console interface for the given server wrapper."""
        
        cache_key = self._get_cache_key(server_wrapper)
        
        # Check if interface already exists
        if cache_key in self._interfaces:
            interface = self._interfaces[cache_key]
            if interface and (interface.stdin_connection.is_connected() or 
                            interface.rcon_connection.is_connected()):
                logger.debug(f"Reusing existing console interface for {cache_key}")
                return interface
            else:
                # Clean up dead interface
                logger.debug(f"Cleaning up dead interface for {cache_key}")
                if cache_key in self._interfaces:
                    del self._interfaces[cache_key]
                if cache_key in self._initialization_locks:
                    del self._initialization_locks[cache_key]
        
        # Create lock for this key if it doesn't exist
        if cache_key not in self._initialization_locks:
            self._initialization_locks[cache_key] = threading.Lock()
        
        # Ensure only one thread initializes the interface
        with self._initialization_locks[cache_key]:
            # Double-check after acquiring lock
            if cache_key in self._interfaces:
                interface = self._interfaces[cache_key]
                if interface and (interface.stdin_connection.is_connected() or 
                                interface.rcon_connection.is_connected()):
                    return interface
            
            try:
                logger.info(f"Creating new console interface for {cache_key}")
                
                # Merge with default config
                rcon_config = get_default_rcon_config()
                if config:
                    rcon_config.update(config)
                
                # Create new interface
                interface = EnhancedConsoleInterface(server_wrapper, rcon_config)
                
                # Initialize the interface
                if await interface.initialize():
                    self._interfaces[cache_key] = interface
                    logger.info(f"Console interface ready for {cache_key} (persistent connection)")
                    return interface
                else:
                    logger.error(f"Failed to initialize console interface for {cache_key}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error creating console interface for {cache_key}: {e}")
                return None
    
    async def close_interface(self, server_wrapper) -> bool:
        """Close and remove console interface for the given server wrapper."""
        cache_key = self._get_cache_key(server_wrapper)
        
        if cache_key in self._interfaces:
            try:
                interface = self._interfaces[cache_key]
                await interface.close()
                del self._interfaces[cache_key]
                
                if cache_key in self._initialization_locks:
                    del self._initialization_locks[cache_key]
                
                logger.info(f"Console interface closed for {cache_key}")
                return True
                
            except Exception as e:
                logger.error(f"Error closing console interface for {cache_key}: {e}")
                return False
        
        return True
    
    async def close_all_interfaces(self) -> bool:
        """Close all console interfaces."""
        success = True
        
        # Get list of interfaces to avoid modification during iteration
        interfaces_to_close = list(self._interfaces.items())
        
        for cache_key, interface in interfaces_to_close:
            try:
                await interface.close()
                logger.info(f"Closed console interface for {cache_key}")
            except Exception as e:
                logger.error(f"Error closing console interface for {cache_key}: {e}")
                success = False
        
        # Clear all interfaces
        self._interfaces.clear()
        self._initialization_locks.clear()
        
        logger.info("All console interfaces closed")
        return success
    
    def get_interface_stats(self) -> Dict[str, Any]:
        """Get statistics for all managed interfaces."""
        stats = {
            'total_interfaces': len(self._interfaces),
            'active_interfaces': 0,
            'interfaces': {}
        }
        
        for cache_key, interface in self._interfaces.items():
            try:
                interface_stats = interface.get_statistics()
                stats['interfaces'][cache_key] = {
                    'stdin_connected': interface.stdin_connection.is_connected(),
                    'rcon_connected': interface.rcon_connection.is_connected(),
                    'current_connection': interface._current_connection.connection_type if interface._current_connection else None,
                    'statistics': interface_stats
                }
                
                if (interface.stdin_connection.is_connected() or 
                    interface.rcon_connection.is_connected()):
                    stats['active_interfaces'] += 1
                    
            except Exception as e:
                stats['interfaces'][cache_key] = {'error': str(e)}
        
        return stats


# Global console manager instance
_console_manager: Optional[ConsoleManager] = None
_manager_lock = threading.Lock()


def get_console_manager() -> ConsoleManager:
    """Get the global console manager instance."""
    global _console_manager
    
    if _console_manager is None:
        with _manager_lock:
            if _console_manager is None:
                _console_manager = ConsoleManager()
    
    return _console_manager


async def get_managed_console_interface(server_wrapper, 
                                      config: Optional[Dict[str, Any]] = None) -> Optional[EnhancedConsoleInterface]:
    """Get a managed console interface (recommended way to get console interfaces)."""
    manager = get_console_manager()
    return await manager.get_console_interface(server_wrapper, config)


async def close_managed_console_interface(server_wrapper) -> bool:
    """Close a managed console interface."""
    manager = get_console_manager()
    return await manager.close_interface(server_wrapper)


async def close_all_managed_interfaces() -> bool:
    """Close all managed console interfaces."""
    manager = get_console_manager()
    return await manager.close_all_interfaces()


def get_all_interface_stats() -> Dict[str, Any]:
    """Get statistics for all managed console interfaces."""
    manager = get_console_manager()
    return manager.get_interface_stats()
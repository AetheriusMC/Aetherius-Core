"""Enhanced console command interface with stdin/stdout primary control and RCON fallback."""

import asyncio
import logging
import struct
import socket
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Union, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Connection status enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class CommandPriority(Enum):
    """Command execution priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class CommandResult:
    """Command execution result with enhanced metadata."""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    connection_type: str = "stdin"
    command_id: Optional[str] = None
    timestamp: Optional[float] = None


class ConnectionInterface(ABC):
    """Abstract base class for server connection interfaces."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the server."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Close connection to the server."""
        pass
    
    @abstractmethod
    async def send_command(self, command: str, timeout: float = 30.0) -> CommandResult:
        """Send command and return result."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is active."""
        pass
    
    @property
    @abstractmethod
    def connection_type(self) -> str:
        """Get connection type identifier."""
        pass


class StdinConnection(ConnectionInterface):
    """Primary connection interface using stdin/stdout/stderr."""
    
    def __init__(self, server_wrapper):
        """Initialize with server process wrapper."""
        self.server_wrapper = server_wrapper
        self._status = ConnectionStatus.DISCONNECTED
        
    async def connect(self) -> bool:
        """Check if stdin connection is available."""
        if self.server_wrapper.is_alive:
            self._status = ConnectionStatus.CONNECTED
            logger.info("Stdin connection established")
            return True
        else:
            self._status = ConnectionStatus.ERROR
            logger.error("Server process not running - stdin unavailable")
            return False
    
    async def disconnect(self) -> bool:
        """Stdin connection doesn't need explicit disconnection."""
        self._status = ConnectionStatus.DISCONNECTED
        return True
    
    async def send_command(self, command: str, timeout: float = 30.0) -> CommandResult:
        """Send command via stdin with enhanced result tracking."""
        start_time = asyncio.get_event_loop().time()
        
        if not self.is_connected():
            return CommandResult(
                success=False,
                error="Stdin connection not available",
                connection_type=self.connection_type,
                execution_time=0.0
            )
        
        try:
            # Use command queue for reliable execution with output capture
            success = await self.server_wrapper.send_command_via_queue(command, timeout)
            execution_time = asyncio.get_event_loop().time() - start_time
            
            if success:
                # Try to get captured output
                output = self._get_recent_output(command)
                return CommandResult(
                    success=True,
                    output=output,
                    connection_type=self.connection_type,
                    execution_time=execution_time,
                    timestamp=start_time
                )
            else:
                return CommandResult(
                    success=False,
                    error="Command execution failed",
                    connection_type=self.connection_type,
                    execution_time=execution_time
                )
                
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"Error sending command via stdin: {e}")
            return CommandResult(
                success=False,
                error=str(e),
                connection_type=self.connection_type,
                execution_time=execution_time
            )
    
    def is_connected(self) -> bool:
        """Check if stdin connection is active."""
        return self._status == ConnectionStatus.CONNECTED and self.server_wrapper.is_alive
    
    @property
    def connection_type(self) -> str:
        """Get connection type identifier."""
        return "stdin"
    
    def _get_recent_output(self, command: str) -> Optional[str]:
        """Attempt to get recent output related to the command."""
        try:
            if hasattr(self.server_wrapper, 'output_capture'):
                # This would need to be implemented based on the output capture system
                return self.server_wrapper.output_capture.get_recent_output()
        except Exception as e:
            logger.debug(f"Could not get recent output: {e}")
        return None


class RconConnection(ConnectionInterface):
    """Backup connection interface using RCON protocol."""
    
    def __init__(self, host: str = "localhost", port: int = 25575, password: str = ""):
        """Initialize RCON connection parameters."""
        self.host = host
        self.port = port
        self.password = password
        self._socket: Optional[socket.socket] = None
        self._status = ConnectionStatus.DISCONNECTED
        self._request_id = 1
    
    async def connect(self) -> bool:
        """Establish RCON connection."""
        try:
            self._status = ConnectionStatus.CONNECTING
            
            # Create socket connection
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(10.0)
            
            await asyncio.get_event_loop().run_in_executor(
                None, self._socket.connect, (self.host, self.port)
            )
            
            # Send authentication packet
            auth_success = await self._authenticate()
            
            if auth_success:
                self._status = ConnectionStatus.CONNECTED
                logger.info(f"RCON connection established to {self.host}:{self.port}")
                return True
            else:
                self._status = ConnectionStatus.ERROR
                await self.disconnect()
                return False
                
        except Exception as e:
            logger.error(f"Failed to establish RCON connection: {e}")
            self._status = ConnectionStatus.ERROR
            await self.disconnect()
            return False
    
    async def disconnect(self) -> bool:
        """Close RCON connection."""
        try:
            if self._socket:
                self._socket.close()
                self._socket = None
            self._status = ConnectionStatus.DISCONNECTED
            logger.info("RCON connection closed")
            return True
        except Exception as e:
            logger.error(f"Error closing RCON connection: {e}")
            return False
    
    async def send_command(self, command: str, timeout: float = 30.0) -> CommandResult:
        """Send command via RCON protocol."""
        start_time = asyncio.get_event_loop().time()
        
        if not self.is_connected():
            return CommandResult(
                success=False,
                error="RCON connection not available",
                connection_type=self.connection_type,
                execution_time=0.0
            )
        
        try:
            # Send command packet
            response = await self._send_packet(2, command, timeout)  # Type 2 = SERVERDATA_EXECCOMMAND
            execution_time = asyncio.get_event_loop().time() - start_time
            
            if response is not None:
                return CommandResult(
                    success=True,
                    output=response,
                    connection_type=self.connection_type,
                    execution_time=execution_time,
                    timestamp=start_time
                )
            else:
                return CommandResult(
                    success=False,
                    error="No response received",
                    connection_type=self.connection_type,
                    execution_time=execution_time
                )
                
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"Error sending RCON command: {e}")
            return CommandResult(
                success=False,
                error=str(e),
                connection_type=self.connection_type,
                execution_time=execution_time
            )
    
    def is_connected(self) -> bool:
        """Check if RCON connection is active."""
        return (self._status == ConnectionStatus.CONNECTED and 
                self._socket is not None)
    
    @property
    def connection_type(self) -> str:
        """Get connection type identifier."""
        return "rcon"
    
    async def _authenticate(self) -> bool:
        """Authenticate with RCON server."""
        try:
            response = await self._send_packet(3, self.password)  # Type 3 = SERVERDATA_AUTH
            return response is not None
        except Exception as e:
            logger.error(f"RCON authentication failed: {e}")
            return False
    
    async def _send_packet(self, packet_type: int, data: str, timeout: float = 10.0) -> Optional[str]:
        """Send RCON packet and receive response."""
        if not self._socket:
            return None
        
        try:
            # Build packet
            request_id = self._request_id
            self._request_id += 1
            
            # Pack packet data
            data_bytes = data.encode('utf-8')
            packet_data = struct.pack('<ii', request_id, packet_type) + data_bytes + b'\x00\x00'
            packet_length = len(packet_data)
            packet = struct.pack('<i', packet_length) + packet_data
            
            # Send packet
            await asyncio.get_event_loop().run_in_executor(
                None, self._socket.send, packet
            )
            
            # Receive response
            response_data = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self._receive_response
                ),
                timeout=timeout
            )
            
            return response_data
            
        except asyncio.TimeoutError:
            logger.error("RCON command timeout")
            return None
        except Exception as e:
            logger.error(f"RCON packet send/receive error: {e}")
            return None
    
    def _receive_response(self) -> Optional[str]:
        """Receive RCON response packet."""
        try:
            # Read packet length
            length_data = self._socket.recv(4)
            if len(length_data) != 4:
                return None
            
            packet_length = struct.unpack('<i', length_data)[0]
            
            # Read packet data
            packet_data = b''
            while len(packet_data) < packet_length:
                chunk = self._socket.recv(packet_length - len(packet_data))
                if not chunk:
                    return None
                packet_data += chunk
            
            # Unpack packet
            if len(packet_data) < 8:
                return None
            
            request_id, response_type = struct.unpack('<ii', packet_data[:8])
            response_data = packet_data[8:-2].decode('utf-8', errors='replace')
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error receiving RCON response: {e}")
            return None


class EnhancedConsoleInterface:
    """Enhanced console interface with multiple connection backends and intelligent failover."""
    
    def __init__(self, server_wrapper, rcon_config: Optional[Dict[str, Any]] = None):
        """Initialize console interface with primary and backup connections."""
        self.server_wrapper = server_wrapper
        
        # Primary connection (stdin)
        self.stdin_connection = StdinConnection(server_wrapper)
        
        # Backup connection (RCON)
        rcon_config = rcon_config or {}
        self.rcon_connection = RconConnection(
            host=rcon_config.get('host', 'localhost'),
            port=rcon_config.get('port', 25575),
            password=rcon_config.get('password', 'password123')
        )
        
        # Connection management
        self._primary_connection = self.stdin_connection
        self._backup_connection = self.rcon_connection
        self._current_connection: Optional[ConnectionInterface] = None
        
        # Command queue for priority management
        self._command_queue: List[Tuple[str, CommandPriority, float, Optional[Callable]]] = []
        self._queue_lock = asyncio.Lock()
        
        # Statistics
        self._stats = {
            'commands_sent': 0,
            'stdin_commands': 0,
            'rcon_commands': 0,
            'failed_commands': 0,
            'avg_response_time': 0.0,
            'connection_switches': 0
        }
    
    async def initialize(self) -> bool:
        """Initialize and establish connections."""
        logger.info("Initializing enhanced console interface")
        
        # Try to establish primary connection first
        if await self._primary_connection.connect():
            self._current_connection = self._primary_connection
            logger.info("Primary connection (stdin) established")
            return True
        
        # Fall back to backup connection
        logger.warning("Primary connection failed, trying backup connection")
        if await self._backup_connection.connect():
            self._current_connection = self._backup_connection
            self._stats['connection_switches'] += 1
            logger.info("Backup connection (RCON) established")
            return True
        
        logger.error("Failed to establish any connection")
        return False
    
    async def send_command(self, 
                          command: str, 
                          priority: CommandPriority = CommandPriority.NORMAL,
                          timeout: float = 30.0,
                          retry_on_failure: bool = True) -> CommandResult:
        """Send command with intelligent connection management and retry logic."""
        
        start_time = asyncio.get_event_loop().time()
        
        # Validate current connection
        if not self._current_connection or not self._current_connection.is_connected():
            if not await self._ensure_connection():
                return CommandResult(
                    success=False,
                    error="No available connections",
                    execution_time=asyncio.get_event_loop().time() - start_time
                )
        
        # Execute command
        result = await self._current_connection.send_command(command, timeout)
        
        # Handle connection failure and retry logic
        if not result.success and retry_on_failure:
            logger.warning(f"Command failed on {self._current_connection.connection_type}, attempting failover")
            
            # Try alternative connection
            alternative_conn = (self._backup_connection 
                              if self._current_connection == self._primary_connection 
                              else self._primary_connection)
            
            if await alternative_conn.connect():
                self._current_connection = alternative_conn
                self._stats['connection_switches'] += 1
                logger.info(f"Switched to {alternative_conn.connection_type} connection")
                
                # Retry command
                result = await self._current_connection.send_command(command, timeout)
        
        # Update statistics
        self._update_stats(result)
        
        # Don't close connection after command execution to maintain persistence
        logger.debug(f"Command executed via {self._current_connection.connection_type}, keeping connection alive")
        
        return result
    
    async def send_command_batch(self, 
                                commands: List[Tuple[str, CommandPriority]], 
                                timeout: float = 30.0) -> List[CommandResult]:
        """Send multiple commands in batch with priority ordering."""
        
        # Sort commands by priority
        sorted_commands = sorted(commands, key=lambda x: x[1].value, reverse=True)
        
        results = []
        for command, priority in sorted_commands:
            result = await self.send_command(command, priority, timeout)
            results.append(result)
            
            # Small delay between commands to prevent overwhelming
            await asyncio.sleep(0.1)
        
        return results
    
    async def execute_script(self, 
                           commands: List[str], 
                           stop_on_error: bool = True,
                           timeout_per_command: float = 30.0) -> Dict[str, Any]:
        """Execute a sequence of commands as a script."""
        
        results = []
        total_start_time = asyncio.get_event_loop().time()
        
        for i, command in enumerate(commands):
            logger.info(f"Executing script command {i+1}/{len(commands)}: {command}")
            
            result = await self.send_command(command, timeout=timeout_per_command)
            results.append(result)
            
            if not result.success and stop_on_error:
                logger.error(f"Script execution stopped at command {i+1} due to error: {result.error}")
                break
        
        total_execution_time = asyncio.get_event_loop().time() - total_start_time
        successful_commands = sum(1 for r in results if r.success)
        
        return {
            'total_commands': len(commands),
            'executed_commands': len(results),
            'successful_commands': successful_commands,
            'failed_commands': len(results) - successful_commands,
            'total_execution_time': total_execution_time,
            'results': results,
            'success': successful_commands == len(results)
        }
    
    async def get_server_info(self) -> Dict[str, Any]:
        """Get comprehensive server information using multiple commands."""
        
        info_commands = [
            ("list", "player_list"),
            ("tps", "performance"),
            ("version", "server_version"),
            ("plugins", "plugin_list")
        ]
        
        server_info = {}
        
        for command, info_key in info_commands:
            try:
                result = await self.send_command(command, timeout=10.0)
                if result.success:
                    server_info[info_key] = result.output
                else:
                    server_info[info_key] = f"Error: {result.error}"
            except Exception as e:
                server_info[info_key] = f"Exception: {str(e)}"
        
        # Add connection information
        server_info['connection_info'] = {
            'current_connection': self._current_connection.connection_type if self._current_connection else None,
            'stdin_available': self.stdin_connection.is_connected(),
            'rcon_available': self.rcon_connection.is_connected(),
            'statistics': self._stats.copy()
        }
        
        return server_info
    
    async def close(self) -> bool:
        """Close all connections and cleanup resources."""
        logger.info("Closing enhanced console interface")
        
        success = True
        
        try:
            if self.stdin_connection.is_connected():
                await self.stdin_connection.disconnect()
        except Exception as e:
            logger.error(f"Error closing stdin connection: {e}")
            success = False
        
        try:
            if self.rcon_connection.is_connected():
                await self.rcon_connection.disconnect()
        except Exception as e:
            logger.error(f"Error closing RCON connection: {e}")
            success = False
        
        self._current_connection = None
        return success
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get interface usage statistics."""
        return self._stats.copy()
    
    async def _ensure_connection(self) -> bool:
        """Ensure we have an active connection, attempting both if necessary."""
        
        # Try primary connection first
        if await self._primary_connection.connect():
            self._current_connection = self._primary_connection
            return True
        
        # Try backup connection
        if await self._backup_connection.connect():
            self._current_connection = self._backup_connection
            self._stats['connection_switches'] += 1
            return True
        
        return False
    
    def _update_stats(self, result: CommandResult) -> None:
        """Update interface statistics based on command result."""
        self._stats['commands_sent'] += 1
        
        if result.success:
            if result.connection_type == 'stdin':
                self._stats['stdin_commands'] += 1
            elif result.connection_type == 'rcon':
                self._stats['rcon_commands'] += 1
            
            # Update average response time
            current_avg = self._stats['avg_response_time']
            total_commands = self._stats['commands_sent']
            self._stats['avg_response_time'] = (
                (current_avg * (total_commands - 1) + result.execution_time) / total_commands
            )
        else:
            self._stats['failed_commands'] += 1


# Convenience functions for easy integration
async def create_console_interface(server_wrapper, config: Optional[Dict[str, Any]] = None) -> EnhancedConsoleInterface:
    """Create and initialize an enhanced console interface."""
    
    interface = EnhancedConsoleInterface(server_wrapper, config)
    
    if await interface.initialize():
        logger.info("Enhanced console interface ready")
        return interface
    else:
        logger.error("Failed to initialize console interface")
        raise RuntimeError("Could not establish any server connections")


def get_default_rcon_config() -> Dict[str, Any]:
    """Get default RCON configuration."""
    return {
        'host': 'localhost',
        'port': 25575,
        'password': 'password123'
    }
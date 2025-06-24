"""Server process wrapper for managing Minecraft server instances."""

import asyncio
import logging
import signal
import time
from pathlib import Path
from typing import Optional, Callable, Any, Dict

import psutil

from .config import ServerConfig
from .log_parser import LogParser
from .event_manager import get_event_manager, fire_event
from .events import (
    ServerStartingEvent, ServerStartedEvent, ServerStoppingEvent, 
    ServerStoppedEvent, ServerCrashEvent
)
from .server_state import get_server_state
from .command_queue import get_command_queue
from .output_capture import get_output_capture


logger = logging.getLogger(__name__)


class ServerProcessWrapper:
    """
    Manages a Minecraft server process with async I/O handling.
    
    This class provides the core functionality for starting, stopping,
    and communicating with a Minecraft server process.
    """
    
    def __init__(self, config: ServerConfig, log_parser: Optional[LogParser] = None):
        """Initialize the server process wrapper."""
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self._stdout_handler: Optional[Callable[[str], None]] = None
        self._stderr_handler: Optional[Callable[[str], None]] = None
        self._running = False
        self._restart_requested = False
        self._start_time: Optional[float] = None
        self._psutil_process: Optional[psutil.Process] = None
        
        # Initialize log parser, state management, command queue, and output capture
        self.log_parser = log_parser or LogParser()
        self.event_manager = get_event_manager()
        self.server_state = get_server_state()
        self.command_queue = get_command_queue()
        self.output_capture = get_output_capture()
    
    @property
    def is_alive(self) -> bool:
        """Check if the server process is currently running."""
        # First check our local process
        if self.process is not None and self.process.returncode is None:
            return True
        
        # If no local process, check the global state
        return self.server_state.is_server_running()
    
    @property
    def is_running(self) -> bool:
        """Check if the wrapper is in running state."""
        return self._running
    
    def set_stdout_handler(self, handler: Callable[[str], None]) -> None:
        """Set a handler function for stdout lines."""
        self._stdout_handler = handler
    
    def set_stderr_handler(self, handler: Callable[[str], None]) -> None:
        """Set a handler function for stderr lines."""
        self._stderr_handler = handler
    
    async def start(self) -> bool:
        """
        Start the Minecraft server process.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.is_alive:
            logger.warning("Server process is already running")
            return False
        
        # Validate server JAR exists
        jar_path = Path(self.config.jar_path)
        if not jar_path.exists():
            logger.error(f"Server JAR not found: {jar_path}")
            return False
        
        # Prepare command
        cmd = [
            self.config.java_executable,
            *self.config.java_args,
            "-jar",
            str(jar_path.resolve()),
            *self.config.server_args
        ]
        
        # Prepare working directory
        work_dir = Path(self.config.working_directory)
        work_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info(f"Starting server with command: {' '.join(cmd)}")
            logger.info(f"Working directory: {work_dir.resolve()}")
            
            # Fire server starting event
            starting_event = ServerStartingEvent(
                command=cmd,
                working_directory=str(work_dir.resolve())
            )
            await fire_event(starting_event)
            
            if starting_event.is_cancelled():
                logger.info("Server start was cancelled by event handler")
                return False
            
            self._start_time = asyncio.get_event_loop().time()
            
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir
            )
            
            self._running = True
            
            # Initialize psutil process for performance monitoring
            try:
                self._psutil_process = psutil.Process(self.process.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f"Could not initialize psutil process monitoring: {e}")
                self._psutil_process = None
            
            # Start I/O handling tasks
            asyncio.create_task(self._handle_stdout())
            asyncio.create_task(self._handle_stderr())
            asyncio.create_task(self._monitor_process())
            asyncio.create_task(self._handle_command_queue())
            
            # Save server state
            self.server_state.set_server_started(
                pid=self.process.pid,
                jar_path=str(jar_path.resolve()),
                working_directory=str(work_dir.resolve())
            )
            
            logger.info(f"Server process started with PID: {self.process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server process: {e}")
            self.process = None
            self._running = False
            return False
    
    async def stop(self, force: bool = False, timeout: float = 30.0) -> bool:
        """
        Stop the Minecraft server process.
        
        Args:
            force: If True, force kill the process immediately
            timeout: Seconds to wait for graceful shutdown before force kill
            
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        if not self.is_alive:
            logger.warning("Server process is not running")
            return True
        
        self._running = False
        
        # Fire server stopping event
        stopping_event = ServerStoppingEvent(
            reason="User requested" if not force else "Force stop",
            force=force
        )
        await fire_event(stopping_event)
        
        try:
            if force:
                logger.info("Force killing server process")
                self.process.kill()
            else:
                logger.info("Sending stop command to server")
                await self.send_command("stop")
                
                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=timeout)
                    logger.info("Server stopped gracefully")
                except asyncio.TimeoutError:
                    logger.warning(f"Server didn't stop within {timeout}s, force killing")
                    self.process.kill()
                    await self.process.wait()
            
            # Calculate uptime
            uptime = 0.0
            if self._start_time:
                uptime = asyncio.get_event_loop().time() - self._start_time
            
            # Fire server stopped event
            stopped_event = ServerStoppedEvent(
                exit_code=self.process.returncode or 0,
                uptime=uptime
            )
            await fire_event(stopped_event)
            
            # Clear server state
            self.server_state.set_server_stopped()
            
            self.process = None
            self._psutil_process = None
            logger.info("Server process stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping server process: {e}")
            return False
    
    async def restart(self) -> bool:
        """
        Restart the server process.
        
        Returns:
            bool: True if restarted successfully, False otherwise
        """
        logger.info("Restarting server process")
        self._restart_requested = True
        
        if self.is_alive:
            await self.stop()
        
        # Wait a bit before restarting
        await asyncio.sleep(self.config.restart_delay)
        
        return await self.start()
    
    async def send_command(self, command: str) -> bool:
        """
        Send a command to the server via stdin.
        
        Args:
            command: The command to send
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.is_alive or self.process.stdin is None:
            logger.error("Cannot send command: server process not running or stdin not available")
            return False
        
        try:
            command_bytes = f"{command.strip()}\n".encode("utf-8")
            self.process.stdin.write(command_bytes)
            await self.process.stdin.drain()
            logger.debug(f"Sent command: {command}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending command '{command}': {e}")
            return False
    
    async def _handle_stdout(self) -> None:
        """Handle stdout from the server process."""
        if self.process is None or self.process.stdout is None:
            return
        
        try:
            while self._running and not self.process.stdout.at_eof():
                line_bytes = await self.process.stdout.readline()
                if not line_bytes:
                    break
                
                line = line_bytes.decode("utf-8", errors="replace").rstrip()
                if line:
                    # Process line for output capture first
                    try:
                        self.output_capture.process_line(line)
                    except Exception as e:
                        logger.error(f"Error processing line for output capture: {e}")
                    
                    # Parse line and fire events
                    try:
                        events = self.log_parser.parse_line(line)
                        for event in events:
                            await fire_event(event)
                            
                            # Check for server started event
                            if isinstance(event, ServerStartedEvent):
                                if self._start_time:
                                    event.startup_time = asyncio.get_event_loop().time() - self._start_time
                                if self.process:
                                    event.pid = self.process.pid
                                
                    except Exception as e:
                        logger.error(f"Error parsing log line: {e}")
                    
                    # Call legacy stdout handler if set
                    if self._stdout_handler:
                        try:
                            self._stdout_handler(line)
                        except Exception as e:
                            logger.error(f"Error in stdout handler: {e}")
                        
        except Exception as e:
            logger.error(f"Error handling stdout: {e}")
    
    async def _handle_stderr(self) -> None:
        """Handle stderr from the server process."""
        if self.process is None or self.process.stderr is None:
            return
        
        try:
            while self._running and not self.process.stderr.at_eof():
                line_bytes = await self.process.stderr.readline()
                if not line_bytes:
                    break
                
                line = line_bytes.decode("utf-8", errors="replace").rstrip()
                if line and self._stderr_handler:
                    try:
                        self._stderr_handler(line)
                    except Exception as e:
                        logger.error(f"Error in stderr handler: {e}")
                        
        except Exception as e:
            logger.error(f"Error handling stderr: {e}")
    
    async def _monitor_process(self) -> None:
        """Monitor the server process and handle crashes."""
        if self.process is None:
            return
        
        try:
            return_code = await self.process.wait()
            logger.info(f"Server process exited with code: {return_code}")
            
            # Check if this was an unexpected crash
            if self._running and not self._restart_requested:
                logger.warning("Server process crashed unexpectedly")
                
                # Fire crash event
                crash_event = ServerCrashEvent(
                    exit_code=return_code,
                    error_output="Server process exited unexpectedly",
                    will_restart=self.config.auto_restart
                )
                await fire_event(crash_event)
                
                if self.config.auto_restart and not crash_event.is_cancelled():
                    logger.info("Auto-restart is enabled, restarting server...")
                    await asyncio.sleep(self.config.restart_delay)
                    await self.start()
            
            self._restart_requested = False
            
        except Exception as e:
            logger.error(f"Error monitoring server process: {e}")
        finally:
            if self._running:
                self._running = False
    
    async def _handle_command_queue(self) -> None:
        """Handle commands from the command queue."""
        logger.info("Command queue handler started")
        try:
            while self._running:
                try:
                    # Process pending commands
                    pending_commands = self.command_queue.get_pending_commands()
                    
                    if pending_commands:
                        logger.info(f"Processing {len(pending_commands)} pending commands")
                    
                    for command_data in pending_commands:
                        command_id = command_data['id']
                        command = command_data['command']
                        
                        try:
                            logger.info(f"Executing queued command: {command}")
                            
                            # Start output capture for this command
                            self.output_capture.start_capture(command_id, command)
                            
                            # Execute the command
                            success = await self.send_command(command)
                            
                            # Wait a bit for output to be captured
                            await asyncio.sleep(0.5)
                            
                            # Finish capture and get output
                            captured_output = self.output_capture.finish_capture(command_id)
                            
                            # Mark command as completed with output
                            self.command_queue.mark_command_completed(
                                command_id, 
                                success,
                                output=captured_output
                            )
                            
                            if success:
                                logger.info(f"Successfully executed queued command: {command}")
                                if captured_output:
                                    logger.debug(f"Command output: {captured_output}")
                            else:
                                logger.warning(f"Failed to execute queued command: {command}")
                                
                        except Exception as e:
                            logger.error(f"Error executing queued command {command}: {e}")
                            # Ensure capture is finished even on error
                            self.output_capture.finish_capture(command_id)
                            self.command_queue.mark_command_completed(command_id, False, str(e))
                    
                    # Clean up old files periodically
                    self.command_queue.cleanup_old_files()
                    
                    # Wait before next check
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error in command queue processing loop: {e}")
                    await asyncio.sleep(1.0)  # Wait longer on error
                
        except Exception as e:
            logger.error(f"Fatal error in command queue handler: {e}")
        finally:
            logger.info("Command queue handler stopped")
    
    async def send_command_via_queue(self, command: str, timeout: float = 30.0) -> bool:
        """
        Send a command via the command queue (for cross-process communication).
        
        Args:
            command: The command to send
            timeout: Timeout in seconds
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            command_id = self.command_queue.add_command(command, timeout)
            result = await self.command_queue.wait_for_completion(command_id, timeout)
            
            if result['status'] == 'completed':
                return result['success']
            else:
                logger.error(f"Command execution failed: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending command via queue: {e}")
            return False
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get detailed performance metrics for the server process.
        
        Returns:
            Dict containing CPU usage, memory usage, and other performance data
        """
        if not self.is_alive or self._psutil_process is None:
            return {
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "memory_percent": 0.0,
                "threads": 0,
                "open_files": 0,
                "connections": 0,
                "status": "not_running"
            }
        
        try:
            # Refresh process info
            if not self._psutil_process.is_running():
                return {
                    "cpu_percent": 0.0,
                    "memory_mb": 0.0,
                    "memory_percent": 0.0,
                    "threads": 0,
                    "open_files": 0,
                    "connections": 0,
                    "status": "not_running"
                }
            
            # Get CPU usage (this call may block briefly)
            cpu_percent = self._psutil_process.cpu_percent(interval=0.1)
            
            # Get memory info
            memory_info = self._psutil_process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024  # Convert bytes to MB
            memory_percent = self._psutil_process.memory_percent()
            
            # Get thread count
            try:
                threads = self._psutil_process.num_threads()
            except psutil.AccessDenied:
                threads = 0
            
            # Get open files count
            try:
                open_files = len(self._psutil_process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                open_files = 0
            
            # Get network connections count
            try:
                connections = len(self._psutil_process.connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                connections = 0
            
            # Get uptime
            uptime = 0.0
            if self._start_time:
                uptime = time.time() - self._start_time
            
            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(memory_mb, 2),
                "memory_percent": round(memory_percent, 2),
                "threads": threads,
                "open_files": open_files,
                "connections": connections,
                "uptime_seconds": round(uptime, 1),
                "status": "running",
                "pid": self._psutil_process.pid
            }
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.warning(f"Error getting performance metrics: {e}")
            return {
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "memory_percent": 0.0,
                "threads": 0,
                "open_files": 0,
                "connections": 0,
                "status": "error",
                "error": str(e)
            }
    
    def get_pid(self) -> Optional[int]:
        """
        Get the process ID of the server.
        
        Returns:
            Process ID if running, None otherwise
        """
        if self.process:
            return self.process.pid
        return None
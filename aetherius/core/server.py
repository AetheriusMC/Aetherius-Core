"""
Server process controller for managing Minecraft server instances with a robust state machine.
"""

import asyncio
import logging
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import psutil

from .config_models import ServerConfig
from .event_manager import fire_event, get_event_manager
from .events_base import (
    ServerCrashEvent,
    ServerLogEvent,
    ServerStartedEvent,
    ServerStateChangedEvent,
    ServerStoppedEvent,
)

logger = logging.getLogger(__name__)


class ServerState(Enum):
    """Represents the lifecycle state of the server."""

    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    CRASHED = auto()


class ServerController:
    """
    Manages a Minecraft server process using a robust asynchronous state machine.
    This class handles starting, stopping, I/O, and health monitoring.
    """

    def __init__(self, config: ServerConfig):
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self._state: ServerState = ServerState.STOPPED
        self._tasks: list[asyncio.Task] = []
        self._psutil_process: psutil.Process | None = None
        self.event_manager = get_event_manager()

    @property
    def state(self) -> ServerState:
        """Get the current state of the server."""
        return self._state

    def _change_state(self, new_state: ServerState):
        """Atomically change the server state and fire an event."""
        if self._state == new_state:
            return

        old_state = self._state
        self._state = new_state
        logger.info(f"Server state changed from {old_state.name} to {new_state.name}")
        asyncio.create_task(
            fire_event(
                ServerStateChangedEvent(old_state=old_state, new_state=new_state)
            )
        )

    async def start(self) -> bool:
        """Start the Minecraft server process."""
        if self.state not in [ServerState.STOPPED, ServerState.CRASHED]:
            logger.warning(f"Cannot start server from state {self.state.name}")
            return False

        self._change_state(ServerState.STARTING)

        jar_path = Path(self.config.jar_path)
        if not jar_path.exists():
            logger.error(f"Server JAR not found: {jar_path}")
            self._change_state(ServerState.STOPPED)
            return False

        cmd = [
            "java",
            *self.config.jvm_args,
            "-jar",
            str(jar_path.resolve()),
            "--nogui",
        ]
        work_dir = jar_path.parent

        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            self._psutil_process = psutil.Process(self.process.pid)
            logger.info(f"Server process started with PID: {self.process.pid}")

            self._tasks.append(asyncio.create_task(self._read_stdout()))
            self._tasks.append(asyncio.create_task(self._read_stderr()))
            self._tasks.append(asyncio.create_task(self._monitor_process()))

            # Transition to RUNNING state is handled by log parser or a timeout
            # For now, we'll transition after a short delay for simplicity
            await asyncio.sleep(1)  # Represents time waiting for "Done" log message
            self._change_state(ServerState.RUNNING)
            await fire_event(ServerStartedEvent(pid=self.process.pid))
            return True

        except (Exception, psutil.Error) as e:
            logger.error(f"Failed to start server process: {e}")
            self._change_state(ServerState.CRASHED)
            return False

    async def stop(self, timeout: float = 30.0) -> bool:
        """Stop the Minecraft server process gracefully."""
        if self.state not in [ServerState.RUNNING, ServerState.STARTING]:
            logger.warning(f"Cannot stop server from state {self.state.name}")
            return False

        self._change_state(ServerState.STOPPING)

        try:
            if self.process and self.process.stdin:
                self.process.stdin.write(b"stop\n")
                await self.process.stdin.drain()

            await asyncio.wait_for(self.process.wait(), timeout=timeout)
            logger.info("Server stopped gracefully.")

        except asyncio.TimeoutError:
            logger.warning(
                f"Server did not stop gracefully within {timeout}s. Killing."
            )
            self.process.kill()
            await self.process.wait()
        except Exception as e:
            logger.error(f"Error during graceful stop: {e}. Killing process.")
            self.process.kill()
            await self.process.wait()
        finally:
            await self._cleanup_tasks()
            exit_code = self.process.returncode if self.process else -1
            self._change_state(ServerState.STOPPED)
            await fire_event(ServerStoppedEvent(exit_code=exit_code))
            self.process = None
            self._psutil_process = None
        return True

    async def send_command(self, command: str) -> bool:
        """Send a command to the server's stdin."""
        if (
            self.state != ServerState.RUNNING
            or not self.process
            or not self.process.stdin
        ):
            logger.error(f"Cannot send command in state {self.state.name}")
            return False

        try:
            command_bytes = f"{command.strip()}\n".encode()
            self.process.stdin.write(command_bytes)
            await self.process.stdin.drain()
            logger.debug(f"Sent command: {command}")
            return True
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            logger.error(f"Failed to send command '{command}': {e}")
            await self._handle_crash()
            return False

    async def _read_stdout(self):
        """Continuously read and process stdout from the server."""
        while self.process and self.process.stdout and not self.process.stdout.at_eof():
            try:
                line_bytes = await self.process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line:
                    await fire_event(ServerLogEvent(level="INFO", message=line))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading stdout: {e}")
                break

    async def _read_stderr(self):
        """Continuously read and process stderr from the server."""
        while self.process and self.process.stderr and not self.process.stderr.at_eof():
            try:
                line_bytes = await self.process.stderr.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line:
                    await fire_event(ServerLogEvent(level="ERROR", message=line))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading stderr: {e}")
                break

    async def _monitor_process(self):
        """Wait for the process to exit and handle the result."""
        if not self.process:
            return
        exit_code = await self.process.wait()
        logger.info(f"Server process exited with code: {exit_code}")

        if self.state not in [ServerState.STOPPING, ServerState.STOPPED]:
            await self._handle_crash(exit_code)

    async def _handle_crash(self, exit_code: int = -1):
        """Handle an unexpected server crash."""
        self._change_state(ServerState.CRASHED)
        await self._cleanup_tasks()
        await fire_event(ServerCrashEvent(exit_code=exit_code))

        # Optional: Implement auto-restart logic here
        if self.config.auto_restart:
            logger.info(f"Auto-restarting in {self.config.restart_delay} seconds...")
            await asyncio.sleep(self.config.restart_delay)
            await self.start()

    async def _cleanup_tasks(self):
        """Cancel and clean up all background tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics using psutil."""
        if not self._psutil_process or not self._psutil_process.is_running():
            return {}
        try:
            with self._psutil_process.oneshot():
                return {
                    "cpu_percent": self._psutil_process.cpu_percent(),
                    "memory_mb": self._psutil_process.memory_info().rss / (1024 * 1024),
                    "threads": self._psutil_process.num_threads(),
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {}

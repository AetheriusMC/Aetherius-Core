"""Server state management for persistent server status tracking."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psutil

logger = logging.getLogger(__name__)


class ServerState:
    """Manages server state persistence across CLI sessions."""

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or Path("server/.server_state.json")
        self.pid: Optional[int] = None
        self.start_time: Optional[str] = None
        self.jar_path: Optional[str] = None
        self.working_directory: Optional[str] = None

        # Ensure directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state
        self.load_state()

    def load_state(self) -> None:
        """Load server state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self.pid = data.get("pid")
                    self.start_time = data.get("start_time")
                    self.jar_path = data.get("jar_path")
                    self.working_directory = data.get("working_directory")
                    logger.debug(f"Loaded server state: PID {self.pid}")
        except Exception as e:
            logger.error(f"Error loading server state: {e}")
            self.clear_state()

    def save_state(self) -> None:
        """Save server state to file."""
        try:
            data = {
                "pid": self.pid,
                "start_time": self.start_time,
                "jar_path": self.jar_path,
                "working_directory": self.working_directory,
            }

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved server state: PID {self.pid}")
        except Exception as e:
            logger.error(f"Error saving server state: {e}")

    def set_server_started(
        self, pid: int, jar_path: str, working_directory: str
    ) -> None:
        """Mark server as started with given PID."""
        self.pid = pid
        self.start_time = datetime.now().isoformat()
        self.jar_path = jar_path
        self.working_directory = working_directory
        self.save_state()

    def set_server_stopped(self) -> None:
        """Mark server as stopped."""
        self.clear_state()

    def clear_state(self) -> None:
        """Clear server state."""
        self.pid = None
        self.start_time = None
        self.jar_path = None
        self.working_directory = None
        if self.state_file.exists():
            try:
                self.state_file.unlink()
            except Exception as e:
                logger.error(f"Error removing state file: {e}")

    def is_server_running(self) -> bool:
        """Check if the server is currently running."""
        if self.pid is None:
            return False

        try:
            # Check if process exists and is still running
            process = psutil.Process(self.pid)

            # Check if it's still a Java process (indicating server is likely still running)
            if "java" in process.name().lower():
                return True
            else:
                # Process exists but isn't java anymore, clear state
                self.clear_state()
                return False

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process doesn't exist anymore, clear state
            self.clear_state()
            return False

    def get_server_info(self) -> Optional[dict[str, Any]]:
        """Get server information if running."""
        if not self.is_server_running():
            return None

        try:
            process = psutil.Process(self.pid)
            return {
                "pid": self.pid,
                "start_time": self.start_time,
                "jar_path": self.jar_path,
                "working_directory": self.working_directory,
                "memory_usage": process.memory_info().rss / 1024 / 1024,  # MB
                "cpu_percent": process.cpu_percent(),
                "status": process.status(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self.clear_state()
            return None

    def terminate_server(self, force: bool = False) -> bool:
        """Terminate the server process."""
        if not self.is_server_running():
            return True

        try:
            process = psutil.Process(self.pid)

            if force:
                process.kill()
                logger.info(f"Force killed server process {self.pid}")
            else:
                process.terminate()
                logger.info(f"Terminated server process {self.pid}")

            # Wait a bit for process to stop
            try:
                process.wait(timeout=10)
            except psutil.TimeoutExpired:
                if not force:
                    # Try force kill if terminate didn't work
                    process.kill()
                    logger.warning(f"Had to force kill server process {self.pid}")

            self.clear_state()
            return True

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"Error terminating server: {e}")
            self.clear_state()
            return False


# Global server state instance
_server_state: ServerState | None = None


def get_server_state() -> ServerState:
    """Get the global server state instance."""
    global _server_state
    if _server_state is None:
        _server_state = ServerState()
    return _server_state

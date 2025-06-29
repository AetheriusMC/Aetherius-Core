"""Command queue system for cross-process server command execution."""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CommandQueue:
    """Manages a command queue for cross-process server command execution."""

    def __init__(self, queue_dir: Path = None):
        self.queue_dir = queue_dir or Path("server/.command_queue")
        self.pending_dir = self.queue_dir / "pending"
        self.completed_dir = self.queue_dir / "completed"

        # Ensure directories exist
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.completed_dir.mkdir(parents=True, exist_ok=True)

    def add_command(self, command: str, timeout: float = 30.0) -> str:
        """
        Add a command to the queue.

        Args:
            command: The command to execute
            timeout: Timeout in seconds

        Returns:
            str: Command ID for tracking
        """
        command_id = str(uuid.uuid4())
        command_data = {
            "id": command_id,
            "command": command,
            "timestamp": time.time(),
            "timeout": timeout,
            "status": "pending",
        }

        command_file = self.pending_dir / f"{command_id}.json"
        try:
            with open(command_file, "w", encoding="utf-8") as f:
                json.dump(command_data, f, indent=2)

            logger.debug(f"Added command to queue: {command} (ID: {command_id})")
            return command_id

        except Exception as e:
            logger.error(f"Error adding command to queue: {e}")
            raise

    async def wait_for_completion(
        self, command_id: str, timeout: float = 30.0
    ) -> dict[str, Any]:
        """
        Wait for a command to complete.

        Args:
            command_id: The command ID to wait for
            timeout: Timeout in seconds

        Returns:
            dict: Command result data
        """
        start_time = time.time()
        completed_file = self.completed_dir / f"{command_id}.json"

        while time.time() - start_time < timeout:
            if completed_file.exists():
                try:
                    with open(completed_file, encoding="utf-8") as f:
                        result = json.load(f)

                    # Clean up the completed file
                    completed_file.unlink()
                    return result

                except Exception as e:
                    logger.error(f"Error reading command result: {e}")
                    break

            await asyncio.sleep(0.1)

        # Timeout or error occurred
        return {
            "id": command_id,
            "status": "timeout",
            "success": False,
            "error": "Command execution timed out",
        }

    def get_pending_commands(self) -> list:
        """Get all pending commands."""
        commands = []

        try:
            for command_file in self.pending_dir.glob("*.json"):
                try:
                    with open(command_file, encoding="utf-8") as f:
                        command_data = json.load(f)

                    # Check if command has timed out
                    if time.time() - command_data["timestamp"] > command_data.get(
                        "timeout", 30.0
                    ):
                        self._mark_command_timeout(command_data["id"])
                        command_file.unlink()
                        continue

                    commands.append(command_data)

                except Exception as e:
                    logger.error(f"Error reading command file {command_file}: {e}")
                    # Remove corrupted file
                    command_file.unlink()

        except Exception as e:
            logger.error(f"Error scanning pending commands: {e}")

        return commands

    def mark_command_completed(
        self,
        command_id: str,
        success: bool,
        error: Optional[str] = None,
        output: Optional[str] = None,
    ) -> None:
        """Mark a command as completed with optional output."""
        try:
            # Remove from pending
            pending_file = self.pending_dir / f"{command_id}.json"
            if pending_file.exists():
                pending_file.unlink()

            # Create completed result
            result_data = {
                "id": command_id,
                "status": "completed",
                "success": success,
                "timestamp": time.time(),
                "error": error,
                "output": output,
            }

            completed_file = self.completed_dir / f"{command_id}.json"
            with open(completed_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2)

            logger.debug(
                f"Marked command as completed: {command_id} (success: {success})"
            )

        except Exception as e:
            logger.error(f"Error marking command as completed: {e}")

    def _mark_command_timeout(self, command_id: str) -> None:
        """Mark a command as timed out."""
        try:
            result_data = {
                "id": command_id,
                "status": "timeout",
                "success": False,
                "timestamp": time.time(),
                "error": "Command execution timed out",
            }

            completed_file = self.completed_dir / f"{command_id}.json"
            with open(completed_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=2)

            logger.warning(f"Command timed out: {command_id}")

        except Exception as e:
            logger.error(f"Error marking command as timed out: {e}")

    def cleanup_old_files(self, max_age_seconds: float = 300.0) -> None:
        """Clean up old command files."""
        try:
            current_time = time.time()

            # Clean up old completed files
            for completed_file in self.completed_dir.glob("*.json"):
                try:
                    if current_time - completed_file.stat().st_mtime > max_age_seconds:
                        completed_file.unlink()
                except Exception:
                    pass

            # Clean up old pending files (should be handled by timeout, but just in case)
            for pending_file in self.pending_dir.glob("*.json"):
                try:
                    if current_time - pending_file.stat().st_mtime > max_age_seconds:
                        pending_file.unlink()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Global command queue instance
_command_queue: CommandQueue | None = None


def get_command_queue() -> CommandQueue:
    """Get the global command queue instance."""
    global _command_queue
    if _command_queue is None:
        _command_queue = CommandQueue()
    return _command_queue

"""Output capture system for command feedback."""

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CommandOutput:
    """Captured output for a command."""

    command_id: str
    command: str
    lines: list[str]
    start_time: float
    end_time: Optional[float] = None

    def add_line(self, line: str) -> None:
        """Add a line to the output."""
        self.lines.append(line)

    def get_output(self) -> str:
        """Get the complete output as a string."""
        return "\n".join(self.lines)

    def is_expired(self, max_age_seconds: float = 30.0) -> bool:
        """Check if this output capture has expired."""
        return time.time() - self.start_time > max_age_seconds


class OutputCapture:
    """Captures server output for specific commands."""

    def __init__(self):
        self.active_captures: dict[str, CommandOutput] = {}
        self.command_patterns = {
            # Basic commands that typically produce immediate output
            "list": [
                r"There are \d+/\d+ players online",
                r"There are \d+ of a max of \d+ players online",
                r"There are no players online",
                r"Players online \(\d+\)",
            ],
            "say": [r"\[Server\]", r"Server:"],
            "give": [
                r"Gave \d+ .+ to .+",
                r"Could not give .+ to .+",
                r"Unknown item",
                r"Player .+ not found",
            ],
            "tp": [
                r"Teleported .+ to",
                r"Could not teleport",
                r"Player .+ not found",
                r"Invalid coordinates",
            ],
            "gamemode": [
                r"Set .+\'s game mode to",
                r"Player .+ not found",
                r"Invalid game mode",
            ],
            "time": [r"Set the time to", r"Added \d+ to the time"],
            "weather": [r"Set the weather to", r"Weather set to"],
            "difficulty": [r"Set the difficulty to", r"Difficulty set to"],
        }

        # Generic patterns that might apply to any command
        self.generic_patterns = [
            r"Unknown command",
            r"Incorrect argument for command",
            r"Permission denied",
            r"Command not found",
            r"Syntax error",
            r"Usage:",
        ]

    def start_capture(self, command_id: str, command: str) -> None:
        """Start capturing output for a command."""
        # Clean up expired captures
        self._cleanup_expired()

        # Start new capture
        self.active_captures[command_id] = CommandOutput(
            command_id=command_id, command=command, lines=[], start_time=time.time()
        )

        logger.debug(
            f"Started output capture for command: {command} (ID: {command_id})"
        )

    def process_line(self, line: str) -> None:
        """Process a server output line and match it to active captures."""
        if not self.active_captures:
            return

        # Remove color codes and formatting
        clean_line = self._clean_line(line)

        # Check each active capture to see if this line is relevant
        for command_id, capture in list(self.active_captures.items()):
            if self._is_line_relevant(capture.command, clean_line):
                capture.add_line(clean_line)
                logger.debug(
                    f"Captured line for command {capture.command}: {clean_line}"
                )

    def finish_capture(self, command_id: str) -> Optional[str]:
        """Finish capturing and return the captured output."""
        if command_id not in self.active_captures:
            return None

        capture = self.active_captures[command_id]
        capture.end_time = time.time()

        # Get the output
        output = capture.get_output()

        # Remove from active captures
        del self.active_captures[command_id]

        logger.debug(
            f"Finished capture for command {capture.command}, captured {len(capture.lines)} lines"
        )
        return output if output.strip() else None

    def _clean_line(self, line: str) -> str:
        """Clean a log line by removing timestamps and color codes."""
        # Remove timestamp patterns like [HH:MM:SS]
        line = re.sub(r"\[\d{2}:\d{2}:\d{2}\]", "", line)

        # Remove log level indicators like [INFO], [WARN], [ERROR]
        line = re.sub(r"\[(INFO|WARN|WARNING|ERROR|DEBUG)\]", "", line)

        # Remove color codes (ANSI escape sequences)
        line = re.sub(r"\x1b\[[0-9;]*m", "", line)

        # Remove server thread indicators
        line = re.sub(r"\[Server thread/[^\]]+\]", "", line)

        return line.strip()

    def _is_line_relevant(self, command: str, line: str) -> bool:
        """Check if a line is relevant to a specific command."""
        # Extract the base command (first word)
        base_command = command.split()[0].lower()

        # Check command-specific patterns
        if base_command in self.command_patterns:
            for pattern in self.command_patterns[base_command]:
                if re.search(pattern, line, re.IGNORECASE):
                    return True

        # Check generic error patterns
        for pattern in self.generic_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True

        # For 'list' command, also capture player names
        if base_command == "list":
            # Player list might be on subsequent lines
            if re.search(
                r"^[a-zA-Z_][a-zA-Z0-9_]{2,15}(,\s*[a-zA-Z_][a-zA-Z0-9_]{2,15})*$", line
            ):
                return True

        return False

    def _cleanup_expired(self) -> None:
        """Remove expired captures."""
        expired_ids = [
            command_id
            for command_id, capture in self.active_captures.items()
            if capture.is_expired()
        ]

        for command_id in expired_ids:
            del self.active_captures[command_id]
            logger.debug(f"Removed expired capture: {command_id}")


# Global output capture instance
_output_capture: OutputCapture | None = None


def get_output_capture() -> OutputCapture:
    """Get the global output capture instance."""
    global _output_capture
    if _output_capture is None:
        _output_capture = OutputCapture()
    return _output_capture

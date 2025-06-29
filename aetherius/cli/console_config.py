"""Console configuration and settings."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ConsoleConfig:
    """Configuration for enhanced console"""

    # Display settings
    max_log_lines: int = 50
    refresh_rate: float = 0.1  # seconds
    auto_scroll: bool = True

    # Command settings
    default_command_type: str = "minecraft"
    command_timeout: float = 10.0

    # UI settings
    show_timestamps: bool = True
    show_event_stats: bool = True
    use_colors: bool = True

    # Log filtering
    log_levels: list[Any] | None = None  # None means all levels
    hide_empty_lines: bool = True

    def __post_init__(self):
        if self.log_levels is None:
            self.log_levels = ["INFO", "WARN", "ERROR", "DEBUG"]


# Default console configuration
DEFAULT_CONSOLE_CONFIG = ConsoleConfig()


def get_console_config() -> ConsoleConfig:
    """Get console configuration"""
    # In future versions, this could load from file
    return DEFAULT_CONSOLE_CONFIG

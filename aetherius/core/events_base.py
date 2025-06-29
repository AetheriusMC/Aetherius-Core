"""Event system for Aetherius - Event definitions and base classes."""

from abc import ABC
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EventPriority(Enum):
    """Event priority levels for controlling execution order."""

    LOWEST = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    HIGHEST = 4


class BaseEvent(BaseModel, ABC):
    """Base class for all events in the Aetherius system."""

    timestamp: datetime = Field(default_factory=datetime.now)
    cancelled: bool = Field(default=False)

    def cancel(self) -> None:
        """Mark this event as cancelled."""
        self.cancelled = True

    def is_cancelled(self) -> bool:
        """Check if this event has been cancelled."""
        return self.cancelled


# Server Lifecycle Events
class ServerLifecycleEvent(BaseEvent):
    """Base class for server lifecycle events."""

    pass


class ServerStartingEvent(ServerLifecycleEvent):
    """Event fired when the server is starting up."""

    command: list[str] = Field(description="Command used to start the server")
    working_directory: str = Field(description="Server working directory")


class ServerStartedEvent(ServerLifecycleEvent):
    """Event fired when the server has successfully started."""

    pid: int = Field(description="Process ID of the server")
    startup_time: float = Field(description="Time taken to start (seconds)")


class ServerStoppingEvent(ServerLifecycleEvent):
    """Event fired when the server is stopping."""

    reason: str = Field(description="Reason for stopping")
    force: bool = Field(default=False, description="Whether this is a forced stop")


class ServerStoppedEvent(ServerLifecycleEvent):
    """Event fired when the server has stopped."""

    exit_code: int = Field(description="Exit code of the server process")
    uptime: float = Field(description="Total uptime in seconds")


class ServerCrashEvent(ServerLifecycleEvent):
    """Event fired when the server crashes unexpectedly."""

    exit_code: int = Field(description="Exit code of the crashed process")
    error_output: str = Field(description="Last error output from server")
    will_restart: bool = Field(description="Whether auto-restart will occur")


class ServerLogEvent(ServerLifecycleEvent):
    """Event fired for server log output."""

    line: str = Field(description="Raw log line")
    level: str = Field(description="Log level (INFO, WARN, ERROR, etc.)")
    message: str = Field(description="Log message content")
    log_timestamp: Optional[datetime] = Field(
        default=None, description="Parsed timestamp from log"
    )


class ServerStateChangedEvent(ServerLifecycleEvent):
    """Event fired when the server state changes."""

    old_state: str = Field(description="Previous server state")
    new_state: str = Field(description="New server state")
    reason: Optional[str] = Field(default=None, description="Reason for state change")


# Player Events
class PlayerEvent(BaseEvent):
    """Base class for player-related events."""

    player_name: str = Field(description="Name of the player")
    player_uuid: Optional[str] = Field(default=None, description="UUID of the player")


class PlayerJoinEvent(PlayerEvent):
    """Event fired when a player joins the server."""

    ip_address: Optional[str] = Field(default=None, description="Player's IP address")
    login_time: datetime = Field(default_factory=datetime.now)


class PlayerLeaveEvent(PlayerEvent):
    """Event fired when a player leaves the server."""

    leave_reason: Optional[str] = Field(default=None, description="Reason for leaving")
    session_duration: Optional[float] = Field(
        default=None, description="Session duration in seconds"
    )


class PlayerChatEvent(PlayerEvent):
    """Event fired when a player sends a chat message."""

    message: str = Field(description="Chat message content")
    channel: str = Field(default="global", description="Chat channel")


class PlayerDeathEvent(PlayerEvent):
    """Event fired when a player dies."""

    death_message: str = Field(description="Death message from server")
    killer: Optional[str] = Field(
        default=None, description="Name of killer if applicable"
    )


class PlayerAdvancementEvent(PlayerEvent):
    """Event fired when a player gets an advancement."""

    advancement: str = Field(description="Advancement identifier")
    advancement_title: str = Field(description="Display title of advancement")


# System Events
class SystemEvent(BaseEvent):
    """Base class for system-related events."""

    pass


class CoreReadyEvent(SystemEvent):
    """Event fired when the Aetherius core is fully initialized."""

    components_loaded: int = Field(description="Number of components loaded")
    plugins_loaded: int = Field(description="Number of plugins loaded")


class LogLineEvent(SystemEvent):
    """Event fired for each log line from the server."""

    line: str = Field(description="Raw log line")
    level: str = Field(description="Log level (INFO, WARN, ERROR, etc.)")
    log_timestamp: Optional[datetime] = Field(
        default=None, description="Parsed timestamp from log"
    )
    message: str = Field(description="Log message content")


class UnknownLogEvent(SystemEvent):
    """Event fired for log lines that couldn't be parsed into specific events."""

    raw_line: str = Field(description="Raw log line that couldn't be parsed")
    attempted_patterns: list[str] = Field(description="Patterns that were attempted")


# Performance Events
class PerformanceEvent(BaseEvent):
    """Base class for performance-related events."""

    pass


class TickTimeEvent(PerformanceEvent):
    """Event fired for server tick timing information."""

    tick_time: float = Field(description="Tick time in milliseconds")
    tps: float = Field(description="Ticks per second")
    warning_threshold: float = Field(
        default=50.0, description="Warning threshold in ms"
    )


class LagSpikeEvent(PerformanceEvent):
    """Event fired when a significant lag spike is detected."""

    duration: float = Field(description="Lag spike duration in milliseconds")
    severity: str = Field(description="Severity level (minor, major, severe)")


# Error Events
class ErrorEvent(BaseEvent):
    """Base class for error-related events."""

    error_message: str = Field(description="Error message")
    stack_trace: Optional[str] = Field(
        default=None, description="Stack trace if available"
    )


class PluginErrorEvent(ErrorEvent):
    """Event fired when a plugin encounters an error."""

    plugin_name: str = Field(description="Name of the plugin with error")
    error_type: str = Field(description="Type of error")


class ConfigurationErrorEvent(ErrorEvent):
    """Event fired when there's a configuration issue."""

    config_file: str = Field(description="Configuration file with error")
    line_number: int | None = Field(
        default=None, description="Line number if applicable"
    )


# Event type registry for dynamic lookup
EVENT_TYPES: dict[str, type[BaseEvent]] = {
    # Server Lifecycle
    "server_starting": ServerStartingEvent,
    "server_started": ServerStartedEvent,
    "server_stopping": ServerStoppingEvent,
    "server_stopped": ServerStoppedEvent,
    "server_crash": ServerCrashEvent,
    "server_log": ServerLogEvent,
    "server_state_changed": ServerStateChangedEvent,
    # Player Events
    "player_join": PlayerJoinEvent,
    "player_leave": PlayerLeaveEvent,
    "player_chat": PlayerChatEvent,
    "player_death": PlayerDeathEvent,
    "player_advancement": PlayerAdvancementEvent,
    # System Events
    "core_ready": CoreReadyEvent,
    "log_line": LogLineEvent,
    "unknown_log": UnknownLogEvent,
    # Performance Events
    "tick_time": TickTimeEvent,
    "lag_spike": LagSpikeEvent,
    # Error Events
    "plugin_error": PluginErrorEvent,
    "configuration_error": ConfigurationErrorEvent,
}

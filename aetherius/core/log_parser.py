"""Log parsing system for Minecraft server logs."""

import logging
import re
from datetime import datetime
from pathlib import Path
from re import Pattern
from typing import Optional, Union

import yaml

from .events_base import (
    BaseEvent,
    LagSpikeEvent,
    LogLineEvent,
    PlayerAdvancementEvent,
    PlayerChatEvent,
    PlayerDeathEvent,
    PlayerJoinEvent,
    PlayerLeaveEvent,
    ServerStartedEvent,
    ServerStoppingEvent,
    TickTimeEvent,
    UnknownLogEvent,
)

logger = logging.getLogger(__name__)


class LogPattern:
    """Represents a log parsing pattern with associated event creation."""

    def __init__(
        self,
        name: str,
        pattern: Union[str, Pattern],
        event_type: type[BaseEvent],
        field_mapping: Optional[dict[str, str]] = None,
        condition: Optional[str] = None,
    ):
        """
        Initialize a log pattern.

        Args:
            name: Name of the pattern
            pattern: Regex pattern to match log lines
            event_type: Event type to create when pattern matches
            field_mapping: Mapping of regex groups to event fields
            condition: Optional condition to check before creating event
        """
        self.name = name
        self.pattern = pattern if isinstance(pattern, Pattern) else re.compile(pattern)
        self.event_type = event_type
        self.field_mapping = field_mapping or {}
        self.condition = condition

    def try_parse(
        self, line: str, timestamp: Optional[datetime] = None
    ) -> Optional[BaseEvent]:
        """
        Try to parse a log line with this pattern.

        Args:
            line: Log line to parse
            timestamp: Parsed timestamp from log line

        Returns:
            BaseEvent: Created event if pattern matches, None otherwise
        """
        match = self.pattern.search(line)
        if not match:
            return None

        # Extract fields from regex groups
        event_data = {}

        # Add timestamp if available
        if timestamp:
            event_data["timestamp"] = timestamp

        # Map named groups to event fields
        for group_name, value in match.groupdict().items():
            if group_name in self.field_mapping:
                field_name = self.field_mapping[group_name]
                event_data[field_name] = value
            elif hasattr(self.event_type, group_name):
                event_data[group_name] = value

        # Map positional groups if field mapping is provided
        groups = match.groups()
        for i, group_value in enumerate(groups):
            field_mapping_key = str(i + 1)  # Groups are 1-indexed in field mapping
            if field_mapping_key in self.field_mapping and group_value is not None:
                field_name = self.field_mapping[field_mapping_key]
                event_data[field_name] = group_value

        # Apply condition if specified
        if self.condition:
            try:
                # Simple condition evaluation (could be expanded)
                if not eval(
                    self.condition, {"match": match, "line": line, "data": event_data}
                ):
                    return None
            except Exception as e:
                logger.warning(f"Error evaluating condition '{self.condition}': {e}")
                return None

        # Type conversion for specific fields
        if self.event_type == ServerStartedEvent and "startup_time" in event_data:
            try:
                event_data["startup_time"] = float(event_data["startup_time"])
            except (ValueError, TypeError):
                logger.warning(
                    f"Could not convert startup_time '{event_data['startup_time']}' to float."
                )
                return None

        if self.event_type == LagSpikeEvent and "duration" in event_data:
            try:
                event_data["duration"] = float(event_data["duration"])
            except (ValueError, TypeError):
                logger.warning(
                    f"Could not convert duration '{event_data['duration']}' to float."
                )
                return None

        if self.event_type == TickTimeEvent and "tps" in event_data:
            try:
                event_data["tps"] = float(event_data["tps"])
            except (ValueError, TypeError):
                logger.warning(f"Could not convert tps '{event_data['tps']}' to float.")
                return None

        # Add default values for missing required fields based on event type
        if self.event_type == PlayerDeathEvent:
            if "death_message" not in event_data:
                if "killer" in event_data:
                    event_data["death_message"] = f"was slain by {event_data['killer']}"
                else:
                    event_data["death_message"] = "died"
        elif self.event_type == ServerStartedEvent:
            if "pid" not in event_data:
                event_data["pid"] = 0  # Will be updated by server wrapper
        elif self.event_type == LagSpikeEvent:
            if "severity" not in event_data:
                duration = float(event_data.get("duration", 0))
                if duration > 5000:
                    event_data["severity"] = "severe"
                elif duration > 1000:
                    event_data["severity"] = "major"
                else:
                    event_data["severity"] = "minor"

        try:
            return self.event_type(**event_data)
        except Exception as e:
            logger.warning(f"Error creating event {self.event_type.__name__}: {e}")
            return None


class LogParser:
    """
    Parses Minecraft server log lines and converts them to events.

    This parser uses configurable regex patterns to identify different types
    of log entries and convert them into structured events.
    """

    def __init__(self, rules_file: Optional[Path] = None):
        """
        Initialize the log parser.

        Args:
            rules_file: Path to YAML file containing parsing rules
        """
        self.patterns: list[LogPattern] = []
        self.timestamp_pattern = re.compile(
            r"\[(\d{2}:\d{2}:\d{2})\]|\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"
        )
        self.log_level_pattern = re.compile(r"\[(INFO|WARN|ERROR|DEBUG|TRACE)\]")

        # Load default patterns
        self._load_default_patterns()

        # Load custom patterns from file if provided
        if rules_file and rules_file.exists():
            self._load_patterns_from_file(rules_file)

    def _load_default_patterns(self) -> None:
        """Load default parsing patterns for common Minecraft server events."""

        # Player join patterns
        self.add_pattern(
            LogPattern(
                name="player_join_vanilla",
                pattern=r"(\w+)\[/([0-9.]+):(\d+)\] logged in",
                event_type=PlayerJoinEvent,
                field_mapping={"1": "player_name", "2": "ip_address"},
            )
        )

        self.add_pattern(
            LogPattern(
                name="player_join_paper",
                pattern=r"(\w+) joined the game",
                event_type=PlayerJoinEvent,
                field_mapping={"1": "player_name"},
            )
        )

        # Player leave patterns
        self.add_pattern(
            LogPattern(
                name="player_leave",
                pattern=r"(\w+) left the game",
                event_type=PlayerLeaveEvent,
                field_mapping={"1": "player_name"},
            )
        )

        # Player chat patterns
        self.add_pattern(
            LogPattern(
                name="player_chat",
                pattern=r"<(\w+)> (.+)",
                event_type=PlayerChatEvent,
                field_mapping={"1": "player_name", "2": "message"},
            )
        )

        # Player death patterns
        self.add_pattern(
            LogPattern(
                name="player_death",
                pattern=r"(\w+) (died|was killed|was slain|drowned|burned|fell|starved|suffocated|was blown up|hit the ground|went up in flames|walked into fire|was struck by lightning)",
                event_type=PlayerDeathEvent,
                field_mapping={"1": "player_name", "2": "death_message"},
            )
        )

        # More specific death patterns
        self.add_pattern(
            LogPattern(
                name="player_death_detailed",
                pattern=r"(\w+) was (?:killed|slain) by (\w+)",
                event_type=PlayerDeathEvent,
                field_mapping={"1": "player_name", "2": "killer"},
            )
        )

        # Player advancement patterns
        self.add_pattern(
            LogPattern(
                name="player_advancement",
                pattern=r"(\w+) has made the advancement \[([^\]]+)\]",
                event_type=PlayerAdvancementEvent,
                field_mapping={"1": "player_name", "2": "advancement_title"},
            )
        )

        # Server lifecycle patterns
        self.add_pattern(
            LogPattern(
                name="server_started",
                pattern=r"Done \(([0-9.]+)s\)! For help, type \"help\"",
                event_type=ServerStartedEvent,
                field_mapping={"1": "startup_time"},
            )
        )

        self.add_pattern(
            LogPattern(
                name="server_stopping",
                pattern=r"Stopping server",
                event_type=ServerStoppingEvent,
                field_mapping={},
            )
        )

        # Performance patterns
        self.add_pattern(
            LogPattern(
                name="tick_time_warning",
                pattern=r"Can't keep up! Is the server overloaded\? Running (\d+)ms or (\d+) ticks behind",
                event_type=LagSpikeEvent,
                field_mapping={"1": "duration", "2": "tick_count"},
            )
        )

        # TPS patterns for Paper/Spigot
        self.add_pattern(
            LogPattern(
                name="tps_report",
                pattern=r"TPS from last 1m, 5m, 15m: ([0-9.]+), ([0-9.]+), ([0-9.]+)",
                event_type=TickTimeEvent,
                field_mapping={"1": "tps"},
            )
        )

    def _load_patterns_from_file(self, rules_file: Path) -> None:
        """Load parsing patterns from a YAML configuration file."""
        try:
            with open(rules_file, encoding="utf-8") as f:
                rules_data = yaml.safe_load(f)

            if not isinstance(rules_data, dict) or "patterns" not in rules_data:
                logger.warning(f"Invalid rules file format: {rules_file}")
                return

            for pattern_data in rules_data["patterns"]:
                try:
                    # Get event type from string
                    event_type_name = pattern_data["event_type"]
                    from .events import EVENT_TYPES

                    event_type = EVENT_TYPES.get(event_type_name)

                    if not event_type:
                        logger.warning(f"Unknown event type: {event_type_name}")
                        continue

                    pattern = LogPattern(
                        name=pattern_data["name"],
                        pattern=pattern_data["pattern"],
                        event_type=event_type,
                        field_mapping=pattern_data.get("field_mapping", {}),
                        condition=pattern_data.get("condition"),
                    )

                    self.add_pattern(pattern)
                    logger.debug(f"Loaded custom pattern: {pattern.name}")

                except Exception as e:
                    logger.error(
                        f"Error loading pattern {pattern_data.get('name', 'unknown')}: {e}"
                    )

        except Exception as e:
            logger.error(f"Error loading rules file {rules_file}: {e}")

    def add_pattern(self, pattern: LogPattern) -> None:
        """Add a parsing pattern to the parser."""
        self.patterns.append(pattern)
        logger.debug(f"Added log pattern: {pattern.name}")

    def remove_pattern(self, name: str) -> bool:
        """Remove a parsing pattern by name."""
        for i, pattern in enumerate(self.patterns):
            if pattern.name == name:
                del self.patterns[i]
                logger.debug(f"Removed log pattern: {name}")
                return True
        return False

    def parse_line(self, line: str) -> list[BaseEvent]:
        """
        Parse a single log line and return any generated events.

        Args:
            line: Raw log line from server

        Returns:
            List[BaseEvent]: List of events generated from the line
        """
        events = []

        # Extract timestamp and log level
        timestamp = self._extract_timestamp(line)
        log_level = self._extract_log_level(line)

        # Create base log line event
        log_event = LogLineEvent(
            line=line,
            level=log_level or "INFO",
            timestamp=timestamp,
            message=self._extract_message(line),
        )
        events.append(log_event)

        # Try to parse with each pattern
        parsed = False
        attempted_patterns = []

        for pattern in self.patterns:
            attempted_patterns.append(pattern.name)
            try:
                event = pattern.try_parse(line, timestamp)
                if event:
                    events.append(event)
                    parsed = True
                    logger.debug(
                        f"Parsed line with pattern '{pattern.name}': {type(event).__name__}"
                    )
                    break  # Use first matching pattern
            except Exception as e:
                logger.warning(f"Error applying pattern '{pattern.name}' to line: {e}")

        # If no pattern matched, create an unknown log event
        if not parsed and line.strip():  # Don't create events for empty lines
            unknown_event = UnknownLogEvent(
                raw_line=line, attempted_patterns=attempted_patterns
            )
            events.append(unknown_event)

        return events

    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """Extract timestamp from log line."""
        match = self.timestamp_pattern.search(line)
        if not match:
            return None

        time_str = match.group(1) or match.group(2)
        if not time_str:
            return None

        try:
            # Try different timestamp formats
            if len(time_str) == 8:  # HH:MM:SS
                # Use today's date with the time
                today = datetime.now().date()
                time_part = datetime.strptime(time_str, "%H:%M:%S").time()
                return datetime.combine(today, time_part)
            else:  # Full datetime
                return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def _extract_log_level(self, line: str) -> str | None:
        """Extract log level from log line."""
        match = self.log_level_pattern.search(line)
        return match.group(1) if match else None

    def _extract_message(self, line: str) -> str:
        """Extract the main message content from a log line."""
        # Remove timestamp and log level prefixes
        message = line

        # Remove timestamp
        message = self.timestamp_pattern.sub("", message).strip()

        # Remove log level
        message = self.log_level_pattern.sub("", message).strip()

        # Remove thread info like [Server thread/INFO]
        message = re.sub(r"\[[^/]+/[^\]]+\]", "", message).strip()

        # Remove leading colons and spaces
        message = message.lstrip(": ")

        return message or line  # Return original line if we stripped everything

    def get_patterns(self) -> list[LogPattern]:
        """Get all registered patterns."""
        return self.patterns.copy()

    def get_pattern_stats(self) -> dict[str, int]:
        """Get statistics about pattern usage (would need to track usage)."""
        # This could be enhanced to track which patterns are used most frequently
        return {pattern.name: 0 for pattern in self.patterns}

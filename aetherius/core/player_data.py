"""Player data management and structured player information API."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from .config import get_config_manager
from .event_manager import fire_event, get_event_manager
from .events_base import BaseEvent
from .player_data_models import PlayerData, PlayerLocation, PlayerStats, PlayerInventory
from .player_data_repository import PlayerDataRepository

logger = logging.getLogger(__name__)


class PlayerDataUpdatedEvent(BaseEvent):
    """Event fired when player data is updated."""

    def __init__(self, player_name: str, data: PlayerData, source: str = "unknown"):
        super().__init__()
        self.player_name = player_name
        self.data = data
        self.source = source


class PlayerDataManager:
    """
    Manager for structured player data with support for helper plugins.

    This manager provides a unified API for accessing detailed player information
    that goes beyond what can be parsed from server logs. It supports integration
    with helper plugins (like AetheriusHelper.jar) that can provide deep game data.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize player data manager."""
        self.data_dir = data_dir or Path("data/players")

        self.config_manager = get_config_manager()
        self.event_manager = get_event_manager()
        self.repository = PlayerDataRepository(self.data_dir)

        # In-memory player data cache
        self._player_cache: dict[str, PlayerData] = {}
        self._online_players: set[str] = set()

        # Helper plugin integration
        self._helper_enabled = False
        self._helper_data_file = Path("data/aetherius_helper.json")
        self._last_helper_update = 0.0

        # Load existing player data
        self._load_player_data()

        # Check for helper plugin
        self._check_helper_plugin()

    def _check_helper_plugin(self) -> None:
        """Check if AetheriusHelper plugin is available and enabled."""
        config = self.config_manager.get_config()
        helper_config = None
        for component in config.components:
            if component.name == "helper":
                helper_config = component.config
                break

        if helper_config:
            self._helper_enabled = helper_config.get("enabled", False)
            self._helper_data_file = Path(
                helper_config.get("data_file", "data/aetherius_helper.json")
            )
        else:
            self._helper_enabled = False

        if self._helper_enabled:
            logger.info("AetheriusHelper plugin integration enabled")
        else:
            logger.info("AetheriusHelper plugin integration disabled")

    def _load_player_data(self) -> None:
        """Load existing player data from files."""
        try:
            self._player_cache = self.repository.load_all_players()
            for player_name, player_data in self._player_cache.items():
                if player_data.is_online:
                    self._online_players.add(player_name)
            logger.info(f"Loaded {len(self._player_cache)} players from repository.")
        except Exception as e:
            logger.error(f"Error loading player data from repository: {e}")

    def _save_player_data(self, player_name: str) -> None:
        """Save player data to file."""
        if player_name not in self._player_cache:
            return

        self.repository.save_player_data(self._player_cache[player_name])

    async def update_from_helper_plugin(self) -> bool:
        """
        Update player data from helper plugin data file.

        Returns:
            True if data was updated, False otherwise
        """
        if not self._helper_enabled or not self._helper_data_file.exists():
            return False

        try:
            # Check if file has been modified since last update
            stat = self._helper_data_file.stat()
            if stat.st_mtime <= self._last_helper_update:
                return False

            with open(self._helper_data_file, encoding="utf-8") as f:
                helper_data = json.load(f)

            self._last_helper_update = stat.st_mtime

            # Process helper data
            players_data = helper_data.get("players", {})
            updated_players = []

            for player_name, data in players_data.items():
                if player_name not in self._player_cache:
                    # Create new player data
                    self._player_cache[player_name] = PlayerData(
                        uuid=data.get("uuid", ""),
                        username=player_name
                    )

                player_data = self._player_cache[player_name]

                # Update player data from helper
                if "uuid" in data:
                    player_data.uuid = data["uuid"]
                if "display_name" in data:
                    player_data.display_name = data["display_name"]
                if "online" in data:
                    player_data.is_online = data["online"]

                # Update location
                if "location" in data:
                    loc_data = data["location"]
                    player_data.location = PlayerLocation(
                        x=loc_data.get("x", 0.0),
                        y=loc_data.get("y", 0.0),
                        z=loc_data.get("z", 0.0),
                        dimension=loc_data.get("dimension", "overworld"),
                        yaw=loc_data.get("yaw", 0.0),
                        pitch=loc_data.get("pitch", 0.0),
                    )

                # Update stats
                if "stats" in data:
                    stats_data = data["stats"]
                    player_data.stats = PlayerStats(
                        health=stats_data.get("health", 20.0),
                        food_level=stats_data.get("hunger", 20),
                        xp_level=stats_data.get("experience_level", 0),
                        xp_progress=stats_data.get("experience_progress", 0.0),
                        play_time=stats_data.get("play_time", 0.0),
                        deaths=stats_data.get("deaths", 0),
                        kills=stats_data.get("kills", 0),
                        blocks_broken=stats_data.get("blocks_broken", 0),
                        blocks_placed=stats_data.get("blocks_placed", 0),
                        distance_walked=stats_data.get("distance_walked", 0.0),
                    )

                # Update inventory
                if "inventory" in data:
                    inv_data = data["inventory"]
                    player_data.inventory = PlayerInventory(
                        items=inv_data.get("items", {}),
                        armor=inv_data.get("armor", {}),
                        ender_chest=inv_data.get("ender_chest", {}),
                    )

                # Update custom data
                if "custom" in data:
                    player_data.metadata.update(data["custom"])

                # Track online status
                if player_data.is_online:
                    self._online_players.add(player_name)
                else:
                    self._online_players.discard(player_name)

                updated_players.append(player_name)

                # Fire update event
                event = PlayerDataUpdatedEvent(
                    player_name, player_data, "helper_plugin"
                )
                await fire_event(event)

            # Save updated data
            for player_name in updated_players:
                self._save_player_data(player_name)

            logger.debug(f"Updated {len(updated_players)} players from helper plugin")
            return True

        except Exception as e:
            logger.error(f"Error updating from helper plugin: {e}")
            return False

    def get_player_data(self, player_name: str) -> Optional[PlayerData]:
        """
        Get player data by name.

        Args:
            player_name: Player name

        Returns:
            PlayerData object or None if not found
        """
        return self._player_cache.get(player_name)

    def get_all_players(self) -> dict[str, PlayerData]:
        """
        Get all player data.

        Returns:
            Dictionary mapping player names to PlayerData objects
        """
        return self._player_cache.copy()

    def get_online_players(self) -> dict[str, PlayerData]:
        """
        Get all online players.

        Returns:
            Dictionary mapping online player names to PlayerData objects
        """
        return {name: data for name, data in self._player_cache.items() if data.is_online}

    def get_player_count(self) -> int:
        """
        Get total number of known players."""
        return len(self._player_cache)

    def get_online_count(self) -> int:
        """
        Get number of online players."""
        return len(self._online_players)

    def update_player_data(self, player_name: str, **kwargs) -> bool:
        """
        Update player data.

        Args:
            player_name: Player name
            **kwargs: Player data fields to update

        Returns:
            True if updated successfully
        """
        try:
            if player_name not in self._player_cache:
                self._player_cache[player_name] = PlayerData(
                    uuid="",
                    username=player_name
                )

            player_data = self._player_cache[player_name]

            # Update basic fields - map old field names to new ones
            field_mapping = {
                "online": "is_online",
                "last_seen": "last_logout", 
                "first_join": "first_join",
                "play_time": None,  # Handle separately
                "ip_address": None,  # Handle via metadata
            }
            
            for old_field, new_field in field_mapping.items():
                if old_field in kwargs and new_field:
                    setattr(player_data, new_field, kwargs[old_field])
            
            # Handle direct field updates
            if "uuid" in kwargs:
                player_data.uuid = kwargs["uuid"]
            if "display_name" in kwargs:
                player_data.display_name = kwargs["display_name"]

            # Update metadata
            if "ip_address" in kwargs:
                player_data.metadata["ip_address"] = kwargs["ip_address"]
            if "permissions" in kwargs:
                player_data.metadata["permissions"] = kwargs["permissions"]
            if "groups" in kwargs:
                player_data.metadata["groups"] = kwargs["groups"]
            if "custom_data" in kwargs:
                player_data.metadata.update(kwargs["custom_data"])

            # Update online status tracking
            if "online" in kwargs:
                player_data.is_online = kwargs["online"]
                if kwargs["online"]:
                    self._online_players.add(player_name)
                else:
                    self._online_players.discard(player_name)

            # Save data
            self._save_player_data(player_name)

            return True

        except Exception as e:
            logger.error(f"Error updating player data for {player_name}: {e}")
            return False

    def set_player_location(
        self,
        player_name: str,
        x: float,
        y: float,
        z: float,
        dimension: str = "overworld",
        yaw: float = 0.0,
        pitch: float = 0.0,
    ) -> bool:
        """
        Set player location.

        Args:
            player_name: Player name
            x, y, z: Coordinates
            dimension: Dimension name
            yaw, pitch: Rotation

        Returns:
            True if set successfully
        """
        try:
            if player_name not in self._player_cache:
                self._player_cache[player_name] = PlayerData(
                    uuid="",
                    username=player_name
                )

            player_data = self._player_cache[player_name]
            player_data.location = PlayerLocation(x, y, z, dimension, yaw, pitch)

            self._save_player_data(player_name)
            return True

        except Exception as e:
            logger.error(f"Error setting location for {player_name}: {e}")
            return False

    def set_player_stats(self, player_name: str, **stats) -> bool:
        """
        Set player statistics.

        Args:
            player_name: Player name
            **stats: Statistics to update

        Returns:
            True if set successfully
        """
        try:
            if player_name not in self._player_cache:
                self._player_cache[player_name] = PlayerData(
                    uuid="",
                    username=player_name
                )

            player_data = self._player_cache[player_name]

            if player_data.stats is None:
                player_data.stats = PlayerStats()

            # Update stats - map old field names to new ones
            field_mapping = {
                "health": "health",
                "hunger": "food_level", 
                "experience_level": "xp_level",
                "experience_total": None,  # No direct equivalent
                "play_time": "play_time",
                "deaths": "deaths",
                "kills": "kills",
                "blocks_broken": "blocks_broken",
                "blocks_placed": "blocks_placed",
                "distance_walked": "distance_walked",
            }
            
            for old_field, new_field in field_mapping.items():
                if old_field in stats and new_field:
                    setattr(player_data.stats, new_field, stats[old_field])

            self._save_player_data(player_name)
            return True

        except Exception as e:
            logger.error(f"Error setting stats for {player_name}: {e}")
            return False

    async def refresh_helper_data(self) -> bool:
        """
        Manually refresh data from helper plugin.

        Returns:
            True if refreshed successfully
        """
        return await self.update_from_helper_plugin()

    def enable_helper_plugin(self, data_file_path: Optional[str] = None) -> None:
        """
        Enable helper plugin integration.

        Args:
            data_file_path: Path to helper plugin data file
        """
        self._helper_enabled = True
        if data_file_path:
            self._helper_data_file = Path(data_file_path)

        config = self.config_manager.get_config()
        helper_config = None
        for component in config.components:
            if component.name == "helper":
                helper_config = component
                break

        if not helper_config:
            from .config_models import ComponentConfig

            helper_config = ComponentConfig(name="helper", config={})
            config.components.append(helper_config)

        helper_config.config["enabled"] = True
        if data_file_path:
            helper_config.config["data_file"] = data_file_path

        self.config_manager.save()
        logger.info("AetheriusHelper plugin integration enabled")

    def disable_helper_plugin(self) -> None:
        """
        Disable helper plugin integration."""
        self._helper_enabled = False
        config = self.config_manager.get_config()
        for component in config.components:
            if component.name == "helper":
                component.config["enabled"] = False
                self.config_manager.save()
                break
        logger.info("AetheriusHelper plugin integration disabled")


# Global player data manager instance
_player_data_manager: PlayerDataManager | None = None


def get_player_data_manager() -> PlayerDataManager:
    """
    Get the global player data manager instance.

    Returns:
        Global PlayerDataManager instance
    """
    global _player_data_manager

    if _player_data_manager is None:
        _player_data_manager = PlayerDataManager()

    return _player_data_manager

"""
Repository for handling persistence of player data.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .player_data_models import PlayerData, PlayerLocation, PlayerStats, PlayerInventory

logger = logging.getLogger(__name__)

class PlayerDataRepository:
    """
    Manages the loading and saving of PlayerData objects to/from persistent storage (JSON files).
    This class is solely responsible for I/O operations related to player data files.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/players")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"PlayerDataRepository initialized. Data directory: {self.data_dir}")

    def load_all_players(self) -> Dict[str, PlayerData]:
        """Load all player data from files in the data directory."""
        players_data: Dict[str, PlayerData] = {}
        try:
            for player_file in self.data_dir.glob("*.json"):
                player_name = player_file.stem
                try:
                    with open(player_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    player_data = self._dict_to_player_data(data)
                    players_data[player_name] = player_data
                    logger.debug(f"Loaded player data for {player_name}")
                except Exception as e:
                    logger.error(f"Error loading player data from {player_file}: {e}")
        except Exception as e:
            logger.error(f"Error scanning player data directory {self.data_dir}: {e}")
        return players_data

    def save_player_data(self, player_data: PlayerData) -> bool:
        """Save a single PlayerData object to its corresponding file."""
        if not player_data.name:
            logger.error("Cannot save player data: Player name is missing.")
            return False

        try:
            player_file = self.data_dir / f"{player_data.name}.json"
            data = self._player_data_to_dict(player_data)
            with open(player_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved player data for {player_data.name}")
            return True
        except Exception as e:
            logger.error(f"Error saving player data for {player_data.name}: {e}")
            return False

    def _dict_to_player_data(self, data: Dict[str, Any]) -> PlayerData:
        """Convert dictionary to PlayerData object."""
        location = PlayerLocation(**data['location']) if 'location' in data else None
        stats = PlayerStats(**data['stats']) if 'stats' in data else None
        inventory = PlayerInventory(**data['inventory']) if 'inventory' in data else None

        return PlayerData(
            name=data['name'],
            uuid=data.get('uuid'),
            display_name=data.get('display_name'),
            online=data.get('online', False),
            last_seen=data.get('last_seen'),
            first_join=data.get('first_join'),
            play_time=data.get('play_time', 0.0),
            location=location,
            stats=stats,
            inventory=inventory,
            ip_address=data.get('ip_address'),
            permissions=data.get('permissions', []),
            groups=data.get('groups', []),
            custom_data=data.get('custom_data', {})
        )

    def _player_data_to_dict(self, player_data: PlayerData) -> Dict[str, Any]:
        """Convert PlayerData object to dictionary."""
        data = {
            'name': player_data.name,
            'uuid': player_data.uuid,
            'display_name': player_data.display_name,
            'online': player_data.online,
            'last_seen': player_data.last_seen,
            'first_join': player_data.first_join,
            'play_time': player_data.play_time,
            'ip_address': player_data.ip_address,
            'permissions': player_data.permissions,
            'groups': player_data.groups,
            'custom_data': player_data.custom_data
        }

        if player_data.location:
            data['location'] = player_data.location.__dict__
        if player_data.stats:
            data['stats'] = player_data.stats.__dict__
        if player_data.inventory:
            data['inventory'] = player_data.inventory.__dict__

        return data

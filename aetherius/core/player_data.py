"""Player data management and structured player information API."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Any, Set
from uuid import UUID

from .config import get_config_manager
from .event_manager import get_event_manager, fire_event
from .events import BaseEvent


logger = logging.getLogger(__name__)


@dataclass
class PlayerLocation:
    """Player location information."""
    x: float
    y: float
    z: float
    dimension: str
    yaw: float = 0.0
    pitch: float = 0.0


@dataclass
class PlayerStats:
    """Player statistics and status."""
    health: float = 20.0
    max_health: float = 20.0
    hunger: int = 20
    saturation: float = 5.0
    experience_level: int = 0
    experience_total: int = 0
    game_mode: str = "survival"


@dataclass
class PlayerInventory:
    """Player inventory information."""
    items: List[Dict[str, Any]] = field(default_factory=list)
    armor: List[Dict[str, Any]] = field(default_factory=list)
    offhand: Optional[Dict[str, Any]] = None
    ender_chest: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PlayerData:
    """Complete player data structure."""
    name: str
    uuid: Optional[str] = None
    display_name: Optional[str] = None
    online: bool = False
    last_seen: Optional[float] = None
    first_join: Optional[float] = None
    play_time: float = 0.0
    
    # Detailed player information
    location: Optional[PlayerLocation] = None
    stats: Optional[PlayerStats] = None
    inventory: Optional[PlayerInventory] = None
    
    # Additional metadata
    ip_address: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    custom_data: Dict[str, Any] = field(default_factory=dict)


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
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_manager = get_config_manager()
        self.event_manager = get_event_manager()
        
        # In-memory player data cache
        self._player_cache: Dict[str, PlayerData] = {}
        self._online_players: Set[str] = set()
        
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
        helper_enabled = self.config_manager.get_value("helper_plugin.enabled", False)
        helper_data_path = self.config_manager.get_value(
            "helper_plugin.data_file", 
            str(self._helper_data_file)
        )
        
        self._helper_enabled = helper_enabled
        self._helper_data_file = Path(helper_data_path)
        
        if self._helper_enabled:
            logger.info("AetheriusHelper plugin integration enabled")
        else:
            logger.info("AetheriusHelper plugin integration disabled")
    
    def _load_player_data(self) -> None:
        """Load existing player data from files."""
        try:
            for player_file in self.data_dir.glob("*.json"):
                player_name = player_file.stem
                
                with open(player_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Convert to PlayerData object
                player_data = self._dict_to_player_data(data)
                self._player_cache[player_name] = player_data
                
                logger.debug(f"Loaded player data for {player_name}")
                
        except Exception as e:
            logger.error(f"Error loading player data: {e}")
    
    def _dict_to_player_data(self, data: Dict[str, Any]) -> PlayerData:
        """Convert dictionary to PlayerData object."""
        # Extract location data
        location_data = data.get('location')
        location = None
        if location_data:
            location = PlayerLocation(**location_data)
        
        # Extract stats data
        stats_data = data.get('stats')
        stats = None
        if stats_data:
            stats = PlayerStats(**stats_data)
        
        # Extract inventory data
        inventory_data = data.get('inventory')
        inventory = None
        if inventory_data:
            inventory = PlayerInventory(**inventory_data)
        
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
            data['location'] = {
                'x': player_data.location.x,
                'y': player_data.location.y,
                'z': player_data.location.z,
                'dimension': player_data.location.dimension,
                'yaw': player_data.location.yaw,
                'pitch': player_data.location.pitch
            }
        
        if player_data.stats:
            data['stats'] = {
                'health': player_data.stats.health,
                'max_health': player_data.stats.max_health,
                'hunger': player_data.stats.hunger,
                'saturation': player_data.stats.saturation,
                'experience_level': player_data.stats.experience_level,
                'experience_total': player_data.stats.experience_total,
                'game_mode': player_data.stats.game_mode
            }
        
        if player_data.inventory:
            data['inventory'] = {
                'items': player_data.inventory.items,
                'armor': player_data.inventory.armor,
                'offhand': player_data.inventory.offhand,
                'ender_chest': player_data.inventory.ender_chest
            }
        
        return data
    
    def _save_player_data(self, player_name: str) -> None:
        """Save player data to file."""
        if player_name not in self._player_cache:
            return
        
        try:
            player_file = self.data_dir / f"{player_name}.json"
            data = self._player_data_to_dict(self._player_cache[player_name])
            
            with open(player_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error saving player data for {player_name}: {e}")
    
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
            
            with open(self._helper_data_file, 'r', encoding='utf-8') as f:
                helper_data = json.load(f)
            
            self._last_helper_update = stat.st_mtime
            
            # Process helper data
            players_data = helper_data.get('players', {})
            updated_players = []
            
            for player_name, data in players_data.items():
                if player_name not in self._player_cache:
                    # Create new player data
                    self._player_cache[player_name] = PlayerData(name=player_name)
                
                player_data = self._player_cache[player_name]
                
                # Update player data from helper
                if 'uuid' in data:
                    player_data.uuid = data['uuid']
                if 'display_name' in data:
                    player_data.display_name = data['display_name']
                if 'online' in data:
                    player_data.online = data['online']
                
                # Update location
                if 'location' in data:
                    loc_data = data['location']
                    player_data.location = PlayerLocation(
                        x=loc_data.get('x', 0.0),
                        y=loc_data.get('y', 0.0),
                        z=loc_data.get('z', 0.0),
                        dimension=loc_data.get('dimension', 'overworld'),
                        yaw=loc_data.get('yaw', 0.0),
                        pitch=loc_data.get('pitch', 0.0)
                    )
                
                # Update stats
                if 'stats' in data:
                    stats_data = data['stats']
                    player_data.stats = PlayerStats(
                        health=stats_data.get('health', 20.0),
                        max_health=stats_data.get('max_health', 20.0),
                        hunger=stats_data.get('hunger', 20),
                        saturation=stats_data.get('saturation', 5.0),
                        experience_level=stats_data.get('experience_level', 0),
                        experience_total=stats_data.get('experience_total', 0),
                        game_mode=stats_data.get('game_mode', 'survival')
                    )
                
                # Update inventory
                if 'inventory' in data:
                    inv_data = data['inventory']
                    player_data.inventory = PlayerInventory(
                        items=inv_data.get('items', []),
                        armor=inv_data.get('armor', []),
                        offhand=inv_data.get('offhand'),
                        ender_chest=inv_data.get('ender_chest', [])
                    )
                
                # Update custom data
                if 'custom' in data:
                    player_data.custom_data.update(data['custom'])
                
                # Track online status
                if player_data.online:
                    self._online_players.add(player_name)
                else:
                    self._online_players.discard(player_name)
                
                updated_players.append(player_name)
                
                # Fire update event
                event = PlayerDataUpdatedEvent(player_name, player_data, "helper_plugin")
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
    
    def get_all_players(self) -> Dict[str, PlayerData]:
        """
        Get all player data.
        
        Returns:
            Dictionary mapping player names to PlayerData objects
        """
        return self._player_cache.copy()
    
    def get_online_players(self) -> Dict[str, PlayerData]:
        """
        Get all online players.
        
        Returns:
            Dictionary mapping online player names to PlayerData objects
        """
        return {
            name: data for name, data in self._player_cache.items()
            if data.online
        }
    
    def get_player_count(self) -> int:
        """Get total number of known players."""
        return len(self._player_cache)
    
    def get_online_count(self) -> int:
        """Get number of online players."""
        return len(self._online_players)
    
    def update_player_data(
        self, 
        player_name: str, 
        **kwargs
    ) -> bool:
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
                self._player_cache[player_name] = PlayerData(name=player_name)
            
            player_data = self._player_cache[player_name]
            
            # Update basic fields
            for field in ['uuid', 'display_name', 'online', 'last_seen', 
                         'first_join', 'play_time', 'ip_address']:
                if field in kwargs:
                    setattr(player_data, field, kwargs[field])
            
            # Update lists
            if 'permissions' in kwargs:
                player_data.permissions = kwargs['permissions']
            if 'groups' in kwargs:
                player_data.groups = kwargs['groups']
            if 'custom_data' in kwargs:
                player_data.custom_data.update(kwargs['custom_data'])
            
            # Update online status tracking
            if 'online' in kwargs:
                if kwargs['online']:
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
        x: float, y: float, z: float, 
        dimension: str = "overworld",
        yaw: float = 0.0, 
        pitch: float = 0.0
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
                self._player_cache[player_name] = PlayerData(name=player_name)
            
            player_data = self._player_cache[player_name]
            player_data.location = PlayerLocation(x, y, z, dimension, yaw, pitch)
            
            self._save_player_data(player_name)
            return True
            
        except Exception as e:
            logger.error(f"Error setting location for {player_name}: {e}")
            return False
    
    def set_player_stats(
        self, 
        player_name: str, 
        **stats
    ) -> bool:
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
                self._player_cache[player_name] = PlayerData(name=player_name)
            
            player_data = self._player_cache[player_name]
            
            if player_data.stats is None:
                player_data.stats = PlayerStats()
            
            # Update stats
            for field in ['health', 'max_health', 'hunger', 'saturation',
                         'experience_level', 'experience_total', 'game_mode']:
                if field in stats:
                    setattr(player_data.stats, field, stats[field])
            
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
        
        # Save to config
        self.config_manager.set_value("helper_plugin.enabled", True)
        if data_file_path:
            self.config_manager.set_value("helper_plugin.data_file", data_file_path)
        
        logger.info("AetheriusHelper plugin integration enabled")
    
    def disable_helper_plugin(self) -> None:
        """Disable helper plugin integration."""
        self._helper_enabled = False
        self.config_manager.set_value("helper_plugin.enabled", False)
        logger.info("AetheriusHelper plugin integration disabled")


# Global player data manager instance
_player_data_manager: Optional[PlayerDataManager] = None


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
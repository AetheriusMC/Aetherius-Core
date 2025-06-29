"""Player data models and structures."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


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
    """Player statistics and game metrics."""

    health: float = 20.0
    food_level: int = 20
    xp_level: int = 0
    xp_progress: float = 0.0
    play_time: float = 0.0  # in seconds
    deaths: int = 0
    kills: int = 0
    blocks_broken: int = 0
    blocks_placed: int = 0
    distance_walked: float = 0.0


@dataclass
class PlayerInventory:
    """Player inventory information."""

    items: Dict[str, Any] = field(default_factory=dict)
    armor: Dict[str, Any] = field(default_factory=dict)
    ender_chest: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlayerData:
    """Comprehensive player data structure."""

    uuid: str
    username: str
    display_name: Optional[str] = None
    first_join: Optional[str] = None
    last_join: Optional[str] = None
    last_logout: Optional[str] = None
    is_online: bool = False
    location: Optional[PlayerLocation] = None
    stats: PlayerStats = field(default_factory=PlayerStats)
    inventory: PlayerInventory = field(default_factory=PlayerInventory)
    permissions: Dict[str, bool] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "uuid": self.uuid,
            "username": self.username,
            "display_name": self.display_name,
            "first_join": self.first_join,
            "last_join": self.last_join,
            "last_logout": self.last_logout,
            "is_online": self.is_online,
            "location": (
                {
                    "x": self.location.x,
                    "y": self.location.y,
                    "z": self.location.z,
                    "dimension": self.location.dimension,
                    "yaw": self.location.yaw,
                    "pitch": self.location.pitch,
                }
                if self.location
                else None
            ),
            "stats": {
                "health": self.stats.health,
                "food_level": self.stats.food_level,
                "xp_level": self.stats.xp_level,
                "xp_progress": self.stats.xp_progress,
                "play_time": self.stats.play_time,
                "deaths": self.stats.deaths,
                "kills": self.stats.kills,
                "blocks_broken": self.stats.blocks_broken,
                "blocks_placed": self.stats.blocks_placed,
                "distance_walked": self.stats.distance_walked,
            },
            "inventory": {
                "items": self.inventory.items,
                "armor": self.inventory.armor,
                "ender_chest": self.inventory.ender_chest,
            },
            "permissions": self.permissions,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerData":
        """Create PlayerData from dictionary."""
        location_data = data.get("location")
        location = None
        if location_data:
            location = PlayerLocation(
                x=location_data["x"],
                y=location_data["y"],
                z=location_data["z"],
                dimension=location_data["dimension"],
                yaw=location_data.get("yaw", 0.0),
                pitch=location_data.get("pitch", 0.0),
            )

        stats_data = data.get("stats", {})
        stats = PlayerStats(
            health=stats_data.get("health", 20.0),
            food_level=stats_data.get("food_level", 20),
            xp_level=stats_data.get("xp_level", 0),
            xp_progress=stats_data.get("xp_progress", 0.0),
            play_time=stats_data.get("play_time", 0.0),
            deaths=stats_data.get("deaths", 0),
            kills=stats_data.get("kills", 0),
            blocks_broken=stats_data.get("blocks_broken", 0),
            blocks_placed=stats_data.get("blocks_placed", 0),
            distance_walked=stats_data.get("distance_walked", 0.0),
        )

        inventory_data = data.get("inventory", {})
        inventory = PlayerInventory(
            items=inventory_data.get("items", {}),
            armor=inventory_data.get("armor", {}),
            ender_chest=inventory_data.get("ender_chest", {}),
        )

        return cls(
            uuid=data["uuid"],
            username=data["username"],
            display_name=data.get("display_name"),
            first_join=data.get("first_join"),
            last_join=data.get("last_join"),
            last_logout=data.get("last_logout"),
            is_online=data.get("is_online", False),
            location=location,
            stats=stats,
            inventory=inventory,
            permissions=data.get("permissions", {}),
            metadata=data.get("metadata", {}),
        )
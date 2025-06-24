# AetheriusHelper Plugin Specification

## Overview

AetheriusHelper is a lightweight Minecraft server-side plugin designed to provide deep game data to the Aetherius Core management system. This helper plugin bridges the gap between server log parsing and detailed player/world information that can only be accessed from within the game.

## Purpose

The AetheriusHelper plugin serves as a data bridge that:

1. **Collects detailed player information** that cannot be obtained from server logs
2. **Provides real-time game state data** for web dashboards and monitoring tools
3. **Enables advanced player management features** through structured data export
4. **Maintains minimal performance impact** on the server

## Data Export Format

The plugin exports data to a JSON file that is periodically read by Aetherius Core.

### File Location
- Default: `data/aetherius_helper.json`
- Configurable via Aetherius Core configuration

### Update Frequency
- Every 5 seconds for online player data
- Every 30 seconds for comprehensive world data
- Immediate updates for critical events (player deaths, dimension changes)

## JSON Data Structure

```json
{
  "timestamp": 1640995200000,
  "server_info": {
    "tps": [19.8, 19.9, 20.0],
    "mspt": 15.2,
    "loaded_chunks": 1250,
    "entities": 450,
    "tile_entities": 1200,
    "worlds": ["world", "world_nether", "world_the_end"]
  },
  "players": {
    "PlayerName": {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "display_name": "§6PlayerName",
      "online": true,
      "location": {
        "x": 125.5,
        "y": 64.0,
        "z": -89.3,
        "dimension": "minecraft:overworld",
        "yaw": 45.5,
        "pitch": -10.2
      },
      "stats": {
        "health": 18.5,
        "max_health": 20.0,
        "hunger": 15,
        "saturation": 3.2,
        "experience_level": 25,
        "experience_total": 1250,
        "game_mode": "survival"
      },
      "inventory": {
        "items": [
          {
            "slot": 0,
            "type": "minecraft:diamond_sword",
            "count": 1,
            "nbt": "{Enchantments:[{id:\"minecraft:sharpness\",lvl:3}]}"
          }
        ],
        "armor": [
          {
            "slot": "helmet",
            "type": "minecraft:diamond_helmet",
            "count": 1,
            "nbt": "{}"
          }
        ],
        "offhand": {
          "type": "minecraft:shield",
          "count": 1,
          "nbt": "{}"
        },
        "ender_chest": []
      },
      "custom": {
        "last_death_location": {
          "x": 100.0,
          "y": 65.0,
          "z": -50.0,
          "dimension": "minecraft:overworld"
        },
        "playtime_session": 3600,
        "last_activity": "mining"
      }
    }
  },
  "world_data": {
    "minecraft:overworld": {
      "spawn_location": {
        "x": 0,
        "y": 64,
        "z": 0
      },
      "weather": "clear",
      "time": 6000,
      "difficulty": "normal"
    }
  }
}
```

## Plugin Requirements

### Minecraft Version Support
- Primary: Minecraft 1.20.1+
- Secondary: Minecraft 1.19.x (limited features)
- Platform: Spigot/Paper/Fabric

### Performance Requirements
- Maximum 1ms average tick impact
- Asynchronous data collection where possible
- Configurable update intervals
- Optional features for low-performance servers

### Permissions Integration
- Support for LuckPerms, PermissionsEx, GroupManager
- Extract player permissions and groups
- Role-based data access control

## Plugin Configuration

The AetheriusHelper plugin should have its own configuration file:

```yaml
# config.yml for AetheriusHelper
aetherius:
  # Data export settings
  data_file: "data/aetherius_helper.json"
  update_intervals:
    player_data: 5  # seconds
    world_data: 30  # seconds
    server_stats: 10  # seconds
  
  # Feature toggles
  features:
    player_location: true
    player_inventory: true
    player_stats: true
    world_data: true
    server_performance: true
    permissions: true
  
  # Performance settings
  performance:
    max_players_per_tick: 5
    async_data_collection: true
    cache_duration: 30  # seconds
  
  # Security settings
  security:
    expose_ip_addresses: false
    expose_inventory_nbt: true
    expose_ender_chest: false
```

## API Commands

The plugin should provide commands for integration testing and management:

### Commands
- `/aetherius reload` - Reload plugin configuration
- `/aetherius export` - Force immediate data export
- `/aetherius status` - Show plugin status and performance metrics
- `/aetherius debug <player>` - Show debug information for a specific player

### Permissions
- `aetherius.admin` - Full plugin access
- `aetherius.reload` - Reload configuration
- `aetherius.export` - Force data export
- `aetherius.debug` - Access debug commands

## Integration Points

### With Aetherius Core

1. **Automatic Discovery**: Aetherius Core automatically detects the helper plugin
2. **Configuration Sync**: Core can update helper plugin settings
3. **Health Monitoring**: Core monitors helper plugin performance
4. **Fallback Mode**: Core continues to function without the helper plugin

### With Other Plugins

1. **Economy Plugins**: Extract player balance information
2. **Land Protection**: Get claim/region information
3. **Custom Plugins**: Extensible data collection API

## Development Phases

### Phase 1: Core Data Collection
- Basic player location and stats
- Simple JSON export
- Essential server performance metrics

### Phase 2: Enhanced Features
- Inventory tracking
- World data collection
- Permissions integration

### Phase 3: Advanced Integration
- Custom plugin data collection
- Real-time event streaming
- Advanced performance monitoring

## Security Considerations

### Data Privacy
- Configurable data exposure levels
- IP address anonymization options
- Inventory privacy controls

### Performance Security
- Rate limiting for data collection
- Resource usage monitoring
- Automatic disable on high load

### Access Control
- Plugin command permissions
- Data file access restrictions
- Integration authentication

## Error Handling

### File I/O Errors
- Graceful handling of file write failures
- Automatic retry with exponential backoff
- Fallback to reduced data sets

### Performance Issues
- Automatic feature degradation under load
- Circuit breaker pattern for expensive operations
- Monitoring and alerting integration

### Plugin Conflicts
- Compatibility checking with common plugins
- Graceful degradation when conflicts detected
- Clear error reporting to server administrators

## Testing Requirements

### Unit Tests
- Data collection accuracy
- JSON format validation
- Performance impact measurement

### Integration Tests
- Aetherius Core integration
- Multi-player scenarios
- Long-running stability tests

### Performance Tests
- TPS impact measurement
- Memory usage profiling
- Concurrent player handling

## Installation Guide

### For Server Administrators

1. **Download**: Get AetheriusHelper.jar from releases
2. **Install**: Place in `plugins/` directory
3. **Configure**: Edit `plugins/AetheriusHelper/config.yml`
4. **Start**: Restart server or use plugin manager
5. **Verify**: Check `data/aetherius_helper.json` is created

### For Aetherius Core Integration

1. **Enable**: Set `helper_plugin.enabled: true` in Aetherius config
2. **Configure**: Set data file path if different from default
3. **Test**: Use `aetherius debug helper` command
4. **Monitor**: Check logs for integration status

## Backward Compatibility

### Without Helper Plugin
- Aetherius Core continues normal operation
- Player data limited to log parsing
- No detailed statistics or inventory data
- Graceful degradation of web dashboard features

### Version Updates
- Configuration migration support
- Data format versioning
- Automatic feature detection

## Future Enhancements

### Planned Features
- Real-time WebSocket streaming
- Custom data collection plugins
- Advanced analytics and metrics
- Multi-server support for networks

### API Extensions
- RESTful API for external tools
- Webhook notifications for events
- Custom data export formats
- Integration with external databases

This specification provides the foundation for developing a helper plugin that significantly enhances Aetherius Core's capabilities while maintaining the core principle of lightweight, stable operation.
# Aetherius Core Technical Documentation

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [API Reference](#api-reference)
4. [Plugin Development](#plugin-development)
5. [Component Development](#component-development)
6. [Configuration](#configuration)
7. [Event System](#event-system)
8. [Command Queue System](#command-queue-system)
9. [Development Workflow](#development-workflow)
10. [Testing](#testing)
11. [Performance Considerations](#performance-considerations)

## Architecture Overview

Aetherius is a lightweight, high-performance Minecraft server management engine built with Python 3.11+ using async/await patterns. The system follows an event-driven architecture with a modular plugin and component system.

### Core Design Principles
- **Stability First**: 7x24 hour reliable operation
- **Performance Oriented**: Async I/O with minimal TPS impact
- **Interface Driven**: Clean, stable internal APIs
- **CLI-Centric**: Complete management solution via command line

### System Components Flow
```
CLI Interface
    ↓
Core Engine (AetheriusCore)
    ↓
ServerProcessWrapper ← → EventManager ← → LogParser
    ↓                        ↓              ↓
Minecraft Server         Plugins      Components
```

## Core Components

### 1. ServerProcessWrapper (`aetherius/core/server.py`)

The lowest-level module managing direct interaction with the Minecraft server process.

**Key Features:**
- **Process Management**: Async start, stop (SIGTERM), force kill (SIGKILL), restart
- **Health Monitoring**: Continuous subprocess status monitoring with crash detection
- **I/O Redirection**: Three async pipes for stdout, stderr, stdin
- **Performance Monitoring**: Integrated psutil for detailed process metrics

**API Methods:**
```python
class ServerProcessWrapper:
    async def start(self) -> bool
    async def stop(self, force: bool = False) -> bool
    async def restart(self) -> bool
    async def send_command(self, command: str) -> None
    def is_alive(self) -> bool
    def get_pid(self) -> Optional[int]
    async def get_performance_metrics(self) -> Dict[str, Any]  # NEW
```

**Performance Metrics:**
```python
{
    "cpu_percent": 15.2,
    "memory_mb": 2048.5,
    "memory_percent": 12.3,
    "threads": 45,
    "open_files": 12,
    "connections": 3,
    "uptime_seconds": 3600.0,
    "status": "running",
    "pid": 12345
}
```

**Configuration:**
- Server JAR path: Configurable via `config.yaml`
- Memory settings: Xms, Xmx parameters
- JVM arguments: Custom JVM flags

### 2. Event System (`aetherius/core/event_manager.py`, `aetherius/core/events.py`)

High-performance async event bus with decorator-based listener registration.

**Core Event Types:**
```python
# Server Lifecycle
class ServerStartingEvent(Event): ...
class ServerStartedEvent(Event): ...
class ServerStoppingEvent(Event): ...

# Player Events
class PlayerJoinEvent(Event):
    player_name: str
    timestamp: datetime

class PlayerLeaveEvent(Event):
    player_name: str
    timestamp: datetime

class PlayerChatEvent(Event):
    player_name: str
    message: str
    timestamp: datetime

# System Events
class ServerCrashEvent(Event):
    exit_code: int
    error_output: str
```

**Event Registration:**
```python
from aetherius.core.events import OnEvent, PlayerJoinEvent

@OnEvent(PlayerJoinEvent)
async def handle_player_join(event: PlayerJoinEvent):
    print(f"Player {event.player_name} joined the server!")
```

### 3. Log Parser (`aetherius/core/log_parser.py`)

Converts raw Minecraft server logs into structured events using configurable regex rules.

**Configuration File**: `rules.yaml`
```yaml
patterns:
  player_join:
    regex: '^\[.*\] \[Server thread/INFO\]: (\w+) joined the game$'
    event_type: "PlayerJoinEvent"
    groups:
      - player_name
      
  player_leave:
    regex: '^\[.*\] \[Server thread/INFO\]: (\w+) left the game$'
    event_type: "PlayerLeaveEvent"
    groups:
      - player_name
```

### 4. Command Queue System (`aetherius/core/command_queue.py`)

Cross-process command execution with output capture and feedback.

**Features:**
- File-based command queuing for cross-process communication
- Command output correlation using timing-based matching
- Feedback system for command execution results

**Usage:**
```python
from aetherius.core.command_queue import CommandQueue

queue = CommandQueue()
await queue.execute_command("say Hello World", capture_output=True)
```

### 5. Server State Management (`aetherius/core/server_state.py`)

Global server state management across different process instances.

**State Information:**
- Server PID and status
- Player count and list
- Server performance metrics
- Last command execution results

### 6. Output Capture System (`aetherius/core/output_capture.py`)

Associates server output with executed commands using timing correlation.

**How it works:**
1. Command is sent with timestamp
2. System captures subsequent log output
3. Output is correlated to command based on timing
4. Results are returned to command issuer

### 7. Configuration Manager (`aetherius/core/config.py`)

Enhanced configuration management with unified API for reading and writing configuration values across components and plugins.

**Key Features:**
- **Dot Notation Access**: Access nested config values with `get_value('server.memory.max')`
- **Thread-Safe Operations**: All operations are thread-safe with proper locking
- **Change Callbacks**: Register callbacks for configuration changes
- **Automatic Persistence**: Changes are automatically saved to file

**API Methods:**
```python
config_manager = get_config_manager()

# Get/set values with dot notation
value = config_manager.get_value('components.web.port', 8080)
config_manager.set_value('components.web.port', 8080)

# Section operations
section = config_manager.get_section('components')
config_manager.set_section('components', {'web': {'port': 8080}})

# Advanced operations
config_manager.delete_value('old.setting')
exists = config_manager.has_value('some.key')
keys = config_manager.get_keys('components.')
```

### 8. Player Data Manager (`aetherius/core/player_data.py`)

Structured player data management with support for helper plugin integration.

**Key Features:**
- **Comprehensive Player Data**: Location, stats, inventory, permissions
- **Helper Plugin Integration**: Deep game data via AetheriusHelper.jar
- **Persistent Storage**: Player data cached locally in JSON files
- **Real-time Updates**: Automatic updates when helper plugin data changes

**Player Data Structure:**
```python
@dataclass
class PlayerData:
    name: str
    uuid: Optional[str] = None
    online: bool = False
    location: Optional[PlayerLocation] = None  # x, y, z, dimension, yaw, pitch
    stats: Optional[PlayerStats] = None        # health, hunger, experience, etc.
    inventory: Optional[PlayerInventory] = None # items, armor, offhand
    permissions: List[str] = field(default_factory=list)
    custom_data: Dict[str, Any] = field(default_factory=dict)
```

**API Methods:**
```python
player_manager = get_player_data_manager()

# Get player data
player_data = player_manager.get_player_data('PlayerName')
online_players = player_manager.get_online_players()

# Update data
player_manager.update_player_data('PlayerName', online=True)
player_manager.set_player_location('PlayerName', 100, 64, -50, 'overworld')

# Helper plugin integration
await player_manager.refresh_helper_data()
player_manager.enable_helper_plugin('data/helper.json')
```

## API Reference

### Core API (`aetherius/api/`)

The Core API provides a controlled interface for plugins and components.

```python
from aetherius.api import AetheriusAPI

api = AetheriusAPI()

# Server management
await api.server.start()
await api.server.stop()
await api.server.send_command("say Hello")

# Event system
@api.events.on(PlayerJoinEvent)
async def on_join(event):
    pass

# Configuration access
config = api.config.get('server.memory')
```

### Enhanced API (`aetherius/api/enhanced.py`)

The Enhanced API provides extended functionality for official components with performance monitoring, player data, and unified configuration management.

```python
from aetherius.api.enhanced import EnhancedAetheriusAPI

api = EnhancedAetheriusAPI(server_wrapper)

# Performance monitoring
perf_data = await api.get_server_performance()
await api.start_performance_monitoring(interval=10.0)

# Configuration management with dot notation
api.set_config_value('components.web_dashboard.port', 8080)
port = api.get_config_value('components.web_dashboard.port', 8080)

# Player data access
player_data = api.get_player_data('PlayerName')
online_players = api.get_online_players()
await api.refresh_player_data()  # Update from helper plugin
```

### Plugin API (`aetherius/api/plugin.py`)

```python
from aetherius.api.plugin import PluginBase

class MyPlugin(PluginBase):
    def on_load(self):
        self.logger.info("Plugin loaded")
    
    def on_unload(self):
        self.logger.info("Plugin unloaded")
    
    @OnEvent(PlayerJoinEvent)
    async def on_player_join(self, event):
        await self.send_command(f"say Welcome {event.player_name}!")
```

### Component API (`aetherius/api/component.py`)

```python
from aetherius.api.component import ComponentBase

class WebDashboard(ComponentBase):
    def __init__(self):
        super().__init__()
        self.app = FastAPI()
    
    async def start(self):
        # Component initialization
        pass
    
    async def stop(self):
        # Component cleanup
        pass
```

### Enhanced Component API (`aetherius/api/enhanced.py`)

For official components requiring advanced functionality:

```python
from aetherius.api.enhanced import EnhancedComponent

class WebDashboard(EnhancedComponent):
    async def on_enable(self):
        # Get configuration with automatic component namespacing
        port = self.get_config('port', 8080)  # Gets components.web_dashboard.port
        
        # Access performance metrics
        perf_data = await self.get_performance_metrics()
        
        # Get player data
        online_players = self.get_online_players()
        
        # Send server commands
        await self.send_server_command('say Dashboard enabled')
    
    async def update_dashboard_data(self):
        # Real-time data updates for web interface
        performance = await self.get_performance_metrics()
        players = self.get_online_players()
        
        return {
            'performance': performance,
            'players': {name: {
                'location': p.location.__dict__ if p.location else None,
                'stats': p.stats.__dict__ if p.stats else None
            } for name, p in players.items()}
        }
```

## Plugin Development

### Plugin Structure

Plugins are Python files placed in the `plugins/` directory:

```python
# plugins/welcome_plugin.py
from aetherius.core.events import OnEvent, PlayerJoinEvent

@OnEvent(PlayerJoinEvent)
async def welcome_player(event: PlayerJoinEvent):
    # Send welcome message
    pass

def on_load():
    print("Welcome plugin loaded")

def on_unload():
    print("Welcome plugin unloaded")
```

### Plugin Lifecycle

1. **Discovery**: Plugins are automatically discovered in `plugins/`
2. **Loading**: Module is imported and `on_load()` is called
3. **Registration**: Event handlers are registered
4. **Execution**: Handlers respond to events
5. **Unloading**: `on_unload()` is called during shutdown

### Plugin Management Commands

```bash
aetherius plugin list           # List all plugins
aetherius plugin reload <name>  # Reload specific plugin
aetherius plugin enable <name>  # Enable plugin
aetherius plugin disable <name> # Disable plugin
```

## Component Development

### Component Structure

Components are more complex than plugins and exist in the `components/` directory:

```
components/
└── web_dashboard/
    ├── __init__.py
    ├── component.json      # Metadata
    ├── dashboard.py        # Main component code
    └── requirements.txt    # Dependencies
```

### Component Metadata (`component.json`)

```json
{
    "name": "web_dashboard",
    "version": "1.0.0",
    "description": "Web-based server dashboard",
    "author": "Aetherius Team",
    "dependencies": ["database"],
    "entry_point": "dashboard:WebDashboard"
}
```

### Component Management

```bash
aetherius component list              # List components
aetherius component enable <name>     # Enable component
aetherius component disable <name>    # Disable component
```

## Configuration

### Main Configuration (`config.yaml`)

```yaml
server:
  jar_path: "server/server.jar"
  memory:
    min: "1G"
    max: "4G"
  jvm_args:
    - "-XX:+UseG1GC"
    - "-XX:+ParallelRefProcEnabled"

logging:
  level: "INFO"
  file: "logs/aetherius.log"
  max_size: "10MB"
  backup_count: 5

plugins:
  directory: "plugins"
  auto_reload: true

components:
  directory: "components"
  enabled:
    - "database"
    - "web_dashboard"
  web_dashboard:
    port: 8080
    host: "0.0.0.0"
    enable_ssl: false

# Helper plugin integration (NEW)
helper_plugin:
  enabled: true
  data_file: "data/aetherius_helper.json"
  update_interval: 5.0
```

### Configuration Management

```python
from aetherius.core.config import Config

config = Config.load("config.yaml")
server_memory = config.server.memory.max
```

## Event System

### Event Priority

Events support priority levels for ordered processing:

```python
@OnEvent(PlayerJoinEvent, priority=10)  # Higher priority
async def high_priority_handler(event):
    pass

@OnEvent(PlayerJoinEvent, priority=1)   # Lower priority
async def low_priority_handler(event):
    pass
```

### Event Cancellation

Events can be cancelled to prevent further processing:

```python
@OnEvent(PlayerChatEvent)
async def chat_filter(event: PlayerChatEvent):
    if "spam" in event.message.lower():
        event.cancel()  # Prevents other handlers from processing
```

### Custom Events

```python
from aetherius.core.events import Event, EventManager

class CustomEvent(Event):
    data: str

# Fire custom event
event_manager = EventManager()
await event_manager.fire(CustomEvent(data="Hello"))
```

## Command Queue System

### Cross-Process Commands

The command queue enables sending commands from different processes:

```bash
# From one terminal
aetherius server start

# From another terminal
aetherius cmd "say Hello from another process"
```

### Command with Output Capture

```python
from aetherius.core.command_queue import CommandQueue

queue = CommandQueue()
result = await queue.execute_command("list", capture_output=True, timeout=5.0)
print(f"Players online: {result.output}")
```

## Development Workflow

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd aetherius-core

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Code Quality Commands

```bash
# Lint code
ruff check .

# Format code
black .

# Run tests
pytest

# Run with coverage
pytest --cov=aetherius
```

### CLI Development Commands

```bash
# Start server
aetherius server start

# Interactive console
aetherius console

# Send command
aetherius cmd "say Development test"

# Check server status
aetherius server status
```

## Testing

### Test Structure

```
tests/
├── unit/
│   ├── test_server.py
│   ├── test_events.py
│   └── test_config.py
├── integration/
│   ├── test_full_workflow.py
│   └── test_plugin_loading.py
└── fixtures/
    ├── sample_config.yaml
    └── sample_logs.txt
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_server.py

# Run with coverage
pytest --cov=aetherius --cov-report=html

# Run integration tests only
pytest tests/integration/
```

### Test Examples

```python
import pytest
from aetherius.core.server import ServerProcessWrapper

@pytest.mark.asyncio
async def test_server_start_stop():
    server = ServerProcessWrapper("test-server.jar")
    
    # Test start
    assert await server.start()
    assert server.is_alive()
    
    # Test stop
    assert await server.stop()
    assert not server.is_alive()
```

## AetheriusHelper Plugin Integration

### Overview

The AetheriusHelper plugin is a lightweight Minecraft server-side plugin that provides deep game data to Aetherius Core. It enables access to detailed player information that cannot be obtained from server logs alone.

### Features Provided

1. **Detailed Player Data**: Real-time location, health, hunger, experience, inventory
2. **Server Performance Metrics**: TPS, MSPT, chunk/entity counts
3. **World Information**: Weather, time, spawn locations
4. **Permission Integration**: Player groups and permissions from permission plugins

### Setup

1. **Install Helper Plugin**: Place `AetheriusHelper.jar` in server `plugins/` directory
2. **Enable Integration**: Set `helper_plugin.enabled: true` in Aetherius config
3. **Configure Data File**: Set path to shared data file (default: `data/aetherius_helper.json`)

### Data Format

The helper plugin exports data in JSON format that is automatically consumed by Aetherius Core:

```json
{
  "timestamp": 1640995200000,
  "players": {
    "PlayerName": {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "location": {"x": 125.5, "y": 64.0, "z": -89.3, "dimension": "overworld"},
      "stats": {"health": 18.5, "hunger": 15, "experience_level": 25},
      "inventory": {"items": [...], "armor": [...]}
    }
  },
  "server_info": {
    "tps": [19.8, 19.9, 20.0],
    "loaded_chunks": 1250,
    "entities": 450
  }
}
```

### API Usage

```python
# Enable helper plugin integration
api.enable_helper_plugin('data/aetherius_helper.json')

# Get enhanced player data
player_data = api.get_player_data('PlayerName')
if player_data and player_data.location:
    print(f"Player at {player_data.location.x}, {player_data.location.y}, {player_data.location.z}")

# Refresh data from helper plugin
await api.refresh_player_data()
```

## Performance Considerations

### Async Best Practices

1. **Use async/await consistently**: All I/O operations should be async
2. **Avoid blocking calls**: Use async alternatives for file I/O, network calls
3. **Proper exception handling**: Use try/except in async contexts

### Memory Management

1. **Event listener cleanup**: Properly unregister event listeners
2. **Plugin lifecycle**: Ensure plugins clean up resources
3. **Log rotation**: Configure appropriate log rotation to prevent disk space issues
4. **Player data caching**: Player data is cached in memory and persisted to disk

### Performance Monitoring

The system provides built-in performance monitoring with detailed metrics:

```python
# Get server performance metrics
perf_data = await api.get_server_performance()
print(f"CPU: {perf_data['cpu_percent']}%")
print(f"Memory: {perf_data['memory_mb']}MB")
print(f"Threads: {perf_data['threads']}")

# Start continuous monitoring
await api.start_performance_monitoring(interval=10.0)
```

### Helper Plugin Performance

- **Minimal Impact**: Helper plugin designed for <1ms average tick impact
- **Async Operations**: Data collection happens asynchronously
- **Configurable Updates**: Update intervals can be adjusted for performance
- **Circuit Breakers**: Automatic feature degradation under high load

---

This documentation covers the core technical aspects of Aetherius. For user guides and tutorials, see the main README.md file.
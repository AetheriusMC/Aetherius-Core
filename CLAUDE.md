# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Quick Start
```bash
python scripts/start.py   # Development mode start
./bin/aetherius start     # Full system start
./bin/aetherius web       # Web console only
```

### Testing
```bash
pytest                    # Run tests
python -m pytest -v      # Verbose testing
```

### Code Quality
```bash
ruff check .              # Lint code
black .                   # Format code
```

### Installation
```bash
pip install -e .          # Install in development mode
pip install -e ".[dev]"   # Install with dev dependencies
```

### Server Management
```bash
aetherius start              # Start Aetherius Core
aetherius stop               # Stop server
aetherius restart            # Restart server
aetherius status             # Show server status
aetherius cmd <command>      # Send command to server
aetherius console            # Interactive console mode
aetherius web                # Start web console
```

## Architecture Overview

Aetherius is a Minecraft server management engine built with Python 3.11+ using async/await patterns. The core architecture consists of:

### Core Components
- **ServerProcessWrapper** (`aetherius/core/server.py`): Main class managing the Minecraft server subprocess with async I/O handling, command queuing, output capture, and performance monitoring
- **Enhanced Console Interface** (`aetherius/core/console_interface.py`): Advanced command interface with stdin/stdout primary control and RCON fallback, intelligent connection management, command prioritization, and batch execution
- **Console Manager** (`aetherius/core/console_manager.py`): Singleton manager for console interfaces to prevent duplicate initialization and resource conflicts
- **ConfigManager** (`aetherius/core/config.py`): Enhanced configuration management with unified API, dot notation access, and change callbacks
- **PlayerDataManager** (`aetherius/core/player_data.py`): Structured player data management with helper plugin integration for detailed game information
- **Event System** (`aetherius/core/event_manager.py`, `aetherius/core/events.py`): Async event-driven architecture for server events (player join/leave, chat, death, etc.)
- **Log Parser** (`aetherius/core/log_parser.py`): Parses Minecraft server logs and converts them to typed events
- **Command Queue** (`aetherius/core/command_queue.py`): Cross-process command execution with output capture and file-based queuing
- **Server State** (`aetherius/core/server_state.py`): Global server state management across processes
- **Output Capture** (`aetherius/core/output_capture.py`): Captures and associates server output with executed commands

### Plugin & Component System
- **Plugin Manager** (`aetherius/plugins/`): Extensible plugin system for custom functionality
- **Component Manager** (`aetherius/components/`): Component system for modular features like database and web dashboard
- **Enhanced API** (`aetherius/api/enhanced.py`): Extended functionality for official components with performance monitoring, player data, and unified configuration
- Both systems support loading, enabling/disabling, and hot-reloading

### CLI Interface
- **Main CLI** (`aetherius/cli/main.py`): Rich-based CLI using Typer with colored output and event-driven display
- **Console Mode**: Interactive console with real-time event display and command feedback
- **Cross-process Communication**: Commands work across different process instances

## Key Patterns

### Async Architecture
The entire system is built around asyncio with proper async/await patterns. Server I/O, event handling, and command execution are all asynchronous.

### Event-Driven Design
Server events (player actions, server state changes) are parsed from logs and fired through the event system. CLI handlers display these events with rich formatting.

### Configuration Management
Uses Pydantic models with YAML serialization. Default configuration is automatically created at `config.yaml`.

### Enhanced Console Interface
The new console interface provides dual-mode command execution:
- **Primary**: Direct stdin/stdout communication for maximum efficiency and real-time response
- **Fallback**: RCON protocol when stdin is unavailable or fails
- **Intelligent Switching**: Automatic failover between connection types based on availability
- **Command Prioritization**: LOW/NORMAL/HIGH/CRITICAL priority levels for command execution
- **Batch Execution**: Send multiple commands with automatic priority ordering
- **Script Execution**: Execute command sequences with error handling and progress tracking

### Cross-Process State
The system maintains server state across different CLI invocations using file-based storage and PID tracking.

### Command Output Capture
Commands sent to the server can capture their output using a timing-based correlation system that matches commands to subsequent log output.

### Performance Monitoring
Built-in performance monitoring using psutil provides detailed metrics for CPU usage, memory consumption, thread count, open files, and network connections.

### Player Data Management
Structured player data system supports detailed information including location, stats, inventory, and permissions. Integrates with AetheriusHelper.jar for deep game data access.

## Development Notes

- The project uses Black for formatting (88 char line length) and Ruff for linting
- Configuration is in `pyproject.toml` with comprehensive tool settings
- Server JAR should be placed at `server/server.jar` (configurable)
- Logs are stored in `logs/` directory with rotation
- Plugin/component hot-reloading is supported for development
- The system supports both foreground and background server execution modes

# Aetherius - Minecraft Server Management Engine

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A lightweight, high-performance Minecraft server management engine designed for stability, performance, and extensibility.

## Features

- **Lightweight & Fast**: Minimal resource usage with async I/O
- **Stable**: Built for 24/7 operation with robust error handling
- **Extensible**: Plugin and component system for custom functionality
- **CLI-First**: Powerful command-line interface for server management
- **Auto-Restart**: Automatic server restart on crashes
- **Real-time Monitoring**: Live server output and detailed performance metrics
- **Player Data Management**: Structured player information with helper plugin support
- **Enhanced Configuration**: Unified configuration API with dot notation access
- **Performance Monitoring**: Built-in CPU, memory, and resource monitoring

## Installation

### Requirements

- Python 3.11 or higher
- Java 17 or higher (for Minecraft server)
- A Minecraft server JAR file

### Install from PyPI (Coming Soon)

```bash
pip install aetherius
```

### Install from Source

```bash
git clone https://github.com/AetheriusMC/Aetherius-Core.git
cd Aetherius-Core
pip install -e .
```

## Quick Start

1. **Setup your server**:
   ```bash
   mkdir server
   # Place your server.jar in the server/ directory
   cp /path/to/your/server.jar server/server.jar
   ```

2. **Start the server**:
   ```bash
   aetherius server start
   ```

3. **Check server status**:
   ```bash
   aetherius server status
   ```

4. **Send commands to server**:
   ```bash
   aetherius cmd "say Hello World"
   ```

5. **Interactive console**:
   ```bash
   aetherius console
   ```

## CLI Commands

### Server Management

- `aetherius server start` - Start the Minecraft server
- `aetherius server stop` - Stop the server gracefully
- `aetherius server restart` - Restart the server
- `aetherius server status` - Show server status

### Server Interaction

- `aetherius cmd <command>` - Send command to server
- `aetherius console` - Interactive console mode

### Configuration

Configuration is managed through `config.yaml`:

```yaml
server:
  jar_path: server/server.jar
  java_executable: java
  java_args:
    - -Xmx2G
    - -Xms1G
  server_args:
    - --nogui
  working_directory: server
  auto_restart: true
  restart_delay: 5.0

logging:
  level: INFO
  file_path: logs/aetherius.log
  console_output: true
```

## Architecture

Aetherius Core consists of several key components:

- **ServerProcessWrapper**: Manages the Minecraft server process with performance monitoring
- **ConfigManager**: Enhanced configuration management with unified API
- **PlayerDataManager**: Structured player data with helper plugin integration
- **Event System**: Real-time event processing with async architecture
- **Plugin System**: Extensible plugin architecture for custom functionality
- **Component System**: Heavy-weight component system for official features
- **CLI**: Full-featured command-line interface with rich output
- **Enhanced API**: Extended functionality for official components

## Development

### Setup Development Environment

```bash
git clone https://github.com/AetheriusMC/Aetherius-Core.git
cd Aetherius-Core
pip install -e ".[dev]"
pre-commit install
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
ruff check .
black .
```

## Roadmap

### Phase 1 - Core Engine (Current)

- [x] **Sprint 1**: Basic server process management and CLI
- [x] **Sprint 2**: Log parsing and event system
- [x] **Sprint 3**: Plugin system and basic extensibility
- [x] **Sprint 4**: Complete CLI functionality and Alpha release
- [x] **Enhanced APIs**: Performance monitoring, player data, unified configuration

### Future Phases

- **Phase 2**: Web interface and dashboard
- **Phase 3**: Advanced monitoring and metrics
- **Phase 4**: Multi-server management
- **Phase 5**: Cloud integration and scaling

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- [Documentation](https://docs.aetherius.mc) (Coming Soon)
- [Issue Tracker](https://github.com/AetheriusMC/Aetherius-Core/issues)
- [Discord Server](https://discord.gg/aetherius) (Coming Soon)

---

**Note**: This is an Alpha release (v0.1.0-alpha). Features and APIs may change before the stable release.

# Contributing to Aetherius

Thank you for your interest in contributing to Aetherius! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- Basic knowledge of async Python programming

### Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/YourUsername/Aetherius-Core.git
   cd Aetherius-Core
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks:**
   ```bash
   pre-commit install
   ```

## Development Workflow

### Code Style

This project uses:
- **Black** for code formatting (88 character line length)
- **Ruff** for linting and import sorting
- **MyPy** for type checking

Run code quality checks:
```bash
ruff check .          # Lint code
black .               # Format code
mypy aetherius/       # Type checking
```

### Testing

Run tests before submitting:
```bash
pytest                # Run all tests
pytest -v             # Verbose output
pytest --cov         # With coverage report
```

### Commit Guidelines

- Use conventional commit messages:
  - `feat:` - New features
  - `fix:` - Bug fixes
  - `docs:` - Documentation changes
  - `refactor:` - Code refactoring
  - `test:` - Test additions/changes
  - `chore:` - Maintenance tasks

Example:
```
feat: add command prefix recognition to console

- Implement CommandPrefixManager class
- Add support for /, !, @, # command prefixes
- Update console logic to distinguish command types
```

## Architecture Guidelines

### Core Principles

1. **Async First**: Use async/await patterns for I/O operations
2. **Event-Driven**: Leverage the event system for loose coupling
3. **Type Safety**: Use proper type hints and Pydantic models
4. **Error Handling**: Implement robust error handling and logging
5. **Extensibility**: Design for plugin and component extensibility

### Code Organization

```
aetherius/
├── core/           # Core engine functionality
├── api/            # Public APIs for plugins/components
├── cli/            # Command-line interface
├── plugins/        # Plugin system
└── components/     # Component system
```

### Adding New Features

1. **Core Features**: Add to `aetherius/core/`
2. **CLI Commands**: Add to `aetherius/cli/main.py`
3. **Events**: Define in `aetherius/core/events.py`
4. **APIs**: Public interfaces in `aetherius/api/`

## Plugin Development

### Creating a Plugin

```python
from aetherius.api.plugin import Plugin, PluginInfo
from aetherius.core.events import PlayerJoinEvent
from aetherius.core.event_manager import on_event

PLUGIN_INFO = PluginInfo(
    name="my_plugin",
    version="1.0.0",
    description="Example plugin",
    author="Your Name",
    api_version="1.0.0"
)

class MyPlugin(Plugin):
    async def on_enable(self):
        self.logger.info("Plugin enabled!")

    @on_event(PlayerJoinEvent)
    async def on_player_join(self, event):
        self.logger.info(f"Player {event.player_name} joined!")
```

## Component Development

### Creating a Component

```python
from aetherius.api.component import Component, ComponentInfo

COMPONENT_INFO = ComponentInfo(
    name="my_component",
    version="1.0.0",
    description="Example component",
    author="Your Name",
    api_version="1.0.0",
    depends=["database"],  # Hard dependencies
    soft_depends=["web_dashboard"]  # Optional dependencies
)

class MyComponent(Component):
    async def on_load(self):
        # Component loading logic
        pass

    async def on_enable(self):
        # Component enable logic
        pass
```

## Submitting Changes

### Pull Request Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes and commit:**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

3. **Push and create a pull request:**
   ```bash
   git push origin feature/your-feature-name
   ```

### Pull Request Guidelines

- Provide a clear description of changes
- Reference any related issues
- Include tests for new functionality
- Ensure all checks pass
- Keep commits focused and atomic

### Review Process

1. Automated checks must pass
2. Code review by maintainers
3. Testing in development environment
4. Approval and merge

## Reporting Issues

### Bug Reports

Include:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (Python version, OS, etc.)
- Relevant logs or error messages

### Feature Requests

Include:
- Clear description of the feature
- Use case and motivation
- Proposed implementation approach (optional)

## Community Guidelines

- Be respectful and inclusive
- Help others learn and grow
- Follow the code of conduct
- Ask questions when uncertain

## Getting Help

- Check existing documentation
- Search for existing issues
- Join our Discord server (coming soon)
- Ask questions in discussions

Thank you for contributing to Aetherius!

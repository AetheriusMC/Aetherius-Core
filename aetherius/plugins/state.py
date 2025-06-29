"""Plugin state management for persistent plugin loading."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PluginState:
    """Manages plugin state persistence."""

    def __init__(self, state_file: Path | None = None):
        self.state_file = state_file or Path("plugins/.plugin_state.json")
        self.loaded_plugins: set[str] = set()
        self.enabled_plugins: set[str] = set()

        # Ensure directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state
        self.load_state()

    def load_state(self) -> None:
        """Load plugin state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self.loaded_plugins = set(data.get("loaded", []))
                    self.enabled_plugins = set(data.get("enabled", []))
                    logger.debug(
                        f"Loaded plugin state: {len(self.loaded_plugins)} loaded, {len(self.enabled_plugins)} enabled"
                    )
        except Exception as e:
            logger.error(f"Error loading plugin state: {e}")
            self.loaded_plugins = set()
            self.enabled_plugins = set()

    def save_state(self) -> None:
        """Save plugin state to file."""
        try:
            data = {
                "loaded": list(self.loaded_plugins),
                "enabled": list(self.enabled_plugins),
            }

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug(
                f"Saved plugin state: {len(self.loaded_plugins)} loaded, {len(self.enabled_plugins)} enabled"
            )
        except Exception as e:
            logger.error(f"Error saving plugin state: {e}")

    def add_loaded_plugin(self, name: str) -> None:
        """Mark a plugin as loaded."""
        self.loaded_plugins.add(name)
        self.save_state()

    def remove_loaded_plugin(self, name: str) -> None:
        """Mark a plugin as unloaded."""
        self.loaded_plugins.discard(name)
        self.enabled_plugins.discard(name)
        self.save_state()

    def add_enabled_plugin(self, name: str) -> None:
        """Mark a plugin as enabled."""
        self.enabled_plugins.add(name)
        self.save_state()

    def remove_enabled_plugin(self, name: str) -> None:
        """Mark a plugin as disabled."""
        self.enabled_plugins.discard(name)
        self.save_state()

    def is_loaded(self, name: str) -> bool:
        """Check if a plugin should be loaded."""
        return name in self.loaded_plugins

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin should be enabled."""
        return name in self.enabled_plugins

    def get_loaded_plugins(self) -> set[str]:
        """Get set of plugins that should be loaded."""
        return self.loaded_plugins.copy()

    def get_enabled_plugins(self) -> set[str]:
        """Get set of plugins that should be enabled."""
        return self.enabled_plugins.copy()

    def clear(self) -> None:
        """Clear all plugin state."""
        self.loaded_plugins.clear()
        self.enabled_plugins.clear()
        self.save_state()

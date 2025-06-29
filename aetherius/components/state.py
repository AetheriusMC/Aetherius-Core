"""Component state management for Aetherius components."""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..api.component import ComponentInfo


class ComponentState:
    """Manages persistent state for components."""

    def __init__(self, state_file: Path = Path("components/.component_state.json")):
        """Initialize component state manager.

        Args:
            state_file: Path to state file
        """
        self.state_file = state_file
        self.logger = logging.getLogger("aetherius.components.state")

        # Component state
        self._loaded: set[str] = set()
        self._enabled: set[str] = set()
        self._metadata: dict[str, dict] = {}

        # Load existing state
        self.load()

    def load(self) -> None:
        """Load component state from file."""
        if not self.state_file.exists():
            self.logger.debug("No component state file found, starting fresh")
            return

        try:
            with open(self.state_file) as f:
                data = json.load(f)

            self._loaded = set(data.get("loaded", []))
            self._enabled = set(data.get("enabled", []))
            self._metadata = data.get("metadata", {})

            self.logger.debug(
                f"Loaded component state: {len(self._loaded)} loaded, {len(self._enabled)} enabled"
            )

        except Exception as e:
            self.logger.error(f"Failed to load component state: {e}")
            # Reset to clean state on error
            self._loaded.clear()
            self._enabled.clear()
            self._metadata.clear()

    def save(self) -> None:
        """Save component state to file."""
        # Ensure directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                "loaded": list(self._loaded),
                "enabled": list(self._enabled),
                "metadata": self._metadata,
            }

            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)

            self.logger.debug("Saved component state")

        except Exception as e:
            self.logger.error(f"Failed to save component state: {e}")

    def add_loaded(self, name: str, info: 'ComponentInfo') -> None:
        """Mark a component as loaded.

        Args:
            name: Component name
            info: Component information
        """
        self._loaded.add(name)
        self._metadata[name] = {
            "version": info.version,
            "path": f"components/{name}",
            "depends": info.depends,
            "soft_depends": info.soft_depends,
        }
        self.logger.debug(f"Marked component {name} as loaded")

    def remove_loaded(self, name: str) -> None:
        """Mark a component as not loaded.

        Args:
            name: Component name
        """
        self._loaded.discard(name)
        self._enabled.discard(name)  # Can't be enabled if not loaded
        self._metadata.pop(name, None)
        self.logger.debug(f"Marked component {name} as not loaded")

    def add_enabled(self, name: str) -> None:
        """Mark a component as enabled.

        Args:
            name: Component name
        """
        if name in self._loaded:
            self._enabled.add(name)
            self.logger.debug(f"Marked component {name} as enabled")
        else:
            self.logger.warning(f"Cannot enable component {name}: not loaded")

    def remove_enabled(self, name: str) -> None:
        """Mark a component as disabled.

        Args:
            name: Component name
        """
        self._enabled.discard(name)
        self.logger.debug(f"Marked component {name} as disabled")

    def is_loaded(self, name: str) -> bool:
        """Check if a component is loaded.

        Args:
            name: Component name

        Returns:
            True if component is loaded
        """
        return name in self._loaded

    def is_enabled(self, name: str) -> bool:
        """Check if a component is enabled.

        Args:
            name: Component name

        Returns:
            True if component is enabled
        """
        return name in self._enabled

    def get_loaded(self) -> list[str]:
        """Get list of loaded component names.

        Returns:
            List of loaded component names
        """
        return list(self._loaded)

    def get_enabled(self) -> list[str]:
        """Get list of enabled component names.

        Returns:
            List of enabled component names
        """
        return list(self._enabled)

    def get_metadata(self, name: str) -> dict:
        """Get metadata for a component.

        Args:
            name: Component name

        Returns:
            Component metadata dictionary
        """
        return self._metadata.get(name, {})

    def clear(self) -> None:
        """Clear all component state."""
        self._loaded.clear()
        self._enabled.clear()
        self._metadata.clear()
        self.logger.info("Cleared all component state")

"""
Configuration management for Aetherius.

This module provides a centralized and type-safe way to manage the application's
configuration. It uses Pydantic for data validation and structure, ensuring that
all configuration is well-defined and easily accessible throughout the application.
"""

import threading
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from .config_models import AetheriusConfig


class ConfigManager:
    """
    Manages the application's configuration, providing a single source of truth.

    This class is responsible for loading the configuration from a YAML file,
    validating it against the Pydantic models, and providing a type-safe way
    to access the configuration settings.
    """

    def __init__(self, config_path: Optional[Path] = None, auto_create: bool = True):
        """Initialize the configuration manager."""
        self.config_path = config_path or Path("config.yaml")
        self._lock = threading.RLock()
        self.config: AetheriusConfig = self._load(auto_create=auto_create)

    def _load(self, auto_create: bool) -> AetheriusConfig:
        """Load configuration from the YAML file and parse it into Pydantic models."""
        if self.config_path.exists():
            with open(self.config_path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
                try:
                    return AetheriusConfig(**config_data)
                except ValidationError as e:
                    # Handle validation errors, e.g., log them or raise an exception
                    print(f"Configuration validation error: {e}")
                    # Depending on desired behavior, you might want to exit or use defaults
                    return AetheriusConfig()  # Fallback to default config
        elif auto_create:
            print(
                f"Configuration file not found at {self.config_path}. Creating a default one."
            )
            default_config = AetheriusConfig()
            self.save(default_config)
            return default_config
        else:
            # If not auto-creating, start with a default, in-memory config
            return AetheriusConfig()

    def save(self, config_model: Optional[AetheriusConfig] = None) -> bool:
        """
        Save the current configuration to the YAML file.

        Args:
            config_model: If provided, this model will be saved. Otherwise, the
                          manager's current config is used.

        Returns:
            True if saved successfully, False otherwise.
        """
        with self._lock:
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                data_to_save = config_model or self.config
                with open(self.config_path, "w", encoding="utf-8") as f:
                    yaml.dump(
                        data_to_save.model_dump(),
                        f,
                        default_flow_style=False,
                        allow_unicode=True,
                        indent=2,
                    )
                return True
            except Exception as e:
                print(f"Error saving config: {e}")
                return False

    def reload(self) -> bool:
        """
        Reload the configuration from the file.

        Returns:
            True if reloaded successfully, False otherwise.
        """
        with self._lock:
            try:
                self.config = self._load(auto_create=False)
                return True
            except Exception as e:
                print(f"Error reloading config: {e}")
                return False

    def get_config(self) -> AetheriusConfig:
        """Returns the current, type-safe configuration object."""
        with self._lock:
            return self.config


# --- Global Instance Management ---

_config_manager: Optional[ConfigManager] = None
_config_lock = threading.Lock()


def get_config_manager(config_path: Path | None = None) -> ConfigManager:
    """
    Get the global singleton instance of the ConfigManager.

    This ensures that the configuration is loaded only once and that all parts
    of the application share the same configuration state.

    Args:
        config_path: The path to the configuration file. This is only used
                     during the first call to initialize the manager.

    Returns:
        The singleton ConfigManager instance.
    """
    global _config_manager

    if _config_manager is None:
        with _config_lock:
            if _config_manager is None:
                _config_manager = ConfigManager(config_path)
    return _config_manager

"""Configuration management for Aetherius."""

import os
from pathlib import Path
from typing import Optional, Any, Dict, List
import threading
from copy import deepcopy

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server configuration settings."""
    
    jar_path: str = Field(default="server/server.jar", description="Path to server JAR file")
    java_executable: str = Field(default="java", description="Java executable path")
    java_args: list[str] = Field(
        default=["-Xmx2G", "-Xms1G"],
        description="JVM arguments"
    )
    server_args: list[str] = Field(
        default=["--nogui"],
        description="Server arguments"
    )
    working_directory: str = Field(default="server", description="Server working directory")
    auto_restart: bool = Field(default=True, description="Auto restart on crash")
    restart_delay: float = Field(default=5.0, description="Delay before restart (seconds)")


class LoggingConfig(BaseModel):
    """Logging configuration settings."""
    
    level: str = Field(default="INFO", description="Log level")
    file_path: str = Field(default="logs/aetherius.log", description="Log file path")
    max_file_size: int = Field(default=10 * 1024 * 1024, description="Max log file size (bytes)")
    backup_count: int = Field(default=5, description="Number of log files to keep")
    console_output: bool = Field(default=True, description="Enable console output")


class Config(BaseModel):
    """Main configuration for Aetherius."""
    
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # Dynamic configuration for components and plugins
    components: Dict[str, Any] = Field(default_factory=dict)
    plugins: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def load_from_file(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = Path("config.yaml")
        
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
                return cls(**config_data)
        else:
            # Create default config file
            config = cls()
            config.save_to_file(config_path)
            return config
    
    def save_to_file(self, config_path: Path) -> None:
        """Save configuration to YAML file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                self.model_dump(),
                f,
                default_flow_style=False,
                allow_unicode=True,
                indent=2
            )


class ConfigManager:
    """
    Enhanced configuration manager with unified API for reading and writing
    configuration values across components and plugins.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager."""
        self.config_path = config_path or Path("config.yaml")
        self.config = Config.load_from_file(self.config_path)
        self._lock = threading.RLock()
        self._change_callbacks: List[callable] = []
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key: Configuration key in dot notation (e.g., 'server.memory.max')
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
            
        Examples:
            config_manager.get_value('server.jar_path')
            config_manager.get_value('components.web_dashboard.port', 8080)
            config_manager.get_value('plugins.player_tracker.enabled', True)
        """
        with self._lock:
            try:
                keys = key.split('.')
                value = self.config.model_dump()
                
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return default
                
                return value
            except Exception:
                return default
    
    def set_value(self, key: str, value: Any, save: bool = True) -> bool:
        """
        Set a configuration value using dot notation.
        
        Args:
            key: Configuration key in dot notation
            value: Value to set
            save: Whether to save to file immediately
            
        Returns:
            True if set successfully, False otherwise
            
        Examples:
            config_manager.set_value('components.web_dashboard.port', 8080)
            config_manager.set_value('server.auto_restart', False)
        """
        with self._lock:
            try:
                keys = key.split('.')
                config_dict = self.config.model_dump()
                
                # Navigate to the parent of the target key
                current = config_dict
                for k in keys[:-1]:
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                
                # Set the final value
                current[keys[-1]] = value
                
                # Recreate config object
                self.config = Config(**config_dict)
                
                if save:
                    self.save()
                
                # Notify callbacks
                self._notify_change_callbacks(key, value)
                
                return True
                
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error setting config value {key}: {e}")
                return False
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get an entire configuration section.
        
        Args:
            section: Section name (e.g., 'server', 'components', 'plugins')
            
        Returns:
            Dictionary containing the section data
        """
        with self._lock:
            return deepcopy(self.get_value(section, {}))
    
    def set_section(self, section: str, data: Dict[str, Any], save: bool = True) -> bool:
        """
        Set an entire configuration section.
        
        Args:
            section: Section name
            data: Section data
            save: Whether to save to file immediately
            
        Returns:
            True if set successfully, False otherwise
        """
        return self.set_value(section, data, save)
    
    def delete_value(self, key: str, save: bool = True) -> bool:
        """
        Delete a configuration value.
        
        Args:
            key: Configuration key in dot notation
            save: Whether to save to file immediately
            
        Returns:
            True if deleted successfully, False otherwise
        """
        with self._lock:
            try:
                keys = key.split('.')
                config_dict = self.config.model_dump()
                
                # Navigate to the parent of the target key
                current = config_dict
                for k in keys[:-1]:
                    if k not in current:
                        return False  # Key doesn't exist
                    current = current[k]
                
                # Delete the final key
                if keys[-1] in current:
                    del current[keys[-1]]
                    
                    # Recreate config object
                    self.config = Config(**config_dict)
                    
                    if save:
                        self.save()
                    
                    # Notify callbacks
                    self._notify_change_callbacks(key, None)
                    
                    return True
                else:
                    return False  # Key doesn't exist
                    
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error deleting config value {key}: {e}")
                return False
    
    def has_value(self, key: str) -> bool:
        """
        Check if a configuration key exists.
        
        Args:
            key: Configuration key in dot notation
            
        Returns:
            True if key exists, False otherwise
        """
        return self.get_value(key, object()) is not object()
    
    def get_keys(self, prefix: str = "") -> List[str]:
        """
        Get all configuration keys with optional prefix filter.
        
        Args:
            prefix: Key prefix to filter by
            
        Returns:
            List of configuration keys
        """
        def _get_keys(obj: Any, current_prefix: str = "") -> List[str]:
            keys = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    key = f"{current_prefix}.{k}" if current_prefix else k
                    keys.append(key)
                    if isinstance(v, dict):
                        keys.extend(_get_keys(v, key))
            return keys
        
        all_keys = _get_keys(self.config.model_dump())
        
        if prefix:
            return [k for k in all_keys if k.startswith(prefix)]
        return all_keys
    
    def save(self) -> bool:
        """
        Save configuration to file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        with self._lock:
            try:
                self.config.save_to_file(self.config_path)
                return True
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error saving config: {e}")
                return False
    
    def reload(self) -> bool:
        """
        Reload configuration from file.
        
        Returns:
            True if reloaded successfully, False otherwise
        """
        with self._lock:
            try:
                self.config = Config.load_from_file(self.config_path)
                return True
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error reloading config: {e}")
                return False
    
    def add_change_callback(self, callback: callable) -> None:
        """
        Add a callback function to be called when configuration changes.
        
        Args:
            callback: Function to call with (key, value) arguments
        """
        with self._lock:
            if callback not in self._change_callbacks:
                self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: callable) -> None:
        """
        Remove a configuration change callback.
        
        Args:
            callback: Callback function to remove
        """
        with self._lock:
            if callback in self._change_callbacks:
                self._change_callbacks.remove(callback)
    
    def _notify_change_callbacks(self, key: str, value: Any) -> None:
        """Notify all change callbacks."""
        for callback in self._change_callbacks:
            try:
                callback(key, value)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error in config change callback: {e}")


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None
_config_lock = threading.Lock()


def get_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
    """
    Get the global configuration manager instance.
    
    Args:
        config_path: Path to configuration file (only used on first call)
        
    Returns:
        Global ConfigManager instance
    """
    global _config_manager
    
    with _config_lock:
        if _config_manager is None:
            _config_manager = ConfigManager(config_path)
        return _config_manager
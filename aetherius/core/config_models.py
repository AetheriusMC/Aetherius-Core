"""
Pydantic models for Aetherius configuration.

This module defines the data structures for all configuration used in the Aetherius
core system. It uses Pydantic to ensure type safety, validation, and to provide
a clear, self-documenting structure for the configuration.
"""
from pydantic import BaseModel, Field, FilePath, DirectoryPath, HttpUrl
from typing import List, Dict, Optional, Literal, Any

class ServerConfig(BaseModel):
    """Minecraft server specific settings."""
    jar_path: FilePath = Field("server/server.jar", description="Path to the server.jar file.")
    eula_accepted: bool = Field(False, description="Must be true to start the server.")
    jvm_args: List[str] = Field(default_factory=lambda: ["-Xms2G", "-Xmx4G"], description="JVM arguments for running the server.")
    properties: Dict[str, str] = Field(default_factory=dict, description="Server properties to be written to server.properties.")

class LoggingConfig(BaseModel):
    """Configuration for logging."""
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field("INFO", description="The logging level.")
    directory: DirectoryPath = Field("logs", description="Directory to store log files.")
    console_format: str = Field("[%(asctime)s] [%(levelname)s] %(message)s", description="Format for console log messages.")
    file_format: str = Field("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", description="Format for file log messages.")

class APIConfig(BaseModel):
    """Configuration for the Aetherius API."""
    enabled: bool = Field(True, description="Enable or disable the API.")
    host: str = Field("127.0.0.1", description="Host for the API server.")
    port: int = Field(8080, ge=1024, le=65535, description="Port for the API server.")
    
class WebComponentConfig(BaseModel):
    """Configuration specific to the Web Console component."""
    web_host: str = Field("0.0.0.0", description="Web server listening host.")
    web_port: int = Field(8080, ge=1024, le=65535, description="Web server port.")
    cors_origins: List[str] = Field(default_factory=list, description="Allowed CORS origins.")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field("INFO", description="Logging level for the web component.")
    max_log_lines: int = Field(1000, gt=0, description="Maximum console log lines to buffer.")
    websocket_timeout: int = Field(60, ge=10, description="WebSocket connection timeout in seconds.")
    enable_file_manager: bool = Field(True, description="Enable the file manager feature.")
    enable_player_management: bool = Field(True, description="Enable the player management feature.")

class ComponentConfig(BaseModel):
    """Generic component configuration."""
    name: str
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)

class AetheriusConfig(BaseModel):
    """The main Aetherius configuration model."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    components: List[ComponentConfig] = Field(default_factory=list)
    plugins: List[str] = Field(default_factory=list, description="List of enabled plugins.")

    class Config:
        """Pydantic configuration."""
        extra = "ignore" # Ignore extra fields from the config file

"""
Hello World Plugin for Aetherius

This is a simple example plugin demonstrating the basic plugin API.
"""

from aetherius.api import on_enable, on_disable, on_load, on_unload
from aetherius.core import on_event, PlayerJoinEvent, PlayerChatEvent

# Plugin metadata
PLUGIN_INFO = {
    "name": "HelloWorld", 
    "version": "1.0.0",
    "description": "A simple Hello World plugin for Aetherius",
    "author": "Aetherius Team",
    "website": "https://github.com/AetheriusMC/Aetherius-Core"
}


# Plugin lifecycle hooks
@on_load
async def load_plugin(context):
    """Called when the plugin is loaded."""
    context.logger.info("Hello World plugin loaded!")


@on_enable
async def enable_plugin(context):
    """Called when the plugin is enabled."""
    context.logger.info("Hello World plugin enabled!")
    
    # Send a welcome message to the server
    await context.send_server_command("say Hello World plugin is now active!")


@on_disable
async def disable_plugin(context):
    """Called when the plugin is disabled."""
    context.logger.info("Hello World plugin disabled!")
    
    # Send a goodbye message to the server
    await context.send_server_command("say Hello World plugin is now disabled!")


@on_unload
async def unload_plugin(context):
    """Called when the plugin is unloaded."""
    context.logger.info("Hello World plugin unloaded!")


# Event handlers
@on_event(PlayerJoinEvent)
async def on_player_join(event: PlayerJoinEvent):
    """Welcome new players."""
    print(f"🎮 [HelloWorld] Welcome {event.player_name} to the server!")


@on_event(PlayerChatEvent)
async def on_player_chat(event: PlayerChatEvent):
    """Respond to specific chat messages."""
    message = event.message.lower()
    
    if "hello" in message:
        print(f"👋 [HelloWorld] {event.player_name} said hello!")
    elif "help" in message and "plugin" in message:
        print(f"ℹ️  [HelloWorld] {event.player_name} needs plugin help!")
    elif message == "!version":
        print(f"📦 [HelloWorld] Plugin version: {PLUGIN_INFO['version']}")


# Additional utility functions (can be called by other plugins)
def get_greeting_message():
    """Get a greeting message."""
    return "Hello from the HelloWorld plugin!"


def get_plugin_stats():
    """Get plugin statistics."""
    return {
        "name": PLUGIN_INFO["name"],
        "version": PLUGIN_INFO["version"],
        "events_handled": ["PlayerJoinEvent", "PlayerChatEvent"],
        "features": ["welcome_messages", "chat_responses", "utility_functions"]
    }
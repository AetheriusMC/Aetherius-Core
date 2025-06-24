"""
Player Tracker Plugin for Aetherius

This plugin tracks player activity and maintains statistics.
"""

import json
from datetime import datetime
from pathlib import Path

from aetherius.api import Plugin, PluginInfo
from aetherius.core import on_event, PlayerJoinEvent, PlayerLeaveEvent, PlayerChatEvent

# Plugin metadata
PLUGIN_INFO = PluginInfo(
    name="PlayerTracker",
    version="1.2.0", 
    description="Tracks player activity and maintains statistics",
    author="Aetherius Team",
    website="https://github.com/AetheriusMC/Aetherius-Core",
    depends=[],
    soft_depends=["HelloWorld"],
    api_version="0.1.0"
)


class PlayerTrackerPlugin(Plugin):
    """Player tracking plugin using class-based approach."""
    
    def __init__(self):
        super().__init__()
        self.player_data = {}
        self.session_data = {}
        self.data_file = None
    
    async def on_load(self):
        """Initialize plugin data."""
        self.data_file = self.get_data_folder() / "player_data.json"
        await self.load_player_data()
        
        # Register event handlers
        self.context.event_manager.register_listener(PlayerJoinEvent, self.on_player_join)
        self.context.event_manager.register_listener(PlayerLeaveEvent, self.on_player_leave)
        self.context.event_manager.register_listener(PlayerChatEvent, self.on_player_chat)
        
        self.get_logger().info("Player Tracker plugin loaded!")
    
    async def on_enable(self):
        """Enable the plugin."""
        self.get_logger().info("Player Tracker plugin enabled!")
        await self.context.send_server_command("say Player tracking is now active!")
    
    async def on_disable(self):
        """Disable the plugin."""
        await self.save_player_data()
        self.get_logger().info("Player Tracker plugin disabled!")
        await self.context.send_server_command("say Player tracking is now disabled!")
    
    async def on_unload(self):
        """Clean up resources."""
        await self.save_player_data()
        self.get_logger().info("Player Tracker plugin unloaded!")
    
    async def load_player_data(self):
        """Load player data from file."""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.player_data = json.load(f)
                self.get_logger().info(f"Loaded data for {len(self.player_data)} players")
            else:
                self.player_data = {}
                self.get_logger().info("Starting with empty player database")
        except Exception as e:
            self.get_logger().error(f"Error loading player data: {e}")
            self.player_data = {}
    
    async def save_player_data(self):
        """Save player data to file."""
        try:
            # Ensure data folder exists
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.player_data, f, indent=2, default=str)
            
            self.get_logger().info("Player data saved successfully")
        except Exception as e:
            self.get_logger().error(f"Error saving player data: {e}")
    
    async def on_player_join(self, event: PlayerJoinEvent):
        """Handle player join events."""
        player_name = event.player_name
        join_time = datetime.now()
        
        # Initialize or update player data
        if player_name not in self.player_data:
            self.player_data[player_name] = {
                "first_join": join_time.isoformat(),
                "total_joins": 0,
                "total_playtime": 0,
                "total_messages": 0,
                "last_seen": None
            }
        
        # Update stats
        self.player_data[player_name]["total_joins"] += 1
        self.player_data[player_name]["last_seen"] = join_time.isoformat()
        
        # Track session
        self.session_data[player_name] = {
            "join_time": join_time,
            "messages": 0
        }
        
        # Log the join
        total_joins = self.player_data[player_name]["total_joins"]
        ip_info = f" from {event.ip_address}" if event.ip_address else ""
        
        self.get_logger().info(f"Player {player_name} joined{ip_info} (#{total_joins})")
        
        # Welcome returning players
        if total_joins > 1:
            await self.context.send_server_command(
                f"say Welcome back, {player_name}! You've joined {total_joins} times."
            )
        else:
            await self.context.send_server_command(
                f"say Welcome to the server, {player_name}! First time here!"
            )
    
    async def on_player_leave(self, event: PlayerLeaveEvent):
        """Handle player leave events."""
        player_name = event.player_name
        leave_time = datetime.now()
        
        if player_name in self.session_data:
            # Calculate session time
            session = self.session_data[player_name]
            session_duration = (leave_time - session["join_time"]).total_seconds()
            
            # Update player data
            if player_name in self.player_data:
                self.player_data[player_name]["total_playtime"] += session_duration
                self.player_data[player_name]["last_seen"] = leave_time.isoformat()
            
            # Log the leave
            minutes = int(session_duration // 60)
            seconds = int(session_duration % 60)
            reason = f" ({event.leave_reason})" if event.leave_reason else ""
            
            self.get_logger().info(
                f"Player {player_name} left{reason} after {minutes}m {seconds}s"
            )
            
            # Clean up session data
            del self.session_data[player_name]
            
            # Save data periodically
            await self.save_player_data()
    
    async def on_player_chat(self, event: PlayerChatEvent):
        """Handle player chat events."""
        player_name = event.player_name
        
        # Update message count
        if player_name in self.player_data:
            self.player_data[player_name]["total_messages"] += 1
        
        if player_name in self.session_data:
            self.session_data[player_name]["messages"] += 1
        
        # Handle commands
        message = event.message.lower()
        if message.startswith("!stats"):
            await self.handle_stats_command(player_name)
        elif message.startswith("!playtime"):
            await self.handle_playtime_command(player_name)
    
    async def handle_stats_command(self, player_name: str):
        """Handle !stats command."""
        if player_name not in self.player_data:
            await self.context.send_server_command(f"say {player_name}: No data available")
            return
        
        data = self.player_data[player_name]
        total_hours = data["total_playtime"] / 3600
        
        stats_msg = (
            f"say {player_name}: Joins: {data['total_joins']}, "
            f"Playtime: {total_hours:.1f}h, Messages: {data['total_messages']}"
        )
        
        await self.context.send_server_command(stats_msg)
    
    async def handle_playtime_command(self, player_name: str):
        """Handle !playtime command."""
        if player_name not in self.player_data:
            await self.context.send_server_command(f"say {player_name}: No data available")
            return
        
        total_seconds = self.player_data[player_name]["total_playtime"]
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        
        await self.context.send_server_command(
            f"say {player_name}: Total playtime: {hours}h {minutes}m"
        )
    
    def get_player_stats(self, player_name: str):
        """Get stats for a specific player."""
        return self.player_data.get(player_name, {})
    
    def get_server_stats(self):
        """Get overall server statistics."""
        if not self.player_data:
            return {}
        
        total_playtime = sum(p.get("total_playtime", 0) for p in self.player_data.values())
        total_messages = sum(p.get("total_messages", 0) for p in self.player_data.values())
        
        return {
            "unique_players": len(self.player_data),
            "total_playtime_hours": total_playtime / 3600,
            "total_messages": total_messages,
            "online_players": len(self.session_data)
        }
"""Enhanced Console Interface Usage Examples

This file demonstrates how to use the new EnhancedConsoleInterface 
for Minecraft server control with stdin/stdout primary control and RCON fallback.
"""

import asyncio
import logging
from typing import Dict, Any

from aetherius.core.console_interface import (
    EnhancedConsoleInterface, 
    CommandPriority,
    create_console_interface,
    get_default_rcon_config
)
from aetherius.core.server import ServerProcessWrapper
from aetherius.core.config import ServerConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_usage_example():
    """Basic usage example with automatic connection management."""
    
    # Create server config and wrapper
    config = ServerConfig()
    server_wrapper = ServerProcessWrapper(config)
    
    # Start server first
    await server_wrapper.start()
    
    try:
        # Create console interface with default RCON config
        rcon_config = get_default_rcon_config()
        console = await create_console_interface(server_wrapper, rcon_config)
        
        # Send basic commands
        result = await console.send_command("list")
        if result.success:
            print(f"Players online: {result.output}")
        else:
            print(f"Command failed: {result.error}")
        
        # Send command with high priority
        result = await console.send_command(
            "save-all", 
            priority=CommandPriority.HIGH,
            timeout=60.0
        )
        
        print(f"Save command: {'Success' if result.success else 'Failed'}")
        print(f"Execution time: {result.execution_time:.2f}s")
        print(f"Connection used: {result.connection_type}")
        
        # Get server statistics
        stats = console.get_statistics()
        print(f"Commands sent: {stats['commands_sent']}")
        print(f"Average response time: {stats['avg_response_time']:.3f}s")
        
        # Close console interface
        await console.close()
        
    finally:
        # Stop server
        await server_wrapper.stop()


async def batch_commands_example():
    """Example of sending multiple commands in batch with priorities."""
    
    config = ServerConfig()
    server_wrapper = ServerProcessWrapper(config)
    
    await server_wrapper.start()
    
    try:
        console = await create_console_interface(server_wrapper)
        
        # Prepare batch commands with different priorities
        commands = [
            ("gamemode creative @a", CommandPriority.LOW),
            ("weather clear", CommandPriority.NORMAL),
            ("save-all", CommandPriority.HIGH),
            ("backup start", CommandPriority.CRITICAL)
        ]
        
        # Send batch commands
        results = await console.send_command_batch(commands)
        
        # Process results
        for i, (command, priority) in enumerate(commands):
            result = results[i]
            print(f"Command: {command}")
            print(f"Priority: {priority.name}")
            print(f"Result: {'✓' if result.success else '✗'}")
            print(f"Time: {result.execution_time:.3f}s")
            print("---")
        
        await console.close()
        
    finally:
        await server_wrapper.stop()


async def script_execution_example():
    """Example of executing a sequence of commands as a script."""
    
    config = ServerConfig()
    server_wrapper = ServerProcessWrapper(config)
    
    await server_wrapper.start()
    
    try:
        console = await create_console_interface(server_wrapper)
        
        # Define a server maintenance script
        maintenance_script = [
            "say Server maintenance starting in 30 seconds",
            "say Please finish your current activities",
            "weather clear",
            "time set day",
            "save-all",
            "say Maintenance complete - thank you for your patience"
        ]
        
        # Execute script
        script_result = await console.execute_script(
            maintenance_script,
            stop_on_error=True,
            timeout_per_command=30.0
        )
        
        print(f"Script execution summary:")
        print(f"Total commands: {script_result['total_commands']}")
        print(f"Successful: {script_result['successful_commands']}")
        print(f"Failed: {script_result['failed_commands']}")
        print(f"Total time: {script_result['total_execution_time']:.2f}s")
        print(f"Overall success: {script_result['success']}")
        
        # Show individual command results
        for i, result in enumerate(script_result['results']):
            cmd = maintenance_script[i]
            print(f"{i+1}. {cmd}: {'✓' if result.success else '✗'}")
        
        await console.close()
        
    finally:
        await server_wrapper.stop()


async def server_info_example():
    """Example of gathering comprehensive server information."""
    
    config = ServerConfig()
    server_wrapper = ServerProcessWrapper(config)
    
    await server_wrapper.start()
    
    try:
        console = await create_console_interface(server_wrapper)
        
        # Get comprehensive server info
        server_info = await console.get_server_info()
        
        print("=== Server Information ===")
        
        # Player information
        if 'player_list' in server_info:
            print(f"Players: {server_info['player_list']}")
        
        # Performance information
        if 'performance' in server_info:
            print(f"Performance: {server_info['performance']}")
        
        # Version information
        if 'server_version' in server_info:
            print(f"Version: {server_info['server_version']}")
        
        # Plugin information
        if 'plugin_list' in server_info:
            print(f"Plugins: {server_info['plugin_list']}")
        
        # Connection information
        conn_info = server_info.get('connection_info', {})
        print(f"\n=== Connection Status ===")
        print(f"Current connection: {conn_info.get('current_connection')}")
        print(f"Stdin available: {conn_info.get('stdin_available')}")
        print(f"RCON available: {conn_info.get('rcon_available')}")
        
        # Statistics
        stats = conn_info.get('statistics', {})
        print(f"\n=== Statistics ===")
        print(f"Commands sent: {stats.get('commands_sent', 0)}")
        print(f"Stdin commands: {stats.get('stdin_commands', 0)}")
        print(f"RCON commands: {stats.get('rcon_commands', 0)}")
        print(f"Failed commands: {stats.get('failed_commands', 0)}")
        print(f"Average response time: {stats.get('avg_response_time', 0):.3f}s")
        print(f"Connection switches: {stats.get('connection_switches', 0)}")
        
        await console.close()
        
    finally:
        await server_wrapper.stop()


async def connection_failover_example():
    """Example demonstrating connection failover between stdin and RCON."""
    
    config = ServerConfig()
    server_wrapper = ServerProcessWrapper(config)
    
    # Custom RCON configuration
    rcon_config = {
        'host': 'localhost',
        'port': 25575,
        'password': 'custom_password'
    }
    
    await server_wrapper.start()
    
    try:
        console = EnhancedConsoleInterface(server_wrapper, rcon_config)
        
        # Initialize with both connections
        await console.initialize()
        
        print(f"Initial connection: {console._current_connection.connection_type}")
        
        # Send some commands
        commands = ["list", "tps", "version"]
        
        for command in commands:
            result = await console.send_command(command, retry_on_failure=True)
            print(f"Command '{command}': {result.connection_type} - {'✓' if result.success else '✗'}")
        
        # Simulate connection issues by manually testing failover
        print("\n=== Testing Connection Failover ===")
        
        # Force disconnect primary connection
        await console.stdin_connection.disconnect()
        
        # This should automatically fail over to RCON
        result = await console.send_command("list", retry_on_failure=True)
        print(f"After stdin disconnect: {result.connection_type} - {'✓' if result.success else '✗'}")
        
        # Show statistics after failover
        stats = console.get_statistics()
        print(f"Connection switches: {stats['connection_switches']}")
        
        await console.close()
        
    finally:
        await server_wrapper.stop()


async def custom_integration_example():
    """Example of custom integration with existing server management code."""
    
    class ServerManager:
        """Custom server manager using enhanced console interface."""
        
        def __init__(self, config: ServerConfig):
            self.config = config
            self.server_wrapper = ServerProcessWrapper(config)
            self.console: Optional[EnhancedConsoleInterface] = None
        
        async def start_server(self) -> bool:
            """Start server and initialize console interface."""
            if not await self.server_wrapper.start():
                return False
            
            try:
                # Initialize console with custom RCON config
                rcon_config = {
                    'host': self.config.rcon_host or 'localhost',
                    'port': self.config.rcon_port or 25575,
                    'password': self.config.rcon_password or 'password123'
                }
                
                self.console = await create_console_interface(
                    self.server_wrapper, 
                    rcon_config
                )
                logger.info("Server and console interface started successfully")
                return True
                
            except Exception as e:
                logger.error(f"Failed to initialize console interface: {e}")
                await self.server_wrapper.stop()
                return False
        
        async def stop_server(self) -> bool:
            """Stop server and close console interface."""
            success = True
            
            if self.console:
                await self.console.close()
                self.console = None
            
            if self.server_wrapper.is_alive:
                success = await self.server_wrapper.stop()
            
            return success
        
        async def execute_admin_command(self, command: str) -> Dict[str, Any]:
            """Execute admin command with high priority."""
            if not self.console:
                return {'success': False, 'error': 'Console not available'}
            
            result = await self.console.send_command(
                command, 
                priority=CommandPriority.HIGH,
                timeout=60.0
            )
            
            return {
                'success': result.success,
                'output': result.output,
                'error': result.error,
                'execution_time': result.execution_time,
                'connection_type': result.connection_type
            }
        
        async def backup_server(self) -> Dict[str, Any]:
            """Perform server backup using script execution."""
            if not self.console:
                return {'success': False, 'error': 'Console not available'}
            
            backup_script = [
                "say Starting server backup...",
                "save-off",
                "save-all",
                "backup create auto_backup",
                "save-on",
                "say Server backup completed!"
            ]
            
            return await self.console.execute_script(
                backup_script,
                stop_on_error=True,
                timeout_per_command=120.0
            )
        
        async def get_server_status(self) -> Dict[str, Any]:
            """Get comprehensive server status."""
            if not self.console:
                return {'available': False}
            
            status = await self.console.get_server_info()
            status['available'] = True
            return status
    
    # Example usage of custom server manager
    config = ServerConfig()
    manager = ServerManager(config)
    
    try:
        await manager.start_server()
        
        # Execute admin commands
        result = await manager.execute_admin_command("whitelist add NewPlayer")
        print(f"Admin command result: {result}")
        
        # Perform backup
        backup_result = await manager.backup_server()
        print(f"Backup result: {backup_result['success']}")
        
        # Get status
        status = await manager.get_server_status()
        print(f"Server available: {status['available']}")
        
    finally:
        await manager.stop_server()


# Main execution function
async def main():
    """Run all examples."""
    
    print("=== Enhanced Console Interface Examples ===\n")
    
    examples = [
        ("Basic Usage", basic_usage_example),
        ("Batch Commands", batch_commands_example),
        ("Script Execution", script_execution_example),
        ("Server Information", server_info_example),
        ("Connection Failover", connection_failover_example),
        ("Custom Integration", custom_integration_example)
    ]
    
    for name, example_func in examples:
        print(f"\n--- {name} Example ---")
        try:
            await example_func()
            print(f"✓ {name} example completed successfully")
        except Exception as e:
            print(f"✗ {name} example failed: {e}")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())
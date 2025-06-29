#!/usr/bin/env python3
"""
Management API Usage Example
============================

This example demonstrates how to use the AetheriusManagementAPI for comprehensive
server, plugin, and component management.
"""

import asyncio
import logging
from aetherius.api import AetheriusManagementAPI, ControlLevel, InfoStreamType
from aetherius.core.server import ServerProcessWrapper


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_plugin_management(api: AetheriusManagementAPI):
    """Demonstrate plugin management capabilities."""
    print("\n=== Plugin Management Demo ===")
    
    # Get list of all plugins
    plugins = await api.get_plugin_list()
    print(f"Found {len(plugins)} plugins:")
    for plugin in plugins:
        print(f"  - {plugin['name']}: {plugin['state']} (v{plugin['version']})")
    
    # Load a plugin if any exist
    if plugins:
        plugin_name = plugins[0]['name']
        if not plugins[0]['loaded']:
            print(f"\nLoading plugin: {plugin_name}")
            result = await api.load_plugin(plugin_name)
            print(f"Load result: {result}")
        
        # Enable the plugin
        if not plugins[0]['enabled']:
            print(f"Enabling plugin: {plugin_name}")
            result = await api.enable_plugin(plugin_name)
            print(f"Enable result: {result}")
        
        # Reload the plugin
        print(f"Reloading plugin: {plugin_name}")
        result = await api.reload_plugin(plugin_name)
        print(f"Reload result: {result}")


async def demo_component_management(api: AetheriusManagementAPI):
    """Demonstrate component management capabilities."""
    print("\n=== Component Management Demo ===")
    
    # Get list of all components
    components = await api.get_component_list()
    print(f"Found {len(components)} components:")
    for component in components:
        print(f"  - {component['name']}: {component['state']} (v{component['version']})")
        if component.get('provides_web_interface'):
            print(f"    ^ Provides web interface")
    
    # Load a component if any exist
    if components:
        component_name = components[0]['name']
        if not components[0]['loaded']:
            print(f"\nLoading component: {component_name}")
            result = await api.load_component(component_name)
            print(f"Load result: {result}")


async def demo_server_control(api: AetheriusManagementAPI):
    """Demonstrate advanced server control capabilities."""
    print("\n=== Advanced Server Control Demo ===")
    
    # Get server status
    status = api.get_server_status()
    print(f"Server running: {status['running']}")
    print(f"Server PID: {status['pid']}")
    print(f"Monitoring enabled: {status['monitoring_enabled']}")
    
    if not status['running']:
        # Start server with custom options
        print("\nStarting server with custom Java arguments...")
        result = await api.start_server_advanced(
            java_args=["-Xmx4G", "-Xms2G", "-XX:+UseG1GC"],
            mc_args=["--nogui"]
        )
        print(f"Start result: {result}")
        
        # Wait a bit for server to start
        await asyncio.sleep(5)
    
    # Send some commands
    print("\nSending server commands...")
    await api.send_command("list")
    await api.send_command("say Hello from Management API!")
    
    # Create a world backup
    print("\nCreating world backup...")
    backup_result = await api.backup_world("demo_backup")
    print(f"Backup result: {backup_result}")


async def demo_information_streams(api: AetheriusManagementAPI):
    """Demonstrate information stream management."""
    print("\n=== Information Stream Demo ===")
    
    # Define stream callbacks
    async def console_callback(data):
        print(f"Console: {data}")
    
    def performance_callback(data):
        print(f"Performance: CPU={data.get('cpu_percent', 0):.1f}%")
    
    def player_event_callback(data):
        print(f"Player Event: {data}")
    
    # Register callbacks
    api.register_stream_callback(InfoStreamType.CONSOLE_OUTPUT, console_callback)
    api.register_stream_callback(InfoStreamType.PERFORMANCE_METRICS, performance_callback)
    api.register_stream_callback(InfoStreamType.PLAYER_EVENTS, player_event_callback)
    
    # Add filters
    def important_only_filter(data):
        """Only allow important messages through."""
        level = data.get('level', '').upper()
        return level in ['WARN', 'ERROR', 'FATAL']
    
    api.add_stream_filter(InfoStreamType.CONSOLE_OUTPUT, important_only_filter)
    
    # Show stream info
    stream_info = api.get_stream_info()
    print("Stream information:")
    for stream_type, info in stream_info.items():
        print(f"  {stream_type}: {info['callback_count']} callbacks, {info['filter_count']} filters")
    
    # Simulate some stream data
    await api.broadcast_to_stream(InfoStreamType.CONSOLE_OUTPUT, {
        'level': 'INFO',
        'message': 'This should be filtered out'
    })
    
    await api.broadcast_to_stream(InfoStreamType.CONSOLE_OUTPUT, {
        'level': 'WARN',
        'message': 'This warning should come through'
    })
    
    await api.broadcast_to_stream(InfoStreamType.PERFORMANCE_METRICS, {
        'cpu_percent': 45.2,
        'memory_percent': 78.1
    })


async def demo_batch_operations(api: AetheriusManagementAPI):
    """Demonstrate batch operations."""
    print("\n=== Batch Operations Demo ===")
    
    # Get all plugins for batch operation
    plugins = await api.get_plugin_list()
    plugin_names = [p['name'] for p in plugins[:3]]  # Take first 3 plugins
    
    if plugin_names:
        print(f"Performing batch reload on plugins: {plugin_names}")
        result = await api.batch_plugin_operation('reload', plugin_names)
        print(f"Batch operation result: {result}")
    
    # Reload all plugins
    print("\nReloading all plugins...")
    result = await api.reload_all_plugins()
    print(f"Reload all result: {result}")


async def demo_system_health(api: AetheriusManagementAPI):
    """Demonstrate system health monitoring."""
    print("\n=== System Health Demo ===")
    
    health = await api.get_system_health()
    print("System Health Report:")
    print(f"  CPU Usage: {health['system']['cpu_percent']:.1f}%")
    print(f"  Memory Usage: {health['system']['memory_percent']:.1f}%")
    print(f"  Disk Usage: {health['system']['disk_percent']:.1f}%")
    print(f"  Server Running: {health['server']['running']}")
    print(f"  Plugins: {health['plugins']['enabled']}/{health['plugins']['total']} enabled")
    print(f"  Components: {health['components']['enabled']}/{health['components']['total']} enabled")


async def main():
    """Main demonstration function."""
    print("Aetherius Management API Demo")
    print("=" * 50)
    
    # Initialize server wrapper (in real usage, this would be your existing server instance)
    server = ServerProcessWrapper()
    
    # Create management API with admin access
    api = AetheriusManagementAPI(server, access_level=ControlLevel.ADMIN)
    
    try:
        # Run all demos
        await demo_plugin_management(api)
        await demo_component_management(api)
        await demo_server_control(api)
        await demo_information_streams(api)
        await demo_batch_operations(api)
        await demo_system_health(api)
        
        print("\n=== Demo Complete ===")
        print("The Management API provides comprehensive control over:")
        print("• Plugin lifecycle (load/unload/enable/disable/reload)")
        print("• Component management")
        print("• Advanced server control with custom options")
        print("• Information stream management with filtering")
        print("• Batch operations for efficiency")
        print("• System health monitoring")
        print("• Access control with permission levels")
        
    except Exception as e:
        logger.error(f"Demo error: {e}")
    finally:
        # Cleanup
        if api._monitoring_enabled:
            await api.stop_performance_monitoring()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
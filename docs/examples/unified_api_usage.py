#!/usr/bin/env python3
"""
Unified Core API Usage Example
==============================

This example demonstrates the new unified Aetherius Core API which provides
elegant, comprehensive access to all functionality through a single interface.

The unified API is designed to be:
- Self-contained and independently runnable
- Comprehensive and feature-complete  
- Elegant and easy to use
- Extensible and modular
"""

import asyncio
import logging
from aetherius.api import AetheriusCoreAPI, create_core_api, get_core_api


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_server_management(api: AetheriusCoreAPI):
    """Demonstrate server management capabilities."""
    print("\n🎮 Server Management Demo")
    print("=" * 50)
    
    # Get server status
    status = await api.server.get_status()
    print(f"Server running: {status['running']}")
    
    if not status['running']:
        # Start server with custom settings
        print("Starting server with custom Java arguments...")
        result = await api.server.start(
            java_args=["-Xmx4G", "-Xms2G", "-XX:+UseG1GC"],
            mc_args=["--nogui"]
        )
        
        if result['success']:
            print(f"✅ {result['message']}")
            print(f"   PID: {result['pid']}")
        else:
            print(f"❌ {result.get('error', 'Failed to start')}")
            return
        
        # Wait for server to fully start
        await asyncio.sleep(10)
    
    # Send some commands
    print("\nSending server commands...")
    
    commands = ["list", "say Hello from Unified API!", "time set day"]
    for cmd in commands:
        result = await api.server.send_command(cmd)
        status_icon = "✅" if result['success'] else "❌"
        print(f"  {status_icon} {cmd}: {result['success']}")
    
    # Get updated status
    status = await api.server.get_status()
    print(f"\nServer uptime: {status['uptime']:.1f} seconds")


async def demo_plugin_management(api: AetheriusCoreAPI):
    """Demonstrate plugin management capabilities."""
    print("\n🔌 Plugin Management Demo")
    print("=" * 50)
    
    # List all plugins
    plugins = await api.plugins.list()
    print(f"Found {len(plugins)} plugins:")
    
    for plugin in plugins[:5]:  # Show first 5
        status_icon = "🟢" if plugin['enabled'] else "🟡" if plugin['loaded'] else "🔴"
        print(f"  {status_icon} {plugin['name']} v{plugin['version']} - {plugin['state']}")
    
    if plugins:
        # Demonstrate plugin operations
        test_plugin = plugins[0]['name']
        print(f"\nTesting operations on plugin: {test_plugin}")
        
        # Reload plugin
        result = await api.plugins.reload(test_plugin)
        status_icon = "✅" if result['success'] else "❌"
        print(f"  {status_icon} Reload: {result['message']}")
        
        # Load/enable if needed
        if not plugins[0]['enabled']:
            result = await api.plugins.enable(test_plugin)
            status_icon = "✅" if result['success'] else "❌"
            print(f"  {status_icon} Enable: {result['message']}")
    
    # Reload all plugins
    print("\nReloading all plugins...")
    result = await api.plugins.reload_all()
    status_icon = "✅" if result['success'] else "⚠️"
    print(f"{status_icon} {result['message']}")


async def demo_component_management(api: AetheriusCoreAPI):
    """Demonstrate component management capabilities."""
    print("\n🧩 Component Management Demo")
    print("=" * 50)
    
    # List all components
    components = await api.components.list()
    print(f"Found {len(components)} components:")
    
    for component in components:
        status_icon = "🟢" if component['enabled'] else "🟡" if component['loaded'] else "🔴"
        web_icon = "🌐" if component.get('provides_web_interface') else "  "
        print(f"  {status_icon} {web_icon} {component['name']} v{component['version']} - {component['state']}")
    
    if components:
        # Test component operations
        test_component = components[0]['name']
        print(f"\nTesting operations on component: {test_component}")
        
        if not components[0]['enabled']:
            result = await api.components.enable(test_component)
            status_icon = "✅" if result['success'] else "❌"
            print(f"  {status_icon} Enable: {result['message']}")


async def demo_player_management(api: AetheriusCoreAPI):
    """Demonstrate player management capabilities."""
    print("\n👥 Player Management Demo")
    print("=" * 50)
    
    # List all players
    all_players = await api.players.list()
    online_players = await api.players.list(online_only=True)
    
    print(f"Total players: {len(all_players)}")
    print(f"Online players: {len(online_players)}")
    
    if online_players:
        print("\nOnline players:")
        for player in online_players:
            location = player.get('location')
            loc_str = f"({location['x']:.1f}, {location['y']:.1f}, {location['z']:.1f})" if location else "Unknown"
            print(f"  🟢 {player['name']} - Level {player['level']} - {loc_str}")
    
    if all_players:
        # Show detailed info for first player
        player_name = all_players[0]['name']
        player_data = await api.players.get(player_name)
        
        if player_data:
            print(f"\nDetailed info for {player_name}:")
            print(f"  UUID: {player_data['uuid']}")
            print(f"  Game Mode: {player_data['game_mode']}")
            print(f"  Level: {player_data['level']}")
            print(f"  Health: {player_data['health']}")
            print(f"  Last Login: {player_data['last_login']}")


async def demo_monitoring_and_performance(api: AetheriusCoreAPI):
    """Demonstrate monitoring and performance capabilities."""
    print("\n📊 Monitoring & Performance Demo")
    print("=" * 50)
    
    # Start performance monitoring
    monitoring_started = await api.monitoring.start_performance_monitoring(interval=5.0)
    if monitoring_started:
        print("✅ Performance monitoring started")
    else:
        print("❌ Failed to start performance monitoring")
    
    # Get current performance data
    perf_data = await api.monitoring.get_performance_data()
    
    if 'error' not in perf_data:
        print(f"\nCurrent Performance:")
        print(f"  Server Running: {perf_data.get('server_running', False)}")
        print(f"  CPU Usage: {perf_data.get('cpu_percent', 0):.1f}%")
        print(f"  Memory Usage: {perf_data.get('memory_mb', 0):.1f} MB")
        print(f"  System CPU: {perf_data.get('system_cpu_percent', 0):.1f}%")
        print(f"  System Memory: {perf_data.get('system_memory_percent', 0):.1f}%")
    
    # Get comprehensive system health
    health = await api.monitoring.get_system_health()
    
    if 'error' not in health:
        print(f"\n🏥 System Health:")
        print(f"  Server: {'🟢 Running' if health['server']['running'] else '🔴 Stopped'}")
        print(f"  Plugins: {health['plugins']['enabled']}/{health['plugins']['total']} enabled")
        print(f"  Components: {health['components']['enabled']}/{health['components']['total']} enabled")
        print(f"  Monitoring: {'🟢 Active' if health['monitoring']['enabled'] else '🔴 Inactive'}")


async def demo_configuration_management(api: AetheriusCoreAPI):
    """Demonstrate configuration management capabilities."""
    print("\n⚙️ Configuration Management Demo")
    print("=" * 50)
    
    # Get some configuration values
    server_jar = api.config.get("server.jar_path", "server.jar")
    working_dir = api.config.get("server.working_directory", "server")
    auto_restart = api.config.get("server.auto_restart", False)
    
    print(f"Server Configuration:")
    print(f"  JAR Path: {server_jar}")
    print(f"  Working Directory: {working_dir}")
    print(f"  Auto Restart: {auto_restart}")
    
    # Get all keys with a prefix
    server_keys = api.config.get_keys("server.")
    print(f"\nServer configuration keys: {len(server_keys)}")
    for key in server_keys[:5]:  # Show first 5
        value = api.config.get(key)
        print(f"  {key}: {value}")
    
    # Demonstrate setting a value
    test_key = "demo.test_value"
    api.config.set(test_key, "Hello from API!", save=False)
    retrieved_value = api.config.get(test_key)
    print(f"\nSet/Get test: {test_key} = {retrieved_value}")
    
    # Clean up
    api.config.delete(test_key, save=False)


async def demo_event_system(api: AetheriusCoreAPI):
    """Demonstrate event system capabilities."""
    print("\n📡 Event System Demo")
    print("=" * 50)
    
    # Set up event listeners
    events_received = []
    
    def on_performance_update(data):
        events_received.append(f"Performance update: CPU {data.get('cpu_percent', 0):.1f}%")
    
    async def on_custom_event(message):
        events_received.append(f"Custom event: {message}")
    
    # Register listeners
    api.events.on("performance_update", on_performance_update)
    api.events.on("demo_event", on_custom_event)
    
    print("Event listeners registered")
    
    # Emit a custom event
    await api.events.emit("demo_event", "Hello from event system!")
    
    # Wait a bit for performance events (if monitoring is running)
    await asyncio.sleep(2)
    
    # Show received events
    print(f"\nEvents received ({len(events_received)}):")
    for event in events_received[-3:]:  # Show last 3
        print(f"  📡 {event}")
    
    # List all registered events
    all_events = api.events.get_events()
    print(f"\nAll registered events: {all_events}")


async def demo_comprehensive_status(api: AetheriusCoreAPI):
    """Demonstrate comprehensive API status."""
    print("\n📋 Comprehensive API Status")
    print("=" * 50)
    
    # Get complete API status
    status = await api.get_status()
    
    print(f"API Initialized: {'✅' if status['api_initialized'] else '❌'}")
    print(f"Timestamp: {status['timestamp']}")
    
    # Server module status
    server_info = status['modules']['server']
    print(f"\n🎮 Server Module:")
    print(f"  Running: {'🟢' if server_info['running'] else '🔴'}")
    print(f"  PID: {server_info.get('pid', 'N/A')}")
    print(f"  Uptime: {server_info.get('uptime', 0):.1f}s")
    
    # Plugin module status
    plugin_info = status['modules']['plugins']
    print(f"\n🔌 Plugin Module:")
    print(f"  Total: {plugin_info['total']}")
    print(f"  Enabled: {plugin_info['enabled']}")
    
    # Component module status
    component_info = status['modules']['components']
    print(f"\n🧩 Component Module:")
    print(f"  Total: {component_info['total']}")
    print(f"  Enabled: {component_info['enabled']}")
    
    # Player module status
    player_info = status['modules']['players']
    print(f"\n👥 Player Module:")
    print(f"  Total: {player_info['total']}")
    print(f"  Online: {player_info['online']}")
    
    # Monitoring module status
    monitoring_info = status['modules']['monitoring']
    print(f"\n📊 Monitoring Module:")
    print(f"  Enabled: {'🟢' if monitoring_info['enabled'] else '🔴'}")


async def main_managed_context_demo():
    """Demo using managed context (recommended approach)."""
    print("\n🏗️ Managed Context Demo (Recommended)")
    print("=" * 60)
    
    # Use managed context for automatic initialization and cleanup
    async with AetheriusCoreAPI().managed_context() as api:
        print(f"✅ API initialized: {api}")
        
        # Run a quick demo
        status = await api.get_status()
        print(f"   Timestamp: {status['timestamp']}")
        print(f"   Modules available: {len(status['modules'])}")
        
        # Server status
        server_status = await api.server.get_status()
        print(f"   Server running: {server_status['running']}")
        
        print("✅ Context will automatically cleanup when exiting")
    
    print("✅ Managed context demo completed")


async def main_factory_demo():
    """Demo using factory function."""
    print("\n🏭 Factory Function Demo")
    print("=" * 60)
    
    # Create API using factory function
    api = await create_core_api(auto_start_monitoring=True)
    
    try:
        print(f"✅ API created and initialized: {api}")
        
        # Quick functionality test
        plugins = await api.plugins.list()
        components = await api.components.list()
        
        print(f"   Plugins: {len(plugins)}")
        print(f"   Components: {len(components)}")
        print(f"   Monitoring: {'🟢' if api.monitoring._monitoring_enabled else '🔴'}")
        
    finally:
        # Manual cleanup
        await api.cleanup()
        print("✅ Factory demo completed with manual cleanup")


async def main_global_api_demo():
    """Demo using global API instance."""
    print("\n🌍 Global API Demo")
    print("=" * 60)
    
    # Get global API instance
    api = await get_core_api()
    
    print(f"✅ Global API instance: {api}")
    
    # Use global instance
    status = await api.get_status()
    print(f"   API initialized: {status['api_initialized']}")
    
    # Global instance persists across calls
    api2 = await get_core_api(initialize_if_needed=False)
    print(f"✅ Same instance: {api is api2}")


async def main():
    """Run comprehensive unified API demonstration."""
    print("Aetherius Unified Core API Demonstration")
    print("=" * 70)
    print("Showcasing elegant, comprehensive access to all functionality")
    print("through a single, unified interface.")
    
    try:
        # Demonstrate different initialization patterns
        await main_managed_context_demo()
        await main_factory_demo()
        await main_global_api_demo()
        
        print("\n" + "=" * 70)
        print("🚀 Full Feature Demonstration")
        print("=" * 70)
        
        # Use managed context for main demo
        async with AetheriusCoreAPI().managed_context() as api:
            # Run all feature demos
            await demo_server_management(api)
            await demo_plugin_management(api)
            await demo_component_management(api)
            await demo_player_management(api)
            await demo_monitoring_and_performance(api)
            await demo_configuration_management(api)
            await demo_event_system(api)
            await demo_comprehensive_status(api)
        
        print("\n" + "=" * 70)
        print("✅ Unified API Demonstration Complete!")
        print("=" * 70)
        print("\n🎯 Key Benefits of the Unified API:")
        print("  • Single point of access for all functionality")
        print("  • Elegant, consistent interface design")
        print("  • Automatic resource management")
        print("  • Comprehensive feature coverage")
        print("  • Independent operation capability")
        print("  • Easy integration with components")
        print("  • Built-in monitoring and health checks")
        print("  • Flexible initialization patterns")
        
    except Exception as e:
        logger.error(f"Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run the comprehensive demonstration
    asyncio.run(main())
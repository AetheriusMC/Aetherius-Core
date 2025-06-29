"""
Management CLI Commands
=======================

CLI commands for using the Aetherius Management API.
"""

import asyncio
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from typing import List, Optional

from ..api.management import AetheriusManagementAPI, ControlLevel, InfoStreamType
from ..core.server import ServerProcessWrapper


console = Console()
management_app = typer.Typer(name="manage", help="Advanced management commands")


def get_management_api() -> AetheriusManagementAPI:
    """Get management API instance."""
    # In real usage, this would get the existing server instance
    server = ServerProcessWrapper()
    return AetheriusManagementAPI(server, access_level=ControlLevel.ADMIN)


@management_app.command("plugins")
def list_plugins():
    """List all plugins with their status."""
    async def _list_plugins():
        api = get_management_api()
        plugins = await api.get_plugin_list()
        
        table = Table(title="Plugins")
        table.add_column("Name", style="cyan")
        table.add_column("State", style="magenta")
        table.add_column("Version", style="green")
        table.add_column("Description", style="white")
        
        for plugin in plugins:
            state_style = "green" if plugin['enabled'] else "yellow" if plugin['loaded'] else "red"
            table.add_row(
                plugin['name'],
                f"[{state_style}]{plugin['state']}[/{state_style}]",
                plugin['version'] or "Unknown",
                plugin['description'] or "No description"
            )
        
        console.print(table)
    
    asyncio.run(_list_plugins())


@management_app.command("components")
def list_components():
    """List all components with their status."""
    async def _list_components():
        api = get_management_api()
        components = await api.get_component_list()
        
        table = Table(title="Components")
        table.add_column("Name", style="cyan")
        table.add_column("State", style="magenta")
        table.add_column("Version", style="green")
        table.add_column("Web Interface", style="blue")
        table.add_column("Description", style="white")
        
        for component in components:
            state_style = "green" if component['enabled'] else "yellow" if component['loaded'] else "red"
            web_interface = "✓" if component.get('provides_web_interface') else "✗"
            table.add_row(
                component['name'],
                f"[{state_style}]{component['state']}[/{state_style}]",
                component['version'] or "Unknown",
                web_interface,
                component['description'] or "No description"
            )
        
        console.print(table)
    
    asyncio.run(_list_components())


@management_app.command("plugin")
def manage_plugin(
    action: str = typer.Argument(..., help="Action: load, unload, enable, disable, reload"),
    name: str = typer.Argument(..., help="Plugin name")
):
    """Manage a specific plugin."""
    async def _manage_plugin():
        api = get_management_api()
        
        actions = {
            'load': api.load_plugin,
            'unload': api.unload_plugin,
            'enable': api.enable_plugin,
            'disable': api.disable_plugin,
            'reload': api.reload_plugin
        }
        
        if action not in actions:
            rprint(f"[red]Unknown action: {action}[/red]")
            rprint(f"Available actions: {', '.join(actions.keys())}")
            return
        
        with console.status(f"[bold green]{action.title()}ing plugin {name}..."):
            result = await actions[action](name)
        
        if result['success']:
            rprint(f"[green]✓[/green] {result['message']}")
        else:
            rprint(f"[red]✗[/red] {result.get('error', 'Operation failed')}")
    
    asyncio.run(_manage_plugin())


@management_app.command("component")
def manage_component(
    action: str = typer.Argument(..., help="Action: load, unload, enable, disable"),
    name: str = typer.Argument(..., help="Component name")
):
    """Manage a specific component."""
    async def _manage_component():
        api = get_management_api()
        
        actions = {
            'load': api.load_component,
            'unload': api.unload_component,
            'enable': api.enable_component,
            'disable': api.disable_component
        }
        
        if action not in actions:
            rprint(f"[red]Unknown action: {action}[/red]")
            rprint(f"Available actions: {', '.join(actions.keys())}")
            return
        
        with console.status(f"[bold green]{action.title()}ing component {name}..."):
            result = await actions[action](name)
        
        if result['success']:
            rprint(f"[green]✓[/green] {result['message']}")
        else:
            rprint(f"[red]✗[/red] {result.get('error', 'Operation failed')}")
    
    asyncio.run(_manage_component())


@management_app.command("batch-plugins")
def batch_plugins(
    action: str = typer.Argument(..., help="Action: load, unload, enable, disable, reload"),
    names: List[str] = typer.Argument(..., help="Plugin names")
):
    """Perform batch operation on multiple plugins."""
    async def _batch_plugins():
        api = get_management_api()
        
        with console.status(f"[bold green]Performing {action} on {len(names)} plugins..."):
            result = await api.batch_plugin_operation(action, names)
        
        if result['success']:
            rprint(f"[green]✓[/green] {result['message']}")
        else:
            rprint(f"[red]✗[/red] Batch operation partially failed")
        
        # Show details
        table = Table(title="Operation Details")
        table.add_column("Plugin", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Message", style="white")
        
        for detail in result.get('details', []):
            status_style = "green" if detail['success'] else "red"
            status_icon = "✓" if detail['success'] else "✗"
            table.add_row(
                detail['plugin'],
                f"[{status_style}]{status_icon}[/{status_style}]",
                detail['message']
            )
        
        console.print(table)
    
    asyncio.run(_batch_plugins())


@management_app.command("reload-all")
def reload_all_plugins():
    """Reload all loaded plugins."""
    async def _reload_all():
        api = get_management_api()
        
        with console.status("[bold green]Reloading all plugins..."):
            result = await api.reload_all_plugins()
        
        if result['success']:
            rprint(f"[green]✓[/green] {result['message']}")
        else:
            rprint(f"[yellow]⚠[/yellow] {result['message']}")
        
        # Show details
        if 'details' in result:
            table = Table(title="Reload Details")
            table.add_column("Plugin", style="cyan")
            table.add_column("Status", style="magenta")
            table.add_column("Message", style="white")
            
            for detail in result['details']:
                status_style = "green" if detail['success'] else "red"
                status_icon = "✓" if detail['success'] else "✗"
                table.add_row(
                    detail['plugin'],
                    f"[{status_style}]{status_icon}[/{status_style}]",
                    detail['message']
                )
            
            console.print(table)
    
    asyncio.run(_reload_all())


@management_app.command("server-start")
def start_server_advanced(
    java_args: Optional[str] = typer.Option(None, "--java-args", help="Custom Java arguments (comma-separated)"),
    mc_args: Optional[str] = typer.Option(None, "--mc-args", help="Custom Minecraft arguments (comma-separated)"),
    jar: Optional[str] = typer.Option(None, "--jar", help="Custom server JAR path")
):
    """Start server with advanced options."""
    async def _start_server():
        api = get_management_api()
        
        # Parse arguments
        java_args_list = java_args.split(',') if java_args else None
        mc_args_list = mc_args.split(',') if mc_args else None
        
        with console.status("[bold green]Starting server with advanced options..."):
            result = await api.start_server_advanced(
                java_args=java_args_list,
                mc_args=mc_args_list,
                custom_jar=jar
            )
        
        if result['success']:
            rprint(f"[green]✓[/green] {result['message']}")
            if java_args_list:
                rprint(f"Java args: {java_args_list}")
            if mc_args_list:
                rprint(f"MC args: {mc_args_list}")
            if jar:
                rprint(f"JAR: {jar}")
        else:
            rprint(f"[red]✗[/red] {result.get('error', 'Failed to start server')}")
    
    asyncio.run(_start_server())


@management_app.command("server-stop")
def stop_server_graceful(
    timeout: float = typer.Option(30.0, "--timeout", help="Graceful shutdown timeout in seconds")
):
    """Stop server gracefully with timeout."""
    async def _stop_server():
        api = get_management_api()
        
        with console.status(f"[bold yellow]Stopping server gracefully (timeout: {timeout}s)..."):
            result = await api.stop_server_graceful(timeout)
        
        if result['success']:
            forced = result.get('forced', False)
            if forced:
                rprint(f"[yellow]⚠[/yellow] {result['message']}")
            else:
                rprint(f"[green]✓[/green] {result['message']}")
        else:
            rprint(f"[red]✗[/red] {result.get('error', 'Failed to stop server')}")
    
    asyncio.run(_stop_server())


@management_app.command("backup")
def backup_world(
    name: Optional[str] = typer.Option(None, "--name", help="Custom backup name")
):
    """Create a world backup."""
    async def _backup():
        api = get_management_api()
        
        with console.status("[bold green]Creating world backup..."):
            result = await api.backup_world(name)
        
        if result['success']:
            rprint(f"[green]✓[/green] {result['message']}")
            rprint(f"Backup path: {result['backup_path']}")
            rprint(f"Backup size: {result['backup_size']} bytes")
        else:
            rprint(f"[red]✗[/red] {result.get('error', 'Failed to create backup')}")
    
    asyncio.run(_backup())


@management_app.command("health")
def system_health():
    """Show comprehensive system health information."""
    async def _health():
        api = get_management_api()
        
        with console.status("[bold green]Gathering system health information..."):
            health = await api.get_system_health()
        
        if 'error' in health:
            rprint(f"[red]✗[/red] Error getting health info: {health['error']}")
            return
        
        # System panel
        system_info = health['system']
        system_panel = Panel(
            f"CPU: {system_info['cpu_percent']:.1f}%\n"
            f"Memory: {system_info['memory_percent']:.1f}%\n"
            f"Disk: {system_info['disk_percent']:.1f}%\n"
            f"Python: {system_info['python_version']}\n"
            f"Platform: {system_info['platform']}",
            title="System Health",
            border_style="green"
        )
        
        # Server panel
        server_info = health['server']
        server_status = "🟢 Running" if server_info['running'] else "🔴 Stopped"
        server_panel = Panel(
            f"Status: {server_status}\n"
            f"Performance monitoring available: {'Yes' if 'performance' in server_info else 'No'}",
            title="Server Status",
            border_style="blue"
        )
        
        # Plugins panel
        plugins_info = health['plugins']
        plugins_panel = Panel(
            f"Total: {plugins_info['total']}\n"
            f"Loaded: {plugins_info['loaded']}\n"
            f"Enabled: {plugins_info['enabled']}",
            title="Plugins",
            border_style="magenta"
        )
        
        # Components panel
        components_info = health['components']
        components_panel = Panel(
            f"Total: {components_info['total']}\n"
            f"Loaded: {components_info['loaded']}\n"
            f"Enabled: {components_info['enabled']}",
            title="Components",
            border_style="cyan"
        )
        
        # Print all panels
        console.print(system_panel)
        console.print(server_panel)
        console.print(plugins_panel)
        console.print(components_panel)
        
        # Streams info
        streams_info = health['streams']
        active_streams = [name for name, info in streams_info.items() if info['active']]
        if active_streams:
            rprint(f"\n[bold]Active Information Streams:[/bold] {', '.join(active_streams)}")
    
    asyncio.run(_health())


@management_app.command("streams")
def stream_info():
    """Show information stream status."""
    async def _streams():
        api = get_management_api()
        streams = api.get_stream_info()
        
        table = Table(title="Information Streams")
        table.add_column("Stream Type", style="cyan")
        table.add_column("Callbacks", style="green")
        table.add_column("Filters", style="yellow")
        table.add_column("Active", style="magenta")
        
        for stream_type, info in streams.items():
            active_icon = "✓" if info['active'] else "✗"
            active_style = "green" if info['active'] else "red"
            table.add_row(
                stream_type,
                str(info['callback_count']),
                str(info['filter_count']),
                f"[{active_style}]{active_icon}[/{active_style}]"
            )
        
        console.print(table)
    
    asyncio.run(_streams())


if __name__ == "__main__":
    management_app()
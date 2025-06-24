"""Simple console - completely rewritten approach."""

import asyncio
import os
import time
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..core import (
    LogLineEvent,
    PlayerJoinEvent,
    on_event,
)
from ..core.server import ServerProcessWrapper


class SimpleConsole:
    """重新设计的简单控制台"""

    def __init__(self, server_wrapper: ServerProcessWrapper):
        self.server_wrapper = server_wrapper
        self.console = Console()
        self.running = False

        # 简单状态
        self.log_messages = []
        self.event_count = 0
        self.last_input = ""

        # 设置事件监听
        self._setup_events()

    def _setup_events(self):
        """设置基本事件监听"""
        @on_event(LogLineEvent)
        async def handle_log(event: LogLineEvent):
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_messages.append(f"[{timestamp}] {event.message}")
            if len(self.log_messages) > 20:
                self.log_messages.pop(0)
            self.event_count += 1

        @on_event(PlayerJoinEvent)
        async def handle_join(event: PlayerJoinEvent):
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_messages.append(f"[{timestamp}] ✓ {event.player_name} joined")
            self.event_count += 1

    def _clear_screen(self):
        """清屏"""
        os.system('clear' if os.name == 'posix' else 'cls')

    def _show_status(self):
        """显示当前状态"""
        self._clear_screen()

        # 标题
        self.console.print(Panel(
            Text("🎮 Aetherius Simple Console", justify="center", style="bold cyan"),
            border_style="blue"
        ))

        # 日志区域
        if self.log_messages:
            log_text = "\n".join(self.log_messages[-15:])
        else:
            log_text = "Waiting for server activity..."

        self.console.print(Panel(
            log_text,
            title=f"📋 Server Logs (Events: {self.event_count})",
            border_style="green"
        ))

        # 输入状态
        if self.last_input:
            input_text = f"Last input: {self._get_command_type(self.last_input)} {self.last_input}"
            style = "white"
        else:
            input_text = "Ready for input..."
            style = "dim"

        self.console.print(Panel(
            Text(input_text, style=style),
            title="⌨️ Input Status",
            border_style="yellow"
        ))

        # 帮助
        help_text = "Commands: / (Minecraft) | ! (Aetherius) | @ (System) | # (Plugin) | exit (Quit)"
        self.console.print(Panel(
            Text(help_text, style="dim"),
            title="💡 Help",
            border_style="magenta"
        ))

    def _get_command_type(self, command: str) -> str:
        """获取命令类型显示"""
        if command.startswith("/"):
            return "[Minecraft]"
        elif command.startswith("!"):
            return "[Aetherius]"
        elif command.startswith("@"):
            return "[System]"
        elif command.startswith("#"):
            return "[Plugin]"
        else:
            return "[Default]"

    def _parse_command(self, user_input: str) -> dict:
        """解析命令"""
        stripped = user_input.strip()
        if not stripped:
            return {'type': 'empty'}

        if stripped.startswith("/"):
            return {'type': 'minecraft', 'command': stripped[1:].strip()}
        elif stripped.startswith("!"):
            return {'type': 'aetherius', 'command': stripped[1:].strip()}
        elif stripped.startswith("@"):
            return {'type': 'system', 'command': stripped[1:].strip()}
        elif stripped.startswith("#"):
            return {'type': 'plugin', 'command': stripped[1:].strip()}
        else:
            return {'type': 'minecraft', 'command': stripped}

    async def _handle_command(self, parsed: dict):
        """处理命令"""
        cmd_type = parsed['type']

        if cmd_type == 'empty':
            return

        command = parsed.get('command', '')
        timestamp = datetime.now().strftime("%H:%M:%S")

        if cmd_type == 'minecraft':
            # 首先检查全局状态
            from ..core.server_state import get_server_state
            global_state = get_server_state()
            
            if self.server_wrapper.is_alive and self.server_wrapper.process is not None:
                # 直接连接模式
                self.log_messages.append(f"[{timestamp}] 📤 Sending: {command}")
                try:
                    success = await self.server_wrapper.send_command(command)
                    if success:
                        self.log_messages.append(f"[{timestamp}] ✅ Command sent successfully")
                    else:
                        self.log_messages.append(f"[{timestamp}] ❌ Failed to send command")
                except Exception as e:
                    self.log_messages.append(f"[{timestamp}] ❌ Command error: {str(e)}")
            elif global_state.is_server_running():
                # 跨进程命令模式
                self.log_messages.append(f"[{timestamp}] 📤 Sending via queue: {command}")
                try:
                    success = await self.server_wrapper.send_command_via_queue(command)
                    if success:
                        self.log_messages.append(f"[{timestamp}] ✅ Command queued successfully")
                    else:
                        self.log_messages.append(f"[{timestamp}] ❌ Failed to queue command")
                except Exception as e:
                    self.log_messages.append(f"[{timestamp}] ❌ Queue error: {str(e)}")
            else:
                # 服务器未运行，显示模拟发送
                self.log_messages.append(f"[{timestamp}] 🔄 Server not running - simulating command: {command}")
                self.log_messages.append(f"[{timestamp}] 💡 Start server with 'aetherius server start' first")

        elif cmd_type == 'aetherius':
            if command == 'clear':
                self.log_messages.clear()
                self.log_messages.append(f"[{timestamp}] 🧹 Logs cleared")
            elif command == 'status':
                status = "running" if self.server_wrapper.is_alive else "stopped"
                self.log_messages.append(f"[{timestamp}] 🔍 Server: {status}")
            elif command == 'help':
                self.log_messages.append(f"[{timestamp}] 📖 Available: !clear, !status, !help")
            else:
                self.log_messages.append(f"[{timestamp}] ❓ Unknown: {command}")

        else:
            self.log_messages.append(f"[{timestamp}] {cmd_type.title()}: {command}")

    async def _input_loop(self):
        """主输入循环"""
        while self.running:
            try:
                # 显示当前状态
                self._show_status()

                # 使用Rich的Prompt来获取输入
                try:
                    self.console.print("\n[bold blue]>[/bold blue] ", end="")
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None, input
                    )
                except (EOFError, KeyboardInterrupt):
                    break

                # 立即保存并显示用户输入
                self.last_input = user_input
                self._show_status()

                # 添加输入到日志显示
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.log_messages.append(f"[{timestamp}] 📝 Input: {self._get_command_type(user_input)} {user_input}")

                # 短暂延迟让用户看到输入
                await asyncio.sleep(0.5)

                # 检查退出
                if user_input.strip().lower() in ('exit', 'quit', 'q'):
                    self.running = False
                    break

                # 处理命令
                parsed = self._parse_command(user_input)
                await self._handle_command(parsed)

                # 处理完成后暂停一下
                await asyncio.sleep(0.3)

            except Exception as e:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.log_messages.append(f"[{timestamp}] ❌ Input error: {str(e)}")
                await asyncio.sleep(1.0)

    async def start(self):
        """启动简单控制台"""
        # 检查服务器状态
        server_running = self.server_wrapper.is_alive
        if server_running:
            self.console.print("[green]✅ Server is running - full functionality enabled[/green]")
        else:
            # 检查全局状态
            from ..core.server_state import get_server_state
            global_state = get_server_state()
            if global_state.is_server_running():
                self.console.print("[yellow]⚠️  Server detected but not connected - some features may be limited[/yellow]")
                server_running = True  # 允许继续
            else:
                self.console.print("[yellow]⚠️  No server detected - console will work in demo mode[/yellow]")
                self.console.print("[dim]Start server with 'aetherius server start' to enable full functionality[/dim]")

        self.running = True

        # 启动消息
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{timestamp}] 🚀 Simple console started")

        # 显示欢迎信息
        self.console.print("\n[bold green]🎮 Starting Simple Console...[/bold green]")
        self.console.print("[dim]This console will show your input immediately after you type it![/dim]")
        time.sleep(1)

        try:
            # 运行主循环
            await self._input_loop()
        except Exception as e:
            self.console.print(f"\n[red]Console error: {e}[/red]")
        finally:
            self.running = False

        self._clear_screen()
        self.console.print("\n[dim]Simple console stopped. Goodbye![/dim]")
        return True


# 超级简单的测试版本
class SuperSimpleConsole:
    """超级简单的控制台测试"""

    def __init__(self, server_wrapper):
        self.server = server_wrapper
        self.console = Console()

    async def start(self):
        """启动超级简单控制台"""
        self.console.print("[bold green]🧪 Super Simple Console Test[/bold green]")
        self.console.print("[dim]Every input will be shown immediately[/dim]\n")

        for i in range(10):
            try:
                self.console.print(f"[yellow]Input {i+1}/10:[/yellow] Type something and press Enter")

                # 直接使用input
                user_input = input("> ")

                # 立即显示用户输入
                self.console.print(f"[green]✓ You typed:[/green] '[white]{user_input}[/white]'")

                # 显示命令类型
                if user_input.startswith("/"):
                    cmd_type = "[Minecraft]"
                elif user_input.startswith("!"):
                    cmd_type = "[Aetherius]"
                elif user_input.startswith("@"):
                    cmd_type = "[System]"
                elif user_input.startswith("#"):
                    cmd_type = "[Plugin]"
                else:
                    cmd_type = "[Default]"

                self.console.print(f"[cyan]Command type:[/cyan] {cmd_type}")

                if user_input.strip().lower() in ('exit', 'quit'):
                    break

                print()  # 空行分隔

            except (EOFError, KeyboardInterrupt):
                break

        self.console.print("\n[dim]Super simple console test completed![/dim]")
        return True

#!/usr/bin/env python3
"""
简化的Aetherius统一控制台 - 解决格式和反馈问题
"""

import asyncio
import logging
import os
import readline
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path

# Import enhanced console interface
try:
    from aetherius.core.console_interface import (
        CommandPriority,
        EnhancedConsoleInterface,
        get_default_rcon_config,
    )
    from aetherius.core.console_manager import (
        close_managed_console_interface,
        get_managed_console_interface,
    )

    HAS_ENHANCED_CONSOLE = True
except ImportError:
    HAS_ENHANCED_CONSOLE = False

# 简单的颜色支持检测
HAS_COLOR = (
    hasattr(sys.stdout, "isatty")
    and sys.stdout.isatty()
    and os.getenv("TERM", "").lower() not in ("dumb", "")
)

if HAS_COLOR:
    try:
        import colorama
        from colorama import Fore, Style

        colorama.init()
    except ImportError:
        HAS_COLOR = False

if not HAS_COLOR:

    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""

    class Style:
        RESET_ALL = ""


class CommandType(Enum):
    """命令类型 - 统一前缀识别系统"""

    MINECRAFT = "/"  # MC指令
    AETHERIUS = "!"  # Aetherius系统指令
    SCRIPT = "@"  # 脚本指令
    PLUGIN = "#"  # 插件指令
    COMPONENT = "$"  # 组件指令
    ADMIN = "%"  # 管理指令
    CHAT = ""  # 聊天消息


class SimpleConsole:
    """简化的统一控制台"""

    def __init__(self, server_manager=None):
        self.server_manager = server_manager
        self.is_running = False
        self.start_time = datetime.now()
        self.commands_executed = 0

        # Enhanced console interface
        self.enhanced_console: EnhancedConsoleInterface | None = None
        self._console_initialized = False

        # 设置readline
        try:
            readline.parse_and_bind("tab: complete")
        except Exception:
            pass

        # 初始化插件管理器
        self._init_plugin_manager()

        # 初始化组件管理器
        self._init_component_manager()

        # 设置服务器日志监听
        self._setup_server_monitoring()

        # 初始化增强控制台接口
        if HAS_ENHANCED_CONSOLE:
            self._init_enhanced_console()

        self._print_startup()

    def _init_plugin_manager(self):
        """初始化插件管理器"""
        try:
            from ..core import get_plugin_manager

            self.plugin_manager = get_plugin_manager()
            print(f"{Fore.GREEN}✓ 已初始化插件管理器{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ 插件管理器初始化失败: {e}{Style.RESET_ALL}")
            self.plugin_manager = None

    def _init_component_manager(self):
        """初始化组件管理器"""
        try:
            from ..core import get_component_manager

            self.component_manager = get_component_manager()
            if self.component_manager is None:
                # 创建一个简单的核心实例
                from types import SimpleNamespace

                from ..core import ComponentManager

                try:
                    from ..core import get_config_manager, get_event_manager

                    event_manager = get_event_manager()
                    config_manager = get_config_manager()
                except:
                    event_manager = None
                    config_manager = None

                mock_core = SimpleNamespace(
                    event_manager=event_manager,
                    config_manager=config_manager,
                    logger=logging.getLogger("aetherius.core"),
                )
                self.component_manager = ComponentManager(mock_core)
            print(f"{Fore.GREEN}✓ 已初始化组件管理器{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ 组件管理器初始化失败: {e}{Style.RESET_ALL}")
            self.component_manager = None

    def _setup_server_monitoring(self):
        """设置服务器监听和事件订阅"""
        if self.server_manager:
            try:
                # 设置日志处理器
                if hasattr(self.server_manager, "set_stdout_handler"):
                    self.server_manager.set_stdout_handler(self._handle_server_log)

                # 启动日志文件监控
                self._start_log_file_monitoring()

                # 设置事件监听
                self._setup_event_listeners()

                print(f"{Fore.GREEN}✓ 已连接服务器日志流{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠ 服务器监听设置失败: {e}{Style.RESET_ALL}")

    def _start_log_file_monitoring(self):
        """启动日志文件监控，持续显示服务器日志"""
        import os
        import threading
        import time

        def monitor_log_file():
            # 常见的日志文件路径
            log_paths = [
                "/workspaces/aetheriusmc.github.io/Aetherius-Core/server/logs/latest.log",
                "server/logs/latest.log",
                "logs/latest.log",
            ]

            log_file = None
            for path in log_paths:
                if os.path.exists(path):
                    log_file = path
                    break

            if not log_file:
                print(f"{Fore.YELLOW}⚠ 未找到服务器日志文件{Style.RESET_ALL}")
                return

            print(f"{Fore.GREEN}✓ 监控日志文件: {log_file}{Style.RESET_ALL}")

            # 监控日志文件变化
            last_size = 0
            try:
                if os.path.exists(log_file):
                    last_size = os.path.getsize(log_file)
            except:
                pass

            while True:
                try:
                    if os.path.exists(log_file):
                        current_size = os.path.getsize(log_file)
                        if current_size > last_size:
                            with open(log_file, encoding="utf-8", errors="ignore") as f:
                                f.seek(last_size)
                                new_lines = f.read()
                                if new_lines:
                                    for line in new_lines.strip().split("\n"):
                                        if line.strip():
                                            self._handle_server_log(line.strip())
                            last_size = current_size
                    time.sleep(0.5)  # 每0.5秒检查一次
                except Exception:
                    # 静默处理文件访问错误
                    time.sleep(1)

        # 在后台线程中运行日志监控
        log_monitor_thread = threading.Thread(target=monitor_log_file, daemon=True)
        log_monitor_thread.start()

    def _handle_server_log(self, line: str):
        """处理服务器日志行"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        # 解析服务器日志格式，提取关键信息
        if "][" in line:
            # 标准MC服务器日志格式: [时间] [线程/级别]: 消息
            try:
                parts = line.split("]")
                if len(parts) >= 3:
                    level_part = parts[1].strip("[]")
                    message = "]".join(parts[2:]).strip(": ")

                    # 根据日志级别着色
                    if "INFO" in level_part:
                        print(
                            f"{Fore.GREEN}[{timestamp}] MC日志:{Style.RESET_ALL} {message}"
                        )
                    elif "WARN" in level_part:
                        print(
                            f"{Fore.YELLOW}[{timestamp}] MC警告:{Style.RESET_ALL} {message}"
                        )
                    elif "ERROR" in level_part:
                        print(
                            f"{Fore.RED}[{timestamp}] MC错误:{Style.RESET_ALL} {message}"
                        )
                    else:
                        print(
                            f"{Fore.CYAN}[{timestamp}] MC日志:{Style.RESET_ALL} {message}"
                        )
                else:
                    print(f"{Fore.GREEN}[{timestamp}] MC日志:{Style.RESET_ALL} {line}")
            except:
                print(f"{Fore.GREEN}[{timestamp}] MC日志:{Style.RESET_ALL} {line}")
        else:
            print(f"{Fore.GREEN}[{timestamp}] MC日志:{Style.RESET_ALL} {line}")

    def _setup_event_listeners(self):
        """设置事件监听器"""
        try:
            from ..core.event_manager import get_event_manager
            from ..core.events import PlayerChatEvent, PlayerJoinEvent, PlayerLeaveEvent

            event_manager = get_event_manager()

            # 注册事件监听器
            def on_player_join(event):
                print(f"{Fore.CYAN}[PLAYER]{Style.RESET_ALL} {event.player_name} 加入了游戏")

            def on_player_leave(event):
                print(f"{Fore.CYAN}[PLAYER]{Style.RESET_ALL} {event.player_name} 离开了游戏")

            def on_player_chat(event):
                print(
                    f"{Fore.BLUE}[CHAT]{Style.RESET_ALL} <{event.player_name}> {event.message}"
                )

            # 注册监听器
            event_manager.register_listener(PlayerJoinEvent, on_player_join)
            event_manager.register_listener(PlayerLeaveEvent, on_player_leave)
            event_manager.register_listener(PlayerChatEvent, on_player_chat)

            print(f"{Fore.GREEN}✓ 已注册事件监听器{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ 事件监听器设置失败: {e}{Style.RESET_ALL}")

    def _init_enhanced_console(self):
        """初始化增强控制台接口"""
        try:
            if self.server_manager:
                # 获取RCON配置
                rcon_config = get_default_rcon_config()

                # 尝试从配置中获取RCON设置
                try:
                    if hasattr(self.server_manager, "config"):
                        config = self.server_manager.config
                        if hasattr(config, "rcon_password"):
                            rcon_config["password"] = config.rcon_password
                        if hasattr(config, "rcon_port"):
                            rcon_config["port"] = config.rcon_port
                except:
                    pass

                # 异步初始化增强控制台 - 使用管理器
                def init_console():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        self.enhanced_console = loop.run_until_complete(
                            get_managed_console_interface(
                                self.server_manager, rcon_config
                            )
                        )
                        if self.enhanced_console:
                            self._console_initialized = True
                            print(f"{Fore.GREEN}✓ 已初始化增强控制台接口 (管理器){Style.RESET_ALL}")
                        else:
                            print(f"{Fore.YELLOW}⚠ 增强控制台初始化失败{Style.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.YELLOW}⚠ 增强控制台初始化失败: {e}{Style.RESET_ALL}")
                    finally:
                        loop.close()

                import threading

                threading.Thread(target=init_console, daemon=True).start()
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ 增强控制台设置失败: {e}{Style.RESET_ALL}")

    def _execute_async_command(self, command: str):
        """执行异步命令并获取反馈 - 使用增强控制台接口"""
        try:
            # 检查服务器是否正在运行
            if (
                hasattr(self.server_manager, "is_alive")
                and not self.server_manager.is_alive
            ):
                print(f"{Fore.RED}  ✗ 服务器未运行{Style.RESET_ALL}")
                return

            # 优先使用增强控制台接口
            if self._console_initialized and self.enhanced_console:
                import asyncio
                import threading

                def execute_with_enhanced_console():
                    try:

                        async def run_enhanced_command():
                            # 确定命令优先级
                            priority = CommandPriority.NORMAL
                            if command.startswith(("stop", "restart", "save-all")):
                                priority = CommandPriority.HIGH
                            elif command.startswith(("backup", "whitelist")):
                                priority = CommandPriority.CRITICAL

                            result = await self.enhanced_console.send_command(
                                command, priority=priority, timeout=30.0
                            )

                            # 显示详细结果，添加前缀标识
                            prefix = self._get_command_prefix(
                                command, CommandType.MINECRAFT
                            )
                            if result.success:
                                print(
                                    f"{Fore.GREEN}  ✓ 命令执行成功 ({result.connection_type}){Style.RESET_ALL}"
                                )
                                if result.output:
                                    # 解析并显示服务器输出，添加前缀
                                    for line in result.output.strip().split("\n"):
                                        if line.strip():
                                            print(f"  {prefix}: {line.strip()}")
                                print(
                                    f"{Fore.CYAN}  执行时间: {result.execution_time:.3f}s{Style.RESET_ALL}"
                                )
                            else:
                                print(
                                    f"{Fore.RED}  ✗ 命令执行失败 ({result.connection_type}){Style.RESET_ALL}"
                                )
                                if result.error:
                                    print(
                                        f"{Fore.RED}  错误: {result.error}{Style.RESET_ALL}"
                                    )

                        # 创建新的事件循环执行
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(run_enhanced_command())
                        finally:
                            loop.close()

                    except Exception as e:
                        print(f"{Fore.RED}  ✗ 增强控制台执行错误: {e}{Style.RESET_ALL}")
                        # 回退到传统方法
                        self._execute_fallback_command(command)

                # 在后台线程执行
                thread = threading.Thread(
                    target=execute_with_enhanced_console, daemon=True
                )
                thread.start()

            else:
                # 回退到传统方法
                self._execute_fallback_command(command)

        except Exception as e:
            print(f"{Fore.RED}  ✗ 异步执行错误: {e}{Style.RESET_ALL}")

    def _execute_fallback_command(self, command: str):
        """传统命令执行方法作为回退"""
        try:
            # 如果服务器有命令队列系统，尝试使用
            if hasattr(self.server_manager, "command_queue"):
                import asyncio
                import threading

                def execute_command():
                    try:
                        # 在新线程中运行异步命令
                        async def run_command():
                            try:
                                command_queue = self.server_manager.command_queue
                                command_id = command_queue.add_command(command)

                                # 缩短超时时间，更快反馈
                                result = await command_queue.wait_for_completion(
                                    command_id, timeout=10.0
                                )

                                # 显示结果
                                if result["status"] == "completed":
                                    if result.get("success", False):
                                        print(
                                            f"{Fore.GREEN}  ✓ 命令执行成功 (队列){Style.RESET_ALL}"
                                        )
                                        if "output" in result and result["output"]:
                                            print(
                                                f"{Fore.BLUE}  输出: {result['output']}{Style.RESET_ALL}"
                                            )
                                    else:
                                        print(f"{Fore.RED}  ✗ 命令执行失败{Style.RESET_ALL}")
                                else:
                                    print(f"{Fore.YELLOW}  ⚠ 命令超时{Style.RESET_ALL}")

                            except Exception as e:
                                print(f"{Fore.RED}  ✗ 命令执行错误: {e}{Style.RESET_ALL}")

                        # 运行异步命令
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(run_command())
                        finally:
                            loop.close()

                    except Exception as e:
                        print(f"{Fore.RED}  ✗ 队列执行错误: {e}{Style.RESET_ALL}")

                # 在后台线程执行
                thread = threading.Thread(target=execute_command, daemon=True)
                thread.start()

            # 如果没有队列，尝试直接发送
            elif hasattr(self.server_manager, "send_command"):
                import asyncio
                import threading

                def direct_send():
                    try:

                        async def send_now():
                            success = await self.server_manager.send_command(command)
                            if success:
                                print(
                                    f"{Fore.GREEN}  ✓ 命令已发送 (direct){Style.RESET_ALL}"
                                )
                            else:
                                print(f"{Fore.RED}  ✗ 命令发送失败{Style.RESET_ALL}")

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(send_now())
                        finally:
                            loop.close()
                    except Exception:
                        print(f"{Fore.YELLOW}  └─ 回退发送: {command}{Style.RESET_ALL}")

                thread = threading.Thread(target=direct_send, daemon=True)
                thread.start()

            else:
                print(f"{Fore.BLUE}  └─ 命令已记录 (模拟模式){Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}  ✗ 回退执行错误: {e}{Style.RESET_ALL}")

    def _print_startup(self):
        """打印启动信息和ASCII艺术横幅"""
        # ASCII艺术横幅
        ascii_banner = f"""{Fore.CYAN}
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║    █████╗ ███████╗████████╗██╗  ██╗███████╗██████╗ ██╗██╗   ██╗███║
║   ██╔══██╗██╔════╝╚══██╔══╝██║  ██║██╔════╝██╔══██╗██║██║   ██║██╔║
║   ███████║█████╗     ██║   ███████║█████╗  ██████╔╝██║██║   ██║███║
║   ██╔══██║██╔══╝     ██║   ██╔══██║██╔══╝  ██╔══██╗██║██║   ██║╚══║
║   ██║  ██║███████╗   ██║   ██║  ██║███████╗██║  ██║██║╚██████╔╝███║
║   ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝ ╚═════╝ ╚══║
║                                                                   ║
║               高性能 Minecraft 服务器管理引擎                        ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}

{Fore.GREEN}✓ Aetherius Console Ready{Style.RESET_ALL}

{Fore.YELLOW}统一前缀识别系统:{Style.RESET_ALL}
  {Fore.WHITE}/ {Style.RESET_ALL} - MC指令 (直接发送至Minecraft服务器)
  {Fore.WHITE}! {Style.RESET_ALL} - Aetherius系统指令
  {Fore.WHITE}@ {Style.RESET_ALL} - 脚本指令 (执行自定义脚本)
  {Fore.WHITE}# {Style.RESET_ALL} - 插件指令 (调用插件特定功能)
  {Fore.WHITE}$ {Style.RESET_ALL} - 组件指令 (组件管理命令)
  {Fore.WHITE}% {Style.RESET_ALL} - 管理指令 (管理相关命令)

{Fore.CYAN}输入 !help 查看详细帮助{Style.RESET_ALL}
"""
        print(ascii_banner)

    def _get_command_prefix(self, command: str, cmd_type: CommandType) -> str:
        """获取命令前缀标识，统一前缀系统"""
        if cmd_type == CommandType.MINECRAFT:
            return "MC指令响应"
        elif cmd_type == CommandType.AETHERIUS:
            return "Aetherius系统响应"
        elif cmd_type == CommandType.SCRIPT:
            return "脚本执行响应"
        elif cmd_type == CommandType.PLUGIN:
            return "插件指令响应"
        elif cmd_type == CommandType.COMPONENT:
            return "组件指令响应"
        elif cmd_type == CommandType.ADMIN:
            return "管理指令响应"
        else:
            return "服务器响应"

    def _parse_command(self, command: str):
        """解析命令类型"""
        if not command:
            return CommandType.CHAT, ""

        first_char = command[0]
        for cmd_type in CommandType:
            if first_char == cmd_type.value:
                return cmd_type, command[1:].strip()

        return CommandType.CHAT, command

    def _execute_minecraft_command(self, command: str):
        """执行Minecraft命令"""
        if self.server_manager:
            try:
                # 检查服务器管理器的正确方法
                if hasattr(self.server_manager, "send_command"):
                    # ServerProcessWrapper使用异步send_command方法
                    import inspect

                    # 检查方法是否为协程函数
                    if inspect.iscoroutinefunction(self.server_manager.send_command):
                        # 对于异步方法，先检查服务器状态
                        if (
                            hasattr(self.server_manager, "is_alive")
                            and not self.server_manager.is_alive
                        ):
                            print(
                                f"{Fore.RED}→ Minecraft (未运行):{Style.RESET_ALL} /{command}"
                            )
                            print(f"{Fore.RED}  ✗ 服务器未启动{Style.RESET_ALL}")
                        else:
                            print(
                                f"{Fore.YELLOW}→ Minecraft:{Style.RESET_ALL} /{command}"
                            )

                            # 使用队列方法获取命令反馈
                            self._execute_async_command(command)
                    else:
                        # 同步版本的send_command
                        try:
                            success = self.server_manager.send_command(command)
                            if success:
                                print(
                                    f"{Fore.GREEN}→ Minecraft:{Style.RESET_ALL} /{command}"
                                )
                            else:
                                print(f"{Fore.RED}✗ Minecraft:{Style.RESET_ALL} 命令发送失败")
                        except Exception as e:
                            print(f"{Fore.RED}✗ Minecraft错误:{Style.RESET_ALL} {e}")

                elif hasattr(self.server_manager, "execute_command"):
                    # 同步方法 (MockServerManager等)
                    result = self.server_manager.execute_command(command)
                    print(f"{Fore.GREEN}→ Minecraft:{Style.RESET_ALL} /{command}")

                else:
                    # 未知接口，显示为模拟
                    print(f"{Fore.YELLOW}→ 模拟Minecraft:{Style.RESET_ALL} /{command}")

            except Exception as e:
                print(f"{Fore.RED}✗ Minecraft错误:{Style.RESET_ALL} {e}")
        else:
            print(f"{Fore.YELLOW}→ 模拟Minecraft:{Style.RESET_ALL} /{command}")

    def _execute_aetherius_command(self, command: str):
        """执行Aetherius命令"""
        if command in ["quit", "exit"]:
            print(f"{Fore.YELLOW}再见!{Style.RESET_ALL}")
            self.is_running = False
            return

        elif command == "help":
            self._show_help()

        elif command == "status":
            self._show_status()

        elif command == "clear":
            os.system("clear" if os.name == "posix" else "cls")
            self._print_startup()

        elif command == "server":
            self._show_server_status()

        else:
            print(f"{Fore.CYAN}→ Aetherius:{Style.RESET_ALL} !{command}")

    def _execute_plugin_command(self, command: str):
        """执行插件命令"""
        if not command:
            print(f"{Fore.YELLOW}请指定插件命令。使用 #help 查看帮助{Style.RESET_ALL}")
            return

        if command == "help":
            self._show_plugin_help()
        elif command == "list":
            self._list_plugins()
        elif command.startswith("enable "):
            plugin_name = command[7:].strip()
            self._enable_plugin(plugin_name)
        elif command.startswith("disable "):
            plugin_name = command[8:].strip()
            self._disable_plugin(plugin_name)
        elif command.startswith("reload "):
            plugin_name = command[7:].strip()
            self._reload_plugin(plugin_name)
        elif command.startswith("info "):
            plugin_name = command[5:].strip()
            self._show_plugin_info(plugin_name)
        else:
            print(f"{Fore.YELLOW}未知的插件命令: #{command}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}使用 #help 查看可用命令{Style.RESET_ALL}")

    def _show_plugin_help(self):
        """显示插件命令帮助"""
        help_text = f"""
{Fore.MAGENTA}=== 插件管理命令帮助 ==={Style.RESET_ALL}

{Fore.YELLOW}可用命令:{Style.RESET_ALL}
  #help               显示此帮助信息
  #list               列出所有插件
  #enable <插件名>     启用指定插件
  #disable <插件名>    禁用指定插件
  #reload <插件名>     重载指定插件
  #info <插件名>       显示插件详细信息

{Fore.YELLOW}示例:{Style.RESET_ALL}
  #list
  #enable MyPlugin
  #disable MyPlugin
  #reload MyPlugin
  #info MyPlugin
"""
        print(help_text)

    def _list_plugins(self):
        """列出所有插件"""
        try:
            # 尝试获取插件管理器
            plugin_manager = None
            if self.server_manager and hasattr(self.server_manager, "plugin_manager"):
                plugin_manager = self.server_manager.plugin_manager
            elif hasattr(self, "core") and hasattr(self.core, "plugin_manager"):
                plugin_manager = self.core.plugin_manager
            else:
                # 尝试从全局获取
                try:
                    from ..core import get_plugin_manager

                    plugin_manager = get_plugin_manager()
                except:
                    pass

            if not plugin_manager:
                print(f"{Fore.YELLOW}插件管理器不可用{Style.RESET_ALL}")
                return

            # 获取插件列表
            if hasattr(plugin_manager, "list_plugins"):
                plugins = plugin_manager.list_plugins()
                if not plugins:
                    print(f"{Fore.YELLOW}未找到任何插件{Style.RESET_ALL}")
                    return

                print(f"{Fore.MAGENTA}=== 插件列表 ==={Style.RESET_ALL}")
                for plugin_name in plugins:
                    is_enabled = (
                        plugin_manager.is_enabled(plugin_name)
                        if hasattr(plugin_manager, "is_enabled")
                        else False
                    )
                    status = (
                        f"{Fore.GREEN}[启用]{Style.RESET_ALL}"
                        if is_enabled
                        else f"{Fore.RED}[禁用]{Style.RESET_ALL}"
                    )
                    print(f"  {status} {plugin_name}")
            else:
                print(f"{Fore.YELLOW}插件管理器不支持列表功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}获取插件列表失败: {e}{Style.RESET_ALL}")

    def _enable_plugin(self, plugin_name: str):
        """启用插件"""
        if not plugin_name:
            print(f"{Fore.YELLOW}请指定插件名称{Style.RESET_ALL}")
            return

        try:
            plugin_manager = self._get_plugin_manager()
            if not plugin_manager:
                print(f"{Fore.RED}插件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(plugin_manager, "enable_plugin"):
                # 如果是异步方法
                import asyncio
                import inspect

                if inspect.iscoroutinefunction(plugin_manager.enable_plugin):

                    def run_async():
                        try:
                            # 创建新的事件循环
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(
                                    plugin_manager.enable_plugin(plugin_name)
                                )
                                if result:
                                    print(
                                        f"{Fore.GREEN}✓ 插件 {plugin_name} 已启用{Style.RESET_ALL}"
                                    )
                                else:
                                    print(
                                        f"{Fore.RED}✗ 插件 {plugin_name} 启用失败{Style.RESET_ALL}"
                                    )
                            finally:
                                loop.close()
                        except Exception as e:
                            print(f"{Fore.RED}✗ 启用插件失败: {e}{Style.RESET_ALL}")

                    import threading

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                    thread.join()  # 等待完成
                else:
                    # 同步方法
                    result = plugin_manager.enable_plugin(plugin_name)
                    if result:
                        print(f"{Fore.GREEN}✓ 插件 {plugin_name} 已启用{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ 插件 {plugin_name} 启用失败{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}插件管理器不支持启用功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}启用插件失败: {e}{Style.RESET_ALL}")

    def _disable_plugin(self, plugin_name: str):
        """禁用插件"""
        if not plugin_name:
            print(f"{Fore.YELLOW}请指定插件名称{Style.RESET_ALL}")
            return

        try:
            plugin_manager = self._get_plugin_manager()
            if not plugin_manager:
                print(f"{Fore.RED}插件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(plugin_manager, "disable_plugin"):
                # 如果是异步方法
                import asyncio
                import inspect

                if inspect.iscoroutinefunction(plugin_manager.disable_plugin):

                    def run_async():
                        try:
                            # 创建新的事件循环
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(
                                    plugin_manager.disable_plugin(plugin_name)
                                )
                                if result:
                                    print(
                                        f"{Fore.GREEN}✓ 插件 {plugin_name} 已禁用{Style.RESET_ALL}"
                                    )
                                else:
                                    print(
                                        f"{Fore.RED}✗ 插件 {plugin_name} 禁用失败{Style.RESET_ALL}"
                                    )
                            finally:
                                loop.close()
                        except Exception as e:
                            print(f"{Fore.RED}✗ 禁用插件失败: {e}{Style.RESET_ALL}")

                    import threading

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                    thread.join()  # 等待完成
                else:
                    # 同步方法
                    result = plugin_manager.disable_plugin(plugin_name)
                    if result:
                        print(f"{Fore.GREEN}✓ 插件 {plugin_name} 已禁用{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ 插件 {plugin_name} 禁用失败{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}插件管理器不支持禁用功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}禁用插件失败: {e}{Style.RESET_ALL}")

    def _reload_plugin(self, plugin_name: str):
        """重载插件"""
        if not plugin_name:
            print(f"{Fore.YELLOW}请指定插件名称{Style.RESET_ALL}")
            return

        try:
            plugin_manager = self._get_plugin_manager()
            if not plugin_manager:
                print(f"{Fore.RED}插件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(plugin_manager, "reload_plugin"):
                # 如果是异步方法
                import asyncio
                import inspect

                if inspect.iscoroutinefunction(plugin_manager.reload_plugin):

                    def run_async():
                        try:
                            # 创建新的事件循环
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(
                                    plugin_manager.reload_plugin(plugin_name)
                                )
                                if result:
                                    print(
                                        f"{Fore.GREEN}✓ 插件 {plugin_name} 已重载{Style.RESET_ALL}"
                                    )
                                else:
                                    print(
                                        f"{Fore.RED}✗ 插件 {plugin_name} 重载失败{Style.RESET_ALL}"
                                    )
                            finally:
                                loop.close()
                        except Exception as e:
                            print(f"{Fore.RED}✗ 重载插件失败: {e}{Style.RESET_ALL}")

                    import threading

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                    thread.join()  # 等待完成
                else:
                    # 同步方法
                    result = plugin_manager.reload_plugin(plugin_name)
                    if result:
                        print(f"{Fore.GREEN}✓ 插件 {plugin_name} 已重载{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ 插件 {plugin_name} 重载失败{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}插件管理器不支持重载功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}重载插件失败: {e}{Style.RESET_ALL}")

    def _show_plugin_info(self, plugin_name: str):
        """显示插件详细信息"""
        if not plugin_name:
            print(f"{Fore.YELLOW}请指定插件名称{Style.RESET_ALL}")
            return

        try:
            plugin_manager = self._get_plugin_manager()
            if not plugin_manager:
                print(f"{Fore.RED}插件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(plugin_manager, "get_plugin_info"):
                plugin_info = plugin_manager.get_plugin_info(plugin_name)
                if plugin_info:
                    print(f"{Fore.MAGENTA}=== 插件信息: {plugin_name} ==={Style.RESET_ALL}")
                    if hasattr(plugin_info, "to_dict"):
                        info_dict = plugin_info.to_dict()
                        for key, value in info_dict.items():
                            print(f"  {key}: {value}")
                    else:
                        print(f"  信息: {plugin_info}")
                else:
                    print(f"{Fore.YELLOW}未找到插件: {plugin_name}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}插件管理器不支持信息查询功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}获取插件信息失败: {e}{Style.RESET_ALL}")

    def _get_plugin_manager(self):
        """获取插件管理器"""
        # 尝试多种方式获取插件管理器
        plugin_manager = None

        # 方式1: 使用控制台的插件管理器
        if hasattr(self, "plugin_manager") and self.plugin_manager:
            plugin_manager = self.plugin_manager

        # 方式2: 从服务器管理器获取
        elif self.server_manager and hasattr(self.server_manager, "plugin_manager"):
            plugin_manager = self.server_manager.plugin_manager

        # 方式3: 从核心实例获取
        elif hasattr(self, "core") and hasattr(self.core, "plugin_manager"):
            plugin_manager = self.core.plugin_manager

        # 方式4: 从全局获取
        else:
            try:
                from ..core import get_plugin_manager

                plugin_manager = get_plugin_manager()
            except:
                pass

        return plugin_manager

    def _execute_component_command(self, command: str):
        """执行组件命令"""
        if not command:
            print(f"{Fore.YELLOW}请指定组件命令。使用 $help 查看帮助{Style.RESET_ALL}")
            return

        if command == "help":
            self._show_component_help()
        elif command == "list":
            self._list_components()
        elif command.startswith("load "):
            component_name = command[5:].strip()
            self._load_component(component_name)
        elif command.startswith("enable "):
            component_name = command[7:].strip()
            self._enable_component(component_name)
        elif command.startswith("disable "):
            component_name = command[8:].strip()
            self._disable_component(component_name)
        elif command.startswith("reload "):
            component_name = command[7:].strip()
            self._reload_component(component_name)
        elif command.startswith("info "):
            component_name = command[5:].strip()
            self._show_component_info(component_name)
        elif command == "scan":
            self._scan_components()
        else:
            print(f"{Fore.YELLOW}未知的组件命令: ${command}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}使用 $help 查看可用命令{Style.RESET_ALL}")

    def _show_component_help(self):
        """显示组件命令帮助"""
        help_text = f"""
{Fore.MAGENTA}=== 组件管理命令帮助 ==={Style.RESET_ALL}

{Fore.YELLOW}可用命令:{Style.RESET_ALL}
  $help               显示此帮助信息
  $list               列出所有组件
  $scan               扫描并发现组件
  $load <组件名>       加载指定组件
  $enable <组件名>     启用指定组件
  $disable <组件名>    禁用指定组件
  $reload <组件名>     重载指定组件
  $info <组件名>       显示组件详细信息

{Fore.YELLOW}示例:{Style.RESET_ALL}
  $list
  $scan
  $load TestComponent
  $enable TestComponent
  $disable TestComponent
  $reload TestComponent
  $info TestComponent
"""
        print(help_text)

    def _list_components(self):
        """列出所有组件"""
        try:
            component_manager = self._get_component_manager()
            if not component_manager:
                print(f"{Fore.YELLOW}组件管理器不可用{Style.RESET_ALL}")
                return

            # 获取组件列表
            if hasattr(component_manager, "list_loaded_components"):
                components = component_manager.list_loaded_components()
                if not components:
                    print(f"{Fore.YELLOW}未找到任何组件{Style.RESET_ALL}")
                    return

                print(f"{Fore.MAGENTA}=== 组件列表 ==={Style.RESET_ALL}")
                for component_name in components:
                    is_enabled = (
                        component_manager.is_enabled(component_name)
                        if hasattr(component_manager, "is_enabled")
                        else False
                    )
                    status = (
                        f"{Fore.GREEN}[启用]{Style.RESET_ALL}"
                        if is_enabled
                        else f"{Fore.RED}[禁用]{Style.RESET_ALL}"
                    )
                    print(f"  {status} {component_name}")
            else:
                print(f"{Fore.YELLOW}组件管理器不支持列表功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}获取组件列表失败: {e}{Style.RESET_ALL}")

    def _scan_components(self):
        """扫描组件"""
        try:
            component_manager = self._get_component_manager()
            if not component_manager:
                print(f"{Fore.RED}组件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(component_manager, "scan_components"):
                print(f"{Fore.CYAN}正在扫描组件...{Style.RESET_ALL}")
                # 处理异步方法
                import asyncio
                import inspect

                if inspect.iscoroutinefunction(component_manager.scan_components):

                    def run_async():
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                discovered = loop.run_until_complete(
                                    component_manager.scan_components()
                                )
                                print(
                                    f"{Fore.GREEN}✓ 发现 {len(discovered)} 个组件{Style.RESET_ALL}"
                                )
                                for component_name in discovered:
                                    print(f"  - {component_name}")
                            finally:
                                loop.close()
                        except Exception as e:
                            print(f"{Fore.RED}✗ 扫描失败: {e}{Style.RESET_ALL}")

                    import threading

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                    thread.join()
                else:
                    discovered = component_manager.scan_components()
                    print(f"{Fore.GREEN}✓ 发现 {len(discovered)} 个组件{Style.RESET_ALL}")
                    for component_name in discovered:
                        print(f"  - {component_name}")
            else:
                print(f"{Fore.YELLOW}组件管理器不支持扫描功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}扫描组件失败: {e}{Style.RESET_ALL}")

    def _load_component(self, component_name: str):
        """加载组件"""
        if not component_name:
            print(f"{Fore.YELLOW}请指定组件名称{Style.RESET_ALL}")
            return

        try:
            component_manager = self._get_component_manager()
            if not component_manager:
                print(f"{Fore.RED}组件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(component_manager, "load_component"):
                # 如果是异步方法
                import asyncio
                import inspect

                if inspect.iscoroutinefunction(component_manager.load_component):

                    def run_async():
                        try:
                            # 创建新的事件循环
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(
                                    component_manager.load_component(component_name)
                                )
                                if result:
                                    print(
                                        f"{Fore.GREEN}✓ 组件 {component_name} 已加载{Style.RESET_ALL}"
                                    )
                                else:
                                    print(
                                        f"{Fore.RED}✗ 组件 {component_name} 加载失败{Style.RESET_ALL}"
                                    )
                            finally:
                                loop.close()
                        except Exception as e:
                            print(f"{Fore.RED}✗ 加载组件失败: {e}{Style.RESET_ALL}")

                    import threading

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                    thread.join()  # 等待完成
                else:
                    # 同步方法
                    result = component_manager.load_component(component_name)
                    if result:
                        print(f"{Fore.GREEN}✓ 组件 {component_name} 已加载{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ 组件 {component_name} 加载失败{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}组件管理器不支持加载功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}加载组件失败: {e}{Style.RESET_ALL}")

    def _enable_component(self, component_name: str):
        """启用组件 - 使用标准启动脚本"""
        if not component_name:
            print(f"{Fore.YELLOW}请指定组件名称{Style.RESET_ALL}")
            return

        try:
            # 首先查找组件标准启动脚本
            component_script_path = self._find_component_start_script(component_name)

            if component_script_path:
                # 使用标准启动脚本启用组件
                print(f"{Fore.CYAN}使用标准启动脚本启用组件 {component_name}...{Style.RESET_ALL}")
                self._start_component_with_script(component_name, component_script_path)
            else:
                # 回退到组件管理器方法
                print(f"{Fore.YELLOW}未找到标准启动脚本，使用组件管理器启用...{Style.RESET_ALL}")
                self._enable_component_fallback(component_name)

        except Exception as e:
            print(f"{Fore.RED}启用组件失败: {e}{Style.RESET_ALL}")

    def _find_component_start_script(self, component_name: str):
        """查找组件的标准启动脚本"""

        # 可能的组件路径
        component_paths = [
            # 如果当前就在组件目录内
            Path("start_component.py"),  # 当前目录就是组件目录
            Path(f"../Component{component_name}/start_component.py"),  # 从其他组件目录切换
            # 相对于当前工作目录
            Path(f"components/{component_name}/start_component.py"),
            Path(f"components/Component{component_name}/start_component.py"),
            # 相对于Aetherius根目录
            Path("../components") / component_name / "start_component.py",
            Path("../components") / f"Component{component_name}" / "start_component.py",
            # 从更深层目录向上查找
            Path("../../components") / component_name / "start_component.py",
            Path("../../components")
            / f"Component{component_name}"
            / "start_component.py",
            # 绝对路径
            Path("/workspaces/aetheriusmc.github.io/Aetherius-Core/components")
            / component_name
            / "start_component.py",
            Path("/workspaces/aetheriusmc.github.io/Aetherius-Core/components")
            / f"Component{component_name}"
            / "start_component.py",
            # 当前目录的components路径
            Path.cwd() / "components" / component_name / "start_component.py",
            Path.cwd()
            / "components"
            / f"Component{component_name}"
            / "start_component.py",
            # 尝试从父目录查找
            Path.cwd().parent / "components" / component_name / "start_component.py",
            Path.cwd().parent
            / "components"
            / f"Component{component_name}"
            / "start_component.py",
        ]

        for path in component_paths:
            if path.exists() and path.is_file():
                print(f"{Fore.GREEN}✓ 找到组件启动脚本: {path}{Style.RESET_ALL}")
                return path

        print(
            f"{Fore.YELLOW}⚠ 未找到组件 {component_name} 的标准启动脚本 (start_component.py){Style.RESET_ALL}"
        )
        return None

    def _start_component_with_script(self, component_name: str, script_path: Path):
        """使用标准启动脚本启动组件"""
        import subprocess
        import threading
        import time

        def run_component():
            try:
                print(f"{Fore.CYAN}正在启动组件 {component_name}...{Style.RESET_ALL}")
                print(f"{Fore.MAGENTA}╭─── 组件启动日志 ───╮{Style.RESET_ALL}")

                # 使用Popen以便实时获取输出 - 默认启动所有服务
                process = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                # 实时读取并显示输出
                start_time = time.time()
                timeout = 60  # 60秒超时
                component_ready = False  # 组件完成标志

                while True:
                    # 检查进程是否结束
                    if process.poll() is not None:
                        break

                    # 检查超时
                    if time.time() - start_time > timeout:
                        print(f"{Fore.YELLOW}│ ⚠ 启动超时，终止进程...{Style.RESET_ALL}")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        break

                    # 读取输出
                    try:
                        line = process.stdout.readline()
                        if line:
                            # 格式化日志行
                            formatted_line = line.rstrip("\n\r")
                            if formatted_line.strip():
                                # 检查组件启动完成标注
                                if (
                                    "AETHERIUS_COMPONENT_STATUS: READY"
                                    in formatted_line
                                ):
                                    component_ready = True
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.GREEN}{formatted_line}{Style.RESET_ALL}"
                                    )
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.CYAN}🎉 检测到组件启动完成标注{Style.RESET_ALL}"
                                    )
                                    # 继续显示剩余的标注信息
                                    continue

                                # 检查是否是关闭启动日志窗口的通知
                                if component_ready and (
                                    "console可以关闭启动日志窗口" in formatted_line
                                    or "🔔 通知:" in formatted_line
                                ):
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.YELLOW}{formatted_line}{Style.RESET_ALL}"
                                    )
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.GREEN}📝 组件启动脚本执行完成，自动关闭启动日志窗口{Style.RESET_ALL}"
                                    )
                                    # 等待一秒让用户看到消息，然后关闭日志窗口
                                    time.sleep(1)
                                    break

                                # 如果组件已就绪但还有其他标注信息，继续显示
                                if component_ready and (
                                    formatted_line.startswith("AETHERIUS_")
                                    or "SERVICE_" in formatted_line
                                ):
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.CYAN}{formatted_line}{Style.RESET_ALL}"
                                    )
                                    continue

                                # 根据内容类型着色
                                if (
                                    "✓" in formatted_line
                                    or "success" in formatted_line.lower()
                                ):
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.GREEN}{formatted_line}{Style.RESET_ALL}"
                                    )
                                elif (
                                    "✗" in formatted_line
                                    or "error" in formatted_line.lower()
                                    or "fail" in formatted_line.lower()
                                ):
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.RED}{formatted_line}{Style.RESET_ALL}"
                                    )
                                elif (
                                    "⚠" in formatted_line
                                    or "warn" in formatted_line.lower()
                                ):
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.YELLOW}{formatted_line}{Style.RESET_ALL}"
                                    )
                                elif "🚀" in formatted_line or "启动" in formatted_line:
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.CYAN}{formatted_line}{Style.RESET_ALL}"
                                    )
                                elif formatted_line.startswith(
                                    "INFO:"
                                ) or formatted_line.startswith("WARNING:"):
                                    # uvicorn日志格式
                                    if "INFO:" in formatted_line:
                                        print(
                                            f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.GREEN}[INFO]{Style.RESET_ALL} {formatted_line[5:]}"
                                        )
                                    elif "WARNING:" in formatted_line:
                                        print(
                                            f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.YELLOW}[WARN]{Style.RESET_ALL} {formatted_line[8:]}"
                                        )
                                else:
                                    print(
                                        f"{Fore.MAGENTA}│{Style.RESET_ALL} {formatted_line}"
                                    )
                        else:
                            time.sleep(0.1)  # 短暂等待
                    except Exception as e:
                        print(
                            f"{Fore.MAGENTA}│{Style.RESET_ALL} {Fore.RED}读取输出错误: {e}{Style.RESET_ALL}"
                        )
                        break

                # 如果组件已就绪并且检测到完成标注，则正常退出循环
                if component_ready:
                    print(f"{Fore.MAGENTA}╰─────────────────────╯{Style.RESET_ALL}")
                    print(
                        f"{Fore.GREEN}✓ 组件 {component_name} 启动成功，服务正在后台运行{Style.RESET_ALL}"
                    )
                    return  # 直接返回，不等待进程完成

                # 如果是因为超时或进程异常退出，检查退出码
                print(f"{Fore.MAGENTA}╰─────────────────────╯{Style.RESET_ALL}")

                if process.poll() is not None:
                    # 进程已退出
                    if process.returncode == 0:
                        print(
                            f"{Fore.GREEN}✓ 组件 {component_name} 启动脚本执行完成{Style.RESET_ALL}"
                        )
                    else:
                        print(
                            f"{Fore.RED}✗ 组件 {component_name} 启动失败 (退出码: {process.returncode}){Style.RESET_ALL}"
                        )
                else:
                    # 进程仍在运行（超时情况）
                    print(
                        f"{Fore.YELLOW}⚠ 组件 {component_name} 启动脚本超时，但进程可能在后台运行{Style.RESET_ALL}"
                    )
                    print(f"{Fore.CYAN}💡 提示: 如果是Web组件等长期运行的服务，这是正常的{Style.RESET_ALL}")

            except Exception as e:
                print(f"{Fore.MAGENTA}╰─────────────────────╯{Style.RESET_ALL}")
                print(f"{Fore.RED}✗ 执行启动脚本失败: {e}{Style.RESET_ALL}")

        # 在后台线程中运行
        thread = threading.Thread(target=run_component, daemon=True)
        thread.start()

        # 给用户一些反馈
        print(f"{Fore.CYAN}⏳ 正在启动组件，请稍候...{Style.RESET_ALL}")

        # 等待线程完成以显示完整日志
        try:
            thread.join(timeout=65)  # 等待最多65秒
            if thread.is_alive():
                print(f"{Fore.YELLOW}⚠ 组件启动线程仍在运行，请手动检查状态{Style.RESET_ALL}")
        except KeyboardInterrupt:
            print(f"{Fore.YELLOW}用户中断了组件启动过程{Style.RESET_ALL}")

    def _enable_component_fallback(self, component_name: str):
        """组件启用的回退方法"""
        try:
            component_manager = self._get_component_manager()
            if not component_manager:
                print(f"{Fore.RED}组件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(component_manager, "enable_component"):
                # 如果是异步方法
                import asyncio
                import inspect

                if inspect.iscoroutinefunction(component_manager.enable_component):

                    def run_async():
                        try:
                            # 创建新的事件循环
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(
                                    component_manager.enable_component(component_name)
                                )
                                if result:
                                    print(
                                        f"{Fore.GREEN}✓ 组件 {component_name} 已启用{Style.RESET_ALL}"
                                    )
                                else:
                                    print(
                                        f"{Fore.RED}✗ 组件 {component_name} 启用失败{Style.RESET_ALL}"
                                    )
                            finally:
                                loop.close()
                        except Exception as e:
                            print(f"{Fore.RED}✗ 启用组件失败: {e}{Style.RESET_ALL}")

                    import threading

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                    thread.join()  # 等待完成
                else:
                    # 同步方法
                    result = component_manager.enable_component(component_name)
                    if result:
                        print(f"{Fore.GREEN}✓ 组件 {component_name} 已启用{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ 组件 {component_name} 启用失败{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}组件管理器不支持启用功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}启用组件失败: {e}{Style.RESET_ALL}")

    def _disable_component(self, component_name: str):
        """禁用组件"""
        if not component_name:
            print(f"{Fore.YELLOW}请指定组件名称{Style.RESET_ALL}")
            return

        try:
            component_manager = self._get_component_manager()
            if not component_manager:
                print(f"{Fore.RED}组件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(component_manager, "disable_component"):
                # 如果是异步方法
                import asyncio
                import inspect

                if inspect.iscoroutinefunction(component_manager.disable_component):

                    def run_async():
                        try:
                            # 创建新的事件循环
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(
                                    component_manager.disable_component(component_name)
                                )
                                if result:
                                    print(
                                        f"{Fore.GREEN}✓ 组件 {component_name} 已禁用{Style.RESET_ALL}"
                                    )
                                else:
                                    print(
                                        f"{Fore.RED}✗ 组件 {component_name} 禁用失败{Style.RESET_ALL}"
                                    )
                            finally:
                                loop.close()
                        except Exception as e:
                            print(f"{Fore.RED}✗ 禁用组件失败: {e}{Style.RESET_ALL}")

                    import threading

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                    thread.join()  # 等待完成
                else:
                    # 同步方法
                    result = component_manager.disable_component(component_name)
                    if result:
                        print(f"{Fore.GREEN}✓ 组件 {component_name} 已禁用{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ 组件 {component_name} 禁用失败{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}组件管理器不支持禁用功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}禁用组件失败: {e}{Style.RESET_ALL}")

    def _reload_component(self, component_name: str):
        """重载组件"""
        if not component_name:
            print(f"{Fore.YELLOW}请指定组件名称{Style.RESET_ALL}")
            return

        try:
            component_manager = self._get_component_manager()
            if not component_manager:
                print(f"{Fore.RED}组件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(component_manager, "reload_component"):
                # 如果是异步方法
                import asyncio
                import inspect

                if inspect.iscoroutinefunction(component_manager.reload_component):

                    def run_async():
                        try:
                            # 创建新的事件循环
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(
                                    component_manager.reload_component(component_name)
                                )
                                if result:
                                    print(
                                        f"{Fore.GREEN}✓ 组件 {component_name} 已重载{Style.RESET_ALL}"
                                    )
                                else:
                                    print(
                                        f"{Fore.RED}✗ 组件 {component_name} 重载失败{Style.RESET_ALL}"
                                    )
                            finally:
                                loop.close()
                        except Exception as e:
                            print(f"{Fore.RED}✗ 重载组件失败: {e}{Style.RESET_ALL}")

                    import threading

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                    thread.join()  # 等待完成
                else:
                    # 同步方法
                    result = component_manager.reload_component(component_name)
                    if result:
                        print(f"{Fore.GREEN}✓ 组件 {component_name} 已重载{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ 组件 {component_name} 重载失败{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}组件管理器不支持重载功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}重载组件失败: {e}{Style.RESET_ALL}")

    def _show_component_info(self, component_name: str):
        """显示组件详细信息"""
        if not component_name:
            print(f"{Fore.YELLOW}请指定组件名称{Style.RESET_ALL}")
            return

        try:
            component_manager = self._get_component_manager()
            if not component_manager:
                print(f"{Fore.RED}组件管理器不可用{Style.RESET_ALL}")
                return

            if hasattr(component_manager, "get_component_info"):
                component_info = component_manager.get_component_info(component_name)
                if component_info:
                    print(
                        f"{Fore.MAGENTA}=== 组件信息: {component_name} ==={Style.RESET_ALL}"
                    )
                    if hasattr(component_info, "to_dict"):
                        info_dict = component_info.to_dict()
                        for key, value in info_dict.items():
                            print(f"  {key}: {value}")
                    else:
                        print(f"  信息: {component_info}")
                else:
                    print(f"{Fore.YELLOW}未找到组件: {component_name}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}组件管理器不支持信息查询功能{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}获取组件信息失败: {e}{Style.RESET_ALL}")

    def _get_component_manager(self):
        """获取组件管理器"""
        # 尝试多种方式获取组件管理器
        component_manager = None

        # 方式1: 使用控制台的组件管理器
        if hasattr(self, "component_manager") and self.component_manager:
            component_manager = self.component_manager

        # 方式2: 从服务器管理器获取
        elif self.server_manager and hasattr(self.server_manager, "component_manager"):
            component_manager = self.server_manager.component_manager

        # 方式3: 从核心实例获取
        elif hasattr(self, "core") and hasattr(self.core, "component_manager"):
            component_manager = self.core.component_manager

        # 方式4: 从全局获取
        else:
            try:
                from ..core import get_component_manager

                component_manager = get_component_manager()
            except:
                pass

        return component_manager

    def _execute_script_command(self, command: str):
        """执行脚本命令"""
        if command == "list":
            print(
                f"{Fore.CYAN}可用脚本:{Style.RESET_ALL} backup.py, maintenance.py, stats.py"
            )
        else:
            print(f"{Fore.CYAN}→ 脚本:{Style.RESET_ALL} #{command}")

    def _execute_admin_command(self, command: str):
        """执行管理命令 - 预留给以后扩展"""
        print(f"{Fore.MAGENTA}→ 管理:{Style.RESET_ALL} %{command}")
        print(f"{Fore.YELLOW}  管理指令功能预留，暂未实现{Style.RESET_ALL}")

    def _execute_chat_command(self, message: str):
        """执行聊天命令"""
        if self.server_manager:
            try:
                # 聊天命令通常是通过/say命令发送
                if hasattr(self.server_manager, "send_command"):
                    import inspect

                    # 检查是否为协程函数
                    if inspect.iscoroutinefunction(self.server_manager.send_command):
                        # 对于异步方法，使用队列获取反馈
                        print(f"{Fore.BLUE}💬 聊天:{Style.RESET_ALL} {message}")

                        # 使用队列方法获取反馈
                        self._execute_async_command(f"say {message}")
                    else:
                        # 同步版本
                        try:
                            success = self.server_manager.send_command(f"say {message}")
                            if success:
                                print(f"{Fore.BLUE}💬 聊天:{Style.RESET_ALL} {message}")
                            else:
                                print(f"{Fore.RED}✗ 聊天:{Style.RESET_ALL} 发送失败")
                        except Exception as e:
                            print(f"{Fore.RED}✗ 聊天错误:{Style.RESET_ALL} {e}")

                elif hasattr(self.server_manager, "send_chat"):
                    self.server_manager.send_chat(message)
                    print(f"{Fore.BLUE}💬 聊天:{Style.RESET_ALL} {message}")

                elif hasattr(self.server_manager, "execute_command"):
                    # 通过execute_command发送say命令
                    self.server_manager.execute_command(f"say {message}")
                    print(f"{Fore.BLUE}💬 聊天:{Style.RESET_ALL} {message}")

                else:
                    print(f"{Fore.YELLOW}💬 模拟聊天:{Style.RESET_ALL} {message}")

            except Exception as e:
                print(f"{Fore.RED}✗ 聊天错误:{Style.RESET_ALL} {e}")
        else:
            print(f"{Fore.BLUE}💬 模拟聊天:{Style.RESET_ALL} {message}")

    def _show_help(self):
        """显示帮助信息"""
        help_text = f"""
{Fore.CYAN}=== Aetherius 控制台帮助 ==={Style.RESET_ALL}

{Fore.YELLOW}统一前缀识别系统:{Style.RESET_ALL}
  {Fore.GREEN}/ {Style.RESET_ALL} MC指令          (例: /help, /stop, /list)
  {Fore.BLUE}! {Style.RESET_ALL} Aetherius系统指令 (例: !status, !quit, !help)
  {Fore.MAGENTA}@ {Style.RESET_ALL} 脚本指令        (例: @run, @list)
  {Fore.YELLOW}# {Style.RESET_ALL} 插件指令        (例: #list, #enable <插件名>, #help)
  {Fore.CYAN}$ {Style.RESET_ALL} 组件指令        (例: $list, $enable <组件名>, $help)
  {Fore.RED}% {Style.RESET_ALL} 管理指令        (预留扩展)
  {Fore.WHITE}  {Style.RESET_ALL} 聊天消息        (直接输入文本)

{Fore.YELLOW}常用命令:{Style.RESET_ALL}
  !help     显示此帮助
  !status   显示控制台状态
  !server   显示服务器状态
  !clear    清屏
  !quit     退出控制台

{Fore.YELLOW}管理命令:{Style.RESET_ALL}
  #help     显示插件管理帮助
  #list     列出所有插件
  $help     显示组件管理帮助
  $list     列出所有组件
  @help     显示脚本命令帮助
  @list     列出可用脚本

{Fore.YELLOW}退出方式:{Style.RESET_ALL}
  !quit 或 !exit    正常退出
  Ctrl+C           中断退出
"""
        print(help_text)

    def _show_status(self):
        """显示状态信息"""
        uptime = datetime.now() - self.start_time

        print(f"\n{Fore.CYAN}=== 系统状态 ==={Style.RESET_ALL}")
        print(f"运行时间: {str(uptime).split('.')[0]}")
        print(f"执行命令: {self.commands_executed}")
        print(f"服务器连接: {'是' if self.server_manager else '否'}")
        print()

    def _show_server_status(self):
        """显示详细的服务器状态"""
        print(f"\n{Fore.CYAN}=== 服务器状态 ==={Style.RESET_ALL}")

        if not self.server_manager:
            print(f"{Fore.RED}✗ 未连接到服务器{Style.RESET_ALL}")
            print("使用 'aetherius server start' 启动服务器")
            return

        # 检查服务器是否运行
        if hasattr(self.server_manager, "is_alive"):
            is_running = self.server_manager.is_alive
            status_icon = (
                f"{Fore.GREEN}✓{Style.RESET_ALL}"
                if is_running
                else f"{Fore.RED}✗{Style.RESET_ALL}"
            )
            status_text = "运行中" if is_running else "未运行"
            print(f"服务器状态: {status_icon} {status_text}")
        else:
            print(f"服务器状态: {Fore.YELLOW}未知{Style.RESET_ALL}")

        # 检查可用功能
        features = []
        if hasattr(self.server_manager, "send_command"):
            features.append("命令发送")
        if hasattr(self.server_manager, "command_queue"):
            features.append("命令队列")
        if hasattr(self.server_manager, "set_stdout_handler"):
            features.append("日志流")

        if features:
            print(f"可用功能: {', '.join(features)}")
        else:
            print(f"{Fore.YELLOW}⚠ 功能检测失败{Style.RESET_ALL}")

        # 显示连接类型
        if hasattr(self.server_manager, "__class__"):
            class_name = self.server_manager.__class__.__name__
            print(f"连接类型: {class_name}")

        print()

    def execute_command(self, command: str):
        """执行命令"""
        if not command.strip():
            return

        command = command.strip()
        self.commands_executed += 1

        # 解析命令类型
        cmd_type, content = self._parse_command(command)

        try:
            # 根据类型执行命令
            if cmd_type == CommandType.MINECRAFT:
                self._execute_minecraft_command(content)
            elif cmd_type == CommandType.AETHERIUS:
                self._execute_aetherius_command(content)
            elif cmd_type == CommandType.PLUGIN:
                self._execute_plugin_command(content)
            elif cmd_type == CommandType.COMPONENT:
                self._execute_component_command(content)
            elif cmd_type == CommandType.SCRIPT:
                self._execute_script_command(content)
            elif cmd_type == CommandType.ADMIN:
                self._execute_admin_command(content)
            else:
                self._execute_chat_command(command)

        except Exception as e:
            print(f"{Fore.RED}✗ 错误:{Style.RESET_ALL} {e}")

    def run(self):
        """运行控制台主循环"""
        self.is_running = True

        try:
            while self.is_running:
                try:
                    # 获取用户输入
                    command = input(f"{Fore.GREEN}Aetherius> {Style.RESET_ALL}")

                    # 执行命令
                    if command:
                        self.execute_command(command)

                except (KeyboardInterrupt, EOFError):
                    print(f"\n{Fore.YELLOW}再见!{Style.RESET_ALL}")
                    break
                except Exception as e:
                    print(f"{Fore.RED}输入错误: {e}{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}控制台错误: {e}{Style.RESET_ALL}")
        finally:
            self.is_running = False
            self.cleanup()

    def cleanup(self):
        """清理控制台资源"""
        try:
            # 清理增强控制台接口
            if HAS_ENHANCED_CONSOLE and self.enhanced_console:
                import asyncio
                import threading

                def cleanup_console():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(
                                close_managed_console_interface(self.server_manager)
                            )
                            print(f"{Fore.GREEN}✓ 已清理增强控制台接口{Style.RESET_ALL}")
                        finally:
                            loop.close()
                    except Exception as e:
                        print(f"{Fore.YELLOW}⚠ 清理增强控制台失败: {e}{Style.RESET_ALL}")

                thread = threading.Thread(target=cleanup_console, daemon=True)
                thread.start()
                thread.join(timeout=5.0)  # 最多等待5秒

            self.enhanced_console = None
            self._console_initialized = False

        except Exception as e:
            print(f"{Fore.YELLOW}⚠ 控制台清理失败: {e}{Style.RESET_ALL}")


class MockServerManager:
    """模拟服务器管理器"""

    def execute_command(self, command: str):
        return f"执行了Minecraft命令: {command}"

    def send_chat(self, message: str):
        return f"发送了聊天消息: {message}"


def main():
    """主函数"""
    print("启动简化Aetherius控制台...")

    # 创建模拟服务器管理器
    server = MockServerManager()

    # 创建控制台
    console = SimpleConsole(server)

    # 运行控制台
    console.run()

    print("控制台已关闭")


if __name__ == "__main__":
    main()

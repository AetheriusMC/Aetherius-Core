#!/usr/bin/env python3
"""
简化的Aetherius统一控制台 - 解决格式和反馈问题
"""

import os
import readline
import sys
from datetime import datetime
from enum import Enum

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
    """命令类型"""

    MINECRAFT = "/"  # Minecraft服务器命令
    AETHERIUS = "!"  # Aetherius系统命令
    PLUGIN = "@"  # 插件管理命令
    SCRIPT = "#"  # 脚本执行命令
    ADMIN = "&"  # 管理员命令
    CHAT = ""  # 聊天消息


class SimpleConsole:
    """简化的统一控制台"""

    def __init__(self, server_manager=None):
        self.server_manager = server_manager
        self.is_running = False
        self.start_time = datetime.now()
        self.commands_executed = 0

        # 设置readline
        try:
            readline.parse_and_bind("tab: complete")
        except Exception:
            pass

        self._print_startup()

    def _print_startup(self):
        """打印启动信息"""
        print(f"{Fore.GREEN}✓ Aetherius Console Ready{Style.RESET_ALL}")
        print(f"{Fore.CYAN}命令前缀: / ! @ # & | 输入 !help 查看帮助{Style.RESET_ALL}")
        print()

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
                result = self.server_manager.execute_command(command)
                print(f"{Fore.GREEN}→ Minecraft:{Style.RESET_ALL} /{command}")
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

        else:
            print(f"{Fore.CYAN}→ Aetherius:{Style.RESET_ALL} !{command}")

    def _execute_plugin_command(self, command: str):
        """执行插件命令"""
        print(f"{Fore.MAGENTA}→ 插件:{Style.RESET_ALL} @{command}")

    def _execute_script_command(self, command: str):
        """执行脚本命令"""
        if command == "list":
            print(
                f"{Fore.CYAN}可用脚本:{Style.RESET_ALL} backup.py, maintenance.py, stats.py"
            )
        else:
            print(f"{Fore.CYAN}→ 脚本:{Style.RESET_ALL} #{command}")

    def _execute_admin_command(self, command: str):
        """执行管理命令"""
        print(f"{Fore.RED}→ 管理:{Style.RESET_ALL} &{command}")

    def _execute_chat_command(self, message: str):
        """执行聊天命令"""
        if self.server_manager:
            try:
                self.server_manager.send_chat(message)
                print(f"{Fore.BLUE}💬 聊天:{Style.RESET_ALL} {message}")
            except Exception as e:
                print(f"{Fore.RED}✗ 聊天错误:{Style.RESET_ALL} {e}")
        else:
            print(f"{Fore.BLUE}💬 模拟聊天:{Style.RESET_ALL} {message}")

    def _show_help(self):
        """显示帮助信息"""
        help_text = f"""
{Fore.CYAN}=== Aetherius 控制台帮助 ==={Style.RESET_ALL}

{Fore.YELLOW}命令前缀:{Style.RESET_ALL}
  {Fore.GREEN}/ {Style.RESET_ALL} Minecraft命令    (例: /help, /stop, /list)
  {Fore.BLUE}! {Style.RESET_ALL} Aetherius命令    (例: !status, !quit, !help)
  {Fore.MAGENTA}@ {Style.RESET_ALL} 插件命令        (例: @list, @enable)
  {Fore.CYAN}# {Style.RESET_ALL} 脚本命令        (例: #run, #list)
  {Fore.RED}& {Style.RESET_ALL} 管理命令        (例: &promote, &ban)
  {Fore.WHITE}  {Style.RESET_ALL} 聊天消息        (直接输入文本)

{Fore.YELLOW}常用命令:{Style.RESET_ALL}
  !help     显示此帮助
  !status   显示状态信息
  !clear    清屏
  !quit     退出控制台

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

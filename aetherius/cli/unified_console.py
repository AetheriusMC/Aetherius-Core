#!/usr/bin/env python3
"""
简化的Aetherius统一控制台 - 解决格式和反馈问题
"""

import os
import sys
import readline
from datetime import datetime
from enum import Enum, auto

# 简单的颜色支持检测
HAS_COLOR = (
    hasattr(sys.stdout, 'isatty') and 
    sys.stdout.isatty() and 
    os.getenv('TERM', '').lower() not in ('dumb', '')
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
    MINECRAFT = "/"      # Minecraft服务器命令
    AETHERIUS = "!"      # Aetherius系统命令  
    PLUGIN = "@"         # 插件管理命令
    SCRIPT = "#"         # 脚本执行命令
    ADMIN = "&"          # 管理员命令
    CHAT = ""           # 聊天消息


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
        except:
            pass
        
        # 设置服务器日志监听
        self._setup_server_monitoring()
            
        self._print_startup()
    
    def _setup_server_monitoring(self):
        """设置服务器监听和事件订阅"""
        if self.server_manager:
            try:
                # 设置日志处理器
                if hasattr(self.server_manager, 'set_stdout_handler'):
                    self.server_manager.set_stdout_handler(self._handle_server_log)
                
                # 设置事件监听
                self._setup_event_listeners()
                
                print(f"{Fore.GREEN}✓ 已连接服务器日志流{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠ 服务器监听设置失败: {e}{Style.RESET_ALL}")
    
    def _handle_server_log(self, line: str):
        """处理服务器日志行"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.GREEN}[{timestamp}] SERVER:{Style.RESET_ALL} {line}")
    
    def _setup_event_listeners(self):
        """设置事件监听器"""
        try:
            from ..core.event_manager import get_event_manager, on_event
            from ..core.events import PlayerJoinEvent, PlayerLeaveEvent, PlayerChatEvent
            
            event_manager = get_event_manager()
            
            # 注册事件监听器
            def on_player_join(event):
                print(f"{Fore.CYAN}[PLAYER]{Style.RESET_ALL} {event.player_name} 加入了游戏")
            
            def on_player_leave(event):  
                print(f"{Fore.CYAN}[PLAYER]{Style.RESET_ALL} {event.player_name} 离开了游戏")
            
            def on_player_chat(event):
                print(f"{Fore.BLUE}[CHAT]{Style.RESET_ALL} <{event.player_name}> {event.message}")
            
            # 注册监听器
            event_manager.register_listener(PlayerJoinEvent, on_player_join)
            event_manager.register_listener(PlayerLeaveEvent, on_player_leave) 
            event_manager.register_listener(PlayerChatEvent, on_player_chat)
            
            print(f"{Fore.GREEN}✓ 已注册事件监听器{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ 事件监听器设置失败: {e}{Style.RESET_ALL}")
    
    def _execute_async_command(self, command: str):
        """执行异步命令并获取反馈"""
        try:
            # 检查服务器是否正在运行
            if hasattr(self.server_manager, 'is_alive') and not self.server_manager.is_alive:
                print(f"{Fore.RED}  ✗ 服务器未运行{Style.RESET_ALL}")
                return
            
            # 如果服务器有命令队列系统，尝试使用
            if hasattr(self.server_manager, 'command_queue'):
                import threading
                import asyncio
                
                def execute_command():
                    try:
                        # 在新线程中运行异步命令
                        async def run_command():
                            try:
                                command_queue = self.server_manager.command_queue
                                command_id = command_queue.add_command(command)
                                
                                # 缩短超时时间，更快反馈
                                result = await command_queue.wait_for_completion(command_id, timeout=5.0)
                                
                                # 显示结果
                                if result['status'] == 'completed':
                                    if result.get('success', False):
                                        print(f"{Fore.GREEN}  ✓ 命令执行成功{Style.RESET_ALL}")
                                        if 'output' in result and result['output']:
                                            print(f"{Fore.BLUE}  输出: {result['output']}{Style.RESET_ALL}")
                                    else:
                                        print(f"{Fore.RED}  ✗ 命令执行失败{Style.RESET_ALL}")
                                else:
                                    print(f"{Fore.YELLOW}  ⚠ 命令超时 (可能服务器未响应){Style.RESET_ALL}")
                                    
                            except Exception as e:
                                print(f"{Fore.RED}  ✗ 命令执行错误: {e}{Style.RESET_ALL}")
                        
                        # 运行异步命令
                        try:
                            asyncio.run(run_command())
                        except RuntimeError:
                            # 如果已在事件循环中，尝试直接发送
                            try:
                                asyncio.create_task(self.server_manager.send_command(command))
                                print(f"{Fore.BLUE}  └─ 已发送到服务器{Style.RESET_ALL}")
                            except Exception as e:
                                print(f"{Fore.YELLOW}  └─ 异步发送: {command}{Style.RESET_ALL}")
                            
                    except Exception as e:
                        print(f"{Fore.RED}  ✗ 队列执行错误: {e}{Style.RESET_ALL}")
                
                # 在后台线程执行
                thread = threading.Thread(target=execute_command, daemon=True)
                thread.start()
                
            # 如果没有队列，尝试直接发送
            elif hasattr(self.server_manager, 'send_command'):
                import threading
                import asyncio
                
                def direct_send():
                    try:
                        async def send_now():
                            success = await self.server_manager.send_command(command)
                            if success:
                                print(f"{Fore.GREEN}  ✓ 命令已发送{Style.RESET_ALL}")
                            else:
                                print(f"{Fore.RED}  ✗ 命令发送失败{Style.RESET_ALL}")
                        
                        asyncio.run(send_now())
                    except Exception as e:
                        print(f"{Fore.YELLOW}  └─ 直接发送: {command}{Style.RESET_ALL}")
                
                thread = threading.Thread(target=direct_send, daemon=True)
                thread.start()
                
            else:
                print(f"{Fore.BLUE}  └─ 命令已记录 (模拟模式){Style.RESET_ALL}")
                
        except Exception as e:
            print(f"{Fore.RED}  ✗ 异步执行错误: {e}{Style.RESET_ALL}")
    
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
                # 检查服务器管理器的正确方法
                if hasattr(self.server_manager, 'send_command'):
                    # ServerProcessWrapper使用异步send_command方法
                    import asyncio
                    import inspect
                    
                    # 检查方法是否为协程函数
                    if inspect.iscoroutinefunction(self.server_manager.send_command):
                        # 对于异步方法，先检查服务器状态
                        if hasattr(self.server_manager, 'is_alive') and not self.server_manager.is_alive:
                            print(f"{Fore.RED}→ Minecraft (未运行):{Style.RESET_ALL} /{command}")
                            print(f"{Fore.RED}  ✗ 服务器未启动{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.YELLOW}→ Minecraft:{Style.RESET_ALL} /{command}")
                            
                            # 使用队列方法获取命令反馈
                            self._execute_async_command(command)
                    else:
                        # 同步版本的send_command
                        try:
                            success = self.server_manager.send_command(command)
                            if success:
                                print(f"{Fore.GREEN}→ Minecraft:{Style.RESET_ALL} /{command}")
                            else:
                                print(f"{Fore.RED}✗ Minecraft:{Style.RESET_ALL} 命令发送失败")
                        except Exception as e:
                            print(f"{Fore.RED}✗ Minecraft错误:{Style.RESET_ALL} {e}")
                        
                elif hasattr(self.server_manager, 'execute_command'):
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
            os.system('clear' if os.name == 'posix' else 'cls')
            self._print_startup()
            
        elif command == "server":
            self._show_server_status()
            
        else:
            print(f"{Fore.CYAN}→ Aetherius:{Style.RESET_ALL} !{command}")
    
    def _execute_plugin_command(self, command: str):
        """执行插件命令"""
        print(f"{Fore.MAGENTA}→ 插件:{Style.RESET_ALL} @{command}")
    
    def _execute_script_command(self, command: str):
        """执行脚本命令"""
        if command == "list":
            print(f"{Fore.CYAN}可用脚本:{Style.RESET_ALL} backup.py, maintenance.py, stats.py")
        else:
            print(f"{Fore.CYAN}→ 脚本:{Style.RESET_ALL} #{command}")
    
    def _execute_admin_command(self, command: str):
        """执行管理命令"""
        print(f"{Fore.RED}→ 管理:{Style.RESET_ALL} &{command}")
    
    def _execute_chat_command(self, message: str):
        """执行聊天命令"""
        if self.server_manager:
            try:
                # 聊天命令通常是通过/say命令发送
                if hasattr(self.server_manager, 'send_command'):
                    import asyncio
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
                        
                elif hasattr(self.server_manager, 'send_chat'):
                    self.server_manager.send_chat(message)
                    print(f"{Fore.BLUE}💬 聊天:{Style.RESET_ALL} {message}")
                    
                elif hasattr(self.server_manager, 'execute_command'):
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

{Fore.YELLOW}命令前缀:{Style.RESET_ALL}
  {Fore.GREEN}/ {Style.RESET_ALL} Minecraft命令    (例: /help, /stop, /list)
  {Fore.BLUE}! {Style.RESET_ALL} Aetherius命令    (例: !status, !quit, !help) 
  {Fore.MAGENTA}@ {Style.RESET_ALL} 插件命令        (例: @list, @enable)
  {Fore.CYAN}# {Style.RESET_ALL} 脚本命令        (例: #run, #list)
  {Fore.RED}& {Style.RESET_ALL} 管理命令        (例: &promote, &ban)
  {Fore.WHITE}  {Style.RESET_ALL} 聊天消息        (直接输入文本)

{Fore.YELLOW}常用命令:{Style.RESET_ALL}
  !help     显示此帮助
  !status   显示控制台状态
  !server   显示服务器状态
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
    
    def _show_server_status(self):
        """显示详细的服务器状态"""
        print(f"\n{Fore.CYAN}=== 服务器状态 ==={Style.RESET_ALL}")
        
        if not self.server_manager:
            print(f"{Fore.RED}✗ 未连接到服务器{Style.RESET_ALL}")
            print("使用 'aetherius server start' 启动服务器")
            return
        
        # 检查服务器是否运行
        if hasattr(self.server_manager, 'is_alive'):
            is_running = self.server_manager.is_alive
            status_icon = f"{Fore.GREEN}✓{Style.RESET_ALL}" if is_running else f"{Fore.RED}✗{Style.RESET_ALL}"
            status_text = "运行中" if is_running else "未运行"
            print(f"服务器状态: {status_icon} {status_text}")
        else:
            print(f"服务器状态: {Fore.YELLOW}未知{Style.RESET_ALL}")
        
        # 检查可用功能
        features = []
        if hasattr(self.server_manager, 'send_command'):
            features.append("命令发送")
        if hasattr(self.server_manager, 'command_queue'):
            features.append("命令队列")
        if hasattr(self.server_manager, 'set_stdout_handler'):
            features.append("日志流")
        
        if features:
            print(f"可用功能: {', '.join(features)}")
        else:
            print(f"{Fore.YELLOW}⚠ 功能检测失败{Style.RESET_ALL}")
        
        # 显示连接类型
        if hasattr(self.server_manager, '__class__'):
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
#!/usr/bin/env python3
"""
测试增强的控制台 - 包含日志流和命令反馈
"""

import sys
import os
import asyncio
import time
import threading
sys.path.insert(0, os.path.abspath('.'))

from aetherius.cli.unified_console import SimpleConsole

class MockCommandQueue:
    """模拟命令队列"""
    
    def __init__(self):
        self.commands = {}
        self.next_id = 1
    
    def add_command(self, command: str) -> int:
        command_id = self.next_id
        self.next_id += 1
        self.commands[command_id] = {
            'command': command,
            'status': 'pending'
        }
        print(f"[QUEUE] 已添加命令: {command} (ID: {command_id})")
        return command_id
    
    async def wait_for_completion(self, command_id: int, timeout: float = 30.0):
        """模拟等待命令完成"""
        print(f"[QUEUE] 等待命令完成 (ID: {command_id})")
        
        # 模拟执行时间
        await asyncio.sleep(0.5)
        
        command = self.commands[command_id]['command']
        
        # 模拟不同命令的输出
        if command == "list":
            output = "There are 2 of a max of 20 players online: Player1, Player2"
        elif command.startswith("say "):
            message = command[4:]
            output = f"[Server] {message}"
        elif command == "time query daytime":
            output = "The time is 1000"
        else:
            output = f"Command '{command}' executed successfully"
        
        result = {
            'status': 'completed',
            'success': True,
            'output': output,
            'command_id': command_id
        }
        
        print(f"[QUEUE] 命令完成: {command} -> {output}")
        return result

class MockEnhancedServerWrapper:
    """增强的模拟服务器包装器 - 支持日志流和事件"""
    
    def __init__(self):
        self.is_alive = True
        self.stdout_handler = None
        self.command_queue = MockCommandQueue()
        self._log_thread = None
        self._stop_logging = False
        
    def set_stdout_handler(self, handler):
        """设置日志处理器"""
        self.stdout_handler = handler
        print("[SERVER] 日志处理器已设置")
        
        # 启动模拟日志流
        self._start_log_stream()
        
    def _start_log_stream(self):
        """启动模拟日志流"""
        def log_generator():
            logs = [
                "[00:00:01] [Server thread/INFO]: Starting minecraft server version 1.20.1",
                "[00:00:02] [Server thread/INFO]: Loading properties",
                "[00:00:03] [Server thread/INFO]: Done (2.5s)! For help, type \"help\"",
                "[00:00:10] [Server thread/INFO]: Player1 joined the game",
                "[00:00:15] [Server thread/INFO]: <Player1> Hello everyone!",
                "[00:00:30] [Server thread/INFO]: Player2 joined the game",
                "[00:00:35] [Server thread/INFO]: <Player2> Hi there!",
            ]
            
            for i, log in enumerate(logs):
                if self._stop_logging:
                    break
                time.sleep(2)  # 每2秒一条日志
                if self.stdout_handler:
                    self.stdout_handler(log)
        
        self._log_thread = threading.Thread(target=log_generator, daemon=True)
        self._log_thread.start()
    
    async def send_command(self, command: str) -> bool:
        """异步发送命令"""
        print(f"[SERVER] 接收异步命令: {command}")
        return True
    
    def stop_logging(self):
        """停止日志流"""
        self._stop_logging = True

def test_enhanced_console():
    print("=== 测试增强控制台 - 日志流和命令反馈 ===")
    
    # 创建增强的服务器包装器
    server = MockEnhancedServerWrapper()
    
    # 创建控制台
    console = SimpleConsole(server)
    
    print("\n等待日志流启动...")
    time.sleep(1)
    
    print("\n测试命令执行和反馈:")
    commands = [
        "/list",
        "/say 测试服务器广播",
        "/time query daytime",
        "大家好，这是聊天测试！"
    ]
    
    for cmd in commands:
        print(f"\n> 执行命令: {cmd}")
        console.execute_command(cmd)
        time.sleep(2)  # 等待命令处理
        print("-" * 40)
    
    # 等待一些日志显示
    print("\n等待更多日志...")
    time.sleep(5)
    
    # 停止日志流
    server.stop_logging()
    
    print(f"\n✅ 测试完成!")
    print(f"执行了 {console.commands_executed} 个命令")

if __name__ == "__main__":
    test_enhanced_console()
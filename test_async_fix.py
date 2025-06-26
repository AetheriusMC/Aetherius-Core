#!/usr/bin/env python3
"""
测试修复后的异步处理
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath('.'))

from aetherius.cli.unified_console import SimpleConsole

class TestAsyncServerWrapper:
    """测试异步服务器包装器"""
    
    def __init__(self):
        self.is_alive = True
        
    async def send_command(self, command: str) -> bool:
        """异步发送命令"""
        print(f"[ASYNC SERVER] 处理命令: {command}")
        
        # 模拟异步操作
        await asyncio.sleep(0.1)
        
        if command.startswith("say "):
            message = command[4:]
            print(f"[ASYNC SERVER] 服务器广播: {message}")
        elif command == "list":
            print(f"[ASYNC SERVER] 在线玩家: 0/20")
        else:
            print(f"[ASYNC SERVER] 执行: {command}")
            
        return True

class TestSyncServerWrapper:
    """测试同步服务器包装器"""
    
    def execute_command(self, command: str) -> str:
        """同步执行命令"""
        print(f"[SYNC SERVER] 处理命令: {command}")
        return f"执行结果: {command}"

def test_async_fix():
    print("=== 测试异步处理修复 ===")
    
    print("\n1. 测试异步服务器接口:")
    async_server = TestAsyncServerWrapper()
    async_console = SimpleConsole(async_server)
    
    test_commands = ["/say 测试异步", "/list", "Hello async world!"]
    
    for cmd in test_commands:
        print(f"\n执行: {cmd}")
        async_console.execute_command(cmd)
        print("-" * 30)
    
    print("\n2. 测试同步服务器接口:")
    sync_server = TestSyncServerWrapper()
    sync_console = SimpleConsole(sync_server)
    
    for cmd in test_commands:
        print(f"\n执行: {cmd}")
        sync_console.execute_command(cmd)
        print("-" * 30)
    
    print("\n✅ 异步处理修复测试完成!")

if __name__ == "__main__":
    test_async_fix()
#!/usr/bin/env python3
"""
测试超时问题修复
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from aetherius.cli.unified_console import SimpleConsole

class MockServerNotRunning:
    """模拟未运行的服务器"""
    
    def __init__(self):
        self.is_alive = False  # 服务器未运行
        
    async def send_command(self, command: str) -> bool:
        """异步发送命令 - 但服务器未运行"""
        return False

class MockServerNoQueue:
    """模拟没有队列的服务器"""
    
    def __init__(self):
        self.is_alive = True
        
    async def send_command(self, command: str) -> bool:
        """异步发送命令 - 没有队列系统"""
        print(f"[MOCK] 直接发送命令: {command}")
        return True

def test_timeout_scenarios():
    print("=== 测试命令超时问题修复 ===")
    
    print("\n1. 测试服务器未运行的情况:")
    server1 = MockServerNotRunning()
    console1 = SimpleConsole(server1)
    
    console1.execute_command("!server")  # 检查服务器状态
    console1.execute_command("/say 测试")  # 应该显示服务器未运行
    
    print("\n" + "="*50)
    
    print("\n2. 测试没有队列的服务器:")
    server2 = MockServerNoQueue()
    console2 = SimpleConsole(server2)
    
    console2.execute_command("!server")  # 检查服务器状态
    console2.execute_command("/say 测试")  # 应该直接发送
    
    print("\n✅ 超时问题测试完成!")

if __name__ == "__main__":
    test_timeout_scenarios()
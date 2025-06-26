#!/usr/bin/env python3
"""
测试与运行中服务器的连接
"""

import sys
import os
import time
sys.path.insert(0, os.path.abspath('.'))

from aetherius.cli.console_manager import create_console

def test_live_server():
    print("=== 测试控制台与运行中服务器的连接 ===")
    
    try:
        # 创建控制台连接到运行中的服务器
        console = create_console()
        
        print("\n测试命令:")
        
        # 测试服务器状态
        print("\n1. 检查服务器状态:")
        console.execute_command("!server")
        
        time.sleep(1)
        
        # 测试Minecraft命令
        print("\n2. 测试Minecraft命令:")
        console.execute_command("/list")
        
        time.sleep(2)  # 等待命令执行
        
        console.execute_command("/say 控制台测试消息")
        
        time.sleep(2)  # 等待命令执行
        
        # 测试聊天
        print("\n3. 测试聊天:")
        console.execute_command("大家好，这是来自控制台的消息！")
        
        time.sleep(2)
        
        print("\n✅ 测试完成!")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_live_server()
#!/usr/bin/env python3
"""
直接测试命令执行，避免输入解析问题
"""

import sys
import os
import time
sys.path.insert(0, os.path.abspath('.'))

from aetherius.cli.console_manager import create_console

def test_direct_commands():
    print("=== 直接测试控制台命令执行 ===")
    
    try:
        # 创建控制台连接到运行中的服务器
        console = create_console()
        
        print("\n✅ 控制台已连接到服务器")
        
        # 直接测试各种命令
        commands = [
            ("!server", "检查服务器状态"),
            ("/list", "列出在线玩家"), 
            ("/time query daytime", "查询游戏时间"),
            ("/say 来自控制台的测试消息", "服务器广播"),
            ("Hello from console!", "聊天消息")
        ]
        
        for cmd, desc in commands:
            print(f"\n{'='*50}")
            print(f"测试: {desc}")
            print(f"命令: {cmd}")
            print("-" * 30)
            
            console.execute_command(cmd)
            
            time.sleep(1)  # 等待命令执行
        
        print(f"\n{'='*50}")
        print("✅ 所有命令测试完成!")
        print(f"总共执行了 {console.commands_executed} 个命令")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_commands()
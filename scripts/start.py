#!/usr/bin/env python3
"""
Aetherius Core - 开发启动脚本

快速启动脚本，用于开发和测试
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aetherius.core.application import AetheriusCore

async def main():
    """主函数"""
    print("🚀 启动 Aetherius Core (开发模式)...")
    
    # 设置调试日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 创建应用实例
        app = AetheriusCore()
        
        # 查找配置文件
        config_path = project_root / "config" / "config.yaml"
        if not config_path.exists():
            print(f"⚠️  配置文件不存在: {config_path}")
            print("将使用默认配置...")
            config_path = None
        else:
            print(f"📋 使用配置文件: {config_path}")
        
        # 启动应用
        await app.run(config_path)
        
    except KeyboardInterrupt:
        print("\n👋 已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
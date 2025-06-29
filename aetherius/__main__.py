#!/usr/bin/env python3
"""
Aetherius Core - 主入口点

当用户运行 `aetherius` 命令时的主入口
"""

import sys
import asyncio
import argparse
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 延迟导入避免循环导入
def get_cli_main():
    from aetherius.cli.main import main as cli_main
    return cli_main

def get_aetherius_core():
    from aetherius.core.application import AetheriusCore
    return AetheriusCore


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='aetherius',
        description='Aetherius Core - Minecraft Server Management Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  aetherius start                    # 启动 Aetherius Core
  aetherius stop                     # 停止服务器
  aetherius restart                  # 重启服务器
  aetherius status                   # 查看服务器状态
  aetherius console                  # 启动交互式控制台
  aetherius cmd "say Hello World"    # 执行服务器命令
  aetherius web                      # 启动 Web 控制台
  aetherius config show             # 显示配置
  aetherius plugin list             # 插件管理
        """
    )
    
    # 全局选项
    parser.add_argument(
        '-c', '--config',
        type=Path,
        default='config/config.yaml',
        help='配置文件路径 (默认: config/config.yaml)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='详细输出'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='调试模式'
    )
    
    # 子命令
    subparsers = parser.add_subparsers(
        dest='command',
        help='可用命令',
        metavar='COMMAND'
    )
    
    # 核心系统命令
    start_parser = subparsers.add_parser('start', help='启动 Aetherius Core')
    start_parser.add_argument('--background', '-b', action='store_true', help='后台运行')
    
    # 服务器管理命令
    subparsers.add_parser('stop', help='停止服务器')
    subparsers.add_parser('restart', help='重启服务器')
    subparsers.add_parser('status', help='查看服务器状态')
    
    # 控制台命令
    console_parser = subparsers.add_parser('console', help='启动交互式控制台')
    console_parser.add_argument('--web', action='store_true', help='启动 Web 控制台')
    
    # 命令执行
    cmd_parser = subparsers.add_parser('cmd', help='执行服务器命令')
    cmd_parser.add_argument('command', help='要执行的命令')
    cmd_parser.add_argument('--wait', '-w', action='store_true', help='等待命令完成')
    
    # Web 控制台
    web_parser = subparsers.add_parser('web', help='启动 Web 控制台')
    web_parser.add_argument('--port', '-p', type=int, default=8080, help='端口号 (默认: 8080)')
    web_parser.add_argument('--host', default='localhost', help='绑定地址 (默认: localhost)')
    
    # 配置管理
    config_parser = subparsers.add_parser('config', help='配置管理')
    config_subparsers = config_parser.add_subparsers(dest='config_action')
    config_subparsers.add_parser('show', help='显示当前配置')
    config_subparsers.add_parser('validate', help='验证配置')
    config_subparsers.add_parser('init', help='初始化默认配置')
    
    # 插件管理
    plugin_parser = subparsers.add_parser('plugin', help='插件管理')
    plugin_subparsers = plugin_parser.add_subparsers(dest='plugin_action')
    plugin_subparsers.add_parser('list', help='列出所有插件')
    
    enable_parser = plugin_subparsers.add_parser('enable', help='启用插件')
    enable_parser.add_argument('name', help='插件名称')
    
    disable_parser = plugin_subparsers.add_parser('disable', help='禁用插件')
    disable_parser.add_argument('name', help='插件名称')
    
    # 组件管理
    component_parser = subparsers.add_parser('component', help='组件管理')
    component_subparsers = component_parser.add_subparsers(dest='component_action')
    component_subparsers.add_parser('list', help='列出所有组件')
    
    comp_start_parser = component_subparsers.add_parser('start', help='启动组件')
    comp_start_parser.add_argument('name', help='组件名称')
    
    comp_stop_parser = component_subparsers.add_parser('stop', help='停止组件')
    comp_stop_parser.add_argument('name', help='组件名称')
    
    # 系统管理
    system_parser = subparsers.add_parser('system', help='系统管理')
    system_subparsers = system_parser.add_subparsers(dest='system_action')
    system_subparsers.add_parser('info', help='显示系统信息')
    system_subparsers.add_parser('health', help='系统健康检查')
    system_subparsers.add_parser('logs', help='查看系统日志')
    
    return parser


async def handle_core_commands(args):
    """处理核心系统命令"""
    try:
        if args.command == 'start':
            print("🚀 启动 Aetherius Core...")
            AetheriusCore = get_aetherius_core()
            app = AetheriusCore()
            await app.run(args.config if args.config.exists() else None)
            
        elif args.command == 'web':
            print(f"🌐 启动 Web 控制台在 http://{args.host}:{args.port}")
            # 这里会调用 Web 组件
            try:
                import sys
                sys.path.append('components/ComponentWeb')
                from start_component import main as web_main
                await web_main(host=args.host, port=args.port)
            except ImportError:
                print("❌ Web 组件未找到，请确保组件已正确安装")
                
        elif args.command == 'config':
            if args.config_action == 'show':
                from aetherius.core.config import ConfigManager, FileConfigSource
                config = ConfigManager()
                if args.config.exists():
                    config.add_source(FileConfigSource(args.config))
                    print("📋 当前配置:")
                    # 显示配置内容的逻辑
                else:
                    print(f"⚠️  配置文件不存在: {args.config}")
                    
            elif args.config_action == 'init':
                print("🔧 初始化默认配置...")
                # 创建默认配置文件的逻辑
                
        elif args.command == 'system':
            if args.system_action == 'info':
                import sys
                print("ℹ️  Aetherius Core 系统信息")
                print(f"版本: 2.0.0")
                print(f"配置文件: {args.config}")
                print(f"工作目录: {Path.cwd()}")
                print(f"Python 版本: {sys.version}")
                
            elif args.system_action == 'health':
                print("🔍 系统健康检查")
                # 执行健康检查的逻辑
                
    except Exception as e:
        print(f"❌ 错误: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main():
    """主入口函数"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    elif args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 如果没有提供命令，显示帮助
    if not args.command:
        parser.print_help()
        return
    
    # 传统 CLI 命令 (console, cmd, stop, restart, status 等)
    # 这些命令使用现有的 CLI 系统
    if args.command in ['console', 'cmd', 'stop', 'restart', 'status']:
        try:
            cli_main = get_cli_main()
            cli_main()
        except KeyboardInterrupt:
            print("\n👋 已取消")
        return
    
    # 核心系统命令和新功能
    try:
        asyncio.run(handle_core_commands(args))
    except KeyboardInterrupt:
        print("\n👋 已取消")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
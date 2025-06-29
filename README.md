# Aetherius Core - Minecraft Server Management Engine

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

一个轻量级、高性能的 Minecraft 服务器管理引擎，专为稳定性、性能和可扩展性而设计。

## ✨ 特性

### 🚀 核心功能
- **轻量级高性能**: 异步 I/O 架构，最小资源占用
- **企业级稳定性**: 为 24/7 运行设计，具备强大的错误处理
- **高度可扩展**: 插件和组件系统支持自定义功能
- **命令行优先**: 强大的 CLI 界面，支持脚本化管理

### 🏗️ 核心架构
- **依赖注入容器**: 支持单例、瞬态、作用域生命周期管理
- **分层配置管理**: 多源配置、验证、热重载和模板渲染
- **增强事件系统**: 异步事件处理、优先级队列和批量操作
- **安全框架**: 认证、授权、审计和权限管理
- **监控诊断**: 实时性能指标、健康检查和系统监控
- **扩展系统**: 插件和组件热加载，支持生命周期管理

### 🔧 管理功能
- **智能服务器管理**: 自动重启、崩溃恢复、性能监控
- **实时控制台**: 双模式命令执行（直接/RCON），智能切换
- **玩家数据管理**: 结构化数据存储，支持详细游戏信息
- **Web 控制台**: 现代化 Web 界面，实时监控和管理

## 📦 安装

### 系统要求

- Python 3.11 或更高版本
- Java 17 或更高版本 (运行 Minecraft 服务器)
- Minecraft 服务器 JAR 文件

### 从源码安装

```bash
git clone https://github.com/AetheriusMC/Aetherius-Core.git
cd Aetherius-Core
pip install -e .
```

## 🚀 快速开始

### 1. 设置服务器

```bash
mkdir server
# 将您的服务器 JAR 文件放到 server/ 目录
cp /path/to/your/server.jar server/server.jar
```

### 2. 启动系统

```bash
# 开发模式启动
python scripts/start.py

# 或使用全局命令
aetherius start
```

### 3. 管理服务器

```bash
# 查看系统状态
aetherius status

# 启动 Web 控制台
aetherius web

# 执行服务器命令
aetherius cmd "say Hello World"

# 交互式控制台
aetherius console
```

## 📖 命令参考

### 核心系统命令

```bash
aetherius start              # 启动 Aetherius Core
aetherius web                # 启动 Web 控制台
aetherius system info        # 显示系统信息
aetherius system health      # 健康检查
```

### 服务器管理

```bash
aetherius stop               # 停止服务器
aetherius restart            # 重启服务器
aetherius status             # 服务器状态
```

### 配置管理

```bash
aetherius config show        # 显示当前配置
aetherius config validate    # 验证配置
aetherius config init        # 初始化默认配置
```

### 插件和组件

```bash
aetherius plugin list        # 列出插件
aetherius plugin enable <name>    # 启用插件
aetherius component list     # 列出组件
aetherius component start <name>  # 启动组件
```

## ⚙️ 配置

配置通过 `config/config.yaml` 文件管理：

```yaml
# 服务器配置
server:
  jar_path: server/server.jar
  java_executable: java
  java_args:
    - -Xmx4G
    - -Xms2G
    - -XX:+UseG1GC
  working_directory: server
  auto_restart: true
  restart_delay: 5.0

# 日志配置
logging:
  level: INFO
  file_path: logs/aetherius.log
  console_output: true

# 安全配置
security:
  enable_authentication: true
  session_timeout: 3600
  max_login_attempts: 5

# 监控配置
monitoring:
  enable_metrics: true
  health_check_interval: 30
  performance_tracking: true

# Web 控制台
web:
  enabled: true
  host: localhost
  port: 8080
  enable_ssl: false
```

## 🏗️ 架构概览

### 核心系统

- **AetheriusCore**: 主应用程序类，整合所有核心系统
- **DependencyContainer**: 依赖注入容器，管理组件生命周期
- **ConfigManager**: 分层配置管理，支持多源和热重载
- **SecurityManager**: 安全框架，处理认证和授权
- **ExtensionManager**: 扩展管理器，支持插件和组件

### 事件系统

- **EnhancedEventBus**: 高性能异步事件总线
- **EventStore**: 事件存储和回放功能
- **EventMetadata**: 事件元数据和优先级管理

### 监控系统

- **MonitoringContext**: 监控上下文管理
- **MetricsCollector**: 性能指标收集
- **HealthChecker**: 系统健康检查

## 📁 目录结构

```
Aetherius-Core/
├── bin/                    # 可执行脚本
│   └── aetherius          # 主启动脚本
├── scripts/               # 开发和部署脚本
│   └── start.py          # 开发启动脚本
├── docs/                  # 文档
│   ├── api/              # API 文档
│   ├── guides/           # 用户指南
│   └── examples/         # 示例代码
├── aetherius/            # 核心代码
│   ├── core/             # 核心系统
│   ├── cli/              # 命令行界面
│   ├── api/              # API 接口
│   └── plugins/          # 插件系统
├── components/           # 官方组件
│   └── ComponentWeb/     # Web 控制台组件
├── config/               # 配置文件
├── data/                 # 数据目录
├── server/               # Minecraft 服务器
└── tests/                # 测试代码
```

## 🔧 开发

### 开发环境设置

```bash
git clone https://github.com/AetheriusMC/Aetherius-Core.git
cd Aetherius-Core
pip install -e ".[dev]"
```

### 代码质量

```bash
ruff check .          # 代码检查
black .               # 代码格式化
pytest                # 运行测试
```

### 开发启动

```bash
# 使用开发启动脚本
python scripts/start.py

# 或直接运行应用
python -m aetherius.core.application
```

## 🗺️ 开发路线图

### ✅ 已完成 - Core Engine v2.0
- 核心架构重构和优化
- 依赖注入和配置管理系统
- 增强事件系统和安全框架
- 监控诊断和扩展系统
- Web 控制台组件

### 🚧 进行中 - 稳定性和优化
- 性能优化和内存管理
- 错误处理和日志系统
- 单元测试和集成测试
- 文档完善和用户指南

### 🔮 计划中 - 高级功能
- 多服务器管理
- 云集成和自动扩展
- 高级监控和告警
- 社区插件市场

## 📚 文档

- [API 文档](docs/api/) - 详细的 API 参考
- [用户指南](docs/guides/) - 使用教程和最佳实践
- [示例代码](docs/examples/) - 实际使用示例
- [架构文档](CLAUDE.md) - 系统架构和开发指南

## 🤝 贡献

我们欢迎各种形式的贡献！请查看 [贡献指南](CONTRIBUTING.md) 了解详情。

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🆘 支持

- [问题反馈](https://github.com/AetheriusMC/Aetherius-Core/issues)
- [讨论区](https://github.com/AetheriusMC/Aetherius-Core/discussions)

---

**注意**: 这是 v2.0 版本，架构已完全重构，具备企业级稳定性和可扩展性。
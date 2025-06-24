# Aetherius - 核心引擎 (Phase 1) 详细开发规划

## 1. 核心设计哲学

Aetherius Core 是整个系统的基石。我们的首要目标是构建一个 **极度轻量、稳定、高性能且具备高度扩展性** 的内核。它本身不提供任何花哨的功能，只专注于做好最基础、最重要的事情：管理服务端进程、处理信息流，并为上层组件和插件提供一个可靠的运行环境。

- **稳定压倒一切**: 核心代码必须经过充分的测试，确保 7x24 小时稳定运行。
- **性能优先**: 采用异步 I/O 模型，最小化对游戏服务器 TPS 的影响。
- **接口驱动**: 定义清晰、稳定的内部 API，这是未来所有扩展的基础。
- **CLI 即核心**: 核心引擎交付时，其自带的 CLI 工具本身就是一套完整且强大的本地管理方案。

## 2. 核心引擎 (Aetherius Core) 模块详解

### 2.1. 服务端进程包装器 (ServerProcessWrapper)

这是与 Minecraft 服务端直接交互的最底层模块。

**技术选型**: Python 的 `asyncio.create_subprocess_exec`。

**核心功能**:
- **进程管理**: 异步地启动、终止 (SIGTERM)、强制终止 (SIGKILL) 和重启 Minecraft 服务端 (.jar 文件) 进程。
- **健康监控**: 持续监控子进程的存活状态，一旦检测到意外崩溃，能立即触发预警或自动重启事件。
- **I/O 重定向**: 建立三个异步管道：
  - `stdout` (标准输出): 逐行异步读取，并交由日志解析器处理。
  - `stderr` (标准错误): 逐行异步读取，用于捕获错误和异常。
  - `stdin` (标准输入): 提供一个异步写入方法，用于向服务端发送指令。

**对外接口** (示例):
```python
class ServerProcessWrapper:
    async def start(self): ...
    async def stop(self, force=False): ...
    async def restart(self): ...
    async def send_command(self, command: str): ...
    def is_alive(self) -> bool: ...
```

### 2.2. 日志解析与事件系统 (LogParser & EventManager)

这是将原始日志流转化为结构化信息的处理中枢。

**日志解析器 (LogParser)**:
- **机制**: 基于正则表达式 (Regex) 和可配置规则。规则定义在外部文件 (如 `rules.yaml`) 中，方便用户为不同服务端 (如 Paper, Fabric) 或特殊插件日志添加自定义解析规则。
- **职责**: 接收 stdout 的原始日志行，匹配规则，如果匹配成功，则生成一个结构化的事件对象。

**事件管理器 (EventManager)**:
- **机制**: 实现一个高效的异步事件总线。使用装饰器语法来注册事件监听器。
- **核心事件定义**:
  - `ServerLifecycleEvent`: `ServerStartingEvent`, `ServerStartedEvent`, `ServerStoppingEvent`
  - `PlayerEvent`: `PlayerJoinEvent(player_name)`, `PlayerLeaveEvent(player_name)`, `PlayerChatEvent(player_name, message)`
  - `SystemEvent`: `ServerCrashEvent`, `CoreReadyEvent`

**监听器注册** (示例):
```python
from aetherius.events import OnEvent, PlayerJoinEvent

@OnEvent(PlayerJoinEvent)
async def handle_player_join(event: PlayerJoinEvent):
    print(f"玩家 {event.player_name} 加入了服务器！")
```

**特性**: 支持事件的优先级处理和取消传播。

### 2.3. 加载器系统 (LoaderSystem)

Aetherius 支持两种粒度的扩展，由两个不同的加载器管理。

**插件加载器 (PluginLoader)**:
- **目标**: 加载轻量级的、基于单脚本的插件 (e.g., `my_plugin.py`)。
- **机制**: 扫描 `plugins/` 目录，使用 `importlib` 动态加载模块。插件通过预定义的函数或类与核心交互。
- **生命周期**: `on_load()`, `on_unload()`, `on_reload()`。

**组件加载器 (ComponentLoader)**:
- **目标**: 加载重量级的、功能性的官方组件 (e.g., `component: web`)。
- **机制**: 扫描 `components/` 目录。每个组件是一个独立的 Python 包，包含一个 `pyproject.toml` 或 `component.json` 清单文件，定义其元数据和依赖。
- **依赖管理**: 负责解析组件间的依赖关系，并按正确顺序加载。

### 2.4. 全功能 CLI 工具 (AetheriusCLI)

这是用户与核心引擎交互的主要界面。

**技术选型**: 强烈推荐 `Typer` (基于 Click) 结合 `rich` 库。Typer 能提供出色的自动补全和参数类型检查，rich 能美化输出格式。

**核心命令族**:
- `aetherius server start|stop|restart|status`: 管理服务器生命周期。
- `aetherius cmd <vanilla_command>`: 向服务器发送指令 (如 `say Hello World`)。
- `aetherius player list|kick <name> [reason]`: 基础的玩家管理。
- `aetherius component list|enable <name>|disable <name>`: 管理功能组件。
- `aetherius plugin list|reload <name>`: 管理轻量级插件。
- `aetherius console`: 进入交互式控制台模式，直接显示服务端日志并允许输入指令。

### 2.5. 核心配置与 API (AetheriusCore)

这是将所有模块粘合在一起的中央对象。

**配置 (Config)**: 使用 Pydantic 定义配置模型，从 `config.yaml` 中加载配置，并提供类型安全的访问。

**核心 API (AetheriusCore)**:
- 作为单例模式存在。
- 持有所有核心模块的实例 (`.server`, `.events`, `.components` 等)。
- 为插件和组件提供一个统一的、受控的 API 接口，而不是直接暴露内部模块。

## 3. 第一阶段开发步骤 (Milestone)

**目标**：发布 Aetherius Core v0.1.0 (Alpha)

### Sprint 1 (第 1-2 周): 项目初始化与进程包装
- 建立 Git 仓库，配置 pre-commit hooks, linter (ruff), formatter (black)。
- 搭建基本的 asyncio 应用骨架。
- 完成 `ServerProcessWrapper` 的核心功能，能稳定启停一个本地的 vanilla 服务端。
- 实现最基础的 CLI 命令：`aetherius server start/stop`。

### Sprint 2 (第 3-5 周): 日志与事件流
- 实现 `LogParser`，能够解析出玩家加入/离开/聊天等基本事件。
- 实现 `EventManager`，支持装饰器注册和异步事件分发。
- 将两者连接，实现日志 -> 事件的转化。
- 增强 CLI：`aetherius console` 模式现在可以实时显示格式化后的服务器日志和聊天信息。

### Sprint 3 (第 6-8 周): 扩展性基础 (加载器)
- 实现 `PluginLoader`，能够加载简单的 `.py` 脚本插件。
- 编写一个"Hello World"插件进行测试。
- 设计并实现 `ComponentLoader` 的基本框架和清单文件格式。
- 增强 CLI：`aetherius plugin list/reload`。

### Sprint 4 (第 9-12 周): CLI 功能完善与 Alpha 发布
- 使用 `Typer` 和 `rich` 全面构建和美化所有规划的 CLI 命令。
- 完善 `Config` 系统，并提供一份详细的默认配置文件。
- 编写核心功能的用户文档和开发者文档初稿。
- 进行全面的内部测试和 Bug 修复。
- 打包并在 PyPI 上发布第一个 Alpha 版本。

## 4. 初始项目目录结构

```
aetherius/
├── aetherius/              # 核心代码库
│   ├── api/                # 对外 API 接口
│   ├── cli/                # CLI 命令定义
│   ├── components/         # 组件加载器与管理
│   ├── core/               # 核心模块 (server, events, config)
│   ├── plugins/            # 插件加载器与管理
│   └── __main__.py         # 程序入口
├── components/             # 用户安装的组件目录
│   └── (empty)
├── plugins/                # 用户安装的插件目录
│   └── (empty)
├── server/                 # Minecraft 服务端文件存放处
│   └── server.jar
├── logs/                   # Aetherius 自身日志
├── config.yaml             # 核心配置文件
├── pyproject.toml          # 项目构建与依赖
└── README.md
```

## 5. 技术栈总结

- **核心语言**: Python 3.11+
- **异步框架**: asyncio
- **CLI 框架**: Typer + Rich
- **配置管理**: Pydantic + PyYAML
- **构建工具**: Poetry / setuptools
- **代码质量**: ruff (linter), black (formatter), pre-commit hooks
- **文档**: Sphinx + reStructuredText

## 6. 成功标准

Phase 1 完成后，Aetherius Core 应该能够：

1. ✅ 稳定地管理 Minecraft 服务端进程（启动、停止、重启）
2. ✅ 实时解析服务端日志并生成结构化事件
3. ✅ 提供完整的 CLI 工具集进行基础管理
4. ✅ 支持简单的插件加载和管理
5. ✅ 提供清晰的扩展接口供后续开发
6. ✅ 具备良好的错误处理和日志记录机制
7. ✅ 拥有基础的配置系统和文档

这个 Alpha 版本将为后续的 Web 界面、高级功能组件和生态系统扩展奠定坚实的基础。
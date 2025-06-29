# **Aetherius Web Console 技术文档**

## 1. 概述

**Aetherius Web Console** (以下简称 Web Console) 是 Aetherius 核心系统的官方图形化管理界面。它作为一个独立的Aetherius组件运行，通过 WebSocket 和 RESTful API 与核心进行实时、双向的通信。Web Console 旨在为服务器管理员提供一个现代、直观、功能强大的远程管理工具，完全取代传统的命令行操作。

本组件的设计严格遵循一个核心原则：**所有展示和操作的数据都必须实时来源于 Aetherius Core API**。绝不使用任何模拟数据或前端缓存的静态数据，以确保数据的绝对准确性和实时性。

### 1.1. 核心功能

*   **实时仪表盘**: 动态展示服务器的核心性能指标 (CPU, 内存, TPS), 在线玩家数量等。
*   **交互式控制台**: 实时显示服务器日志，并提供命令输入与执行功能。
*   **玩家管理**: 查看在线及离线玩家列表，管理玩家权限 (OP/De-OP)、执行操作 (踢出/封禁)。
*   **文件管理器**: 浏览、编辑、上传和下载服务器文件。
*   **插件与组件管理**: 查看已安装的插件和组件，并对其进行加载、卸载、启用、禁用等生命周期管理。
*   **系统健康监控**: 实时监控系统健康状况，提供预警和诊断信息。

### 1.2. 技术架构

*   **后端**: FastAPI, Uvicorn, WebSocket
*   **前端**: Vue 3 (Composition API), Vite, Element Plus, Pinia, ECharts
*   **通信协议**:
    *   **REST API**: 用于执行一次性的、请求-响应模式的操作 (如启动服务器)。
    *   **WebSocket**: 用于持续性的、实时的双向数据流 (如控制台日志、状态更新)。

## 2. 功能模块详解

所有功能模块的数据和操作均直接映射到 `Aetherius Core 统一API`。

### 2.1. 仪表盘 (Dashboard)

仪表盘是 Web Console 的门户，提供服务器当前状态的快照。所有数据通过 WebSocket 实时推送或定期通过 REST API 刷新。

*   **服务器状态**:
    *   **数据来源**: `api.server.get_status()`
    *   **显示内容**: 运行状态 (running/stopped/starting/stopping), 启动时间, Minecraft 版本。
    *   **实时更新**: 通过监听 `server_start`, `server_stop` 事件，并结合 WebSocket 推送的 `status` 消息进行更新。

*   **性能监控图表**:
    *   **数据来源**: `api.monitoring.get_performance_data()`
    *   **显示内容**:
        *   CPU 使用率 (`cpu_percent`)
        *   内存使用 (`memory_mb`)
        *   TPS (Ticks Per Second) - *此数据需要通过扩展API或特定事件获取*
    *   **实现方式**: 前端通过 WebSocket 接收由后端定时推送的性能数据，并使用 ECharts 动态渲染图表。

*   **玩家统计**:
    *   **数据来源**: `api.server.get_status()` (`online_players`, `max_players`)
    *   **显示内容**: 在线玩家数 / 最大玩家数。
    *   **实时更新**: 通过监听 `player_join`, `player_leave` 事件，并结合 WebSocket 推送的 `status` 消息进行更新。

### 2.2. 实时控制台 (Console)

提供一个与服务器后台完全同步的交互式控制台。

*   **日志显示**:
    *   **数据来源**: 监听 `InfoStreamType.CONSOLE_OUTPUT` 和 `InfoStreamType.SERVER_LOGS` 信息流。
    *   **实现方式**: 后端通过 `mgmt_api.register_stream_callback` 注册回调，将获取到的日志行通过 WebSocket (`/ws/console`) 实时推送到前端。前端对不同日志级别 (INFO, WARN, ERROR) 进行不同颜色的高亮显示。

*   **命令执行**:
    *   **数据来源**: `api.server.send_command(command: str)`
    *   **实现方式**: 前端输入框捕获用户输入的命令，通过 REST API (`POST /api/v1/server/command`) 发送到后端。后端调用核心API执行命令。命令本身及其输出会通过日志流返回到控制台。

### 2.3. 玩家管理 (Player Management)

提供全面的玩家数据查看和管理功能。

*   **玩家列表**:
    *   **数据来源**: `api.players.list(online_only: bool)`
    *   **显示内容**: 玩家名称, UUID, 在线状态, 上次在线时间。
    *   **实现方式**: 提供 "在线玩家" 和 "所有玩家" 两个视图。数据通过 REST API (`GET /api/v1/players`) 获取。列表会通过监听 `player_join` 和 `player_leave` 事件自动刷新。

*   **玩家详情**:
    *   **数据来源**: `api.players.get_player_info(player_name: str)`
    *   **显示内容**: 玩家的详细信息，包括等级、经验、生命值、饥饿度、坐标、游戏模式等。
    *   **实现方式**: 点击玩家列表中的条目，会触发一次 API 调用以获取该玩家的详细数据，并以弹窗或侧边栏的形式展示。

*   **玩家操作**:
    *   **数据来源**:
        *   `api.players.kick(player_name: str, reason: str)`
        *   `api.players.ban(player_name: str, reason: str)`
        *   `api.players.op(player_name: str)`
        *   `api.players.deop(player_name: str)`
    *   **实现方式**: 在玩家列表或详情视图中提供操作按钮 (踢出, 封禁, 设为OP, 取消OP)。点击后，前端会弹出确认框，要求输入原因（如果需要），然后通过相应的 REST API (`POST /api/v1/players/{uuid}/kick` 等) 执行操作。

### 2.4. 文件管理器 (File Manager)

*此功能依赖于核心API对文件系统的抽象，假设核心提供了相应的文件操作接口。*

*   **文件浏览**:
    *   **数据来源**: 假设存在 `api.files.list(path: str)`
    *   **显示内容**: 文件和目录列表，包括名称、大小、修改日期、权限。
    *   **实现方式**: 类似标准的文件浏览器界面，支持目录树和文件列表。点击目录会异步加载其内容。

*   **文件编辑**:
    *   **数据来源**:
        *   读取: `api.files.read(path: str)`
        *   保存: `api.files.write(path: str, content: str)`
    *   **实现方式**: 对于文本文件 (如 `.yml`, `.json`, `.properties`), 点击后会使用 Monaco Editor 在前端打开一个编辑器。编辑完成后，内容通过 API 写回服务器。

*   **文件操作**:
    *   **数据来源**:
        *   上传: `api.files.upload(path: str, file_data)`
        *   下载: `api.files.download(path: str)`
        *   删除: `api.files.delete(path: str)`
    *   **实现方式**: 提供上传、下载、删除按钮。上传功能会打开文件选择对话框，下载则直接触发浏览器下载。

### 2.5. 插件与组件管理

*   **列表展示**:
    *   **数据来源**: `api.plugins.list()` 和 `api.components.list()`
    *   **显示内容**: 名称、版本、描述、作者、启用状态。
    *   **实现方式**: 分别提供插件和组件两个标签页，通过 REST API 获取列表并展示。

*   **生命周期管理**:
    *   **数据来源**:
        *   `api.plugins.enable/disable/reload/load/unload(name: str)`
        *   `api.components.enable/disable/reload/load/unload(name: str)`
    *   **实现方式**: 每个条目旁边提供一个操作菜单，包含所有可用的生命周期操作。操作结果通过 `InfoStreamType.PLUGIN_EVENTS` 和 `InfoStreamType.COMPONENT_EVENTS` 事件流反馈，并自动刷新列表状态。

## 3. API 端点设计

Web Console 的后端作为核心 API 的一个适配器和代理，将核心功能封装为对前端友好的 RESTful API 和 WebSocket 通道。

### 3.1. REST API (`/api/v1`)

| Method | Endpoint                       | 核心 API 映射                               | 描述                                     |
| :----- | :----------------------------- | :------------------------------------------ | :--------------------------------------- |
| `POST` | `/server/start`                | `api.server.start()`                        | 启动服务器                               |
| `POST` | `/server/stop`                 | `api.server.stop()`                         | 停止服务器                               |
| `POST` | `/server/restart`              | `api.server.restart()`                      | 重启服务器                               |
| `POST` | `/server/command`              | `api.server.send_command()`                 | 发送控制台命令                           |
| `GET`  | `/players`                     | `api.players.list()`                        | 获取玩家列表                             |
| `GET`  | `/players/{uuid}`              | `api.players.get_player_info()`             | 获取玩家详情                             |
| `POST` | `/players/{uuid}/kick`         | `api.players.kick()`                        | 踢出玩家                                 |
| `POST` | `/players/{uuid}/ban`          | `api.players.ban()`                         | 封禁玩家                                 |
| `POST` | `/plugins/{name}/{operation}`  | `api.plugins.*`                             | 对插件执行操作 (enable/disable/reload)   |
| `POST` | `/components/{name}/{operation}` | `api.components.*`                          | 对组件执行操作 (enable/disable/reload)   |
| `GET`  | `/files`                       | `api.files.list()`                          | 获取文件列表                             |
| `GET`  | `/files/content`               | `api.files.read()`                          | 获取文件内容                             |
| `POST` | `/files/content`               | `api.files.write()`                         | 保存文件内容                             |

### 3.2. WebSocket 端点

| Endpoint      | 核心 API / 事件流 映射                                                              | 描述                                                         |
| :------------ | :------------------------------------------------------------------------------------ | :----------------------------------------------------------- |
| `/ws/status`  | `api.monitoring.get_performance_data`, `server_start`, `server_stop`, `player_join`, `player_leave` | 实时推送服务器状态、性能指标和玩家数量的聚合信息。     |
| `/ws/console` | `InfoStreamType.CONSOLE_OUTPUT`, `InfoStreamType.SERVER_LOGS`                         | 实时推送控制台和服务器日志。                                 |
| `/ws/events`  | `InfoStreamType.PLAYER_EVENTS`, `InfoStreamType.SYSTEM_EVENTS`, `InfoStreamType.PLUGIN_EVENTS`, `InfoStreamType.COMPONENT_EVENTS` | 推送各类系统级事件，用于前端UI的实时刷新和通知。 |

## 4. 安全与权限

Web Console 的安全完全依赖于 Aetherius Core 的安全机制。

*   **认证**: 用户登录 Web Console 需要提供凭据，后端将这些凭据传递给核心进行验证。验证成功后，后端会生成一个 JWT (JSON Web Token) 返回给前端，用于后续所有 API 请求的身份认证。
*   **授权**: 所有通过 Web Console 发起的操作，其权限检查都在 Aetherius Core 层面完成。例如，一个只有 `viewer` 权限的用户，即使前端显示了 "封禁玩家" 的按钮，其发出的 API 请求在核心层面也会因为 `InsufficientPermissionsException` 而被拒绝。前端会根据 API 返回的 403 Forbidden 状态码向用户显示权限不足的提示。

## 5. 部署与集成

Web Console 作为 Aetherius 的一个标准组件，其部署过程非常简单：

1.  将 `ComponentWeb` 目录放置到 Aetherius Core 的 `components` 目录下。
2.  启动 Aetherius Core。核心的组件加载器会自动发现并加载 Web Console。
3.  在核心控制台或通过管理 API 启用该组件: `component enable web`。
4.  组件启用后，其内部的 FastAPI 服务器会自动启动，并监听在 `component.yaml` 中配置的端口（默认为 8080）。
5.  通过浏览器访问 `http://<your-server-ip>:8080` 即可打开 Web Console 界面。

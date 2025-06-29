# Aetherius Core 统一API文档

## 概述

Aetherius Core 统一API系统提供了一个优雅、全面的接口来访问所有核心功能。该系统采用模块化设计，确保组件所需的所有服务都可以通过API及其扩展调用，同时保证核心可以独立运行。

## 架构设计

### 核心理念

- **统一接口**: 所有功能通过单一 API 入口点访问
- **模块化设计**: 功能按领域分组为独立的 API 模块
- **优雅初始化**: 支持多种初始化模式和生命周期管理
- **核心独立性**: API 系统不依赖外部组件，可独立运行
- **扩展性**: 支持高级管理功能和自定义扩展

### 系统架构

```
AetheriusCoreAPI (统一入口)
├── ServerAPI (服务器管理)
├── PluginAPI (插件管理)
├── ComponentAPI (组件管理)
├── PlayerAPI (玩家管理)
├── MonitoringAPI (性能监控)
├── ConfigAPI (配置管理)
└── EventAPI (事件系统)

AetheriusManagementAPI (高级管理)
├── 访问控制系统
├── 信息流管理
├── 批量操作
└── 系统健康监控
```

## 核心API类

### AetheriusCoreAPI

主要的统一API接口，提供对所有核心功能的访问。

#### 初始化

```python
from aetherius.api.core import AetheriusCoreAPI

# 基本初始化
api = AetheriusCoreAPI()

# 使用现有服务器实例
api = AetheriusCoreAPI(server=existing_server)

# 禁用自动初始化
api = AetheriusCoreAPI(auto_initialize=False)
```

#### 工厂函数

```python
from aetherius.api.core import create_core_api, get_core_api

# 创建新实例
api = await create_core_api()

# 获取全局实例
api = await get_core_api()
```

#### 上下文管理

```python
# 自动资源管理
async with api.managed_context() as managed_api:
    status = await managed_api.get_status()
    # API 将在退出时自动清理
```

#### 主要方法

```python
# 初始化所有模块
await api.initialize()

# 获取系统状态
status = await api.get_status()

# 清理资源
await api.close()
```

## API 模块详解

### 1. ServerAPI - 服务器管理

管理 Minecraft 服务器的生命周期和操作。

#### 主要功能

```python
# 获取服务器状态
status = await api.server.get_status()

# 启动服务器
result = await api.server.start()

# 停止服务器
result = await api.server.stop()

# 重启服务器
result = await api.server.restart()

# 发送命令
result = await api.server.send_command("say Hello World")

# 获取在线玩家数
count = await api.server.get_online_players_count()
```

#### 返回格式

```python
# 状态信息
{
    "status": "running|stopped|starting|stopping",
    "uptime": 3600.0,
    "online_players": 5,
    "max_players": 20,
    "version": "1.20.1",
    "timestamp": "2024-01-01T12:00:00Z"
}

# 操作结果
{
    "success": True,
    "message": "Server started successfully",
    "timestamp": "2024-01-01T12:00:00Z"
}
```

### 2. PluginAPI - 插件管理

管理插件的加载、启用、禁用和生命周期。

#### 主要功能

```python
# 列出所有插件
plugins = await api.plugins.list()

# 加载插件
result = await api.plugins.load("plugin_name")

# 卸载插件
result = await api.plugins.unload("plugin_name")

# 启用插件
result = await api.plugins.enable("plugin_name")

# 禁用插件
result = await api.plugins.disable("plugin_name")

# 重载插件
result = await api.plugins.reload("plugin_name")
```

#### 插件信息格式

```python
{
    "name": "example_plugin",
    "version": "1.0.0",
    "description": "示例插件",
    "author": "开发者",
    "enabled": True,
    "loaded": True,
    "dependencies": ["dependency1", "dependency2"],
    "path": "/path/to/plugin"
}
```

### 3. ComponentAPI - 组件管理

管理系统组件的生命周期和状态。

#### 主要功能

```python
# 列出所有组件
components = await api.components.list()

# 加载组件
result = await api.components.load("component_name")

# 卸载组件
result = await api.components.unload("component_name")

# 启用组件
result = await api.components.enable("component_name")

# 禁用组件
result = await api.components.disable("component_name")
```

#### 组件信息格式

```python
{
    "name": "ComponentWeb",
    "version": "1.0.0",
    "description": "Web管理界面组件",
    "type": "web_component",
    "enabled": True,
    "loaded": True,
    "config": {...},
    "endpoints": [...]
}
```

### 4. PlayerAPI - 玩家管理

管理玩家数据和操作。

#### 主要功能

```python
# 列出玩家
players = await api.players.list()
online_players = await api.players.list(online_only=True)

# 获取玩家详细信息
player_info = await api.players.get_player_info("player_name")

# 踢出玩家
result = await api.players.kick("player_name", "reason")

# 封禁玩家
result = await api.players.ban("player_name", "reason")

# 解封玩家
result = await api.players.unban("player_name")

# 设置管理员
result = await api.players.op("player_name")

# 取消管理员
result = await api.players.deop("player_name")
```

#### 玩家信息格式

```python
{
    "name": "player_name",
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "online": True,
    "last_seen": "2024-01-01T12:00:00Z",
    "level": 30,
    "experience": 15000,
    "health": 20.0,
    "food_level": 20,
    "location": {
        "world": "world",
        "x": 100.0,
        "y": 64.0,
        "z": 200.0
    },
    "statistics": {...}
}
```

### 5. MonitoringAPI - 性能监控

监控系统性能和资源使用情况。

#### 主要功能

```python
# 获取性能数据
performance = await api.monitoring.get_performance_data()

# 获取系统健康状况
health = await api.monitoring.get_system_health()

# 开始性能监控
await api.monitoring.start_performance_monitoring(interval=10.0)

# 停止性能监控
await api.monitoring.stop_performance_monitoring()
```

#### 性能数据格式

```python
{
    "cpu_percent": 45.2,
    "memory_mb": 2048.0,
    "uptime_seconds": 3600.0,
    "system_cpu_percent": 25.0,
    "system_memory_percent": 60.0,
    "system_disk_percent": 30.0,
    "timestamp": "2024-01-01T12:00:00Z"
}
```

### 6. ConfigAPI - 配置管理

管理系统配置和设置。

#### 主要功能

```python
# 获取配置值
value = api.config.get("server.port", 25565)

# 设置配置值
success = api.config.set("server.port", 25566)

# 删除配置项
success = api.config.delete("custom.setting")

# 保存配置
success = api.config.save()
```

#### 配置访问

```python
# 支持点号分隔的路径
port = api.config.get("server.port")
motd = api.config.get("server.motd")
debug = api.config.get("logging.debug", False)
```

### 7. EventAPI - 事件系统

管理事件的注册、发出和处理。

#### 主要功能

```python
# 注册事件处理器
def on_player_join(player_name):
    print(f"Player {player_name} joined")

api.events.register("player_join", on_player_join)

# 发出事件
await api.events.emit("custom_event", data={"key": "value"})

# 注销事件处理器
api.events.unregister("player_join", on_player_join)
```

#### 内置事件类型

- `server_start` - 服务器启动
- `server_stop` - 服务器停止
- `player_join` - 玩家加入
- `player_leave` - 玩家离开
- `player_chat` - 玩家聊天
- `plugin_loaded` - 插件加载
- `component_enabled` - 组件启用

## 高级管理API

### AetheriusManagementAPI

扩展的管理API，提供高级控制功能和访问权限管理。

#### 初始化

```python
from aetherius.api.management import AetheriusManagementAPI, ControlLevel

# 创建管理API实例
mgmt_api = AetheriusManagementAPI(server, ControlLevel.ADMIN)
```

#### 访问控制级别

```python
class ControlLevel(Enum):
    READ_ONLY = "read_only"    # 只读访问
    OPERATOR = "operator"      # 操作员权限
    ADMIN = "admin"           # 管理员权限
    SYSTEM = "system"         # 系统级权限
```

#### 信息流管理

```python
from aetherius.api.management import InfoStreamType

# 支持的信息流类型
INFO_STREAMS = [
    InfoStreamType.CONSOLE_OUTPUT,     # 控制台输出
    InfoStreamType.SERVER_LOGS,       # 服务器日志
    InfoStreamType.PERFORMANCE_METRICS, # 性能指标
    InfoStreamType.PLAYER_EVENTS,     # 玩家事件
    InfoStreamType.SYSTEM_EVENTS,     # 系统事件
    InfoStreamType.PLUGIN_EVENTS,     # 插件事件
    InfoStreamType.COMPONENT_EVENTS   # 组件事件
]

# 注册信息流回调
mgmt_api.register_stream_callback(
    InfoStreamType.CONSOLE_OUTPUT, 
    console_handler
)

# 广播到信息流
await mgmt_api.broadcast_to_stream(
    InfoStreamType.SYSTEM_EVENTS,
    {"event": "maintenance_start", "timestamp": "..."}
)

# 获取信息流信息
stream_info = mgmt_api.get_stream_info()
```

#### 批量操作

```python
# 批量插件操作
plugin_operations = [
    {"name": "plugin1", "operation": "enable"},
    {"name": "plugin2", "operation": "reload"},
    {"name": "plugin3", "operation": "disable"}
]
results = await mgmt_api.batch_plugin_operations(plugin_operations)

# 批量组件操作
component_operations = [
    {"name": "ComponentWeb", "operation": "enable"},
    {"name": "ComponentDB", "operation": "reload"}
]
results = await mgmt_api.batch_component_operations(component_operations)
```

#### 高级服务器控制

```python
# 优雅重启（带警告）
await mgmt_api.graceful_restart(
    warning_intervals=[60, 30, 10, 5],  # 重启前警告时间（秒）
    custom_message="服务器将重启以应用更新"
)

# 世界备份
backup_result = await mgmt_api.backup_world(
    backup_name="pre_update_backup",
    include_plugins=True
)
```

## 使用示例

### 基本使用

```python
import asyncio
from aetherius.api.core import AetheriusCoreAPI

async def main():
    # 创建API实例
    api = AetheriusCoreAPI()
    
    try:
        # 初始化API
        await api.initialize()
        
        # 获取服务器状态
        status = await api.server.get_status()
        print(f"服务器状态: {status['status']}")
        
        # 列出插件
        plugins = await api.plugins.list()
        print(f"已加载插件: {len(plugins)} 个")
        
        # 获取性能数据
        performance = await api.monitoring.get_performance_data()
        print(f"CPU使用率: {performance['cpu_percent']}%")
        
    finally:
        # 清理资源
        await api.close()

# 运行
asyncio.run(main())
```

### 上下文管理器使用

```python
async def managed_example():
    async with AetheriusCoreAPI().managed_context() as api:
        # API 自动初始化和清理
        status = await api.get_status()
        
        # 启动服务器
        if status['status'] == 'stopped':
            result = await api.server.start()
            print(f"服务器启动: {result['success']}")
        
        # 监控性能
        await api.monitoring.start_performance_monitoring(interval=5.0)
        
        # 等待一段时间
        await asyncio.sleep(30)
        
        # 停止监控
        await api.monitoring.stop_performance_monitoring()
    # API 在此处自动清理
```

### 事件处理示例

```python
async def event_example():
    api = AetheriusCoreAPI()
    
    # 定义事件处理器
    def on_player_join(player_name):
        print(f"欢迎 {player_name} 加入服务器!")
    
    def on_server_start():
        print("服务器已启动")
    
    # 注册事件处理器
    api.events.register("player_join", on_player_join)
    api.events.register("server_start", on_server_start)
    
    # 启动服务器（将触发事件）
    await api.server.start()
    
    # 等待事件
    await asyncio.sleep(60)
    
    await api.close()
```

### 高级管理示例

```python
from aetherius.api.management import AetheriusManagementAPI, ControlLevel

async def management_example():
    # 创建管理API（需要管理员权限）
    mgmt_api = AetheriusManagementAPI(None, ControlLevel.ADMIN)
    
    # 批量启用插件
    plugin_ops = [
        {"name": "EssentialsX", "operation": "enable"},
        {"name": "WorldEdit", "operation": "enable"},
        {"name": "Vault", "operation": "enable"}
    ]
    
    results = await mgmt_api.batch_plugin_operations(plugin_ops)
    for result in results:
        print(f"插件 {result['plugin']}: {result['message']}")
    
    # 设置性能监控
    await mgmt_api.start_performance_monitoring(interval=10.0)
    
    # 优雅重启服务器
    await mgmt_api.graceful_restart(
        warning_intervals=[60, 30, 10],
        custom_message="服务器将在 {} 秒后重启"
    )
```

## 配置

### API 配置项

在 `config.yaml` 中可以配置以下API相关设置：

```yaml
api:
  # API服务器配置
  server:
    host: "127.0.0.1"
    port: 8080
    
  # 监控配置
  monitoring:
    enabled: true
    interval: 10.0
    retention_hours: 24
    
  # 事件系统配置
  events:
    max_listeners: 100
    async_timeout: 30.0
    
  # 安全配置
  security:
    access_control: true
    rate_limiting: true
    max_requests_per_minute: 60
```

### 环境变量

```bash
# API访问控制
export AETHERIUS_API_ACCESS_LEVEL=admin

# 监控设置
export AETHERIUS_MONITORING_INTERVAL=10

# 事件系统
export AETHERIUS_EVENTS_ENABLED=true
```

## 错误处理

### 异常类型

```python
from aetherius.api.exceptions import (
    AetheriusAPIException,      # 基础API异常
    ServerNotRunningException,  # 服务器未运行
    PluginNotFoundException,    # 插件未找到
    InsufficientPermissionsException,  # 权限不足
    ConfigurationException      # 配置错误
)

try:
    await api.server.start()
except ServerNotRunningException as e:
    print(f"服务器启动失败: {e}")
except AetheriusAPIException as e:
    print(f"API错误: {e}")
```

### 错误响应格式

```python
{
    "success": False,
    "error": "错误描述",
    "error_code": "ERROR_CODE",
    "timestamp": "2024-01-01T12:00:00Z",
    "details": {
        "additional": "info"
    }
}
```

## 最佳实践

### 1. 资源管理

```python
# 推荐：使用上下文管理器
async with AetheriusCoreAPI().managed_context() as api:
    # 使用API
    pass  # 自动清理

# 或者手动管理
api = AetheriusCoreAPI()
try:
    await api.initialize()
    # 使用API
finally:
    await api.close()
```

### 2. 错误处理

```python
async def robust_server_start():
    api = AetheriusCoreAPI()
    
    try:
        result = await api.server.start()
        if not result['success']:
            logger.error(f"服务器启动失败: {result.get('error', '未知错误')}")
            return False
        return True
    except Exception as e:
        logger.exception(f"启动服务器时发生异常: {e}")
        return False
    finally:
        await api.close()
```

### 3. 性能考虑

```python
# 避免频繁创建API实例
class MyService:
    def __init__(self):
        self.api = None
    
    async def start(self):
        self.api = await create_core_api()
    
    async def stop(self):
        if self.api:
            await self.api.close()
    
    async def get_status(self):
        if not self.api:
            raise RuntimeError("Service not started")
        return await self.api.get_status()
```

### 4. 事件处理

```python
class EventHandler:
    def __init__(self, api):
        self.api = api
        self._handlers = {}
    
    def register_all(self):
        """注册所有事件处理器"""
        self._handlers['player_join'] = self.on_player_join
        self._handlers['server_start'] = self.on_server_start
        
        for event, handler in self._handlers.items():
            self.api.events.register(event, handler)
    
    def unregister_all(self):
        """注销所有事件处理器"""
        for event, handler in self._handlers.items():
            self.api.events.unregister(event, handler)
    
    def on_player_join(self, player_name):
        # 处理玩家加入事件
        pass
    
    def on_server_start(self):
        # 处理服务器启动事件
        pass
```

## 扩展开发

### 自定义API模块

```python
from aetherius.api.core import APIModule

class CustomAPI(APIModule):
    """自定义API模块"""
    
    async def initialize(self) -> bool:
        """初始化模块"""
        self.logger.info("自定义API模块初始化")
        return True
    
    async def cleanup(self) -> None:
        """清理模块"""
        self.logger.info("自定义API模块清理")
    
    async def custom_operation(self) -> dict:
        """自定义操作"""
        return {"success": True, "message": "自定义操作完成"}

# 集成到核心API
class ExtendedCoreAPI(AetheriusCoreAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom = CustomAPI(self)
        self._modules["custom"] = self.custom
```

### 插件API扩展

```python
# 在插件中扩展API功能
from aetherius.api.core import get_core_api

class MyPlugin:
    async def on_enable(self):
        # 获取核心API
        self.api = await get_core_api()
        
        # 注册自定义事件处理器
        self.api.events.register("custom_event", self.handle_custom_event)
    
    async def handle_custom_event(self, data):
        # 处理自定义事件
        self.logger.info(f"收到自定义事件: {data}")
    
    async def trigger_custom_action(self):
        # 使用API执行操作
        await self.api.server.send_command("say 插件执行了自定义操作")
        await self.api.events.emit("custom_event", {"source": "plugin"})
```

## 故障排除

### 常见问题

1. **API初始化失败**
   ```python
   # 检查配置文件
   config = api.config.get('api.enabled', True)
   if not config:
       print("API被配置为禁用")
   ```

2. **服务器连接失败**
   ```python
   # 检查服务器状态
   status = await api.server.get_status()
   if status['status'] == 'stopped':
       print("服务器未运行")
   ```

3. **权限不足错误**
   ```python
   # 检查访问级别
   from aetherius.api.management import AetheriusManagementAPI
   mgmt_api = AetheriusManagementAPI(server, ControlLevel.ADMIN)
   ```

### 调试模式

```python
import logging

# 启用调试日志
logging.getLogger('aetherius.api').setLevel(logging.DEBUG)

# 或在配置中设置
# config.yaml
logging:
  level: DEBUG
  loggers:
    aetherius.api: DEBUG
```

## 版本兼容性

- **最低Python版本**: 3.11+
- **Minecraft版本**: 1.16.5+
- **API版本**: 1.0.0

### 版本升级指南

从旧版本升级到统一API系统时，请注意以下变更：

1. **导入路径变更**
   ```python
   # 旧版本
   from aetherius.server import ServerManager
   
   # 新版本
   from aetherius.api.core import AetheriusCoreAPI
   api = AetheriusCoreAPI()
   # 使用 api.server 替代 ServerManager
   ```

2. **异步操作**
   ```python
   # 旧版本
   result = server.start()
   
   # 新版本
   result = await api.server.start()
   ```

3. **配置访问**
   ```python
   # 旧版本
   config = Config()
   port = config.get_server_port()
   
   # 新版本
   port = api.config.get('server.port', 25565)
   ```

---

*本文档描述了Aetherius Core统一API系统的完整功能和使用方法。如有疑问或需要更多信息，请参考源代码或联系开发团队。*
# API 文档

Aetherius Core 提供了一套完整的 API，用于扩展和集成。

## 核心 API

### 应用程序接口

- **AetheriusCore**: 主应用程序类
  - `initialize()`: 初始化所有系统
  - `run()`: 启动应用程序
  - `shutdown()`: 优雅关闭

### 依赖注入

- **DependencyContainer**: 依赖注入容器
  - `register()`: 注册服务
  - `resolve()`: 解析依赖
  - `register_singleton()`: 注册单例
  - `register_transient()`: 注册瞬态服务

### 配置管理

- **ConfigManager**: 配置管理器
  - `get()`: 获取配置值
  - `set()`: 设置配置值
  - `add_source()`: 添加配置源
  - `reload()`: 重新加载配置

- **IConfigSource**: 配置源接口
  - `load()`: 加载配置
  - `save()`: 保存配置
  - `watch()`: 监听变更

### 事件系统

- **EnhancedEventBus**: 增强事件总线
  - `emit()`: 发送事件
  - `subscribe()`: 订阅事件
  - `unsubscribe()`: 取消订阅
  - `start()`: 启动事件总线

- **EventMetadata**: 事件元数据
  - `priority`: 事件优先级
  - `delivery_mode`: 传递模式
  - `timeout`: 超时设置

### 安全框架

- **SecurityManager**: 安全管理器
  - `authenticate()`: 用户认证
  - `authorize()`: 权限检查
  - `create_session()`: 创建会话
  - `revoke_session()`: 撤销会话

- **Permission**: 权限类
  - `name`: 权限名称
  - `resource_type`: 资源类型
  - `permission_type`: 权限类型

### 监控系统

- **MonitoringContext**: 监控上下文
  - `start_monitoring()`: 开始监控
  - `stop_monitoring()`: 停止监控
  - `get_metrics()`: 获取指标

- **IMetricsCollector**: 指标收集器接口
  - `increment()`: 增加计数器
  - `gauge()`: 设置仪表值
  - `histogram()`: 记录直方图

## 扩展 API

### 插件系统

- **IPlugin**: 插件接口
  - `initialize()`: 插件初始化
  - `enable()`: 启用插件
  - `disable()`: 禁用插件
  - `cleanup()`: 清理资源

### 组件系统

- **IComponent**: 组件接口
  - `start()`: 启动组件
  - `stop()`: 停止组件
  - `get_status()`: 获取状态
  - `get_info()`: 获取信息

## 事件参考

### 核心事件

- **ApplicationStarted**: 应用程序启动
- **ApplicationStopped**: 应用程序停止
- **ConfigChanged**: 配置变更
- **SecurityEvent**: 安全事件

### 服务器事件

- **ServerStarted**: 服务器启动
- **ServerStopped**: 服务器停止
- **PlayerJoined**: 玩家加入
- **PlayerLeft**: 玩家离开
- **ChatMessage**: 聊天消息

## 使用示例

### 基本插件

```python
from aetherius.plugins import IPlugin
from aetherius.core.events import PlayerJoinEvent

class MyPlugin(IPlugin):
    def initialize(self):
        self.event_bus.subscribe(PlayerJoinEvent, self.on_player_join)
    
    def on_player_join(self, event: PlayerJoinEvent):
        print(f"玩家 {event.player_name} 加入了服务器")
```

### 配置管理

```python
from aetherius.core.config import ConfigManager, FileConfigSource

config = ConfigManager()
config.add_source(FileConfigSource("my_config.yaml"))

# 获取配置
value = config.get("my_setting", "default_value")

# 设置配置
config.set("my_setting", "new_value")
```

### 事件发送

```python
from aetherius.core.events import EnhancedEventBus, EventMetadata, EventPriority

event_bus = EnhancedEventBus()

# 发送高优先级事件
await event_bus.emit(
    "custom.event",
    {"data": "value"},
    metadata=EventMetadata(priority=EventPriority.HIGH)
)
```

## 错误处理

### 异常类型

- **ConfigError**: 配置相关错误
- **SecurityError**: 安全相关错误
- **EventError**: 事件处理错误
- **PluginError**: 插件相关错误

### 最佳实践

1. 总是检查返回值
2. 使用适当的异常处理
3. 正确清理资源
4. 遵循异步编程模式

## 版本兼容性

当前 API 版本: `2.0.0`

- **主版本**: 不兼容的 API 变更
- **次版本**: 向后兼容的新功能
- **修订版本**: 向后兼容的错误修复
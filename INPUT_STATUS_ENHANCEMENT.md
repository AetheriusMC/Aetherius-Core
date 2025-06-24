# 输入状态指示区域实现总结

## 问题描述

在原有的增强控制台中，用户无法看到正在输入的内容，因为使用的是标准的 `input()` 函数，这导致：

1. 输入时没有实时反馈
2. 无法显示正在输入的命令
3. 用户体验较差，不知道当前输入状态

## 解决方案

实现了一个全新的输入处理器 `InputHandler`，提供实时输入状态显示功能。

## 核心功能

### 1. 输入状态指示区域

在控制台布局中新增了一个专门的输入区域：

```
┌─────────────────────────────────────────────────────────┐
│                Aetherius Enhanced Console               │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────┬─────────────────────────────┐
│     Server Logs &       │        Statistics           │
│         Events          │                             │
└─────────────────────────┴─────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ Input                                                   │
│ > [Minecraft] /gamemode creative_                       │  ← 新增的输入状态区域
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ / Minecraft  ! Aetherius  @ System  exit to quit       │
└─────────────────────────────────────────────────────────┘
```

### 2. 实时命令类型识别

输入处理器能够实时识别和显示命令类型：

- **默认状态**: `> Type a command...`
- **Minecraft命令**: `> [Minecraft] /list_`
- **Aetherius命令**: `> [Aetherius] !stats_`
- **系统命令**: `> [System] @time_`
- **插件命令**: `> [Plugin] #help_`

### 3. 光标位置显示

- 光标用蓝色背景下划线表示：`_`
- 支持光标在文本中间的显示
- 实时更新光标位置

### 4. 按键处理

实现了完整的按键处理系统：

- **Enter**: 执行命令
- **Backspace/Delete**: 删除字符
- **可打印字符**: 插入字符
- **Ctrl+C**: 中断操作
- **Ctrl+D**: EOF信号

## 技术实现

### 核心类: InputHandler

```python
class InputHandler:
    """处理用户输入并提供实时显示支持"""
    
    def __init__(self):
        self.input_buffer = ""          # 输入缓冲区
        self.cursor_position = 0        # 光标位置
        self.running = False            # 运行状态
        self.input_callback = None      # 输入处理回调
        self.update_callback = None     # 显示更新回调
```

### 关键特性

#### 1. 终端原始模式
```python
def _setup_terminal(self):
    """设置终端为原始模式"""
    if sys.stdin.isatty():
        self.original_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
```

#### 2. 异步按键读取
```python
async def _read_key(self) -> str | None:
    """异步读取单个按键"""
    loop = asyncio.get_event_loop()
    char = await loop.run_in_executor(None, sys.stdin.read, 1)
    return char
```

#### 3. 实时显示更新
```python
def get_input_display(self) -> Text:
    """获取输入显示文本"""
    # 检测命令类型并设置相应样式
    # 显示输入内容和光标位置
    # 返回格式化的Rich Text对象
```

### 集成到增强控制台

#### 1. 布局修改
```python
layout.split_column(
    Layout(name="header", size=3),
    Layout(name="main", ratio=1),
    Layout(name="input", size=3),      # 新增输入区域
    Layout(name="footer", size=3)
)
```

#### 2. 输入处理集成
```python
# 初始化输入处理器
self.input_handler = InputHandler()
self.input_handler.set_input_callback(self._handle_user_input)
self.input_handler.set_update_callback(self._refresh_display_sync)
```

#### 3. 异步处理循环
```python
async def _input_loop(self):
    """输入处理循环（使用增强输入处理器）"""
    try:
        await self.input_handler.start_input_loop()
    except (EOFError, KeyboardInterrupt):
        self.running = False
```

## 兼容性处理

### 回退机制

如果终端不支持原始模式（如非TTY环境），自动回退到传统的行输入模式：

```python
async def _fallback_input_loop(self):
    """回退到传统输入模式"""
    while self.running:
        user_input = await asyncio.get_event_loop().run_in_executor(
            None, input, ""
        )
        # 处理输入...
```

### 终端状态恢复

确保在任何情况下都能正确恢复终端设置：

```python
def _restore_terminal(self):
    """恢复终端设置"""
    if self.original_settings:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.original_settings)
```

## 用户体验提升

### 1. 实时反馈
- 用户可以看到正在输入的内容
- 实时显示命令类型提示
- 光标位置清晰可见

### 2. 视觉指示
- 不同命令类型使用不同颜色
- 清晰的输入提示
- 友好的默认状态显示

### 3. 直观操作
- 支持标准的编辑操作
- 熟悉的快捷键组合
- 流畅的输入体验

## 示例演示

### 输入不同类型的命令

1. **空状态**:
   ```
   > Type a command...
   ```

2. **输入Minecraft命令**:
   ```
   > [Minecraft] /gamemode creative_
   ```

3. **输入Aetherius命令**:
   ```
   > [Aetherius] !status_
   ```

4. **输入系统命令**:
   ```
   > [System] @time_
   ```

5. **光标在中间位置**:
   ```
   > [Minecraft] /game_mode creative
                       ^ 光标位置
   ```

## 性能优化

### 1. 异步处理
- 所有输入处理都是异步的
- 不阻塞UI更新
- 响应速度快

### 2. 高效更新
- 只在需要时更新显示
- 最小化重绘次数
- CPU占用低

### 3. 内存管理
- 输入缓冲区大小合理
- 及时清理资源
- 无内存泄漏

## 错误处理

### 1. 异常恢复
- 捕获所有可能的异常
- 自动恢复终端状态
- 优雅降级处理

### 2. 信号处理
- 正确处理Ctrl+C和Ctrl+D
- 保证资源清理
- 安全退出机制

## 扩展性

### 1. 可配置性
- 易于自定义样式
- 支持添加新的命令前缀
- 可调整显示格式

### 2. 功能扩展
- 支持添加更多快捷键
- 可实现命令历史记录
- 可添加自动补全功能

## 总结

输入状态指示区域的实现显著提升了控制台的用户体验：

1. **可见性**: 用户可以清楚地看到正在输入的内容
2. **实时性**: 输入状态实时更新和显示
3. **智能性**: 自动识别命令类型并提供视觉提示
4. **兼容性**: 支持多种终端环境，有完善的回退机制
5. **稳定性**: 强健的错误处理和资源管理

这个改进让AetheriusMC的控制台界面更加现代化和用户友好，提供了接近IDE级别的输入体验。
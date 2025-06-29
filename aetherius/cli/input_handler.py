"""Enhanced input handler with real-time display support."""

import asyncio
import sys
import termios
import tty
from collections.abc import Awaitable, Callable

from rich.text import Text


class InputHandler:
    """处理用户输入并提供实时显示支持"""

    def __init__(self):
        self.input_buffer = ""
        self.cursor_position = 0
        self.running = False
        self.input_callback: Callable[[str], Awaitable[bool]] | None = None
        self.update_callback: Callable[[], None] | None = None

        # 保存原始终端设置
        self.original_settings = None

    def set_input_callback(self, callback: Callable[[str], Awaitable[bool]]):
        """设置输入处理回调"""
        self.input_callback = callback

    def set_update_callback(self, callback: Callable[[], None]):
        """设置显示更新回调"""
        self.update_callback = callback

    def get_input_display(self) -> Text:
        """获取输入显示文本"""
        text = Text()

        if not self.input_buffer:
            text.append("> ", style="bold blue")
            text.append("Type a command... ", style="dim")
            return text

        # 检测命令类型
        first_char = self.input_buffer[0] if self.input_buffer else ""
        if first_char == "/":
            prefix_style = "bold green"
            type_hint = "[Minecraft] "
        elif first_char == "!":
            prefix_style = "bold yellow"
            type_hint = "[Aetherius] "
        elif first_char == "@":
            prefix_style = "bold cyan"
            type_hint = "[System] "
        elif first_char == "#":
            prefix_style = "bold magenta"
            type_hint = "[Plugin] "
        else:
            prefix_style = "bold green"
            type_hint = "[Minecraft] "

        text.append("> ", style="bold blue")
        text.append(type_hint, style=prefix_style)

        # 显示输入内容，光标位置用下划线表示
        if self.cursor_position == len(self.input_buffer):
            text.append(self.input_buffer, style="white")
            text.append("_", style="white on blue")  # 光标
        else:
            # 在中间位置的光标
            before_cursor = self.input_buffer[: self.cursor_position]
            cursor_char = (
                self.input_buffer[self.cursor_position]
                if self.cursor_position < len(self.input_buffer)
                else " "
            )
            after_cursor = self.input_buffer[self.cursor_position + 1 :]

            text.append(before_cursor, style="white")
            text.append(cursor_char, style="white on blue")
            text.append(after_cursor, style="white")

        return text

    def _setup_terminal(self):
        """设置终端为原始模式"""
        if sys.stdin.isatty():
            self.original_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())

    def _restore_terminal(self):
        """恢复终端设置"""
        if self.original_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.original_settings)

    async def _read_key(self) -> str | None:
        """异步读取单个按键"""
        try:
            if sys.stdin.isatty():
                # 在原始模式下读取单个字符
                loop = asyncio.get_event_loop()
                char = await loop.run_in_executor(None, sys.stdin.read, 1)
                return char
            else:
                # 如果不是TTY，回退到行读取
                return None
        except Exception:
            return None

    def _handle_key(self, key: str) -> bool:
        """处理按键输入，返回是否需要执行命令"""
        if not key:
            return False

        ascii_code = ord(key)

        # 处理特殊键
        if ascii_code == 13:  # Enter
            return True
        elif ascii_code == 127 or ascii_code == 8:  # Backspace/Delete
            if self.cursor_position > 0:
                self.input_buffer = (
                    self.input_buffer[: self.cursor_position - 1]
                    + self.input_buffer[self.cursor_position :]
                )
                self.cursor_position -= 1
        elif ascii_code == 27:  # ESC序列（方向键等）
            # 读取更多字符来处理方向键
            # 这里简化处理，可以后续扩展
            return False
        elif ascii_code == 3:  # Ctrl+C
            raise KeyboardInterrupt()
        elif ascii_code == 4:  # Ctrl+D (EOF)
            raise EOFError()
        elif 32 <= ascii_code <= 126:  # 可打印字符
            self.input_buffer = (
                self.input_buffer[: self.cursor_position]
                + key
                + self.input_buffer[self.cursor_position :]
            )
            self.cursor_position += 1

        # 触发显示更新
        if self.update_callback:
            self.update_callback()

        return False

    async def start_input_loop(self):
        """启动输入循环"""
        self.running = True

        try:
            self._setup_terminal()

            while self.running:
                # 尝试读取按键
                key = await self._read_key()

                if key is None:
                    # 如果无法读取按键，回退到行输入模式
                    await self._fallback_input_loop()
                    break

                try:
                    should_execute = self._handle_key(key)

                    if should_execute:
                        if self.input_buffer.strip():
                            # 执行命令
                            command = self.input_buffer.strip()
                            self.input_buffer = ""
                            self.cursor_position = 0

                            if self.update_callback:
                                self.update_callback()

                            if self.input_callback:
                                await self.input_callback(command)
                                if command.lower() in ("exit", "quit"):
                                    self.running = False
                                    break
                        else:
                            # 空命令，只清空缓冲区
                            self.input_buffer = ""
                            self.cursor_position = 0
                            if self.update_callback:
                                self.update_callback()

                except (KeyboardInterrupt, EOFError):
                    self.running = False
                    break

                # 短暂延迟避免CPU占用过高
                await asyncio.sleep(0.01)

        finally:
            self._restore_terminal()

    async def _fallback_input_loop(self):
        """回退到传统输入模式"""
        while self.running:
            try:
                # 使用传统的行输入
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, ""
                )

                if self.input_callback:
                    await self.input_callback(user_input)
                    if user_input.strip().lower() in ("exit", "quit"):
                        self.running = False
                        break

            except (EOFError, KeyboardInterrupt):
                self.running = False
                break
            except Exception:
                await asyncio.sleep(0.1)

    def stop(self):
        """停止输入处理"""
        self.running = False
        self._restore_terminal()

"""
Console Manager for Aetherius - Updated for Unified Console
Manages console capabilities and provides unified console access
"""

import logging
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

try:
    import termios
    import tty

    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

try:
    import colorama

    colorama.init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

from rich.console import Console


@dataclass
class ConsoleCapabilities:
    """Terminal capabilities detection"""

    has_color: bool = False
    has_unicode: bool = False
    has_raw_mode: bool = False
    is_interactive: bool = False
    width: int = 80
    height: int = 24
    supports_cursor_control: bool = False


def detect_terminal_capabilities() -> dict:
    """Detect terminal capabilities (legacy compatibility)"""
    capabilities = {
        "color_support": False,
        "unicode_support": False,
        "interactive": False,
        "raw_mode": False,
        "size_detection": False,
    }

    # Check if running in an interactive terminal
    capabilities["interactive"] = sys.stdin.isatty() and sys.stdout.isatty()

    # Check color support
    if capabilities["interactive"]:
        # Check TERM environment variable
        term = os.environ.get("TERM", "").lower()
        colorterm = os.environ.get("COLORTERM", "").lower()

        capabilities["color_support"] = (
            "color" in term
            or "256" in term
            or "24bit" in colorterm
            or "truecolor" in colorterm
            or term in ["xterm", "xterm-256color", "screen", "tmux"]
        )

    # Check unicode support
    try:
        encoding = sys.stdout.encoding or "ascii"
        capabilities["unicode_support"] = encoding.lower() in ["utf-8", "utf8"]
    except Exception:
        capabilities["unicode_support"] = False

    # Check raw mode support (needed for enhanced console)
    capabilities["raw_mode"] = (
        capabilities["interactive"] and HAS_TERMIOS and hasattr(sys.stdin, "fileno")
    )

    # Check terminal size detection
    try:
        size = os.get_terminal_size()
        capabilities["size_detection"] = size.columns > 80 and size.lines > 24
    except:
        capabilities["size_detection"] = False

    return capabilities


class ConsoleManager:
    """Manages unified console and provides capability detection"""

    def __init__(self, server_wrapper=None, command_handler: Optional[Callable] = None):
        self.server_wrapper = server_wrapper
        self.command_handler = command_handler
        self.logger = logging.getLogger(__name__)
        self.capabilities = self._detect_capabilities()
        self.selected_console = None
        self.rich_console = Console()

    def _detect_capabilities(self) -> ConsoleCapabilities:
        """Detect terminal capabilities"""
        caps = ConsoleCapabilities()

        # Color support
        caps.has_color = (
            HAS_COLOR
            and os.getenv("TERM", "").lower() not in ("dumb", "")
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )

        # Unicode support
        try:
            # Test unicode character
            test_char = "\u2588"
            print(test_char, end="", flush=True)
            print("\b \b", end="", flush=True)
            caps.has_unicode = True
        except (UnicodeEncodeError, UnicodeError):
            caps.has_unicode = False

        # Raw mode capability
        caps.has_raw_mode = (
            HAS_TERMIOS
            and hasattr(sys.stdin, "fileno")
            and os.isatty(sys.stdin.fileno())
        )

        # Interactive terminal
        caps.is_interactive = (
            hasattr(sys.stdin, "isatty")
            and sys.stdin.isatty()
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )

        # Terminal size
        try:
            size = shutil.get_terminal_size()
            caps.width = size.columns
            caps.height = size.lines
        except:
            caps.width, caps.height = 80, 24

        # Cursor control (basic test)
        caps.supports_cursor_control = caps.is_interactive and caps.has_color

        return caps

    def create_console(self, force_type: Optional[str] = None):
        """Create and return unified console instance"""
        # Legacy compatibility - ignore force_type since we only have unified console
        if force_type:
            self.rich_console.print(
                f"[yellow]Note: Console type '{force_type}' ignored - using unified console[/yellow]"
            )

        try:
            from .unified_console import SimpleConsole

            # 获取运行中的服务器实例
            server_instance = self.server_wrapper
            if not server_instance:
                # 尝试获取全局服务器实例
                try:
                    from .main import get_server_wrapper

                    server_instance = get_server_wrapper()
                    self.rich_console.print("[blue]Connected to running server[/blue]")
                except Exception as e:
                    self.rich_console.print(
                        f"[yellow]No running server found: {e}[/yellow]"
                    )

            console = SimpleConsole(server_instance)
            self.selected_console = console
            self.logger.info("Created simplified unified console")

            self.rich_console.print("[green]Using simplified unified console[/green]")

            return console

        except ImportError as e:
            self.logger.error(f"Failed to import unified console: {e}")
            raise RuntimeError("Unified console implementation not available")
        except Exception as e:
            self.logger.error(f"Failed to create unified console: {e}")
            raise

    def get_capabilities_report(self) -> dict[str, Any]:
        """Get detailed capabilities report"""
        return {
            "capabilities": {
                "color": self.capabilities.has_color,
                "unicode": self.capabilities.has_unicode,
                "raw_mode": self.capabilities.has_raw_mode,
                "interactive": self.capabilities.is_interactive,
                "cursor_control": self.capabilities.supports_cursor_control,
                "terminal_size": f"{self.capabilities.width}x{self.capabilities.height}",
            },
            "environment": {
                "term": os.getenv("TERM", "unknown"),
                "platform": sys.platform,
                "has_termios": HAS_TERMIOS,
                "has_colorama": HAS_COLOR,
            },
            "console_type": "unified",
        }

    def get_capabilities_info(self) -> str:
        """Get terminal capabilities information (legacy compatibility)"""
        caps = detect_terminal_capabilities()

        info = "Terminal Capabilities:\n"
        for cap, supported in caps.items():
            status = "✓" if supported else "✗"
            info += f"  {status} {cap.replace('_', ' ').title()}\n"

        # Add system info
        info += "\nSystem Information:\n"
        info += f"  Platform: {sys.platform}\n"
        info += f"  Python: {sys.version.split()[0]}\n"
        info += f"  Terminal: {os.environ.get('TERM', 'unknown')}\n"

        try:
            size = os.get_terminal_size()
            info += f"  Size: {size.columns}x{size.lines}\n"
        except:
            info += "  Size: unknown\n"

        info += "\nConsole Type: Unified (auto-detecting)\n"

        return info

    def diagnose_issues(self) -> list:
        """Diagnose potential console issues"""
        issues = []

        if not self.capabilities.is_interactive:
            issues.append("Terminal is not interactive - limited functionality")

        if not self.capabilities.has_color:
            issues.append("No color support detected - output will be monochrome")

        if not self.capabilities.has_unicode:
            issues.append("Unicode support issues detected")

        if self.capabilities.width < 80:
            issues.append(
                f"Terminal width ({self.capabilities.width}) is narrow - some features may not display properly"
            )

        if self.capabilities.height < 24:
            issues.append(
                f"Terminal height ({self.capabilities.height}) is short - display may be cramped"
            )

        if not HAS_TERMIOS and sys.platform != "win32":
            issues.append("termios module not available - raw input mode disabled")

        return issues

    def show_console_info(self):
        """Display console information and capabilities"""
        self.rich_console.print("[cyan]Aetherius Console Manager[/cyan]")
        self.rich_console.print(
            "[yellow]Console Type:[/yellow] Unified (with automatic mode detection)"
        )
        self.rich_console.print("[yellow]Capabilities:[/yellow]")
        self.rich_console.print(
            f"  Color Support: {'[green]✓[/green]' if self.capabilities.has_color else '[red]✗[/red]'}"
        )
        self.rich_console.print(
            f"  Unicode Support: {'[green]✓[/green]' if self.capabilities.has_unicode else '[red]✗[/red]'}"
        )
        self.rich_console.print(
            f"  Raw Mode: {'[green]✓[/green]' if self.capabilities.has_raw_mode else '[red]✗[/red]'}"
        )
        self.rich_console.print(
            f"  Interactive: {'[green]✓[/green]' if self.capabilities.is_interactive else '[red]✗[/red]'}"
        )
        self.rich_console.print(
            f"  Terminal Size: {self.capabilities.width}x{self.capabilities.height}"
        )

        issues = self.diagnose_issues()
        if issues:
            self.rich_console.print("\n[yellow]Potential Issues:[/yellow]")
            for issue in issues:
                self.rich_console.print(f"  [yellow]⚠[/yellow] {issue}")
        else:
            self.rich_console.print("\n[green]✓ No issues detected[/green]")


def should_use_enhanced_console() -> bool:
    """Determine if enhanced console should be used (legacy compatibility)"""
    caps = detect_terminal_capabilities()

    # Enhanced console requirements
    return (
        caps["interactive"]
        and caps["color_support"]
        and caps["raw_mode"]
        and caps["size_detection"]
    )


def get_console_manager() -> ConsoleManager:
    """Get or create console manager instance"""
    if not hasattr(get_console_manager, "_instance"):
        get_console_manager._instance = ConsoleManager()
    return get_console_manager._instance


def create_console(server_manager=None):
    """Convenience function to create unified console"""
    manager = get_console_manager()
    return manager.create_console(server_manager)


def get_capabilities() -> dict[str, Any]:
    """Get terminal capabilities report"""
    manager = get_console_manager()
    return manager.get_capabilities_report()


def diagnose_console() -> list:
    """Diagnose console issues"""
    manager = get_console_manager()
    return manager.diagnose_issues()


def show_console_info():
    """Show console information"""
    manager = get_console_manager()
    manager.show_console_info()


async def start_console(
    server_wrapper,
    command_handler: Callable | None = None,
    console_type: str | None = None,
) -> None:
    """Start the unified console (updated for unified console)"""
    manager = ConsoleManager(server_wrapper, command_handler)

    # Show capabilities if requested
    if console_type == "info":
        console = Console()
        console.print(manager.get_capabilities_info())
        return

    try:
        # Create and start simplified console
        console_instance = manager.create_console(console_type)
        console_instance.run()

    except KeyboardInterrupt:
        console = Console()
        console.print("\n[yellow]Console interrupted by user[/yellow]")
    except Exception as e:
        console = Console()
        console.print(f"[red]Console error: {e}[/red]")
        console.print(
            "[yellow]The simplified console handles all functionality automatically[/yellow]"
        )

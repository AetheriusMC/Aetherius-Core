#!/usr/bin/env python3
"""
Unified Aetherius Console - Consolidated console with progressive enhancement
Combines all console features with automatic capability detection and fallback
"""

import logging
import os
import readline
import shutil
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional

try:
    import termios
    import tty

    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

try:
    import colorama
    from colorama import Back, Fore, Style

    colorama.init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

    # Fallback color constants
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""

    class Back:
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""

    class Style:
        DIM = NORMAL = BRIGHT = RESET_ALL = ""


class ConsoleMode(Enum):
    """Console operating modes"""

    ENHANCED = auto()  # Full features with raw terminal
    STANDARD = auto()  # Standard features with readline
    FALLBACK = auto()  # Basic compatibility mode


class CommandType(Enum):
    """Command type indicators"""

    MINECRAFT = "/"  # Minecraft server commands
    AETHERIUS = "!"  # Aetherius system commands
    PLUGIN = "@"  # Plugin management commands
    SCRIPT = "#"  # Script execution commands
    ADMIN = "&"  # Admin/operator commands
    CHAT = ""  # Default chat message


@dataclass
class TerminalCapabilities:
    """Terminal capability detection results"""

    has_color: bool = False
    has_unicode: bool = False
    has_raw_mode: bool = False
    is_interactive: bool = False
    width: int = 80
    height: int = 24


@dataclass
class ConsoleState:
    """Console state tracking"""

    start_time: datetime
    commands_executed: int = 0
    events_received: int = 0
    current_input: str = ""
    cursor_pos: int = 0
    history_index: int = -1
    is_running: bool = False


class FeedbackLogger:
    """Centralized logging and feedback system"""

    def __init__(self, console_name: str = "Aetherius"):
        self.console_name = console_name
        self.setup_logging()

    def setup_logging(self):
        """Setup file-only logging system"""
        # Create a unique logger to avoid conflicts
        self.logger = logging.getLogger(f"aetherius_console_{id(self)}")
        self.logger.handlers = []  # Clear any existing handlers

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        # File handler only - no console output
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler(
            f"logs/{self.console_name.lower()}_console.log"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)

        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

    def command_feedback(
        self, command: str, result: str = "executed", status: str = "success"
    ):
        """Log command execution with clean feedback"""
        color = Fore.GREEN if status == "success" else Fore.RED
        print(f"{color}✓{Style.RESET_ALL} {command}")
        self.logger.info(f"Command {status}: {command} -> {result}")

    def system_feedback(self, message: str, level: str = "info"):
        """System status feedback - file logging only"""
        log_level = "info" if level == "success" else level
        getattr(self.logger, log_level)(f"System: {message}")

    def event_feedback(self, event_type: str, message: str):
        """Event notification feedback"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.BLUE}[{timestamp}]{Style.RESET_ALL} {message}")
        self.logger.info(f"Event {event_type}: {message}")


class UnifiedConsole:
    """Unified console with progressive enhancement and comprehensive feedback"""

    def __init__(self, server_manager=None):
        self.server_manager = server_manager
        self.capabilities = self._detect_capabilities()
        self.mode = self._determine_mode()
        self.state = ConsoleState(start_time=datetime.now())
        self.feedback = FeedbackLogger("Aetherius")

        # Command history and completion
        self.command_history: list[str] = []
        self.completion_cache: dict[str, list[str]] = {}

        # Threading for non-blocking input
        self.input_thread: Optional[threading.Thread] = None
        self.display_lock = threading.Lock()

        # Terminal state management
        self.original_termios = None
        self.in_raw_mode = False

        self._setup_console()

        # Clean startup message
        if self.capabilities.has_color:
            print(
                f"{Fore.GREEN}✓ Aetherius Console ready{Style.RESET_ALL} ({self.mode.name.lower()} mode)"
            )
        else:
            print(f"✓ Aetherius Console ready ({self.mode.name.lower()} mode)")

        self.feedback.system_feedback(
            f"Console initialized in {self.mode.name} mode", "success"
        )

    def _detect_capabilities(self) -> TerminalCapabilities:
        """Comprehensive terminal capability detection"""
        caps = TerminalCapabilities()

        # Color support detection
        caps.has_color = (
            HAS_COLOR
            and os.getenv("TERM", "").lower() not in ("dumb", "")
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )

        # Unicode support detection
        try:
            print("\u2588", end="", flush=True)
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

        # Interactive terminal detection
        caps.is_interactive = (
            hasattr(sys.stdin, "isatty")
            and sys.stdin.isatty()
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
        )

        # Terminal size detection
        try:
            size = shutil.get_terminal_size()
            caps.width = size.columns
            caps.height = size.lines
        except:
            caps.width, caps.height = 80, 24

        return caps

    def _determine_mode(self) -> ConsoleMode:
        """Determine optimal console mode based on capabilities"""
        if (
            self.capabilities.has_raw_mode
            and self.capabilities.is_interactive
            and self.capabilities.width >= 80
        ):
            return ConsoleMode.ENHANCED
        elif self.capabilities.is_interactive:
            return ConsoleMode.STANDARD
        else:
            return ConsoleMode.FALLBACK

    def _setup_console(self):
        """Setup console based on detected mode"""
        if self.mode == ConsoleMode.ENHANCED:
            self._setup_enhanced_mode()
        elif self.mode == ConsoleMode.STANDARD:
            self._setup_standard_mode()
        else:
            self._setup_fallback_mode()

        # Setup command completion
        self._setup_completion()

    def _setup_enhanced_mode(self):
        """Setup enhanced mode with raw terminal"""
        try:
            if HAS_TERMIOS and sys.stdin.isatty():
                self.original_termios = termios.tcgetattr(sys.stdin.fileno())
                tty.setraw(sys.stdin.fileno())
                self.in_raw_mode = True
        except Exception:
            # Silently fall back to standard mode
            self.mode = ConsoleMode.STANDARD
            self._setup_standard_mode()

    def _setup_standard_mode(self):
        """Setup standard mode with readline"""
        try:
            readline.parse_and_bind("tab: complete")
            readline.set_completer(self._tab_completer)
        except Exception:
            pass
            # Silently fall back to fallback mode
            self.mode = ConsoleMode.FALLBACK
            self._setup_fallback_mode()

    def _setup_fallback_mode(self):
        """Setup basic fallback mode"""
        pass  # Nothing special needed for fallback mode

    def _setup_completion(self):
        """Setup command completion system with categorized commands"""
        # Minecraft server commands
        minecraft_commands = [
            "/help",
            "/stop",
            "/restart",
            "/reload",
            "/save-all",
            "/save-on",
            "/save-off",
            "/list",
            "/players",
            "/ban",
            "/unban",
            "/ban-ip",
            "/unban-ip",
            "/pardon",
            "/op",
            "/deop",
            "/kick",
            "/whitelist",
            "/gamemode",
            "/difficulty",
            "/time",
            "/weather",
            "/tp",
            "/teleport",
            "/give",
            "/clear",
            "/kill",
            "/say",
            "/tell",
            "/msg",
            "/me",
            "/seed",
            "/spawnpoint",
            "/setworldspawn",
            "/gamerule",
            "/worldborder",
            "/fill",
            "/clone",
            "/setblock",
            "/summon",
        ]

        # Aetherius system commands
        aetherius_commands = [
            "!status",
            "!quit",
            "!exit",
            "!help",
            "!clear",
            "!logs",
            "!backup",
            "!update",
            "!restart",
            "!config",
            "!debug",
            "!monitor",
            "!stats",
            "!memory",
            "!performance",
            "!console",
            "!version",
            "!uptime",
        ]

        # Plugin management commands
        plugin_commands = [
            "@list",
            "@enable",
            "@disable",
            "@reload",
            "@info",
            "@load",
            "@unload",
            "@update",
            "@install",
            "@remove",
            "@search",
            "@config",
            "@help",
        ]

        # Script execution commands
        script_commands = [
            "#run",
            "#list",
            "#stop",
            "#schedule",
            "#status",
            "#edit",
            "#create",
            "#delete",
            "#logs",
            "#help",
            "#backup",
            "#restore",
        ]

        # Admin/operator commands
        admin_commands = [
            "&promote",
            "&demote",
            "&permissions",
            "&groups",
            "&users",
            "&audit",
            "&security",
            "&maintenance",
            "&emergency",
            "&lockdown",
            "&unlock",
        ]

        # Combine all commands
        all_commands = (
            minecraft_commands
            + aetherius_commands
            + plugin_commands
            + script_commands
            + admin_commands
        )

        self.completion_cache["base"] = all_commands
        self.completion_cache["minecraft"] = minecraft_commands
        self.completion_cache["aetherius"] = aetherius_commands
        self.completion_cache["plugin"] = plugin_commands
        self.completion_cache["script"] = script_commands
        self.completion_cache["admin"] = admin_commands

        # Log to file only
        self.feedback.system_feedback(
            f"Loaded {len(all_commands)} commands for completion", "info"
        )

    def _tab_completer(self, text: str, state: int) -> str | None:
        """Tab completion handler"""
        if state == 0:
            # Generate completion options
            self._completion_options = []

            # Get base commands
            base_commands = self.completion_cache.get("base", [])

            # Filter matching commands
            matches = [cmd for cmd in base_commands if cmd.startswith(text)]
            self._completion_options = matches

        try:
            return self._completion_options[state]
        except IndexError:
            return None

    def _parse_command_type(self, command: str) -> tuple[CommandType, str]:
        """Parse command to determine type and extract content"""
        if not command:
            return CommandType.CHAT, ""

        first_char = command[0]
        for cmd_type in CommandType:
            if first_char == cmd_type.value:
                return cmd_type, command[1:].strip()

        return CommandType.CHAT, command

    def _display_header(self):
        """Display console header with status"""
        if not self.capabilities.has_color:
            print("=" * 60)
            print(
                f"Aetherius Console [{self.mode.name}] - {datetime.now().strftime('%H:%M:%S')}"
            )
            print("=" * 60)
            return

        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(
            f"{Fore.GREEN}🔷 Aetherius Console {Fore.CYAN}[{self.mode.name}]{Style.RESET_ALL}"
        )
        print(
            f"{Fore.YELLOW}📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}"
        )

        uptime = datetime.now() - self.state.start_time
        print(
            f"{Fore.BLUE}⏱️  Uptime: {str(uptime).split('.')[0]} | "
            f"Commands: {self.state.commands_executed} | "
            f"Events: {self.state.events_received}{Style.RESET_ALL}"
        )
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

    def _display_events(self, events: list[str]):
        """Display recent events with timestamps"""
        if not events:
            return

        print(f"{Fore.MAGENTA}📋 Recent Events:{Style.RESET_ALL}")
        for event in events[-5:]:  # Show last 5 events
            print(f"  {event}")
        print()

    def _display_input_prompt(self):
        """Display input prompt with current input"""
        prompt = f"{Fore.GREEN}Aetherius> {Style.RESET_ALL}"

        if self.mode == ConsoleMode.ENHANCED and self.state.current_input:
            # Show current input with cursor
            cursor_pos = self.state.cursor_pos
            input_text = self.state.current_input

            if cursor_pos < len(input_text):
                display_text = (
                    input_text[:cursor_pos]
                    + f"{Back.WHITE}{Fore.BLACK}{input_text[cursor_pos]}{Style.RESET_ALL}"
                    + input_text[cursor_pos + 1 :]
                )
            else:
                display_text = input_text + f"{Back.WHITE} {Style.RESET_ALL}"

            print(f"{prompt}{display_text}", end="", flush=True)
        else:
            print(prompt, end="", flush=True)

    def _handle_enhanced_input(self) -> str:
        """Handle input in enhanced mode with real-time feedback"""
        self.state.current_input = ""
        self.state.cursor_pos = 0

        while True:
            try:
                char = sys.stdin.read(1)

                if ord(char) == 13:  # Enter
                    print()  # New line
                    result = self.state.current_input
                    self.state.current_input = ""
                    self.state.cursor_pos = 0
                    return result

                elif ord(char) == 127:  # Backspace
                    if self.state.cursor_pos > 0:
                        self.state.current_input = (
                            self.state.current_input[: self.state.cursor_pos - 1]
                            + self.state.current_input[self.state.cursor_pos :]
                        )
                        self.state.cursor_pos -= 1

                elif ord(char) == 27:  # Escape sequence
                    next_char = sys.stdin.read(1)
                    if next_char == "[":
                        arrow_key = sys.stdin.read(1)
                        if arrow_key == "A":  # Up arrow
                            self._handle_history_up()
                        elif arrow_key == "B":  # Down arrow
                            self._handle_history_down()
                        elif arrow_key == "C":  # Right arrow
                            if self.state.cursor_pos < len(self.state.current_input):
                                self.state.cursor_pos += 1
                        elif arrow_key == "D":  # Left arrow
                            if self.state.cursor_pos > 0:
                                self.state.cursor_pos -= 1

                elif ord(char) == 9:  # Tab
                    self._handle_tab_completion()

                elif ord(char) >= 32 and ord(char) <= 126:  # Printable characters
                    self.state.current_input = (
                        self.state.current_input[: self.state.cursor_pos]
                        + char
                        + self.state.current_input[self.state.cursor_pos :]
                    )
                    self.state.cursor_pos += 1

                # Refresh display
                print("\r\033[K", end="")  # Clear line
                self._display_input_prompt()

            except KeyboardInterrupt:
                print("\n^C")
                return "!quit"
            except EOFError:
                print("\nEOF")
                return "!quit"

    def _handle_standard_input(self) -> str:
        """Handle input in standard mode with readline"""
        try:
            prompt = (
                f"{Fore.GREEN}Aetherius> {Style.RESET_ALL}"
                if self.capabilities.has_color
                else "Aetherius> "
            )
            return input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            return "!quit"

    def _handle_fallback_input(self) -> str:
        """Handle input in fallback mode"""
        try:
            command = input("Aetherius> ").strip()
            return command
        except (KeyboardInterrupt, EOFError):
            print()  # New line after Ctrl+C
            return "!quit"

    def _handle_history_up(self):
        """Handle command history navigation up"""
        if (
            self.command_history
            and self.state.history_index < len(self.command_history) - 1
        ):
            self.state.history_index += 1
            self.state.current_input = self.command_history[
                -(self.state.history_index + 1)
            ]
            self.state.cursor_pos = len(self.state.current_input)

    def _handle_history_down(self):
        """Handle command history navigation down"""
        if self.state.history_index > 0:
            self.state.history_index -= 1
            self.state.current_input = self.command_history[
                -(self.state.history_index + 1)
            ]
            self.state.cursor_pos = len(self.state.current_input)
        elif self.state.history_index == 0:
            self.state.history_index = -1
            self.state.current_input = ""
            self.state.cursor_pos = 0

    def _handle_tab_completion(self):
        """Handle tab completion"""
        if not self.state.current_input:
            return

        # Simple completion for now
        matches = [
            cmd
            for cmd in self.completion_cache.get("base", [])
            if cmd.startswith(self.state.current_input)
        ]

        if matches:
            if len(matches) == 1:
                self.state.current_input = matches[0]
                self.state.cursor_pos = len(self.state.current_input)
            else:
                # Show options
                print(
                    f"\n{Fore.CYAN}Options: {', '.join(matches[:10])}{Style.RESET_ALL}"
                )

    def execute_command(self, command: str):
        """Execute command with comprehensive feedback"""
        if not command:
            return

        # Add to history
        if (
            command not in self.command_history[-5:]
        ):  # Avoid duplicates in recent history
            self.command_history.append(command)
            if len(self.command_history) > 100:  # Limit history size
                self.command_history = self.command_history[-100:]

        # Parse command type
        cmd_type, cmd_content = self._parse_command_type(command)

        # Update statistics
        self.state.commands_executed += 1

        # Execute based on type
        try:
            if cmd_type == CommandType.AETHERIUS:
                self._execute_aetherius_command(cmd_content)
            elif cmd_type == CommandType.MINECRAFT:
                self._execute_minecraft_command(cmd_content)
            elif cmd_type == CommandType.PLUGIN:
                self._execute_plugin_command(cmd_content)
            elif cmd_type == CommandType.SCRIPT:
                self._execute_script_command(cmd_content)
            elif cmd_type == CommandType.ADMIN:
                self._execute_admin_command(cmd_content)
            else:
                self._execute_chat_command(command)

            # Don't show success message for quit commands
            if not (
                cmd_type == CommandType.AETHERIUS and cmd_content in ["quit", "exit"]
            ):
                self.feedback.command_feedback(
                    command, f"completed [{cmd_type.name}]", "success"
                )

        except Exception as e:
            print(f"{Fore.RED}✗ Error: {e}{Style.RESET_ALL}")
            self.feedback.command_feedback(command, f"failed: {e}", "error")

    def _execute_aetherius_command(self, command: str):
        """Execute Aetherius system commands with feedback"""
        if command in ["quit", "exit"]:
            print(f"{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
            self.state.is_running = False
            return
        elif command == "status":
            self._show_system_status()
        elif command == "help":
            self._show_help()
        elif command == "clear":
            os.system("clear" if os.name == "posix" else "cls")
        elif command == "version":
            self.feedback.system_feedback(
                "Aetherius Console v1.0 - Unified Edition", "info"
            )
        elif command == "uptime":
            uptime = datetime.now() - self.state.start_time
            self.feedback.system_feedback(
                f"Console uptime: {str(uptime).split('.')[0]}", "info"
            )
        elif command == "stats":
            self.feedback.system_feedback(
                f"Commands: {self.state.commands_executed}, Events: {self.state.events_received}",
                "info",
            )
        elif command == "config":
            self.feedback.system_feedback(
                "Configuration management not yet implemented", "warning"
            )
        elif command == "logs":
            self.feedback.system_feedback("Log viewer not yet implemented", "warning")
        elif command == "backup":
            self.feedback.system_feedback(
                "Backup system not yet implemented", "warning"
            )
        elif command == "debug":
            self._show_debug_info()
        else:
            self.feedback.system_feedback(
                f"Unknown Aetherius command: {command}", "warning"
            )

    def _execute_minecraft_command(self, command: str):
        """Execute Minecraft server commands with feedback"""
        if self.server_manager:
            result = self.server_manager.execute_command(command)
            print(f"{Fore.GREEN}→{Style.RESET_ALL} Minecraft: /{command}")
        else:
            print(f"{Fore.YELLOW}→{Style.RESET_ALL} No server (would run: /{command})")

    def _execute_plugin_command(self, command: str):
        """Execute plugin commands with feedback"""
        print(f"{Fore.MAGENTA}→{Style.RESET_ALL} Plugin: @{command}")

    def _execute_admin_command(self, command: str):
        """Execute admin/operator commands with feedback"""
        print(f"{Fore.RED}→{Style.RESET_ALL} Admin: &{command}")

    def _execute_script_command(self, command: str):
        """Execute script commands with feedback"""
        if command == "list":
            print(
                f"{Fore.CYAN}Available scripts:{Style.RESET_ALL} backup.py, maintenance.py, stats.py"
            )
        else:
            print(f"{Fore.CYAN}→{Style.RESET_ALL} Script: #{command}")

    def _execute_chat_command(self, message: str):
        """Execute chat commands with feedback"""
        if self.server_manager:
            self.server_manager.send_chat(message)
            print(f"{Fore.BLUE}💬{Style.RESET_ALL} {message}")
        else:
            print(f"{Fore.YELLOW}💬{Style.RESET_ALL} No server (would send: {message})")

    def _show_system_status(self):
        """Display comprehensive system status"""
        uptime = datetime.now() - self.state.start_time

        print(f"\n{Fore.CYAN}System Status:{Style.RESET_ALL}")
        print(f"  Console Mode: {self.mode.name}")
        print(f"  Uptime: {str(uptime).split('.')[0]}")
        print(f"  Commands Executed: {self.state.commands_executed}")
        print(f"  Events Received: {self.state.events_received}")
        print(f"  Terminal Size: {self.capabilities.width}x{self.capabilities.height}")
        print(
            f"  Capabilities: Color={self.capabilities.has_color}, "
            f"Unicode={self.capabilities.has_unicode}, "
            f"RawMode={self.capabilities.has_raw_mode}"
        )

        if self.server_manager:
            print("  Server Status: Connected")
        else:
            print("  Server Status: Not connected")
        print()

    def _show_help(self):
        """Display help information"""
        help_text = f"""
{Fore.CYAN}Aetherius Unified Console Help{Style.RESET_ALL}

{Fore.YELLOW}Command Categories & Prefixes:{Style.RESET_ALL}
  {Fore.GREEN}/  - Minecraft commands{Style.RESET_ALL} (e.g., /help, /stop, /players, /gamemode)
  {Fore.BLUE}!  - Aetherius commands{Style.RESET_ALL} (e.g., !status, !quit, !debug, !logs)
  {Fore.MAGENTA}@  - Plugin commands{Style.RESET_ALL} (e.g., @list, @enable, @disable)
  {Fore.CYAN}#  - Script commands{Style.RESET_ALL} (e.g., #run, #list, #schedule)
  {Fore.RED}&  - Admin commands{Style.RESET_ALL} (e.g., &promote, &permissions, &security)
  {Fore.WHITE}   - Chat messages{Style.RESET_ALL} (direct text without prefix)

{Fore.YELLOW}Aetherius Commands:{Style.RESET_ALL}
  !help      - Show this help
  !status    - Show system status
  !quit/exit - Exit console
  !clear     - Clear screen
  !version   - Show version info
  !uptime    - Show console uptime
  !stats     - Show statistics
  !debug     - Show debug information

{Fore.YELLOW}Minecraft Commands:{Style.RESET_ALL}
  /help      - Minecraft help
  /stop      - Stop server
  /list      - List players
  /op <user> - Make user operator
  /gamemode <mode> <player> - Change gamemode

{Fore.YELLOW}Navigation:{Style.RESET_ALL}
  ↑/↓ Arrow keys - Command history
  Tab - Command completion
  Ctrl+C - Interrupt/quit

{Fore.YELLOW}Console Modes:{Style.RESET_ALL}
  Enhanced - Full features with real-time input
  Standard - Standard features with readline
  Fallback - Basic compatibility mode

{Fore.YELLOW}Current Mode: {Fore.WHITE}{self.mode.name}{Style.RESET_ALL}
"""
        print(help_text)

    def _show_debug_info(self):
        """Display debug information"""
        print(f"\n{Fore.CYAN}Debug Information:{Style.RESET_ALL}")
        print(f"  Console Mode: {self.mode.name}")
        print("  Terminal Capabilities:")
        print(f"    Color Support: {self.capabilities.has_color}")
        print(f"    Unicode Support: {self.capabilities.has_unicode}")
        print(f"    Raw Mode: {self.capabilities.has_raw_mode}")
        print(f"    Interactive: {self.capabilities.is_interactive}")
        print(f"    Size: {self.capabilities.width}x{self.capabilities.height}")
        print("  State:")
        print(f"    Running: {self.state.is_running}")
        print(f"    Commands Executed: {self.state.commands_executed}")
        print(f"    Events Received: {self.state.events_received}")
        print(f"    History Length: {len(self.command_history)}")
        print("  Completion Cache:")
        for category, commands in self.completion_cache.items():
            print(f"    {category}: {len(commands)} commands")
        print()

    def handle_event(self, event_type: str, data: Any):
        """Handle server events with feedback"""
        self.state.events_received += 1

        # Format event message
        timestamp = datetime.now().strftime("%H:%M:%S")

        if event_type == "player_join":
            message = f"Player {data.get('player', 'Unknown')} joined"
        elif event_type == "player_leave":
            message = f"Player {data.get('player', 'Unknown')} left"
        elif event_type == "chat":
            player = data.get("player", "Unknown")
            msg = data.get("message", "")
            message = f"<{player}> {msg}"
        elif event_type == "server_log":
            message = data.get("message", str(data))
        else:
            message = f"{event_type}: {data}"

        self.feedback.event_feedback(event_type.upper(), message)

    def cleanup(self):
        """Cleanup console resources"""
        try:
            if self.in_raw_mode and self.original_termios:
                termios.tcsetattr(
                    sys.stdin.fileno(), termios.TCSADRAIN, self.original_termios
                )
                self.in_raw_mode = False

            if self.input_thread and self.input_thread.is_alive():
                self.input_thread.join(timeout=1.0)

            self.feedback.system_feedback("Console cleanup completed", "success")

        except Exception as e:
            self.feedback.system_feedback(f"Cleanup error: {e}", "warning")

    def run(self):
        """Main console loop with clean output"""
        self.state.is_running = True

        # Show simple startup message
        print(f"{Fore.CYAN}Type !help for commands or !quit to exit{Style.RESET_ALL}")

        try:
            while self.state.is_running:
                # Clear screen and show header (enhanced mode only)
                if self.mode == ConsoleMode.ENHANCED:
                    os.system("clear" if os.name == "posix" else "cls")
                    self._display_header()

                # Get input based on mode
                try:
                    if self.mode == ConsoleMode.ENHANCED:
                        command = self._handle_enhanced_input()
                    elif self.mode == ConsoleMode.STANDARD:
                        command = self._handle_standard_input()
                    else:
                        command = self._handle_fallback_input()

                    # Execute command
                    if command and command.strip():
                        self.execute_command(command.strip())

                except (KeyboardInterrupt, EOFError):
                    print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
                    break

        except Exception as e:
            print(f"\n{Fore.RED}Console error: {e}{Style.RESET_ALL}")
        finally:
            self.cleanup()


def main():
    """Console entry point for testing"""
    console = UnifiedConsole()
    console.run()


if __name__ == "__main__":
    main()

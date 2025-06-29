"""
Aetherius服务器管理扩展
=====================

为Web组件提供的服务器管理功能扩展
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import psutil

from .server import ServerProcessWrapper

logger = logging.getLogger(__name__)


@dataclass
class ServerPerformanceMetrics:
    """服务器性能指标"""

    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_usage_mb: float
    network_sent_mb: float
    network_recv_mb: float
    thread_count: int
    file_descriptors: int
    uptime_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class ServerStatus:
    """服务器状态信息"""

    is_running: bool
    is_starting: bool
    is_stopping: bool
    start_time: Optional[datetime]
    uptime_seconds: float
    player_count: int
    max_players: int
    tps: float
    version: str
    world_name: str
    difficulty: str
    game_mode: str
    view_distance: int
    simulation_distance: int

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data["start_time"] = self.start_time.isoformat() if self.start_time else None
        return data


@dataclass
class PlayerInfo:
    """玩家信息"""

    name: str
    uuid: str
    ip_address: str
    join_time: datetime
    last_activity: datetime
    location: dict[str, float]
    health: float
    food_level: int
    experience_level: int
    game_mode: str

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data["join_time"] = self.join_time.isoformat()
        data["last_activity"] = self.last_activity.isoformat()
        return data


class ServerManagerExtensions:
    """服务器管理器扩展类"""

    def __init__(self, server_wrapper: ServerProcessWrapper):
        """
        初始化服务器管理扩展

        Args:
            server_wrapper: 服务器进程包装器
        """
        self.server_wrapper = server_wrapper
        self.config = server_wrapper.config

        # 性能监控
        self._performance_history: list[ServerPerformanceMetrics] = []
        self._max_history_entries = 1000
        self._monitoring_interval = 30  # 秒
        self._monitoring_task: Optional[asyncio.Task] = None

        # 状态缓存
        self._cached_status: Optional[ServerStatus] = None
        self._status_cache_time: Optional[datetime] = None
        self._status_cache_ttl = 5  # 秒

        # 玩家管理
        self._online_players: dict[str, PlayerInfo] = {}
        self._player_history: list[dict[str, Any]] = []

        # 命令历史
        self._command_history: list[dict[str, Any]] = []
        self._max_command_history = 500

        # 事件回调
        self._status_change_callbacks: list[Callable] = []
        self._performance_callbacks: list[Callable] = []

        # 自动备份
        self._backup_enabled = False
        self._backup_interval = 3600  # 1小时
        self._backup_task: Optional[asyncio.Task] = None

        logger.info("Server manager extensions initialized")

    async def start_monitoring(self):
        """开始性能监控"""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Monitoring already running")
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Performance monitoring started")

    async def stop_monitoring(self):
        """停止性能监控"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

        logger.info("Performance monitoring stopped")

    async def _monitoring_loop(self):
        """监控循环"""
        while True:
            try:
                if self.server_wrapper.is_alive:
                    metrics = await self._collect_performance_metrics()
                    if metrics:
                        self._performance_history.append(metrics)

                        # 限制历史记录大小
                        if len(self._performance_history) > self._max_history_entries:
                            self._performance_history.pop(0)

                        # 通知回调函数
                        for callback in self._performance_callbacks:
                            try:
                                await callback(metrics)
                            except Exception as e:
                                logger.error(f"Error in performance callback: {e}")

                await asyncio.sleep(self._monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self._monitoring_interval)

    async def _collect_performance_metrics(self) -> Optional[ServerPerformanceMetrics]:
        """收集性能指标"""
        try:
            if not self.server_wrapper.process:
                return None

            pid = self.server_wrapper.process.pid
            process = psutil.Process(pid)

            # CPU和内存
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            memory_percent = process.memory_percent()

            # 磁盘使用（服务器目录）
            server_dir = Path(self.config.server_directory)
            disk_usage = 0
            if server_dir.exists():
                for file_path in server_dir.rglob("*"):
                    if file_path.is_file():
                        disk_usage += file_path.stat().st_size
            disk_usage_mb = disk_usage / 1024 / 1024

            # 网络信息
            network_io = process.io_counters()
            network_sent_mb = network_io.write_bytes / 1024 / 1024
            network_recv_mb = network_io.read_bytes / 1024 / 1024

            # 线程和文件描述符
            thread_count = process.num_threads()
            file_descriptors = process.num_fds() if hasattr(process, "num_fds") else 0

            # 运行时间
            uptime_seconds = time.time() - process.create_time()

            return ServerPerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                memory_percent=memory_percent,
                disk_usage_mb=disk_usage_mb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                thread_count=thread_count,
                file_descriptors=file_descriptors,
                uptime_seconds=uptime_seconds,
            )

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return None

    async def get_server_status(self, use_cache: bool = True) -> ServerStatus:
        """
        获取服务器状态

        Args:
            use_cache: 是否使用缓存

        Returns:
            服务器状态对象
        """
        now = datetime.now()

        # 检查缓存
        if (
            use_cache
            and self._cached_status
            and self._status_cache_time
            and (now - self._status_cache_time).total_seconds() < self._status_cache_ttl
        ):
            return self._cached_status

        try:
            # 基本状态
            is_running = self.server_wrapper.is_alive
            is_starting = (
                hasattr(self.server_wrapper, "_starting")
                and self.server_wrapper._starting
            )
            is_stopping = (
                hasattr(self.server_wrapper, "_stopping")
                and self.server_wrapper._stopping
            )

            start_time = None
            uptime_seconds = 0
            if self.server_wrapper.start_time:
                start_time = datetime.fromtimestamp(self.server_wrapper.start_time)
                uptime_seconds = time.time() - self.server_wrapper.start_time

            # 从服务器状态获取信息
            player_count = len(self._online_players)
            max_players = (
                self.config.max_players if hasattr(self.config, "max_players") else 20
            )

            # 从服务器属性获取信息
            server_properties = await self._read_server_properties()

            status = ServerStatus(
                is_running=is_running,
                is_starting=is_starting,
                is_stopping=is_stopping,
                start_time=start_time,
                uptime_seconds=uptime_seconds,
                player_count=player_count,
                max_players=max_players,
                tps=20.0,  # 默认值，需要从服务器获取实际TPS
                version=server_properties.get("version", "Unknown"),
                world_name=server_properties.get("level-name", "world"),
                difficulty=server_properties.get("difficulty", "normal"),
                game_mode=server_properties.get("gamemode", "survival"),
                view_distance=int(server_properties.get("view-distance", 10)),
                simulation_distance=int(
                    server_properties.get("simulation-distance", 10)
                ),
            )

            # 更新缓存
            self._cached_status = status
            self._status_cache_time = now

            return status

        except Exception as e:
            logger.error(f"Error getting server status: {e}")
            # 返回默认状态
            return ServerStatus(
                is_running=False,
                is_starting=False,
                is_stopping=False,
                start_time=None,
                uptime_seconds=0,
                player_count=0,
                max_players=20,
                tps=0.0,
                version="Unknown",
                world_name="world",
                difficulty="normal",
                game_mode="survival",
                view_distance=10,
                simulation_distance=10,
            )

    async def _read_server_properties(self) -> dict[str, str]:
        """读取服务器属性文件"""
        try:
            properties_file = Path(self.config.server_directory) / "server.properties"
            if not properties_file.exists():
                return {}

            properties = {}
            with open(properties_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        properties[key.strip()] = value.strip()

            return properties

        except Exception as e:
            logger.error(f"Error reading server properties: {e}")
            return {}

    async def execute_command_with_result(
        self, command: str, timeout: float = 30.0
    ) -> dict[str, Any]:
        """
        执行命令并等待结果

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）

        Returns:
            命令执行结果
        """
        if not self.server_wrapper.is_alive:
            return {
                "success": False,
                "error": "Server is not running",
                "output": "",
                "execution_time": 0,
            }

        start_time = time.time()

        try:
            # 通过命令队列执行命令
            command_id = self.server_wrapper.command_queue.add_command(command)
            result = await self.server_wrapper.command_queue.wait_for_completion(
                command_id, timeout
            )

            execution_time = time.time() - start_time

            # 记录命令历史
            command_record = {
                "timestamp": datetime.now().isoformat(),
                "command": command,
                "result": result,
                "execution_time": execution_time,
            }

            self._command_history.append(command_record)
            if len(self._command_history) > self._max_command_history:
                self._command_history.pop(0)

            return {
                "success": result.get("status") == "completed",
                "error": result.get("error"),
                "output": result.get("output", ""),
                "execution_time": execution_time,
            }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error executing command '{command}': {e}")

            return {
                "success": False,
                "error": str(e),
                "output": "",
                "execution_time": execution_time,
            }

    async def get_online_players(self) -> list[PlayerInfo]:
        """获取在线玩家列表"""
        try:
            # 执行list命令获取玩家列表
            result = await self.execute_command_with_result("list")

            if result["success"] and result["output"]:
                # 解析list命令输出
                # 示例输出: "There are 2 of a max of 20 players online: player1, player2"
                output = result["output"]
                if "players online:" in output:
                    player_names = output.split("players online:")[-1].strip()
                    if player_names and player_names != "":
                        names = [name.strip() for name in player_names.split(",")]

                        # 更新在线玩家信息
                        for name in names:
                            if name not in self._online_players:
                                # 新玩家加入
                                self._online_players[name] = PlayerInfo(
                                    name=name,
                                    uuid="",  # 需要从其他地方获取
                                    ip_address="",
                                    join_time=datetime.now(),
                                    last_activity=datetime.now(),
                                    location={},
                                    health=20.0,
                                    food_level=20,
                                    experience_level=0,
                                    game_mode="survival",
                                )

            return list(self._online_players.values())

        except Exception as e:
            logger.error(f"Error getting online players: {e}")
            return []

    async def get_performance_history(
        self, hours: int = 24, metric: str = None
    ) -> list[dict[str, Any]]:
        """
        获取性能历史数据

        Args:
            hours: 获取多少小时的数据
            metric: 指定指标类型

        Returns:
            性能数据列表
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        history = []
        for metrics in self._performance_history:
            if metrics.timestamp >= cutoff_time:
                data = metrics.to_dict()
                if metric and metric in data:
                    # 只返回指定指标
                    history.append(
                        {"timestamp": data["timestamp"], metric: data[metric]}
                    )
                else:
                    history.append(data)

        return history

    async def get_command_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        获取命令历史

        Args:
            limit: 返回的最大记录数

        Returns:
            命令历史列表
        """
        return (
            self._command_history[-limit:]
            if len(self._command_history) > limit
            else self._command_history
        )

    async def create_backup(self, backup_name: str | None = None) -> dict[str, Any]:
        """
        创建服务器备份

        Args:
            backup_name: 备份名称

        Returns:
            备份结果
        """
        try:
            if not backup_name:
                backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 执行保存命令
            save_result = await self.execute_command_with_result("save-all")
            if not save_result["success"]:
                return {
                    "success": False,
                    "error": "Failed to save world before backup",
                    "backup_name": backup_name,
                }

            # 创建备份目录
            backups_dir = Path(self.config.server_directory) / "backups"
            backups_dir.mkdir(exist_ok=True)

            backup_path = backups_dir / f"{backup_name}.zip"
            world_path = Path(self.config.server_directory) / "world"

            if not world_path.exists():
                return {
                    "success": False,
                    "error": "World directory not found",
                    "backup_name": backup_name,
                }

            # 使用文件管理器创建压缩包
            from .file_manager import FileManager

            file_manager = FileManager(self.config.server_directory)

            success = file_manager.create_archive(world_path, backup_path, "zip")

            if success:
                backup_size = backup_path.stat().st_size
                return {
                    "success": True,
                    "backup_name": backup_name,
                    "backup_path": str(backup_path),
                    "backup_size": backup_size,
                    "created_at": datetime.now().isoformat(),
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create backup archive",
                    "backup_name": backup_name,
                }

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return {
                "success": False,
                "error": str(e),
                "backup_name": backup_name or "unknown",
            }

    async def list_backups(self) -> list[dict[str, Any]]:
        """列出所有备份"""
        try:
            backups_dir = Path(self.config.server_directory) / "backups"
            if not backups_dir.exists():
                return []

            backups = []
            for backup_file in backups_dir.glob("*.zip"):
                stat = backup_file.stat()
                backups.append(
                    {
                        "name": backup_file.stem,
                        "filename": backup_file.name,
                        "size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_at": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                    }
                )

            # 按创建时间排序（最新的在前）
            backups.sort(key=lambda x: x["created_at"], reverse=True)
            return backups

        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []

    async def restore_backup(self, backup_name: str) -> dict[str, Any]:
        """
        恢复备份

        Args:
            backup_name: 备份名称

        Returns:
            恢复结果
        """
        try:
            # 检查服务器是否运行
            if self.server_wrapper.is_alive:
                return {
                    "success": False,
                    "error": "Cannot restore backup while server is running",
                }

            backups_dir = Path(self.config.server_directory) / "backups"
            backup_path = backups_dir / f"{backup_name}.zip"

            if not backup_path.exists():
                return {"success": False, "error": f"Backup {backup_name} not found"}

            world_path = Path(self.config.server_directory) / "world"

            # 备份当前世界（如果存在）
            if world_path.exists():
                backup_current = world_path.parent / f"world_backup_{int(time.time())}"
                world_path.rename(backup_current)

            # 使用文件管理器解压备份
            from .file_manager import FileManager

            file_manager = FileManager(self.config.server_directory)

            success = file_manager.extract_archive(backup_path, world_path.parent)

            if success:
                return {
                    "success": True,
                    "backup_name": backup_name,
                    "restored_at": datetime.now().isoformat(),
                }
            else:
                return {"success": False, "error": "Failed to extract backup archive"}

        except Exception as e:
            logger.error(f"Error restoring backup {backup_name}: {e}")
            return {"success": False, "error": str(e)}

    def add_status_change_callback(self, callback: Callable):
        """添加状态变更回调函数"""
        self._status_change_callbacks.append(callback)

    def add_performance_callback(self, callback: Callable):
        """添加性能数据回调函数"""
        self._performance_callbacks.append(callback)

    def remove_status_change_callback(self, callback: Callable):
        """移除状态变更回调函数"""
        if callback in self._status_change_callbacks:
            self._status_change_callbacks.remove(callback)

    def remove_performance_callback(self, callback: Callable):
        """移除性能数据回调函数"""
        if callback in self._performance_callbacks:
            self._performance_callbacks.remove(callback)

    async def enable_auto_backup(self, interval_hours: int = 1):
        """
        启用自动备份

        Args:
            interval_hours: 备份间隔（小时）
        """
        self._backup_enabled = True
        self._backup_interval = interval_hours * 3600  # 转换为秒

        if self._backup_task and not self._backup_task.done():
            self._backup_task.cancel()

        self._backup_task = asyncio.create_task(self._auto_backup_loop())
        logger.info(f"Auto backup enabled with interval: {interval_hours} hours")

    async def disable_auto_backup(self):
        """禁用自动备份"""
        self._backup_enabled = False

        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
            self._backup_task = None

        logger.info("Auto backup disabled")

    async def _auto_backup_loop(self):
        """自动备份循环"""
        while self._backup_enabled:
            try:
                if self.server_wrapper.is_alive:
                    backup_name = (
                        f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    )
                    result = await self.create_backup(backup_name)

                    if result["success"]:
                        logger.info(f"Auto backup created: {backup_name}")
                    else:
                        logger.error(f"Auto backup failed: {result.get('error')}")

                await asyncio.sleep(self._backup_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto backup loop: {e}")
                await asyncio.sleep(self._backup_interval)

    def get_statistics(self) -> dict[str, Any]:
        """获取扩展统计信息"""
        return {
            "performance_entries": len(self._performance_history),
            "command_history_entries": len(self._command_history),
            "online_players": len(self._online_players),
            "monitoring_enabled": self._monitoring_task is not None
            and not self._monitoring_task.done(),
            "auto_backup_enabled": self._backup_enabled,
            "backup_interval_hours": self._backup_interval / 3600,
            "status_callbacks": len(self._status_change_callbacks),
            "performance_callbacks": len(self._performance_callbacks),
        }

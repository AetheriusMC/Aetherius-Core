"""
增强版服务器控制器

集成新架构的服务器管理系统
"""

import asyncio
import logging
import time
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime

import psutil

from .di import inject, Injectable, singleton
from .config import IConfigManager
from .events.enhanced import EnhancedEventBus, Event, EventMetadata, EventPriority
from .monitoring import IMetricsCollector, IHealthChecker, HealthCheck, HealthStatus
from .security import SecurityContext, Permission, BuiltinPermissions
from .exceptions import AetheriusError

logger = logging.getLogger(__name__)


class ServerState(Enum):
    """服务器状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    CRASHED = "crashed"
    MAINTENANCE = "maintenance"


@dataclass
class ServerMetrics:
    """服务器性能指标"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_total: float = 0.0
    uptime: float = 0.0
    players_online: int = 0
    tps: float = 20.0
    mspt: float = 0.0


@Injectable(lifetime="singleton")
class EnhancedServerController:
    """增强版服务器控制器"""
    
    def __init__(self,
                 config: IConfigManager = inject(IConfigManager),
                 events: EnhancedEventBus = inject(EnhancedEventBus),
                 metrics: Optional[IMetricsCollector] = None,
                 health_checker: Optional[IHealthChecker] = None):
        self.config = config
        self.events = events
        self.metrics = metrics
        self.health_checker = health_checker
        
        # 服务器状态
        self._state = ServerState.STOPPED
        self._previous_state = ServerState.STOPPED
        self._state_changed_at = time.time()
        
        # 进程管理
        self.process: Optional[asyncio.subprocess.Process] = None
        self._psutil_process: Optional[psutil.Process] = None
        self._start_time: Optional[float] = None
        
        # 任务管理
        self._tasks: List[asyncio.Task] = []
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # 性能指标
        self._metrics = ServerMetrics()
        self._last_metrics_update = 0.0
        
        # 配置
        self._load_config()
        
        # 注册健康检查
        if self.health_checker:
            self.health_checker.register_check("server_process", self._health_check_process, 30.0)
            self.health_checker.register_check("server_resources", self._health_check_resources, 60.0)
    
    @property
    def state(self) -> ServerState:
        """获取当前状态"""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._state == ServerState.RUNNING
    
    @property
    def is_starting(self) -> bool:
        """检查是否正在启动"""
        return self._state == ServerState.STARTING
    
    @property
    def is_stopping(self) -> bool:
        """检查是否正在停止"""
        return self._state == ServerState.STOPPING
    
    @property
    def uptime(self) -> float:
        """获取运行时间（秒）"""
        if self._start_time and self.is_running:
            return time.time() - self._start_time
        return 0.0
    
    async def start(self, security_context: Optional[SecurityContext] = None) -> bool:
        """启动服务器"""
        # 权限检查
        if security_context:
            from .security import SecurityManager
            security_manager = SecurityManager  # 这里需要从容器获取
            # await security_manager.require_permission(security_context, BuiltinPermissions.SERVER_START)
        
        if self._state != ServerState.STOPPED:
            logger.warning(f"Cannot start server in state: {self._state}")
            return False
        
        try:
            await self._change_state(ServerState.STARTING)
            
            # 发送启动开始事件
            await self._emit_event("server.start_initiated", {
                "user": security_context.user.username if security_context and security_context.user else "system"
            })
            
            # 准备启动环境
            await self._prepare_server_environment()
            
            # 启动服务器进程
            success = await self._start_server_process()
            
            if success:
                await self._change_state(ServerState.RUNNING)
                self._start_time = time.time()
                
                # 启动监控任务
                self._monitoring_task = asyncio.create_task(self._monitoring_loop())
                
                # 发送启动完成事件
                await self._emit_event("server.started", {
                    "pid": self.process.pid if self.process else None,
                    "start_time": self._start_time
                }, priority=EventPriority.HIGH)
                
                logger.info("Server started successfully")
                return True
            else:
                await self._change_state(ServerState.STOPPED)
                await self._emit_event("server.start_failed", {})
                return False
        
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            await self._change_state(ServerState.CRASHED)
            await self._emit_event("server.crashed", {
                "error": str(e),
                "during": "startup"
            }, priority=EventPriority.CRITICAL)
            return False
    
    async def stop(self, 
                  force: bool = False, 
                  timeout: float = 30.0,
                  security_context: Optional[SecurityContext] = None) -> bool:
        """停止服务器"""
        # 权限检查
        if security_context:
            # await security_manager.require_permission(security_context, BuiltinPermissions.SERVER_STOP)
            pass
        
        if self._state in (ServerState.STOPPED, ServerState.STOPPING):
            logger.warning(f"Server is already stopping or stopped")
            return True
        
        try:
            await self._change_state(ServerState.STOPPING)
            
            # 发送停止开始事件
            await self._emit_event("server.stop_initiated", {
                "force": force,
                "timeout": timeout,
                "user": security_context.user.username if security_context and security_context.user else "system"
            })
            
            # 停止监控任务
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
                self._monitoring_task = None
            
            # 停止服务器进程
            success = await self._stop_server_process(force, timeout)
            
            await self._change_state(ServerState.STOPPED)
            self._start_time = None
            
            # 发送停止完成事件
            await self._emit_event("server.stopped", {
                "graceful": success,
                "uptime": self.uptime
            }, priority=EventPriority.HIGH)
            
            logger.info("Server stopped successfully")
            return success
        
        except Exception as e:
            logger.error(f"Error during server stop: {e}")
            await self._change_state(ServerState.CRASHED)
            return False
    
    async def restart(self, 
                     timeout: float = 30.0,
                     security_context: Optional[SecurityContext] = None) -> bool:
        """重启服务器"""
        logger.info("Restarting server...")
        
        # 发送重启事件
        await self._emit_event("server.restart_initiated", {
            "user": security_context.user.username if security_context and security_context.user else "system"
        })
        
        # 先停止
        stop_success = await self.stop(timeout=timeout, security_context=security_context)
        if not stop_success:
            logger.error("Failed to stop server during restart")
            return False
        
        # 等待一小段时间
        await asyncio.sleep(2.0)
        
        # 再启动
        start_success = await self.start(security_context=security_context)
        
        # 发送重启完成事件
        await self._emit_event("server.restarted" if start_success else "server.restart_failed", {
            "success": start_success
        })
        
        return start_success
    
    async def send_command(self, 
                          command: str,
                          security_context: Optional[SecurityContext] = None) -> bool:
        """发送命令到服务器"""
        # 权限检查
        if security_context:
            # await security_manager.require_permission(security_context, BuiltinPermissions.SERVER_CONSOLE)
            pass
        
        if not self.is_running or not self.process:
            return False
        
        try:
            # 发送命令事件
            await self._emit_event("server.command_sent", {
                "command": command,
                "user": security_context.user.username if security_context and security_context.user else "system"
            })
            
            # 发送到进程
            self.process.stdin.write(f"{command}\n".encode())
            await self.process.stdin.drain()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to send command '{command}': {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取服务器状态"""
        return {
            "state": self._state.value,
            "uptime": self.uptime,
            "pid": self.process.pid if self.process else None,
            "metrics": {
                "cpu_usage": self._metrics.cpu_usage,
                "memory_usage": self._metrics.memory_usage,
                "memory_total": self._metrics.memory_total,
                "players_online": self._metrics.players_online,
                "tps": self._metrics.tps,
                "mspt": self._metrics.mspt
            },
            "state_changed_at": self._state_changed_at,
            "config": {
                "jar_file": self.jar_file,
                "java_args": self.java_args,
                "server_args": self.server_args,
                "working_directory": str(self.working_directory)
            }
        }
    
    def get_metrics(self) -> ServerMetrics:
        """获取性能指标"""
        return self._metrics
    
    # 私有方法
    
    def _load_config(self):
        """加载配置"""
        self.jar_file = self.config.get("server.jar_file", "server.jar")
        self.java_executable = self.config.get("server.java_executable", "java")
        self.java_args = self.config.get("server.java_args", ["-Xmx2G", "-Xms1G"])
        self.server_args = self.config.get("server.server_args", ["nogui"])
        self.working_directory = Path(self.config.get("server.working_directory", "server"))
        
        # 监控配置
        self.metrics_update_interval = self.config.get("server.metrics_update_interval", 5.0)
        self.health_check_interval = self.config.get("server.health_check_interval", 10.0)
    
    async def _change_state(self, new_state: ServerState):
        """改变服务器状态"""
        if new_state == self._state:
            return
        
        old_state = self._state
        self._previous_state = old_state
        self._state = new_state
        self._state_changed_at = time.time()
        
        logger.info(f"Server state changed: {old_state.value} -> {new_state.value}")
        
        # 发送状态变更事件
        await self._emit_event("server.state_changed", {
            "old_state": old_state.value,
            "new_state": new_state.value,
            "timestamp": self._state_changed_at
        })
        
        # 记录指标
        if self.metrics:
            self.metrics.increment("server.state_changes", labels={
                "from_state": old_state.value,
                "to_state": new_state.value
            })
    
    async def _prepare_server_environment(self):
        """准备服务器环境"""
        # 确保工作目录存在
        self.working_directory.mkdir(parents=True, exist_ok=True)
        
        # 检查JAR文件是否存在
        jar_path = self.working_directory / self.jar_file
        if not jar_path.exists():
            raise AetheriusError(f"Server JAR file not found: {jar_path}")
        
        logger.debug("Server environment prepared")
    
    async def _start_server_process(self) -> bool:
        """启动服务器进程"""
        try:
            # 构建命令
            cmd = [
                self.java_executable,
                *self.java_args,
                "-jar",
                self.jar_file,
                *self.server_args
            ]
            
            logger.info(f"Starting server with command: {' '.join(cmd)}")
            
            # 启动进程
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.working_directory,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 创建psutil进程对象
            try:
                self._psutil_process = psutil.Process(self.process.pid)
            except psutil.NoSuchProcess:
                self._psutil_process = None
            
            # 启动I/O处理任务
            self._tasks.extend([
                asyncio.create_task(self._handle_stdout()),
                asyncio.create_task(self._handle_stderr()),
                asyncio.create_task(self._monitor_process())
            ])
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to start server process: {e}")
            return False
    
    async def _stop_server_process(self, force: bool = False, timeout: float = 30.0) -> bool:
        """停止服务器进程"""
        if not self.process:
            return True
        
        try:
            if not force:
                # 尝试优雅停止
                try:
                    await self.send_command("stop")
                    await asyncio.wait_for(self.process.wait(), timeout=timeout)
                    return True
                except asyncio.TimeoutError:
                    logger.warning(f"Server did not stop gracefully within {timeout}s, forcing...")
            
            # 强制停止
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Server did not terminate, killing...")
                self.process.kill()
                await self.process.wait()
            
            return True
        
        except Exception as e:
            logger.error(f"Error stopping server process: {e}")
            return False
        
        finally:
            # 清理任务
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                self._tasks.clear()
            
            self.process = None
            self._psutil_process = None
    
    async def _handle_stdout(self):
        """处理标准输出"""
        if not self.process or not self.process.stdout:
            return
        
        try:
            async for line in self.process.stdout:
                line_str = line.decode('utf-8', errors='replace').strip()
                if line_str:
                    # 发送日志事件
                    await self._emit_event("server.log", {
                        "level": "INFO",
                        "message": line_str,
                        "stream": "stdout"
                    })
                    
                    # 解析特定日志模式
                    await self._parse_log_line(line_str)
        
        except Exception as e:
            logger.error(f"Error handling stdout: {e}")
    
    async def _handle_stderr(self):
        """处理标准错误"""
        if not self.process or not self.process.stderr:
            return
        
        try:
            async for line in self.process.stderr:
                line_str = line.decode('utf-8', errors='replace').strip()
                if line_str:
                    # 发送日志事件
                    await self._emit_event("server.log", {
                        "level": "ERROR",
                        "message": line_str,
                        "stream": "stderr"
                    })
        
        except Exception as e:
            logger.error(f"Error handling stderr: {e}")
    
    async def _monitor_process(self):
        """监控进程状态"""
        if not self.process:
            return
        
        try:
            # 等待进程结束
            return_code = await self.process.wait()
            
            if self._state in (ServerState.RUNNING, ServerState.STARTING):
                # 非预期退出
                logger.error(f"Server process exited unexpectedly with code {return_code}")
                await self._change_state(ServerState.CRASHED)
                
                await self._emit_event("server.crashed", {
                    "return_code": return_code,
                    "uptime": self.uptime
                }, priority=EventPriority.CRITICAL)
        
        except Exception as e:
            logger.error(f"Error monitoring process: {e}")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while self._state == ServerState.RUNNING:
            try:
                await self._update_metrics()
                await asyncio.sleep(self.metrics_update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5.0)
    
    async def _update_metrics(self):
        """更新性能指标"""
        if not self._psutil_process:
            return
        
        try:
            # 获取进程信息
            with self._psutil_process.oneshot():
                cpu_percent = self._psutil_process.cpu_percent()
                memory_info = self._psutil_process.memory_info()
                
            # 更新指标
            self._metrics.cpu_usage = cpu_percent
            self._metrics.memory_usage = memory_info.rss / 1024 / 1024  # MB
            self._metrics.uptime = self.uptime
            
            # 记录到监控系统
            if self.metrics:
                self.metrics.set_gauge("server.cpu_usage", cpu_percent)
                self.metrics.set_gauge("server.memory_usage", self._metrics.memory_usage)
                self.metrics.set_gauge("server.uptime", self._metrics.uptime)
                self.metrics.set_gauge("server.players_online", self._metrics.players_online)
                self.metrics.set_gauge("server.tps", self._metrics.tps)
            
            self._last_metrics_update = time.time()
        
        except psutil.NoSuchProcess:
            logger.warning("Server process no longer exists")
            self._psutil_process = None
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    async def _parse_log_line(self, line: str):
        """解析日志行以提取信息"""
        # 这里可以添加更多的日志解析逻辑
        # 例如：玩家加入/离开、TPS信息等
        
        # 示例：解析玩家加入
        if "joined the game" in line:
            # 提取玩家名
            parts = line.split()
            if len(parts) >= 4:
                player_name = parts[3]
                self._metrics.players_online += 1
                
                await self._emit_event("player.joined", {
                    "player_name": player_name,
                    "timestamp": time.time()
                })
        
        # 示例：解析玩家离开
        elif "left the game" in line:
            parts = line.split()
            if len(parts) >= 4:
                player_name = parts[3]
                self._metrics.players_online = max(0, self._metrics.players_online - 1)
                
                await self._emit_event("player.left", {
                    "player_name": player_name,
                    "timestamp": time.time()
                })
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any], priority: EventPriority = EventPriority.NORMAL):
        """发送事件"""
        metadata = EventMetadata(
            priority=priority,
            source="server_controller"
        )
        
        await self.events.publish(event_type, data, metadata)
    
    # 健康检查方法
    
    async def _health_check_process(self) -> HealthCheck:
        """进程健康检查"""
        if not self.is_running or not self.process:
            return HealthCheck(
                name="server_process",
                status=HealthStatus.CRITICAL,
                message="Server process is not running",
                details={"state": self._state.value}
            )
        
        try:
            # 检查进程是否还活着
            if self.process.returncode is not None:
                return HealthCheck(
                    name="server_process",
                    status=HealthStatus.CRITICAL,
                    message=f"Server process exited with code {self.process.returncode}",
                    details={"return_code": self.process.returncode}
                )
            
            return HealthCheck(
                name="server_process",
                status=HealthStatus.HEALTHY,
                message="Server process is running normally",
                details={
                    "pid": self.process.pid,
                    "uptime": self.uptime,
                    "state": self._state.value
                }
            )
        
        except Exception as e:
            return HealthCheck(
                name="server_process",
                status=HealthStatus.UNKNOWN,
                message=f"Error checking process health: {e}",
                details={"error": str(e)}
            )
    
    async def _health_check_resources(self) -> HealthCheck:
        """资源健康检查"""
        if not self._psutil_process:
            return HealthCheck(
                name="server_resources",
                status=HealthStatus.UNKNOWN,
                message="No process information available"
            )
        
        try:
            with self._psutil_process.oneshot():
                cpu_percent = self._psutil_process.cpu_percent()
                memory_info = self._psutil_process.memory_info()
                memory_percent = self._psutil_process.memory_percent()
            
            # 检查资源使用情况
            status = HealthStatus.HEALTHY
            issues = []
            
            if cpu_percent > 90:
                status = HealthStatus.CRITICAL
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            elif cpu_percent > 70:
                status = HealthStatus.WARNING
                issues.append(f"Elevated CPU usage: {cpu_percent:.1f}%")
            
            if memory_percent > 90:
                status = HealthStatus.CRITICAL
                issues.append(f"High memory usage: {memory_percent:.1f}%")
            elif memory_percent > 80:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append(f"Elevated memory usage: {memory_percent:.1f}%")
            
            message = "Resource usage is normal"
            if issues:
                message = "; ".join(issues)
            
            return HealthCheck(
                name="server_resources",
                status=status,
                message=message,
                details={
                    "cpu_usage": cpu_percent,
                    "memory_usage_mb": memory_info.rss / 1024 / 1024,
                    "memory_percent": memory_percent
                }
            )
        
        except Exception as e:
            return HealthCheck(
                name="server_resources",
                status=HealthStatus.UNKNOWN,
                message=f"Error checking resource health: {e}",
                details={"error": str(e)}
            )
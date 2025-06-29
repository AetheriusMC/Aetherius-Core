"""
系统监控插件

演示新架构的插件开发示例
"""

import asyncio
import psutil
from typing import Dict, List, Any, Callable, Optional

from aetherius.core.extensions import (
    IPlugin, ExtensionInfo, ExtensionContext, ExtensionState,
    plugin, ExtensionPermission
)

@plugin(
    name="system_monitor",
    version="1.0.0",
    display_name="System Monitor Plugin",
    description="系统监控插件，提供详细的系统性能监控和告警",
    author="Aetherius Team",
    category="monitoring",
    tags=["monitoring", "system", "performance"],
    permissions=[
        ExtensionPermission.SYSTEM_ENV,
        ExtensionPermission.CORE_ACCESS
    ]
)
class SystemMonitorPlugin(IPlugin):
    """系统监控插件"""
    
    def __init__(self, context: ExtensionContext):
        super().__init__(context)
        self._commands = {}
        self._event_handlers = {}
        self._event_registrations = []  # 保存事件订阅ID
        self._monitoring_task = None
        self._metrics_collector = None
        self._health_checker = None
        
        # 初始化配置属性（默认值）
        self.monitoring_interval = 10.0
        self.enable_detailed_monitoring = True
        self.alert_thresholds = {
            "cpu": 80.0,
            "memory": 85.0,
            "disk": 90.0,
            "load": 5.0
        }
        self.track_processes = ["java", "python"]
        
        self._setup_commands()
        self._setup_event_handlers()
    
    @property
    def info(self) -> ExtensionInfo:
        return self.__class__.__extension_info__
    
    async def load(self):
        """加载插件"""
        self.context.logger.info("Loading System Monitor plugin...")
        
        # 获取监控组件（可选）
        try:
            if self.context.services:
                self._metrics_collector = self.context.services.resolve("IMetricsCollector")
                self._health_checker = self.context.services.resolve("IHealthChecker")
        except Exception as e:
            self.context.logger.warning(f"Failed to resolve monitoring services: {e}")
        
        # 加载配置
        self._load_config()
        
        # 注册命令（如果事件系统可用）
        if self.context.events:
            try:
                for cmd_name, cmd_func in self._commands.items():
                    await self.context.events.publish("command.register", {
                        "name": cmd_name,
                        "handler": cmd_func,
                        "plugin": self.info.name
                    })
            except Exception as e:
                self.context.logger.warning(f"Failed to register commands: {e}")
        
        self.context.logger.info("System Monitor plugin loaded")
    
    async def start(self):
        """启动插件"""
        self.context.logger.info("Starting System Monitor plugin...")
        
        # 注册事件处理器
        if self.context.events:
            try:
                for event_type, handlers in self._event_handlers.items():
                    for handler in handlers:
                        self.context.events.subscribe(event_type, handler)
            except Exception as e:
                self.context.logger.warning(f"Failed to register event handlers: {e}")
        
        # 注册健康检查（如果可用）
        if self._health_checker:
            try:
                self._health_checker.register_check(
                    "system_performance",
                    self._system_performance_check,
                    30.0
                )
                self._health_checker.register_check(
                    "process_health",
                    self._process_health_check,
                    60.0
                )
            except Exception as e:
                self.context.logger.warning(f"Failed to register health checks: {e}")
        
        # 启动监控任务
        if self.enable_detailed_monitoring:
            self._monitoring_task = asyncio.create_task(self._detailed_monitoring_loop())
        
        # 发送启动消息
        if self.context.events:
            try:
                await self.context.events.publish("server.broadcast", {
                    "message": "System Monitor plugin started!",
                    "color": "green"
                })
            except Exception as e:
                self.context.logger.warning(f"Failed to send startup message: {e}")
        
        self.context.logger.info("System Monitor plugin started")
    
    async def stop(self):
        """停止插件"""
        self.context.logger.info("Stopping System Monitor plugin...")
        
        # 停止监控任务
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        
        # 注销事件处理器
        for event_type, handlers in self._event_handlers.items():
            for handler in handlers:
                self.context.events.unsubscribe(event_type, handler)
        
        # 注销健康检查
        if self._health_checker:
            self._health_checker.unregister_check("system_performance")
            self._health_checker.unregister_check("process_health")
        
        # 发送停止消息
        if self.context.events:
            try:
                await self.context.events.publish("server.broadcast", {
                    "message": "System Monitor plugin stopped!",
                    "color": "red"
                })
            except Exception as e:
                self.context.logger.warning(f"Failed to send stop message: {e}")
        
        self.context.logger.info("System Monitor plugin stopped")
    
    async def unload(self):
        """卸载插件"""
        self.context.logger.info("Unloading System Monitor plugin...")
        
        # 注销命令
        if self.context.events:
            try:
                for cmd_name in self._commands.keys():
                    await self.context.events.publish("command.unregister", {
                        "name": cmd_name,
                        "plugin": self.info.name
                    })
            except Exception as e:
                self.context.logger.warning(f"Failed to unregister commands: {e}")
        
        self.context.logger.info("System Monitor plugin unloaded")
    
    def get_commands(self) -> Dict[str, Callable]:
        """获取插件提供的命令"""
        return self._commands
    
    def get_event_handlers(self) -> Dict[str, List[Callable]]:
        """获取事件处理器"""
        return self._event_handlers
    
    def _load_config(self):
        """加载配置"""
        try:
            self.monitoring_interval = self.context.get_extension_config(
                "monitoring_interval", 10.0
            )
            self.enable_detailed_monitoring = self.context.get_extension_config(
                "enable_detailed_monitoring", True
            )
            self.alert_thresholds = self.context.get_extension_config(
                "alert_thresholds", {
                    "cpu": 80.0,
                    "memory": 85.0,
                    "disk": 90.0,
                    "load": 5.0
                }
            )
            self.track_processes = self.context.get_extension_config(
                "track_processes", ["java", "python"]
            )
        except Exception as e:
            # 如果配置系统不可用，使用默认值
            self.context.logger.warning(f"Failed to load config, using defaults: {e}")
            self.monitoring_interval = 10.0
            self.enable_detailed_monitoring = True
            self.alert_thresholds = {
                "cpu": 80.0,
                "memory": 85.0,
                "disk": 90.0,
                "load": 5.0
            }
            self.track_processes = ["java", "python"]
    
    def _setup_commands(self):
        """设置命令"""
        self._commands = {
            "sysinfo": self._cmd_sysinfo,
            "performance": self._cmd_performance,
            "processes": self._cmd_processes,
            "monitor": self._cmd_monitor,
            "alerts": self._cmd_alerts
        }
    
    def _setup_event_handlers(self):
        """设置事件处理器"""
        self._event_handlers = {
            "server.started": [self._on_server_started],
            "player.joined": [self._on_player_joined]
        }
    
    # 命令处理器
    
    async def _cmd_sysinfo(self, sender, args):
        """系统信息命令"""
        try:
            # 获取系统信息
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            boot_time = psutil.boot_time()
            
            # 格式化信息
            info = [
                f"CPU: {cpu_count} cores",
                f"CPU Frequency: {cpu_freq.current:.0f} MHz" if cpu_freq else "CPU Frequency: Unknown",
                f"Memory: {memory.total / 1024**3:.1f} GB total, {memory.available / 1024**3:.1f} GB available",
                f"Disk: {disk.total / 1024**3:.1f} GB total, {disk.free / 1024**3:.1f} GB free",
                f"Uptime: {(asyncio.get_event_loop().time() - boot_time) / 3600:.1f} hours"
            ]
            
            message = "System Information:\\n" + "\\n".join(info)
            
        except Exception as e:
            message = f"Error getting system info: {e}"
        
        if self.context.events:
            try:
                await self.context.events.publish("chat.send", {
                    "recipient": sender,
                    "message": message,
                    "color": "blue"
                })
            except Exception as e:
                self.context.logger.warning(f"Failed to send message: {e}")
    
    async def _cmd_performance(self, sender, args):
        """性能信息命令"""
        try:
            # 获取当前性能数据
            cpu_percent = psutil.cpu_percent(interval=1.0)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
            
            info = [
                f"CPU Usage: {cpu_percent:.1f}%",
                f"Memory Usage: {memory.percent:.1f}% ({memory.used / 1024**3:.1f} GB / {memory.total / 1024**3:.1f} GB)",
                f"Disk Usage: {(disk.used / disk.total) * 100:.1f}% ({disk.free / 1024**3:.1f} GB free)",
                f"Load Average: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}"
            ]
            
            message = "System Performance:\\n" + "\\n".join(info)
            
        except Exception as e:
            message = f"Error getting performance info: {e}"
        
        if self.context.events:
            try:
                await self.context.events.publish("chat.send", {
                    "recipient": sender,
                    "message": message,
                    "color": "yellow"
                })
            except Exception as e:
                self.context.logger.warning(f"Failed to send message: {e}")
    
    async def _cmd_processes(self, sender, args):
        """进程信息命令"""
        try:
            # 获取相关进程
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    if any(name in proc_info['name'].lower() for name in self.track_processes):
                        processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not processes:
                message = "No tracked processes found"
            else:
                info = ["Tracked Processes:"]
                for proc in processes[:10]:  # 限制显示数量
                    info.append(f"PID {proc['pid']}: {proc['name']} - CPU: {proc['cpu_percent']:.1f}%, Memory: {proc['memory_percent']:.1f}%")
                
                message = "\\n".join(info)
        
        except Exception as e:
            message = f"Error getting process info: {e}"
        
        if self.context.events:
            try:
                await self.context.events.publish("chat.send", {
                    "recipient": sender,
                    "message": message,
                    "color": "cyan"
                })
            except Exception as e:
                self.context.logger.warning(f"Failed to send message: {e}")
    
    async def _cmd_monitor(self, sender, args):
        """监控控制命令"""
        if not args:
            status = "enabled" if self._monitoring_task else "disabled"
            message = f"Detailed monitoring is {status}"
        elif args[0].lower() == "start":
            if not self._monitoring_task:
                self._monitoring_task = asyncio.create_task(self._detailed_monitoring_loop())
                message = "Detailed monitoring started"
            else:
                message = "Detailed monitoring is already running"
        elif args[0].lower() == "stop":
            if self._monitoring_task:
                self._monitoring_task.cancel()
                self._monitoring_task = None
                message = "Detailed monitoring stopped"
            else:
                message = "Detailed monitoring is not running"
        else:
            message = "Usage: /monitor [start|stop]"
        
        if self.context.events:
            try:
                await self.context.events.publish("chat.send", {
                    "recipient": sender,
                    "message": message,
                    "color": "green"
                })
            except Exception as e:
                self.context.logger.warning(f"Failed to send message: {e}")
    
    async def _cmd_alerts(self, sender, args):
        """告警信息命令"""
        try:
            # 检查当前状态是否触发告警
            alerts = []
            
            cpu_percent = psutil.cpu_percent()
            if cpu_percent > self.alert_thresholds["cpu"]:
                alerts.append(f"High CPU usage: {cpu_percent:.1f}%")
            
            memory = psutil.virtual_memory()
            if memory.percent > self.alert_thresholds["memory"]:
                alerts.append(f"High memory usage: {memory.percent:.1f}%")
            
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > self.alert_thresholds["disk"]:
                alerts.append(f"High disk usage: {disk_percent:.1f}%")
            
            if hasattr(psutil, 'getloadavg'):
                load_avg = psutil.getloadavg()[0]
                if load_avg > self.alert_thresholds["load"]:
                    alerts.append(f"High system load: {load_avg:.2f}")
            
            if alerts:
                message = "Active Alerts:\\n" + "\\n".join(f"⚠ {alert}" for alert in alerts)
            else:
                message = "No active alerts. System is healthy."
        
        except Exception as e:
            message = f"Error checking alerts: {e}"
        
        if self.context.events:
            try:
                await self.context.events.publish("chat.send", {
                    "recipient": sender,
                    "message": message,
                    "color": "orange" if alerts else "green"
                })
            except Exception as e:
                self.context.logger.warning(f"Failed to send message: {e}")
    
    # 事件处理器
    
    async def _on_server_started(self, event_data):
        """服务器启动事件处理器"""
        self.context.logger.info("Server started, beginning system monitoring")
        
        # 记录服务器启动时的系统状态
        if self._metrics_collector:
            try:
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                
                self._metrics_collector.set_gauge("server.startup.cpu_usage", cpu_percent)
                self._metrics_collector.set_gauge("server.startup.memory_usage", memory.percent)
                
            except Exception as e:
                self.context.logger.error(f"Error recording startup metrics: {e}")
    
    async def _on_player_joined(self, event_data):
        """玩家加入事件处理器"""
        player_name = event_data.get("player_name")
        if player_name and self._metrics_collector:
            # 记录玩家加入时的系统负载
            try:
                cpu_percent = psutil.cpu_percent()
                self._metrics_collector.record_histogram("player.join.cpu_load", cpu_percent)
                
            except Exception as e:
                self.context.logger.error(f"Error recording player join metrics: {e}")
    
    # 健康检查
    
    async def _system_performance_check(self):
        """系统性能健康检查"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1.0)
            memory = psutil.virtual_memory()
            
            issues = []
            status = "healthy"
            
            if cpu_percent > 90:
                status = "critical"
                issues.append(f"Critical CPU usage: {cpu_percent:.1f}%")
            elif cpu_percent > 70:
                status = "warning"
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            
            if memory.percent > 90:
                status = "critical"
                issues.append(f"Critical memory usage: {memory.percent:.1f}%")
            elif memory.percent > 80:
                if status == "healthy":
                    status = "warning"
                issues.append(f"High memory usage: {memory.percent:.1f}%")
            
            message = "System performance is normal"
            if issues:
                message = "; ".join(issues)
            
            return {
                "name": "system_performance",
                "status": status,
                "message": message,
                "details": {
                    "cpu_usage": cpu_percent,
                    "memory_usage": memory.percent,
                    "memory_available_gb": memory.available / 1024**3
                }
            }
        
        except Exception as e:
            return {
                "name": "system_performance",
                "status": "unknown",
                "message": f"Error checking system performance: {e}",
                "details": {"error": str(e)}
            }
    
    async def _process_health_check(self):
        """进程健康检查"""
        try:
            tracked_processes = []
            total_cpu = 0
            total_memory = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    proc_info = proc.info
                    if any(name in proc_info['name'].lower() for name in self.track_processes):
                        tracked_processes.append(proc_info)
                        total_cpu += proc_info['cpu_percent'] or 0
                        total_memory += proc_info['memory_percent'] or 0
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not tracked_processes:
                return {
                    "name": "process_health",
                    "status": "warning",
                    "message": "No tracked processes found",
                    "details": {"tracked_processes": self.track_processes}
                }
            
            # 检查是否有异常进程
            issues = []
            for proc in tracked_processes:
                if proc['status'] == 'zombie':
                    issues.append(f"Zombie process: {proc['name']} (PID {proc['pid']})")
                elif proc['cpu_percent'] and proc['cpu_percent'] > 80:
                    issues.append(f"High CPU process: {proc['name']} ({proc['cpu_percent']:.1f}%)")
            
            status = "critical" if issues else "healthy"
            message = f"Found {len(tracked_processes)} tracked processes"
            if issues:
                message += f"; Issues: {'; '.join(issues)}"
            
            return {
                "name": "process_health",
                "status": status,
                "message": message,
                "details": {
                    "process_count": len(tracked_processes),
                    "total_cpu_usage": total_cpu,
                    "total_memory_usage": total_memory,
                    "processes": tracked_processes[:5]  # 只返回前5个进程的详情
                }
            }
        
        except Exception as e:
            return {
                "name": "process_health",
                "status": "unknown",
                "message": f"Error checking process health: {e}",
                "details": {"error": str(e)}
            }
    
    # 监控循环
    
    async def _detailed_monitoring_loop(self):
        """详细监控循环"""
        self.context.logger.info("Started detailed monitoring loop")
        
        while True:
            try:
                await self._collect_detailed_metrics()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.context.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)  # 错误时等待30秒
        
        self.context.logger.info("Stopped detailed monitoring loop")
    
    async def _collect_detailed_metrics(self):
        """收集详细指标"""
        if not self._metrics_collector:
            return
        
        try:
            # CPU指标
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_count = psutil.cpu_count()
            
            self._metrics_collector.set_gauge("system.cpu.usage", cpu_percent)
            self._metrics_collector.set_gauge("system.cpu.count", cpu_count)
            
            # 内存指标
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            self._metrics_collector.set_gauge("system.memory.total", memory.total)
            self._metrics_collector.set_gauge("system.memory.available", memory.available)
            self._metrics_collector.set_gauge("system.memory.used", memory.used)
            self._metrics_collector.set_gauge("system.memory.percent", memory.percent)
            self._metrics_collector.set_gauge("system.swap.total", swap.total)
            self._metrics_collector.set_gauge("system.swap.used", swap.used)
            self._metrics_collector.set_gauge("system.swap.percent", swap.percent)
            
            # 磁盘指标
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            self._metrics_collector.set_gauge("system.disk.total", disk.total)
            self._metrics_collector.set_gauge("system.disk.used", disk.used)
            self._metrics_collector.set_gauge("system.disk.free", disk.free)
            self._metrics_collector.set_gauge("system.disk.percent", (disk.used / disk.total) * 100)
            
            if disk_io:
                self._metrics_collector.set_gauge("system.disk.io.read_bytes", disk_io.read_bytes)
                self._metrics_collector.set_gauge("system.disk.io.write_bytes", disk_io.write_bytes)
                self._metrics_collector.set_gauge("system.disk.io.read_count", disk_io.read_count)
                self._metrics_collector.set_gauge("system.disk.io.write_count", disk_io.write_count)
            
            # 网络指标
            net_io = psutil.net_io_counters()
            if net_io:
                self._metrics_collector.set_gauge("system.network.bytes_sent", net_io.bytes_sent)
                self._metrics_collector.set_gauge("system.network.bytes_recv", net_io.bytes_recv)
                self._metrics_collector.set_gauge("system.network.packets_sent", net_io.packets_sent)
                self._metrics_collector.set_gauge("system.network.packets_recv", net_io.packets_recv)
            
            # 系统负载（如果可用）
            if hasattr(psutil, 'getloadavg'):
                load_1, load_5, load_15 = psutil.getloadavg()
                self._metrics_collector.set_gauge("system.load.1m", load_1)
                self._metrics_collector.set_gauge("system.load.5m", load_5)
                self._metrics_collector.set_gauge("system.load.15m", load_15)
            
            # 进程计数
            process_count = len(psutil.pids())
            self._metrics_collector.set_gauge("system.processes.count", process_count)
            
        except Exception as e:
            self.context.logger.error(f"Error collecting detailed metrics: {e}")
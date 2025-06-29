"""
监控系统收集器实现

提供指标收集、健康检查和告警管理的具体实现
"""

import asyncio
import time
import threading
import psutil
from typing import Dict, List, Optional, Set, Callable, Any, Union
from collections import defaultdict, deque
from dataclasses import dataclass, field
import logging

from . import (
    IMetricsCollector, IHealthChecker, IAlertManager, ITracer,
    Metric, MetricType, HealthCheck, HealthStatus, Alert, AlertLevel,
    Timer, Span, SystemMetrics, ApplicationMetrics, MinecraftMetrics
)

logger = logging.getLogger(__name__)


class InMemoryMetricsCollector(IMetricsCollector):
    """内存指标收集器"""
    
    def __init__(self, max_metrics: int = 10000):
        self.max_metrics = max_metrics
        self._metrics: Dict[str, List[Metric]] = defaultdict(list)
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def increment(self, 
                 name: str, 
                 value: float = 1.0, 
                 labels: Optional[Dict[str, str]] = None):
        """递增计数器"""
        key = self._make_key(name, labels)
        
        with self._lock:
            self._counters[key] += value
            
            metric = Metric(
                name=name,
                type=MetricType.COUNTER,
                value=self._counters[key],
                labels=labels or {}
            )
            
            self._store_metric(name, metric)
    
    def set_gauge(self, 
                 name: str, 
                 value: float, 
                 labels: Optional[Dict[str, str]] = None):
        """设置仪表值"""
        key = self._make_key(name, labels)
        
        with self._lock:
            self._gauges[key] = value
            
            metric = Metric(
                name=name,
                type=MetricType.GAUGE,
                value=value,
                labels=labels or {}
            )
            
            self._store_metric(name, metric)
    
    def record_histogram(self, 
                        name: str, 
                        value: float, 
                        labels: Optional[Dict[str, str]] = None):
        """记录直方图数据"""
        key = self._make_key(name, labels)
        
        with self._lock:
            self._histograms[key].append(value)
            
            # 限制历史数据大小
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
            
            metric = Metric(
                name=name,
                type=MetricType.HISTOGRAM,
                value=value,
                labels=labels or {}
            )
            
            self._store_metric(name, metric)
    
    def start_timer(self, 
                   name: str, 
                   labels: Optional[Dict[str, str]] = None) -> Timer:
        """开始计时"""
        return Timer(self, name, labels)
    
    def get_metrics(self, 
                   name_pattern: Optional[str] = None) -> List[Metric]:
        """获取指标"""
        with self._lock:
            all_metrics = []
            
            for metric_name, metrics in self._metrics.items():
                if name_pattern is None or name_pattern in metric_name:
                    all_metrics.extend(metrics[-100:])  # 返回最近100个指标
            
            return all_metrics
    
    def get_counter_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """获取计数器值"""
        key = self._make_key(name, labels)
        with self._lock:
            return self._counters.get(key, 0.0)
    
    def get_gauge_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """获取仪表值"""
        key = self._make_key(name, labels)
        with self._lock:
            return self._gauges.get(key)
    
    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """获取直方图统计"""
        key = self._make_key(name, labels)
        with self._lock:
            values = self._histograms.get(key, [])
            if not values:
                return {}
            
            sorted_values = sorted(values)
            count = len(sorted_values)
            
            return {
                "count": count,
                "sum": sum(sorted_values),
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "avg": sum(sorted_values) / count,
                "p50": sorted_values[int(count * 0.5)],
                "p90": sorted_values[int(count * 0.9)],
                "p95": sorted_values[int(count * 0.95)],
                "p99": sorted_values[int(count * 0.99)]
            }
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """生成指标键"""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def _store_metric(self, name: str, metric: Metric):
        """存储指标"""
        self._metrics[name].append(metric)
        
        # 限制指标数量
        if len(self._metrics[name]) > self.max_metrics:
            self._metrics[name] = self._metrics[name][-self.max_metrics:]


class HealthCheckManager(IHealthChecker):
    """健康检查管理器"""
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._intervals: Dict[str, float] = {}
        self._last_results: Dict[str, HealthCheck] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._lock = threading.RLock()
        self._running = False
    
    async def start(self):
        """启动健康检查"""
        if self._running:
            return
        
        self._running = True
        
        # 启动所有定期检查
        for name in self._checks:
            if name in self._intervals:
                self._tasks[name] = asyncio.create_task(
                    self._periodic_check(name, self._intervals[name])
                )
        
        logger.info("Health check manager started")
    
    async def stop(self):
        """停止健康检查"""
        if not self._running:
            return
        
        self._running = False
        
        # 停止所有任务
        for task in self._tasks.values():
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
            self._tasks.clear()
        
        logger.info("Health check manager stopped")
    
    async def check_health(self, name: str) -> HealthCheck:
        """执行健康检查"""
        with self._lock:
            check_func = self._checks.get(name)
            if not check_func:
                return HealthCheck(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check '{name}' not found"
                )
        
        try:
            start_time = time.time()
            
            # 执行检查
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()
            
            duration = time.time() - start_time
            
            # 处理结果
            if isinstance(result, HealthCheck):
                result.duration = duration
                health_check = result
            elif isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.CRITICAL
                health_check = HealthCheck(
                    name=name,
                    status=status,
                    message="Health check passed" if result else "Health check failed",
                    duration=duration
                )
            else:
                health_check = HealthCheck(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Invalid health check result: {result}",
                    duration=duration
                )
            
            # 缓存结果
            with self._lock:
                self._last_results[name] = health_check
            
            return health_check
        
        except Exception as e:
            health_check = HealthCheck(
                name=name,
                status=HealthStatus.CRITICAL,
                message=f"Health check error: {e}",
                details={"error": str(e)}
            )
            
            with self._lock:
                self._last_results[name] = health_check
            
            logger.error(f"Health check '{name}' failed: {e}")
            return health_check
    
    def register_check(self, 
                      name: str, 
                      check_func: Callable[[], Union[bool, HealthCheck]],
                      interval: Optional[float] = None):
        """注册健康检查"""
        with self._lock:
            self._checks[name] = check_func
            
            if interval:
                self._intervals[name] = interval
                
                # 如果已经在运行，启动新的定期检查
                if self._running:
                    self._tasks[name] = asyncio.create_task(
                        self._periodic_check(name, interval)
                    )
        
        logger.info(f"Registered health check: {name}" + 
                   (f" (interval: {interval}s)" if interval else ""))
    
    def unregister_check(self, name: str) -> bool:
        """注销健康检查"""
        with self._lock:
            if name not in self._checks:
                return False
            
            # 停止定期检查任务
            if name in self._tasks:
                self._tasks[name].cancel()
                del self._tasks[name]
            
            # 清理数据
            del self._checks[name]
            self._intervals.pop(name, None)
            self._last_results.pop(name, None)
        
        logger.info(f"Unregistered health check: {name}")
        return True
    
    async def get_health_status(self) -> Dict[str, HealthCheck]:
        """获取健康状态"""
        with self._lock:
            check_names = list(self._checks.keys())
        
        results = {}
        for name in check_names:
            results[name] = await self.check_health(name)
        
        return results
    
    def get_last_results(self) -> Dict[str, HealthCheck]:
        """获取最后的检查结果"""
        with self._lock:
            return self._last_results.copy()
    
    async def _periodic_check(self, name: str, interval: float):
        """定期健康检查"""
        while self._running:
            try:
                await self.check_health(name)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic health check '{name}': {e}")
                await asyncio.sleep(min(interval, 60))  # 错误时最多等待60秒


class SimpleAlertManager(IAlertManager):
    """简单告警管理器"""
    
    def __init__(self):
        self._rules: Dict[str, Dict[str, Any]] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: deque = deque(maxlen=1000)
        self._handlers: List[Callable[[Alert], None]] = []
        self._lock = threading.RLock()
    
    async def send_alert(self, alert: Alert):
        """发送告警"""
        alert_key = f"{alert.name}:{alert.source}"
        
        with self._lock:
            self._active_alerts[alert_key] = alert
            self._alert_history.append(alert)
        
        logger.warning(f"Alert: {alert.message} (level: {alert.level.name})")
        
        # 调用处理器
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")
    
    async def resolve_alert(self, alert_name: str, source: str):
        """解决告警"""
        alert_key = f"{alert_name}:{source}"
        
        with self._lock:
            alert = self._active_alerts.get(alert_key)
            if alert:
                alert.resolve()
                del self._active_alerts[alert_key]
                self._alert_history.append(alert)
        
        if alert:
            logger.info(f"Alert resolved: {alert.message}")
            
            # 通知处理器
            for handler in self._handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(alert)
                    else:
                        handler(alert)
                except Exception as e:
                    logger.error(f"Error in alert handler: {e}")
    
    def add_rule(self, 
                name: str, 
                condition: Callable[[List[Metric]], bool],
                alert_template: Alert):
        """添加告警规则"""
        with self._lock:
            self._rules[name] = {
                "condition": condition,
                "template": alert_template
            }
        
        logger.info(f"Added alert rule: {name}")
    
    def remove_rule(self, name: str) -> bool:
        """移除告警规则"""
        with self._lock:
            if name in self._rules:
                del self._rules[name]
                logger.info(f"Removed alert rule: {name}")
                return True
            return False
    
    async def get_active_alerts(self) -> List[Alert]:
        """获取活动告警"""
        with self._lock:
            return list(self._active_alerts.values())
    
    def add_handler(self, handler: Callable[[Alert], None]):
        """添加告警处理器"""
        self._handlers.append(handler)
    
    def remove_handler(self, handler: Callable[[Alert], None]):
        """移除告警处理器"""
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    async def evaluate_rules(self, metrics: List[Metric]):
        """评估告警规则"""
        with self._lock:
            rules = self._rules.copy()
        
        for rule_name, rule_data in rules.items():
            try:
                condition = rule_data["condition"]
                template = rule_data["template"]
                
                if condition(metrics):
                    # 创建告警
                    alert = Alert(
                        name=template.name,
                        level=template.level,
                        message=template.message,
                        source=template.source,
                        labels=template.labels.copy(),
                        annotations=template.annotations.copy()
                    )
                    
                    await self.send_alert(alert)
            
            except Exception as e:
                logger.error(f"Error evaluating rule '{rule_name}': {e}")


class SystemMetricsCollector:
    """系统指标收集器"""
    
    def __init__(self, metrics_collector: IMetricsCollector):
        self.metrics = metrics_collector
        self._collection_task: Optional[asyncio.Task] = None
        self._running = False
        self.collection_interval = 5.0  # 5秒
    
    async def start(self):
        """启动系统指标收集"""
        if self._running:
            return
        
        self._running = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        logger.info("System metrics collector started")
    
    async def stop(self):
        """停止系统指标收集"""
        if not self._running:
            return
        
        self._running = False
        
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        
        logger.info("System metrics collector stopped")
    
    async def _collection_loop(self):
        """指标收集循环"""
        while self._running:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _collect_system_metrics(self):
        """收集系统指标"""
        try:
            # CPU指标
            cpu_percent = psutil.cpu_percent(interval=None)
            self.metrics.set_gauge(SystemMetrics.CPU_USAGE, cpu_percent)
            
            # 内存指标
            memory = psutil.virtual_memory()
            self.metrics.set_gauge(SystemMetrics.MEMORY_USAGE, memory.percent)
            self.metrics.set_gauge(SystemMetrics.MEMORY_AVAILABLE, memory.available / 1024 / 1024)  # MB
            self.metrics.set_gauge(SystemMetrics.MEMORY_TOTAL, memory.total / 1024 / 1024)  # MB
            
            # 磁盘指标
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            self.metrics.set_gauge(SystemMetrics.DISK_USAGE, disk_usage_percent)
            self.metrics.set_gauge(SystemMetrics.DISK_FREE, disk.free / 1024 / 1024 / 1024)  # GB
            
            # 网络指标
            net_io = psutil.net_io_counters()
            self.metrics.set_gauge(SystemMetrics.NETWORK_IN, net_io.bytes_recv)
            self.metrics.set_gauge(SystemMetrics.NETWORK_OUT, net_io.bytes_sent)
            
            # 连接数
            connections = len(psutil.net_connections())
            self.metrics.set_gauge(SystemMetrics.NETWORK_CONNECTIONS, connections)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")


# 内置健康检查
class SystemHealthChecks:
    """系统健康检查集合"""
    
    @staticmethod
    def cpu_usage_check(threshold: float = 90.0) -> Callable[[], HealthCheck]:
        """CPU使用率检查"""
        def check():
            try:
                cpu_percent = psutil.cpu_percent(interval=1.0)
                
                if cpu_percent > threshold:
                    return HealthCheck(
                        name="cpu_usage",
                        status=HealthStatus.CRITICAL,
                        message=f"High CPU usage: {cpu_percent:.1f}%",
                        details={"cpu_percent": cpu_percent, "threshold": threshold}
                    )
                elif cpu_percent > threshold * 0.8:
                    return HealthCheck(
                        name="cpu_usage",
                        status=HealthStatus.WARNING,
                        message=f"Elevated CPU usage: {cpu_percent:.1f}%",
                        details={"cpu_percent": cpu_percent, "threshold": threshold}
                    )
                else:
                    return HealthCheck(
                        name="cpu_usage",
                        status=HealthStatus.HEALTHY,
                        message=f"CPU usage normal: {cpu_percent:.1f}%",
                        details={"cpu_percent": cpu_percent}
                    )
            
            except Exception as e:
                return HealthCheck(
                    name="cpu_usage",
                    status=HealthStatus.UNKNOWN,
                    message=f"Error checking CPU usage: {e}",
                    details={"error": str(e)}
                )
        
        return check
    
    @staticmethod
    def memory_usage_check(threshold: float = 85.0) -> Callable[[], HealthCheck]:
        """内存使用率检查"""
        def check():
            try:
                memory = psutil.virtual_memory()
                
                if memory.percent > threshold:
                    return HealthCheck(
                        name="memory_usage",
                        status=HealthStatus.CRITICAL,
                        message=f"High memory usage: {memory.percent:.1f}%",
                        details={
                            "memory_percent": memory.percent,
                            "memory_used_gb": memory.used / 1024 / 1024 / 1024,
                            "memory_total_gb": memory.total / 1024 / 1024 / 1024,
                            "threshold": threshold
                        }
                    )
                elif memory.percent > threshold * 0.8:
                    return HealthCheck(
                        name="memory_usage",
                        status=HealthStatus.WARNING,
                        message=f"Elevated memory usage: {memory.percent:.1f}%",
                        details={
                            "memory_percent": memory.percent,
                            "memory_used_gb": memory.used / 1024 / 1024 / 1024,
                            "memory_total_gb": memory.total / 1024 / 1024 / 1024
                        }
                    )
                else:
                    return HealthCheck(
                        name="memory_usage",
                        status=HealthStatus.HEALTHY,
                        message=f"Memory usage normal: {memory.percent:.1f}%",
                        details={
                            "memory_percent": memory.percent,
                            "memory_available_gb": memory.available / 1024 / 1024 / 1024
                        }
                    )
            
            except Exception as e:
                return HealthCheck(
                    name="memory_usage",
                    status=HealthStatus.UNKNOWN,
                    message=f"Error checking memory usage: {e}",
                    details={"error": str(e)}
                )
        
        return check
    
    @staticmethod
    def disk_space_check(path: str = "/", threshold: float = 90.0) -> Callable[[], HealthCheck]:
        """磁盘空间检查"""
        def check():
            try:
                disk = psutil.disk_usage(path)
                usage_percent = (disk.used / disk.total) * 100
                
                if usage_percent > threshold:
                    return HealthCheck(
                        name="disk_space",
                        status=HealthStatus.CRITICAL,
                        message=f"Low disk space: {usage_percent:.1f}% used",
                        details={
                            "path": path,
                            "usage_percent": usage_percent,
                            "free_gb": disk.free / 1024 / 1024 / 1024,
                            "total_gb": disk.total / 1024 / 1024 / 1024,
                            "threshold": threshold
                        }
                    )
                elif usage_percent > threshold * 0.8:
                    return HealthCheck(
                        name="disk_space",
                        status=HealthStatus.WARNING,
                        message=f"Disk space getting low: {usage_percent:.1f}% used",
                        details={
                            "path": path,
                            "usage_percent": usage_percent,
                            "free_gb": disk.free / 1024 / 1024 / 1024,
                            "total_gb": disk.total / 1024 / 1024 / 1024
                        }
                    )
                else:
                    return HealthCheck(
                        name="disk_space",
                        status=HealthStatus.HEALTHY,
                        message=f"Disk space OK: {usage_percent:.1f}% used",
                        details={
                            "path": path,
                            "usage_percent": usage_percent,
                            "free_gb": disk.free / 1024 / 1024 / 1024
                        }
                    )
            
            except Exception as e:
                return HealthCheck(
                    name="disk_space",
                    status=HealthStatus.UNKNOWN,
                    message=f"Error checking disk space: {e}",
                    details={"error": str(e), "path": path}
                )
        
        return check
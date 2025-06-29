"""
Aetherius Core 监控诊断系统

提供全面的系统监控和诊断功能，包括：
- 性能指标收集和分析
- 健康检查和状态监控
- 资源使用情况监控
- 错误追踪和告警
- 分布式追踪
- 自定义指标和仪表板
"""

from typing import Any, Dict, List, Optional, Callable, Union, Protocol, TypeVar
from abc import ABC, abstractmethod
from enum import Enum, IntEnum
from dataclasses import dataclass, field
import time
import asyncio
from datetime import datetime, timedelta

__all__ = [
    'MetricType', 'HealthStatus', 'AlertLevel', 'Metric', 'HealthCheck',
    'Alert', 'MonitoringContext', 'IMetricsCollector', 'IHealthChecker',
    'IAlertManager', 'ITracer', 'monitoring', 'health_check', 'alert_on'
]

T = TypeVar('T')


class MetricType(Enum):
    """指标类型枚举"""
    COUNTER = "counter"         # 计数器：只增不减
    GAUGE = "gauge"            # 仪表：可增可减的瞬时值
    HISTOGRAM = "histogram"     # 直方图：分布统计
    SUMMARY = "summary"        # 摘要：分位数统计
    TIMER = "timer"           # 计时器：耗时统计


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"         # 健康
    WARNING = "warning"         # 警告
    CRITICAL = "critical"       # 严重
    UNKNOWN = "unknown"         # 未知


class AlertLevel(IntEnum):
    """告警级别枚举"""
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4
    FATAL = 5


@dataclass
class Metric:
    """指标定义"""
    name: str                           # 指标名称
    type: MetricType                    # 指标类型
    value: float                        # 指标值
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)  # 标签
    unit: Optional[str] = None          # 单位
    description: Optional[str] = None   # 描述
    
    def with_labels(self, **labels) -> 'Metric':
        """添加标签"""
        new_labels = {**self.labels, **labels}
        return Metric(
            name=self.name,
            type=self.type,
            value=self.value,
            timestamp=self.timestamp,
            labels=new_labels,
            unit=self.unit,
            description=self.description
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'type': self.type.value,
            'value': self.value,
            'timestamp': self.timestamp,
            'labels': self.labels,
            'unit': self.unit,
            'description': self.description
        }


@dataclass
class HealthCheck:
    """健康检查结果"""
    name: str                           # 检查名称
    status: HealthStatus                # 健康状态
    message: Optional[str] = None       # 状态消息
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息
    timestamp: float = field(default_factory=time.time)
    duration: Optional[float] = None    # 检查耗时
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp,
            'duration': self.duration
        }


@dataclass
class Alert:
    """告警定义"""
    name: str                           # 告警名称
    level: AlertLevel                   # 告警级别
    message: str                        # 告警消息
    source: str                         # 告警源
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    resolved: bool = False              # 是否已解决
    resolved_at: Optional[float] = None # 解决时间
    
    def resolve(self):
        """标记告警为已解决"""
        self.resolved = True
        self.resolved_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'level': self.level.value,
            'message': self.message,
            'source': self.source,
            'timestamp': self.timestamp,
            'labels': self.labels,
            'annotations': self.annotations,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at
        }


@dataclass
class MonitoringContext:
    """监控上下文"""
    service_name: str                   # 服务名称
    instance_id: str                    # 实例ID
    version: str                        # 版本
    environment: str                    # 环境
    labels: Dict[str, str] = field(default_factory=dict)  # 全局标签
    
    def with_labels(self, **labels) -> 'MonitoringContext':
        """添加标签"""
        new_labels = {**self.labels, **labels}
        return MonitoringContext(
            service_name=self.service_name,
            instance_id=self.instance_id,
            version=self.version,
            environment=self.environment,
            labels=new_labels
        )


class IMetricsCollector(Protocol):
    """指标收集器接口"""
    
    def increment(self, 
                 name: str, 
                 value: float = 1.0, 
                 labels: Optional[Dict[str, str]] = None):
        """递增计数器"""
        ...
    
    def set_gauge(self, 
                 name: str, 
                 value: float, 
                 labels: Optional[Dict[str, str]] = None):
        """设置仪表值"""
        ...
    
    def record_histogram(self, 
                        name: str, 
                        value: float, 
                        labels: Optional[Dict[str, str]] = None):
        """记录直方图数据"""
        ...
    
    def start_timer(self, 
                   name: str, 
                   labels: Optional[Dict[str, str]] = None) -> 'Timer':
        """开始计时"""
        ...
    
    def get_metrics(self, 
                   name_pattern: Optional[str] = None) -> List[Metric]:
        """获取指标"""
        ...


class IHealthChecker(Protocol):
    """健康检查器接口"""
    
    async def check_health(self, name: str) -> HealthCheck:
        """执行健康检查"""
        ...
    
    def register_check(self, 
                      name: str, 
                      check_func: Callable[[], Union[bool, HealthCheck]],
                      interval: Optional[float] = None):
        """注册健康检查"""
        ...
    
    def unregister_check(self, name: str) -> bool:
        """注销健康检查"""
        ...
    
    async def get_health_status(self) -> Dict[str, HealthCheck]:
        """获取健康状态"""
        ...


class IAlertManager(Protocol):
    """告警管理器接口"""
    
    async def send_alert(self, alert: Alert):
        """发送告警"""
        ...
    
    async def resolve_alert(self, alert_name: str, source: str):
        """解决告警"""
        ...
    
    def add_rule(self, 
                name: str, 
                condition: Callable[[List[Metric]], bool],
                alert_template: Alert):
        """添加告警规则"""
        ...
    
    def remove_rule(self, name: str) -> bool:
        """移除告警规则"""
        ...
    
    async def get_active_alerts(self) -> List[Alert]:
        """获取活动告警"""
        ...


class ITracer(Protocol):
    """追踪器接口"""
    
    def start_span(self, 
                  operation_name: str, 
                  parent_span: Optional['Span'] = None) -> 'Span':
        """开始追踪跨度"""
        ...
    
    def inject(self, 
              span: 'Span', 
              carrier: Dict[str, str]):
        """注入追踪上下文"""
        ...
    
    def extract(self, carrier: Dict[str, str]) -> Optional['Span']:
        """提取追踪上下文"""
        ...


class Span:
    """追踪跨度"""
    
    def __init__(self, 
                 operation_name: str, 
                 trace_id: str, 
                 span_id: str,
                 parent_span_id: Optional[str] = None):
        self.operation_name = operation_name
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.tags: Dict[str, Any] = {}
        self.logs: List[Dict[str, Any]] = []
        self.finished = False
    
    def set_tag(self, key: str, value: Any):
        """设置标签"""
        self.tags[key] = value
    
    def log(self, **kwargs):
        """记录日志"""
        log_entry = {
            'timestamp': time.time(),
            **kwargs
        }
        self.logs.append(log_entry)
    
    def finish(self):
        """结束跨度"""
        if not self.finished:
            self.end_time = time.time()
            self.finished = True
    
    @property
    def duration(self) -> Optional[float]:
        """获取持续时间"""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.set_tag('error', True)
            self.log(error=str(exc_val))
        self.finish()


class Timer:
    """计时器"""
    
    def __init__(self, 
                 collector: IMetricsCollector, 
                 name: str, 
                 labels: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.labels = labels or {}
        self.start_time = time.time()
    
    def stop(self) -> float:
        """停止计时并记录"""
        duration = time.time() - self.start_time
        self.collector.record_histogram(self.name, duration, self.labels)
        return duration
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# 装饰器和工具函数

def monitoring(metrics_collector: IMetricsCollector):
    """监控装饰器"""
    def decorator(func):
        func_name = f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                with metrics_collector.start_timer(f"{func_name}.duration"):
                    try:
                        result = await func(*args, **kwargs)
                        metrics_collector.increment(f"{func_name}.calls", labels={"status": "success"})
                        return result
                    except Exception as e:
                        metrics_collector.increment(f"{func_name}.calls", labels={"status": "error"})
                        metrics_collector.increment(f"{func_name}.errors", labels={"error_type": type(e).__name__})
                        raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                with metrics_collector.start_timer(f"{func_name}.duration"):
                    try:
                        result = func(*args, **kwargs)
                        metrics_collector.increment(f"{func_name}.calls", labels={"status": "success"})
                        return result
                    except Exception as e:
                        metrics_collector.increment(f"{func_name}.calls", labels={"status": "error"})
                        metrics_collector.increment(f"{func_name}.errors", labels={"error_type": type(e).__name__})
                        raise
            return sync_wrapper
    
    return decorator


def health_check(name: str, 
                health_checker: IHealthChecker, 
                interval: Optional[float] = None):
    """健康检查装饰器"""
    def decorator(func):
        health_checker.register_check(name, func, interval)
        return func
    return decorator


def alert_on(condition: str, 
            level: AlertLevel = AlertLevel.WARNING,
            alert_manager: Optional[IAlertManager] = None):
    """告警条件装饰器"""
    def decorator(func):
        func._alert_condition = condition
        func._alert_level = level
        func._alert_manager = alert_manager
        return func
    return decorator


# 内置指标定义
class SystemMetrics:
    """系统指标定义"""
    
    # CPU指标
    CPU_USAGE = "system.cpu.usage"
    CPU_LOAD_1M = "system.cpu.load_1m"
    CPU_LOAD_5M = "system.cpu.load_5m"
    CPU_LOAD_15M = "system.cpu.load_15m"
    
    # 内存指标
    MEMORY_USAGE = "system.memory.usage"
    MEMORY_AVAILABLE = "system.memory.available"
    MEMORY_TOTAL = "system.memory.total"
    
    # 磁盘指标
    DISK_USAGE = "system.disk.usage"
    DISK_FREE = "system.disk.free"
    DISK_IO_READ = "system.disk.io.read"
    DISK_IO_WRITE = "system.disk.io.write"
    
    # 网络指标
    NETWORK_IN = "system.network.in"
    NETWORK_OUT = "system.network.out"
    NETWORK_CONNECTIONS = "system.network.connections"


class ApplicationMetrics:
    """应用指标定义"""
    
    # HTTP指标
    HTTP_REQUESTS_TOTAL = "http.requests.total"
    HTTP_REQUEST_DURATION = "http.request.duration"
    HTTP_RESPONSE_SIZE = "http.response.size"
    
    # 数据库指标
    DB_CONNECTIONS_ACTIVE = "db.connections.active"
    DB_CONNECTIONS_IDLE = "db.connections.idle"
    DB_QUERY_DURATION = "db.query.duration"
    
    # 缓存指标
    CACHE_HITS = "cache.hits"
    CACHE_MISSES = "cache.misses"
    CACHE_SIZE = "cache.size"
    
    # 队列指标
    QUEUE_SIZE = "queue.size"
    QUEUE_PROCESSING_TIME = "queue.processing_time"
    
    # 错误指标
    ERRORS_TOTAL = "errors.total"
    EXCEPTIONS_TOTAL = "exceptions.total"


class MinecraftMetrics:
    """Minecraft特定指标"""
    
    # 服务器指标
    SERVER_UPTIME = "minecraft.server.uptime"
    SERVER_TPS = "minecraft.server.tps"
    SERVER_MEMORY_USAGE = "minecraft.server.memory.usage"
    
    # 玩家指标
    PLAYERS_ONLINE = "minecraft.players.online"
    PLAYERS_MAX = "minecraft.players.max"
    PLAYERS_JOINED = "minecraft.players.joined"
    PLAYERS_LEFT = "minecraft.players.left"
    
    # 世界指标
    CHUNKS_LOADED = "minecraft.world.chunks.loaded"
    ENTITIES_COUNT = "minecraft.world.entities.count"
    
    # 性能指标
    TICK_TIME = "minecraft.performance.tick_time"
    MSPT = "minecraft.performance.mspt"  # Milliseconds per tick


# 健康检查定义
class HealthChecks:
    """健康检查定义"""
    
    DATABASE = "database"
    REDIS = "redis"
    SERVER_PROCESS = "server_process"
    DISK_SPACE = "disk_space"
    MEMORY_USAGE = "memory_usage"
    EXTERNAL_API = "external_api"


# 告警规则模板
class AlertTemplates:
    """告警规则模板"""
    
    HIGH_CPU_USAGE = Alert(
        name="high_cpu_usage",
        level=AlertLevel.WARNING,
        message="CPU usage is above 80%",
        source="system_monitor"
    )
    
    HIGH_MEMORY_USAGE = Alert(
        name="high_memory_usage",
        level=AlertLevel.WARNING,
        message="Memory usage is above 85%",
        source="system_monitor"
    )
    
    DISK_SPACE_LOW = Alert(
        name="disk_space_low",
        level=AlertLevel.CRITICAL,
        message="Disk space is below 10%",
        source="system_monitor"
    )
    
    SERVER_DOWN = Alert(
        name="server_down",
        level=AlertLevel.CRITICAL,
        message="Minecraft server is not responding",
        source="health_check"
    )
    
    HIGH_ERROR_RATE = Alert(
        name="high_error_rate",
        level=AlertLevel.ERROR,
        message="Error rate is above 5%",
        source="application_monitor"
    )
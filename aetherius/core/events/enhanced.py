"""
增强事件系统

提供高性能、功能丰富的事件处理框架，支持：
- 异步事件处理
- 事件优先级和调度
- 事件过滤和路由
- 事件持久化和重放
- 事件链和编排
- 性能监控和诊断
- 分布式事件支持
"""

import asyncio
import time
import weakref
import threading
import json
import uuid
from typing import (
    Any, Dict, List, Optional, Callable, Union, TypeVar, Generic, 
    Protocol, runtime_checkable, Set, Tuple, AsyncIterator
)
from abc import ABC, abstractmethod
from enum import Enum, IntEnum
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class EventPriority(IntEnum):
    """事件优先级枚举"""
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100
    CRITICAL = 125  # 系统关键事件


class EventStatus(Enum):
    """事件状态枚举"""
    CREATED = "created"
    DISPATCHING = "dispatching"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class EventDeliveryMode(Enum):
    """事件投递模式"""
    FIRE_AND_FORGET = "fire_and_forget"  # 触发即忘
    RELIABLE = "reliable"                # 可靠投递
    ORDERED = "ordered"                  # 有序投递
    BROADCAST = "broadcast"              # 广播模式
    UNICAST = "unicast"                  # 单播模式


@dataclass
class EventMetadata:
    """事件元数据"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    delivery_mode: EventDeliveryMode = EventDeliveryMode.FIRE_AND_FORGET
    ttl: Optional[float] = None  # 生存时间（秒）
    retry_count: int = 0
    max_retries: int = 3
    tags: Set[str] = field(default_factory=set)
    custom_headers: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """增强事件对象"""
    type: str
    data: Any
    metadata: EventMetadata = field(default_factory=EventMetadata)
    status: EventStatus = EventStatus.CREATED
    
    def __post_init__(self):
        if isinstance(self.metadata, dict):
            self.metadata = EventMetadata(**self.metadata)
    
    @property
    def is_expired(self) -> bool:
        """检查事件是否已过期"""
        if not self.metadata.ttl:
            return False
        return time.time() > self.metadata.timestamp + self.metadata.ttl
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "data": self.data,
            "metadata": asdict(self.metadata),
            "status": self.status.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """从字典创建事件"""
        metadata = EventMetadata(**data.get("metadata", {}))
        status = EventStatus(data.get("status", "created"))
        return cls(
            type=data["type"],
            data=data["data"],
            metadata=metadata,
            status=status
        )


@runtime_checkable
class IEventHandler(Protocol):
    """事件处理器接口"""
    
    async def handle(self, event: Event) -> Any:
        """处理事件"""
        ...
    
    def can_handle(self, event_type: str) -> bool:
        """检查是否可以处理指定类型的事件"""
        ...
    
    @property
    def priority(self) -> EventPriority:
        """处理器优先级"""
        ...


@runtime_checkable
class IEventFilter(Protocol):
    """事件过滤器接口"""
    
    def should_process(self, event: Event) -> bool:
        """检查事件是否应该被处理"""
        ...


@runtime_checkable
class IEventStore(Protocol):
    """事件存储接口"""
    
    async def store_event(self, event: Event) -> bool:
        """存储事件"""
        ...
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        """获取事件"""
        ...
    
    async def get_events(self, 
                        event_type: Optional[str] = None,
                        start_time: Optional[float] = None,
                        end_time: Optional[float] = None,
                        limit: Optional[int] = None) -> List[Event]:
        """查询事件"""
        ...


class EventHandlerRegistration:
    """事件处理器注册信息"""
    
    def __init__(self, 
                 handler: IEventHandler,
                 event_types: List[str],
                 priority: EventPriority = EventPriority.NORMAL,
                 filters: Optional[List[IEventFilter]] = None,
                 async_mode: bool = True,
                 max_concurrent: int = 10):
        self.handler = handler
        self.event_types = set(event_types)
        self.priority = priority
        self.filters = filters or []
        self.async_mode = async_mode
        self.max_concurrent = max_concurrent
        
        # 统计信息
        self.processed_count = 0
        self.error_count = 0
        self.total_processing_time = 0.0
        self.last_processed = None
        
        # 并发控制
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: Set[asyncio.Task] = set()
    
    def can_handle(self, event: Event) -> bool:
        """检查是否可以处理事件"""
        # 检查事件类型
        if event.type not in self.event_types and '*' not in self.event_types:
            return False
        
        # 检查过滤器
        for filter_obj in self.filters:
            if not filter_obj.should_process(event):
                return False
        
        return True
    
    async def handle_event(self, event: Event) -> Any:
        """处理事件"""
        async with self._semaphore:
            start_time = time.time()
            try:
                if self.async_mode:
                    task = asyncio.create_task(self.handler.handle(event))
                    self._active_tasks.add(task)
                    try:
                        result = await task
                    finally:
                        self._active_tasks.discard(task)
                else:
                    # 在线程池中执行同步处理器
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, self.handler.handle, event
                    )
                
                # 更新统计
                self.processed_count += 1
                self.total_processing_time += time.time() - start_time
                self.last_processed = time.time()
                
                return result
            
            except Exception as e:
                self.error_count += 1
                logger.error(f"Error in event handler {self.handler}: {e}")
                raise
    
    async def cancel_active_tasks(self):
        """取消活动任务"""
        if self._active_tasks:
            for task in self._active_tasks:
                task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_time = (self.total_processing_time / self.processed_count 
                   if self.processed_count > 0 else 0)
        return {
            "handler": str(self.handler),
            "event_types": list(self.event_types),
            "priority": self.priority.value,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "avg_processing_time": avg_time,
            "last_processed": self.last_processed,
            "active_tasks": len(self._active_tasks)
        }


class EnhancedEventBus:
    """增强事件总线"""
    
    def __init__(self, 
                 max_queue_size: int = 10000,
                 max_workers: int = 50,
                 enable_persistence: bool = False,
                 event_store: Optional[IEventStore] = None):
        self.max_queue_size = max_queue_size
        self.max_workers = max_workers
        self.enable_persistence = enable_persistence
        self.event_store = event_store
        
        # 处理器注册表
        self._handlers: Dict[str, List[EventHandlerRegistration]] = defaultdict(list)
        self._global_handlers: List[EventHandlerRegistration] = []
        self._handler_lock = threading.RLock()
        
        # 事件队列和处理
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._priority_queues: Dict[EventPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in EventPriority
        }
        
        # 工作线程池
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._worker_tasks: List[asyncio.Task] = []
        
        # 事件路由和过滤
        self._event_routers: List[Callable[[Event], str]] = []
        self._global_filters: List[IEventFilter] = []
        
        # 监控和统计
        self._stats = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "events_dropped": 0,
            "handlers_registered": 0
        }
        self._event_history: deque = deque(maxlen=1000)
        
        # 分布式支持
        self._remote_buses: Dict[str, 'IRemoteEventBus'] = {}
        
        # 状态管理
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    async def start(self):
        """启动事件总线"""
        if self._running:
            return
        
        self._running = True
        self._shutdown_event.clear()
        
        # 启动工作协程
        for i in range(self.max_workers):
            task = asyncio.create_task(self._event_worker(f"worker_{i}"))
            self._worker_tasks.append(task)
        
        # 启动优先级处理器
        for priority in EventPriority:
            task = asyncio.create_task(self._priority_worker(priority))
            self._worker_tasks.append(task)
        
        logger.info(f"Event bus started with {len(self._worker_tasks)} workers")
    
    async def stop(self):
        """停止事件总线"""
        if not self._running:
            return
        
        self._running = False
        self._shutdown_event.set()
        
        # 等待工作协程完成
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            self._worker_tasks.clear()
        
        # 取消所有活动的处理器任务
        with self._handler_lock:
            for handlers in self._handlers.values():
                for registration in handlers:
                    await registration.cancel_active_tasks()
            
            for registration in self._global_handlers:
                await registration.cancel_active_tasks()
        
        # 关闭线程池
        self._thread_pool.shutdown(wait=True)
        
        logger.info("Event bus stopped")
    
    async def publish(self, 
                     event_type: str, 
                     data: Any,
                     metadata: Optional[EventMetadata] = None,
                     wait_for_completion: bool = False) -> str:
        """发布事件"""
        if not self._running:
            raise RuntimeError("Event bus is not running")
        
        # 创建事件
        if metadata is None:
            metadata = EventMetadata()
        
        event = Event(
            type=event_type,
            data=data,
            metadata=metadata
        )
        
        # 应用全局过滤器
        for filter_obj in self._global_filters:
            if not filter_obj.should_process(event):
                logger.debug(f"Event {event.metadata.event_id} filtered out")
                return event.metadata.event_id
        
        # 路由事件
        routed_type = self._route_event(event)
        if routed_type != event_type:
            event.type = routed_type
        
        # 持久化事件
        if self.enable_persistence and self.event_store:
            await self.event_store.store_event(event)
        
        # 加入队列
        try:
            if event.metadata.priority == EventPriority.CRITICAL:
                # 关键事件直接处理
                await self._process_event_immediately(event)
            else:
                # 根据优先级加入对应队列
                queue = self._priority_queues[event.metadata.priority]
                queue.put_nowait(event)
            
            self._stats["events_published"] += 1
            self._event_history.append({
                "event_id": event.metadata.event_id,
                "type": event.type,
                "timestamp": event.metadata.timestamp,
                "status": "published"
            })
            
            if wait_for_completion:
                # 等待事件处理完成
                return await self._wait_for_event_completion(event)
            
            return event.metadata.event_id
        
        except asyncio.QueueFull:
            self._stats["events_dropped"] += 1
            logger.warning(f"Event queue full, dropping event {event.metadata.event_id}")
            raise RuntimeError("Event queue is full")
    
    def subscribe(self, 
                 event_types: Union[str, List[str]], 
                 handler: Union[IEventHandler, Callable],
                 priority: EventPriority = EventPriority.NORMAL,
                 filters: Optional[List[IEventFilter]] = None,
                 async_mode: bool = True,
                 max_concurrent: int = 10) -> str:
        """订阅事件"""
        if isinstance(event_types, str):
            event_types = [event_types]
        
        # 包装函数式处理器
        if not isinstance(handler, IEventHandler):
            handler = FunctionEventHandler(handler, priority)
        
        registration = EventHandlerRegistration(
            handler=handler,
            event_types=event_types,
            priority=priority,
            filters=filters,
            async_mode=async_mode,
            max_concurrent=max_concurrent
        )
        
        with self._handler_lock:
            if '*' in event_types:
                self._global_handlers.append(registration)
            else:
                for event_type in event_types:
                    self._handlers[event_type].append(registration)
                    # 按优先级排序
                    self._handlers[event_type].sort(
                        key=lambda x: x.priority.value, reverse=True
                    )
        
        self._stats["handlers_registered"] += 1
        
        # 返回注册ID
        registration_id = str(uuid.uuid4())
        registration._registration_id = registration_id
        
        logger.debug(f"Subscribed handler {handler} to events {event_types}")
        return registration_id
    
    def unsubscribe(self, registration_id: str) -> bool:
        """取消订阅"""
        with self._handler_lock:
            # 在全局处理器中查找
            for i, registration in enumerate(self._global_handlers):
                if getattr(registration, '_registration_id', None) == registration_id:
                    del self._global_handlers[i]
                    asyncio.create_task(registration.cancel_active_tasks())
                    return True
            
            # 在特定事件类型处理器中查找
            for event_type, handlers in self._handlers.items():
                for i, registration in enumerate(handlers):
                    if getattr(registration, '_registration_id', None) == registration_id:
                        del handlers[i]
                        asyncio.create_task(registration.cancel_active_tasks())
                        return True
        
        return False
    
    def add_global_filter(self, filter_obj: IEventFilter):
        """添加全局过滤器"""
        self._global_filters.append(filter_obj)
    
    def add_event_router(self, router: Callable[[Event], str]):
        """添加事件路由器"""
        self._event_routers.append(router)
    
    async def replay_events(self, 
                           start_time: Optional[float] = None,
                           end_time: Optional[float] = None,
                           event_types: Optional[List[str]] = None):
        """重放事件"""
        if not self.event_store:
            raise RuntimeError("Event store not configured")
        
        events = await self.event_store.get_events(
            event_type=event_types[0] if event_types and len(event_types) == 1 else None,
            start_time=start_time,
            end_time=end_time
        )
        
        logger.info(f"Replaying {len(events)} events")
        
        for event in events:
            if event_types and event.type not in event_types:
                continue
            
            # 重新发布事件
            await self.publish(
                event.type,
                event.data,
                event.metadata
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        handler_stats = []
        
        with self._handler_lock:
            for handlers in self._handlers.values():
                for registration in handlers:
                    handler_stats.append(registration.get_stats())
            
            for registration in self._global_handlers:
                handler_stats.append(registration.get_stats())
        
        return {
            **self._stats,
            "queue_size": self._event_queue.qsize(),
            "priority_queue_sizes": {
                priority.name: queue.qsize() 
                for priority, queue in self._priority_queues.items()
            },
            "handlers": handler_stats,
            "recent_events": list(self._event_history)
        }
    
    # 私有方法
    
    async def _event_worker(self, worker_name: str):
        """事件工作协程"""
        logger.debug(f"Event worker {worker_name} started")
        
        while self._running:
            try:
                # 从主队列获取事件
                event = await asyncio.wait_for(
                    self._event_queue.get(), timeout=1.0
                )
                
                await self._process_event(event)
                self._event_queue.task_done()
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in event worker {worker_name}: {e}")
        
        logger.debug(f"Event worker {worker_name} stopped")
    
    async def _priority_worker(self, priority: EventPriority):
        """优先级队列工作协程"""
        queue = self._priority_queues[priority]
        
        while self._running:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                
                if priority == EventPriority.CRITICAL:
                    # 关键事件立即处理
                    await self._process_event(event)
                else:
                    # 其他事件加入主队列
                    await self._event_queue.put(event)
                
                queue.task_done()
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in priority worker {priority.name}: {e}")
    
    async def _process_event(self, event: Event):
        """处理单个事件"""
        if event.is_expired:
            logger.debug(f"Event {event.metadata.event_id} expired")
            return
        
        event.status = EventStatus.PROCESSING
        start_time = time.time()
        
        try:
            # 获取处理器
            handlers = await self._get_event_handlers(event)
            
            if not handlers:
                logger.debug(f"No handlers for event {event.type}")
                return
            
            # 并发处理
            tasks = []
            for registration in handlers:
                if registration.can_handle(event):
                    task = asyncio.create_task(registration.handle_event(event))
                    tasks.append(task)
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 检查处理结果
                failed_count = sum(1 for result in results if isinstance(result, Exception))
                if failed_count > 0:
                    logger.warning(f"Event {event.metadata.event_id} had {failed_count} failed handlers")
                    event.status = EventStatus.FAILED
                    self._stats["events_failed"] += 1
                else:
                    event.status = EventStatus.COMPLETED
                    self._stats["events_processed"] += 1
            
            # 更新事件历史
            self._event_history.append({
                "event_id": event.metadata.event_id,
                "type": event.type,
                "timestamp": event.metadata.timestamp,
                "status": event.status.value,
                "processing_time": time.time() - start_time,
                "handlers_count": len(tasks)
            })
        
        except Exception as e:
            event.status = EventStatus.FAILED
            self._stats["events_failed"] += 1
            logger.error(f"Error processing event {event.metadata.event_id}: {e}")
    
    async def _process_event_immediately(self, event: Event):
        """立即处理事件（用于关键事件）"""
        await self._process_event(event)
    
    async def _get_event_handlers(self, event: Event) -> List[EventHandlerRegistration]:
        """获取事件处理器"""
        handlers = []
        
        with self._handler_lock:
            # 添加全局处理器
            handlers.extend(self._global_handlers)
            
            # 添加特定事件类型处理器
            if event.type in self._handlers:
                handlers.extend(self._handlers[event.type])
        
        return handlers
    
    def _route_event(self, event: Event) -> str:
        """路由事件"""
        for router in self._event_routers:
            try:
                routed_type = router(event)
                if routed_type and routed_type != event.type:
                    logger.debug(f"Event {event.metadata.event_id} routed from {event.type} to {routed_type}")
                    return routed_type
            except Exception as e:
                logger.error(f"Error in event router: {e}")
        
        return event.type
    
    async def _wait_for_event_completion(self, event: Event) -> str:
        """等待事件处理完成"""
        # 这里可以实现更复杂的等待逻辑
        # 简单实现：等待一小段时间
        await asyncio.sleep(0.1)
        return event.metadata.event_id


class FunctionEventHandler:
    """函数式事件处理器包装器"""
    
    def __init__(self, func: Callable, priority: EventPriority = EventPriority.NORMAL):
        self.func = func
        self._priority = priority
    
    async def handle(self, event: Event) -> Any:
        """处理事件"""
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(event)
        else:
            return self.func(event)
    
    def can_handle(self, event_type: str) -> bool:
        """检查是否可以处理指定类型的事件"""
        return True  # 函数式处理器默认可以处理所有事件
    
    @property
    def priority(self) -> EventPriority:
        """处理器优先级"""
        return self._priority
    
    def __str__(self):
        return f"FunctionHandler({self.func.__name__})"


# 内置过滤器

class EventTypeFilter:
    """事件类型过滤器"""
    
    def __init__(self, allowed_types: Set[str]):
        self.allowed_types = allowed_types
    
    def should_process(self, event: Event) -> bool:
        return event.type in self.allowed_types


class EventTagFilter:
    """事件标签过滤器"""
    
    def __init__(self, required_tags: Set[str], match_all: bool = True):
        self.required_tags = required_tags
        self.match_all = match_all
    
    def should_process(self, event: Event) -> bool:
        event_tags = event.metadata.tags
        
        if self.match_all:
            return self.required_tags.issubset(event_tags)
        else:
            return bool(self.required_tags.intersection(event_tags))


class EventSourceFilter:
    """事件源过滤器"""
    
    def __init__(self, allowed_sources: Set[str]):
        self.allowed_sources = allowed_sources
    
    def should_process(self, event: Event) -> bool:
        return event.metadata.source in self.allowed_sources


# 内置事件存储

class MemoryEventStore:
    """内存事件存储"""
    
    def __init__(self, max_events: int = 10000):
        self.max_events = max_events
        self._events: Dict[str, Event] = {}
        self._events_by_type: Dict[str, List[Event]] = defaultdict(list)
        self._events_by_time: List[Event] = []
        self._lock = threading.RLock()
    
    async def store_event(self, event: Event) -> bool:
        """存储事件"""
        with self._lock:
            # 存储事件
            self._events[event.metadata.event_id] = event
            self._events_by_type[event.type].append(event)
            self._events_by_time.append(event)
            
            # 限制存储数量
            if len(self._events_by_time) > self.max_events:
                # 移除最旧的事件
                oldest_event = self._events_by_time.pop(0)
                del self._events[oldest_event.metadata.event_id]
                self._events_by_type[oldest_event.type].remove(oldest_event)
        
        return True
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        """获取事件"""
        with self._lock:
            return self._events.get(event_id)
    
    async def get_events(self, 
                        event_type: Optional[str] = None,
                        start_time: Optional[float] = None,
                        end_time: Optional[float] = None,
                        limit: Optional[int] = None) -> List[Event]:
        """查询事件"""
        with self._lock:
            if event_type:
                events = self._events_by_type.get(event_type, [])
            else:
                events = self._events_by_time
            
            # 时间过滤
            if start_time or end_time:
                filtered_events = []
                for event in events:
                    timestamp = event.metadata.timestamp
                    if start_time and timestamp < start_time:
                        continue
                    if end_time and timestamp > end_time:
                        continue
                    filtered_events.append(event)
                events = filtered_events
            
            # 限制数量
            if limit:
                events = events[-limit:]
            
            return events.copy()
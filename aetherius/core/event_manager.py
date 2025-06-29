"""Event management system for Aetherius."""

import asyncio
import logging
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional, TypeVar

from .events_base import BaseEvent, EventPriority

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseEvent)


class EventListener:
    """Represents an event listener with metadata."""

    def __init__(
        self,
        callback: Callable[[BaseEvent], Any],
        event_type: type[BaseEvent],
        priority: EventPriority = EventPriority.NORMAL,
        ignore_cancelled: bool = False,
    ):
        self.callback = callback
        self.event_type = event_type
        self.priority = priority
        self.ignore_cancelled = ignore_cancelled
        self.is_async = asyncio.iscoroutinefunction(callback)

    async def call(self, event: BaseEvent) -> Any:
        """Call the listener with the given event."""
        if event.is_cancelled() and not self.ignore_cancelled:
            return None

        try:
            if self.is_async:
                return await self.callback(event)
            else:
                return self.callback(event)
        except Exception as e:
            logger.error(
                f"Error in event listener {self.callback.__name__}: {e}", exc_info=True
            )
            return None


class EventManager:
    """
    Manages event registration, firing, and lifecycle.

    This class provides a high-performance async event system with support for:
    - Priority-based event handling
    - Event cancellation
    - Decorator-based listener registration
    - Async and sync listener support
    """

    def __init__(self):
        # 原有初始化
        self._listeners: dict[type[BaseEvent], list[EventListener]] = defaultdict(list)
        self._global_listeners: list[EventListener] = []
        self._event_stats: dict[str, int] = defaultdict(int)
        self._running = True

        # Web组件扩展
        self._event_history: deque = deque(maxlen=1000)  # 事件历史记录
        self._web_subscribers: dict[str, set[str]] = defaultdict(set)  # Web订阅者
        self._real_time_events: set[str] = set()  # 实时事件类型
        self._event_filters: dict[str, Callable] = {}  # 事件过滤器

        # 性能监控
        self._event_timing: dict[str, list[float]] = defaultdict(list)
        self._slow_event_threshold = 1.0  # 慢事件阈值（秒）

    def register_listener(
        self,
        event_type: type[T],
        callback: Callable[[T], Any],
        priority: EventPriority = EventPriority.NORMAL,
        ignore_cancelled: bool = False,
    ) -> EventListener:
        """
        Register an event listener.

        Args:
            event_type: The type of event to listen for
            callback: The callback function to call when the event is fired
            priority: Priority level for the listener
            ignore_cancelled: Whether to call this listener even if the event is cancelled

        Returns:
            EventListener: The created listener object
        """
        listener = EventListener(callback, event_type, priority, ignore_cancelled)

        # Insert listener in priority order (highest first)
        listeners = self._listeners[event_type]
        inserted = False

        for i, existing_listener in enumerate(listeners):
            if listener.priority.value > existing_listener.priority.value:
                listeners.insert(i, listener)
                inserted = True
                break

        if not inserted:
            listeners.append(listener)

        logger.debug(
            f"Registered event listener for {event_type.__name__} with priority {priority.name}"
        )
        return listener

    def unregister_listener(self, listener: EventListener) -> bool:
        """
        Unregister an event listener.

        Args:
            listener: The listener to remove

        Returns:
            bool: True if the listener was found and removed
        """
        for event_type, listeners in self._listeners.items():
            if listener in listeners:
                listeners.remove(listener)
                logger.debug(f"Unregistered event listener for {event_type.__name__}")
                return True

        if listener in self._global_listeners:
            self._global_listeners.remove(listener)
            logger.debug("Unregistered global event listener")
            return True

        return False

    def register_global_listener(
        self,
        callback: Callable[[BaseEvent], Any],
        priority: EventPriority = EventPriority.NORMAL,
        ignore_cancelled: bool = False,
    ) -> EventListener:
        """
        Register a global event listener that receives all events.

        Args:
            callback: The callback function to call for any event
            priority: Priority level for the listener
            ignore_cancelled: Whether to call this listener even if the event is cancelled

        Returns:
            EventListener: The created listener object
        """
        listener = EventListener(callback, BaseEvent, priority, ignore_cancelled)

        # Insert in priority order
        inserted = False
        for i, existing_listener in enumerate(self._global_listeners):
            if listener.priority.value > existing_listener.priority.value:
                self._global_listeners.insert(i, listener)
                inserted = True
                break

        if not inserted:
            self._global_listeners.append(listener)

        logger.debug(f"Registered global event listener with priority {priority.name}")
        return listener

    async def fire_event(self, event: BaseEvent) -> BaseEvent:
        """
        Fire an event to all registered listeners.

        Args:
            event: The event to fire

        Returns:
            BaseEvent: The event object (potentially modified by listeners)
        """
        if not self._running:
            return event

        event_type = type(event)
        event_name = event_type.__name__

        logger.debug(f"Firing event: {event_name}")
        self._event_stats[event_name] += 1

        # Collect all applicable listeners
        applicable_listeners: list[EventListener] = []

        # Add specific event type listeners
        applicable_listeners.extend(self._listeners.get(event_type, []))

        # Add listeners for parent event types
        for base_type in event_type.__mro__[1:]:  # Skip the event type itself
            if issubclass(base_type, BaseEvent) and base_type != BaseEvent:
                applicable_listeners.extend(self._listeners.get(base_type, []))

        # Add global listeners
        applicable_listeners.extend(self._global_listeners)

        # Sort by priority (highest first)
        applicable_listeners.sort(key=lambda l: l.priority.value, reverse=True)

        # Call all listeners
        for listener in applicable_listeners:
            if not self._running:
                break

            try:
                await listener.call(event)
            except Exception as e:
                logger.error(f"Error calling event listener: {e}", exc_info=True)

            # If event was cancelled, stop processing lower priority listeners
            # unless they specifically ignore cancellation
            if event.is_cancelled() and not listener.ignore_cancelled:
                logger.debug(f"Event {event_name} was cancelled, stopping propagation")
                break

        return event

    def get_listeners(
        self, event_type: Optional[type[BaseEvent]] = None
    ) -> list[EventListener]:
        """
        Get all listeners for a specific event type or all listeners.

        Args:
            event_type: The event type to get listeners for, or None for all

        Returns:
            List[EventListener]: List of listeners
        """
        if event_type is None:
            # Return all listeners
            all_listeners = []
            for listeners in self._listeners.values():
                all_listeners.extend(listeners)
            all_listeners.extend(self._global_listeners)
            return all_listeners
        else:
            return self._listeners.get(event_type, []).copy()

    def get_event_stats(self) -> dict[str, int]:
        """Get statistics about fired events."""
        return dict(self._event_stats)

    def clear_stats(self) -> None:
        """Clear event statistics."""
        self._event_stats.clear()

    def shutdown(self) -> None:
        """Shutdown the event manager."""
        self._running = False
        logger.info("Event manager shutdown")

    def add_to_history(self, event: BaseEvent, processing_time: float = None):
        """
        将事件添加到历史记录

        Args:
            event: 事件对象
            processing_time: 处理时间（秒）
        """
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event.__class__.__name__,
            "event_data": self._serialize_event_data(event),
            "processing_time": processing_time,
            "source": getattr(event, "source", None),
        }

        self._event_history.append(event_data)

        # 记录处理时间
        if processing_time is not None:
            self._event_timing[event.__class__.__name__].append(processing_time)

            # 检查慢事件
            if processing_time > self._slow_event_threshold:
                logger.warning(
                    f"Slow event detected: {event.__class__.__name__} took {processing_time:.3f}s"
                )

    def _serialize_event_data(self, event: BaseEvent) -> dict[str, Any]:
        """
        序列化事件数据用于存储

        Args:
            event: 事件对象

        Returns:
            序列化后的事件数据
        """
        try:
            # 尝试使用事件的内置序列化方法
            if hasattr(event, "to_dict"):
                return event.to_dict()

            # 否则序列化公共属性
            data = {}
            for attr_name in dir(event):
                if not attr_name.startswith("_") and not callable(
                    getattr(event, attr_name)
                ):
                    try:
                        value = getattr(event, attr_name)
                        # 只包含基本类型
                        if isinstance(
                            value, (str, int, float, bool, list, dict, type(None))
                        ):
                            data[attr_name] = value
                        else:
                            data[attr_name] = str(value)
                    except Exception:
                        continue

            return data

        except Exception as e:
            logger.warning(
                f"Failed to serialize event data for {event.__class__.__name__}: {e}"
            )
            return {"error": "serialization_failed"}

    def get_event_history(
        self, event_type: str = None, limit: int = 100, since: datetime = None
    ) -> list[dict[str, Any]]:
        """
        获取事件历史记录

        Args:
            event_type: 事件类型过滤器
            limit: 返回的最大事件数
            since: 时间过滤器

        Returns:
            事件历史记录列表
        """
        events = list(self._event_history)

        # 时间过滤
        if since:
            events = [
                e for e in events if datetime.fromisoformat(e["timestamp"]) >= since
            ]

        # 事件类型过滤
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]

        # 限制数量并按时间倒序
        events = events[-limit:] if len(events) > limit else events
        return list(reversed(events))

    def subscribe_to_events(self, subscriber_id: str, event_types: list[str]):
        """
        为Web客户端订阅事件

        Args:
            subscriber_id: 订阅者ID
            event_types: 要订阅的事件类型列表
        """
        for event_type in event_types:
            self._web_subscribers[event_type].add(subscriber_id)

        logger.debug(f"Subscriber {subscriber_id} subscribed to events: {event_types}")

    def unsubscribe_from_events(
        self, subscriber_id: str, event_types: list[str] = None
    ):
        """
        取消Web客户端的事件订阅

        Args:
            subscriber_id: 订阅者ID
            event_types: 要取消订阅的事件类型列表，None表示全部
        """
        if event_types is None:
            # 取消所有订阅
            for subscribers in self._web_subscribers.values():
                subscribers.discard(subscriber_id)
        else:
            for event_type in event_types:
                self._web_subscribers[event_type].discard(subscriber_id)

        logger.debug(f"Subscriber {subscriber_id} unsubscribed from events")

    def get_subscribers(self, event_type: str) -> set[str]:
        """
        获取特定事件类型的订阅者

        Args:
            event_type: 事件类型

        Returns:
            订阅者ID集合
        """
        return self._web_subscribers.get(event_type, set()).copy()

    def set_real_time_events(self, event_types: list[str]):
        """
        设置需要实时推送的事件类型

        Args:
            event_types: 事件类型列表
        """
        self._real_time_events = set(event_types)
        logger.info(f"Real-time events set to: {event_types}")

    def is_real_time_event(self, event_type: str) -> bool:
        """
        检查事件是否为实时事件

        Args:
            event_type: 事件类型

        Returns:
            是否为实时事件
        """
        return event_type in self._real_time_events

    def add_event_filter(
        self, event_type: str, filter_func: Callable[[BaseEvent], bool]
    ):
        """
        为特定事件类型添加过滤器

        Args:
            event_type: 事件类型
            filter_func: 过滤函数，返回True表示通过
        """
        self._event_filters[event_type] = filter_func
        logger.debug(f"Added filter for event type: {event_type}")

    def remove_event_filter(self, event_type: str):
        """
        移除事件过滤器

        Args:
            event_type: 事件类型
        """
        self._event_filters.pop(event_type, None)
        logger.debug(f"Removed filter for event type: {event_type}")

    def should_process_event(self, event: BaseEvent) -> bool:
        """
        检查事件是否应该被处理（通过过滤器）

        Args:
            event: 事件对象

        Returns:
            是否应该处理
        """
        event_type = event.__class__.__name__
        filter_func = self._event_filters.get(event_type)

        if filter_func:
            try:
                return filter_func(event)
            except Exception as e:
                logger.warning(f"Event filter error for {event_type}: {e}")
                return True  # 过滤器出错时默认通过

        return True  # 没有过滤器时默认通过

    def get_performance_stats(self) -> dict[str, Any]:
        """
        获取事件系统性能统计

        Returns:
            性能统计信息
        """
        stats = {
            "total_events_fired": sum(self._event_stats.values()),
            "event_counts": dict(self._event_stats),
            "timing_stats": {},
            "slow_events": [],
            "total_listeners": sum(
                len(listeners) for listeners in self._listeners.values()
            ),
            "global_listeners": len(self._global_listeners),
            "web_subscribers": {
                event_type: len(subscribers)
                for event_type, subscribers in self._web_subscribers.items()
            },
        }

        # 计算时间统计
        for event_type, times in self._event_timing.items():
            if times:
                stats["timing_stats"][event_type] = {
                    "count": len(times),
                    "avg_time": sum(times) / len(times),
                    "max_time": max(times),
                    "min_time": min(times),
                }

                # 检查慢事件
                slow_times = [t for t in times if t > self._slow_event_threshold]
                if slow_times:
                    stats["slow_events"].append(
                        {
                            "event_type": event_type,
                            "slow_count": len(slow_times),
                            "avg_slow_time": sum(slow_times) / len(slow_times),
                        }
                    )

        return stats

    def clear_performance_data(self):
        """清除性能数据"""
        self._event_timing.clear()
        self._event_history.clear()
        self.clear_stats()
        logger.info("Performance data cleared")

    async def fire_event_enhanced(self, event: BaseEvent) -> BaseEvent:
        """
        增强的事件触发方法，包含Web组件支持

        Args:
            event: 要触发的事件

        Returns:
            处理后的事件对象
        """
        start_time = datetime.now()

        # 检查过滤器
        if not self.should_process_event(event):
            logger.debug(f"Event {event.__class__.__name__} filtered out")
            return event

        # 调用原有的事件处理
        processed_event = await self.fire_event(event)

        # 计算处理时间
        processing_time = (datetime.now() - start_time).total_seconds()

        # 添加到历史记录
        self.add_to_history(processed_event, processing_time)

        # 如果是实时事件，通知Web订阅者
        event_type = event.__class__.__name__
        if self.is_real_time_event(event_type):
            await self._notify_web_subscribers(event_type, processed_event)

        return processed_event

    async def _notify_web_subscribers(self, event_type: str, event: BaseEvent):
        """
        通知Web订阅者有新事件

        Args:
            event_type: 事件类型
            event: 事件对象
        """
        subscribers = self.get_subscribers(event_type)
        if not subscribers:
            return

        # 这里应该通过WebSocket或其他机制通知Web客户端
        # 具体实现依赖于Web组件
        event_data = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": self._serialize_event_data(event),
        }

        logger.debug(
            f"Notifying {len(subscribers)} web subscribers of {event_type} event"
        )

        # 如果存在Web组件管理器，委托给它处理
        # 这将在Web组件中实现具体的通知逻辑
        if hasattr(self, "_web_notifier"):
            try:
                await self._web_notifier(subscribers, event_data)
            except Exception as e:
                logger.error(f"Error notifying web subscribers: {e}")

    def set_web_notifier(self, notifier_func: Callable):
        """
        设置Web通知函数

        Args:
            notifier_func: 通知函数
        """
        self._web_notifier = notifier_func
        logger.info("Web notifier function set")


# Global event manager instance
_event_manager: EventManager | None = None


def get_event_manager() -> EventManager:
    """Get the global event manager instance."""
    global _event_manager
    if _event_manager is None:
        _event_manager = EventManager()
    return _event_manager


def set_event_manager(manager: EventManager) -> None:
    """Set the global event manager instance."""
    global _event_manager
    _event_manager = manager


# Decorator for easy event listener registration
def on_event(
    event_type: type[T],
    priority: EventPriority = EventPriority.NORMAL,
    ignore_cancelled: bool = False,
) -> Callable[[Callable[[T], Any]], Callable[[T], Any]]:
    """
    Decorator to register a function as an event listener.

    Args:
        event_type: The type of event to listen for
        priority: Priority level for the listener
        ignore_cancelled: Whether to call this listener even if the event is cancelled

    Example:
        @on_event(PlayerJoinEvent)
        async def handle_player_join(event: PlayerJoinEvent):
            print(f"Player {event.player_name} joined!")
    """

    def decorator(func: Callable[[T], Any]) -> Callable[[T], Any]:
        # Register the listener immediately
        get_event_manager().register_listener(
            event_type, func, priority, ignore_cancelled
        )

        # Add metadata to the function for introspection
        func._event_listener = True
        func._event_type = event_type
        func._event_priority = priority
        func._ignore_cancelled = ignore_cancelled

        return func

    return decorator


def on_any_event(
    priority: EventPriority = EventPriority.NORMAL, ignore_cancelled: bool = False
) -> Callable[[Callable[[BaseEvent], Any]], Callable[[BaseEvent], Any]]:
    """
    Decorator to register a function as a global event listener.

    Args:
        priority: Priority level for the listener
        ignore_cancelled: Whether to call this listener even if the event is cancelled

    Example:
        @on_any_event()
        async def log_all_events(event: BaseEvent):
            print(f"Event fired: {type(event).__name__}")
    """

    def decorator(func: Callable[[BaseEvent], Any]) -> Callable[[BaseEvent], Any]:
        # Register the listener immediately
        get_event_manager().register_global_listener(func, priority, ignore_cancelled)

        # Add metadata to the function for introspection
        func._global_event_listener = True
        func._event_priority = priority
        func._ignore_cancelled = ignore_cancelled

        return func

    return decorator


# Convenience functions
async def fire_event(event: BaseEvent) -> BaseEvent:
    """Fire an event using the global event manager."""
    return await get_event_manager().fire_event(event)


def register_listener(
    event_type: type[T],
    callback: Callable[[T], Any],
    priority: EventPriority = EventPriority.NORMAL,
    ignore_cancelled: bool = False,
) -> EventListener:
    """Register an event listener using the global event manager."""
    return get_event_manager().register_listener(
        event_type, callback, priority, ignore_cancelled
    )

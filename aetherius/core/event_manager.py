"""Event management system for Aetherius."""

import asyncio
import inspect
import logging
from collections import defaultdict
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union

from .events import BaseEvent, EventPriority

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseEvent)


class EventListener:
    """Represents an event listener with metadata."""
    
    def __init__(
        self,
        callback: Callable[[BaseEvent], Any],
        event_type: Type[BaseEvent],
        priority: EventPriority = EventPriority.NORMAL,
        ignore_cancelled: bool = False
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
            logger.error(f"Error in event listener {self.callback.__name__}: {e}", exc_info=True)
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
        self._listeners: Dict[Type[BaseEvent], List[EventListener]] = defaultdict(list)
        self._global_listeners: List[EventListener] = []
        self._event_stats: Dict[str, int] = defaultdict(int)
        self._running = True
    
    def register_listener(
        self,
        event_type: Type[T],
        callback: Callable[[T], Any],
        priority: EventPriority = EventPriority.NORMAL,
        ignore_cancelled: bool = False
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
        
        logger.debug(f"Registered event listener for {event_type.__name__} with priority {priority.name}")
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
        ignore_cancelled: bool = False
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
        applicable_listeners: List[EventListener] = []
        
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
    
    def get_listeners(self, event_type: Optional[Type[BaseEvent]] = None) -> List[EventListener]:
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
    
    def get_event_stats(self) -> Dict[str, int]:
        """Get statistics about fired events."""
        return dict(self._event_stats)
    
    def clear_stats(self) -> None:
        """Clear event statistics."""
        self._event_stats.clear()
    
    def shutdown(self) -> None:
        """Shutdown the event manager."""
        self._running = False
        logger.info("Event manager shutdown")


# Global event manager instance
_event_manager: Optional[EventManager] = None


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
    event_type: Type[T],
    priority: EventPriority = EventPriority.NORMAL,
    ignore_cancelled: bool = False
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
        get_event_manager().register_listener(event_type, func, priority, ignore_cancelled)
        
        # Add metadata to the function for introspection
        func._event_listener = True
        func._event_type = event_type
        func._event_priority = priority
        func._ignore_cancelled = ignore_cancelled
        
        return func
    
    return decorator


def on_any_event(
    priority: EventPriority = EventPriority.NORMAL,
    ignore_cancelled: bool = False
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
    event_type: Type[T],
    callback: Callable[[T], Any],
    priority: EventPriority = EventPriority.NORMAL,
    ignore_cancelled: bool = False
) -> EventListener:
    """Register an event listener using the global event manager."""
    return get_event_manager().register_listener(event_type, callback, priority, ignore_cancelled)
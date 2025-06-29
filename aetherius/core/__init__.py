"""Core modules for Aetherius engine."""

# Core event system
from .event_manager import EventManager, fire_event, get_event_manager, on_event
from .events_base import *

# Core server components  
from .log_parser import LogParser

# Import only what's absolutely necessary to avoid circular imports
# Other components should be imported directly when needed

__all__ = [
    # Core event system
    "EventManager",
    "get_event_manager", 
    "on_event",
    "fire_event",
    "LogParser",
    # All event classes from events.py
]

# Add all event classes to __all__ dynamically
import sys
_current_module = sys.modules[__name__]
for name in dir(_current_module):
    if name.endswith('Event') and not name.startswith('_'):
        __all__.append(name)

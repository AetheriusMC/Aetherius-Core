"""Component management system for Aetherius.

This module provides the component management system that allows
loading and managing heavy-weight official components.

Components are different from plugins in that they:
- Are official parts of the Aetherius ecosystem
- Have complex dependency management
- Can provide services to other components
- Are designed for heavy-weight functionality like web dashboards, databases, etc.
"""

from .loader import ComponentManager
from .state import ComponentState

__all__ = ["ComponentManager", "ComponentState"]

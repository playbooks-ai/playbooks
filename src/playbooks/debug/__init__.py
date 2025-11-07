"""Debug system for real-time playbook inspection.

This module provides debugging capabilities for playbook execution,
including event inspection, server-based debugging, and real-time
monitoring of agent and playbook state.
"""

from playbooks.core.events import Event as DebugEvent
from .debug_handler import DebugHandler
from .server import DebugServer

__all__ = [
    "DebugServer",
    "DebugHandler",
    "DebugEvent",
]

"""
Meeting system for multi-agent coordination.

This module provides classes and utilities for managing meetings between agents,
including meeting lifecycle management, message routing, and participant coordination.
"""

from .meeting import Meeting, Message
from .meeting_manager import MeetingManager
from .meeting_message_handler import MeetingMessageHandler
from .meeting_registry import MeetingRegistry

__all__ = [
    "Meeting",
    "Message",
    "MeetingManager",
    "MeetingMessageHandler",
    "MeetingRegistry",
]

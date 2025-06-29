"""
Simple message structure for threaded agents.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SimpleMessage:
    """Simple message structure for agent communication."""

    sender_id: str
    content: str
    message_type: str = "direct"
    meeting_id: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

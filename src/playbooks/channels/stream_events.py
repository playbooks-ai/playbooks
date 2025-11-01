"""Stream event classes for channel-based streaming communication."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..message import Message


@dataclass
class StreamStartEvent:
    """Event emitted when a stream starts."""

    stream_id: str
    sender_id: str
    sender_klass: Optional[str] = None
    receiver_spec: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate event data."""
        if not self.stream_id:
            raise ValueError("stream_id is required")
        if not self.sender_id:
            raise ValueError("sender_id is required")


@dataclass
class StreamChunkEvent:
    """Event emitted when a chunk of streaming content is available."""

    stream_id: str
    chunk: str
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate event data."""
        if not self.stream_id:
            raise ValueError("stream_id is required")
        if self.chunk is None:
            raise ValueError("chunk cannot be None")


@dataclass
class StreamCompleteEvent:
    """Event emitted when a stream completes."""

    stream_id: str
    final_message: Message
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate event data."""
        if not self.stream_id:
            raise ValueError("stream_id is required")
        if not self.final_message:
            raise ValueError("final_message is required")

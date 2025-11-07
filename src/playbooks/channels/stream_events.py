"""Stream event classes for channel-based streaming communication."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from playbooks.core.message import Message


@dataclass
class StreamStartEvent:
    """Event emitted when a stream starts."""

    stream_id: str
    sender_id: str
    sender_klass: Optional[str] = None
    receiver_spec: Optional[str] = None
    recipient_id: Optional[str] = None  # Resolved recipient ID
    recipient_klass: Optional[str] = None  # Resolved recipient class
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate event data.

        Raises:
            ValueError: If required fields are missing
        """
        if not self.stream_id:
            raise ValueError("stream_id is required")
        if not self.sender_id:
            raise ValueError("sender_id is required")


@dataclass
class StreamChunkEvent:
    """Event emitted when a chunk of streaming content is available."""

    stream_id: str
    chunk: str
    recipient_id: Optional[str] = None  # Target human ID for filtering
    meeting_id: Optional[str] = None  # Meeting context if applicable
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate event data.

        Raises:
            ValueError: If required fields are missing or invalid
        """
        if not self.stream_id:
            raise ValueError("stream_id is required")
        if self.chunk is None:
            raise ValueError("chunk cannot be None")


@dataclass
class StreamCompleteEvent:
    """Event emitted when a stream completes."""

    stream_id: str
    final_message: Message
    recipient_id: Optional[str] = None  # Target human ID for filtering
    meeting_id: Optional[str] = None  # Meeting context if applicable
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate event data.

        Raises:
            ValueError: If required fields are missing
        """
        if not self.stream_id:
            raise ValueError("stream_id is required")
        if not self.final_message:
            raise ValueError("final_message is required")

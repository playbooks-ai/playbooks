"""Stream result type for explicit control flow in streaming operations."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StreamResult:
    """Result of initiating a stream operation.

    This makes the control flow explicit:
    - should_stream=True: Streaming was started, use stream_id to track it
    - should_stream=False: Streaming was skipped (e.g., agent-to-agent communication)

    This avoids the confusing pattern of returning None to mean "skip streaming".
    """

    stream_id: Optional[str]
    should_stream: bool

    @classmethod
    def start(cls, stream_id: str) -> "StreamResult":
        """Create a result indicating streaming was started.

        Args:
            stream_id: Unique identifier for the stream

        Returns:
            StreamResult with should_stream=True
        """
        return cls(stream_id=stream_id, should_stream=True)

    @classmethod
    def skip(cls) -> "StreamResult":
        """Create a result indicating streaming was skipped.

        Returns:
            StreamResult with should_stream=False and stream_id=None
        """
        return cls(stream_id=None, should_stream=False)

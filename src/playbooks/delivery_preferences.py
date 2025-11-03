"""Delivery preferences for human agents.

This module defines the DeliveryPreferences dataclass that configures how messages
are delivered to human agents. Supports streaming, buffering, and custom handlers.
"""

from dataclasses import dataclass
from typing import Callable, Literal, Optional


@dataclass
class DeliveryPreferences:
    """Delivery preferences for how messages are delivered to a human agent.

    Attributes:
        channel: Primary delivery channel (streaming, buffered, custom)
        streaming_enabled: Whether to enable character-by-character streaming
        streaming_chunk_size: Characters per streaming chunk (default 1 for char-by-char)
        buffer_messages: Whether to accumulate messages before delivery
        buffer_timeout: Seconds to wait before flushing buffer
        meeting_notifications: Meeting notification mode
            - "all": Receive all meeting messages
            - "targeted": Only when mentioned/targeted
            - "none": No meeting notifications
        custom_handler: Optional custom delivery handler function

    Examples:
        # Real-time streaming
        DeliveryPreferences(channel="streaming", streaming_enabled=True)

        # Buffered delivery
        DeliveryPreferences(
            channel="buffered",
            streaming_enabled=False,
            buffer_messages=True,
            buffer_timeout=60.0
        )

        # Custom handler
        DeliveryPreferences(
            channel="custom",
            custom_handler=my_sms_handler
        )
    """

    # Primary delivery channel
    channel: Literal["streaming", "buffered", "custom"] = "streaming"

    # Streaming configuration
    streaming_enabled: bool = True
    streaming_chunk_size: int = 1  # Characters per chunk

    # Buffering configuration
    buffer_messages: bool = False
    buffer_timeout: float = 5.0  # Seconds

    # Meeting configuration
    meeting_notifications: Literal["all", "targeted", "none"] = "targeted"

    # Custom handler
    custom_handler: Optional[Callable] = None

    def __post_init__(self) -> None:
        """Validate delivery preferences after initialization.

        Ensures channel-specific settings are properly configured and validates
        all numeric parameters.
        """
        # Validate channel-specific settings
        if self.channel == "streaming":
            if not self.streaming_enabled:
                # If channel is streaming but streaming disabled, enable it
                object.__setattr__(self, "streaming_enabled", True)

        if self.channel == "buffered":
            # Buffered channel doesn't stream
            if self.streaming_enabled:
                object.__setattr__(self, "streaming_enabled", False)
            # Buffered channel requires buffering
            if not self.buffer_messages:
                object.__setattr__(self, "buffer_messages", True)

        if self.channel == "custom":
            if self.custom_handler is None:
                raise ValueError(
                    "custom_handler must be provided when channel='custom'"
                )

        # Validate chunk size
        if self.streaming_chunk_size < 1:
            raise ValueError("streaming_chunk_size must be >= 1")

        # Validate buffer timeout
        if self.buffer_timeout < 0:
            raise ValueError("buffer_timeout must be >= 0")

    @classmethod
    def streaming_default(cls) -> "DeliveryPreferences":
        """Create default preferences for real-time streaming."""
        return cls(
            channel="streaming",
            streaming_enabled=True,
            streaming_chunk_size=1,
            buffer_messages=False,
            meeting_notifications="targeted",
        )

    @classmethod
    def buffered_default(cls, timeout: float = 60.0) -> "DeliveryPreferences":
        """Create default preferences for buffered delivery.

        Args:
            timeout: Buffer timeout in seconds (default 60)
        """
        return cls(
            channel="buffered",
            streaming_enabled=False,
            buffer_messages=True,
            buffer_timeout=timeout,
            meeting_notifications="targeted",
        )

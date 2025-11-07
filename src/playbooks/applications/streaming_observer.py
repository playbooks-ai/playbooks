"""Shared streaming observer for channel-based message streaming.

This module provides a unified ChannelStreamObserver implementation that can be
used by both CLI (agent_chat) and web applications (web_server). The observer
subscribes to channels and receives streaming events, delegating display logic
to subclass implementations.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from playbooks.channels.stream_events import (
    StreamChunkEvent,
    StreamCompleteEvent,
    StreamStartEvent,
)
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.core.events import ChannelCreatedEvent

if TYPE_CHECKING:
    from playbooks.program import Program


class ChannelStreamObserver(ABC):
    """Base observer for channel streaming events.

    Handles subscription to channels and receives streaming events. Subclasses
    implement display-specific logic (terminal output, WebSocket broadcast, etc.).
    """

    def __init__(
        self,
        program: "Program",
        streaming_enabled: bool = True,
        target_human_id: str = None,
    ):
        """Initialize the stream observer.

        Args:
            program: The Program instance to observe
            streaming_enabled: Whether to display streaming output incrementally
            target_human_id: Optional human ID to filter streams (None = receive all)
        """
        self.program = program
        self.streaming_enabled = streaming_enabled
        self.target_human_id = target_human_id
        self.subscribed_channels = set()

        # Subscribe to channel creation events
        self.program.event_bus.subscribe(
            ChannelCreatedEvent, self._on_channel_created_event
        )

    def _on_channel_created_event(self, event: ChannelCreatedEvent) -> None:
        """Event handler for channel creation events.

        This is a synchronous handler to ensure the observer is subscribed
        to channels immediately when they are created, before any streaming begins.

        Args:
            event: ChannelCreatedEvent containing channel information
        """
        channel = self.program.channels.get(event.channel_id)
        if channel and channel.channel_id not in self.subscribed_channels:
            channel.add_stream_observer(self)
            self.subscribed_channels.add(channel.channel_id)
            debug(f"ChannelStreamObserver: Subscribed to channel {channel.channel_id}")

    async def subscribe_to_all_channels(self) -> None:
        """Subscribe to all existing channels.

        Called during initialization to subscribe to channels created before
        the observer was registered.
        """
        for channel_id, channel in self.program.channels.items():
            if channel_id not in self.subscribed_channels:
                channel.add_stream_observer(self)
                self.subscribed_channels.add(channel_id)
                debug(
                    f"ChannelStreamObserver: Subscribed to existing channel {channel_id}"
                )

    async def on_stream_start(self, event: StreamStartEvent) -> None:
        """Handle stream start event.

        Args:
            event: Stream start event containing sender/recipient info
        """
        sender = self.program.agents_by_id.get(event.sender_id)
        agent_name = sender.klass if sender else "Agent"

        if self.streaming_enabled:
            await self._display_start(event, agent_name)

    async def on_stream_chunk(self, event: StreamChunkEvent) -> None:
        """Handle stream chunk event.

        Args:
            event: Stream chunk event containing content
        """
        if self.streaming_enabled:
            await self._display_chunk(event)

    async def on_stream_complete(self, event: StreamCompleteEvent) -> None:
        """Handle stream completion event.

        Args:
            event: Stream complete event containing final message
        """
        if self.streaming_enabled:
            await self._display_complete(event)
        else:
            # Non-streaming mode: display complete message now
            await self._display_buffered(event)

    @abstractmethod
    async def _display_start(self, event: StreamStartEvent, agent_name: str) -> None:
        """Display stream start (subclass implements display logic).

        Args:
            event: Stream start event
            agent_name: Name of the sending agent
        """
        pass

    @abstractmethod
    async def _display_chunk(self, event: StreamChunkEvent) -> None:
        """Display stream chunk (subclass implements display logic).

        Args:
            event: Stream chunk event
        """
        pass

    @abstractmethod
    async def _display_complete(self, event: StreamCompleteEvent) -> None:
        """Display stream completion (subclass implements display logic).

        Args:
            event: Stream complete event
        """
        pass

    @abstractmethod
    async def _display_buffered(self, event: StreamCompleteEvent) -> None:
        """Display buffered complete message (non-streaming mode).

        Args:
            event: Stream complete event
        """
        pass

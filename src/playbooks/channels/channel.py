"""Unified Channel class for all communication types."""

import uuid
from typing import List, Optional, Protocol

from ..message import Message
from .participant import Participant
from .stream_events import StreamChunkEvent, StreamCompleteEvent, StreamStartEvent


class MessageObserver(Protocol):
    """Protocol for observers of complete messages."""

    async def on_message(self, message: Message) -> None:
        """Called when a complete message is sent through the channel."""
        ...


class StreamObserver(Protocol):
    """Protocol for observers of streaming content."""

    async def on_stream_start(self, event: StreamStartEvent) -> None:
        """Called when a stream starts."""
        ...

    async def on_stream_chunk(self, event: StreamChunkEvent) -> None:
        """Called when a chunk of streaming content is available."""
        ...

    async def on_stream_complete(self, event: StreamCompleteEvent) -> None:
        """Called when a stream completes."""
        ...


class Channel:
    """Universal communication channel for any number of participants.

    A single Channel class handles all communication types:
    - 1 participant: Direct message (though typically 2 participants)
    - 2 participants: Conversation
    - N participants: Meeting

    Humans are just participants - delivery is polymorphic via the Participant interface.

    Key features:
    - Unified interface for all communication types
    - Streaming support built-in
    - Observable pattern for monitoring and display
    - Polymorphic delivery via Participant interface
    """

    def __init__(self, channel_id: str, participants: List[Participant]):
        """Initialize a channel.

        Args:
            channel_id: Unique identifier for this channel
            participants: List of participants in this channel
        """
        if not channel_id:
            raise ValueError("channel_id is required")
        if not participants:
            raise ValueError("at least one participant is required")

        self.channel_id = channel_id
        self.participants = participants
        self.observers: List[MessageObserver] = []
        self.stream_observers: List[StreamObserver] = []

        # Active streams tracking
        self._active_streams: dict = {}

    def add_participant(self, participant: Participant) -> None:
        """Add a participant to the channel.

        Args:
            participant: The participant to add
        """
        if participant not in self.participants:
            self.participants.append(participant)

    def remove_participant(self, participant: Participant) -> None:
        """Remove a participant from the channel.

        Args:
            participant: The participant to remove
        """
        if participant in self.participants:
            self.participants.remove(participant)

    def add_observer(self, observer: MessageObserver) -> None:
        """Add an observer to receive message events.

        Args:
            observer: The observer to add
        """
        if observer not in self.observers:
            self.observers.append(observer)

    def remove_observer(self, observer: MessageObserver) -> None:
        """Remove an observer.

        Args:
            observer: The observer to remove
        """
        if observer in self.observers:
            self.observers.remove(observer)

    def add_stream_observer(self, observer: StreamObserver) -> None:
        """Add an observer to receive streaming events.

        Args:
            observer: The observer to add
        """
        if observer not in self.stream_observers:
            self.stream_observers.append(observer)

    def remove_stream_observer(self, observer: StreamObserver) -> None:
        """Remove a streaming observer.

        Args:
            observer: The observer to remove
        """
        if observer in self.stream_observers:
            self.stream_observers.remove(observer)

    def get_participant(self, participant_id: str) -> Optional[Participant]:
        """Get a participant by ID.

        Args:
            participant_id: ID of the participant to find

        Returns:
            The participant if found, None otherwise
        """
        for participant in self.participants:
            if participant.id == participant_id:
                return participant
        return None

    async def send(self, message: Message, sender_id: str) -> None:
        """Send a message to all participants except the sender.

        Args:
            message: The message to send
            sender_id: ID of the sender (excluded from delivery)
        """
        # Deliver to all participants except sender
        for participant in self.participants:
            if participant.id != sender_id:
                await participant.deliver(message)

        # Notify observers
        for observer in self.observers:
            await observer.on_message(message)

    async def start_stream(
        self,
        sender_id: str,
        sender_klass: Optional[str] = None,
        receiver_spec: Optional[str] = None,
    ) -> str:
        """Start a streaming session.

        Args:
            sender_id: ID of the sender
            sender_klass: Class/type of the sender
            receiver_spec: Receiver specification (for context)

        Returns:
            stream_id: Unique identifier for this stream
        """
        stream_id = str(uuid.uuid4())

        # Track active stream
        self._active_streams[stream_id] = {
            "sender_id": sender_id,
            "sender_klass": sender_klass,
            "receiver_spec": receiver_spec,
            "chunks": [],
        }

        # Notify observers
        event = StreamStartEvent(
            stream_id=stream_id,
            sender_id=sender_id,
            sender_klass=sender_klass,
            receiver_spec=receiver_spec,
        )

        for observer in self.stream_observers:
            await observer.on_stream_start(event)

        return stream_id

    async def stream_chunk(self, stream_id: str, chunk: str) -> None:
        """Stream a chunk of content.

        Args:
            stream_id: ID of the stream
            chunk: Content chunk to stream
        """
        if stream_id not in self._active_streams:
            raise ValueError(f"Stream {stream_id} not found or already completed")

        # Track chunk
        self._active_streams[stream_id]["chunks"].append(chunk)

        # Notify observers
        event = StreamChunkEvent(stream_id=stream_id, chunk=chunk)

        for observer in self.stream_observers:
            await observer.on_stream_chunk(event)

    async def complete_stream(self, stream_id: str, final_message: Message) -> None:
        """Complete a streaming session and deliver the final message.

        Args:
            stream_id: ID of the stream
            final_message: Complete message to deliver
        """
        if stream_id not in self._active_streams:
            raise ValueError(f"Stream {stream_id} not found or already completed")

        # Get stream metadata
        stream_info = self._active_streams.pop(stream_id)
        sender_id = stream_info["sender_id"]

        # Notify observers of stream completion
        event = StreamCompleteEvent(stream_id=stream_id, final_message=final_message)

        for observer in self.stream_observers:
            await observer.on_stream_complete(event)

        # Deliver the complete message
        await self.send(final_message, sender_id)

    @property
    def participant_count(self) -> int:
        """Get the number of participants in this channel."""
        return len(self.participants)

    @property
    def is_direct(self) -> bool:
        """Check if this is a direct channel (2 participants)."""
        return self.participant_count == 2

    @property
    def is_meeting(self) -> bool:
        """Check if this is a meeting channel (>2 participants)."""
        return self.participant_count > 2

    def __repr__(self) -> str:
        participant_info = ", ".join([repr(p) for p in self.participants])
        return f"Channel({self.channel_id}, [{participant_info}])"

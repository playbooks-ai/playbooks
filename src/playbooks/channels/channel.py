"""Unified Channel class for all communication types."""

from typing import List, Optional, Protocol

from playbooks.core.message import Message

from .participant import Participant
from .stream_events import StreamChunkEvent, StreamCompleteEvent, StreamStartEvent


class StreamObserver(Protocol):
    """Protocol for observers of streaming content.

    Stream observers can optionally specify a target_human_id to filter
    which streams they receive. If target_human_id is None, the observer
    receives all streams (backward compatible behavior).
    """

    @property
    def target_human_id(self) -> Optional[str]:
        """Optional human ID this observer is for.

        Returns:
            Human agent ID to filter by, or None to receive all streams
        """
        return None

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

    def __init__(self, channel_id: str, participants: List[Participant]) -> None:
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

    def _should_notify_observer(
        self, observer: StreamObserver, recipient_id: Optional[str]
    ) -> bool:
        """Check if an observer should be notified about a stream event.

        Filters observers based on their target_human_id property:
        - If observer.target_human_id is None: Notify (receives all streams)
        - If recipient_id is None: Notify (broadcast to all)
        - Otherwise: Notify only if observer.target_human_id matches recipient_id

        Args:
            observer: The stream observer to check
            recipient_id: The recipient ID from the stream event

        Returns:
            True if observer should be notified, False otherwise
        """
        # Check if observer has target_human_id property
        observer_target = getattr(observer, "target_human_id", None)

        # Observer wants all streams (backward compatible)
        if observer_target is None:
            return True

        # Stream has no specific recipient (broadcast)
        if recipient_id is None:
            return True

        # Match observer's target to stream's recipient
        return observer_target == recipient_id

    async def start_stream(
        self,
        stream_id: str,
        sender_id: str,
        sender_klass: Optional[str] = None,
        receiver_spec: Optional[str] = None,
        recipient_id: Optional[str] = None,
        recipient_klass: Optional[str] = None,
    ) -> str:
        """Start a streaming session.

        Args:
            stream_id: Unique identifier for this stream (caller-provided)
            sender_id: ID of the sender
            sender_klass: Class/type of the sender
            receiver_spec: Receiver specification (for context)
            recipient_id: Resolved recipient ID
            recipient_klass: Resolved recipient class

        Returns:
            stream_id: The same stream_id that was passed in
        """
        # Track active stream with recipient info for filtering
        self._active_streams[stream_id] = {
            "sender_id": sender_id,
            "sender_klass": sender_klass,
            "receiver_spec": receiver_spec,
            "recipient_id": recipient_id,
            "chunks": [],
        }

        # Notify observers with filtering
        event = StreamStartEvent(
            stream_id=stream_id,
            sender_id=sender_id,
            sender_klass=sender_klass,
            receiver_spec=receiver_spec,
            recipient_id=recipient_id,
            recipient_klass=recipient_klass,
        )

        for observer in self.stream_observers:
            if self._should_notify_observer(observer, recipient_id):
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

        # Get recipient info from active stream for filtering
        stream_info = self._active_streams[stream_id]
        recipient_id = stream_info.get("recipient_id")

        # Notify observers with filtering
        event = StreamChunkEvent(
            stream_id=stream_id,
            chunk=chunk,
            recipient_id=recipient_id,
        )

        for observer in self.stream_observers:
            if self._should_notify_observer(observer, recipient_id):
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
        recipient_id = stream_info.get("recipient_id")

        # Notify observers of stream completion with filtering
        event = StreamCompleteEvent(
            stream_id=stream_id,
            final_message=final_message,
            recipient_id=recipient_id,
        )

        for observer in self.stream_observers:
            if self._should_notify_observer(observer, recipient_id):
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

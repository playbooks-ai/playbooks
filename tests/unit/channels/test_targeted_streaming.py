"""Tests for targeted streaming with observer filtering."""

import pytest

from playbooks.channels.channel import Channel
from playbooks.channels.stream_events import (
    StreamChunkEvent,
    StreamCompleteEvent,
    StreamStartEvent,
)
from playbooks.channels.participant import HumanParticipant
from playbooks.core.identifiers import AgentID
from playbooks.core.message import Message, MessageType


class MockStreamObserver:
    """Mock stream observer for testing filtering."""

    def __init__(self, target_human_id=None):
        self.target_human_id = target_human_id
        self.events_received = []

    async def on_stream_start(self, event: StreamStartEvent) -> None:
        self.events_received.append(("start", event))

    async def on_stream_chunk(self, event: StreamChunkEvent) -> None:
        self.events_received.append(("chunk", event))

    async def on_stream_complete(self, event: StreamCompleteEvent) -> None:
        self.events_received.append(("complete", event))


class TestObserverFiltering:
    """Test observer filtering based on target_human_id."""

    def test_should_notify_observer_with_no_target(self):
        """Observer with no target receives all streams."""
        # Create channel with mock participant
        mock_participant = HumanParticipant("human", "Human")
        channel = Channel("test_channel", [mock_participant])
        observer = MockStreamObserver(target_human_id=None)

        # Should notify for any recipient
        assert channel._should_notify_observer(observer, "human_alice")
        assert channel._should_notify_observer(observer, "human_bob")
        assert channel._should_notify_observer(observer, None)

    def test_should_notify_observer_with_target_match(self):
        """Observer receives streams targeted to them."""
        mock_participant = HumanParticipant("human", "Human")
        channel = Channel("test_channel", [mock_participant])
        observer = MockStreamObserver(target_human_id="human_alice")

        # Should notify when recipient matches
        assert channel._should_notify_observer(observer, "human_alice")

        # Should not notify when recipient doesn't match
        assert not channel._should_notify_observer(observer, "human_bob")

    def test_should_notify_observer_with_broadcast(self):
        """All observers receive broadcast streams (recipient_id=None)."""
        mock_participant = HumanParticipant("human", "Human")
        channel = Channel("test_channel", [mock_participant])
        observer_alice = MockStreamObserver(target_human_id="human_alice")
        observer_bob = MockStreamObserver(target_human_id="human_bob")

        # Broadcast (None) should notify all observers
        assert channel._should_notify_observer(observer_alice, None)
        assert channel._should_notify_observer(observer_bob, None)

    @pytest.mark.asyncio
    async def test_filtered_streaming_to_specific_human(self):
        """Stream events are filtered to specific human observer."""
        mock_participant = HumanParticipant("human", "Human")
        channel = Channel("test_channel", [mock_participant])

        # Create observers for different humans
        observer_alice = MockStreamObserver(target_human_id="human_alice")
        observer_bob = MockStreamObserver(target_human_id="human_bob")
        observer_all = MockStreamObserver(target_human_id=None)

        channel.add_stream_observer(observer_alice)
        channel.add_stream_observer(observer_bob)
        channel.add_stream_observer(observer_all)

        # Start stream targeted to Alice
        await channel.start_stream(
            stream_id="stream_1",
            sender_id="agent_1",
            sender_klass="Agent",
            receiver_spec="Alice",
            recipient_id="human_alice",
            recipient_klass="Alice",
        )

        # Stream chunks
        await channel.stream_chunk("stream_1", "Hello ")
        await channel.stream_chunk("stream_1", "Alice!")

        # Complete stream
        final_msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Agent",
            recipient_id=AgentID("human_alice"),
            recipient_klass="Alice",
            content="Hello Alice!",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
        await channel.complete_stream("stream_1", final_msg)

        # Alice observer should receive all events
        assert len(observer_alice.events_received) == 4  # start + 2 chunks + complete
        assert observer_alice.events_received[0][0] == "start"
        assert observer_alice.events_received[1][0] == "chunk"
        assert observer_alice.events_received[2][0] == "chunk"
        assert observer_alice.events_received[3][0] == "complete"

        # Bob observer should receive NO events (different target)
        assert len(observer_bob.events_received) == 0

        # All observer should receive all events (target_human_id=None)
        assert len(observer_all.events_received) == 4

    @pytest.mark.asyncio
    async def test_broadcast_stream_notifies_all_observers(self):
        """Broadcast stream (recipient_id=None) notifies all observers."""
        mock_participant = HumanParticipant("human", "Human")
        channel = Channel("test_channel", [mock_participant])

        observer_alice = MockStreamObserver(target_human_id="human_alice")
        observer_bob = MockStreamObserver(target_human_id="human_bob")

        channel.add_stream_observer(observer_alice)
        channel.add_stream_observer(observer_bob)

        # Start broadcast stream (no specific recipient)
        await channel.start_stream(
            stream_id="stream_broadcast",
            sender_id="agent_1",
            sender_klass="Agent",
            receiver_spec="meeting 1",
            recipient_id=None,  # Broadcast
            recipient_klass=None,
        )

        await channel.stream_chunk("stream_broadcast", "Broadcast!")

        final_msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Agent",
            recipient_id=None,  # Broadcast has no specific recipient
            recipient_klass=None,
            content="Broadcast!",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id=None,
        )
        await channel.complete_stream("stream_broadcast", final_msg)

        # Both observers should receive all events
        assert len(observer_alice.events_received) == 3  # start + chunk + complete
        assert len(observer_bob.events_received) == 3


class TestStreamEventFields:
    """Test that stream events include recipient info."""

    @pytest.mark.asyncio
    async def test_stream_start_event_has_recipient_id(self):
        """StreamStartEvent includes recipient_id."""
        mock_participant = HumanParticipant("human", "Human")
        channel = Channel("test_channel", [mock_participant])
        observer = MockStreamObserver()
        channel.add_stream_observer(observer)

        await channel.start_stream(
            stream_id="stream_1",
            sender_id="agent_1",
            sender_klass="Agent",
            receiver_spec="Alice",
            recipient_id="human_alice",
            recipient_klass="Alice",
        )

        assert len(observer.events_received) == 1
        event_type, event = observer.events_received[0]
        assert event_type == "start"
        assert event.recipient_id == "human_alice"

    @pytest.mark.asyncio
    async def test_stream_chunk_event_has_recipient_id(self):
        """StreamChunkEvent includes recipient_id."""
        mock_participant = HumanParticipant("human", "Human")
        channel = Channel("test_channel", [mock_participant])
        observer = MockStreamObserver()
        channel.add_stream_observer(observer)

        # Start stream
        await channel.start_stream(
            stream_id="stream_1",
            sender_id="agent_1",
            recipient_id="human_bob",
        )

        # Stream chunk
        await channel.stream_chunk("stream_1", "Test")

        # Find chunk event
        chunk_events = [e for e in observer.events_received if e[0] == "chunk"]
        assert len(chunk_events) == 1
        _, event = chunk_events[0]
        assert event.recipient_id == "human_bob"

    @pytest.mark.asyncio
    async def test_stream_complete_event_has_recipient_id(self):
        """StreamCompleteEvent includes recipient_id."""
        mock_participant = HumanParticipant("human", "Human")
        channel = Channel("test_channel", [mock_participant])
        observer = MockStreamObserver()
        channel.add_stream_observer(observer)

        # Start stream
        await channel.start_stream(
            stream_id="stream_1",
            sender_id="agent_1",
            recipient_id="human_carol",
        )

        # Complete stream
        final_msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Agent",
            recipient_id=AgentID("human_carol"),
            recipient_klass="Carol",
            content="Done",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
        await channel.complete_stream("stream_1", final_msg)

        # Find complete event
        complete_events = [e for e in observer.events_received if e[0] == "complete"]
        assert len(complete_events) == 1
        _, event = complete_events[0]
        assert event.recipient_id == "human_carol"

"""Unit tests for the unified Channel class."""

import pytest

from playbooks.channels import Channel
from playbooks.channels.participant import Participant
from playbooks.channels.stream_events import (
    StreamChunkEvent,
    StreamCompleteEvent,
    StreamStartEvent,
)
from playbooks.message import Message, MessageType


class MockParticipant(Participant):
    """Mock participant for testing."""

    def __init__(self, participant_id: str, participant_klass: str = "mock"):
        self._id = participant_id
        self._klass = participant_klass
        self.delivered_messages = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def klass(self) -> str:
        return self._klass

    async def deliver(self, message: Message) -> None:
        self.delivered_messages.append(message)


class MockMessageObserver:
    """Mock message observer for testing."""

    def __init__(self):
        self.messages = []

    async def on_message(self, message: Message) -> None:
        self.messages.append(message)


class MockStreamObserver:
    """Mock stream observer for testing."""

    def __init__(self):
        self.stream_starts = []
        self.stream_chunks = []
        self.stream_completes = []

    async def on_stream_start(self, event: StreamStartEvent) -> None:
        self.stream_starts.append(event)

    async def on_stream_chunk(self, event: StreamChunkEvent) -> None:
        self.stream_chunks.append(event)

    async def on_stream_complete(self, event: StreamCompleteEvent) -> None:
        self.stream_completes.append(event)


@pytest.fixture
def participants():
    """Create test participants."""
    return [
        MockParticipant("agent1", "TestAgent"),
        MockParticipant("agent2", "TestAgent"),
        MockParticipant("human", "human"),
    ]


@pytest.fixture
def channel(participants):
    """Create a test channel."""
    return Channel("test_channel", participants)


@pytest.fixture
def sample_message():
    """Create a sample message."""
    return Message(
        sender_id="agent1",
        sender_klass="TestAgent",
        recipient_id="agent2",
        recipient_klass="TestAgent",
        message_type=MessageType.DIRECT,
        content="Test message",
        meeting_id=None,
    )


class TestChannelInit:
    """Test channel initialization."""

    def test_create_channel_with_participants(self, participants):
        """Test creating a channel with participants."""
        channel = Channel("test", participants)
        assert channel.channel_id == "test"
        assert len(channel.participants) == 3
        assert channel.participant_count == 3

    def test_create_channel_requires_id(self, participants):
        """Test that channel_id is required."""
        with pytest.raises(ValueError, match="channel_id is required"):
            Channel("", participants)

    def test_create_channel_requires_participants(self):
        """Test that at least one participant is required."""
        with pytest.raises(ValueError, match="at least one participant is required"):
            Channel("test", [])

    def test_direct_channel_property(self):
        """Test is_direct property for 2-participant channels."""
        p1 = MockParticipant("p1")
        p2 = MockParticipant("p2")
        channel = Channel("direct", [p1, p2])

        assert channel.is_direct is True
        assert channel.is_meeting is False

    def test_meeting_channel_property(self):
        """Test is_meeting property for N-participant channels."""
        participants = [MockParticipant(f"p{i}") for i in range(5)]
        channel = Channel("meeting", participants)

        assert channel.is_direct is False
        assert channel.is_meeting is True


class TestChannelObserverManagement:
    """Test observer management."""

    def test_add_observer(self, channel):
        """Test adding a message observer."""
        observer = MockMessageObserver()
        initial_count = len(channel.observers)

        channel.add_observer(observer)

        assert len(channel.observers) == initial_count + 1
        assert observer in channel.observers

    def test_add_duplicate_observer_ignored(self, channel):
        """Test that adding a duplicate observer is ignored."""
        observer = MockMessageObserver()
        channel.add_observer(observer)
        initial_count = len(channel.observers)

        channel.add_observer(observer)

        assert len(channel.observers) == initial_count

    def test_remove_observer(self, channel):
        """Test removing a message observer."""
        observer = MockMessageObserver()
        channel.add_observer(observer)
        initial_count = len(channel.observers)

        channel.remove_observer(observer)

        assert len(channel.observers) == initial_count - 1
        assert observer not in channel.observers

    def test_add_stream_observer(self, channel):
        """Test adding a stream observer."""
        observer = MockStreamObserver()
        initial_count = len(channel.stream_observers)

        channel.add_stream_observer(observer)

        assert len(channel.stream_observers) == initial_count + 1
        assert observer in channel.stream_observers

    def test_add_duplicate_stream_observer_ignored(self, channel):
        """Test that adding a duplicate stream observer is ignored."""
        observer = MockStreamObserver()
        channel.add_stream_observer(observer)
        initial_count = len(channel.stream_observers)

        channel.add_stream_observer(observer)

        assert len(channel.stream_observers) == initial_count

    def test_remove_stream_observer(self, channel):
        """Test removing a stream observer."""
        observer = MockStreamObserver()
        channel.add_stream_observer(observer)
        initial_count = len(channel.stream_observers)

        channel.remove_stream_observer(observer)

        assert len(channel.stream_observers) == initial_count - 1
        assert observer not in channel.stream_observers


class TestChannelParticipantManagement:
    """Test participant management."""

    def test_add_participant(self, channel):
        """Test adding a participant."""
        new_participant = MockParticipant("agent3", "TestAgent")
        initial_count = channel.participant_count

        channel.add_participant(new_participant)

        assert channel.participant_count == initial_count + 1
        assert new_participant in channel.participants

    def test_add_duplicate_participant_ignored(self, channel, participants):
        """Test that adding a duplicate participant is ignored."""
        initial_count = channel.participant_count

        channel.add_participant(participants[0])

        assert channel.participant_count == initial_count

    def test_remove_participant(self, channel, participants):
        """Test removing a participant."""
        initial_count = channel.participant_count
        participant_to_remove = participants[0]
        participant_id = participant_to_remove.id

        channel.remove_participant(participant_to_remove)

        assert channel.participant_count == initial_count - 1
        assert channel.get_participant(participant_id) is None

    def test_get_participant_by_id(self, channel, participants):
        """Test getting a participant by ID."""
        participant = channel.get_participant("agent1")

        assert participant is not None
        assert participant.id == "agent1"

    def test_get_nonexistent_participant(self, channel):
        """Test getting a nonexistent participant returns None."""
        participant = channel.get_participant("nonexistent")
        assert participant is None


@pytest.mark.asyncio
class TestChannelMessaging:
    """Test channel messaging functionality."""

    async def test_send_message_to_participants(
        self, channel, sample_message, participants
    ):
        """Test sending a message to all participants except sender."""
        await channel.send(sample_message, sender_id="agent1")

        # Agent1 (sender) should not receive
        assert len(participants[0].delivered_messages) == 0

        # Agent2 should receive
        assert len(participants[1].delivered_messages) == 1
        assert participants[1].delivered_messages[0] == sample_message

        # Human should receive
        # Note: HumanParticipant.deliver() is a no-op, so this would be 0
        # But our MockParticipant actually tracks deliveries
        assert len(participants[2].delivered_messages) == 1

    async def test_send_notifies_observers(self, channel, sample_message):
        """Test that sending a message notifies observers."""
        observer = MockMessageObserver()
        channel.add_observer(observer)

        await channel.send(sample_message, sender_id="agent1")

        assert len(observer.messages) == 1
        assert observer.messages[0] == sample_message

    async def test_send_with_multiple_observers(self, channel, sample_message):
        """Test sending with multiple observers."""
        observer1 = MockMessageObserver()
        observer2 = MockMessageObserver()
        channel.add_observer(observer1)
        channel.add_observer(observer2)

        await channel.send(sample_message, sender_id="agent1")

        assert len(observer1.messages) == 1
        assert len(observer2.messages) == 1


@pytest.mark.asyncio
class TestChannelStreaming:
    """Test channel streaming functionality."""

    async def test_start_stream(self, channel):
        """Test starting a stream."""
        observer = MockStreamObserver()
        channel.add_stream_observer(observer)

        stream_id = await channel.start_stream(
            sender_id="agent1", sender_klass="TestAgent", receiver_spec="agent2"
        )

        assert stream_id is not None
        assert len(observer.stream_starts) == 1
        assert observer.stream_starts[0].stream_id == stream_id
        assert observer.stream_starts[0].sender_id == "agent1"

    async def test_stream_chunk(self, channel):
        """Test streaming a chunk."""
        observer = MockStreamObserver()
        channel.add_stream_observer(observer)

        stream_id = await channel.start_stream(sender_id="agent1")
        await channel.stream_chunk(stream_id, "Hello ")
        await channel.stream_chunk(stream_id, "world!")

        assert len(observer.stream_chunks) == 2
        assert observer.stream_chunks[0].chunk == "Hello "
        assert observer.stream_chunks[1].chunk == "world!"

    async def test_stream_chunk_invalid_stream_raises_error(self, channel):
        """Test streaming to an invalid stream raises an error."""
        with pytest.raises(ValueError, match="Stream .* not found"):
            await channel.stream_chunk("invalid_stream_id", "chunk")

    async def test_complete_stream(self, channel, sample_message, participants):
        """Test completing a stream."""
        observer = MockStreamObserver()
        channel.add_stream_observer(observer)

        stream_id = await channel.start_stream(sender_id="agent1")
        await channel.stream_chunk(stream_id, "Hello")
        await channel.complete_stream(stream_id, sample_message)

        # Check stream completion was notified
        assert len(observer.stream_completes) == 1
        assert observer.stream_completes[0].stream_id == stream_id

        # Check final message was delivered
        assert len(participants[1].delivered_messages) == 1

    async def test_complete_stream_invalid_stream_raises_error(
        self, channel, sample_message
    ):
        """Test completing an invalid stream raises an error."""
        with pytest.raises(ValueError, match="Stream .* not found"):
            await channel.complete_stream("invalid_stream_id", sample_message)

    async def test_complete_stream_removes_from_active_streams(
        self, channel, sample_message
    ):
        """Test that completing a stream removes it from active streams."""
        stream_id = await channel.start_stream(sender_id="agent1")
        await channel.complete_stream(stream_id, sample_message)

        # Try to stream another chunk - should fail
        with pytest.raises(ValueError, match="Stream .* not found"):
            await channel.stream_chunk(stream_id, "more content")

    async def test_full_streaming_workflow(self, channel, participants):
        """Test a complete streaming workflow."""
        observer = MockStreamObserver()
        channel.add_stream_observer(observer)

        # Start stream
        stream_id = await channel.start_stream(
            sender_id="agent1", sender_klass="TestAgent"
        )

        # Stream chunks
        chunks = ["The ", "quick ", "brown ", "fox"]
        for chunk in chunks:
            await channel.stream_chunk(stream_id, chunk)

        # Complete stream
        final_message = Message(
            sender_id="agent1",
            sender_klass="TestAgent",
            recipient_id="agent2",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            content="The quick brown fox",
            meeting_id=None,
        )
        await channel.complete_stream(stream_id, final_message)

        # Verify observer received all events
        assert len(observer.stream_starts) == 1
        assert len(observer.stream_chunks) == 4
        assert len(observer.stream_completes) == 1

        # Verify final message was delivered
        assert len(participants[1].delivered_messages) == 1
        assert participants[1].delivered_messages[0].content == "The quick brown fox"


@pytest.mark.asyncio
class TestChannelMultipleParticipants:
    """Test channel behavior with multiple participants (meetings)."""

    async def test_meeting_delivers_to_all_except_sender(self):
        """Test that meeting messages are delivered to all except sender."""
        participants = [MockParticipant(f"agent{i}") for i in range(5)]
        channel = Channel("meeting", participants)

        message = Message(
            sender_id="agent0",
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Meeting message",
            meeting_id="meeting_100",
        )

        await channel.send(message, sender_id="agent0")

        # Agent0 (sender) should not receive
        assert len(participants[0].delivered_messages) == 0

        # All other agents should receive
        for i in range(1, 5):
            assert len(participants[i].delivered_messages) == 1
            assert participants[i].delivered_messages[0] == message


class TestChannelRepr:
    """Test channel string representation."""

    def test_channel_repr(self, channel):
        """Test channel repr."""
        repr_str = repr(channel)
        assert "Channel" in repr_str
        assert "test_channel" in repr_str
        assert "MockParticipant" in repr_str

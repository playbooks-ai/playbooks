"""Tests for multi-human meeting functionality."""

from datetime import datetime

import pytest

from playbooks.agents.human_agent import HumanAgent
from playbooks.delivery_preferences import DeliveryPreferences
from playbooks.event_bus import EventBus
from playbooks.identifiers import AgentID
from playbooks.meetings.meeting import Meeting
from playbooks.message import Message, MessageType


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus(session_id="test-session")


@pytest.fixture
def alice_human(event_bus):
    """Create Alice human agent with 'all' notifications."""
    alice = HumanAgent(
        event_bus=event_bus,
        agent_id="human_alice",
        klass="Alice",
        name="Alice Chen",
        delivery_preferences=DeliveryPreferences(
            channel="streaming",
            streaming_enabled=True,
            meeting_notifications="all",
        ),
    )
    return alice


@pytest.fixture
def bob_human(event_bus):
    """Create Bob human agent with 'targeted' notifications."""
    bob = HumanAgent(
        event_bus=event_bus,
        agent_id="human_bob",
        klass="Bob",
        name="Bob Smith",
        delivery_preferences=DeliveryPreferences(
            channel="buffered",
            streaming_enabled=False,
            meeting_notifications="targeted",
        ),
    )
    return bob


@pytest.fixture
def carol_human(event_bus):
    """Create Carol human agent with 'none' notifications."""
    carol = HumanAgent(
        event_bus=event_bus,
        agent_id="human_carol",
        klass="Carol",
        name="Carol Williams",
        delivery_preferences=DeliveryPreferences(
            channel="streaming",
            streaming_enabled=True,
            meeting_notifications="none",
        ),
    )
    return carol


class TestMeetingGetHumans:
    """Test getting human participants from meetings."""

    def test_get_humans_empty_meeting(self):
        """Meeting with no participants returns empty list."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
        )

        humans = meeting.get_humans()
        assert humans == []

    def test_get_humans_only_humans(self, alice_human, bob_human):
        """Meeting with only human participants."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice_human, bob_human],
        )

        humans = meeting.get_humans()
        assert len(humans) == 2
        assert alice_human in humans
        assert bob_human in humans

    def test_get_humans_mixed_participants(self, alice_human, event_bus):
        """Meeting with mix of human and AI participants."""

        # Create a mock AI agent
        class MockAIAgent:
            def __init__(self):
                self.id = "agent_1"
                self.klass = "Facilitator"

        ai_agent = MockAIAgent()

        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice_human, ai_agent],
        )

        humans = meeting.get_humans()
        assert len(humans) == 1
        assert humans[0] == alice_human


class TestShouldStreamToHuman:
    """Test should_stream_to_human logic."""

    def test_stream_to_human_not_in_meeting(self, alice_human):
        """Should not stream if human not in meeting."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[],
        )

        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Test message",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        assert not meeting.should_stream_to_human("human_alice", msg)

    def test_stream_disabled_returns_false(self, bob_human):
        """Should not stream if human has streaming disabled."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[bob_human],
        )

        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Test message",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        # Bob has streaming_enabled=False
        assert not meeting.should_stream_to_human("human_bob", msg)

    def test_notifications_none_returns_false(self, carol_human):
        """Should not stream if notifications set to 'none'."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[carol_human],
        )

        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Test message",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        # Carol has meeting_notifications="none"
        assert not meeting.should_stream_to_human("human_carol", msg)

    def test_notifications_all_returns_true(self, alice_human):
        """Should stream if notifications set to 'all'."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice_human],
        )

        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Generic message to everyone",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        # Alice has meeting_notifications="all" and streaming_enabled=True
        assert meeting.should_stream_to_human("human_alice", msg)

    def test_targeted_by_name_in_content(self, alice_human):
        """Should stream if human name mentioned in message."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice_human],
        )

        # Temporarily set Alice to targeted mode for this test
        alice_human.delivery_preferences.meeting_notifications = "targeted"

        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Alice Chen, what do you think?",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        assert meeting.should_stream_to_human("human_alice", msg)

    def test_targeted_by_klass_in_content(self, alice_human):
        """Should stream if human klass mentioned in message."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice_human],
        )

        # Set Alice to targeted mode
        alice_human.delivery_preferences.meeting_notifications = "targeted"

        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Alice, can you help with this?",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        assert meeting.should_stream_to_human("human_alice", msg)

    def test_targeted_by_agent_ids(self, alice_human):
        """Should stream if human in target_agent_ids."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice_human],
        )

        # Set Alice to targeted mode
        alice_human.delivery_preferences.meeting_notifications = "targeted"

        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="What do you think?",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
            target_agent_ids=[AgentID("human_alice"), AgentID("agent_2")],
        )

        assert meeting.should_stream_to_human("human_alice", msg)

    def test_not_targeted_returns_false(self, alice_human):
        """Should not stream if in targeted mode and not mentioned."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice_human],
        )

        # Set Alice to targeted mode
        alice_human.delivery_preferences.meeting_notifications = "targeted"

        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Bob, what do you think?",  # Mentions Bob, not Alice
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        assert not meeting.should_stream_to_human("human_alice", msg)


class TestMultiHumanMeetingScenarios:
    """Test real-world multi-human meeting scenarios."""

    def test_meeting_with_three_humans_different_preferences(
        self, alice_human, bob_human, carol_human
    ):
        """Test meeting with humans having different notification preferences."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice_human, bob_human, carol_human],
        )

        # Broadcast message
        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Hello everyone!",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        # Alice (all) should stream
        assert meeting.should_stream_to_human("human_alice", msg)

        # Bob (targeted, not mentioned) should NOT stream (streaming also disabled)
        assert not meeting.should_stream_to_human("human_bob", msg)

        # Carol (none) should NOT stream
        assert not meeting.should_stream_to_human("human_carol", msg)

    def test_targeted_message_in_meeting(self, alice_human, bob_human):
        """Test targeted message in meeting."""
        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice_human, bob_human],
        )

        # Set Bob to targeted mode and enable streaming for this test
        bob_human.delivery_preferences.streaming_enabled = True
        bob_human.delivery_preferences.meeting_notifications = "targeted"

        # Message targeting Bob
        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Bob, what's your opinion?",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        # Alice (all) should stream
        assert meeting.should_stream_to_human("human_alice", msg)

        # Bob (targeted, mentioned) should stream
        assert meeting.should_stream_to_human("human_bob", msg)

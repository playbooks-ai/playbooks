"""Integration-style unit tests for multi-human functionality.

These tests verify interactions between:
- AgentBuilder (parsing :Human syntax)
- HumanAgent (with delivery preferences)
- Program (initialization and routing)
- Channel (observer filtering)
- Meeting (per-human streaming logic)
"""

import uuid

import pytest

from playbooks.agents.human_agent import HumanAgent
from playbooks.channels.stream_events import StreamChunkEvent, StreamStartEvent
from playbooks.delivery_preferences import DeliveryPreferences
from playbooks.infrastructure.event_bus import EventBus
from playbooks.core.identifiers import AgentID
from playbooks.meetings.meeting import Meeting
from playbooks.core.message import Message, MessageType
from playbooks.program import Program


def create_event_bus():
    """Create an EventBus with unique session ID."""
    return EventBus(session_id=str(uuid.uuid4()))


def create_program_content(content: str) -> str:
    """Wrap content with public.json."""
    return f"""```public.json
[]
```

{content}"""


class MockStreamObserver:
    """Mock observer for testing stream filtering."""

    def __init__(self, name: str, target_human_id: str = None):
        self.name = name
        self.target_human_id = target_human_id
        self.events = []

    async def on_stream_start(self, event: StreamStartEvent) -> None:
        self.events.append(("start", event))

    async def on_stream_chunk(self, event: StreamChunkEvent) -> None:
        self.events.append(("chunk", event))

    async def on_stream_complete(self, event) -> None:
        self.events.append(("complete", event))


class TestMultiHumanParsing:
    """Test multi-human agent parsing and initialization."""

    @pytest.mark.asyncio
    async def test_parse_and_initialize_multiple_humans(self):
        """Test complete flow from parsing to initialization."""
        content = create_program_content(
            """
# Alice:Human
metadata:
  name: Alice Chen
  delivery_channel: streaming
  meeting_notifications: all

# Bob:Human
metadata:
  name: Bob Smith  
  delivery_channel: buffered
  meeting_notifications: targeted

# Carol:Human
metadata:
  name: Carol Williams
  delivery_channel: streaming
  meeting_notifications: none
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(event_bus=event_bus, program_content=content)
            await program.initialize()

            # All three humans should be created
            assert len(program.agents) == 3

            alice = program.agents_by_klass["Alice"][0]
            bob = program.agents_by_klass["Bob"][0]
            carol = program.agents_by_klass["Carol"][0]

            # Verify all are HumanAgent instances
            assert isinstance(alice, HumanAgent)
            assert isinstance(bob, HumanAgent)
            assert isinstance(carol, HumanAgent)

            # Verify unique IDs
            assert len({alice.id, bob.id, carol.id}) == 3

            # Verify names extracted from metadata
            assert alice.name == "Alice Chen"
            assert bob.name == "Bob Smith"
            assert carol.name == "Carol Williams"

            # Verify delivery preferences
            assert alice.delivery_preferences.channel == "streaming"
            assert alice.delivery_preferences.streaming_enabled
            assert alice.delivery_preferences.meeting_notifications == "all"

            assert bob.delivery_preferences.channel == "buffered"
            assert not bob.delivery_preferences.streaming_enabled  # auto-disabled
            assert bob.delivery_preferences.meeting_notifications == "targeted"

            assert carol.delivery_preferences.channel == "streaming"
            assert carol.delivery_preferences.streaming_enabled
            assert carol.delivery_preferences.meeting_notifications == "none"

            # Verify no default User was created (humans were declared)
            assert "User" not in program.agents_by_klass


class TestTargetedStreamingWithProgram:
    """Test targeted streaming through Program and Channel."""

    @pytest.mark.asyncio
    async def test_stream_to_specific_human_filters_observers(self):
        """Test that streaming to a specific human filters observers correctly."""
        content = create_program_content(
            """
# Alice:Human
metadata:
  name: Alice

# Bob:Human
metadata:
  name: Bob

# Host:AI

## TestPlaybook
### Steps
- Say("Alice", "Message for Alice")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(event_bus=event_bus, program_content=content)
            await program.initialize()

            alice = program.agents_by_klass["Alice"][0]
            bob = program.agents_by_klass["Bob"][0]

            # Create targeted observers
            alice_observer = MockStreamObserver("alice_obs", target_human_id=alice.id)
            bob_observer = MockStreamObserver("bob_obs", target_human_id=bob.id)
            all_observer = MockStreamObserver("all_obs", target_human_id=None)

            # Subscribe observers to any future channels
            def add_observers_to_channel(channel):
                channel.add_stream_observer(alice_observer)
                channel.add_stream_observer(bob_observer)
                channel.add_stream_observer(all_observer)

            # Subscribe to existing channels
            for channel in program.channels.values():
                add_observers_to_channel(channel)

            # Create a channel manually to test
            # In real execution, this would be created by Program.route_message
            from playbooks.channels.channel import Channel
            from playbooks.channels.participant import HumanParticipant

            channel = Channel(
                "test_channel", [HumanParticipant(alice.id, alice.klass, alice)]
            )
            add_observers_to_channel(channel)

            # Start a stream targeted to Alice
            await channel.start_stream(
                stream_id="test_stream",
                sender_id="agent_1",
                sender_klass="Host",
                receiver_spec="Alice",
                recipient_id=alice.id,
                recipient_klass=alice.klass,
            )

            # Stream some content
            await channel.stream_chunk("test_stream", "Hello ")
            await channel.stream_chunk("test_stream", "Alice!")

            # Complete stream
            final_msg = Message(
                sender_id=AgentID("agent_1"),
                sender_klass="Host",
                recipient_id=AgentID(alice.id),
                recipient_klass=alice.klass,
                content="Hello Alice!",
                message_type=MessageType.DIRECT,
                meeting_id=None,
            )
            await channel.complete_stream("test_stream", final_msg)

            # Verify filtering worked
            # Alice observer should receive all events (targeted to her)
            assert len(alice_observer.events) == 4  # start + 2 chunks + complete

            # Bob observer should receive NO events (different target)
            assert len(bob_observer.events) == 0

            # All observer should receive all events (no filter)
            assert len(all_observer.events) == 4


class TestMeetingWithMultipleHumans:
    """Test meeting logic with multiple human participants."""

    @pytest.mark.asyncio
    async def test_get_humans_from_meeting(self):
        """Test get_humans() method filters HumanAgent instances."""
        event_bus = create_event_bus()

        alice = HumanAgent(
            event_bus=event_bus,
            agent_id="human_alice",
            klass="Alice",
            name="Alice",
        )
        bob = HumanAgent(
            event_bus=event_bus,
            agent_id="human_bob",
            klass="Bob",
            name="Bob",
        )

        # Mock AI agent
        class MockAI:
            def __init__(self):
                self.id = "agent_1"
                self.klass = "Facilitator"

        ai_agent = MockAI()

        from datetime import datetime

        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id=ai_agent.id,
            joined_attendees=[alice, ai_agent, bob],
        )

        humans = meeting.get_humans()
        assert len(humans) == 2
        assert alice in humans
        assert bob in humans
        assert ai_agent not in humans

    @pytest.mark.asyncio
    async def test_should_stream_to_human_all_notifications(self):
        """Test streaming to human with 'all' notifications."""
        event_bus = create_event_bus()

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

        from datetime import datetime

        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice],
        )

        # Any message should stream to Alice
        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="General announcement",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        assert meeting.should_stream_to_human(alice.id, msg)

    @pytest.mark.asyncio
    async def test_should_stream_to_human_targeted_by_mention(self):
        """Test streaming when human is mentioned in message."""
        event_bus = create_event_bus()

        alice = HumanAgent(
            event_bus=event_bus,
            agent_id="human_alice",
            klass="Alice",
            name="Alice Chen",
            delivery_preferences=DeliveryPreferences(
                channel="streaming",
                streaming_enabled=True,
                meeting_notifications="targeted",
            ),
        )

        from datetime import datetime

        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice],
        )

        # Message mentioning Alice by name
        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Alice Chen, what's your opinion?",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        assert meeting.should_stream_to_human(alice.id, msg)

    @pytest.mark.asyncio
    async def test_should_stream_to_human_not_targeted(self):
        """Test no streaming when in targeted mode and not mentioned."""
        event_bus = create_event_bus()

        alice = HumanAgent(
            event_bus=event_bus,
            agent_id="human_alice",
            klass="Alice",
            name="Alice Chen",
            delivery_preferences=DeliveryPreferences(
                channel="streaming",
                streaming_enabled=True,
                meeting_notifications="targeted",
            ),
        )

        from datetime import datetime

        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice],
        )

        # Message NOT mentioning Alice
        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Bob, what do you think?",  # Mentions Bob, not Alice
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        assert not meeting.should_stream_to_human(alice.id, msg)

    @pytest.mark.asyncio
    async def test_three_humans_different_streaming_behavior(self):
        """Test three humans with different preferences in same meeting."""
        event_bus = create_event_bus()

        alice = HumanAgent(
            event_bus=event_bus,
            agent_id="human_alice",
            klass="Alice",
            name="Alice",
            delivery_preferences=DeliveryPreferences(
                streaming_enabled=True,
                meeting_notifications="all",
            ),
        )

        bob = HumanAgent(
            event_bus=event_bus,
            agent_id="human_bob",
            klass="Bob",
            name="Bob",
            delivery_preferences=DeliveryPreferences(
                streaming_enabled=True,
                meeting_notifications="targeted",
            ),
        )

        carol = HumanAgent(
            event_bus=event_bus,
            agent_id="human_carol",
            klass="Carol",
            name="Carol",
            delivery_preferences=DeliveryPreferences(
                streaming_enabled=True,
                meeting_notifications="none",
            ),
        )

        from datetime import datetime

        meeting = Meeting(
            id="meeting_1",
            created_at=datetime.now(),
            owner_id="agent_1",
            joined_attendees=[alice, bob, carol],
        )

        # Broadcast message not mentioning anyone
        msg_broadcast = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="General announcement",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        # Alice (all) should stream
        assert meeting.should_stream_to_human(alice.id, msg_broadcast)
        # Bob (targeted, not mentioned) should NOT stream
        assert not meeting.should_stream_to_human(bob.id, msg_broadcast)
        # Carol (none) should NOT stream
        assert not meeting.should_stream_to_human(carol.id, msg_broadcast)

        # Message targeting Bob
        msg_targeted = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Facilitator",
            recipient_id=None,
            recipient_klass=None,
            content="Bob, what's your update?",
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id="meeting_1",
        )

        # Alice (all) should stream
        assert meeting.should_stream_to_human(alice.id, msg_targeted)
        # Bob (targeted, mentioned) should stream
        assert meeting.should_stream_to_human(bob.id, msg_targeted)
        # Carol (none) should NOT stream
        assert not meeting.should_stream_to_human(carol.id, msg_targeted)


class TestDefaultUserCreation:
    """Test default User:Human creation when none declared."""

    @pytest.mark.asyncio
    async def test_default_user_created_for_ai_only_program(self):
        """Default User:Human created when only AI agents declared."""
        content = create_program_content(
            """
# Host:AI

## Main
### Steps
- Say("User", "Hello")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(event_bus=event_bus, program_content=content)
            await program.initialize()

            # AI agent class created
            assert "Host" in program.agent_klasses

            # Default User human instance created
            assert "User" in program.agents_by_klass
            user = program.agents_by_klass["User"][0]

            assert isinstance(user, HumanAgent)
            assert user.klass == "User"
            assert user.id == "human"
            assert user.delivery_preferences.streaming_enabled

    @pytest.mark.asyncio
    async def test_no_default_user_when_humans_declared(self):
        """No default User created when humans are declared."""
        content = create_program_content(
            """
# Alice:Human

# Host:AI

## Main
### Steps
- Say("Alice", "Hello")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(event_bus=event_bus, program_content=content)
            await program.initialize()

            # Alice declared and created
            assert "Alice" in program.agents_by_klass

            # No default User created
            assert "User" not in program.agents_by_klass

            # Only Alice should be in agents
            human_agents = [a for a in program.agents if isinstance(a, HumanAgent)]
            assert len(human_agents) == 1
            assert human_agents[0].klass == "Alice"


class TestChannelObserverIntegration:
    """Test Channel and StreamObserver integration."""

    @pytest.mark.asyncio
    async def test_channel_filters_observers_by_recipient(self):
        """Test that Channel correctly filters observers by recipient_id."""
        event_bus = create_event_bus()

        alice = HumanAgent(
            event_bus=event_bus,
            agent_id="human_alice",
            klass="Alice",
        )
        bob = HumanAgent(
            event_bus=event_bus,
            agent_id="human_bob",
            klass="Bob",
        )

        from playbooks.channels.channel import Channel
        from playbooks.channels.participant import HumanParticipant

        channel = Channel(
            "test_channel",
            [HumanParticipant(alice.id, alice.klass, alice)],
        )

        # Create observers
        alice_obs = MockStreamObserver("alice", alice.id)
        bob_obs = MockStreamObserver("bob", bob.id)
        all_obs = MockStreamObserver("all", None)

        channel.add_stream_observer(alice_obs)
        channel.add_stream_observer(bob_obs)
        channel.add_stream_observer(all_obs)

        # Stream to Alice
        await channel.start_stream(
            stream_id="stream_1",
            sender_id="agent_1",
            recipient_id=alice.id,
        )
        await channel.stream_chunk("stream_1", "Test")

        msg = Message(
            sender_id=AgentID("agent_1"),
            sender_klass="Agent",
            recipient_id=AgentID(alice.id),
            recipient_klass=alice.klass,
            content="Test",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
        await channel.complete_stream("stream_1", msg)

        # Alice observer: 3 events (start + chunk + complete)
        assert len(alice_obs.events) == 3

        # Bob observer: 0 events (filtered out)
        assert len(bob_obs.events) == 0

        # All observer: 3 events (receives everything)
        assert len(all_obs.events) == 3


class TestDeliveryPreferencesValidation:
    """Test delivery preferences validation and auto-configuration."""

    def test_buffered_channel_auto_disables_streaming(self):
        """Buffered channel automatically disables streaming."""
        prefs = DeliveryPreferences(
            channel="buffered",
            streaming_enabled=True,  # Will be auto-disabled
            buffer_timeout=30.0,
        )

        # Should be auto-corrected in __post_init__
        assert not prefs.streaming_enabled
        assert prefs.buffer_messages

    def test_buffered_channel_auto_enables_buffering(self):
        """Buffered channel automatically enables buffering."""
        prefs = DeliveryPreferences(
            channel="buffered",
            buffer_messages=False,  # Will be auto-enabled
        )

        assert prefs.buffer_messages

    def test_streaming_channel_auto_enables_streaming(self):
        """Streaming channel automatically enables streaming."""
        prefs = DeliveryPreferences(
            channel="streaming",
            streaming_enabled=False,  # Will be auto-enabled
        )

        assert prefs.streaming_enabled

    def test_custom_channel_requires_handler(self):
        """Custom channel requires custom_handler."""
        with pytest.raises(ValueError, match="custom_handler must be provided"):
            DeliveryPreferences(
                channel="custom",
                custom_handler=None,  # Missing required handler
            )

    def test_streaming_default_factory(self):
        """Test streaming_default() factory method."""
        prefs = DeliveryPreferences.streaming_default()

        assert prefs.channel == "streaming"
        assert prefs.streaming_enabled
        assert not prefs.buffer_messages
        assert prefs.meeting_notifications == "targeted"

    def test_buffered_default_factory(self):
        """Test buffered_default() factory method."""
        prefs = DeliveryPreferences.buffered_default(timeout=120.0)

        assert prefs.channel == "buffered"
        assert not prefs.streaming_enabled  # Auto-disabled
        assert prefs.buffer_messages  # Auto-enabled
        assert prefs.buffer_timeout == 120.0


class TestAgentBuilderHumanFactory:
    """Test AgentBuilder creates HumanAgent correctly."""

    @pytest.mark.asyncio
    async def test_human_agent_class_has_correct_attributes(self):
        """Test that dynamically created HumanAgent class has correct attributes."""
        content = create_program_content(
            """
# ProjectManager:Human
metadata:
  name: Alice Chen
  role: PM
  delivery_channel: streaming
  meeting_notifications: all
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(event_bus=event_bus, program_content=content)

            # Check class was created correctly
            assert "ProjectManager" in program.agent_klasses
            pm_class = program.agent_klasses["ProjectManager"]

            # Verify class attributes
            assert pm_class.klass == "ProjectManager"
            assert pm_class.human_name == "Alice Chen"
            assert pm_class.metadata["role"] == "PM"
            assert pm_class.delivery_preferences.channel == "streaming"
            assert pm_class.delivery_preferences.meeting_notifications == "all"

            # Initialize to create instance
            await program.initialize()

            pm = program.agents_by_klass["ProjectManager"][0]

            # Verify instance got class attributes
            assert pm.klass == "ProjectManager"
            assert pm.name == "Alice Chen"
            assert pm.delivery_preferences.channel == "streaming"


class TestMixedAIAndHumanProgram:
    """Test programs with both AI and Human agents."""

    @pytest.mark.asyncio
    async def test_mixed_agent_types_initialized_correctly(self):
        """Test program with mix of AI and Human agents."""
        content = create_program_content(
            """
# Alice:Human
metadata:
  name: Alice

# Bob:Human  
metadata:
  name: Bob

# Facilitator:AI

## Main
### Steps
- Say("Alice", "Hi Alice")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(event_bus=event_bus, program_content=content)
            await program.initialize()

            # All agent classes created
            assert "Alice" in program.agent_klasses
            assert "Bob" in program.agent_klasses
            assert "Facilitator" in program.agent_klasses

            # Human instances created
            assert "Alice" in program.agents_by_klass
            assert "Bob" in program.agents_by_klass

            # Verify types
            alice = program.agents_by_klass["Alice"][0]
            bob = program.agents_by_klass["Bob"][0]

            assert isinstance(alice, HumanAgent)
            assert isinstance(bob, HumanAgent)

            # Count agent types
            humans = [a for a in program.agents if isinstance(a, HumanAgent)]
            assert len(humans) == 2

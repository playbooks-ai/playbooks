"""Integration tests for declarative multi-human agent support."""

import uuid

import pytest

from playbooks.agents.human_agent import HumanAgent
from playbooks.event_bus import EventBus
from playbooks.program import Program


def create_event_bus():
    """Create an EventBus with unique session ID."""
    return EventBus(session_id=str(uuid.uuid4()))


def create_compiled_program_content(playbook_content: str) -> str:
    """Wrap playbook content with public.json for compilation."""
    return f"""```public.json
[]
```

{playbook_content}"""


class TestDeclarativeHumanSyntax:
    """Test declarative human agent syntax in playbooks."""

    @pytest.mark.asyncio
    async def test_single_human_agent_declared(self):
        """Test declaring a single human agent with :Human syntax."""
        playbook_content = create_compiled_program_content(
            """
# Alice:Human

## SayHello
### Steps
- Say("Alice", "Hello Alice!")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            # Check that Alice was created
            assert "Alice" in program.agents_by_klass
            alice = program.agents_by_klass["Alice"][0]

            # Verify it's a HumanAgent
            assert isinstance(alice, HumanAgent)
            assert alice.klass == "Alice"
            assert alice.name == "Alice"

            # Verify delivery preferences default to streaming
            assert alice.delivery_preferences.channel == "streaming"
            assert alice.delivery_preferences.streaming_enabled

            # Verify no default "User" human was created
            assert "User" not in program.agents_by_klass

    @pytest.mark.asyncio
    async def test_multiple_human_agents_declared(self):
        """Test declaring multiple human agents in same playbook."""
        playbook_content = create_compiled_program_content(
            """
# Alice:Human

# Bob:Human

# Facilitator:AI

## Main
### Steps
- Say("Alice", "Hello Alice!")
- Say("Bob", "Hello Bob!")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            # Check that both humans were instantiated
            assert "Alice" in program.agents_by_klass
            assert "Bob" in program.agents_by_klass
            # Facilitator AI agent class created but may not be instantiated (no BGN trigger in raw markdown)
            assert "Facilitator" in program.agent_klasses

            alice = program.agents_by_klass["Alice"][0]
            bob = program.agents_by_klass["Bob"][0]

            # Verify types
            assert isinstance(alice, HumanAgent)
            assert isinstance(bob, HumanAgent)

            # Verify unique IDs
            assert alice.id != bob.id

            # Verify no default "User" human was created
            assert "User" not in program.agents_by_klass

    @pytest.mark.asyncio
    async def test_no_human_declared_creates_default_user(self):
        """Test that default User:Human is created when none declared."""
        playbook_content = create_compiled_program_content(
            """
# Host:AI

## Main
### Steps
- Say("User", "Hello!")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            # Check that Host AI agent class was created (even if not instantiated)
            assert "Host" in program.agent_klasses

            # Check that default User was created
            assert "User" in program.agents_by_klass
            user = program.agents_by_klass["User"][0]

            # Verify it's a HumanAgent
            assert isinstance(user, HumanAgent)
            assert user.klass == "User"
            assert user.name == "User"
            assert user.id == "human"

            # Verify delivery preferences default to streaming
            assert user.delivery_preferences.channel == "streaming"

    @pytest.mark.asyncio
    async def test_human_with_metadata(self):
        """Test human agent with metadata for name and delivery preferences."""
        playbook_content = create_compiled_program_content(
            """
# Alice:Human
metadata:
  name: Alice Chen
  delivery_channel: buffered
  buffer_timeout: 30.0
  meeting_notifications: all

# Host:AI

## Greet
### Steps
- Say("Alice", "Hello!")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            # Check that Alice was created with correct metadata
            assert "Alice" in program.agents_by_klass
            alice = program.agents_by_klass["Alice"][0]

            # Verify human name from metadata
            assert alice.name == "Alice Chen"

            # Verify delivery preferences from metadata
            assert alice.delivery_preferences.channel == "buffered"
            assert alice.delivery_preferences.buffer_timeout == 30.0
            assert alice.delivery_preferences.meeting_notifications == "all"
            assert (
                not alice.delivery_preferences.streaming_enabled
            )  # auto-set for buffered
            assert alice.delivery_preferences.buffer_messages  # auto-set for buffered

    @pytest.mark.asyncio
    async def test_ai_agent_without_type_annotation_defaults_to_ai(self):
        """Test that agents without :Type annotation default to :AI."""
        playbook_content = create_compiled_program_content(
            """
# Host

## Main
### Steps
- Say("User", "Hello!")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            # Check that Host AI agent class was created
            assert "Host" in program.agent_klasses
            host_klass = program.agent_klasses["Host"]

            # Verify it's NOT a HumanAgent class
            assert not issubclass(host_klass, HumanAgent)

            # Verify default User was created as instance
            assert "User" in program.agents_by_klass
            user = program.agents_by_klass["User"][0]
            assert isinstance(user, HumanAgent)

    @pytest.mark.asyncio
    async def test_human_agent_has_unique_id(self):
        """Test that each human agent gets a unique ID."""
        playbook_content = create_compiled_program_content(
            """
# Alice:Human

# Bob:Human

# Carol:Human
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            alice = program.agents_by_klass["Alice"][0]
            bob = program.agents_by_klass["Bob"][0]
            carol = program.agents_by_klass["Carol"][0]

            # All should have unique IDs
            ids = {alice.id, bob.id, carol.id}
            assert len(ids) == 3

            # All should be HumanAgents
            assert isinstance(alice, HumanAgent)
            assert isinstance(bob, HumanAgent)
            assert isinstance(carol, HumanAgent)

    @pytest.mark.asyncio
    async def test_invalid_agent_type_raises_error(self):
        """Test that invalid agent type raises configuration error."""
        playbook_content = create_compiled_program_content(
            """
# Host:Invalid

## Greet
### Steps
- Say("User", "Hello!")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            with pytest.raises(Exception) as exc_info:
                Program(
                    event_bus=event_bus,
                    program_content=playbook_content,
                )

            # Should mention invalid agent type
            assert "Invalid agent type" in str(exc_info.value)


class TestDeliveryPreferences:
    """Test delivery preferences extraction and validation."""

    @pytest.mark.asyncio
    async def test_streaming_preference(self):
        """Test streaming delivery preference."""
        playbook_content = create_compiled_program_content(
            """
# Alice:Human
metadata:
  name: Alice Chen
  delivery_channel: streaming
  streaming_enabled: true
  streaming_chunk_size: 1
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            alice = program.agents_by_klass["Alice"][0]
            prefs = alice.delivery_preferences

            assert prefs.channel == "streaming"
            assert prefs.streaming_enabled
            assert prefs.streaming_chunk_size == 1

    @pytest.mark.asyncio
    async def test_buffered_preference(self):
        """Test buffered delivery preference."""
        playbook_content = create_compiled_program_content(
            """
# Bob:Human
metadata:
  name: Bob Smith
  delivery_channel: buffered
  buffer_timeout: 60.0
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            bob = program.agents_by_klass["Bob"][0]
            prefs = bob.delivery_preferences

            assert prefs.channel == "buffered"
            assert prefs.buffer_timeout == 60.0
            # Auto-enabled for buffered channel
            assert prefs.buffer_messages
            assert not prefs.streaming_enabled

    @pytest.mark.asyncio
    async def test_meeting_notification_preferences(self):
        """Test meeting notification preferences."""
        playbook_content = create_compiled_program_content(
            """
# Alice:Human
metadata:
  meeting_notifications: all

# Bob:Human
metadata:
  meeting_notifications: targeted

# Carol:Human
metadata:
  meeting_notifications: none
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            alice = program.agents_by_klass["Alice"][0]
            bob = program.agents_by_klass["Bob"][0]
            carol = program.agents_by_klass["Carol"][0]

            assert alice.delivery_preferences.meeting_notifications == "all"
            assert bob.delivery_preferences.meeting_notifications == "targeted"
            assert carol.delivery_preferences.meeting_notifications == "none"

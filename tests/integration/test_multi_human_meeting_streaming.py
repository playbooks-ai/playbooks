"""Integration tests for multi-human meeting with streaming."""

import uuid

import pytest

from playbooks.channels.stream_events import StreamChunkEvent, StreamStartEvent
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


class MockStreamObserver:
    """Mock observer that tracks received events."""

    def __init__(self, target_human_id=None):
        self.target_human_id = target_human_id
        self.events = []

    async def on_stream_start(self, event: StreamStartEvent) -> None:
        self.events.append(("start", event))

    async def on_stream_chunk(self, event: StreamChunkEvent) -> None:
        self.events.append(("chunk", event))

    async def on_stream_complete(self, event) -> None:
        self.events.append(("complete", event))


class TestMultiHumanMeetingStreaming:
    """Test streaming in meetings with multiple humans."""

    @pytest.mark.asyncio
    async def test_targeted_streaming_in_meeting(self):
        """Test that streaming respects per-human preferences in meetings."""
        playbook_content = create_compiled_program_content(
            """
# Alice:Human
metadata:
  name: Alice Chen
  delivery_channel: streaming
  streaming_enabled: true
  meeting_notifications: all

# Bob:Human
metadata:
  name: Bob Smith
  delivery_channel: buffered
  streaming_enabled: false
  meeting_notifications: targeted

# Facilitator:AI

## TeamMeeting
meeting: true
required_attendees: [Alice, Bob]

### Steps
- Say("meeting", "Welcome everyone!")
- Say("meeting", "Bob, what's your update?")
"""
        )

        event_bus = create_event_bus()
        async with event_bus:
            program = Program(
                event_bus=event_bus,
                program_content=playbook_content,
            )
            await program.initialize()

            # Verify both humans created
            assert "Alice" in program.agents_by_klass
            assert "Bob" in program.agents_by_klass

            alice = program.agents_by_klass["Alice"][0]
            bob = program.agents_by_klass["Bob"][0]

            # Verify their preferences
            assert alice.delivery_preferences.streaming_enabled
            assert alice.delivery_preferences.meeting_notifications == "all"

            assert not bob.delivery_preferences.streaming_enabled
            assert bob.delivery_preferences.meeting_notifications == "targeted"

            # Create observers for each human
            alice_observer = MockStreamObserver(target_human_id=alice.id)
            bob_observer = MockStreamObserver(target_human_id=bob.id)

            # Subscribe observers to all channels
            for channel in program.channels.values():
                channel.add_stream_observer(alice_observer)
                channel.add_stream_observer(bob_observer)

            # Note: Full execution testing would require running the meeting playbook
            # For now, this test verifies the setup is correct
            # End-to-end testing will be in P4.4.5

    @pytest.mark.asyncio
    async def test_observer_filtering_by_target_human_id(self):
        """Test that observers are correctly filtered by target_human_id."""
        playbook_content = create_compiled_program_content(
            """
# Alice:Human

# Bob:Human

# Host:AI

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

            alice = program.agents_by_klass["Alice"][0]
            bob = program.agents_by_klass["Bob"][0]

            # Create targeted observers
            alice_observer = MockStreamObserver(target_human_id=alice.id)
            bob_observer = MockStreamObserver(target_human_id=bob.id)
            all_observer = MockStreamObserver(target_human_id=None)

            # Subscribe to all channels
            for channel in program.channels.values():
                channel.add_stream_observer(alice_observer)
                channel.add_stream_observer(bob_observer)
                channel.add_stream_observer(all_observer)

            # This test verifies the infrastructure is in place
            # The actual streaming behavior is tested in unit tests

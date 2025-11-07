"""Unit tests for architecture overhaul regressions.

Tests for issues discovered during integration testing after the Phase 1-5
architectural changes.
"""

import pytest

from playbooks.agents.human_agent import HumanAgent
from playbooks.applications.streaming_observer import ChannelStreamObserver
from playbooks.channels.channel import Channel
from playbooks.channels.participant import AgentParticipant, HumanParticipant
from playbooks.channels.stream_events import (
    StreamChunkEvent,
    StreamCompleteEvent,
    StreamStartEvent,
)
from playbooks.infrastructure.event_bus import EventBus
from playbooks.core.events import ChannelCreatedEvent
from playbooks.program import Program


# Concrete implementation of ChannelStreamObserver for testing
class ConcreteStreamObserver(ChannelStreamObserver):
    """Concrete implementation for testing."""

    def __init__(self, program, streaming_enabled=True, target_human_id=None):
        super().__init__(program, streaming_enabled, target_human_id)
        self.started_streams = []
        self.chunks = []
        self.completed_streams = []

    async def _display_start(self, event: StreamStartEvent, agent_name: str) -> None:
        self.started_streams.append((event.stream_id, agent_name))

    async def _display_chunk(self, event: StreamChunkEvent) -> None:
        self.chunks.append((event.stream_id, event.chunk))

    async def _display_complete(self, event: StreamCompleteEvent) -> None:
        self.completed_streams.append(event.stream_id)

    async def _display_buffered(self, event: StreamCompleteEvent) -> None:
        self.completed_streams.append(event.stream_id)


@pytest.mark.asyncio
async def test_human_agent_send_message_without_call_stack():
    """Test that HumanAgent.SendMessage() works without call_stack.

    Regression: HumanState doesn't have call_stack, but SendMessage() was
    trying to access self.state.call_stack without checking if it exists.

    Fixed by: Adding hasattr(self.state, 'call_stack') check in base_agent.py
    """
    event_bus = EventBus(session_id="test")

    # Create a minimal program for context
    program_content = "# TestAgent\n## TestPlaybook\n### Steps\n- Do something"
    program = Program(
        event_bus=event_bus,
        program_content=program_content,
    )
    await program.initialize()

    # Create human agent
    human = HumanAgent(
        event_bus=event_bus,
        agent_id="human",
        program=program,
        klass="TestUser",
    )

    # This should not raise AttributeError about 'call_stack'
    # Even though HumanState doesn't have call_stack attribute
    await human.SendMessage("1000", "Hello")

    # Verify the call didn't crash
    assert human.state is not None
    assert not hasattr(human.state, "call_stack")


@pytest.mark.asyncio
async def test_streaming_observer_subscribes_synchronously():
    """Test that StreamingObserver subscribes to channels synchronously.

    Regression: ChannelCreatedEvent handler was async, causing race condition
    where streaming wouldn't be set up before messages were sent.

    Fixed by: Making _on_channel_created_event synchronous
    """
    event_bus = EventBus(session_id="test")

    # Create a minimal program
    program_content = "# TestAgent\n## TestPlaybook\n### Steps\n- Do something"
    program = Program(
        event_bus=event_bus,
        program_content=program_content,
    )
    await program.initialize()

    # Create streaming observer
    observer = ConcreteStreamObserver(program, streaming_enabled=True)

    # Create a channel and publish event
    agent2_participant = AgentParticipant(program.agents[0])
    human_participant = HumanParticipant("human", "User", agent=None)

    channel = Channel(
        channel_id="test_channel", participants=[agent2_participant, human_participant]
    )
    program.channels["test_channel"] = channel

    # Publish ChannelCreatedEvent
    event = ChannelCreatedEvent(
        session_id=event_bus.session_id,
        agent_id="",
        channel_id="test_channel",
        is_meeting=False,
        participant_ids=["1000", "human"],
    )
    event_bus.publish(event)

    # Observer should be subscribed immediately (synchronously)
    assert "test_channel" in observer.subscribed_channels
    assert observer in channel.stream_observers


@pytest.mark.asyncio
async def test_streaming_observer_subscribe_to_existing_channels():
    """Test that streaming observer can subscribe to existing channels.

    Regression: subscribe_to_all_channels() was calling non-existent
    on_new_channel() method instead of directly subscribing.

    Fixed by: Implementing subscribe_to_all_channels() correctly
    """
    event_bus = EventBus(session_id="test")

    # Create program with existing channel
    program_content = "# TestAgent\n## TestPlaybook\n### Steps\n- Do something"
    program = Program(
        event_bus=event_bus,
        program_content=program_content,
    )
    await program.initialize()

    # Create a channel before the observer exists
    agent_participant = AgentParticipant(program.agents[0])
    human_participant = HumanParticipant("human", "User", agent=None)

    channel = Channel(
        channel_id="existing_channel",
        participants=[agent_participant, human_participant],
    )
    program.channels["existing_channel"] = channel

    # Now create observer and subscribe to existing channels
    observer = ConcreteStreamObserver(program, streaming_enabled=True)
    await observer.subscribe_to_all_channels()

    # Observer should be subscribed to the existing channel
    assert "existing_channel" in observer.subscribed_channels
    assert observer in channel.stream_observers


@pytest.mark.asyncio
async def test_human_participant_detection_for_streaming():
    """Test that HumanParticipant is correctly detected for streaming.

    Regression: _to_participant() was checking entity.klass == HUMAN_AGENT_KLASS
    instead of using isinstance(entity, HumanAgent).

    Fixed by: Using isinstance(entity, HumanAgent) check in _to_participant()
    """
    event_bus = EventBus(session_id="test")

    # Create program
    program_content = "# TestAgent\n## TestPlaybook\n### Steps\n- Do something"
    program = Program(
        event_bus=event_bus,
        program_content=program_content,
    )
    await program.initialize()

    # Get default human agent created by program
    human = program.agents_by_id.get("human")
    assert human is not None
    assert isinstance(human, HumanAgent)

    # Convert to participant
    participant = program._to_participant(human)

    # Should be HumanParticipant, not AgentParticipant
    assert isinstance(participant, HumanParticipant)
    assert not isinstance(participant, AgentParticipant)


@pytest.mark.asyncio
async def test_channel_streaming_detects_human_participants():
    """Test that channel streaming is enabled when HumanParticipant exists.

    Regression: HumanParticipant detection wasn't working, so streaming
    was being skipped even for human recipients.

    Fixed by: Proper isinstance checks for HumanParticipant
    """
    event_bus = EventBus(session_id="test")

    # Create program
    program_content = "# TestAgent\n## TestPlaybook\n### Steps\n- Do something"
    program = Program(
        event_bus=event_bus,
        program_content=program_content,
    )
    await program.initialize()

    agent = program.agents[0]

    # Create channel with human
    channel = await program.get_or_create_channel(agent, "human")

    # Check if any participant is human
    has_human = any(isinstance(p, HumanParticipant) for p in channel.participants)

    # Should have detected human participant
    assert has_human, "Channel should have HumanParticipant"

    # Verify streaming should be enabled
    stream_result = await program.start_stream(
        sender_id=agent.id,
        sender_klass=agent.klass,
        receiver_spec="human",
        stream_id="test_stream",
    )

    assert (
        stream_result.should_stream
    ), "Streaming should be enabled for human recipients"


@pytest.mark.asyncio
async def test_llm_streaming_uses_channel_infrastructure():
    """Test that LLM response streaming uses channel-based infrastructure.

    Regression: _stream_llm_response() was calling legacy start_streaming_say()
    which is now a no-op, instead of start_streaming_say_via_channel().

    Fixed by: Updated playbook.py to use channel-based streaming methods
    """
    event_bus = EventBus(session_id="test")

    # Create program
    program_content = "# TestAgent\n## TestPlaybook\n### Steps\n- Do something"
    program = Program(
        event_bus=event_bus,
        program_content=program_content,
    )
    await program.initialize()

    agent = program.agents[0]

    # Verify that start_streaming_say_via_channel returns a StreamResult
    result = await agent.start_streaming_say_via_channel("human")

    # Should return StreamResult with should_stream=True for human
    assert result is not None
    assert hasattr(result, "should_stream")
    assert hasattr(result, "stream_id")

    # For human recipient, streaming should be enabled
    assert result.should_stream


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

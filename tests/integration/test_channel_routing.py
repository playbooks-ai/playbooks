"""Integration tests for channel-based message routing."""

import asyncio

import pytest
import pytest_asyncio

from playbooks.agents.human_agent import HumanAgent
from playbooks.core.message import MessageType
from playbooks.infrastructure.event_bus import EventBus
from playbooks.program import Program


@pytest.fixture
def simple_program_content():
    """Create a simple program with two agents for testing."""
    return """
```public.json
[
  {"name": "Main", "description": "Main playbook"}
]
```

# AgentA
You are Agent A.

## Main
### Triggers
- At the beginning

### Steps
- Set done to true

```public.json
[
  {"name": "Main", "description": "Main playbook"}
]
```

# AgentB  
You are Agent B.

## Main
### Triggers
- At the beginning

### Steps
- Set done to true
"""


@pytest_asyncio.fixture
async def program_with_agents(simple_program_content):
    """Create a program with initialized agents."""
    event_bus = EventBus(session_id="test-session")
    program = Program(
        event_bus=event_bus,
        program_content=simple_program_content,
    )
    await program.initialize()

    # Manually create agent instances for testing
    for klass in program.agent_klasses.values():
        await program.create_agent(klass)
        # Don't add to program.agents (it's managed separately)

    return program


@pytest.mark.asyncio
class TestChannelRouting:
    """Test message routing through channels."""

    async def test_direct_message_creates_channel(self, program_with_agents):
        """Test that sending a direct message creates a channel."""
        program = program_with_agents

        # Get agents (excluding human)
        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        assert len(agents) == 2, f"Expected 2 agents, got {len(agents)}"
        agent_a = agents[0]
        agent_b = agents[1]

        # Initially no channels
        assert len(program.channels) == 0

        # Send message from A to B
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"agent {agent_b.id}",
            message="Hello from A",
            message_type=MessageType.DIRECT,
        )

        # Channel should be created
        assert len(program.channels) == 1

        # Channel should have both participants
        channel_id = program._make_channel_id(agent_a.id, agent_b.id)
        channel = program.channels[channel_id]
        assert channel.participant_count == 2

    async def test_direct_message_delivered_to_recipient(self, program_with_agents):
        """Test that direct messages are delivered to the recipient."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        agent_a = agents[0]
        agent_b = agents[1]

        # Send message
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"agent {agent_b.id}",
            message="Test message",
            message_type=MessageType.DIRECT,
        )

        # Agent B should have received the message
        assert agent_b._message_queue.size == 1
        msg = await agent_b._message_queue.peek()
        assert msg.content == "Test message"
        assert msg.sender_id.id == agent_a.id

    async def test_direct_message_not_delivered_to_sender(self, program_with_agents):
        """Test that the sender doesn't receive their own message."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        agent_a = agents[0]
        agent_b = agents[1]

        # Send message
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"agent {agent_b.id}",
            message="Test message",
            message_type=MessageType.DIRECT,
        )

        # Agent A should NOT have received their own message
        assert agent_a._message_queue.size == 0

    async def test_channel_reused_for_same_participants(self, program_with_agents):
        """Test that the same channel is reused for the same participants."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        agent_a = agents[0]
        agent_b = agents[1]

        # Send first message
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"agent {agent_b.id}",
            message="Message 1",
            message_type=MessageType.DIRECT,
        )

        initial_channel_count = len(program.channels)

        # Send second message
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"agent {agent_b.id}",
            message="Message 2",
            message_type=MessageType.DIRECT,
        )

        # Should still have the same number of channels
        assert len(program.channels) == initial_channel_count

        # Agent B should have received both messages
        assert agent_b._message_queue.size == 2

    async def test_bidirectional_communication_uses_same_channel(
        self, program_with_agents
    ):
        """Test that A→B and B→A use the same channel."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        agent_a = agents[0]
        agent_b = agents[1]

        # A sends to B
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"agent {agent_b.id}",
            message="Message from A",
            message_type=MessageType.DIRECT,
        )

        # B sends to A
        await program.route_message(
            sender_id=agent_b.id,
            sender_klass=agent_b.klass,
            receiver_spec=f"agent {agent_a.id}",
            message="Message from B",
            message_type=MessageType.DIRECT,
        )

        # Should only have one channel
        assert len(program.channels) == 1

    async def test_message_to_human(self, program_with_agents):
        """Test sending a message to human."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        agent_a = agents[0]
        human = program.agents_by_id["human"]

        # Send message to human
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec="human",
            message="Hello human",
            message_type=MessageType.DIRECT,
        )

        # Channel should be created
        channel_id = program._make_channel_id(agent_a.id, "human")
        assert channel_id in program.channels

        # Human should receive the message
        assert human._message_queue.size == 1


@pytest.mark.asyncio
class TestTargetedMessaging:
    """Test agent targeting in meetings."""

    async def test_parse_meeting_with_single_target(self, program_with_agents):
        """Test parsing meeting spec with single target agent."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        agent_a = agents[0]

        # Create a mock meeting channel first
        meeting_id = "100"
        mock_participants = agents
        await program.create_meeting_channel(meeting_id, mock_participants)

        # Send message with targeting
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"meeting {meeting_id}, agent {mock_participants[1].id}",
            message="Question for AgentB",
            message_type=MessageType.MEETING_BROADCAST,
        )

        # Flush pending messages to ensure they are delivered to the queue
        agent_b = mock_participants[1]
        await agent_b.meeting_manager.flush_pending_messages(meeting_id)

        # Wait a bit for the async delivery task to complete
        await asyncio.sleep(0.1)

        # Agent B should have received the message with targeting metadata
        assert agent_b._message_queue.size == 1
        message = await agent_b._message_queue.peek()
        assert message.target_agent_ids is not None
        # target_agent_ids is now a list of AgentID objects
        assert any(aid.id == agent_b.id for aid in message.target_agent_ids)

    async def test_parse_meeting_with_multiple_targets(self, program_with_agents):
        """Test parsing meeting spec with multiple target agents."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        agent_a = agents[0]
        agent_b = agents[1]

        # Create mock meeting
        meeting_id = "101"
        mock_participants = [agent_a, agent_b]
        await program.create_meeting_channel(meeting_id, mock_participants)

        # Send with multiple targets
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"meeting {meeting_id}, agent {agent_b.id}",
            message="Question for both",
            message_type=MessageType.MEETING_BROADCAST,
        )

        # Flush pending messages
        await agent_b.meeting_manager.flush_pending_messages(meeting_id)
        await asyncio.sleep(0.1)

        # Agent B should receive with targeting
        message = await agent_b._message_queue.peek()
        assert message.target_agent_ids is not None
        assert len(message.target_agent_ids) == 1

    async def test_meeting_message_without_targeting(self, program_with_agents):
        """Test meeting message without targeting (broadcast to all)."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        agent_a = agents[0]
        agent_b = agents[1]

        # Create meeting
        meeting_id = "102"
        await program.create_meeting_channel(meeting_id, [agent_a, agent_b])

        # Send without targeting
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"meeting {meeting_id}",
            message="Broadcast to all",
            message_type=MessageType.MEETING_BROADCAST,
        )

        # Flush pending messages
        await agent_b.meeting_manager.flush_pending_messages(meeting_id)
        await asyncio.sleep(0.1)

        # Agent B should receive without targeting metadata
        message = await agent_b._message_queue.peek()
        assert message.target_agent_ids is None


@pytest.mark.asyncio
class TestChannelProperties:
    """Test channel properties and behavior."""

    async def test_channel_is_direct_property(self, program_with_agents):
        """Test that 2-participant channels are marked as direct."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        agent_a = agents[0]
        agent_b = agents[1]

        # Create channel
        await program.route_message(
            sender_id=agent_a.id,
            sender_klass=agent_a.klass,
            receiver_spec=f"agent {agent_b.id}",
            message="Test",
            message_type=MessageType.DIRECT,
        )

        channel_id = program._make_channel_id(agent_a.id, agent_b.id)
        channel = program.channels[channel_id]

        assert channel.is_direct is True
        assert channel.is_meeting is False

    async def test_channel_is_meeting_property(self, program_with_agents):
        """Test that N-participant channels are marked as meetings."""
        program = program_with_agents

        agents = [a for a in program.agents if not isinstance(a, HumanAgent)]
        participants = agents

        # Create meeting channel
        meeting_id = "103"
        channel = await program.create_meeting_channel(meeting_id, participants)

        # With 2 participants, it's direct
        assert channel.is_direct is True

        # Add human to make it a meeting
        human = program.agents_by_id["human"]
        human_participant = program._to_participant(human)
        channel.add_participant(human_participant)

        # Now it's a meeting
        assert channel.is_meeting is True
        assert channel.is_direct is False

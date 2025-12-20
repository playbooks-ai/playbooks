"""
Test for agent-to-agent communication timeout issue.

Reproduces bug where:
1. Agent A sends message to Agent B via SendMessage()
2. Agent A calls Yield("agent B") to wait for response
3. Agent B takes >5 seconds to respond
4. Agent A times out and continues without response
5. Response arrives later but AgentCommunicationLLMMessage is never created in proper context
"""

import asyncio

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.core.identifiers import AgentID
from playbooks.core.message import Message, MessageType
from playbooks.execution.python_executor import PythonExecutor
from playbooks.infrastructure.event_bus import EventBus
from playbooks.llm.messages import AgentCommunicationLLMMessage


class MockProgram:
    """Mock program for testing."""

    def __init__(self, event_bus):
        self.agents_by_id = {}
        self.execution_finished = False
        self.event_bus = event_bus
        self._debug_server = None  # No debug server in tests

    async def route_message(
        self, sender_id, sender_klass, receiver_spec, message, **kwargs
    ):
        """Route message directly to recipient's buffer."""
        # Parse receiver spec to get ID
        receiver_id = receiver_spec.replace("agent ", "")
        if receiver_id in self.agents_by_id:
            recipient = self.agents_by_id[receiver_id]
            msg = Message(
                sender_id=AgentID.parse(sender_id),
                sender_klass=sender_klass,
                content=message,
                recipient_id=AgentID.parse(receiver_id),
                recipient_klass=recipient.klass,
                message_type=MessageType.DIRECT,
                meeting_id=None,
            )
            await recipient._add_message_to_buffer(msg)


class SlowRespondingAgent(AIAgent):
    """Mock agent that responds slowly to messages."""

    klass = "SlowAgent"
    description = "Agent that takes >5s to respond"
    metadata = {}
    playbooks = {}
    namespace_manager = None

    def __init__(self, event_bus, agent_id, delay_seconds=6):
        super().__init__(event_bus, agent_id=agent_id)
        self.delay_seconds = delay_seconds
        self.response_sent = False

    async def discover_playbooks(self):
        """No playbooks to discover."""
        pass

    async def process_and_respond(self, question_message):
        """Simulate slow processing and send response."""
        await asyncio.sleep(self.delay_seconds)
        # Send response
        await self.SendMessage(question_message.sender_id.id, "Response: 15%")
        self.response_sent = True


class FastRequestingAgent(AIAgent):
    """Mock agent that sends request and waits."""

    klass = "FastAgent"
    description = "Agent that sends request and waits"
    metadata = {}
    playbooks = {}
    namespace_manager = None

    def __init__(self, event_bus, agent_id):
        super().__init__(event_bus, agent_id=agent_id)
        self.received_messages = []

    async def discover_playbooks(self):
        """No playbooks to discover."""
        pass


@pytest.mark.asyncio
class TestAgentTimeoutResponse:
    """Test agent-to-agent timeout scenarios."""

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing."""
        return EventBus("test_timeout_session")

    @pytest.fixture
    def mock_program(self, event_bus):
        """Create mock program."""
        return MockProgram(event_bus)

    async def test_timeout_returns_system_notification(self, event_bus, mock_program):
        """
        Test that timeout returns a system notification allowing LLM to decide next action.

        With the new progressive timeout system:
        1. Agent A sends message to Agent B via Yld()
        2. Agent B takes 6 seconds to respond
        3. After 5s, Yld() returns system notification (not None)
        4. LLM sees "agent hasn't replied in 5 seconds" and can decide to wait more
        5. LLM calls Yld() again and eventually gets the response
        """
        # Create agents
        agent_a = FastRequestingAgent(event_bus, "1000")
        agent_b = SlowRespondingAgent(event_bus, "1001", delay_seconds=6)

        # Setup program
        agent_a.program = mock_program
        agent_b.program = mock_program
        mock_program.agents_by_id = {"1000": agent_a, "1001": agent_b}

        # Agent A sends message to Agent B
        question = "What is the tax rate?"
        await agent_a.SendMessage("1001", question)

        # Start Agent B's slow processing in background
        question_msg = Message(
            sender_id=AgentID.parse("1000"),
            sender_klass=agent_a.klass,
            content=question,
            recipient_id=AgentID.parse("1001"),
            recipient_klass=agent_b.klass,
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
        process_task = asyncio.create_task(agent_b.process_and_respond(question_msg))

        # Create executor to test Yld() behavior
        executor = PythonExecutor(agent_a)

        # Agent A yields waiting for response (will timeout after 5s)
        print("\n=== Agent A calling Yld('1001') - will timeout after 5s... ===")
        response = await executor.capture_yld("1001")

        # ASSERT: Got system notification (not None)
        print(f"=== Agent A received response: {response[:100]}... ===")
        assert response is not None, "Should receive system notification, not None"
        assert "hasn't replied in 5" in response, "Should contain timeout notification"
        assert "1001" in response, "Should mention target agent"
        assert "await self.Yld" in response, "Should tell LLM how to continue waiting"

        print("=== SYSTEM NOTIFICATION VERIFIED ===")
        print(f"Response: {response}")

        # Wait for Agent B to finish (response arrives after timeout)
        await process_task
        assert agent_b.response_sent, "Agent B should have sent response"
        print("\n=== Agent B has sent response (late) ===")

        # Give message routing time to complete
        await asyncio.sleep(0.1)

        # LLM decides to wait more - call Yld() again
        print("=== Agent A calling Yld('1001') again to continue waiting... ===")
        response2 = await executor.capture_yld("1001")

        # ASSERT: Now we get the actual response
        print(f"=== Agent A received response: {response2} ===")
        assert response2 is not None, "Should receive response"
        assert "15%" in response2, "Should contain actual response from agent"

        print("\n=== FIX VERIFIED ===")
        print("1. First Yld() returned system notification after 5s timeout")
        print("2. LLM could see the notification and decide to wait more")
        print("3. Second Yld() successfully received the late response")
        print("4. No messages were lost or orphaned")

    async def test_successful_response_within_timeout(self, event_bus, mock_program):
        """
        Test normal case where response arrives within timeout.

        This test verifies the expected behavior works correctly.
        """
        # Create agents (fast responder)
        agent_a = FastRequestingAgent(event_bus, "1000")
        agent_b = SlowRespondingAgent(
            event_bus, "1001", delay_seconds=1
        )  # Fast response

        # Setup program
        agent_a.program = mock_program
        agent_b.program = mock_program
        mock_program.agents_by_id = {"1000": agent_a, "1001": agent_b}

        # Agent A sends message
        question = "What is the tax rate?"
        await agent_a.SendMessage("1001", question)

        # Start processing
        question_msg = Message(
            sender_id=AgentID.parse("1000"),
            sender_klass=agent_a.klass,
            content=question,
            recipient_id=AgentID.parse("1001"),
            recipient_klass=agent_b.klass,
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
        process_task = asyncio.create_task(agent_b.process_and_respond(question_msg))

        # Agent A waits (should succeed)
        print("\n=== Agent A waiting for response (fast response expected)... ===")
        messages = await agent_a.WaitForMessage("1001", timeout=5.0)

        await process_task

        # ASSERT: Message received within timeout
        print(f"=== Agent A received {len(messages)} message(s) within timeout ===")
        assert len(messages) == 1
        assert "15%" in messages[0].content

        # ASSERT: AgentCommunicationLLMMessage created immediately
        print(
            f"=== Agent A call stack has {len(agent_a.call_stack.top_level_llm_messages)} messages ==="
        )
        assert (
            len(agent_a.call_stack.top_level_llm_messages) == 2
        ), "Should have both sent and received messages"
        received_msg = agent_a.call_stack.top_level_llm_messages[1]
        assert isinstance(received_msg, AgentCommunicationLLMMessage)
        assert "15%" in received_msg.content

        print("\n=== NORMAL BEHAVIOR VERIFIED ===")
        print("Response arrived within timeout and was properly logged in call stack.")

    async def test_timeout_with_interrupt_messages(self, event_bus, mock_program):
        """
        Test that interrupt messages from other sources are delivered with timeout notification.

        When waiting for agent 1001 and timeout occurs, messages from user or other agents
        should be delivered along with the timeout notification.
        """
        # Create agents
        agent_a = FastRequestingAgent(event_bus, "1000")
        agent_b = SlowRespondingAgent(event_bus, "1001", delay_seconds=10)

        # Setup program
        agent_a.program = mock_program
        agent_b.program = mock_program
        mock_program.agents_by_id = {"1000": agent_a, "1001": agent_b}

        # Agent A sends message to Agent B
        await agent_a.SendMessage("1001", "Calculate tax rate")

        # Start Agent B's slow processing
        question_msg = Message(
            sender_id=AgentID.parse("1000"),
            sender_klass=agent_a.klass,
            content="Calculate tax rate",
            recipient_id=AgentID.parse("1001"),
            recipient_klass=agent_b.klass,
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
        process_task = asyncio.create_task(agent_b.process_and_respond(question_msg))

        # While Agent A is waiting, simulate user sending interrupt message
        async def send_user_interrupt():
            await asyncio.sleep(2.5)  # Send after 2.5s
            user_msg = Message(
                sender_id=AgentID.parse("human"),
                sender_klass="User",
                content="Are you still there?",
                recipient_id=AgentID.parse("1000"),
                recipient_klass=agent_a.klass,
                message_type=MessageType.DIRECT,
                meeting_id=None,
            )
            await agent_a._add_message_to_buffer(user_msg)

        interrupt_task = asyncio.create_task(send_user_interrupt())

        # Create executor
        executor = PythonExecutor(agent_a)

        # Agent A yields waiting for agent 1001
        print("\n=== Agent A calling Yld('1001') - user interrupt will arrive... ===")
        response = await executor.capture_yld("1001")

        await interrupt_task

        # ASSERT: Response contains both interrupt message and timeout notification
        print(f"=== Agent A received response: {response} ===")
        assert response is not None
        assert (
            "Are you still there?" in response
        ), "Should contain user interrupt message"
        assert "User" in response, "Should indicate message is from user"
        assert "hasn't replied in 5" in response, "Should contain timeout notification"

        print("\n=== INTERRUPT HANDLING VERIFIED ===")
        print("User message was delivered along with timeout notification")
        print(f"Response:\n{response}")

        # Cleanup
        process_task.cancel()
        try:
            await process_task
        except asyncio.CancelledError:
            pass

    async def test_timeout_value_is_5_seconds(self, event_bus, mock_program):
        """
        Verify that the default timeout for direct agent messages is 5 seconds.
        """
        agent_a = FastRequestingAgent(event_bus, "1000")
        agent_a.program = mock_program
        mock_program.agents_by_id = {"1000": agent_a}

        import time

        start_time = time.time()
        messages = await agent_a.WaitForMessage(
            "1001"
        )  # No timeout param, should use default
        elapsed = time.time() - start_time

        # Should timeout after approximately 5 seconds
        assert 4.5 <= elapsed <= 5.5, f"Expected ~5s timeout, got {elapsed}s"
        assert len(messages) == 0, "Should timeout with no messages"

        print(f"\n=== Confirmed: Default timeout is {elapsed:.2f}s (expected ~5s) ===")

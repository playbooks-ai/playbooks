"""Integration tests for agent communication with new CallStack top-level message handling."""

from unittest.mock import AsyncMock

import pytest

from playbooks.agents.ai_agent import AIAgent
from playbooks.infrastructure.event_bus import EventBus
from playbooks.llm.messages import AgentCommunicationLLMMessage
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer


class MockProgram:
    """Mock program for testing agent communication."""

    def __init__(self):
        self.agents_by_id = {}
        self.runtime = AsyncMock()
        self.execution_finished = False

    async def route_message(self, sender_id, receiver_spec, message):
        """Mock message routing."""
        return f"Response from {receiver_spec}"


class MockAIAgent(AIAgent):
    """Mock AIAgent for testing."""

    klass = "MockAIAgent"
    description = "Mock AIAgent for testing"
    metadata = {}
    playbooks = {}
    namespace_manager = None

    def __init__(self, event_bus: EventBus, agent_id: str):
        super().__init__(event_bus, agent_id=agent_id)

    async def discover_playbooks(self):
        pass


class TestAgentCommunicationIntegration:
    """Test agent communication integration with new CallStack functionality."""

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing."""
        return EventBus("test_session")

    @pytest.fixture
    def base_agent(self, event_bus):
        """Create base agent for testing."""
        agent = MockAIAgent(event_bus, "agent_1000")
        agent.program = MockProgram()
        return agent

    def test_send_message_with_empty_call_stack_adds_to_top_level(self, base_agent):
        """Test that agent communication with empty call stack adds to top_level_llm_messages."""
        # Ensure call stack is empty
        assert base_agent.call_stack.is_empty()

        # Simulate the message creation part of SendMessage (without async routing)
        message = "Hello, agent_2000!"
        target_agent_id = "agent_2000"

        # Create the agent communication message (same as in SendMessage)
        target_agent = base_agent.program.agents_by_id.get(target_agent_id)
        target_name = (
            str(target_agent) if target_agent else f"UnknownAgent({target_agent_id})"
        )
        agent_comm_msg = AgentCommunicationLLMMessage(
            f"I {str(base_agent)} sent message to {target_name}: {message}",
            sender_agent=base_agent.klass,
            target_agent=target_name,
        )

        # Test the call stack logic (same as in SendMessage)
        if hasattr(base_agent, "call_stack"):
            # Add to current frame or top-level if stack is empty
            base_agent.call_stack.add_llm_message(agent_comm_msg)

        # Check that message was added to top-level
        assert len(base_agent.call_stack.top_level_llm_messages) == 1

        comm_msg = base_agent.call_stack.top_level_llm_messages[0]
        assert isinstance(comm_msg, AgentCommunicationLLMMessage)
        assert message in comm_msg.content
        assert "MockAIAgent" in comm_msg.content

    def test_send_message_with_call_stack_frame_adds_to_frame(self, base_agent):
        """Test that agent communication with call stack frame adds to current frame."""
        # Add a frame to call stack
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        base_agent.call_stack.push(frame)

        # Simulate agent communication logic
        message = "Hello from playbook!"
        target_agent_id = "agent_2000"

        agent_comm_msg = AgentCommunicationLLMMessage(
            f"I {str(base_agent)} sent message to UnknownAgent({target_agent_id}): {message}",
            sender_agent=base_agent.klass,
            target_agent=f"UnknownAgent({target_agent_id})",
        )

        # Test the call stack logic
        current_frame = base_agent.call_stack.peek()
        if current_frame is not None and current_frame.playbook == "Say":
            base_agent.call_stack.add_llm_message_on_parent(agent_comm_msg)
        else:
            base_agent.call_stack.add_llm_message(agent_comm_msg)

        # Check that message was added to frame, not top-level
        assert len(base_agent.call_stack.top_level_llm_messages) == 0
        assert len(frame.llm_messages) == 1

        comm_msg = frame.llm_messages[0]
        assert isinstance(comm_msg, AgentCommunicationLLMMessage)
        assert message in comm_msg.content

    def test_send_message_from_say_playbook_adds_to_parent(self, base_agent):
        """Test that agent communication from Say playbook adds to parent context."""
        # Add caller frame
        ip1 = InstructionPointer("caller_playbook", "01", 1)
        caller_frame = CallStackFrame(ip1)
        base_agent.call_stack.push(caller_frame)

        # Add Say frame
        ip2 = InstructionPointer("Say", "01", 1)
        say_frame = CallStackFrame(ip2)
        base_agent.call_stack.push(say_frame)

        # Simulate agent communication from Say playbook
        message = "Message from Say"
        agent_comm_msg = AgentCommunicationLLMMessage(
            f"I {str(base_agent)} sent message to UnknownAgent(agent_2000): {message}",
            sender_agent=base_agent.klass,
            target_agent="UnknownAgent(agent_2000)",
        )

        # Test the Say playbook logic
        current_frame = base_agent.call_stack.peek()
        if current_frame is not None and current_frame.playbook == "Say":
            base_agent.call_stack.add_llm_message_on_parent(agent_comm_msg)
        else:
            base_agent.call_stack.add_llm_message(agent_comm_msg)

        # Check that message was added to caller frame, not Say frame or top-level
        assert len(base_agent.call_stack.top_level_llm_messages) == 0
        assert len(say_frame.llm_messages) == 0
        assert len(caller_frame.llm_messages) == 1

        comm_msg = caller_frame.llm_messages[0]
        assert isinstance(comm_msg, AgentCommunicationLLMMessage)
        assert message in comm_msg.content


class TestCallStackMethodsIntegration:
    """Test CallStack methods integration scenarios."""

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing."""
        return EventBus("test_session")

    @pytest.fixture
    def call_stack(self, event_bus):
        """Create call stack for testing."""
        return CallStack(event_bus, "test_agent")

    def test_add_llm_message_vs_add_on_parent_behavior(self, call_stack):
        """Test behavioral differences between add_llm_message and add_on_parent."""
        from playbooks.llm.messages import UserInputLLMMessage

        # Test with empty stack
        msg1 = UserInputLLMMessage(instruction="Message 1")
        msg2 = UserInputLLMMessage(instruction="Message 2")

        call_stack.add_llm_message(msg1)  # Should go to top-level
        call_stack.add_llm_message_on_parent(msg2)  # Should also go to top-level

        assert len(call_stack.top_level_llm_messages) == 2

        # Test with one frame
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        call_stack.push(frame)

        msg3 = UserInputLLMMessage(instruction="Message 3")
        msg4 = UserInputLLMMessage(instruction="Message 4")

        call_stack.add_llm_message(msg3)  # Should go to frame
        call_stack.add_llm_message_on_parent(
            msg4
        )  # Should go to top-level (no parent frame)

        assert len(call_stack.top_level_llm_messages) == 3  # msg1, msg2, msg4
        assert len(frame.llm_messages) == 1  # msg3

        # Test with two frames
        ip2 = InstructionPointer("called_playbook", "01", 1)
        frame2 = CallStackFrame(ip2)
        call_stack.push(frame2)

        msg5 = UserInputLLMMessage(instruction="Message 5")
        msg6 = UserInputLLMMessage(instruction="Message 6")

        call_stack.add_llm_message(msg5)  # Should go to frame2
        call_stack.add_llm_message_on_parent(
            msg6
        )  # Should go to frame (parent of frame2)

        assert len(call_stack.top_level_llm_messages) == 3  # unchanged
        assert len(frame.llm_messages) == 2  # msg3, msg6
        assert len(frame2.llm_messages) == 1  # msg5

    def test_deprecated_methods_still_work(self, call_stack):
        """Test that deprecated methods still work correctly."""
        from playbooks.llm.messages import UserInputLLMMessage

        # Test add_llm_message_with_fallback
        msg1 = UserInputLLMMessage(instruction="Fallback test")
        result = call_stack.add_llm_message_with_fallback(msg1)

        assert result is False  # No frame to add to
        assert len(call_stack.top_level_llm_messages) == 1

        # Add frame and test again
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        call_stack.push(frame)

        msg2 = UserInputLLMMessage(instruction="Fallback test 2")
        result = call_stack.add_llm_message_with_fallback(msg2)

        assert result is True  # Added to frame
        assert len(frame.llm_messages) == 1

        # Test add_llm_message_on_caller
        msg3 = UserInputLLMMessage(instruction="Caller test")
        call_stack.add_llm_message_on_caller(msg3)

        # Should behave same as add_on_parent (go to top-level since only one frame)
        assert len(call_stack.top_level_llm_messages) == 2  # msg1, msg3

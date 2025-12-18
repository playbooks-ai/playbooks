"""Tests for CallStack top-level message handling functionality."""

from playbooks.infrastructure.event_bus import EventBus
from playbooks.llm.messages import (
    AgentCommunicationLLMMessage,
    AssistantResponseLLMMessage,
    PlaybookImplementationLLMMessage,
    UserInputLLMMessage,
)
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer


class TestCallStackTopLevelMessages:
    """Test top-level message handling in CallStack."""

    def test_empty_call_stack_has_empty_top_level_messages(self):
        """Test that new call stack has empty top-level messages."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        assert call_stack.top_level_llm_messages == []

    def test_add_llm_message_to_empty_stack_goes_to_top_level(self):
        """Test that adding message to empty stack goes to top_level_llm_messages."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        msg = UserInputLLMMessage(instruction="Test message")
        call_stack.add_llm_message(msg)

        assert len(call_stack.top_level_llm_messages) == 1
        assert call_stack.top_level_llm_messages[0] == msg

    def test_add_llm_message_to_stack_with_frame_goes_to_frame(self):
        """Test that adding message to stack with frame goes to current frame."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add a frame
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        call_stack.push(frame)

        msg = UserInputLLMMessage(instruction="Test message")
        call_stack.add_llm_message(msg)

        # Should go to frame, not top-level
        assert len(call_stack.top_level_llm_messages) == 0
        assert len(frame.llm_messages) == 1
        assert frame.llm_messages[0] == msg

    def test_add_multiple_messages_to_empty_stack(self):
        """Test adding multiple messages to empty stack."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        msg1 = UserInputLLMMessage(instruction="Message 1")
        msg2 = AssistantResponseLLMMessage("Message 2")
        msg3 = AgentCommunicationLLMMessage("Message 3", "Agent1", "Agent2")

        call_stack.add_llm_message(msg1)
        call_stack.add_llm_message(msg2)
        call_stack.add_llm_message(msg3)

        assert len(call_stack.top_level_llm_messages) == 3
        assert call_stack.top_level_llm_messages[0] == msg1
        assert call_stack.top_level_llm_messages[1] == msg2
        assert call_stack.top_level_llm_messages[2] == msg3

    def test_get_llm_messages_includes_top_level_messages(self):
        """Test that get_llm_messages includes top-level messages."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        msg1 = UserInputLLMMessage(instruction="Top level message 1")
        msg2 = UserInputLLMMessage(instruction="Top level message 2")

        call_stack.add_llm_message(msg1)
        call_stack.add_llm_message(msg2)

        messages = call_stack.get_llm_messages()

        assert len(messages) == 2
        assert messages[0]["content"] == "Top level message 1"
        assert messages[1]["content"] == "Top level message 2"

    def test_get_llm_messages_combines_frame_and_top_level_messages(self):
        """Test that get_llm_messages combines frame and top-level messages."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add top-level message first
        top_msg = UserInputLLMMessage(instruction="Top level message")
        call_stack.add_llm_message(top_msg)

        # Add a frame with messages
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        frame_msg = PlaybookImplementationLLMMessage("Frame message", "test")
        frame.add_llm_message(frame_msg)
        call_stack.push(frame)

        # Add another top-level message (should go to frame now)
        frame_msg2 = UserInputLLMMessage(instruction="Another message")
        call_stack.add_llm_message(frame_msg2)

        messages = call_stack.get_llm_messages()

        # Should have: top_msg + frame_msg + frame_msg2
        assert len(messages) == 3
        # Top-level messages come first, then frame messages
        assert messages[0]["content"] == "Top level message"  # top-level first
        assert messages[1]["content"] == "Frame message"  # frame messages
        assert messages[2]["content"] == "Another message"  # went to frame

    def test_transition_from_empty_to_frame_preserves_top_level(self):
        """Test that pushing frame after top-level messages preserves them."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add messages to empty stack (go to top-level)
        msg1 = UserInputLLMMessage(instruction="Before frame 1")
        msg2 = UserInputLLMMessage(instruction="Before frame 2")
        call_stack.add_llm_message(msg1)
        call_stack.add_llm_message(msg2)

        # Push a frame
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        call_stack.push(frame)

        # Add message after frame (should go to frame)
        msg3 = UserInputLLMMessage(instruction="After frame")
        call_stack.add_llm_message(msg3)

        # Check that top-level messages are preserved
        assert len(call_stack.top_level_llm_messages) == 2
        assert call_stack.top_level_llm_messages[0] == msg1
        assert call_stack.top_level_llm_messages[1] == msg2

        # Check that new message went to frame
        assert len(frame.llm_messages) == 1
        assert frame.llm_messages[0] == msg3

    def test_pop_frame_returns_to_top_level_behavior(self):
        """Test that popping all frames returns to top-level message behavior."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add frame
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        call_stack.push(frame)

        # Add message to frame
        msg1 = UserInputLLMMessage(instruction="Frame message")
        call_stack.add_llm_message(msg1)

        # Pop frame
        call_stack.pop()

        # Add message after pop (should go to top-level)
        msg2 = UserInputLLMMessage(instruction="After pop")
        call_stack.add_llm_message(msg2)

        assert len(call_stack.top_level_llm_messages) == 1
        assert call_stack.top_level_llm_messages[0] == msg2


class TestCallStackAddLLMMessageOnParent:
    """Test add_llm_message_on_parent functionality."""

    def test_add_on_parent_with_no_frames_goes_to_top_level(self):
        """Test that add_on_parent with no frames goes to top_level_llm_messages."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        msg = AgentCommunicationLLMMessage("Parent message", "Agent1", "Agent2")
        call_stack.add_llm_message_on_parent(msg)

        assert len(call_stack.top_level_llm_messages) == 1
        assert call_stack.top_level_llm_messages[0] == msg

    def test_add_on_parent_with_one_frame_goes_to_top_level(self):
        """Test that add_on_parent with only one frame goes to top_level_llm_messages."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add one frame
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        call_stack.push(frame)

        msg = AgentCommunicationLLMMessage("Parent message", "Agent1", "Agent2")
        call_stack.add_llm_message_on_parent(msg)

        # Should go to top-level (no parent frame)
        assert len(call_stack.top_level_llm_messages) == 1
        assert call_stack.top_level_llm_messages[0] == msg
        assert len(frame.llm_messages) == 0

    def test_add_on_parent_with_two_frames_goes_to_caller(self):
        """Test that add_on_parent with two frames goes to caller frame."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add two frames
        ip1 = InstructionPointer("caller_playbook", "01", 1)
        caller_frame = CallStackFrame(ip1)
        call_stack.push(caller_frame)

        ip2 = InstructionPointer("called_playbook", "01", 1)
        called_frame = CallStackFrame(ip2)
        call_stack.push(called_frame)

        msg = AgentCommunicationLLMMessage("Parent message", "Agent1", "Agent2")
        call_stack.add_llm_message_on_parent(msg)

        # Should go to caller frame (second from top)
        assert len(call_stack.top_level_llm_messages) == 0
        assert len(caller_frame.llm_messages) == 1
        assert caller_frame.llm_messages[0] == msg
        assert len(called_frame.llm_messages) == 0

    def test_add_on_parent_with_three_frames_goes_to_caller(self):
        """Test that add_on_parent with three frames goes to caller frame."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add three frames
        ip1 = InstructionPointer("root_playbook", "01", 1)
        root_frame = CallStackFrame(ip1)
        call_stack.push(root_frame)

        ip2 = InstructionPointer("caller_playbook", "01", 1)
        caller_frame = CallStackFrame(ip2)
        call_stack.push(caller_frame)

        ip3 = InstructionPointer("called_playbook", "01", 1)
        called_frame = CallStackFrame(ip3)
        call_stack.push(called_frame)

        msg = AgentCommunicationLLMMessage("Parent message", "Agent1", "Agent2")
        call_stack.add_llm_message_on_parent(msg)

        # Should go to caller frame (second from top)
        assert len(call_stack.top_level_llm_messages) == 0
        assert len(root_frame.llm_messages) == 0
        assert len(caller_frame.llm_messages) == 1
        assert caller_frame.llm_messages[0] == msg
        assert len(called_frame.llm_messages) == 0


class TestCallStackAddLLMMessageOnCallerDeprecated:
    """Test deprecated add_llm_message_on_caller method."""

    def test_add_on_caller_delegates_to_add_on_parent(self):
        """Test that add_on_caller delegates to add_on_parent."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        msg = AgentCommunicationLLMMessage("Caller message", "Agent1", "Agent2")
        call_stack.add_llm_message_on_caller(msg)

        # Should behave same as add_on_parent (go to top-level when no frames)
        assert len(call_stack.top_level_llm_messages) == 1
        assert call_stack.top_level_llm_messages[0] == msg


class TestCallStackAddLLMMessageWithFallbackDeprecated:
    """Test deprecated add_llm_message_with_fallback method."""

    def test_add_with_fallback_empty_stack_returns_false(self):
        """Test that add_with_fallback on empty stack returns False and adds to top-level."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        msg = UserInputLLMMessage(instruction="Fallback message")
        result = call_stack.add_llm_message_with_fallback(msg)

        assert result is False  # No frame to add to
        assert len(call_stack.top_level_llm_messages) == 1
        assert call_stack.top_level_llm_messages[0] == msg

    def test_add_with_fallback_with_frame_returns_true(self):
        """Test that add_with_fallback with frame returns True and adds to frame."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add frame
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        call_stack.push(frame)

        msg = UserInputLLMMessage(instruction="Fallback message")
        result = call_stack.add_llm_message_with_fallback(msg)

        assert result is True  # Added to frame
        assert len(call_stack.top_level_llm_messages) == 0
        assert len(frame.llm_messages) == 1
        assert frame.llm_messages[0] == msg


class TestCallStackMessageOrderAndIntegration:
    """Test message ordering and integration scenarios."""

    def test_complex_scenario_with_mixed_messages(self):
        """Test complex scenario with mixed frame and top-level messages."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # 1. Add messages to empty stack (go to top-level)
        msg1 = UserInputLLMMessage(instruction="Initial message")
        call_stack.add_llm_message(msg1)

        # 2. Push frame and add messages
        ip1 = InstructionPointer("playbook1", "01", 1)
        frame1 = CallStackFrame(ip1)
        call_stack.push(frame1)

        msg2 = PlaybookImplementationLLMMessage("Playbook 1 start", "playbook1")
        call_stack.add_llm_message(msg2)

        # 3. Push another frame
        ip2 = InstructionPointer("playbook2", "01", 1)
        frame2 = CallStackFrame(ip2)
        call_stack.push(frame2)

        msg3 = PlaybookImplementationLLMMessage("Playbook 2 start", "playbook2")
        call_stack.add_llm_message(msg3)

        # 4. Add message to parent context (should go to frame1)
        msg4 = AgentCommunicationLLMMessage("Communication", "Agent1", "Agent2")
        call_stack.add_llm_message_on_parent(msg4)

        # 5. Pop frame2
        call_stack.pop()

        # 6. Add message (should go to frame1)
        msg5 = AssistantResponseLLMMessage("Back to frame1")
        call_stack.add_llm_message(msg5)

        # 7. Pop frame1
        call_stack.pop()

        # 8. Add message (should go to top-level)
        msg6 = UserInputLLMMessage(instruction="Back to top level")
        call_stack.add_llm_message(msg6)

        # Verify final state
        messages = call_stack.get_llm_messages()

        # After popping all frames, only top-level messages remain
        # top-level: msg1, msg6
        assert len(messages) == 2

        # Top-level messages in order they were added
        assert messages[0]["content"] == "Initial message"  # msg1
        assert messages[1]["content"] == "Back to top level"  # msg6

        # Verify that frame1 still has its messages (even though popped)
        assert len(frame1.llm_messages) == 3  # msg2, msg4, msg5

    def test_get_llm_messages_preserves_order_within_categories(self):
        """Test that get_llm_messages preserves order within frame and top-level categories."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add multiple top-level messages
        top_msg1 = UserInputLLMMessage(instruction="Top 1")
        top_msg2 = UserInputLLMMessage(instruction="Top 2")
        call_stack.add_llm_message(top_msg1)
        call_stack.add_llm_message(top_msg2)

        # Add frame with multiple messages
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)
        frame_msg1 = PlaybookImplementationLLMMessage("Frame 1", "test")
        frame_msg2 = PlaybookImplementationLLMMessage("Frame 2", "test")
        frame.add_llm_message(frame_msg1)
        frame.add_llm_message(frame_msg2)
        call_stack.push(frame)

        # Add more messages to frame
        frame_msg3 = UserInputLLMMessage(instruction="Frame 3")
        call_stack.add_llm_message(frame_msg3)

        messages = call_stack.get_llm_messages()

        # Should be: top-level messages in order, then frame messages in order
        assert len(messages) == 5
        assert messages[0]["content"] == "Top 1"  # top-level messages first
        assert messages[1]["content"] == "Top 2"
        assert messages[2]["content"] == "Frame 1"  # frame messages last
        assert messages[3]["content"] == "Frame 2"
        assert messages[4]["content"] == "Frame 3"

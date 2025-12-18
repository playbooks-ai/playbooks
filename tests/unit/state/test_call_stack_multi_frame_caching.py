"""Tests for message handling across multiple call stack frames.

Note: Frame-based caching is applied by InterpreterPrompt just-in-time,
not by the call stack itself. These tests verify message collection.
"""

from playbooks.infrastructure.event_bus import EventBus
from playbooks.llm.messages import (
    AssistantResponseLLMMessage,
    PlaybookImplementationLLMMessage,
    UserInputLLMMessage,
)
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer


class TestMultiFrameMessages:
    """Test message collection across multiple call stack frames."""

    def test_empty_call_stack_returns_empty_list(self):
        """Test that an empty call stack returns an empty message list."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        messages = call_stack.get_llm_messages()

        assert messages == []

    def test_single_frame_with_multiple_messages(self):
        """Test message collection from one frame with multiple messages."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        ip1 = InstructionPointer("playbook1", "01", 1)
        frame1 = CallStackFrame(ip1)

        msg1 = PlaybookImplementationLLMMessage("# Playbook 1", "playbook1")
        msg2 = UserInputLLMMessage(instruction="Execute step 1")
        msg3 = AssistantResponseLLMMessage("Step 1 complete")

        frame1.add_llm_message(msg1)
        frame1.add_llm_message(msg2)
        frame1.add_llm_message(msg3)

        call_stack.push(frame1)

        messages = call_stack.get_llm_messages()

        assert len(messages) == 3
        # No caching at call stack level - applied later by InterpreterPrompt
        for msg in messages:
            assert "cache_control" not in msg

    def test_multiple_frames_messages_combined(self):
        """Test that messages from multiple frames are combined in order."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Frame 1: playbook1 with 2 messages
        ip1 = InstructionPointer("playbook1", "01", 1)
        frame1 = CallStackFrame(ip1)
        frame1.add_llm_message(PlaybookImplementationLLMMessage("# P1", "p1"))
        frame1.add_llm_message(AssistantResponseLLMMessage("Response 1"))
        call_stack.push(frame1)

        # Frame 2: playbook2 with 3 messages
        ip2 = InstructionPointer("playbook2", "01", 1)
        frame2 = CallStackFrame(ip2)
        frame2.add_llm_message(PlaybookImplementationLLMMessage("# P2", "p2"))
        frame2.add_llm_message(UserInputLLMMessage(instruction="Input 2"))
        frame2.add_llm_message(AssistantResponseLLMMessage("Response 2"))
        call_stack.push(frame2)

        messages = call_stack.get_llm_messages()

        # Should have 5 messages total (2 from frame1 + 3 from frame2)
        assert len(messages) == 5

        # Verify order is preserved (frame1 messages, then frame2 messages)
        assert messages[0]["content"] == "# P1"
        assert messages[1]["content"] == "Response 1"
        assert messages[2]["content"] == "# P2"
        assert messages[3]["content"] == "Input 2"
        assert messages[4]["content"] == "Response 2"

        # No caching at call stack level
        for msg in messages:
            assert "cache_control" not in msg

    def test_three_nested_frames(self):
        """Test message collection with three nested frames."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Frame 1: 1 message
        ip1 = InstructionPointer("main", "01", 1)
        frame1 = CallStackFrame(ip1)
        frame1.add_llm_message(UserInputLLMMessage(instruction="Start"))
        call_stack.push(frame1)

        # Frame 2: 2 messages
        ip2 = InstructionPointer("sub1", "01", 1)
        frame2 = CallStackFrame(ip2)
        frame2.add_llm_message(PlaybookImplementationLLMMessage("# Sub1", "sub1"))
        frame2.add_llm_message(AssistantResponseLLMMessage("Sub1 done"))
        call_stack.push(frame2)

        # Frame 3: 1 message
        ip3 = InstructionPointer("sub2", "01", 1)
        frame3 = CallStackFrame(ip3)
        frame3.add_llm_message(UserInputLLMMessage(instruction="Final"))
        call_stack.push(frame3)

        messages = call_stack.get_llm_messages()

        # Should have 4 messages total (1 + 2 + 1)
        assert len(messages) == 4
        assert messages[0]["content"] == "Start"
        assert messages[1]["content"] == "# Sub1"
        assert messages[2]["content"] == "Sub1 done"
        assert messages[3]["content"] == "Final"

    def test_frames_with_single_messages(self):
        """Test frames that each contain only one message."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Add 3 frames, each with only 1 message
        for i in range(3):
            ip = InstructionPointer(f"playbook{i}", "01", 1)
            frame = CallStackFrame(ip)
            frame.add_llm_message(UserInputLLMMessage(f"Message {i}"))
            call_stack.push(frame)

        messages = call_stack.get_llm_messages()

        # Should have 3 messages
        assert len(messages) == 3
        for i, msg in enumerate(messages):
            assert msg["content"] == f"Message {i}"

    def test_popping_frame_removes_its_messages(self):
        """Test that popping frames removes their messages from the stack."""
        event_bus = EventBus("test_session")
        call_stack = CallStack(event_bus, "test_agent")

        # Push 2 frames
        ip1 = InstructionPointer("p1", "01", 1)
        frame1 = CallStackFrame(ip1)
        frame1.add_llm_message(UserInputLLMMessage(instruction="Frame 1 msg 1"))
        frame1.add_llm_message(UserInputLLMMessage(instruction="Frame 1 msg 2"))
        call_stack.push(frame1)

        ip2 = InstructionPointer("p2", "01", 1)
        frame2 = CallStackFrame(ip2)
        frame2.add_llm_message(UserInputLLMMessage(instruction="Frame 2 msg"))
        call_stack.push(frame2)

        # Before pop: should have 3 messages
        messages_before = call_stack.get_llm_messages()
        assert len(messages_before) == 3

        # Pop frame 2
        call_stack.pop()

        # After pop: should only have frame1's 2 messages
        messages_after = call_stack.get_llm_messages()
        assert len(messages_after) == 2
        assert messages_after[0]["content"] == "Frame 1 msg 1"
        assert messages_after[1]["content"] == "Frame 1 msg 2"

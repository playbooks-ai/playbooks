"""Tests for CallStackFrame message handling."""

from playbooks.core.enums import LLMMessageRole
from playbooks.llm.messages import (
    AssistantResponseLLMMessage,
    PlaybookImplementationLLMMessage,
    UserInputLLMMessage,
)
from playbooks.state.call_stack import CallStackFrame, InstructionPointer


class TestCallStackFrameMessages:
    """Test message handling in CallStackFrame.

    Note: Caching is applied later by InterpreterPrompt, not at frame level.
    """

    def test_empty_frame_returns_empty_list(self):
        """Test that an empty frame returns an empty message list."""
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)

        messages = frame.get_llm_messages()

        assert messages == []

    def test_single_message_returns_dict(self):
        """Test that a single message is returned as a dictionary."""
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)

        msg = UserInputLLMMessage(instruction="Test message")
        frame.add_llm_message(msg)

        messages = frame.get_llm_messages()

        assert len(messages) == 1
        assert messages[0]["content"] == "Test message"
        assert messages[0]["role"] == LLMMessageRole.USER
        # Caching applied later by InterpreterPrompt
        assert "cache_control" not in messages[0]

    def test_multiple_messages_all_returned(self):
        """Test that all messages in a frame are returned."""
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)

        msg1 = PlaybookImplementationLLMMessage("# Playbook", "test")
        msg2 = UserInputLLMMessage(instruction="User input")
        msg3 = AssistantResponseLLMMessage("Assistant response")

        frame.add_llm_message(msg1)
        frame.add_llm_message(msg2)
        frame.add_llm_message(msg3)

        messages = frame.get_llm_messages()

        assert len(messages) == 3
        assert messages[0]["content"] == "# Playbook"
        assert messages[1]["content"] == "User input"
        assert messages[2]["content"] == "Assistant response"

        # No caching at frame level - applied later by InterpreterPrompt
        for msg in messages:
            assert "cache_control" not in msg

    def test_adding_messages_incrementally(self):
        """Test that messages can be added incrementally."""
        ip = InstructionPointer("test_playbook", "01", 1)
        frame = CallStackFrame(ip)

        msg1 = UserInputLLMMessage(instruction="First message")
        frame.add_llm_message(msg1)

        messages1 = frame.get_llm_messages()
        assert len(messages1) == 1

        # Add a second message
        msg2 = UserInputLLMMessage(instruction="Second message")
        frame.add_llm_message(msg2)

        messages2 = frame.get_llm_messages()
        assert len(messages2) == 2
        assert messages2[0]["content"] == "First message"
        assert messages2[1]["content"] == "Second message"

"""Tests for UserInputLLMMessage compaction behavior."""

from playbooks.llm.messages import UserInputLLMMessage


class TestUserInputLLMMessageCompaction:
    """Test suite for UserInputLLMMessage.to_compact_message()."""

    def test_compact_message_with_components(self):
        """Test compaction with component-based construction."""
        about_you = "Remember: You are a helpful AI agent."
        instruction = "Execute step GameRoom:03[meeting 100]"
        python_code_context = """*Python Code Context*
```python
from box import Box
import asyncio

self: AIAgent = ...  # MyAgent (agent 1020)

self.state: Box = Box({
  "name": "Alice",
  "age": 30
})
```"""
        final_instructions = "Carefully analyze session activity log above."

        msg = UserInputLLMMessage(
            about_you=about_you,
            instruction=instruction,
            python_code_context=python_code_context,
            final_instructions=final_instructions,
        )

        # Full message should contain all components
        full = msg.to_full_message()
        assert "Remember: You are a helpful AI agent." in full["content"]
        assert "Execute step GameRoom:03[meeting 100]" in full["content"]
        assert "*Python Code Context*" in full["content"]
        assert "from box import Box" in full["content"]
        assert "Carefully analyze session activity log above." in full["content"]

        # Compacted message should only include instruction
        compacted = msg.to_compact_message()
        assert compacted["content"] == instruction
        assert "Remember: You are a helpful AI agent." not in compacted["content"]
        assert "*Python Code Context*" not in compacted["content"]
        assert "from box import Box" not in compacted["content"]
        assert (
            "Carefully analyze session activity log above." not in compacted["content"]
        )

    def test_component_based_message_without_python_context(self):
        """Test component-based message without Python Context."""
        msg = UserInputLLMMessage(
            about_you="You are an agent",
            instruction="Execute task",
            final_instructions="Please complete the task.",
        )

        # Full message includes all components
        full = msg.to_full_message()
        assert "You are an agent" in full["content"]
        assert "Execute task" in full["content"]
        assert "Please complete the task." in full["content"]

        # Compacted message only includes instruction
        compacted = msg.to_compact_message()
        assert compacted is not None
        assert compacted["role"] == "user"
        assert compacted["content"] == "Execute task"

    def test_component_message_with_only_instruction(self):
        """Test message with only instruction component."""
        msg = UserInputLLMMessage(instruction="Execute step Main:03")

        # Full message only has instruction
        full = msg.to_full_message()
        assert "Execute step Main:03" in full["content"]

        # Compacted message has the same instruction
        compacted = msg.to_compact_message()
        assert compacted is not None
        assert compacted["content"] == "Execute step Main:03"

    def test_all_components_present(self):
        """Test message with all components present."""
        msg = UserInputLLMMessage(
            about_you="Remember: You are Agent X",
            instruction="Execute Main:05",
            python_code_context="*Python Code Context*\n```python\nself.state = {}\n```",
            final_instructions="Follow the contract exactly.",
        )

        # Full message has all components
        full = msg.to_full_message()
        assert "Remember: You are Agent X" in full["content"]
        assert "Execute Main:05" in full["content"]
        assert "*Python Code Context*" in full["content"]
        assert "Follow the contract exactly." in full["content"]

        # Compacted message only has instruction
        compacted = msg.to_compact_message()
        assert compacted["content"] == "Execute Main:05"

    def test_empty_components(self):
        """Test message with empty components."""
        msg = UserInputLLMMessage(
            about_you="",
            instruction="",
            python_code_context="",
            final_instructions="",
        )

        # Full message is empty
        full = msg.to_full_message()
        assert full["content"] == ""

        # Compacted message is also empty
        compacted = msg.to_compact_message()
        assert compacted["content"] == ""

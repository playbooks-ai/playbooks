"""Integration tests for UserInputLLMMessage component-based storage."""

from playbooks.llm.llm_context_compactor import LLMContextCompactor
from playbooks.llm.messages import AssistantResponseLLMMessage, UserInputLLMMessage


class TestUserInputComponentsIntegration:
    """Test integration of component-based UserInputLLMMessage with compaction."""

    def test_end_to_end_component_based_compaction(self):
        """Test full flow: create with components, compact, preserve structure."""
        # Create a UserInputLLMMessage with all components (typical interpreter prompt)
        about_you = "Remember: You are executing as Agent MyAgent (agent 1020)"
        instruction = "GameRoom:03[meeting 100] was executed - continue execution. Refer to GameRoom playbook implementation above."
        python_code_context = """*Python Code Context*
```python
from box import Box
import asyncio

self: AIAgent = ...  # MyAgent (agent 1020)

self.call_stack: list[str] = ["GameRoom"]

self.state: Box = Box({
  "room_name": "Game Room Alpha",
  "players": ["Alice", "Bob"],
  "current_turn": 1
})

agents: AgentsAccessor = ...  # AgentsAccessor object
agents.all: list[str] = ["agent 1020", "agent 1021"]
```"""
        final_instructions = """Carefully analyze session activity log above to understand anything unexpected like infinite loops, errors, inconsistancies, tasks already done or expected, and reflect that in recap and plan accordingly. You must act like an intelligent, conscientious and responsible expert. Keep your thinking concise and don't repeat yourself. Yield for call if you need to do semantic processing/extraction on the result of a playbook call.
**Follow the contract exactly; deviations break execution.**"""

        msg = UserInputLLMMessage(
            about_you=about_you,
            instruction=instruction,
            python_code_context=python_code_context,
            final_instructions=final_instructions,
        )

        # Verify components are stored correctly
        assert msg.about_you == about_you
        assert msg.instruction == instruction
        assert msg.python_code_context == python_code_context
        assert msg.final_instructions == final_instructions

        # Verify full message includes all components
        full = msg.to_full_message()
        assert "Remember: You are executing as Agent MyAgent" in full["content"]
        assert "GameRoom:03[meeting 100]" in full["content"]
        assert "*Python Code Context*" in full["content"]
        assert "self.state: Box" in full["content"]
        assert "Carefully analyze session activity log" in full["content"]

        # Verify compacted message only includes instruction
        compacted = msg.to_compact_message()
        assert compacted["content"] == instruction
        assert (
            "Remember: You are executing as Agent MyAgent" not in compacted["content"]
        )
        assert "*Python Code Context*" not in compacted["content"]
        assert "self.state: Box" not in compacted["content"]
        assert "Carefully analyze session activity log" not in compacted["content"]

    def test_compaction_in_context_compactor(self):
        """Test that LLMContextCompactor correctly uses component-based compaction."""
        # Create a conversation with multiple UserInputLLMMessages
        messages = []

        # Old message (will be compacted)
        messages.append(
            UserInputLLMMessage(
                about_you="Remember: You are Agent A",
                instruction="Execute step 1",
                python_code_context="*Python Code Context*\n```python\nself.state = {}\n```",
                final_instructions="Follow the contract.",
            )
        )
        messages.append(
            AssistantResponseLLMMessage("# execution_id: 1\n# recap: Step 1 done")
        )

        # Recent message (will not be compacted)
        messages.append(
            UserInputLLMMessage(
                about_you="Remember: You are Agent A",
                instruction="Execute step 2",
                python_code_context="*Python Code Context*\n```python\nself.state = {'x': 1}\n```",
                final_instructions="Follow the contract.",
            )
        )
        messages.append(
            AssistantResponseLLMMessage(
                "# execution_id: 2\n# recap: Step 2 done\n# plan: Continue\nsome logs"
            )
        )

        compactor = LLMContextCompactor()
        result = compactor.compact_messages(messages)

        # First user message should be compacted (only instruction)
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Execute step 1"
        assert "Remember: You are Agent A" not in result[0]["content"]
        assert "*Python Code Context*" not in result[0]["content"]
        assert "self.state" not in result[0]["content"]
        assert "Follow the contract." not in result[0]["content"]

        # First assistant message should be compacted (first 2 lines only)
        assert result[1]["role"] == "assistant"
        assert "# execution_id: 1" in result[1]["content"]
        assert "# recap: Step 1 done" in result[1]["content"]

        # Recent user message should be full (includes Python Context)
        assert result[2]["role"] == "user"
        assert "Remember: You are Agent A" in result[2]["content"]
        assert "Execute step 2" in result[2]["content"]
        assert "*Python Code Context*" in result[2]["content"]
        assert "self.state = {'x': 1}" in result[2]["content"]

        # Recent assistant message should be full
        assert result[3]["role"] == "assistant"
        assert "some logs" in result[3]["content"]

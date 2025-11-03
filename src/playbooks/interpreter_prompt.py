"""LLM interpreter prompt construction.

This module handles the construction of prompts sent to LLMs for playbook
interpretation, including context management, agent information, and
execution state formatting.
"""

import json
import os
import types
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.debug_logger import debug
from playbooks.llm_context_compactor import LLMContextCompactor
from playbooks.llm_messages import (
    AgentInfoLLMMessage,
    OtherAgentInfoLLMMessage,
    TriggerInstructionsLLMMessage,
    UserInputLLMMessage,
)
from playbooks.playbook import Playbook
from playbooks.utils.llm_helper import get_messages_for_prompt
from playbooks.utils.token_counter import get_messages_token_count
from playbooks.variables import Variable

if TYPE_CHECKING:
    from playbooks.execution_state import ExecutionState


class SetEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling sets and other non-serializable types."""

    def default(self, obj: Any) -> Any:
        """Encode non-serializable objects.

        Args:
            obj: Object to encode

        Returns:
            JSON-serializable representation of the object
        """
        if isinstance(obj, set):
            return list(obj)
        if obj is Ellipsis:
            return "..."
        if isinstance(obj, Variable):
            return json.JSONEncoder.default(self, obj.value)
        # Handle module objects and other non-serializable types
        if isinstance(obj, types.ModuleType):
            return f"<module: {obj.__name__}>"
        if isinstance(obj, type):
            return f"<class: {obj.__name__}>"
        # For any other non-serializable object, convert to string
        try:
            return super().default(obj)
        except TypeError:
            return f"<{type(obj).__name__}: {str(obj)[:50]}>"


class InterpreterPrompt:
    """Generates the prompt for the interpreter LLM based on the current state."""

    def __init__(
        self,
        execution_state: "ExecutionState",
        playbooks: Dict[str, Playbook],
        current_playbook: Optional[Playbook],
        instruction: str,
        agent_instructions: str,
        artifacts_to_load: List[str],
        trigger_instructions: List[str],
        agent_information: str,
        other_agent_klasses_information: List[str],
        execution_id: Optional[int] = None,
    ) -> None:
        """Initialize the InterpreterPrompt.

        Args:
            execution_state: The current execution state
            playbooks: Dictionary of available playbooks
            current_playbook: The currently executing playbook, if any
            instruction: The user's latest instruction
            agent_instructions: General instructions for the agent
            artifacts_to_load: List of artifact names to load
            trigger_instructions: List of trigger instruction strings
            agent_information: Information about the current agent
            other_agent_klasses_information: List of information strings about other agents
            execution_id: Sequential execution counter for this LLM call
        """
        self.execution_state = execution_state
        self.playbooks = playbooks
        self.current_playbook = current_playbook
        self.instruction = instruction
        self.agent_instructions = agent_instructions
        self.artifacts_to_load = artifacts_to_load
        self.trigger_instructions = trigger_instructions
        self.agent_information = agent_information
        self.other_agent_klasses_information = other_agent_klasses_information
        self.execution_id = execution_id  # NEW: Store execution_id
        self.compactor = LLMContextCompactor()

    def _get_trigger_instructions_message(self) -> str:
        if len(self.trigger_instructions) > 0:
            trigger_instructions = (
                ["*Available playbook triggers*", "```md"]
                + self.trigger_instructions
                + ["```"]
            )

            return TriggerInstructionsLLMMessage(
                "\n".join(trigger_instructions)
            ).to_full_message()
        return None

    def _get_other_agent_klasses_information_message(self) -> str:
        if len(self.other_agent_klasses_information) > 0:
            other_agent_klasses_information = [
                "*Other agents*",
                "```md",
                "\n\n".join(self.other_agent_klasses_information),
                "```",
            ]
            return OtherAgentInfoLLMMessage(
                "\n".join(other_agent_klasses_information)
            ).to_full_message()
        return None

    def _get_compact_agent_information_message(self) -> str:
        parts = []
        parts.append("*My agent*")
        parts.append("```md")
        parts.append(self.agent_information)
        parts.append("```")
        return AgentInfoLLMMessage("\n".join(parts)).to_full_message()

    @property
    def prompt(self) -> str:
        """Constructs the full prompt string for the LLM.

        Returns:
            The formatted prompt string.
        """
        # trigger_instructions_str = self._get_trigger_instructions_str()

        # current_playbook_markdown = (
        #     self.playbooks[self.current_playbook.klass].markdown
        #     if self.current_playbook
        #     else "No playbook is currently running."
        # )

        try:
            with open(
                os.path.join(
                    os.path.dirname(__file__), "./prompts/interpreter_run.txt"
                ),
                "r",
            ) as f:
                prompt = f.read()
        except FileNotFoundError:
            debug("Error: Prompt template file not found")
            return "Error: Prompt template missing."

        initial_state = json.dumps(
            self.execution_state.to_dict(), indent=2, cls=SetEncoder
        )

        # session_log_str = str(self.execution_state.session_log)

        # prompt = prompt_template.replace("{{TRIGGERS}}", trigger_instructions_str)
        # prompt = prompt.replace(
        #     "{{CURRENT_PLAYBOOK_MARKDOWN}}", current_playbook_markdown
        # )
        # prompt = prompt.replace("{{SESSION_LOG}}", session_log_str)
        prompt = prompt.replace("{{INITIAL_STATE}}", initial_state)
        prompt = prompt.replace("{{INSTRUCTION}}", self.instruction)
        if self.agent_instructions:
            prompt = prompt.replace("{{AGENT_INSTRUCTIONS}}", self.agent_instructions)
        else:
            prompt = prompt.replace("{{AGENT_INSTRUCTIONS}}", "")
        return prompt

    @property
    def messages(self) -> List[Dict[str, str]]:
        """Formats the prompt into the message structure expected by the LLM helper."""
        prompt_messages = get_messages_for_prompt(self.prompt)

        messages = []
        messages.append(prompt_messages[0])

        other_agent_klasses_information_message = (
            self._get_other_agent_klasses_information_message()
        )
        if other_agent_klasses_information_message:
            messages.append(other_agent_klasses_information_message)

        messages.append(self._get_compact_agent_information_message())

        trigger_instructions_message = self._get_trigger_instructions_message()
        if trigger_instructions_message:
            messages.append(trigger_instructions_message)

        # Convert the prompt message dict back to a proper message object
        if len(prompt_messages) > 1:
            user_instruction_msg = UserInputLLMMessage(prompt_messages[1]["content"])
            self.execution_state.call_stack.add_llm_message(user_instruction_msg)

        # Original call stack messages (as LLMMessage objects)
        call_stack_llm_messages = []
        for frame in self.execution_state.call_stack.frames:
            call_stack_llm_messages.extend(frame.llm_messages)

        # Apply compaction - returns Dict[str, str] format ready for LLM API
        compacted_dict_messages = self.compactor.compact_messages(
            call_stack_llm_messages
        )

        # Log compaction stats using token counts
        original_dict_messages = [
            msg.to_full_message() for msg in call_stack_llm_messages
        ]
        original_tokens = get_messages_token_count(messages + original_dict_messages)
        compacted_tokens = get_messages_token_count(messages + compacted_dict_messages)
        compression_ratio = (
            compacted_tokens / original_tokens if original_tokens > 0 else 1.0
        )

        debug(
            f"LLM Context Compaction: {original_tokens} -> {compacted_tokens} tokens ({compression_ratio:.2%})"
        )

        messages.extend(compacted_dict_messages)

        return messages

"""LLM interpreter prompt construction.

This module handles the construction of prompts sent to LLMs for playbook
interpretation, including context management, agent information, and
execution state formatting.
"""

import json
import os
import types
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.config import config
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.llm.llm_context_compactor import LLMContextCompactor
from playbooks.llm.messages import (
    AgentInfoLLMMessage,
    OtherAgentInfoLLMMessage,
    TriggerInstructionsLLMMessage,
    UserInputLLMMessage,
)
from playbooks.llm.messages.types import FrameType
from playbooks.playbook import Playbook
from playbooks.utils.llm_helper import get_messages_for_prompt
from playbooks.utils.token_counter import get_messages_token_count

if TYPE_CHECKING:
    from playbooks.state.execution_state import ExecutionState


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
        self.frame_type = None  # Will be set when generating prompt

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

    def _add_artifact_hints(self, state_json: str, state_dict: Dict[str, Any]) -> str:
        """Add artifact load status hints to state JSON.

        Args:
            state_json: JSON string representation of state
            state_dict: State dictionary

        Returns:
            JSON string with artifact hints added
        """
        variables = state_dict.get("variables", {})
        if not variables:
            return state_json

        lines = state_json.split("\n")
        for i, line in enumerate(lines):
            for var_name, var_value in variables.items():
                if isinstance(var_value, str) and var_value.startswith("Artifact:"):
                    if f'"{var_name}":' in line:
                        is_loaded = self.execution_state.call_stack.is_artifact_loaded(
                            var_name
                        )
                        if is_loaded:
                            lines[i] = (
                                line.rstrip(",")
                                + "  // content loaded above"
                                + ("," if line.rstrip().endswith(",") else "")
                            )
                        else:
                            lines[i] = (
                                line.rstrip(",")
                                + f"  // not loaded: use LoadArtifact('{var_name}') to load"
                                + ("," if line.rstrip().endswith(",") else "")
                            )

        return "\n".join(lines)

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
                    os.path.dirname(os.path.dirname(__file__)),
                    "./prompts/interpreter_run.txt",
                ),
                "r",
            ) as f:
                prompt = f.read()
        except FileNotFoundError:
            debug("Error: Prompt template file not found")
            return "Error: Prompt template missing."

        # Get state with compression applied
        state_dict, self.frame_type = self.execution_state.get_state_for_llm(
            self.execution_id, config.state_compression
        )

        # Generate state block in code (not template)
        if state_dict is not None:
            title = (
                "Current state" if self.frame_type == FrameType.I else "State changes"
            )
            state_json = json.dumps(state_dict, indent=2, cls=SetEncoder)

            # Add artifact load status hints
            state_json = self._add_artifact_hints(state_json, state_dict)

            state_block = f"""*{title}*
```json
{state_json}
```

"""
        else:
            # Empty delta - no state block
            state_block = ""

        prompt = prompt.replace("{{INITIAL_STATE}}", state_block)

        # session_log_str = str(self.execution_state.session_log)

        # prompt = prompt_template.replace("{{TRIGGERS}}", trigger_instructions_str)
        # prompt = prompt.replace(
        #     "{{CURRENT_PLAYBOOK_MARKDOWN}}", current_playbook_markdown
        # )
        # prompt = prompt.replace("{{SESSION_LOG}}", session_log_str)
        prompt = prompt.replace("{{INSTRUCTION}}", self.instruction)

        # Only include agent instructions for I-frames (full state)
        # P-frames skip this since it was already in the last I-frame
        if self.agent_instructions and self.frame_type == FrameType.I:
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
            # Use frame_type from prompt generation (set in self.prompt property)

            frame_type = self.frame_type if self.frame_type is not None else FrameType.I
            user_instruction_msg = UserInputLLMMessage(
                prompt_messages[1]["content"], frame_type=frame_type
            )
            self.execution_state.call_stack.add_llm_message(user_instruction_msg)

        # Collect all LLM messages: from call stack frames + top-level messages
        call_stack_llm_messages = []

        # Add messages from call stack frames
        for frame in self.execution_state.call_stack.frames:
            call_stack_llm_messages.extend(frame.llm_messages)
            for index, message in enumerate(frame.llm_messages):
                message.cached = index == len(frame.llm_messages) - 1

        # Add top-level messages (when call stack is empty or before first playbook)
        top_level_messages = self.execution_state.call_stack.top_level_llm_messages
        if top_level_messages:
            call_stack_llm_messages.extend(top_level_messages)
            # Mark the last message as cached if no call stack frames
            if not self.execution_state.call_stack.frames and top_level_messages:
                top_level_messages[-1].cached = True

        # Apply compaction - the cached flags will be preserved through to_full_message()
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

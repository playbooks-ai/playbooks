import json
import os
from typing import TYPE_CHECKING, Dict, List, Optional

from playbooks.debug_logger import debug
from playbooks.llm_context_compactor import LLMContextCompactor
from playbooks.llm_messages import (
    AgentInfoLLMMessage,
    AssistantResponseLLMMessage,
    OtherAgentInfoLLMMessage,
    TriggerInstructionsLLMMessage,
    UserInputLLMMessage,
)
from playbooks.playbook import Playbook
from playbooks.utils.llm_helper import get_messages_for_prompt

if TYPE_CHECKING:
    from playbooks.execution_state import ExecutionState


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
    ):
        """
        Initializes the InterpreterPrompt.

        Args:
            execution_state: The current execution state.
            playbooks: A dictionary of available playbooks.
            current_playbook: The currently executing playbook, if any.
            instruction: The user's latest instruction.
            agent_instructions: General instructions for the agent.
            artifacts_to_load: List of artifact names to load.
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

        initial_state = json.dumps(self.execution_state.to_dict(), indent=2)

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

        # Log compaction stats
        original_dict_messages = [
            msg.to_full_message() for msg in call_stack_llm_messages
        ]
        original_size = len(str(original_dict_messages))
        compacted_size = len(str(compacted_dict_messages))
        compression_ratio = compacted_size / original_size if original_size > 0 else 1.0

        debug(
            f"LLM Context Compaction: {original_size} -> {compacted_size} chars ({compression_ratio:.2%})"
        )

        messages.extend(compacted_dict_messages)
        # messages.extend(self._get_artifact_messages())
        # messages.append(prompt_messages[1])

        return messages

    def _get_artifact_messages(self) -> List[Dict[str, str]]:
        """Generates messages for the artifacts to load."""
        artifact_messages = []
        for artifact in self.artifacts_to_load:
            artifact = self.execution_state.artifacts[artifact]
            artifact_message = f"Artifact[{artifact.name}]\n\nSummary: {artifact.summary}\n\nContent: {artifact.content}"
            artifact_messages.append(
                AssistantResponseLLMMessage(artifact_message).to_full_message()
            )
        return artifact_messages

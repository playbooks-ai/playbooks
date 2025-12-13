"""LLM interpreter prompt construction.

This module handles the construction of prompts sent to LLMs for playbook
interpretation, including context management, agent information, and
execution state formatting.
"""

import json
import os
import types
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.llm.llm_context_compactor import LLMContextCompactor
from playbooks.llm.messages import (
    AgentInfoLLMMessage,
    OtherAgentInfoLLMMessage,
    TriggerInstructionsLLMMessage,
    UserInputLLMMessage,
)
from playbooks.playbook import Playbook
from playbooks.utils.llm_helper import get_messages_for_prompt
from playbooks.utils.token_counter import get_messages_token_count

if TYPE_CHECKING:
    from playbooks.agents import AIAgent


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
        agent: "AIAgent",
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
            agent: The AIAgent instance for accessing state and execution context
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
        self.agent = agent
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
                        is_loaded = self.agent.call_stack.is_artifact_loaded(var_name)
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

    def _build_context_prefix(self) -> str:
        """Build Python code prefix showing all available context.

        Returns a Python code block with:
        - Imports from namespace
        - Local variables (including playbook args)
        - self reference
        - self.state dict
        """
        lines = ["```python"]

        # Imports
        imports = self._extract_imports()
        if imports:
            lines.extend(imports)
            lines.append("")  # blank line after imports

        # Call stack, list of agents, meetings
        agent_dict = self.agent.to_dict()
        call_stack = agent_dict.get("call_stack", [])
        agents = agent_dict.get("agents", [])
        owned_meetings = agent_dict.get("owned_meetings", [])
        joined_meetings = agent_dict.get("joined_meetings", [])
        lines.append(f"call_stack = {call_stack} # managed by the runtime")
        lines.append(
            f"owned_meetings = {owned_meetings if owned_meetings else []} # managed by the runtime"
        )
        lines.append(
            f"joined_meetings = {joined_meetings if joined_meetings else []} # managed by the runtime"
        )

        lines.append(
            "all_agents.by_klass(agent_klass) = ... # method to access agents by type"
        )
        lines.append("all_agents.by_id(agent_id) = ... # method to access agents by id")
        lines.append(f"all_agents.all = {agents}")

        # Local variables (including playbook args from frame.locals)
        current_frame = self.agent.call_stack.peek()
        if current_frame and current_frame.locals:
            for name, value in sorted(current_frame.locals.items()):
                lines.append(self._format_variable(name, value))
            if current_frame.locals:
                lines.append("")  # blank line after locals

        # self reference (formatted like agents in state)
        lines.append(f"self = ...  # {self.agent.klass} ({self.agent.id})")

        # self.state
        for name, value in sorted(self.agent.state.items()):
            if name not in ["_busy"]:
                lines.append("self.state." + self._format_variable(name, value))

        lines.append("")
        lines.append("```")
        return "\n".join(lines) + "\n\n"

    def _format_variable(self, name: str, value: Any) -> str:
        """Format a single variable assignment."""
        if self._is_literal(value):
            # Use repr() for actual Python literal
            return f"{name} = {repr(value)}"
        else:
            # Use ... with type comment
            type_hint = self._get_type_hint(value)
            return f"{name} = ...  # {type_hint}"

    def _is_literal(self, value: Any) -> bool:
        """Check if value should be shown as literal."""
        if isinstance(value, (int, float, bool, type(None))):
            return True
        if isinstance(value, str):
            return len(value) < 200  # Show strings up to 200 chars
        if isinstance(value, (list, dict, tuple)):
            repr_str = repr(value)
            return len(repr_str) < 100  # Show collections if repr < 100 chars
        return False

    def _get_type_hint(self, value: Any) -> str:
        """Get human-readable type hint for non-literal values."""
        if hasattr(value, "id") and hasattr(value, "klass"):
            # Looks like an agent instance
            return f"{value.klass} instance"
        if hasattr(value, "__class__"):
            return type(value).__name__
        return "Any"

    def _format_state_dict(self, state_dict: Dict[str, Any]) -> str:
        """Format state dict as Python dict literal.

        Handles special cases:
        - Artifacts: Keep "Artifact: summary" notation
        - Literals: Use repr()
        - Non-literals: Use <TypeName> placeholder
        """
        formatted = {}
        for key, value in state_dict.items():
            if key.startswith("_"):
                # Skip internal keys like __
                continue
            if isinstance(value, str) and value.startswith("Artifact: "):
                # Keep artifact notation
                formatted[key] = value
            elif self._is_literal(value):
                formatted[key] = value
            else:
                # Non-literal, use type placeholder
                formatted[key] = f"<{type(value).__name__}>"

        # Use json.dumps for cleaner formatting with proper escaping
        import json

        try:
            return json.dumps(formatted, indent=None, ensure_ascii=False)
        except (TypeError, ValueError):
            # Fallback to repr if json fails
            return repr(formatted)

    def _extract_imports(self) -> List[str]:
        """Extract import statements from agent namespace."""
        imports = []
        if hasattr(self.agent, "namespace_manager") and hasattr(
            self.agent.namespace_manager, "namespace"
        ):
            for name, value in self.agent.namespace_manager.namespace.items():
                if isinstance(value, types.ModuleType) and not name.startswith("_"):
                    # Get the actual module name
                    module_name = getattr(value, "__name__", name)
                    if module_name != name:
                        # Was imported with alias
                        imports.append(f"import {module_name} as {name}")
                    else:
                        imports.append(f"import {name}")
        return sorted(imports)

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

        # Generate context prefix (imports, locals, self.state)
        context_prefix = self._build_context_prefix()
        prompt = prompt.replace("{{CONTEXT_PREFIX}}", context_prefix)

        # session_log_str = str(self.agent.session_log)

        # prompt = prompt_template.replace("{{TRIGGERS}}", trigger_instructions_str)
        # prompt = prompt.replace(
        #     "{{CURRENT_PLAYBOOK_MARKDOWN}}", current_playbook_markdown
        # )
        # prompt = prompt.replace("{{SESSION_LOG}}", session_log_str)
        prompt = prompt.replace("{{INSTRUCTION}}", self.instruction)

        # Include agent instructions
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
            self.agent.call_stack.add_llm_message(user_instruction_msg)

        # Collect all LLM messages: from call stack frames + top-level messages
        call_stack_llm_messages = []

        # Add messages from call stack frames
        for frame in self.agent.call_stack.frames:
            call_stack_llm_messages.extend(frame.llm_messages)
            for index, message in enumerate(frame.llm_messages):
                message.cached = index == len(frame.llm_messages) - 1

        # Add top-level messages (when call stack is empty or before first playbook)
        top_level_messages = self.agent.call_stack.top_level_llm_messages
        if top_level_messages:
            call_stack_llm_messages.extend(top_level_messages)
            # Mark the last message as cached if no call stack frames
            if not self.agent.call_stack.frames and top_level_messages:
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
            f"LLM Context Compaction: {original_tokens} -> {compacted_tokens} tokens ({compression_ratio:.2%})",
            agent=self.agent,
        )

        messages.extend(compacted_dict_messages)

        return messages

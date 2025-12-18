"""LLM interpreter prompt construction.

This module handles the construction of prompts sent to LLMs for playbook
interpretation, including context management, agent information, and
execution state formatting.
"""

import json
import types
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.llm.llm_context_compactor import LLMContextCompactor
from playbooks.llm.messages import (
    AgentInfoLLMMessage,
    OtherAgentInfoLLMMessage,
    UserInputLLMMessage,
)
from playbooks.playbook import Playbook

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
            agent_information: Information about the current agent
            other_agent_klasses_information: List of information strings about other agents
            execution_id: Sequential execution counter for this LLM call
        """
        self.agent = agent
        self.call_stack = agent.call_stack  # Access to call stack for LLM messages
        self.playbooks = playbooks
        self.current_playbook = current_playbook
        self.instruction = instruction
        self.agent_instructions = agent_instructions
        self.artifacts_to_load = artifacts_to_load
        self.agent_information = agent_information
        self.other_agent_klasses_information = other_agent_klasses_information
        self.execution_id = execution_id  # NEW: Store execution_id
        self.compactor = LLMContextCompactor()
        self._user_message: Optional[UserInputLLMMessage] = None

    def create_user_message(self) -> None:
        """Create and store the user input message for this LLM call."""
        context_prefix = self._build_context_prefix()
        python_code_context = f"*Python Code Context*\n{context_prefix}"
        final_instructions = self._get_final_instructions()

        self._user_message = UserInputLLMMessage(
            about_you=self.agent_instructions,
            instruction=self.instruction,
            python_code_context=python_code_context,
            final_instructions=final_instructions,
        )

        # Add to call stack for persistence
        self.agent.call_stack.add_llm_message(self._user_message)

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

    def _get_final_instructions(self) -> str:
        """Get the final instructions for user input messages."""
        return """Carefully analyze session activity log above to understand anything unexpected like infinite loops, errors, inconsistancies, tasks already done or expected, and reflect that in recap and plan accordingly. You must act like an intelligent, conscientious and responsible expert. Keep your thinking concise and don't repeat yourself. Precisely follow python code context, available variables and available playbooks. **Follow the contract exactly; deviations break execution.**"""

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
        - agent object with all its attributes
        - agents list
        - Local variables (including playbook args)
        """
        lines = ["```python"]

        # Imports
        imports = self._extract_imports()
        if imports:
            lines.extend(imports)
            lines.append("")  # blank line after imports

        # Get agent data
        agent_dict = self.agent.to_dict()
        call_stack = agent_dict.get("call_stack", [])
        agents = agent_dict.get("agents", [])

        # Agent (self) reference
        lines.append(
            f"self: AIAgent = ...  # {self.agent.klass} (agent {self.agent.id})"
        )
        lines.append("")

        # self.call_stack with type info
        lines.append(
            f"self.call_stack: list[str] = {call_stack}  # managed by the runtime"
        )
        lines.append("")

        # self.active_meetings - all meetings (owned + joined)
        lines.append("self.active_meetings: list[Meeting] = [")
        for meeting in self.agent.active_meetings:
            lines.append(f"    {repr(meeting)},")
        lines.append("]")
        lines.append("")

        # self.current_meeting - check if currently in a meeting
        active_meeting_id = (
            self.agent.meeting_manager.get_current_meeting_from_call_stack()
        )

        if active_meeting_id:
            # Find the active meeting in owned or joined meetings
            meeting_obj = None
            if active_meeting_id in self.agent.owned_meetings:
                meeting_obj = self.agent.owned_meetings[active_meeting_id]
            elif active_meeting_id in self.agent.joined_meetings:
                meeting_obj = self.agent.joined_meetings[active_meeting_id]

            if meeting_obj:
                # Show current meeting using repr
                lines.append(
                    f"self.current_meeting: Meeting = {repr(meeting_obj)} # read-only, managed by the runtime"
                )
                lines.append("")

                # Show shared_state as Box with full content
                shared_state_dict = dict(meeting_obj.shared_state.items())
                shared_state_json = json.dumps(
                    shared_state_dict, indent=2, cls=SetEncoder, ensure_ascii=False
                )
                lines.append(
                    f"self.current_meeting.shared_state: Box = Box({shared_state_json})"
                )
                lines.append("")
        else:
            lines.append("self.current_meeting: Meeting | None = None")
            lines.append("")

        # self.state as Box
        state_dict = {}
        for name, value in self.agent.state.items():
            if name not in ["_busy"]:
                state_dict[name] = value

        state_json = json.dumps(
            state_dict, indent=2, cls=SetEncoder, ensure_ascii=False
        )
        lines.append(f"self.state: Box = Box({state_json})")
        lines.append("")

        # All agents accessor
        lines.append("agents: AgentsAccessor = ...  # AgentsAccessor object")

        # Show agents.all as the list of all agents
        lines.append(f"agents.all: list[str] = {agents}")

        # Show methods available on agents
        lines.append(
            "agents.by_klass: dict[str, list[Agent]] = ...  # agents grouped by class"
        )
        lines.append("agents.by_id: dict[str, Agent] = ...  # agents indexed by ID")
        lines.append("")

        # Local variables (including playbook args from frame.locals)
        current_frame = self.agent.call_stack.peek()
        if current_frame and current_frame.locals:
            lines.append("# Local variables")
            for name, value in sorted(current_frame.locals.items()):
                lines.append(self._format_variable(name, value, include_type=True))
            lines.append("")  # blank line after locals

        lines.append("```")
        return "\n".join(lines) + "\n\n"

    def _format_variable(
        self, name: str, value: Any, include_type: bool = False
    ) -> str:
        """Format a single variable assignment with optional type hint.

        Args:
            name: Variable name
            value: Variable value
            include_type: Whether to include type annotation

        Returns:
            Formatted variable assignment string
        """
        type_annotation = ""
        if include_type:
            type_hint = self._get_type_hint(value)
            type_annotation = f": {type_hint}"

        # Get the value representation with smart compacting
        value_repr = self._smart_repr(value, max_length=400)

        return f"{name}{type_annotation} = {value_repr}"

    def _smart_repr(self, value: Any, max_length: int = 400) -> str:
        """Create a smart representation of a value with intelligent compacting.

        For long values (>max_length), compacts similar to numpy's tensor representation.

        Args:
            value: The value to represent
            max_length: Maximum length before compacting

        Returns:
            String representation of the value
        """
        # For simple literals, use repr
        if isinstance(value, (int, float, bool, type(None))):
            return repr(value)

        if isinstance(value, str):
            r = repr(value)
            if len(r) <= max_length:
                return r
            # Compact long strings
            preview_len = max_length // 2 - 20
            return f"{r[:preview_len]}...{r[-preview_len:]} (length: {len(value)})"

        if isinstance(value, (list, tuple)):
            full_repr = repr(value)
            if len(full_repr) <= max_length:
                return full_repr

            # Compact long lists/tuples - show shape and sample
            type_name = "tuple" if isinstance(value, tuple) else "list"
            length = len(value)
            if length == 0:
                return "[]" if type_name == "list" else "()"

            # Show first and last few items
            sample_size = 2
            if length <= sample_size * 2:
                return full_repr

            first_items = repr(value[:sample_size])[1:-1]  # Remove brackets
            last_items = repr(value[-sample_size:])[1:-1]
            return f"[{first_items}, ..., {last_items}] (length: {length})"

        if isinstance(value, dict):
            full_repr = repr(value)
            if len(full_repr) <= max_length:
                return full_repr

            # Compact long dicts - show count and sample keys
            length = len(value)
            if length == 0:
                return "{}"

            sample_size = 2
            items = list(value.items())
            if length <= sample_size * 2:
                return full_repr

            sample_items = dict(items[:sample_size])
            return f"{{{repr(sample_items)[1:-1]}, ...}} ({length} keys)"

        # For non-literals, use type placeholder
        return f"...  # {self._get_type_hint(value)}"

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
        """Get human-readable type hint for values."""
        if hasattr(value, "id") and hasattr(value, "klass"):
            # Looks like an agent instance
            return f"{value.klass}"

        if isinstance(value, list):
            if not value:
                return "list"
            # Try to infer element type
            first_type = type(value[0]).__name__
            if all(type(v).__name__ == first_type for v in value[:10]):
                return f"list[{first_type}]"
            return "list"

        if isinstance(value, dict):
            if not value:
                return "dict"
            # Try to infer key/value types from first item
            first_key, first_val = next(iter(value.items()))
            key_type = type(first_key).__name__
            val_type = type(first_val).__name__
            return f"dict[{key_type}, {val_type}]"

        if isinstance(value, tuple):
            return "tuple"

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

        # Always include Box as it's used for meeting shared state
        imports.append("from box import Box")

        # Always include asyncio as it's available in the execution namespace
        imports.append("import asyncio")

        if hasattr(self.agent, "namespace_manager") and hasattr(
            self.agent.namespace_manager, "namespace"
        ):
            for name, value in self.agent.namespace_manager.namespace.items():
                if isinstance(value, types.ModuleType) and not name.startswith("_"):
                    # Skip asyncio since we already added it
                    if name == "asyncio":
                        continue
                    # Get the actual module name
                    module_name = getattr(value, "__name__", name)
                    if module_name != name:
                        # Was imported with alias
                        imports.append(f"import {module_name} as {name}")
                    else:
                        imports.append(f"import {name}")
        return sorted(imports)

    @property
    def messages(self) -> List[Dict[str, str]]:
        """Return all messages including user input and call stack messages."""
        # Get raw LLMMessage objects from call stack for proper compaction
        llm_message_objects = self.call_stack.get_llm_message_objects()

        # Apply compaction
        compacted_messages = self.compactor.compact_messages(llm_message_objects)

        return compacted_messages

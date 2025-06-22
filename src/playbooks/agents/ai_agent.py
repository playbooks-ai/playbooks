import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List

from ..call_stack import CallStackFrame, InstructionPointer
from ..enums import LLMMessageRole
from ..event_bus import EventBus
from ..execution_state import ExecutionState
from ..playbook import MarkdownPlaybook, Playbook, PythonPlaybook, RemotePlaybook
from ..playbook_call import PlaybookCall, PlaybookCallResult
from ..utils.langfuse_helper import LangfuseHelper
from ..utils.parse_utils import parse_metadata_and_description
from .base_agent import BaseAgent

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AIAgent(BaseAgent, ABC):
    """
    Abstract base class for AI agents.

    An Agent represents an AI entity capable of processing messages through playbooks
    using a main execution thread. This class defines the interface that all AI agent
    implementations must adhere to.

    Attributes:
        klass: The class/type of this agent.
        description: Human-readable description of the agent.
        playbooks: Dictionary of playbooks available to this agent.
        other_agents: Dictionary of other agents for direct communication.
    """

    def __init__(
        self,
        klass: str,
        description: str,
        event_bus: EventBus,
        playbooks: Dict[str, Playbook] = None,
        source_line_number: int = None,
        agent_id: str = None,
    ):
        """Initialize a new AIAgent.

        Args:
            klass: The class/type of this agent.
            description: Human-readable description of the agent.
            event_bus: The event bus for publishing events.
            playbooks: Dictionary of playbooks available to this agent.
            source_line_number: The line number in the source markdown where this
                agent is defined.
            agent_id: Optional agent ID. If not provided, will generate UUID.
        """
        super().__init__(klass, agent_id)
        self.metadata, self.description = parse_metadata_and_description(description)
        self.playbooks: Dict[str, Playbook] = playbooks or {}
        self.state = ExecutionState(event_bus)
        self.source_line_number = source_line_number
        self.public_json = None
        self.other_agents: Dict[str, "AIAgent"] = {}

    @abstractmethod
    async def discover_playbooks(self) -> None:
        """Discover and load playbooks for this agent.

        This method should populate the self.playbooks dictionary with
        available playbooks for this agent.
        """
        pass

    def register_agent(self, agent_name: str, agent: "AIAgent") -> None:
        """Register another agent for direct communication.

        Args:
            agent_name: Name/identifier of the agent
            agent: The agent instance to register
        """
        self.other_agents[agent_name] = agent

    def get_available_playbooks(self) -> List[str]:
        """Get a list of available playbook names.

        Returns:
            List of playbook names available to this agent
        """
        return list(self.playbooks.keys())

    async def begin(self):
        """Execute playbooks with BGN trigger."""
        # Find playbooks with a BGN trigger and execute them
        playbooks_to_execute = []
        for playbook in self.playbooks.values():
            if hasattr(playbook, "triggers") and playbook.triggers:
                for trigger in playbook.triggers.triggers:
                    if trigger.is_begin:
                        playbooks_to_execute.append(playbook)

        # TODO: execute the playbooks in parallel
        for playbook in playbooks_to_execute:
            await self.execute_playbook(playbook.name)

    def parse_instruction_pointer(self, step: str) -> InstructionPointer:
        """Parse a step string into an InstructionPointer.

        Args:
            step: Step string to parse

        Returns:
            InstructionPointer: Parsed instruction pointer
        """
        # Extract the step number from the step string
        step_number = step.split(".")[0]
        return InstructionPointer(self.klass, step_number, 0)

    def trigger_instructions(
        self,
        with_namespace: bool = False,
        public_only: bool = False,
        skip_bgn: bool = True,
    ) -> List[str]:
        """Get trigger instructions for this agent's playbooks.

        Args:
            with_namespace: Whether to include namespace in instructions
            public_only: Whether to only include public playbooks
            skip_bgn: Whether to skip BGN trigger instructions

        Returns:
            List of trigger instruction strings
        """
        instructions = []
        for playbook in self.playbooks.values():
            if public_only and not playbook.public:
                continue

            namespace = self.klass if with_namespace else None
            playbook_instructions = playbook.trigger_instructions(namespace, skip_bgn)
            instructions.extend(playbook_instructions)
        return instructions

    @property
    def other_agents_list(self) -> List["AIAgent"]:
        """Get list of other registered agents.

        Returns:
            List of other agent instances
        """
        return list(self.other_agents.values())

    def all_trigger_instructions(self) -> List[str]:
        """Get all trigger instructions including from other agents.

        Returns:
            List of all trigger instruction strings
        """
        instructions = self.trigger_instructions(with_namespace=False)
        for agent in self.other_agents.values():
            instructions.extend(agent.trigger_instructions(with_namespace=True))
        return instructions

    def get_public_information(self) -> str:
        """Get public information about this agent.

        Returns:
            String containing public agent information
        """
        info_parts = []
        info_parts.append(f"Agent: {self.klass} (agent_id: {self.id})")
        if self.description:
            info_parts.append(f"Description: {self.description}")

        public_playbooks = self.public_playbooks
        if public_playbooks:
            info_parts.append("Public Playbooks:")
            for playbook in public_playbooks:
                info_parts.append(
                    f"  - {self.klass}.{playbook.name}: {playbook.description}"
                )

        return "\n".join(info_parts)

    def other_agents_information(self) -> List[str]:
        """Get information about other registered agents.

        Returns:
            List of information strings for other agents
        """
        return [agent.get_public_information() for agent in self.other_agents.values()]

    def resolve_target(self, target: str = None, allow_fallback: bool = True) -> str:
        """Resolve a target specification to an agent ID.

        Args:
            target: Target specification (agent ID, agent type, "human", etc.)
            allow_fallback: Whether to use fallback logic when target is None

        Returns:
            Resolved target agent ID, or None if no fallback allowed and target not found
        """
        if target is not None:
            target = target.strip()

            # Handle human aliases
            if target.lower() in ["human", "user"]:
                return "human"

            # Handle meeting targets (Phase 5)
            if target.startswith("meeting "):
                return target  # Return as-is for now

            # Handle agent ID targets
            if target.startswith("agent "):
                agent_id = target[6:].strip()  # Remove "agent " prefix
                return agent_id

            # Check if target is a numeric agent ID
            if target.isdigit():
                return target

            # Handle special YLD targets
            if target == "last_non_human_agent":
                if (
                    self.state.last_message_target
                    and self.state.last_message_target != "human"
                ):
                    return self.state.last_message_target
                return None  # No fallback for this case

            # Handle agent type - find first agent of this type
            for agent in self.other_agents.values():
                if agent.klass == target:
                    return agent.id

            # If not found, check if Human agent exists with this type name
            if target == "Human":
                return "human"

            # Target not found - fallback to human if allowed
            return "human" if allow_fallback else None

        # No target specified - use fallback logic if allowed
        if not allow_fallback:
            return None

        # Fallback logic: current context → last 1:1 target → Human
        # TODO: Phase 5 - Check current meeting context first
        # if meeting_id := self.state.get_current_meeting():
        #     return meeting_id

        # Check last 1:1 target
        if self.state.last_message_target:
            return self.state.last_message_target

        # Default to Human
        return "human"

    def resolve_say_target(self, target: str = None) -> str:
        """Resolve the target for a Say() call using fallback logic."""
        return self.resolve_target(target, allow_fallback=True)

    @property
    def public_playbooks(self) -> List[Dict[str, Playbook]]:
        """Get list of public playbooks with their information.

        Returns:
            List of dictionaries containing public playbook information
        """
        public_playbooks = []
        for playbook in self.playbooks.values():
            if playbook.public:
                public_playbooks.append(playbook)
        return public_playbooks

    def _build_input_log(self, playbook: Playbook, call: PlaybookCall) -> str:
        """Build the input log string for Langfuse tracing.

        Args:
            playbook: The playbook being executed
            call: The playbook call information

        Returns:
            A string containing the input log data
        """
        log_parts = []
        log_parts.append(str(self.state.call_stack))
        log_parts.append(str(self.state.variables))
        log_parts.append("Session log: \n" + str(self.state.session_log))

        if isinstance(playbook, MarkdownPlaybook):
            log_parts.append(playbook.markdown)
        elif isinstance(playbook, PythonPlaybook):
            log_parts.append(playbook.code or f"Python function: {playbook.name}")
        elif isinstance(playbook, RemotePlaybook):
            log_parts.append(playbook.__repr__())

        log_parts.append(str(call))

        return "\n\n".join(log_parts)

    async def _pre_execute(
        self, playbook_name: str, args: List[Any], kwargs: Dict[str, Any]
    ) -> tuple:
        call = PlaybookCall(playbook_name, args, kwargs)
        playbook = self.playbooks.get(playbook_name)

        trace_str = self.klass + "." + call.to_log_full()

        if playbook:
            # Set up tracing
            if isinstance(playbook, MarkdownPlaybook):
                trace_str = f"Markdown: {trace_str}"
            elif isinstance(playbook, PythonPlaybook):
                trace_str = f"Python: {trace_str}"
        else:
            trace_str = f"External: {trace_str}"

        if self.state.call_stack.peek() is not None:
            langfuse_span = self.state.call_stack.peek().langfuse_span.span(
                name=trace_str
            )
        else:
            langfuse_span = LangfuseHelper.instance().trace(name=trace_str)

        if playbook:
            input_log = self._build_input_log(playbook, call)
            langfuse_span.update(input=input_log)
        else:
            langfuse_span.update(input=trace_str)

        # Add the call to the call stack
        if playbook:
            # Get first step line number if available (for MarkdownPlaybook)
            first_step_line_number = (
                getattr(playbook, "first_step_line_number", None) or 0
            )
        else:
            first_step_line_number = 0

        call_stack_frame = CallStackFrame(
            InstructionPointer(call.playbook_klass, "01", first_step_line_number),
            llm_messages=[],
            langfuse_span=langfuse_span,
        )
        llm_message = []
        if playbook and isinstance(playbook, MarkdownPlaybook):
            llm_message.append("```md\n" + playbook.markdown + "\n```")

        # Add a cached message whenever we add a stack frame
        llm_message.append("Executing " + str(call))
        call_stack_frame.add_cached_llm_message(
            "\n\n".join(llm_message), role=LLMMessageRole.ASSISTANT
        )

        self.state.call_stack.push(call_stack_frame)

        self.state.session_log.append(call)

        self.state.variables.update({"$__": None})

        return playbook, call, langfuse_span

    async def execute_playbook(
        self, playbook_name: str, args: List[Any] = [], kwargs: Dict[str, Any] = {}
    ) -> Any:
        playbook, call, langfuse_span = await self._pre_execute(
            playbook_name, args, kwargs
        )

        # Replace variable names with actual values
        for arg in args:
            if isinstance(arg, str) and arg.startswith("$"):
                var_name = arg
                if var_name in self.state.variables.variables:
                    args[args.index(arg)] = self.state.variables.variables[
                        var_name
                    ].value

        for key, value in kwargs.items():
            if isinstance(value, str) and value.startswith("$"):
                var_name = value
                if var_name in self.state.variables.variables:
                    kwargs[key] = self.state.variables.variables[var_name].value

        # Execute local playbook in this agent
        if playbook:
            try:
                # Set agent reference for playbooks that need it
                if hasattr(playbook, "func") and playbook.func:
                    playbook.func.__globals__.update({"agent": self})

                result = await playbook.execute(*args, **kwargs)
                await self._post_execute(call, result, langfuse_span)
                return result
            except Exception as e:
                await self._post_execute(call, f"Error: {str(e)}", langfuse_span)
                raise
        else:
            # Handle cross-agent playbook calls (AgentName.PlaybookName format)
            if "." in playbook_name:
                agent_name, actual_playbook_name = playbook_name.split(".", 1)
                target_agent = self.other_agents.get(agent_name)
                if (
                    target_agent
                    and actual_playbook_name in target_agent.playbooks
                    and target_agent.playbooks[actual_playbook_name].public
                ):
                    result = await target_agent.execute_playbook(
                        actual_playbook_name, args, kwargs
                    )
                    await self._post_execute(call, result, langfuse_span)
                    return result

            # Try to execute playbook in other agents (fallback)
            for agent in self.other_agents.values():
                if (
                    playbook_name in agent.playbooks
                    and agent.playbooks[playbook_name].public
                ):
                    result = await agent.execute_playbook(playbook_name, args, kwargs)
                    await self._post_execute(call, result, langfuse_span)
                    return result

            # Playbook not found
            error_msg = f"Playbook '{playbook_name}' not found in agent '{self.klass}' or any registered agents"
            await self._post_execute(call, error_msg, langfuse_span)
            return error_msg

    async def _post_execute(
        self, call: PlaybookCall, result: Any, langfuse_span: Any
    ) -> None:
        execution_summary = self.state.variables.variables["$__"].value
        call_result = PlaybookCallResult(call, result, execution_summary)
        self.state.session_log.append(call_result)

        self.state.call_stack.pop()
        if self.state.call_stack.peek() is not None:
            self.state.call_stack.peek().add_uncached_llm_message(
                call_result.to_log_full(), role=LLMMessageRole.ASSISTANT
            )
        langfuse_span.update(output=result)

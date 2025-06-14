from typing import TYPE_CHECKING, Any, Dict, List

from ..agent_clients import InProcessPlaybooksAgentClient
from ..call_stack import CallStackFrame, InstructionPointer
from ..enums import LLMMessageRole
from ..event_bus import EventBus
from ..execution_state import ExecutionState
from ..playbook import MarkdownPlaybook, Playbook, PythonPlaybook
from ..playbook_call import PlaybookCall, PlaybookCallResult
from ..utils.langfuse_helper import LangfuseHelper
from ..utils.parse_utils import parse_metadata_and_description
from .base_agent import BaseAgent

if TYPE_CHECKING:
    pass


class AIAgent(BaseAgent):
    """
    Base class for AI agents.

    An Agent represents an AI entity capable of processing messages through playbooks
    using a main execution thread.

    Attributes:
        klass: The class/type of this agent.
        description: Human-readable description of the agent.
        playbooks: Dictionary of playbooks available to this agent.
        agent_python_namespace: Isolated python namespace for the agent's python playbooks.
    """

    def __init__(
        self,
        klass: str,
        description: str,
        event_bus: EventBus,
        playbooks: Dict[str, Playbook] = None,
        source_line_number: int = None,
    ):
        """Initialize a new Agent.

        Args:
            klass: The class/type of this agent.
            description: Human-readable description of the agent.
            bus: The event bus for publishing events.
            playbooks: Dictionary of playbooks available to this agent.
            source_line_number: The line number in the source markdown where this
                agent is defined.
        """
        super().__init__(klass)
        self.metadata, self.description = parse_metadata_and_description(description)
        self.playbooks: Dict[str, Playbook] = playbooks or {}
        self.state = ExecutionState(event_bus)
        self.source_line_number = source_line_number
        self.public_json = None
        self.agent_clients = {}
        for playbook in self.playbooks.values():
            if hasattr(playbook, "func") and playbook.func:
                playbook.func.__globals__.update({"agent": self})

    async def begin(self):
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

        log_parts.append(str(call))

        return "\n\n".join(log_parts)

    async def _pre_execute(
        self, playbook_name: str, args: List[Any], kwargs: Dict[str, Any]
    ) -> tuple:
        call = PlaybookCall(playbook_name, args, kwargs)
        playbook = self.playbooks.get(playbook_name)

        trace_str = call.to_log_full()

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
                    playbook.func.__globals__["agent"] = self

                # Use the new execute interface
                result = await playbook.execute(*args, **kwargs)
                await self._post_execute(call, result, langfuse_span)
                return result
            except Exception as e:
                await self._post_execute(call, str(e), langfuse_span)
                raise

        # Execute playbook in another agent
        elif "." in playbook_name:
            agent_klass, playbook_name = playbook_name.split(".", maxsplit=1)
            if agent_klass != self.klass:
                other_agent = self.agent_clients.get(agent_klass)
                try:
                    if other_agent:
                        retval = await other_agent.execute_playbook(
                            playbook_name, args, kwargs
                        )
                    await self._post_execute(call, retval, langfuse_span)
                    return retval
                except Exception as e:
                    await self._post_execute(call, str(e), langfuse_span)
                    raise
            else:
                raise ValueError(
                    f"Agent {agent_klass} not found when making call {call}"
                )
        else:
            raise ValueError(f"Playbook {playbook_name} not found")

    def parse_instruction_pointer(self, step: str) -> InstructionPointer:
        """Parse an instruction pointer from a string in format "Playbook:LineNumber[:Extra]".

        Args:
            step: The instruction pointer string in format "Playbook:LineNumber[:Extra]".

        Returns:
            An InstructionPointer object.
        """
        parts = step.split(":")
        playbook_name = parts[0]
        line_number = parts[1] if len(parts) > 1 else "01"

        playbook = self.playbooks[playbook_name]

        # Only MarkdownPlaybook has step_collection
        if isinstance(playbook, MarkdownPlaybook) and playbook.step_collection:
            playbook_step = playbook.step_collection.get_step(line_number)
            if playbook_step:
                source_line_number = playbook_step.source_line_number
            else:
                source_line_number = playbook.first_step_line_number
        else:
            source_line_number = 0

        return InstructionPointer(
            playbook_name,
            line_number,
            source_line_number,
        )

    def trigger_instructions(
        self, with_namespace: bool = False, public_only: bool = False
    ) -> List[str]:
        """Get trigger instructions for this agent."""
        trigger_instructions = []
        playbooks = self.playbooks.values()
        if public_only:
            playbooks = [playbook for playbook in playbooks if playbook.public]

        for playbook in playbooks:
            # Only get trigger instructions if the playbook has them
            if hasattr(playbook, "trigger_instructions"):
                playbook_trigger_instructions = playbook.trigger_instructions(
                    namespace=self.klass if with_namespace else None
                )
                trigger_instructions.extend(playbook_trigger_instructions)

        return trigger_instructions

    def other_agents(self) -> List["AIAgent"]:
        """Get all other agents in the program."""
        return [
            agent
            for agent in self.program.agents
            if agent.id != self.id and isinstance(agent, AIAgent)
        ]

    def all_trigger_instructions(self) -> List[str]:
        """Get all trigger instructions for this agent and public only with namespace for other agents"""
        trigger_instructions = self.trigger_instructions()

        for agent in self.other_agents():
            trigger_instructions.extend(
                agent.trigger_instructions(with_namespace=True, public_only=True)
            )

        return trigger_instructions

    def get_public_information(self) -> str:
        """Get public information about this agent."""
        """
        Format:
        # AgentName
        Description
        Public playbooks:
        - `Playbook signature`: Playbook description
        - `Playbook signature`: Playbook description
        - ...
        """
        information = []
        information.append(f"# {self.klass}")
        information.append(self.description)
        information.append("Public playbooks:")
        for playbook in self.playbooks.values():
            if playbook.public:
                signature = getattr(playbook, "signature", playbook.name)
                information.append(
                    f"- `{self.klass}.{signature}`: {playbook.description}"
                )
        return "\n".join(information)

    def other_agents_information(self) -> List[str]:
        """Get public information about other agents in the program."""
        information = []
        for agent in self.other_agents():
            information.append(agent.get_public_information())

        return information

    def set_up_agent_clients(self):
        for agent in self.other_agents():
            self.agent_clients[agent.klass] = InProcessPlaybooksAgentClient(agent)

    @property
    def public_playbooks(self) -> List[Dict[str, Any]]:
        """Get a list of public playbooks for this agent.

        Returns:
            A list of dictionaries containing public playbook information
        """
        public_playbooks = []
        for playbook in self.playbooks.values():
            if playbook.public:
                playbook_info = {
                    "name": playbook.name,
                }

                # Add triggers if they exist
                if hasattr(playbook, "triggers") and playbook.triggers:
                    playbook_info["triggers"] = [
                        trigger.trigger for trigger in playbook.triggers.triggers
                    ]

                public_playbooks.append(playbook_info)

        return public_playbooks

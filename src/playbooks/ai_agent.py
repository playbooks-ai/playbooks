from typing import TYPE_CHECKING, Any, Dict, List

from .base_agent import BaseAgent
from .call_stack import CallStackFrame, InstructionPointer
from .enums import PlaybookExecutionType
from .event_bus import EventBus
from .execution_state import ExecutionState
from .playbook import Playbook
from .playbook_call import PlaybookCall, PlaybookCallResult
from .utils.langfuse_helper import LangfuseHelper

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
        self.description = description
        self.playbooks: Dict[str, Playbook] = playbooks or {}
        self.state = ExecutionState(event_bus)
        self.source_line_number = source_line_number
        for playbook in self.playbooks.values():
            playbook.func.__globals__.update({"agent": self})
        self.public = None

    async def begin(self):
        # Find playbooks with a BGN trigger and execute them
        playbooks_to_execute = []
        for playbook in self.playbooks.values():
            if playbook.triggers:
                for trigger in playbook.triggers.triggers:
                    if trigger.is_begin:
                        playbooks_to_execute.append(playbook)

        # TODO: execute the playbooks in parallel
        for playbook in playbooks_to_execute:
            await self.execute_playbook(playbook.klass)

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
        if playbook.execution_type == PlaybookExecutionType.MARKDOWN:
            log_parts.append(playbook.markdown)
        else:
            log_parts.append(playbook.code)
        log_parts.append(str(call))

        return "\n\n".join(log_parts)

    async def _pre_execute(
        self, playbook_klass: str, args: List[Any], kwargs: Dict[str, Any]
    ) -> tuple:
        playbook = self.playbooks[playbook_klass]
        call = PlaybookCall(playbook_klass, args, kwargs)

        # Set up tracing
        trace_str = call.to_log_compact()
        if playbook.execution_type == PlaybookExecutionType.MARKDOWN:
            trace_str = f"Markdown: {trace_str}"
        else:
            trace_str = f"Python: {trace_str}"
        if self.state.call_stack.peek() is not None:
            langfuse_span = self.state.call_stack.peek().langfuse_span.span(
                name=trace_str
            )
        else:
            langfuse_span = LangfuseHelper.instance().trace(name=trace_str)

        input_log = self._build_input_log(playbook, call)
        langfuse_span.update(input=input_log)

        # Add the call to the call stack
        first_step_line_number = playbook.first_step_line_number
        self.state.call_stack.push(
            CallStackFrame(
                InstructionPointer(playbook.klass, "01", first_step_line_number),
                langfuse_span=langfuse_span,
            )
        )

        self.state.session_log.append(call)

        return playbook, call, langfuse_span

    async def _post_execute(
        self, call: PlaybookCall, result: Any, langfuse_span: Any
    ) -> None:
        call_result = PlaybookCallResult(call, result)
        self.state.session_log.append(call_result)

        self.state.call_stack.pop()
        langfuse_span.update(output=result)

    async def execute_playbook(
        self, playbook_klass: str, args: List[Any] = [], kwargs: Dict[str, Any] = {}
    ) -> Any:
        playbook, call, langfuse_span = await self._pre_execute(
            playbook_klass, args, kwargs
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

        try:
            playbook.func.__globals__["agent"] = self
            result = await playbook.func(*args, **kwargs)
            await self._post_execute(call, result, langfuse_span)
            return result
        except Exception as e:
            await self._post_execute(call, str(e), langfuse_span)
            raise

    def parse_instruction_pointer(self, step: str) -> InstructionPointer:
        """Parse an instruction pointer from a string in format "Playbook:LineNumber[:Extra]".

        Args:
            step: The instruction pointer string in format "Playbook:LineNumber[:Extra]".

        Returns:
            An InstructionPointer object.
        """
        parts = step.split(":")
        playbook_klass = parts[0]
        line_number = parts[1] if len(parts) > 1 else "01"

        playbook = self.playbooks[playbook_klass]
        playbook_step = playbook.step_collection.get_step(line_number)
        if playbook_step:
            source_line_number = playbook_step.source_line_number
        else:
            source_line_number = playbook.first_step_line_number
        return InstructionPointer(
            playbook_klass,
            line_number,
            source_line_number,
        )

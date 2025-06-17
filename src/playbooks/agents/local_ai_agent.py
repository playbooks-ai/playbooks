import logging
from typing import Any, Dict, List

from ..call_stack import CallStackFrame, InstructionPointer
from ..enums import LLMMessageRole
from ..event_bus import EventBus
from ..playbook import MarkdownPlaybook, Playbook, PythonPlaybook
from ..playbook_call import PlaybookCall, PlaybookCallResult
from ..utils.langfuse_helper import LangfuseHelper
from .ai_agent import AIAgent

logger = logging.getLogger(__name__)


class LocalAIAgent(AIAgent):
    """
    Local AI agent that executes playbooks locally.

    This agent executes markdown and Python playbooks within the local process,
    using the existing execution infrastructure.
    """

    def __init__(
        self,
        klass: str,
        description: str,
        event_bus: EventBus,
        playbooks: Dict[str, Playbook] = None,
        source_line_number: int = None,
    ):
        """Initialize a new LocalAIAgent.

        Args:
            klass: The class/type of this agent.
            description: Human-readable description of the agent.
            event_bus: The event bus for publishing events.
            playbooks: Dictionary of playbooks available to this agent.
            source_line_number: The line number in the source markdown where this
                agent is defined.
        """
        super().__init__(klass, description, event_bus, playbooks, source_line_number)
        # Set up agent reference for playbooks that need it
        for playbook in self.playbooks.values():
            if hasattr(playbook, "func") and playbook.func:
                playbook.func.__globals__.update({"agent": self})

    async def discover_playbooks(self) -> None:
        """Discover playbooks for local agent.

        For LocalAIAgent, playbooks are already provided during initialization,
        so this method is a no-op.
        """
        pass

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

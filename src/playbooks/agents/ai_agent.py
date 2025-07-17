import asyncio
import copy
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List

from ..call_stack import CallStackFrame, InstructionPointer
from ..constants import HUMAN_AGENT_KLASS
from ..enums import LLMMessageRole, StartupMode
from ..event_bus import EventBus
from ..exceptions import ExecutionFinished
from ..execution_state import ExecutionState
from ..meetings import MeetingManager
from ..message import Message, MessageType
from ..playbook import MarkdownPlaybook, Playbook, PythonPlaybook, RemotePlaybook
from ..playbook_call import PlaybookCall, PlaybookCallResult
from ..utils.langfuse_helper import LangfuseHelper
from ..utils.spec_utils import SpecUtils
from .base_agent import BaseAgent, BaseAgentMeta

if TYPE_CHECKING:
    from ..program import Program

logger = logging.getLogger(__name__)


class AIAgentMeta(BaseAgentMeta):
    """Meta class for AIAgent."""

    def __new__(cls, name, bases, attrs):
        cls = super().__new__(cls, name, bases, attrs)
        cls.validate_metadata()
        return cls

    @property
    def startup_mode(self) -> StartupMode:
        """Get the startup mode for this agent."""
        return getattr(self, "metadata", {}).get("startup_mode", StartupMode.DEFAULT)

    def validate_metadata(self):
        """Validate the metadata for this agent."""
        if self.startup_mode not in [StartupMode.DEFAULT, StartupMode.STANDBY]:
            raise ValueError(f"Invalid startup mode: {self.startup_mode}")

    def should_create_instance_at_start(self) -> bool:
        """Whether to create an instance of the agent at start.

        Override in subclasses to control whether to create an instance at start.
        """
        # If there is any playbook with a BGN trigger, return True
        for playbook in self.playbooks.values():
            if playbook.triggers:
                for trigger in playbook.triggers.triggers:
                    if trigger.is_begin:
                        return True

        # This agent does not have any BGN playbook
        # Check if it should be created in standby mode
        if self.startup_mode == StartupMode.STANDBY:
            return True

        return False


class AIAgent(BaseAgent, ABC, metaclass=AIAgentMeta):
    """
    Abstract base class for AI agents.

    An Agent represents an AI entity capable of processing messages through playbooks
    using a main execution thread. This class defines the interface that all AI agent
    implementations must adhere to.

    Attributes:
        klass: The class/type of this agent.
        description: Human-readable description of the agent.
        playbooks: Dictionary of playbooks available to this agent.
    """

    def __init__(
        self,
        event_bus: EventBus,
        source_line_number: int = None,
        agent_id: str = None,
        program: "Program" = None,
        **kwargs,
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
        super().__init__(agent_id=agent_id, program=program, **kwargs)
        self.playbooks: Dict[str, Playbook] = copy.deepcopy(
            self.__class__.playbooks or {}
        )

        # Create instance-specific namespace manager if available
        if (
            hasattr(self.__class__, "namespace_manager")
            and self.__class__.namespace_manager
        ):
            # Use shallow copy of namespace - most objects are safe to share
            from .namespace_manager import AgentNamespaceManager

            self.namespace_manager = AgentNamespaceManager(
                namespace=self.__class__.namespace_manager.namespace.copy()
            )
            self.namespace_manager.namespace["agent"] = self

            # Create cross-playbook wrapper functions for this instance
            for playbook_name, playbook in self.playbooks.items():
                call_through = playbook.create_namespace_function(self)
                self.namespace_manager.namespace[playbook_name] = call_through

            # Create instance-specific wrapper functions that bind the correct agent
            for playbook_name, playbook in self.playbooks.items():
                if hasattr(playbook, "func") and playbook.func:
                    # For MarkdownPlaybook, create agent-specific function
                    if hasattr(playbook, "create_agent_specific_function"):
                        agent_specific_func = playbook.create_agent_specific_function(
                            self
                        )
                        # Copy globals from original for cross-agent access
                        agent_specific_func.__globals__.update(
                            self.namespace_manager.namespace
                        )
                        self.playbooks[playbook_name].func = agent_specific_func
                    else:
                        # For other playbook types, just update globals
                        playbook.func.__globals__.update(
                            self.namespace_manager.namespace
                        )

        # Initialize meeting manager
        self.meeting_manager = MeetingManager(agent=self)

        self.meeting_manager.ensure_meeting_playbook_kwargs(self.playbooks)

        self.state = ExecutionState(event_bus, self.klass, self.id)
        self.source_line_number = source_line_number
        self.public_json = None

    @abstractmethod
    async def discover_playbooks(self) -> None:
        """Discover and load playbooks for this agent.

        This method should populate the self.playbooks dictionary with
        available playbooks for this agent.
        """
        pass

    @property
    def other_agents(self) -> List["AIAgent"]:
        """Get list of other AI agents in the system.

        Returns:
            List of other agent instances
        """
        if (
            not self.program
            or not hasattr(self.program, "agents")
            or not self.program.agents
        ):
            return []

        return list(
            filter(lambda x: isinstance(x, AIAgent) and x != self, self.program.agents)
        )

    def event_agents_changed(self):
        self.state.agents = [str(agent) for agent in self.program.agents]

    def get_available_playbooks(self) -> List[str]:
        """Get a list of available playbook names.

        Returns:
            List of playbook names available to this agent
        """
        return list(self.playbooks.keys())

    async def begin(self):
        """Execute playbooks with BGN trigger."""
        # Create a list to track BGN playbook tasks
        bgn_tasks = []

        def create_idle_task():
            asyncio.create_task(self._idle_loop())
            # idle_task.add_done_callback(
            #     lambda t: print(f"{str(self)} : Idle loop task done")
            # )

        # Find playbooks with a BGN trigger and execute them
        for playbook in self.playbooks.values():
            if hasattr(playbook, "triggers") and playbook.triggers:
                for trigger in playbook.triggers.triggers:
                    if trigger.is_begin:
                        # Create task for each BGN playbook
                        task = asyncio.create_task(self.execute_playbook(playbook.name))
                        # print(f"{str(self)} : BGN task created - {playbook.name}")

                        def task_done_callback(t):
                            # print(f"{str(self)} : BGN task done - {playbook.name}")
                            create_idle_task()

                        task.add_done_callback(task_done_callback)
                        bgn_tasks.append(task)
                        break  # Only need one BGN trigger per playbook

        # If there are BGN tasks, we can optionally wait for them
        # But the idle loop continues running regardless
        if bgn_tasks:
            # Wait for all BGN playbooks to complete
            await asyncio.gather(*bgn_tasks, return_exceptions=True)
        else:
            # Start idle loop because there are no BGN tasks
            create_idle_task()

    async def _idle_loop(self):
        """Idle loop that processes incoming messages."""
        sleep_turns = 0
        sleep_turns_max = 5
        while True:
            if self.program.execution_finished:
                break
            # print(f"\n{str(self)}: _idle_loop")
            # If playbooks are running, we let them receive messages
            if not self.state.call_stack.is_empty():
                # print(f"{str(self)} : _idle_loop - playbooks are running, sleeping...")
                await asyncio.sleep(5)
                sleep_turns += 1
                if sleep_turns >= sleep_turns_max:
                    # print(
                    #     f"{str(self)} : _idle_loop - max sleep turns reached, forcing a continue message"
                    # )
                    self._message_buffer.append(
                        Message(
                            sender_id="human",
                            sender_klass=HUMAN_AGENT_KLASS,
                            recipient_id=self.id,
                            recipient_klass=self.klass,
                            content="Continue",
                            message_type=MessageType.DIRECT,
                            meeting_id=self.state.get_current_meeting(),
                        )
                    )
                    self._message_event.set()
                    sleep_turns = 0
                continue

            sleep_turns = 0
            try:
                # Wait for message event with timeout to allow graceful shutdown
                await asyncio.wait_for(self._message_event.wait(), timeout=1.0)
                self._process_collected_messages()
                self._message_event.clear()
            except asyncio.TimeoutError:
                # Timeout is normal - just check if we should continue
                continue
            except asyncio.CancelledError:
                # Task is being cancelled - exit gracefully
                break

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

    def all_trigger_instructions(self) -> List[str]:
        """Get all trigger instructions including from other agents.

        Returns:
            List of all trigger instruction strings
        """
        instructions = self.trigger_instructions(with_namespace=False)
        for agent in self.other_agents:
            instructions.extend(agent.trigger_instructions(with_namespace=True))
        return instructions

    @classmethod
    def get_compact_information(cls) -> str:
        info_parts = []
        info_parts.append(f"# {cls.klass}")
        if cls.description:
            info_parts.append(f"{cls.description}")

        if cls.playbooks:
            for playbook in cls.playbooks.values():
                if not playbook.hidden:
                    info_parts.append(f"## {playbook.signature}")
                    if playbook.description:
                        info_parts.append(
                            playbook.description[:100]
                            + ("..." if len(playbook.description) > 100 else "")
                        )
                    info_parts.append("\n")

        return "\n".join(info_parts)

    @classmethod
    def get_public_information(cls) -> str:
        """Get public information about an agent klass

        Returns:
            String containing public agent information
        """
        info_parts = []
        info_parts.append(f"# {cls.klass}")
        if cls.description:
            info_parts.append(f"{cls.description}")

        if cls.playbooks:
            for playbook in cls.playbooks.values():
                if playbook.public:
                    info_parts.append(f"## {cls.klass}.{playbook.name}")
                    info_parts.append(playbook.description)

        return "\n".join(info_parts)

    def other_agent_klasses_information(self) -> List[str]:
        """Get information about other registered agents.

        Returns:
            List of information strings for other agents
        """
        return [
            agent_klass.get_public_information()
            for agent_klass in self.program.agent_klasses.values()
            if agent_klass.klass != self.klass
        ]

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
            if target == "meeting":
                # Map "meeting" to current meeting context
                if meeting_id := self.state.get_current_meeting():
                    return f"meeting {meeting_id}"
                return None  # No current meeting

            if SpecUtils.is_meeting_spec(target):
                return target  # Return as-is for now

            # Handle agent ID targets
            if SpecUtils.is_agent_spec(target):
                agent_id = SpecUtils.extract_agent_id(target)
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
            for agent in self.other_agents:
                if agent.klass == target:
                    return agent.id

            # If not found, check if Human agent exists with this type name
            if target == HUMAN_AGENT_KLASS:
                return "human"

            # Target not found - fallback to human if allowed
            return "human" if allow_fallback else None

        # No target specified - use fallback logic if allowed
        if not allow_fallback:
            return None

        # Fallback logic: current context → last 1:1 target → Human
        # Check current meeting context first
        if meeting_id := self.state.get_current_meeting():
            return f"meeting {meeting_id}"

        # Check last 1:1 target
        if self.state.last_message_target:
            return self.state.last_message_target

        # Default to Human
        return "human"

    @property
    def public_playbooks(self) -> List[Playbook]:
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

        trace_str = str(self) + "." + call.to_log_full()

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

        # Check if this is a meeting playbook and get meeting context
        is_meeting = False
        meeting_id = None
        if playbook and playbook.meeting:
            is_meeting = True
            # Try to get meeting ID from kwargs or current context
            meeting_id = kwargs.get("meeting_id") or self.state.get_current_meeting()

        call_stack_frame = CallStackFrame(
            InstructionPointer(call.playbook_klass, "01", first_step_line_number),
            llm_messages=[],
            langfuse_span=langfuse_span,
            is_meeting=is_meeting,
            meeting_id=meeting_id,
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

        try:
            # Handle meeting playbook initialization (only for new meetings, not when joining existing ones)
            if (
                playbook
                and playbook.meeting
                and not self.meeting_manager.get_current_meeting_from_call_stack()
            ):
                meeting = await self.meeting_manager.create_meeting(
                    playbook_name, kwargs
                )

                # Wait for required attendees to join before proceeding (if any besides requester)
                await self.meeting_manager._wait_for_required_attendees(meeting)

                message = f"Meeting {meeting.id} ready to proceed - all required attendees present"
                self.state.session_log.append(message)
                self.add_uncached_llm_message(message)

        except TimeoutError as e:
            error_msg = f"Meeting initialization failed: {str(e)}"
            await self._post_execute(call, error_msg, langfuse_span)
            return error_msg

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
                result = await playbook.execute(*args, **kwargs)
                await self._post_execute(call, result, langfuse_span)
                return result
            except ExecutionFinished as e:
                self.program.execution_finished_event.set()
                message = str(e)
                await self._post_execute(call, message, langfuse_span)
                return message
            except Exception as e:
                message = f"Error: {str(e)}"
                await self._post_execute(call, message, langfuse_span)
                raise
        else:
            # Handle cross-agent playbook calls (AgentName.PlaybookName format)
            if "." in playbook_name:
                agent_name, actual_playbook_name = playbook_name.split(".", 1)
                target_agent = list(
                    filter(lambda x: x.klass == agent_name, self.program.agents)
                )
                if target_agent:
                    target_agent = target_agent[0]

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
            for agent in self.other_agents:
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
        self.add_uncached_llm_message(message=call_result.to_log_full())

        langfuse_span.update(output=result)

    def __str__(self):
        if self.kwargs:
            kwargs_msg = ", ".join([f"{k}:{v}" for k, v in self.kwargs.items()])
            return f"{self.klass}(agent {self.id}, {kwargs_msg})"
        else:
            return f"{self.klass}(agent {self.id})"

    def __repr__(self):
        return f"{self.klass}(agent {self.id})"

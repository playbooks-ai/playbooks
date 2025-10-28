import copy
import hashlib
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from ..argument_types import LiteralValue, VariableReference
from ..call_stack import CallStackFrame, InstructionPointer
from ..config import config
from ..constants import EXECUTION_FINISHED, HUMAN_AGENT_KLASS
from ..debug_logger import debug
from ..enums import StartupMode
from ..event_bus import EventBus
from ..exceptions import ExecutionFinished
from ..execution_state import ExecutionState
from ..llm_messages import (
    ExecutionResultLLMMessage,
    FileLoadLLMMessage,
    MeetingLLMMessage,
)
from ..llm_messages.types import ArtifactLLMMessage
from ..meetings import MeetingManager
from ..playbook import LLMPlaybook, Playbook, PythonPlaybook, RemotePlaybook
from ..playbook_call import PlaybookCall, PlaybookCallResult
from ..utils.expression_engine import (
    ExpressionContext,
    resolve_description_placeholders,
)
from ..utils.langfuse_helper import LangfuseHelper
from ..utils.misc import copy_func
from ..utils.spec_utils import SpecUtils
from ..variables import Artifact
from .base_agent import BaseAgent, BaseAgentMeta
from .namespace_manager import AgentNamespaceManager

if TYPE_CHECKING:
    from ..program import Program


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
        source_file_path: str = None,
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
        super().__init__(
            agent_id=agent_id,
            program=program,
            source_line_number=source_line_number,
            source_file_path=source_file_path,
            **kwargs,
        )
        self.playbooks: Dict[str, Playbook] = self.deep_copy_playbooks(
            self.__class__.playbooks or {}
        )
        # Create instance-specific namespace with playbook wrappers
        self._setup_isolated_namespace()

        # Initialize meeting manager
        self.meeting_manager = MeetingManager(agent=self)

        self.meeting_manager.ensure_meeting_playbook_kwargs(self.playbooks)

        self.state = ExecutionState(event_bus, self.klass, self.id)
        self.source_line_number = source_line_number
        self.public_json = None

        # Track background tasks for cleanup
        # self._background_tasks = []

        # Create playbook to run BGN playbooks
        self.bgn_playbook_name = None
        self.create_begin_playbook()

    def deep_copy_playbooks(self, playbooks):
        """Deep copy the playbooks."""
        playbooks_copy = copy.deepcopy(playbooks)
        for playbook in playbooks_copy.values():
            if playbook.func:
                playbook.func = copy_func(playbook.func)

        return playbooks_copy

    def _setup_isolated_namespace(self):
        """Create isolated namespace with instance-specific agent reference and playbook wrappers."""
        # Create isolated namespace for this instance
        # Preserve class-level namespace if it exists (contains imports from Python code blocks)
        if (
            hasattr(self.__class__, "namespace_manager")
            and self.__class__.namespace_manager
        ):
            # Copy the class namespace to preserve imports and module-level variables
            self.namespace_manager = AgentNamespaceManager(
                namespace=self.__class__.namespace_manager.namespace.copy()
            )
        else:
            self.namespace_manager = AgentNamespaceManager()
        self.namespace_manager.namespace["agent"] = self

        # Set up cross-playbook wrapper functions and bind agent-specific functions
        for playbook_name, playbook in self.playbooks.items():
            # Create cross-playbook wrapper function
            call_through = playbook.create_namespace_function(self)
            self.namespace_manager.namespace[playbook_name] = call_through
            playbook.agent_name = str(self)

        for playbook_name, playbook in self.playbooks.items():
            if (
                hasattr(playbook, "create_agent_specific_function")
                and not playbook.func
            ):
                playbook.func = playbook.create_agent_specific_function(self)
            else:
                playbook.func = copy_func(
                    playbook.func,
                    globals={
                        **playbook.func.__globals__,
                        **self.namespace_manager.namespace,
                    },
                )

    def create_agent_wrapper(self, agent, func):
        """Create an agent-specific wrapper that bypasses globals lookup."""

        async def agent_specific_wrapper(*args, _agent=agent, **kwargs):
            return await func(*args, **kwargs)

        return agent_specific_wrapper

    @abstractmethod
    async def discover_playbooks(self) -> None:
        """Discover and load playbooks for this agent.

        This method should populate the self.playbooks dictionary with
        available playbooks for this agent.
        """
        pass

    @property
    def startup_mode(self) -> StartupMode:
        """Get the startup mode for this agent."""
        return self.__class__.startup_mode

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

    def create_begin_playbook(self):
        begin_playbooks = {}
        for playbook in self.playbooks.values():
            if hasattr(playbook, "triggers") and playbook.triggers:
                for trigger in playbook.triggers.triggers:
                    if trigger.is_begin:
                        begin_playbooks[playbook.name] = playbook

        # If there are multiple BGN playbooks, create a new playbook that calls them in order
        self.bgn_playbook_name = "Begin__"
        while self.bgn_playbook_name in self.playbooks:
            self.bgn_playbook_name = "_" + self.bgn_playbook_name
        code_block = f"""
@playbook
async def {self.bgn_playbook_name}() -> None:
    # Main loop for agent "{self.klass}"
    # Auto-generated by Playbooks AI runtime
    # 
    # Calls any playbooks that should be executed when the program starts, followed by a loop that waits for messages and processes them.
    agent.state.variables["$_busy"] = True
{"\n".join(["    await " + playbook.name + "()" for playbook in begin_playbooks.values()])}

    agent.state.variables["$_busy"] = False
    if agent.program and agent.program.execution_finished:
        return
    
    # Enter a message processing event loop
    await MessageProcessingEventLoop()
"""

        # Save to tmp file
        filename = f"{self.klass}_{self.bgn_playbook_name}_{hashlib.sha256(code_block.encode()).hexdigest()[:16]}.pb"
        file_path = Path(tempfile.gettempdir()) / filename
        with open(file_path, "w") as f:
            f.write(code_block)

        # debug("BGN Playbook Code Block: " + code_block)
        new_playbook = PythonPlaybook.create_playbooks_from_code_block(
            code_block,
            self.namespace_manager,
            file_path,
            1,
        )
        for playbook in new_playbook.values():
            playbook.source_file_path = file_path
            playbook.agent_name = str(self)
        self.playbooks.update(new_playbook)

    async def begin(self):
        success, result = await self.execute_playbook(self.bgn_playbook_name)
        return

    async def cleanup(self):
        """Cancel all background tasks and clean up resources."""
        # Only cleanup if execution is truly finished
        if not (self.program and self.program.execution_finished):
            return

    def parse_instruction_pointer(self, step_id: str) -> InstructionPointer:
        """Parse a step string into an InstructionPointer.

        Args:
            step: Step string to parse

        Returns:
            InstructionPointer: Parsed instruction pointer
        """
        # Extract the step number from the step string
        playbook_name = step_id.split(":")[0]
        step_number = step_id.split(":")[1]
        playbook = self.playbooks.get(playbook_name)

        # Ignore trigger and note step, e.g. `PB:T1`, `PB:N1`
        if playbook and step_number[0] not in ["T", "N"] and playbook.steps:
            line = playbook.steps.get_step(step_number)
            if line:
                return InstructionPointer(
                    playbook=playbook_name,
                    line_number=step_number,
                    source_line_number=line.source_line_number,
                    step=line,
                    source_file_path=line.source_file_path,
                )
        return InstructionPointer(
            playbook=playbook_name,
            line_number=step_number,
            source_line_number=0,
            step=None,
            source_file_path=None,
        )

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

        if isinstance(playbook, LLMPlaybook):
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
            if isinstance(playbook, LLMPlaybook):
                trace_str = f"Markdown: {trace_str}"
            elif isinstance(playbook, PythonPlaybook):
                trace_str = f"Python: {trace_str}"
            elif isinstance(playbook, RemotePlaybook):
                trace_str = f"Remote: {trace_str}"
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
            # Get first step line number if available (for LLMPlaybook)
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

        source_file_path = (
            playbook.source_file_path
            if playbook and hasattr(playbook, "source_file_path")
            else None
        )
        source_file_path = source_file_path or "[unknown]"
        call_stack_frame = CallStackFrame(
            InstructionPointer(
                playbook=call.playbook_klass,
                line_number="01",
                source_line_number=first_step_line_number,
                source_file_path=source_file_path,
            ),
            langfuse_span=langfuse_span,
            is_meeting=is_meeting,
            meeting_id=meeting_id,
        )
        self.state.call_stack.push(call_stack_frame)
        self.state.session_log.append(call)

        self.state.variables.update({"$__": None})

        return playbook, call, langfuse_span

    def _is_external_playbook(self, playbook_name: str, playbook: Any) -> bool:
        """Determine if playbook is external (cross-agent communication).

        External playbooks include:
        - Say (all targets: user, agent, meeting)
        - SendMessage (always cross-agent)
        - RemotePlaybook (MCP tools)
        - Cross-agent calls (OtherAgent.PlaybookName)
        """
        from playbooks.playbook import RemotePlaybook

        # Say to any target (user, agent, meeting)
        if playbook_name == "Say":
            return True
        # SendMessage is always cross-agent
        if playbook_name == "SendMessage":
            return True
        # RemotePlaybook (MCP tools)
        if playbook and isinstance(playbook, RemotePlaybook):
            return True
        # Cross-agent calls (OtherAgent.PlaybookName)
        if "." in playbook_name:
            return True
        return False

    async def _resolve_argument(
        self,
        arg: Any,
        is_external: bool,
        is_python: bool,
        is_llm: bool,
        context: "ExpressionContext",
    ) -> Any:
        """Resolve argument based on playbook type.

        Args:
            arg: Argument to resolve (may be LiteralValue, VariableReference, or raw value)
            is_external: Whether playbook is external (Say, SendMessage, RemotePlaybook, etc.)
            is_python: Whether playbook is a PythonPlaybook
            is_llm: Whether playbook is an LLMPlaybook
            context: Expression context for variable resolution

        Returns:
            Resolved argument value appropriate for the playbook type
        """

        if isinstance(arg, LiteralValue):
            # Handle string interpolation {$var}
            if isinstance(arg.value, str) and "{" in arg.value:
                return await resolve_description_placeholders(arg.value, context)
            return arg.value

        elif isinstance(arg, VariableReference):
            # Evaluate the reference
            resolved = context.evaluate_expression(arg.reference)

            # Handle Artifact based on playbook type
            if isinstance(resolved, Artifact):
                if is_llm:
                    return arg.reference  # LLM: keep as "$var" string
                elif is_python:
                    return resolved  # Python: keep Artifact object
                else:  # is_external or unknown (default to external behavior)
                    return resolved.value  # External: resolve to value
            else:
                if is_llm:
                    return arg.reference  # LLM: keep as "$var" for non-artifacts too
                return resolved  # External/Python/Unknown: use resolved value

        else:
            # Not a typed argument (shouldn't happen, but fallback)
            return arg

    async def execute_playbook(
        self, playbook_name: str, args: List[Any] = [], kwargs: Dict[str, Any] = {}
    ) -> tuple[bool, Any]:
        if self.program and self.program.execution_finished:
            return (True, EXECUTION_FINISHED)

        playbook, call, langfuse_span = await self._pre_execute(
            playbook_name, args, kwargs
        )

        # Type-based argument resolution
        # Use call.args and call.kwargs which contain typed arguments from _pre_execute
        args = call.args if hasattr(call, "args") else args
        kwargs = call.kwargs if hasattr(call, "kwargs") else kwargs

        # Ensure args is a list (not tuple) so we can modify it
        args = list(args) if not isinstance(args, list) else args

        context = ExpressionContext(agent=self, state=self.state, call=call)

        # Determine playbook type
        is_external = self._is_external_playbook(playbook_name, playbook)
        is_python = isinstance(playbook, PythonPlaybook) if playbook else False
        is_llm = isinstance(playbook, LLMPlaybook) if playbook else False

        # Resolve arguments based on playbook type
        for i, arg in enumerate(args):
            args[i] = await self._resolve_argument(
                arg, is_external, is_python, is_llm, context
            )

        for key, value in kwargs.items():
            kwargs[key] = await self._resolve_argument(
                value, is_external, is_python, is_llm, context
            )

        try:
            # Handle meeting playbook initialization (only for new meetings, not when joining existing ones)
            debug(f"{str(self)}: Handling meeting playbook execution: {playbook_name}")
            debug(
                f"{str(self)}: Current meeting from call stack: {self.meeting_manager.get_current_meeting_from_call_stack()}"
            )
            if (
                playbook
                and playbook.meeting
                and not self.meeting_manager.get_current_meeting_from_call_stack()
            ):
                meeting = await self.meeting_manager.create_meeting(
                    playbook_name, kwargs
                )

                if self.program and self.program.execution_finished:
                    return EXECUTION_FINISHED

                # Wait for required attendees to join before proceeding (if any besides requester)
                await self.meeting_manager._wait_for_required_attendees(meeting)

                message = f"Meeting {meeting.id} ready to proceed - all required attendees present"
                self.state.session_log.append(message)

                meeting_msg = MeetingLLMMessage(message, meeting_id=meeting.id)
                self.state.call_stack.add_llm_message(meeting_msg)
        except TimeoutError as e:
            error_msg = f"Meeting initialization failed: {str(e)}"
            await self._post_execute(call, False, error_msg, langfuse_span)
            return (False, error_msg)

        # Execute local playbook in this agent
        if playbook:
            try:
                if self.program and self.program.execution_finished:
                    return (False, EXECUTION_FINISHED)

                result = await playbook.execute(*args, **kwargs)
                await self._post_execute(call, True, result, langfuse_span)
                return (True, result)
            except ExecutionFinished as e:
                debug("Execution finished, exiting", agent=str(self))
                self.program.set_execution_finished(reason="normal", exit_code=0)
                message = str(e)
                await self._post_execute(call, False, message, langfuse_span)
                return (False, message)
            except Exception as e:
                message = f"Error: {str(e)}"
                await self._post_execute(call, False, message, langfuse_span)
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
                    success, result = await target_agent.execute_playbook(
                        actual_playbook_name, args, kwargs
                    )
                    await self._post_execute(call, success, result, langfuse_span)
                    return (success, result)

            # Try to execute playbook in other agents (fallback)
            for agent in self.other_agents:
                if (
                    playbook_name in agent.playbooks
                    and agent.playbooks[playbook_name].public
                ):
                    success, result = await agent.execute_playbook(
                        playbook_name, args, kwargs
                    )
                    await self._post_execute(call, success, result, langfuse_span)
                    return (success, result)

            # Playbook not found
            error_msg = f"Playbook '{playbook_name}' not found in agent '{self.klass}' or any registered agents"
            await self._post_execute(call, False, error_msg, langfuse_span)
            return (False, error_msg)

    async def _post_execute(
        self, call: PlaybookCall, success: bool, result: Any, langfuse_span: Any
    ) -> None:

        if "$__" in self.state.variables:
            execution_summary = self.state.variables.variables["$__"].value
        else:
            execution_summary = None

        # Check if result is already an Artifact object (before it gets modified)
        returned_artifact = None
        if success and isinstance(result, Artifact):
            returned_artifact = result

        artifact_result = False
        if success and len(str(result)) > config.artifact_result_threshold:
            # Create an artifact to store the result
            # Use user-specified variable name if provided, otherwise auto-generate
            if call.variable_to_assign:
                artifact_var_name = call.variable_to_assign
                artifact_var_name = (
                    artifact_var_name[1:]
                    if artifact_var_name.startswith("$")
                    else artifact_var_name
                )
            else:
                # Generate a hash of the content to use as the artifact name
                # This ensures stable artifact names across runs
                content_hash = hashlib.sha256(str(result).encode()).hexdigest()[:8]
                artifact_var_name = f"a_{content_hash}"

            artifact_summary = f"Output from {call.to_log_full()}"
            artifact_contents = str(result)

            # Create artifact and store in variables
            artifact = Artifact(
                name=f"${artifact_var_name}",
                summary=artifact_summary,
                value=artifact_contents,
            )
            # Store with $ prefix to follow variable naming convention
            self.state.variables[f"${artifact_var_name}"] = artifact
            artifact_result = True
            result = f"${artifact_var_name}"

        # Set $_ to capture the return value for next operation
        # If artifact was created, result is now the artifact var reference
        # Otherwise it's the plain result value
        if artifact_result:
            # result is now a string like "$a_uuid", retrieve the artifact
            if isinstance(self.state.variables[result], Artifact):
                artifact_obj = self.state.variables[result]
            elif isinstance(self.state.variables[result].value, Artifact):
                artifact_obj = self.state.variables[result].value
            else:
                raise ValueError(
                    f"Invalid artifact object: {self.state.variables[result]}"
                )
            # Store in $_ for chaining operations
            # Create with the $ prefix key to match dictionary key for proper filtering
            self.state.variables["$_"] = artifact_obj
            # Note: result stays as $a_... (the artifact variable reference)
        elif returned_artifact:
            # Playbook returned an artifact object directly
            self.state.variables["$_"] = returned_artifact
            artifact_var_name = returned_artifact.name
            result = f"Artifact: {artifact_var_name}"
        else:
            # Plain result value
            self.state.variables["$_"] = result

        call_result = PlaybookCallResult(call, result, execution_summary)
        self.state.session_log.append(call_result)

        self.state.call_stack.pop()

        if artifact_result:
            artifact_msg = ArtifactLLMMessage(artifact_obj)
            self.state.call_stack.add_llm_message(artifact_msg)
        elif returned_artifact:
            artifact_msg = ArtifactLLMMessage(returned_artifact)
            self.state.call_stack.add_llm_message(artifact_msg)

        result_msg = ExecutionResultLLMMessage(
            call_result.to_log_full(),
            playbook_name=call.playbook_klass,
            success=success,
        )
        self.state.call_stack.add_llm_message(result_msg)

        if artifact_result:
            langfuse_span.update(output=artifact_obj.value)
        else:
            langfuse_span.update(output=result)

    def __str__(self):
        if self.kwargs:
            kwargs_msg = ", ".join([f"{k}:{v}" for k, v in self.kwargs.items()])
            return f"{self.klass}(agent {self.id}, {kwargs_msg})"
        else:
            return f"{self.klass}(agent {self.id})"

    @property
    def name(self):
        if self.kwargs and "name" in self.kwargs:
            return self.kwargs["name"]
        else:
            return self.klass

    def __repr__(self):
        return f"{self.klass}(agent {self.id})"

    async def load_file(
        self, file_path: str, inline: bool = False, silent: bool = False
    ) -> str:
        with open(file_path, "r") as file:
            content = file.read()
        if inline:
            return content
        else:
            # Safely get the caller frame (second from top)
            if len(self.state.call_stack.frames) >= 2:
                caller_frame = self.state.call_stack.frames[-2]

                if silent:
                    file_msg = FileLoadLLMMessage(content, file_path=file_path)
                    caller_frame.add_llm_message(file_msg)
                    return ""
                else:
                    file_msg = FileLoadLLMMessage(
                        f"Contents of file {file_path}:\n\n{content}",
                        file_path=file_path,
                    )
                    caller_frame.add_llm_message(file_msg)

                    return f"Loaded file {file_path}"
            else:
                # Not enough frames in call stack, just return the content
                return f"Loaded file {file_path}"

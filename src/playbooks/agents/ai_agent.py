"""AI agent implementation for executing playbooks.

This module provides the AIAgent class and related metaclasses for AI-powered
agents that can execute various types of playbooks, handle LLM interactions,
and manage execution state.
"""

import copy
import hashlib
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from playbooks.compilation.expression_engine import (
    ExpressionContext,
    resolve_description_placeholders,
)
from playbooks.config import config
from playbooks.core.argument_types import LiteralValue, VariableReference
from playbooks.core.constants import EXECUTION_FINISHED, HUMAN_AGENT_KLASS
from playbooks.core.enums import StartupMode
from playbooks.core.events import (
    AgentTerminatedEvent,
    PlaybookEndEvent,
    PlaybookStartEvent,
)
from playbooks.core.exceptions import ExecutionFinished
from playbooks.core.identifiers import AgentID
from playbooks.core.message import MessageType
from playbooks.execution.agents_accessor import AgentsAccessor
from playbooks.execution.call import PlaybookCall, PlaybookCallResult
from playbooks.infrastructure.event_bus import EventBus
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.llm.messages import (
    ExecutionResultLLMMessage,
    FileLoadLLMMessage,
    MeetingLLMMessage,
)
from playbooks.llm.messages.types import (
    AgentInfoLLMMessage,
    ArtifactLLMMessage,
    OtherAgentInfoLLMMessage,
    SystemPromptLLMMessage,
    TriggerInstructionsLLMMessage,
)
from playbooks.meetings.meeting import JoinedMeeting, Meeting
from playbooks.playbook import LLMPlaybook, Playbook, PythonPlaybook, RemotePlaybook
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer
from playbooks.state.session_log import SessionLog
from playbooks.state.variables import Artifact, PlaybookBox, VariablesTracker
from playbooks.utils.misc import copy_func
from playbooks.utils.text_utils import indent, simple_shorten

from .base_agent import BaseAgent, BaseAgentMeta
from .namespace_manager import AgentNamespaceManager

if TYPE_CHECKING:
    from playbooks.program import Program


class AIAgentMeta(BaseAgentMeta):
    """Meta class for AIAgent.

    Handles validation of agent metadata and startup mode configuration
    during class creation.
    """

    def __new__(cls, name: str, bases: tuple, attrs: dict) -> type:
        """Create a new AIAgent class with metadata validation.

        Args:
            name: Class name
            bases: Base classes
            attrs: Class attributes

        Returns:
            New class with validated metadata
        """
        cls = super().__new__(cls, name, bases, attrs)
        cls.validate_metadata()
        return cls

    @property
    def startup_mode(self) -> StartupMode:
        """Get the startup mode for this agent."""
        return getattr(self, "metadata", {}).get("startup_mode", StartupMode.DEFAULT)

    def validate_metadata(self) -> None:
        """Validate the metadata for this agent.

        Raises:
            ValueError: If startup_mode is invalid
        """
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

        # Execution state attributes (flattened from ExecutionState)
        self.event_bus: EventBus = event_bus
        self.session_log: SessionLog = SessionLog(self.klass, self.id)
        self.call_stack: CallStack = CallStack(event_bus, self.id)

        self._initialized = False

        self.state: PlaybookBox = PlaybookBox()
        self.previous_variables: Optional[Dict[str, Any]] = None
        self.agents_list: List[str] = []
        self.last_llm_response: str = ""
        self.last_message_target: Optional[str] = None

        # Meetings
        self.owned_meetings: Dict[str, Meeting] = {}
        self.joined_meetings: Dict[str, JoinedMeeting] = {}

        # Initialize meeting manager with dependency injection (after state is created)
        # Import MeetingManager here to avoid circular import
        from playbooks.meetings.meeting_manager import MeetingManager

        self.meeting_manager = MeetingManager(
            agent_id=self.id,
            agent_klass=self.klass,
            agent=self,
            program=self.program,
            playbook_executor=self,
        )

        self.meeting_manager.ensure_meeting_playbook_kwargs(self.playbooks)
        self.source_line_number = source_line_number
        self.public_json = None

        # Track background tasks for cleanup
        # self._background_tasks = []

        # Create playbook to run BGN playbooks
        self.bgn_playbook_name = None
        self.create_begin_playbook()

    def _initialize_system_messages(self) -> None:
        """Initialize system messages that are always present in the call stack."""
        # Only add system messages for agents with playbooks (skip test/mock agents)
        if not self.playbooks:
            return

        # Add system prompt
        system_msg = SystemPromptLLMMessage()
        self.call_stack.top_level_llm_messages.append(system_msg)

        # Add agent information
        agent_info_msg = AgentInfoLLMMessage(self.get_compact_information())
        self.call_stack.top_level_llm_messages.append(agent_info_msg)

        # Add other agents information if available
        other_agents_info = self.other_agent_klasses_information()
        if other_agents_info:
            other_agents_msg = OtherAgentInfoLLMMessage("\n\n".join(other_agents_info))
            self.call_stack.top_level_llm_messages.append(other_agents_msg)

        # Add trigger instructions
        trigger_instructions = self.all_trigger_instructions()
        if trigger_instructions:
            trigger_instructions_content = [
                "*Available playbook triggers*",
                "```md",
                *trigger_instructions,
                "```",
            ]
            trigger_msg = TriggerInstructionsLLMMessage(
                "\n".join(trigger_instructions_content)
            )
            self.call_stack.top_level_llm_messages.append(trigger_msg)

    def deep_copy_playbooks(self, playbooks):
        """Deep copy the playbooks."""
        playbooks_copy = copy.deepcopy(playbooks)
        for playbook in playbooks_copy.values():
            if hasattr(playbook, "func") and playbook.func:
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
        self.namespace_manager.namespace["self"] = self
        self.namespace_manager.namespace["agent"] = (
            self  # Allow 'agent' as alias for 'self'
        )
        self.namespace_manager.namespace["agents"] = (
            self.all_agents  # Provide access to agents list
        )

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

        # Add agent classes for factory pattern access
        self._add_agent_classes_to_namespace()

    def _add_agent_classes_to_namespace(self):
        """Add AIAgent classes to namespace for factory method access.

        Adds all AIAgent classes (including self) to enable clean factory syntax:
        - agent = await AccountantExpert.get_or_create(requester=self)
        - all_agents = AccountantExpert.get_all(self.program)

        Only AIAgent classes are added, not HumanAgent classes.
        """
        if not self.program or not hasattr(self.program, "agent_klasses"):
            return

        # Add all AIAgent subclasses to namespace (including own class)
        for agent_klass_name, agent_class in self.program.agent_klasses.items():
            # Only add AIAgent subclasses, not HumanAgent
            if issubclass(agent_class, AIAgent):
                self.namespace_manager.namespace[agent_klass_name] = agent_class

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
        self.agents_list = [str(agent) for agent in self.program.agents]

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

        # Generate playbook calls - pass **kwargs to support CLI args
        playbook_calls = []
        for playbook in begin_playbooks.values():
            playbook_calls.append(f"        await {playbook.name}(**kwargs)")

        playbook_calls_str = chr(10).join(playbook_calls)
        if playbook_calls_str:
            playbook_calls_str = f"""
    try:
{playbook_calls_str}
    except Exception as e:
        agent.state._busy = False
        raise e
    """

        code_block = f"""
@playbook
async def {self.bgn_playbook_name}(**kwargs) -> None:
    # Main loop for agent "{self.klass}"
    # Auto-generated by Playbooks AI runtime
    # 
    # Calls any playbooks that should be executed when the program starts, followed by a loop that waits for messages and processes them.
    agent.state._busy = True
{playbook_calls_str}

    agent.state._busy = False
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

    async def initialize(self) -> None:
        """Initialize the agent.

        This method is called by the Program before begin().
        """
        if self._initialized:
            return

        await super().initialize()
        self._initialize_system_messages()
        self._initialized = True

    async def begin(self):
        # Pre-load initial artifacts if any
        if hasattr(self, "_initial_artifacts_to_load"):
            # Create a temporary frame to hold artifact messages before BGN starts
            # Actually, we need to load them in the BGN frame, so store for _pre_execute
            self._artifacts_to_preload = []
            for artifact_name in self._initial_artifacts_to_load:
                if hasattr(self.state, artifact_name):
                    artifact_var = getattr(self.state, artifact_name)
                    if isinstance(artifact_var, Artifact):
                        self._artifacts_to_preload.append(artifact_var)

        # Pass CLI args to BGN playbook if available
        cli_args = getattr(self.program, "cli_args", {}) if self.program else {}
        success, result = await self.execute_playbook(
            self.bgn_playbook_name, kwargs=cli_args
        )

        # Publish agent terminated event for telemetry
        self.event_bus.publish(
            AgentTerminatedEvent(
                session_id=self.program.event_bus.session_id if self.program else "",
                agent_id=self.id,
                agent_klass=self.klass,
            )
        )

        return

    async def cleanup(self):
        """Cancel all background tasks and clean up resources."""
        # Only cleanup if execution is truly finished
        if not (self.program and self.program.execution_finished):
            return

        # Clean up meeting manager background tasks
        if hasattr(self, "meeting_manager") and self.meeting_manager:
            await self.meeting_manager.cleanup()
            # Also clean up the message collector
            if (
                hasattr(self.meeting_manager, "message_collector")
                and self.meeting_manager.message_collector
            ):
                await self.meeting_manager.message_collector.cleanup()

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
        steps = getattr(playbook, "steps", None) if playbook else None
        if playbook and step_number[0] not in ["T", "N"] and steps:
            line = steps.get_step(step_number)
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

            namespace = self.klass if with_namespace else "self"
            playbook_instructions = playbook.trigger_instructions(namespace, skip_bgn)
            instructions.extend(playbook_instructions)
        return instructions

    def all_trigger_instructions(self) -> List[str]:
        """Get all trigger instructions including from other agents.

        Only includes public triggers from other agents since private playbooks
        cannot be called cross-agent. Deduplicates triggers from multiple instances
        of the same agent class.

        Returns:
            List of all trigger instruction strings
        """
        instructions = self.trigger_instructions(with_namespace=False)
        seen = set(instructions)

        for agent in self.other_agents:
            # Only include public triggers from other agents
            agent_instructions = agent.trigger_instructions(
                with_namespace=True, public_only=True
            )
            for instr in agent_instructions:
                if instr not in seen:
                    instructions.append(instr)
                    seen.add(instr)

        return instructions

    @classmethod
    def get_compact_information(cls, public_only: bool = False) -> str:
        info_parts = []
        info_parts.append(f"class {cls.klass}:")
        if cls.description:
            if public_only:
                description_first_paragraph = cls.description.split("\n\n")[0]
                description_first_paragraph = f'"""{description_first_paragraph}"""'
                info_parts.append(indent(description_first_paragraph, indent_size=2))
            else:
                description = f'"""{cls.description}"""'
                info_parts.append(indent(description, indent_size=2))

        if cls.playbooks:
            for playbook in cls.playbooks.values():
                if not playbook.hidden and (not public_only or playbook.public):
                    info_parts.append(indent("@playbook", indent_size=2))
                    info_parts.append(
                        indent(f"async def {playbook.signature}:", indent_size=2)
                    )
                    if playbook.description:
                        info_parts.append(
                            indent('"""', indent_size=4)
                            + indent(
                                simple_shorten(playbook.description, width=200),
                                indent_size=4,
                            )
                            + indent('"""', indent_size=4)
                        )
                    info_parts.append(indent("pass", indent_size=4))
                    info_parts.append("")

        return "\n".join(info_parts)

    @classmethod
    def get_public_information(cls) -> str:
        """Get public information about an agent klass

        Returns:
            String containing public agent information
        """
        return cls.get_compact_information(public_only=True)

    def other_agent_klasses_information(self) -> List[str]:
        """Get information about other registered agents.

        Returns:
            List of information strings for other agents
        """
        if not self.program or not hasattr(self.program, "agent_klasses"):
            return []

        return [
            agent_klass.get_public_information()
            for agent_klass in self.program.agent_klasses.values()
            if agent_klass.klass != self.klass
            and hasattr(agent_klass, "get_public_information")  # Skip human agents
        ]

    def resolve_target(
        self, target: Optional[str] = None, allow_fallback: bool = True
    ) -> Optional[str]:
        """Resolve a target specification to an agent ID or meeting spec.

        Args:
            target: Target specification (agent ID, agent type, "human", "meeting", etc.)
            allow_fallback: Whether to use fallback logic when target is None or not found

        Returns:
            Resolved target identifier (agent ID or meeting spec), or None if not found
        """
        if target is not None:
            target = target.strip()

            # Try explicit target resolution
            resolved = self._resolve_explicit_target(target)
            if resolved is not None:
                return resolved

            # Target not found - fallback to human if allowed
            return "human" if allow_fallback else None

        # No target specified - use context-based fallback
        return self._resolve_fallback_target() if allow_fallback else None

    def _resolve_explicit_target(self, target: str) -> Optional[str]:
        """Resolve an explicitly specified target.

        Args:
            target: Target specification string

        Returns:
            Resolved target identifier, or None if not found
        """
        # Human aliases
        if target.lower() in ["human", "user"]:
            return "human"

        # Meeting targets
        if target == "meeting":
            if meeting := self.get_current_meeting():
                return f"meeting {meeting.id}"
            return None

        if target.startswith("meeting "):
            return target

        # Agent ID formats (structured or raw)
        if target.startswith("agent "):
            return AgentID.parse(target).id

        if target.isdigit():
            return target

        # Special context targets
        if target == "last_non_human_agent":
            if self.last_message_target and self.last_message_target != "human":
                return self.last_message_target
            return None

        # Agent by class name
        return self._find_agent_by_klass(target)

    def _find_agent_by_klass(self, klass: str) -> Optional[str]:
        """Find first agent matching the given class name.

        Args:
            klass: Agent class name to search for

        Returns:
            Agent ID if found, None otherwise
        """
        # Search other agents for matching class
        for agent in self.other_agents:
            if agent.klass == klass:
                return agent.id

        # Check if target is the human agent class
        if klass == HUMAN_AGENT_KLASS:
            return "human"

        return None

    def _resolve_fallback_target(self) -> str:
        """Resolve target using context-based fallback logic.

        Fallback order:
        1. Current meeting context (if in a meeting)
        2. Last 1:1 message target (conversation continuity)
        3. Human (default)

        Returns:
            Fallback target identifier
        """
        # Current meeting context
        if meeting := self.get_current_meeting():
            return f"meeting {meeting.id}"

        # Last 1:1 conversation target
        if self.last_message_target:
            return self.last_message_target

        # Default to human
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
        """Build the input log string for telemetry.

        Args:
            playbook: The playbook being executed
            call: The playbook call information

        Returns:
            A string containing the input log data
        """
        log_parts = []
        log_parts.append(str(self.call_stack))
        log_parts.append(str(self.state))
        log_parts.append("Session log: \n" + str(self.session_log))

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
    ) -> tuple[Optional[Playbook], PlaybookCall, Optional[Any]]:
        """Prepare for playbook execution by setting up call stack frame and tracing metadata."""
        call = PlaybookCall(playbook_name, args, kwargs)
        playbook = self.playbooks.get(playbook_name)

        # Build proper trace name
        trace_str = str(self) + "." + call.to_log_full()

        if playbook:
            if isinstance(playbook, LLMPlaybook):
                trace_str = f"Markdown: {trace_str}"
            elif isinstance(playbook, PythonPlaybook):
                trace_str = f"Python: {trace_str}"
            elif isinstance(playbook, RemotePlaybook):
                trace_str = f"Remote: {trace_str}"
        else:
            trace_str = f"External: {trace_str}"

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
        meeting = self.get_current_meeting()
        if meeting:
            is_meeting = True
            meeting_id = meeting.id
        elif "meeting_id" in kwargs:
            # Even if not a meeting playbook, if meeting_id is in kwargs (e.g., AcceptAndJoinMeeting),
            # mark as meeting context so get_current_meeting_from_call_stack() can find it
            is_meeting = True
            meeting_id = kwargs.get("meeting_id")
        elif playbook and playbook.meeting:
            # If the playbook itself is a meeting playbook, mark as meeting context
            is_meeting = True
            # meeting_id will remain None for now - it will be set when the meeting is actually created

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
            is_meeting=is_meeting,
            meeting_id=meeting_id,
        )
        self.call_stack.push(call_stack_frame)
        self.session_log.append(call)

        self.state.__ = None

        # Pre-load initial artifacts if this is the first playbook execution
        if hasattr(self, "_artifacts_to_preload") and self._artifacts_to_preload:
            for artifact in self._artifacts_to_preload:
                artifact_msg = ArtifactLLMMessage(artifact)
                call_stack_frame.add_llm_message(artifact_msg)
            # Clear so we don't re-add on subsequent playbooks
            self._artifacts_to_preload = []

        return playbook, call

    def _is_external_playbook(self, playbook_name: str, playbook: Any) -> bool:
        """Determine if playbook is external (cross-agent communication).

        External playbooks include:
        - Say (all targets: user, agent, meeting)
        - SendMessage (always cross-agent)
        - RemotePlaybook (MCP tools)
        - Cross-agent calls (OtherAgent.PlaybookName)
        """
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

    def _resolve_target_agent(
        self, playbook_name: str
    ) -> tuple[Optional["AIAgent"], Optional[str]]:
        """Resolve the target agent for a cross-agent playbook call.

        Supports two formats:
        - AgentName.PlaybookName: Targets first instance of AgentName
        - AgentName:AgentId.PlaybookName: Targets specific instance with AgentId
          (AgentId can be "agent 1020" or just "1020")

        Args:
            playbook_name: The full playbook name (may include agent prefix)

        Returns:
            Tuple of (target_agent, actual_playbook_name) or (None, None) if not found
        """
        if not self.program or "." not in playbook_name:
            return (None, None)

        # Check if targeting a specific agent instance (AgentName:AgentId.PlaybookName)
        if ":" in playbook_name:
            agent_part, actual_playbook_name = playbook_name.split(".", 1)
            agent_name, agent_id_spec = agent_part.split(":", 1)

            # Parse agent ID to handle both "agent 1020" and "1020" formats
            try:
                agent_id_obj = AgentID.parse(agent_id_spec)
                normalized_agent_id = agent_id_obj.id  # Just the numeric part
            except ValueError:
                # If parsing fails, use as-is
                normalized_agent_id = agent_id_spec

            # Filter by both agent class and instance ID
            target_agents = list(
                filter(
                    lambda x: x.klass == agent_name and x.id == normalized_agent_id,
                    self.program.agents,
                )
            )
            target_agent = target_agents[0] if target_agents else None
        else:
            # Original format: AgentName.PlaybookName (targets first instance)
            agent_name, actual_playbook_name = playbook_name.split(".", 1)
            target_agents = list(
                filter(lambda x: x.klass == agent_name, self.program.agents)
            )
            target_agent = target_agents[0] if target_agents else None

        return (target_agent, actual_playbook_name)

    async def execute_playbook(
        self, playbook_name: str, args: List[Any] = [], kwargs: Dict[str, Any] = {}
    ) -> tuple[bool, Any]:
        """Execute a playbook in this agent.

        Creates a traced span for observability, capturing inputs, outputs, and errors.
        Supports local playbooks, remote playbooks, and cross-agent calls.

        Returns:
            Tuple of (success: bool, result: Any)
        """
        # Ensure agent is initialized before execution to populate system messages.
        # This acts as a safety net for agents that failed initial discovery or
        # were created after program initialization.
        await self.initialize()

        if self.program and self.program.execution_finished:
            return (True, EXECUTION_FINISHED)

        playbook, call = await self._pre_execute(playbook_name, args, kwargs)

        # Type-based argument resolution
        # Use call.args and call.kwargs which contain typed arguments from _pre_execute
        args = call.args if hasattr(call, "args") else args
        kwargs = call.kwargs if hasattr(call, "kwargs") else kwargs

        # Ensure args is a list (not tuple) so we can modify it
        args = list(args) if not isinstance(args, list) else args

        context = ExpressionContext(agent=self, call=call)

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
            # Handle meeting playbook initialization
            if playbook and playbook.meeting:
                debug(
                    f"{str(self)}: Handling meeting playbook execution: {playbook_name}"
                )

                # Check if we're joining an existing meeting (meeting_id in kwargs)
                existing_meeting_id = kwargs.get("meeting_id")

                if (
                    existing_meeting_id
                    and existing_meeting_id not in self.joined_meetings
                ):
                    # We're joining an existing meeting - accept the invitation first
                    inviter_id = AgentID.parse(kwargs.get("inviter_id")).id
                    topic = kwargs.get("topic", "Meeting")

                    debug(
                        f"{str(self)}: Auto-accepting meeting invitation {existing_meeting_id}"
                    )
                    await self.meeting_manager._accept_meeting_invitation(
                        existing_meeting_id, inviter_id, topic, playbook_name
                    )
                    # No need to wait for attendees - we're joining, not creating

                elif (
                    existing_meeting_id and existing_meeting_id in self.joined_meetings
                ):
                    # We've already joined this meeting, just proceed with execution
                    debug(
                        f"{str(self)}: Already in meeting {existing_meeting_id}, proceeding with execution"
                    )

                elif (
                    not existing_meeting_id
                    and not self.meeting_manager.get_current_meeting_from_call_stack()
                ):
                    # We're creating a new meeting (no meeting_id provided and not in a meeting context)
                    debug(
                        f"{str(self)}: Creating new meeting for playbook {playbook_name}"
                    )
                    meeting = await self.meeting_manager.create_meeting(
                        self.playbooks[playbook_name], kwargs
                    )

                    if self.program and self.program.execution_finished:
                        return EXECUTION_FINISHED

                    # Wait for required attendees to join before proceeding (if any besides requester)
                    await self.meeting_manager._wait_for_required_attendees(meeting)

                    message = f"Meeting {meeting.id} ready to proceed - all required attendees present"
                    self.session_log.append(message)

                    meeting_msg = MeetingLLMMessage(message, meeting_id=meeting.id)
                    self.call_stack.add_llm_message(meeting_msg)

                    # Add meeting_id and topic to kwargs so the owner's meeting playbook has context
                    kwargs["meeting_id"] = meeting.id
                    kwargs["topic"] = meeting.topic
        except TimeoutError as e:
            error_msg = f"Meeting initialization failed: {str(e)}"
            await self._post_execute(call, False, error_msg)
            return (False, error_msg)
        except ValueError as e:
            # Treat meeting attendee rejection (and other meeting init validation errors)
            # as a normal playbook failure rather than crashing streaming execution.
            error_msg = f"Meeting initialization failed: {str(e)}"
            await self._post_execute(call, False, error_msg)
            return (False, error_msg)

        # Execute local playbook in this agent
        if playbook:
            try:
                if self.program and self.program.execution_finished:
                    return (False, EXECUTION_FINISHED)

                # Publish playbook start event for telemetry (only for Python playbooks)
                # LLM/markdown playbooks publish their own events from PlaybookLLMExecution
                # Built-in playbooks (Say, CreateAgent, etc.) are skipped since they're thin wrappers
                is_python_playbook = isinstance(playbook, PythonPlaybook)
                builtin_playbooks = {
                    "Say",
                    "CreateAgent",
                    "LoadArtifact",
                    "SaveArtifact",
                    "SendMessage",
                    "WaitForMessage",
                    "Loadfile",
                }
                is_builtin = playbook.name in builtin_playbooks

                if is_python_playbook and not is_builtin:
                    self.event_bus.publish(
                        PlaybookStartEvent(
                            session_id=(
                                self.program.event_bus.session_id
                                if self.program
                                else ""
                            ),
                            agent_id=self.id,
                            playbook=playbook.name,
                        )
                    )

                result = await playbook.execute(*args, **kwargs)

                # Publish playbook end event for telemetry (only for Python playbooks, excluding built-ins)
                if is_python_playbook and not is_builtin:
                    self.event_bus.publish(
                        PlaybookEndEvent(
                            session_id=(
                                self.program.event_bus.session_id
                                if self.program
                                else ""
                            ),
                            agent_id=self.id,
                            playbook=playbook.name,
                            return_value=result,
                            call_stack_depth=len(self.call_stack.frames),
                        )
                    )

                success, result = await self._post_execute(call, True, result)
                # End-of-meeting signal: when the meeting owner finishes the meeting playbook,
                # notify participants so any waiting Yld("meeting ...") can unblock and exit.
                if getattr(playbook, "meeting", False):
                    meeting_id = kwargs.get("meeting_id")
                    if (
                        meeting_id
                        and hasattr(self, "owned_meetings")
                        and meeting_id in self.owned_meetings
                    ):
                        await self.program.route_message(
                            sender_id=self.id,
                            sender_klass=self.klass,
                            receiver_spec=f"meeting {meeting_id}",
                            message=f"MEETING_ENDED {meeting_id}",
                            message_type=MessageType.MEETING_BROADCAST,
                            meeting_id=meeting_id,
                        )
                return (success, result)
            except ExecutionFinished as e:
                debug("Execution finished, exiting", agent=str(self))
                self.state._busy = False
                await self.program.set_execution_finished(reason="normal", exit_code=0)
                message = str(e)
                await self._post_execute(call, False, message)
                return (False, message)
            except Exception as e:
                message = f"Error: {str(e)}"
                await self._post_execute(call, False, message)
                raise
        else:
            # Handle cross-agent playbook calls (AgentName.PlaybookName or AgentName:AgentId.PlaybookName format)
            target_agent, actual_playbook_name = self._resolve_target_agent(
                playbook_name
            )

            if (
                target_agent
                and actual_playbook_name
                and actual_playbook_name in target_agent.playbooks
                and target_agent.playbooks[actual_playbook_name].public
            ):
                success, result = await target_agent.execute_playbook(
                    actual_playbook_name, args, kwargs
                )
                await self._post_execute(call, success, result)
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
                    await self._post_execute(call, success, result)
                    return (success, result)

            # Playbook not found
            error_msg = f"Playbook '{playbook_name}' not found in agent '{self.klass}' or any registered agents"
            await self._post_execute(call, False, error_msg)
            return (False, error_msg)

    async def _post_execute(
        self,
        call: PlaybookCall,
        success: bool,
        result: Any,
    ) -> tuple[bool, Any]:
        """Handle post-execution tasks: artifact creation, call stack management, and session logging."""

        # Note: __ (double underscore) cannot use attribute access in Box
        # due to Python's dunder name handling, so we use bracket notation
        if "__" in self.state:
            execution_summary = self.state["__"]
            # Convert to string if it's an Artifact to ensure it can be used in string operations
            if isinstance(execution_summary, Artifact):
                execution_summary = str(execution_summary)
        else:
            execution_summary = None

        # Check if result is already an Artifact object (before it gets modified)
        returned_artifact = None
        if success and isinstance(result, Artifact):
            returned_artifact = result

        artifact_result = False
        # Skip artifact conversion for hidden builtin playbooks that return structured data
        # (like WaitForMessage which returns List[Message])
        skip_artifact_conversion = call.playbook_klass in ["WaitForMessage"]

        if (
            success
            and not skip_artifact_conversion
            and len(str(result)) > config.artifact_result_threshold
        ):
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
                name=artifact_var_name,
                summary=artifact_summary,
                value=artifact_contents,
            )
            # Store artifact in variables
            setattr(self.state, artifact_var_name, artifact)
            artifact_result = True
            result = artifact_var_name

        # Set $_ to capture the return value for next operation
        # If artifact was created, result is now the artifact var reference
        # Otherwise it's the plain result value
        if artifact_result:
            # result is now the artifact name, retrieve it
            artifact_obj = getattr(self.state, result)
            if not isinstance(artifact_obj, Artifact):
                raise ValueError(f"Invalid artifact object: {artifact_obj}")
            # Store in _ for chaining operations
            self.state._ = artifact_obj
        elif returned_artifact:
            # Playbook returned an artifact object directly
            self.state._ = returned_artifact
            artifact_var_name = returned_artifact.name
            result = f"Artifact: {artifact_var_name}"
        else:
            # Plain result value
            self.state._ = result

        call_result = PlaybookCallResult(call, result, execution_summary)
        self.session_log.append(call_result)

        self.call_stack.pop()

        if artifact_result:
            artifact_msg = ArtifactLLMMessage(artifact_obj)
            self.call_stack.add_llm_message(artifact_msg)
        elif returned_artifact:
            artifact_msg = ArtifactLLMMessage(returned_artifact)
            self.call_stack.add_llm_message(artifact_msg)

        if call.playbook_klass not in ["WaitForMessage"]:
            content = call_result.to_log_full()
            # Only add message if content is not empty (Say/SaveArtifact return empty string)
            if content:
                result_msg = ExecutionResultLLMMessage(
                    content,
                    playbook_name=call.playbook_klass,
                    success=success,
                )
                self.call_stack.add_llm_message(result_msg)

        return success, (artifact_obj if artifact_result else result)

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
            if len(self.call_stack.frames) >= 2:
                caller_frame = self.call_stack.frames[-2]

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

    def load_artifact(self, artifact_name: str):
        if not hasattr(self.state, artifact_name):
            raise ValueError(f"Artifact {artifact_name} not found")

        artifact = getattr(self.state, artifact_name)
        if not isinstance(artifact, Artifact):
            raise ValueError(f"{artifact_name} is not an artifact")

        if not self.call_stack.is_artifact_loaded(artifact_name):
            artifact_msg = ArtifactLLMMessage(artifact)
            self.call_stack.add_llm_message_on_parent(artifact_msg)
            return f"Artifact {artifact_name} is now loaded"
        else:
            return f"Artifact {artifact_name} is already loaded"

    async def message_processing_event_loop(self):
        """Main message processing loop for agents. Waits for messages and delegates all processing to ProcessMessages."""
        while True:
            if self.program and self.program.execution_finished:
                break

            self.state._busy = False

            # Wait for messages
            messages = await self.WaitForMessage("*")

            if not messages:
                continue

            self.state._busy = True

            # Delegate all message processing to ProcessMessages LLM playbook
            # This includes trigger matching, meeting invitations, and natural language handling
            await self.execute_playbook("ProcessMessages", [messages])

    # Execution logging methods (used by LLM-generated code)

    @property
    def _current_executor(self):
        """Get the current executor from the top call stack frame.

        The executor is stored in the call stack frame and automatically
        handles nested execution contexts - when a frame is popped, the
        previous frame's executor becomes current.

        Returns:
            The executor associated with the current call stack frame.

        Raises:
            RuntimeError: If called outside of code execution context
                (no frame on stack or frame has no executor).
        """
        current_frame = self.call_stack.peek()
        if (
            not current_frame
            or not hasattr(current_frame, "executor")
            or current_frame.executor is None
        ):
            raise RuntimeError("Called outside of code execution context")
        return current_frame.executor

    async def Step(self, location: str) -> None:
        """Log step execution for tracking and debugging.

        Args:
            location: Step location (e.g., "Welcome:01:QUE")
        """
        await self._current_executor.capture_step(location)

    async def Yield(self, target: str = "user") -> None:
        """Yield execution control back to framework.

        Args:
            target: Yield target ("user", "call", "agent <id>", "meeting <id>", "exit")
        """
        return await self._current_executor.capture_yld(target)

    async def Return(self, value: Any) -> None:
        """Return value from playbook and set self.state._ for use in caller.

        Args:
            value: The value to return from the playbook
        """
        await self._current_executor.capture_return(value)

    async def SaveArtifact(self, name: str, summary: str, content: str) -> None:
        """Create and save artifact with summary and full content.

        Args:
            name: Artifact variable name
            summary: Short summary of the artifact
            content: Full artifact content
        """
        await self._current_executor.capture_artifact(name, summary, content)

    async def LogTrigger(self, code: str) -> None:
        """Log trigger execution.

        Args:
            code: Trigger code to execute
        """
        await self._current_executor.capture_trigger(code)

    @classmethod
    async def get_or_create(cls, *, requester, **create_kwargs):
        """Get an available agent of this type or create a new one.

        Automatically finds an idle agent or creates a new instance.
        Supports load balancing and allows same-type creation.

        Args:
            requester: The agent requesting the instance (keyword-only)
            **create_kwargs: Arguments to pass to agent creation

        Returns:
            Agent instance of this class type

        Example:
            accountant = await AccountantExpert.get_or_create(requester=self)
        """
        return await requester.program.get_or_create_agent(
            agent_klass=cls.klass, **create_kwargs
        )

    @classmethod
    def get_all(cls, program):
        """Get all agents of this type.

        Args:
            program: The program instance

        Returns:
            List of all agent instances of this class type

        Example:
            all_accountants = AccountantExpert.get_all(self.program)
        """
        return program.agents_by_klass.get(cls.klass, [])

    @property
    def all_agents(self) -> AgentsAccessor:
        """Access to all agents in the program."""
        return AgentsAccessor(self.program)

    @property
    def agents(self):
        """Alias for agents_list."""
        return self.agents_list

    @agents.setter
    def agents(self, value):
        """Setter for agents_list."""
        self.agents_list = value

    def get_current_meeting(self) -> Optional[Union[Meeting, JoinedMeeting]]:
        """Get the current meeting object from top meeting playbook in call stack.

        Returns:
            Meeting or JoinedMeeting object if currently in a meeting, None otherwise
        """
        for frame in reversed(self.call_stack.frames):
            if frame.is_meeting and frame.meeting_id:
                meeting_id = frame.meeting_id
                # Check owned meetings first
                if meeting_id in self.owned_meetings:
                    return self.owned_meetings[meeting_id]
                # Check joined meetings
                if meeting_id in self.joined_meetings:
                    return self.joined_meetings[meeting_id]

                raise RuntimeError(
                    f"Meeting {meeting_id} is not an owned or joined meeting in agent {self.id}"
                )
        return None

    @property
    def current_meeting(self) -> Optional[Union[Meeting, JoinedMeeting]]:
        """Get the current meeting object (Meeting or JoinedMeeting).

        Returns:
            Meeting or JoinedMeeting object if currently in a meeting, None otherwise
        """
        return self.get_current_meeting()

    @property
    def active_meetings(self) -> List[Union[Meeting, JoinedMeeting]]:
        """Get all active meetings (owned and joined).

        Returns:
            List of all Meeting and JoinedMeeting objects this agent is part of
        """
        meetings = []
        meetings.extend(self.owned_meetings.values())
        meetings.extend(self.joined_meetings.values())
        return meetings

    def snapshot_variables(self) -> None:
        """Snapshot current variables for diff computation."""
        self.previous_variables = VariablesTracker.snapshot(self.state)

    def publish_variable_changes(self) -> None:
        """Publish events for any variable changes since last snapshot."""
        VariablesTracker.publish_changes(
            self.event_bus, self.id, self.state, self.previous_variables
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the execution state.

        Returns:
            Dictionary containing call stack, variables, agents, and meetings
        """
        # Owned meetings
        owned_meetings_list = []
        joined_meetings_list = []

        for meeting_id, meeting in self.owned_meetings.items():
            participants_list = []
            for participant in meeting.joined_attendees:
                participants_list.append(f"{participant.klass}(agent {participant.id})")
            owned_meetings_list.append(
                {
                    "meeting_id": meeting_id,
                    "participants": participants_list,
                    "topic": meeting.topic,
                }
            )
            joined_meetings_list.append(
                {
                    "meeting_id": meeting_id,
                    "owner": f"Owned by me - agent {meeting.owner_id}",
                    "topic": meeting.topic,
                }
            )

        # Joined meetings
        for meeting_id, meeting in self.joined_meetings.items():
            joined_meetings_list.append(
                {
                    "meeting_id": meeting_id,
                    "owner": f"agent {meeting.owner_id}",
                    "topic": meeting.topic,
                }
            )

        return {
            "call_stack": [
                frame.instruction_pointer.to_compact_str()
                for frame in self.call_stack.frames
            ],
            "variables": VariablesTracker.to_dict(self.state),
            "agents": self.agents_list.copy() if self.agents_list else [],
            "owned_meetings": owned_meetings_list,
            "joined_meetings": joined_meetings_list,
        }

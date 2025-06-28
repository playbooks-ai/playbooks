import asyncio
import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from ..call_stack import CallStackFrame, InstructionPointer
from ..enums import LLMMessageRole
from ..event_bus import EventBus
from ..execution_state import ExecutionState
from ..meetings import MeetingManager
from ..playbook import MarkdownPlaybook, Playbook, PythonPlaybook, RemotePlaybook
from ..playbook_call import PlaybookCall, PlaybookCallResult
from ..utils.langfuse_helper import LangfuseHelper
from ..utils.parse_utils import parse_metadata_and_description
from ..utils.spec_utils import SpecUtils
from .base_agent import BaseAgent

if TYPE_CHECKING:
    from ..program import Program

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
    """

    def __init__(
        self,
        event_bus: EventBus,
        source_line_number: int = None,
        agent_id: str = None,
        program: "Program" = None,
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
        self.klass = self.__class__.klass
        self.description = self.__class__.description

        super().__init__(self.klass, agent_id)

        # Initialize meeting manager
        self.meeting_manager = MeetingManager(self.id, self.klass)

        self.playbooks: Dict[str, Playbook] = (self.__class__.playbooks or {}).copy()
        self.meeting_manager.ensure_meeting_playbook_kwargs(self.playbooks)

        self.metadata, self.description = parse_metadata_and_description(
            self.description
        )
        self.state = ExecutionState(event_bus)
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
            if target == "Human":
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

    def resolve_say_target(self, target: str = None) -> str:
        """Resolve the target for a Say() call using fallback logic."""
        return self.resolve_target(target, allow_fallback=True)

    def get_meeting_playbooks(self) -> List[str]:
        """Get list of meeting playbook names."""
        return self.meeting_manager.get_meeting_playbooks(self.playbooks)

    def is_meeting_playbook(self, playbook_name: str) -> bool:
        """Check if a playbook is a meeting playbook."""
        return self.meeting_manager.is_meeting_playbook(playbook_name, self.playbooks)

    def get_playbook_attendees(self, playbook_name: str) -> Tuple[List[str], List[str]]:
        """Get required and optional attendees for a meeting playbook."""
        return self.meeting_manager.get_playbook_attendees(
            playbook_name, self.playbooks
        )

    async def _inject_meeting_parameters(
        self, playbook_name: str, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Auto-inject meeting_id parameter for meeting playbooks."""
        return self.meeting_manager.inject_meeting_parameters(
            playbook_name, kwargs, self.state.call_stack
        )

    async def create_meeting(
        self,
        invited_agents: List[str],
        topic: Optional[str] = None,
    ) -> str:
        """Create meeting and send invitations."""
        meeting_id = await self.meeting_manager.create_meeting(
            invited_agents, topic, self.program.meeting_id_registry
        )

        # Copy meeting to execution state for backward compatibility
        meeting = self.meeting_manager.get_meeting(meeting_id)
        if meeting:
            self.state.owned_meetings[meeting_id] = meeting

        # Send invitations
        for agent_spec in invited_agents:
            await self._send_invitation(meeting_id, agent_spec)

        return meeting_id

    async def _send_invitation(self, meeting_id: str, agent_spec: str):
        """Send invitation to an agent using the message system.

        Args:
            meeting_id: ID of the meeting
            agent_spec: Agent type or ID to invite
        """
        meeting = self.state.owned_meetings[meeting_id]

        # Track pending invitation on the meeting
        meeting.pending_invitations.add(agent_spec)

        # Send structured invitation message
        invitation_content = f"You are invited to join meeting {meeting_id}: {meeting.topic or 'Meeting'}"

        # Resolve agent spec to proper agent ID
        resolved_target = self.resolve_target(agent_spec, allow_fallback=False)
        if resolved_target:
            await self.program.route_message(
                self.id,
                resolved_target,
                invitation_content,
                message_type="meeting_invite",
                meeting_id=meeting_id,
            )
        else:
            self.state.session_log.append(
                f"Could not resolve invitation target: {agent_spec}"
            )

    async def _initialize_meeting_playbook(
        self, playbook_name: str, kwargs: Dict[str, Any]
    ):
        """Initialize meeting before executing meeting playbook.

        This method is called implicitly before any meeting playbook executes.
        For new meetings, it creates the meeting, sends invitations, and waits for required participants.
        For existing meetings (when meeting_id is provided), it joins the existing meeting.

        Args:
            playbook_name: Name of the meeting playbook being executed
            kwargs: Keyword arguments passed to the playbook (may contain attendees, topic, meeting_id)
        """
        # Check if we're joining an existing meeting (meeting_id provided) or creating a new one
        existing_meeting_id = kwargs.get("meeting_id")

        if existing_meeting_id:
            # Joining an existing meeting - just proceed with execution
            # The meeting system will handle participant management via messages
            self.state.session_log.append(
                f"Joining existing meeting {existing_meeting_id} for playbook {playbook_name}"
            )
            return  # No need to create meeting or wait for attendees

        # Creating a new meeting (original logic)
        # Extract attendees and topic from kwargs if provided
        kwargs_attendees = kwargs.get("attendees", [])
        topic = kwargs.get("topic", f"{playbook_name} meeting")

        # Determine attendee strategy: kwargs attendees take precedence
        if kwargs_attendees:
            # If attendees specified in kwargs, treat them as required (ignore metadata)
            required_attendees = kwargs_attendees
            all_attendees = kwargs_attendees
            self.state.session_log.append(
                f"Using kwargs attendees as required for meeting {playbook_name}: {required_attendees}"
            )
        else:
            # If no kwargs attendees, use metadata-defined attendees
            metadata_required, metadata_optional = self.get_playbook_attendees(
                playbook_name
            )
            required_attendees = metadata_required
            all_attendees = list(set(metadata_required + metadata_optional))
            self.state.session_log.append(
                f"Using metadata attendees for meeting {playbook_name}: required={metadata_required}, optional={metadata_optional}"
            )

        # Filter out the requester from required attendees (they're already present)
        required_attendees_to_wait_for = [
            attendee
            for attendee in required_attendees
            if attendee != self.klass
            and attendee != self.id  # Remove both requester's type and ID
        ]

        # Create the meeting
        meeting_id = await self.create_meeting(
            invited_agents=all_attendees, topic=topic
        )

        # Store meeting_id in kwargs for the playbook to access
        kwargs["meeting_id"] = meeting_id

        # Log the meeting initialization
        self.state.session_log.append(
            f"Initialized meeting {meeting_id} for playbook {playbook_name}"
        )

        # Wait for required attendees to join before proceeding (if any besides requester)
        await self._wait_for_required_attendees(
            meeting_id, required_attendees_to_wait_for
        )

        self.state.session_log.append(
            f"Meeting {meeting_id} ready to proceed - all required attendees present"
        )

        return meeting_id

    async def _wait_for_required_attendees(
        self, meeting_id: str, required_attendees: List[str], timeout_seconds: int = 30
    ):
        """Wait for required attendees to join the meeting before proceeding.

        Args:
            meeting_id: ID of the meeting to wait for
            required_attendees: List of required attendee types/names (excluding requester)
            timeout_seconds: Maximum time to wait for attendees

        Raises:
            TimeoutError: If required attendees don't join within timeout
            ValueError: If required attendee rejects the invitation
        """
        # If no attendees to wait for, proceed immediately
        if not required_attendees:
            self.state.session_log.append(
                f"No required attendees to wait for in meeting {meeting_id} - proceeding immediately"
            )
            return

        self.state.session_log.append(
            f"Waiting for required attendees to join meeting {meeting_id}: {required_attendees}"
        )

        # Track which required attendees have joined
        joined_attendees: Set[str] = set()
        start_time = asyncio.get_event_loop().time()

        while len(joined_attendees) < len(required_attendees):
            # Check for timeout
            if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                missing_attendees = set(required_attendees) - joined_attendees
                raise TimeoutError(
                    f"Timeout waiting for required attendees to join meeting {meeting_id}. "
                    f"Missing: {list(missing_attendees)}"
                )

            # Meeting responses are handled automatically by the centralized processor
            # Just wait a brief moment to allow message processing to occur
            await asyncio.sleep(0.1)
            processed_any_messages = True  # Assume processing happened

            # Check current meeting participants (after processing messages)
            if meeting_id in self.state.owned_meetings:
                meeting = self.state.owned_meetings[meeting_id]

                # Check which required attendees have joined
                for attendee in required_attendees:
                    if attendee not in joined_attendees:
                        # Check if attendee is an agent ID (e.g., "agent 1002" or starts with "agent ")
                        if SpecUtils.is_agent_spec(attendee):
                            # It's an agent ID with prefix - strip the prefix and check
                            agent_id = SpecUtils.extract_agent_id(attendee)
                            if agent_id in meeting.participants:
                                joined_attendees.add(attendee)
                                self.state.session_log.append(
                                    f"Required attendee {attendee} (ID) joined meeting {meeting_id}"
                                )
                        elif attendee in meeting.participants:
                            # It's an agent ID without prefix - check directly
                            joined_attendees.add(attendee)
                            self.state.session_log.append(
                                f"Required attendee {attendee} (ID) joined meeting {meeting_id}"
                            )
                        else:
                            # It's an agent type - look for any participant of this type
                            for (
                                participant_id,
                                participant_type,
                            ) in meeting.participants.items():
                                if participant_type == attendee:
                                    joined_attendees.add(attendee)
                                    self.state.session_log.append(
                                        f"Required attendee {attendee} (type) joined meeting {meeting_id}"
                                    )
                                    break

            # Check for rejections from required attendees
            # Check if any required attendees are still in pending invitations
            if meeting_id in self.state.owned_meetings:
                meeting = self.state.owned_meetings[meeting_id]
                for attendee in required_attendees:
                    if attendee in meeting.pending_invitations:
                        # Still has pending invitation, continue waiting
                        pass

            # Short sleep to avoid busy waiting (shorter if we processed messages)
            sleep_time = 0.05 if processed_any_messages else 0.1
            await asyncio.sleep(sleep_time)

        self.state.session_log.append(
            f"All required attendees have joined meeting {meeting_id}: {list(joined_attendees)}"
        )

    async def broadcast_to_meeting(
        self,
        meeting_id: str,
        message: str,
        exclude_sender: bool = True,
    ):
        """Broadcast a message to all participants in a meeting.

        Args:
            meeting_id: ID of the meeting to broadcast to
            message: Message content to send
            exclude_sender: Whether to exclude the sender from receiving the message
        """
        # Check if I'm the owner of this meeting
        if meeting_id in self.state.owned_meetings:
            # I'm the owner - add directly to message history
            from datetime import datetime

            from playbooks.execution_state import Message

            msg = Message(
                sender_id=self.id,
                sender_type=self.klass,
                content=message,
                timestamp=datetime.now(),
                meeting_id=meeting_id,
            )
            self.state.owned_meetings[meeting_id].message_history.append(msg)

            self.state.session_log.append(
                f"Added message to owned meeting {meeting_id}: {message}"
            )

        elif meeting_id in self.state.joined_meetings:
            # I'm a participant - escape message and send to owner
            owner_id = self.state.joined_meetings[meeting_id]["owner_agent_id"]

            # Escape any MEETING: prefix at the beginning to prevent injection
            escaped_message = re.sub(r"^MEETING:", "~~MEETING:", message)

            # Send to meeting owner with protocol prefix
            await self.program.route_message(
                self.id, owner_id, f"MEETING:{meeting_id}:{escaped_message}"
            )

            self.state.session_log.append(
                f"Sent message to meeting {meeting_id} owner {owner_id}: {message}"
            )

        else:
            # Error: not in this meeting
            self.state.session_log.append(
                f"Cannot broadcast to meeting {meeting_id} - not a participant"
            )

    async def _process_meeting_invitation(
        self, inviter_id: str, meeting_id: str, topic: str
    ):
        """Process a meeting invitation by checking for suitable meeting playbooks.

        Args:
            inviter_id: ID of the agent that sent the invitation
            meeting_id: ID of the meeting
            topic: Topic/description of the meeting
        """
        self.state.session_log.append(
            f"Received meeting invitation {meeting_id} from {inviter_id} for '{topic}'"
        )

        # Check if agent is busy (has active call stack)
        if len(self.state.call_stack.frames) > 0:
            self.state.session_log.append(
                f"Rejecting meeting {meeting_id} - agent is busy"
            )
            if self.program:
                await self.program.route_message(
                    self.id,
                    inviter_id,
                    "Meeting invitation rejected: Agent is currently busy",
                    message_type="meeting_response",
                    meeting_id=meeting_id,
                )
            return

        # Find matching meeting playbooks
        meeting_playbooks = []
        for playbook in self.playbooks.values():
            if playbook.meeting:
                meeting_playbooks.append(playbook)

        if not meeting_playbooks:
            # No meeting playbooks available
            self.state.session_log.append(
                f"Rejecting meeting {meeting_id} - no meeting playbooks available"
            )
            available_types = self.get_meeting_playbooks()
            rejection_message = f"Meeting invitation rejected: Cannot handle this type of meeting. Available meeting types: {available_types}"

            if self.program:
                await self.program.route_message(
                    self.id,
                    inviter_id,
                    rejection_message,
                    message_type="meeting_response",
                    meeting_id=meeting_id,
                )
            return

        # Accept the invitation and join the meeting
        self.state.session_log.append(f"Accepting meeting invitation {meeting_id}")

        # Store meeting info in joined_meetings for future message routing
        from datetime import datetime

        self.state.joined_meetings[meeting_id] = {
            "owner_agent_id": inviter_id,
            "joined_at": datetime.now(),
        }

        # Send structured JOINED response
        if self.program:
            await self.program.route_message(
                self.id,
                inviter_id,
                "Meeting invitation accepted: Ready to participate",
                message_type="meeting_response",
                meeting_id=meeting_id,
            )

        # The initiator will add us as a participant when they receive our JOINED message
        # We don't directly access the meeting object here to support remote agents

        # Execute the first available meeting playbook
        # In a more sophisticated implementation, we could match playbook by topic/type
        meeting_playbook = meeting_playbooks[0]

        try:
            self.state.session_log.append(
                f"Starting meeting playbook '{meeting_playbook.name}' for meeting {meeting_id}"
            )

            # Execute the meeting playbook with meeting context
            await self.execute_playbook(
                meeting_playbook.name,
                args=[],
                kwargs={"meeting_id": meeting_id, "topic": topic},
            )

        except Exception as e:
            self.state.session_log.append(
                f"Error executing meeting playbook for {meeting_id}: {str(e)}"
            )
            # Send error message to meeting
            if self.program:
                await self.program.route_message(
                    self.id,
                    inviter_id,
                    f"Meeting {meeting_id}: Error in playbook execution - {str(e)}",
                )

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
        if playbook and self.is_meeting_playbook(playbook_name):
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
        # Auto-inject parameters for meeting playbooks
        if self.is_meeting_playbook(playbook_name):
            kwargs = await self._inject_meeting_parameters(playbook_name, kwargs)

        playbook, call, langfuse_span = await self._pre_execute(
            playbook_name, args, kwargs
        )

        try:
            # Handle meeting playbook initialization (only for new meetings, not when joining existing ones)
            if (
                playbook
                and self.is_meeting_playbook(playbook_name)
                and not kwargs.get("meeting_id")
            ):
                meeting_id = await self._initialize_meeting_playbook(
                    playbook_name, kwargs
                )
                self.state.call_stack.peek().meeting_id = meeting_id
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
        if self.state.call_stack.peek() is not None:
            self.state.call_stack.peek().add_uncached_llm_message(
                call_result.to_log_full(), role=LLMMessageRole.ASSISTANT
            )
        langfuse_span.update(output=result)

    def __str__(self):
        return f"{self.klass}(agent {self.id})"

    def __repr__(self):
        kwargs = str(self.kwargs) if self.kwargs else ""
        return f"{self.klass}(agent {self.id}{kwargs})"

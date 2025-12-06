"""Meeting management functionality for AI agents."""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol

from playbooks.agents.human_agent import HumanAgent
from playbooks.core.exceptions import KlassNotFoundError
from playbooks.core.identifiers import MeetingID
from playbooks.core.message import Message, MessageType
from playbooks.debug.debug_handler import debug
from playbooks.llm.messages import MeetingLLMMessage, SessionLogLLMMessage
from playbooks.meetings.meeting import (
    JoinedMeeting,
    Meeting,
    MeetingInvitation,
    MeetingInvitationStatus,
)
from playbooks.meetings.meeting_message_handler import MeetingMessageHandler
from playbooks.playbook import LLMPlaybook, Playbook

if TYPE_CHECKING:
    from playbooks.agents.base_agent import BaseAgent
    from playbooks.program import Program
    from playbooks.state.execution_state import ExecutionState

logger = logging.getLogger(__name__)


class PlaybookExecutor(Protocol):
    """Protocol for executing playbooks."""

    playbooks: Dict[str, Playbook]

    async def execute_playbook(
        self, name: str, args: List[Any] = None, kwargs: Dict[str, Any] = None
    ) -> Any:
        """Execute a playbook by name."""
        ...


class MeetingManager:
    """Manages meeting-related functionality for AI agents.

    Uses dependency injection for clean separation of concerns:
    - agent_id, agent_klass: Simple identity data
    - state: ExecutionState or HumanState for meeting tracking
    - program: Program instance for message routing and agent lookup
    - playbook_executor: Protocol for executing playbooks
    """

    def __init__(
        self,
        agent_id: str,
        agent_klass: str,
        state: "ExecutionState",
        program: "Program",
        playbook_executor: PlaybookExecutor,
    ):
        """Initialize meeting manager with injected dependencies.

        Args:
            agent_id: The agent's unique identifier
            agent_klass: The agent's class/type
            state: ExecutionState for tracking meetings and session
            program: Program instance for routing and lookups
            playbook_executor: Protocol implementation for playbook execution
        """
        self.agent_id = agent_id
        self.agent_klass = agent_klass
        self.state = state
        self.program = program
        self.playbook_executor = playbook_executor

        self.meeting_message_handler = MeetingMessageHandler(
            self.agent_id, self.agent_klass
        )

    def ensure_meeting_playbook_kwargs(self, playbooks: Dict[str, Any]) -> None:
        """Ensure that all meeting playbooks have the required kwargs.

        Args:
            playbooks: Dictionary of playbooks to process
        """
        for playbook in playbooks.values():
            if playbook.meeting and isinstance(playbook, LLMPlaybook):
                signature = playbook.signature

                # Check if topic and attendees are missing
                missing_params = []
                if "topic:" not in signature and "topic :" not in signature:
                    missing_params.append("topic: str")
                if "attendees:" not in signature and "attendees :" not in signature:
                    missing_params.append("attendees: List[str]")

                if missing_params:
                    # Find the position to insert parameters (before the closing parenthesis)
                    # Handle cases like "GameRoom() -> None" or "TaxPrepMeeting($form: str) -> None"
                    if ") ->" in signature:
                        # Has return type annotation
                        before_return = signature.split(") ->")[0]
                        after_return = ") ->" + signature.split(") ->", 1)[1]
                    else:
                        # No return type, just ends with )
                        before_return = signature.rstrip(")")
                        after_return = ")"

                    # Check if there are existing parameters
                    if before_return.endswith("("):
                        # No existing parameters, add directly
                        new_params = ", ".join(missing_params)
                    else:
                        # Has existing parameters, add with comma prefix
                        new_params = ", " + ", ".join(missing_params)

                    # Reconstruct the signature
                    playbook.signature = before_return + new_params + after_return

    # def get_meeting_playbooks(self, playbooks: Dict[str, Playbook]) -> List[str]:
    #     """Get list of meeting playbook names.

    #     Args:
    #         playbooks: Dictionary of available playbooks

    #     Returns:
    #         List of playbook names that are marked as meeting playbooks
    #     """
    #     meeting_playbooks = []
    #     for playbook in playbooks.values():
    #         if playbook.meeting:
    #             meeting_playbooks.append(playbook.name)
    #     return meeting_playbooks

    # def is_meeting_playbook(
    #     self, playbook_name: str, playbooks: Dict[str, Playbook]
    # ) -> bool:
    #     """Check if a playbook is a meeting playbook.

    #     Args:
    #         playbook_name: Name of the playbook to check
    #         playbooks: Dictionary of available playbooks

    #     Returns:
    #         True if the playbook is a meeting playbook
    #     """
    #     playbook = playbooks.get(playbook_name)
    #     if not playbook:
    #         return False
    #     return playbook.meeting

    async def create_meeting(
        self, playbook: Playbook, kwargs: Dict[str, Any]
    ) -> Meeting:
        """Create meeting and prepare for invitations.

        Args:
            playbook: The playbook to create a meeting for
            kwargs: Keyword arguments passed to the playbook

        Returns:
            The created meeting
        """
        meeting_id = self.program.meeting_id_registry.generate_meeting_id()

        # Create meeting record
        meeting = Meeting(
            id=meeting_id,
            owner_id=self.agent_id,
            created_at=datetime.now(),
            topic=kwargs.get("topic", f"{playbook.name} meeting"),
        )

        self.state.owned_meetings[meeting_id] = meeting
        # Note: Meeting class requires BaseAgent object - playbook_executor is the agent
        meeting.agent_joined(self.playbook_executor)

        # Create asyncio.Event for tracking invitation responses
        meeting.invitation_event = asyncio.Event()

        # Figure out the attendees
        if "attendees" in kwargs and kwargs["attendees"]:
            # Either provided in the playbook call, e.g. attendees=["agent 1000", "agent 1001", "human"]
            meeting.required_attendees = (
                await self.program.get_agents_by_klasses_or_specs(kwargs["attendees"])
            )

            if not meeting.required_attendees:
                raise ValueError(
                    f"Unknown attendees {kwargs['attendees']} for meeting {meeting_id} with playbook {playbook.name}"
                )

        else:
            # Or configured in playbook metadata, e.g. required_attendees:["Accountant", "user"]
            if playbook.required_attendees or playbook.optional_attendees:
                try:
                    meeting.required_attendees = (
                        await self.program.get_agents_by_klasses(
                            playbook.required_attendees
                        )
                    )

                    meeting.optional_attendees = (
                        await self.program.get_agents_by_klasses(
                            playbook.optional_attendees
                        )
                    )
                except KlassNotFoundError:
                    raise ValueError(
                        f"Unknown required attendees {playbook.required_attendees} or optional attendees {playbook.optional_attendees} for meeting {meeting_id} with playbook {playbook.name}"
                    )

        if not meeting.required_attendees and not meeting.optional_attendees:
            raise ValueError(
                f"Unknown attendees for meeting {meeting_id} with playbook {playbook.name}"
            )

        # Create meeting channel with all potential participants
        all_participants = list(
            set(
                [self.playbook_executor]
                + meeting.required_attendees
                + meeting.optional_attendees
            )
        )
        await self.program.create_meeting_channel(meeting_id, all_participants)
        debug(
            f"Agent {self.agent_id}: Created meeting channel {meeting_id} with {len(all_participants)} participants"
        )

        # Send invitations concurrently
        invitation_tasks = []

        # Create tasks for all required attendees
        for attendee in meeting.required_attendees:
            future = self._invite_to_meeting(meeting, attendee)
            if future:
                invitation_tasks.append(asyncio.create_task(future))

        # Create tasks for all optional attendees
        for attendee in meeting.optional_attendees:
            future = self._invite_to_meeting(meeting, attendee)
            if future:
                invitation_tasks.append(asyncio.create_task(future))

        # Yield for other tasks (async yield point)
        await asyncio.sleep(0)

        # Wait for all invitations to be sent
        if invitation_tasks:
            await asyncio.gather(*invitation_tasks)

        return meeting

    async def _invite_to_meeting(
        self, meeting: Meeting, target_agent: "BaseAgent"
    ) -> str:
        """Invite an agent to a meeting.

        Creates invitation record and sends invitation message. Human agents
        are automatically joined without invitation.

        Args:
            meeting: The meeting to invite to
            target_agent: The agent to invite

        Returns:
            Response message describing the invitation result
        """
        # Check if the target agent is already a participant
        if meeting.is_participant(target_agent.id):
            response = f"Agent {target_agent.id} is already a participant of meeting {meeting.id}"
        elif isinstance(target_agent, HumanAgent):
            response = f"User joined meeting {meeting.id}"
            meeting.agent_joined(target_agent)
        else:
            meeting.invitations[target_agent.id] = MeetingInvitation(
                agent=target_agent,
                created_at=datetime.now(),
                status=MeetingInvitationStatus.PENDING,
            )
            response = f"Inviting {str(target_agent)} to meeting {meeting.id}: {meeting.topic or 'Meeting'}"
            await self._send_invitation(meeting, target_agent)

        self.state.session_log.append(response)
        meeting_msg = MeetingLLMMessage(response, meeting_id=meeting.id)
        self.state.call_stack.add_llm_message(meeting_msg)

        return response

    async def _send_invitation(
        self, meeting: Meeting, target_agent: "BaseAgent"
    ) -> str:
        """Send meeting invitation to an agent using the message system.

        Routes a MEETING_INVITATION message to the target agent and logs it.

        Args:
            meeting: The meeting to send the invitation to
            target_agent: The agent to send the invitation to

        Returns:
            Response message confirming invitation was sent
        """

        # Send structured invitation message
        invitation_content = meeting.topic or "Meeting"

        await self.program.route_message(
            sender_id=self.agent_id,
            sender_klass=self.agent_klass,
            receiver_spec=f"agent {target_agent.id}",
            message=invitation_content,
            message_type=MessageType.MEETING_INVITATION,
            meeting_id=meeting.id,
        )

        response = (
            f"Invited {str(target_agent)} to meeting {meeting.id}: {invitation_content}"
        )
        self.state.session_log.append(response)
        meeting_msg = MeetingLLMMessage(response, meeting_id=meeting.id)
        self.state.call_stack.add_llm_message(meeting_msg)

        return response

    async def InviteToMeeting(
        self, meeting_id: str, attendees: List[str]
    ) -> Optional[str]:
        """Invite agents to a meeting.

        Only the meeting owner can invite attendees. Sends invitations
        concurrently to all specified attendees.

        Args:
            meeting_id: The ID of the meeting to invite to
            attendees: List of agent specs to invite

        Returns:
            Error message if not owner, None if successful
        """
        if meeting_id not in self.state.owned_meetings:
            return f"I am not the owner of meeting {meeting_id}, so cannot invite attendees"

        meeting = self.state.owned_meetings[meeting_id]
        attendees = self.program.get_agents_by_specs(attendees)

        # Send invitations concurrently
        invitation_tasks = []
        for attendee in attendees:
            future = self._invite_to_meeting(meeting, attendee)
            if future:
                invitation_tasks.append(asyncio.create_task(future))

        # Wait for all invitations and collect responses
        if invitation_tasks:
            responses = await asyncio.gather(*invitation_tasks)
            return "\n".join(responses)
        return ""

    async def _wait_for_required_attendees(
        self, meeting: Meeting, timeout_seconds: int = 30
    ):
        """Wait for required attendees to join the meeting before proceeding.

        Args:
            meeting: The meeting to wait for
            timeout_seconds: Maximum time to wait for attendees

        Raises:
            TimeoutError: If required attendees don't join within timeout
            ValueError: If required attendee rejects the invitation
        """
        # If no attendees to wait for, proceed immediately
        if not meeting.required_attendees:
            message = f"No required attendees to wait for in meeting {meeting.id} - proceeding immediately"
            self.state.session_log.append(message)
            meeting_msg = MeetingLLMMessage(message, meeting_id=meeting.id)
            self.state.call_stack.add_llm_message(meeting_msg)
            return

        messages = f"Waiting for required attendees to join meeting {meeting.id}: {[attendee.__repr__() for attendee in meeting.required_attendees]}"
        self.state.session_log.append(messages)
        meeting_msg = MeetingLLMMessage(messages, meeting_id=meeting.id)
        self.state.call_stack.add_llm_message(meeting_msg)

        # Event-driven waiting: wait for invitation responses
        start_time = asyncio.get_event_loop().time()

        while meeting.has_pending_invitations():
            # Calculate remaining timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining_timeout = timeout_seconds - elapsed

            if remaining_timeout <= 0:
                raise TimeoutError(
                    f"Timeout waiting for required attendees to join meeting {meeting.id}. "
                    f"Missing: {[attendee.__repr__() for attendee in meeting.missing_required_attendees()]}"
                )

            try:
                # Wait for invitation event (signaled when any response received)
                await asyncio.wait_for(
                    meeting.invitation_event.wait(), timeout=remaining_timeout
                )
                meeting.invitation_event.clear()  # Reset for next wait

                # Check if all required attendees have joined
                if not meeting.has_pending_invitations():
                    break

                # Log progress
                message = f"Waiting for remaining attendees: {[attendee.__repr__() for attendee in meeting.missing_required_attendees()]}"
                self.state.session_log.append(message)

            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Timeout waiting for required attendees to join meeting {meeting.id}. "
                    f"Missing: {[attendee.__repr__() for attendee in meeting.missing_required_attendees()]}"
                )

        message = f"All required attendees have joined meeting {meeting.id}: {[attendee.__repr__() for attendee in meeting.joined_attendees]}"
        self.state.session_log.append(message)
        meeting_msg = MeetingLLMMessage(message, meeting_id=meeting.id)
        self.state.call_stack.add_llm_message(meeting_msg)

        # Finally, set the meeting ID as the current meeting ID in the call stack
        self.state.call_stack.peek().meeting_id = meeting.id

    def get_current_meeting_from_call_stack(self) -> Optional[str]:
        """Get meeting ID from top meeting playbook in call stack.

        Args:
            call_stack: The agent's call stack

        Returns:
            Meeting ID if currently in a meeting, None otherwise
        """
        call_stack = self.state.call_stack
        for frame in reversed(call_stack.frames):
            if frame.is_meeting and frame.meeting_id:
                return frame.meeting_id
        return None

    async def broadcast_to_meeting_as_owner(
        self,
        meeting_id: str,
        message: str,
        from_agent_id: str = None,
        from_agent_klass: str = None,
    ):
        """Broadcast a message to all participants via unified channel.

        Args:
            meeting_id: ID of the meeting to broadcast to
            message: Message content to send
            from_agent_id: ID of the sender (defaults to self)
            from_agent_klass: Class of the sender (defaults to self)
        """
        # Check if I'm the owner of this meeting
        assert (
            hasattr(self.state, "owned_meetings")
            and hasattr(self.state, "owned_meetings")
            and meeting_id in self.state.owned_meetings
        )

        if not from_agent_id or not from_agent_klass:
            from_agent_id = self.agent_id
            from_agent_klass = self.agent_klass

        self.state.session_log.append(
            f"Broadcasting to meeting {meeting_id}: {message}"
        )

        # Use unified channel architecture - route_message handles channel multicast
        await self.program.route_message(
            sender_id=from_agent_id,
            sender_klass=from_agent_klass,
            receiver_spec=f"meeting {meeting_id}",
            message=message,
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id=meeting_id,
        )

    async def broadcast_to_meeting_as_participant(
        self, meeting_id: str, message: str
    ) -> None:
        """Broadcast a message to all participants via unified channel.

        Args:
            meeting_id: ID of the meeting to broadcast to
            message: Message content to send
        """
        assert (
            hasattr(self.state, "owned_meetings")
            and hasattr(self.state, "joined_meetings")
            and meeting_id in self.state.joined_meetings
        )

        self.state.session_log.append(
            f"Broadcasting to meeting {meeting_id} as participant: {message}"
        )

        # Use unified channel architecture - participants can send directly to meeting channel
        await self.program.route_message(
            sender_id=self.agent_id,
            sender_klass=self.agent_klass,
            receiver_spec=f"meeting {meeting_id}",
            message=message,
            message_type=MessageType.MEETING_BROADCAST,
            meeting_id=meeting_id,
        )

    async def _add_message_to_buffer(self, message: Message) -> bool:
        """Add a message to buffer and notify waiting processes.

        This is the single entry point for all incoming messages.
        Handles meeting invitations and responses immediately.

        Args:
            message: Message to add to buffer

        Returns:
            True if message was handled, False otherwise
        """
        if message.message_type == MessageType.MEETING_INVITATION:
            # Process meeting invitation immediately
            return await self._handle_meeting_invitation_immediately(message)
        elif message.message_type == MessageType.MEETING_INVITATION_RESPONSE:
            # Process meeting response immediately and signal event
            await self._handle_meeting_response_immediately(message)

            # Signal the meeting's invitation event to wake up _wait_for_required_attendees
            meeting_id_obj = message.meeting_id
            if (
                meeting_id_obj
                and hasattr(self.state, "owned_meetings")
                and meeting_id_obj.id in self.state.owned_meetings
            ):
                meeting = self.state.owned_meetings[meeting_id_obj.id]
                if hasattr(meeting, "invitation_event"):
                    meeting.invitation_event.set()
                    debug(
                        f"Agent {self.agent_id}: Signaled invitation event for meeting {meeting_id_obj.id}"
                    )

            return True
        return False

    async def _handle_meeting_invitation_immediately(self, message) -> None:
        """Handle meeting invitation immediately without buffering."""
        # Extract meeting information from the message
        meeting_id_obj = getattr(message, "meeting_id", None)
        sender_id = message.sender_id.id
        topic = message.content  # The invitation content contains the topic

        meeting_id = meeting_id_obj.id if meeting_id_obj else None

        if meeting_id:
            # Use async task to handle the invitation since this is called synchronously
            return await self._process_meeting_invitation(sender_id, meeting_id, topic)
        else:
            log = f"Received meeting invitation from {sender_id} without meeting_id"
            self.state.session_log.append(log)
            session_msg = SessionLogLLMMessage(log, log_level="warning")
            self.state.call_stack.add_llm_message(session_msg)
            return True

    async def _handle_meeting_response_immediately(self, message) -> None:
        """Handle meeting response immediately without buffering."""
        # Process the meeting response using the handler that updates meeting state
        await self.meeting_message_handler.handle_meeting_response(
            message, self.playbook_executor
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
        log = f"Received meeting invitation for meeting {meeting_id} from {inviter_id} for '{topic}'"
        self.state.session_log.append(log)
        meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
        self.state.call_stack.add_llm_message(meeting_msg)

        # Check if agent is busy (has active call stack)
        if hasattr(self.state.variables, "_busy") and self.state.variables._busy:
            log = f"Rejecting meeting {meeting_id} - agent is busy"
            self.state.session_log.append(log)
            meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
            self.state.call_stack.add_llm_message(meeting_msg)
            if self.program:
                await self.program.route_message(
                    sender_id=self.agent_id,
                    sender_klass=self.agent_klass,
                    receiver_spec=f"agent {inviter_id}",
                    message=f"REJECTED {meeting_id}",
                    message_type=MessageType.MEETING_INVITATION_RESPONSE,
                    meeting_id=meeting_id,
                )
            return True
        return False

    async def _accept_meeting_invitation(
        self, meeting_id: str, inviter_id: str, topic: str, playbook_name: str
    ) -> bool:
        # Accept the invitation and join the meeting
        debug(f"Agent {self.agent_id}: Accepting meeting invitation {meeting_id}")
        log = f"Accepting meeting invitation {meeting_id}"
        meeting_id_obj = MeetingID.parse(meeting_id)
        meeting_id = meeting_id_obj.id
        self.state.session_log.append(log)
        meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
        self.state.call_stack.add_llm_message(meeting_msg)

        # Store meeting info in joined_meetings for future message routing

        self.state.joined_meetings[meeting_id] = JoinedMeeting(
            id=meeting_id,
            owner_id=inviter_id,
            topic=topic,
            joined_at=datetime.now(),
        )
        debug(f"Agent {self.agent_id}: joined_meetings {self.state.joined_meetings}")

        # Send structured JOINED response
        if self.program:
            await self.program.route_message(
                sender_id=self.agent_id,
                sender_klass=self.agent_klass,
                receiver_spec=f"agent {inviter_id}",
                message=f"JOINED {meeting_id}",
                message_type=MessageType.MEETING_INVITATION_RESPONSE,
                meeting_id=meeting_id,
            )

        # The initiator will add us as a participant when they receive our JOINED message
        # We don't directly access the meeting object here to support remote agents

    async def _execute_meeting_playbook(
        self, meeting_id: str, playbook_name: str
    ) -> None:
        try:
            meeting_playbook = self.playbook_executor.playbooks[playbook_name]

            meeting = self.state.joined_meetings[meeting_id]
            topic = meeting.topic

            log = f"Starting meeting playbook '{meeting_playbook.name}' for meeting {meeting_id}"
            debug(f"Agent {self.agent_id}: {log}")
            self.state.session_log.append(log)
            meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
            self.state.call_stack.add_llm_message(meeting_msg)

            # Execute the meeting playbook with meeting context
            debug(
                "Agent executing meeting playbook",
                agent_id=self.agent_id,
                playbook_name=meeting_playbook.name,
            )
            task = asyncio.create_task(
                self.playbook_executor.execute_playbook(
                    meeting_playbook.name,
                    args=[],
                    kwargs={"meeting_id": meeting_id, "topic": topic},
                )
            )
            task.add_done_callback(
                lambda t: debug(
                    "Meeting playbook task done",
                    agent_id=self.agent_id,
                    playbook_name=meeting_playbook.name,
                )
            )
            await asyncio.gather(task)

        except Exception as e:
            log = f"Error executing meeting playbook for {meeting_id}: {str(e)}"
            self.state.session_log.append(log)
            meeting_msg = MeetingLLMMessage(log, meeting_id=meeting_id)
            self.state.call_stack.add_llm_message(meeting_msg)
            # Send error message to meeting
            if self.program:
                await self.program.route_message(
                    sender_id=self.agent_id,
                    sender_klass=self.agent_klass,
                    receiver_spec=f"agent {meeting.owner_id}",
                    message=f"Meeting {meeting_id}: Error in playbook execution - {str(e)}",
                    message_type=MessageType.MEETING_INVITATION_RESPONSE,
                    meeting_id=meeting_id,
                )

    # async def initialize_meeting_playbook(
    #     self,
    #     playbook_name: str,
    #     kwargs: Dict[str, Any],
    #     playbooks: Dict[str, Any],
    #     meeting_registry: MeetingRegistry,
    #     session_log,
    #     wait_for_attendees_callback,
    # ):
    #     """Initialize meeting before executing meeting playbook.

    #     This method is called implicitly before any meeting playbook executes.
    #     For new meetings, it creates the meeting, sends invitations, and waits for required participants.
    #     For existing meetings (when meeting_id is provided), it joins the existing meeting.

    #     Args:
    #         playbook_name: Name of the meeting playbook being executed
    #         kwargs: Keyword arguments passed to the playbook
    #         playbooks: Dictionary of available playbooks
    #         meeting_registry: Registry for meeting IDs
    #         session_log: Session log for recording events
    #         wait_for_attendees_callback: Callback to wait for required attendees
    #     """
    #     # Check if we're joining an existing meeting (meeting_id provided) or creating a new one
    #     existing_meeting_id = kwargs.get("meeting_id")

    #     if existing_meeting_id:
    #         # Joining an existing meeting - just proceed with execution
    #         session_log.append(
    #             f"Joining existing meeting {existing_meeting_id} for playbook {playbook_name}"
    #         )
    #         return  # No need to create meeting or wait for attendees

    #     # Creating a new meeting
    #     kwargs_attendees = kwargs.get("attendees", [])
    #     topic = kwargs.get("topic", f"{playbook_name} meeting")

    #     # Determine attendee strategy: kwargs attendees take precedence
    #     if kwargs_attendees:
    #         # If attendees specified in kwargs, treat them as required
    #         required_attendees = kwargs_attendees
    #         all_attendees = kwargs_attendees
    #         session_log.append(
    #             f"Using kwargs attendees as required for meeting {playbook_name}: {required_attendees}"
    #         )
    #     else:
    #         # If no kwargs attendees, use metadata-defined attendees
    #         metadata_required, metadata_optional = self.get_playbook_attendees(
    #             playbook_name, playbooks
    #         )
    #         required_attendees = metadata_required
    #         all_attendees = list(set(metadata_required + metadata_optional))
    #         session_log.append(
    #             f"Using metadata attendees for meeting {playbook_name}: required={metadata_required}, optional={metadata_optional}"
    #         )

    #     # Filter out the requester from required attendees (they're already present)
    #     required_attendees_to_wait_for = [
    #         attendee
    #         for attendee in required_attendees
    #         if attendee != self.agent_klass and attendee != self.agent_id
    #     ]

    #     # Create the meeting
    #     meeting_id = await self.create_meeting(
    #         invited_agents=all_attendees, topic=topic, meeting_registry=meeting_registry
    #     )

    #     # Store meeting_id in kwargs for the playbook to access
    #     kwargs["meeting_id"] = meeting_id

    #     # Log the meeting initialization
    #     session_log.append(
    #         f"Initialized meeting {meeting_id} for playbook {playbook_name}"
    #     )

    #     # Wait for required attendees to join before proceeding
    #     await wait_for_attendees_callback(meeting_id, required_attendees_to_wait_for)

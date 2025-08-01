"""Meeting management functionality for AI agents."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from playbooks.constants import HUMAN_AGENT_KLASS
from playbooks.exceptions import KlassNotFoundError
from playbooks.meetings.meeting_message_handler import MeetingMessageHandler

from ..agents.base_agent import BaseAgent
from ..message import Message, MessageType
from ..playbook import LLMPlaybook, Playbook
from .meeting import JoinedMeeting, Meeting, MeetingInvitation, MeetingInvitationStatus

logger = logging.getLogger(__name__)


class MeetingManager:
    """Manages meeting-related functionality for AI agents."""

    def __init__(self, agent: BaseAgent):
        """Initialize meeting manager.

        Args:
            agent: The agent
        """
        self.agent = agent
        self.meeting_message_handler = MeetingMessageHandler(
            self.agent.id, self.agent.klass
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
        meeting_id = self.agent.program.meeting_id_registry.generate_meeting_id()

        # Create meeting record
        meeting = Meeting(
            id=meeting_id,
            owner_id=self.agent.id,
            created_at=datetime.now(),
            topic=kwargs.get("topic", f"{playbook} meeting"),
        )

        self.agent.state.owned_meetings[meeting_id] = meeting
        meeting.agent_joined(self.agent)

        # Figure out the attendees
        if "attendees" in kwargs and kwargs["attendees"]:
            # Either provided in the playbook call, e.g. attendees=["agent 1000", "agent 1001", "human"]
            meeting.required_attendees = (
                await self.agent.program.get_agents_by_klasses_or_specs(
                    kwargs["attendees"]
                )
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
                        await self.agent.program.get_agents_by_klasses(
                            playbook.required_attendees
                        )
                    )

                    meeting.optional_attendees = (
                        await self.agent.program.get_agents_by_klasses(
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

        # Send invitations concurrently
        invitation_tasks = []

        # Create tasks for all required attendees
        for attendee in meeting.required_attendees:
            task = asyncio.create_task(self._invite_to_meeting(meeting, attendee))
            invitation_tasks.append(task)

        # Create tasks for all optional attendees
        for attendee in meeting.optional_attendees:
            task = asyncio.create_task(self._invite_to_meeting(meeting, attendee))
            invitation_tasks.append(task)

        # Yield for other tasks
        await asyncio.sleep(0.1)

        # Wait for all invitations to be sent
        if invitation_tasks:
            await asyncio.gather(*invitation_tasks)

        return meeting

    async def _invite_to_meeting(self, meeting: Meeting, target_agent: BaseAgent):
        """Invite an agent to a meeting.

        Args:
            meeting: The meeting to invite to
            target_agent: The agent to invite
        """
        # Check if the target agent is already a participant
        if meeting.is_participant(target_agent.id):
            response = f"Agent {target_agent.id} is already a participant of meeting {meeting.id}"
        elif target_agent.klass == HUMAN_AGENT_KLASS:
            response = f"User joined meeting {meeting.id}"
            meeting.agent_joined(target_agent)
        else:
            meeting.invitations[target_agent.id] = MeetingInvitation(
                agent=target_agent,
                created_at=datetime.now(),
                status=MeetingInvitationStatus.PENDING,
            )
            response = f"Inviting {str(target_agent)} to meeting {meeting.id}: {meeting.topic or 'Meeting'}"
            self.agent.state.session_log.append(response)
            self.agent.add_uncached_llm_message(response)
            asyncio.create_task(self._send_invitation(meeting, target_agent))

        return response

    async def _send_invitation(self, meeting: Meeting, target_agent: BaseAgent):
        """Send meeting invitation to an agent using the message system.

        Args:
            meeting: The meeting to send the invitation to
            target_agent: The agent to send the invitation to
        """

        # Send structured invitation message
        invitation_content = meeting.topic or "Meeting"

        await self.agent.program.route_message(
            sender_id=self.agent.id,
            sender_klass=self.agent.klass,
            receiver_spec=target_agent.id,
            message=invitation_content,
            message_type=MessageType.MEETING_INVITATION,
            meeting_id=meeting.id,
        )

        response = (
            f"Invited {str(target_agent)} to meeting {meeting.id}: {invitation_content}"
        )
        self.agent.state.session_log.append(response)
        self.agent.add_uncached_llm_message(response)

        return response

    async def InviteToMeeting(self, meeting_id: str, attendees: List[str]):
        """Invite an agent to a meeting.

        Args:
            meeting_id: The ID of the meeting to invite to
            attendees: The agents to invite
        """
        if meeting_id not in self.agent.state.owned_meetings:
            return f"I am not the owner of meeting {meeting_id}, so cannot invite attendees"

        meeting = self.agent.state.owned_meetings[meeting_id]
        attendees = self.agent.program.get_agents_by_specs(attendees)

        # Send invitations concurrently
        invitation_tasks = []
        for attendee in attendees:
            task = asyncio.create_task(self._invite_to_meeting(meeting, attendee))
            invitation_tasks.append(task)

        # Wait for all invitations and collect responses
        responses = await asyncio.gather(*invitation_tasks) if invitation_tasks else []
        return "\n".join(responses)

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
            self.agent.state.session_log.append(message)
            self.agent.add_uncached_llm_message(message)
            return

        messages = f"Waiting for required attendees to join meeting {meeting.id}: {[attendee.__repr__() for attendee in meeting.required_attendees]}"
        self.agent.state.session_log.append(messages)
        self.agent.add_uncached_llm_message(messages)

        # Track which required attendees have joined
        start_time = asyncio.get_event_loop().time()

        while meeting.has_pending_invitations():
            # Check for timeout
            if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                raise TimeoutError(
                    f"Timeout waiting for required attendees to join meeting {meeting.id}. "
                    f"Missing: {[attendee.__repr__() for attendee in meeting.missing_required_attendees()]}"
                )
            message = f"Waiting for required attendees to join meeting {meeting.id}: {[attendee.__repr__() for attendee in meeting.missing_required_attendees()]}"
            self.agent.state.session_log.append(message)
            await asyncio.sleep(1)

        message = f"All required attendees have joined meeting {meeting.id}: {[attendee.__repr__() for attendee in meeting.joined_attendees]}"
        self.agent.state.session_log.append(message)
        self.agent.add_uncached_llm_message(message)

        # Finally, set the meeting ID as the current meeting ID in the call stack
        self.agent.state.call_stack.peek().meeting_id = meeting.id

    def get_current_meeting_from_call_stack(self) -> Optional[str]:
        """Get meeting ID from top meeting playbook in call stack.

        Args:
            call_stack: The agent's call stack

        Returns:
            Meeting ID if currently in a meeting, None otherwise
        """
        call_stack = self.agent.state.call_stack
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
        """Broadcast a message to all participants in a meeting.

        Args:
            meeting_id: ID of the meeting to broadcast to
            message: Message content to send
        """
        # Check if I'm the owner of this meeting
        assert (
            hasattr(self.agent, "state")
            and hasattr(self.agent.state, "owned_meetings")
            and meeting_id in self.agent.state.owned_meetings
        )

        if not from_agent_id or not from_agent_klass:
            from_agent_id = self.agent.id
            from_agent_klass = self.agent.klass

        meeting: Meeting = self.agent.state.owned_meetings[meeting_id]
        self.agent.state.session_log.append(
            f"Adding message to owned meeting {meeting_id}: {message}"
        )
        for participant in meeting.joined_attendees:
            if participant.id == from_agent_id:
                continue
            # print(f"  - Broadcasting to {participant.id}")
            await self.agent.program.route_message(
                sender_id=from_agent_id,
                sender_klass=from_agent_klass,
                receiver_spec=f"agent {participant.id}",
                message=message,
                message_type=MessageType.MEETING_BROADCAST,
                meeting_id=meeting_id,
            )

    async def broadcast_to_meeting_as_participant(self, meeting_id: str, message: str):
        """Broadcast a message to all participants in a meeting.

        Args:
            meeting_id: ID of the meeting to broadcast to
            message: Message content to send
        """
        assert (
            hasattr(self.agent, "state")
            and hasattr(self.agent.state, "joined_meetings")
            and meeting_id in self.agent.state.joined_meetings
        )
        # I'm a participant - I will request the owner
        owner_id = self.agent.state.joined_meetings[meeting_id].owner_id

        # Send to meeting owner with protocol prefix
        await self.agent.program.route_message(
            sender_id=self.agent.id,
            sender_klass=self.agent.klass,
            receiver_spec=f"agent {owner_id}",
            message=message,
            message_type=MessageType.MEETING_BROADCAST_REQUEST,
            meeting_id=meeting_id,
        )

    async def _add_message_to_buffer(self, message: Message) -> bool:
        """Add a message to buffer and notify waiting processes.

        This is the single entry point for all incoming messages.
        """
        if message.message_type == MessageType.MEETING_INVITATION:
            # Process meeting invitation immediately
            await self._handle_meeting_invitation_immediately(message)
            return True
        elif message.message_type == MessageType.MEETING_INVITATION_RESPONSE:
            # Process meeting response immediately
            await self._handle_meeting_response_immediately(message)
            return True
        elif message.message_type == MessageType.MEETING_BROADCAST_REQUEST:
            # Process meeting message immediately
            await self.broadcast_to_meeting_as_owner(
                meeting_id=message.meeting_id,
                message=message.content,
                from_agent_id=message.sender_id,
                from_agent_klass=message.sender_klass,
            )
            return True
        return False

    async def _handle_meeting_invitation_immediately(self, message) -> None:
        """Handle meeting invitation immediately without buffering."""
        # Extract meeting information from the message
        meeting_id = getattr(message, "meeting_id", None)
        sender_id = message.sender_id
        topic = message.content  # The invitation content contains the topic

        if meeting_id:
            # Use async task to handle the invitation since this is called synchronously
            await self._process_meeting_invitation(sender_id, meeting_id, topic)
        else:
            log = f"Received meeting invitation from {sender_id} without meeting_id"
            self.agent.state.session_log.append(log)
            self.agent.add_uncached_llm_message(log)

    async def _handle_meeting_response_immediately(self, message) -> None:
        """Handle meeting response immediately without buffering."""
        # Use existing meeting message handler for responses
        if hasattr(self, "meeting_message_handler"):
            # Create task to handle response asynchronously
            await self.meeting_message_handler.handle_meeting_response(
                message,
                self.agent,
            )
        else:
            self.agent.state.session_log.append(
                f"Received meeting response from {message.sender_id} but no handler available"
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
        self.agent.state.session_log.append(log)
        self.agent.add_uncached_llm_message(log)

        # Check if agent is busy (has active call stack)
        if len(self.agent.state.call_stack.frames) > 0:
            log = f"Rejecting meeting {meeting_id} - agent is busy"
            self.agent.state.session_log.append(log)
            self.agent.add_uncached_llm_message(log)
            if self.agent.program:
                await self.agent.program.route_message(
                    sender_id=self.agent.id,
                    sender_klass=self.agent.klass,
                    receiver_spec=f"agent {inviter_id}",
                    message=f"REJECTED {meeting_id}",
                    message_type=MessageType.MEETING_INVITATION_RESPONSE,
                    meeting_id=meeting_id,
                )
            return

        # Find matching meeting playbooks
        meeting_playbooks = []
        for playbook in self.agent.playbooks.values():
            if playbook.meeting:
                meeting_playbooks.append(playbook)

        if not meeting_playbooks:
            # No meeting playbooks available
            log = f"Rejecting meeting {meeting_id} - no meeting playbooks available"
            self.agent.state.session_log.append(log)
            self.agent.add_uncached_llm_message(log)
            available_types = self.get_meeting_playbooks()
            rejection_message = f"Meeting invitation rejected: Cannot handle this type of meeting. Available meeting types: {available_types}"

            if self.agent.program:
                await self.agent.program.route_message(
                    self.agent.id,
                    inviter_id,
                    f"REJECTED {meeting_id}: {rejection_message}",
                    message_type="meeting_response",
                    meeting_id=meeting_id,
                )
            return

        # Accept the invitation and join the meeting
        log = f"Accepting meeting invitation {meeting_id}"
        self.agent.state.session_log.append(log)
        self.agent.add_uncached_llm_message(log)

        # Store meeting info in joined_meetings for future message routing

        self.agent.state.joined_meetings[meeting_id] = JoinedMeeting(
            id=meeting_id,
            owner_id=inviter_id,
            joined_at=datetime.now(),
        )

        # Send structured JOINED response
        if self.agent.program:
            await self.agent.program.route_message(
                sender_id=self.agent.id,
                sender_klass=self.agent.klass,
                receiver_spec=f"agent {inviter_id}",
                message=f"JOINED {meeting_id}",
                message_type=MessageType.MEETING_INVITATION_RESPONSE,
                meeting_id=meeting_id,
            )

        # The initiator will add us as a participant when they receive our JOINED message
        # We don't directly access the meeting object here to support remote agents

        # Execute the first available meeting playbook
        # In a more sophisticated implementation, we could match playbook by topic/type
        meeting_playbook = meeting_playbooks[0]

        try:
            log = f"Starting meeting playbook '{meeting_playbook.name}' for meeting {meeting_id}"
            self.agent.state.session_log.append(log)
            self.agent.add_uncached_llm_message(log)

            # Execute the meeting playbook with meeting context
            task = asyncio.create_task(
                self.agent.execute_playbook(
                    meeting_playbook.name,
                    args=[],
                    kwargs={"meeting_id": meeting_id, "topic": topic},
                )
            )
            task.add_done_callback(
                lambda t: print(
                    f"{str(self.agent)} : Meeting playbook task done - {meeting_playbook.name}"
                )
            )
            await asyncio.gather(task)

        except Exception as e:
            log = f"Error executing meeting playbook for {meeting_id}: {str(e)}"
            self.agent.state.session_log.append(log)
            self.agent.add_uncached_llm_message(log)
            # Send error message to meeting
            if self.agent.program:
                await self.agent.program.route_message(
                    sender_id=self.agent.id,
                    sender_klass=self.agent.klass,
                    receiver_spec=f"agent {inviter_id}",
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

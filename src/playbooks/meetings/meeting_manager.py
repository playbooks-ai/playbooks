"""Meeting management functionality for AI agents."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..playbook import MarkdownPlaybook
from .meeting import Meeting, Message
from .meeting_registry import MeetingRegistry

logger = logging.getLogger(__name__)


class MeetingManager:
    """Manages meeting-related functionality for AI agents."""

    def __init__(self, agent_id: str, agent_klass: str):
        """Initialize meeting manager.

        Args:
            agent_id: The agent's unique ID
            agent_klass: The agent's class/type
        """
        self.agent_id = agent_id
        self.agent_klass = agent_klass
        self.owned_meetings: Dict[str, Meeting] = {}
        self.joined_meetings: Dict[str, Dict[str, Any]] = {}

    def ensure_meeting_playbook_kwargs(self, playbooks: Dict[str, Any]) -> None:
        """Ensure that all meeting playbooks have the required kwargs.

        Args:
            playbooks: Dictionary of playbooks to process
        """
        for playbook in playbooks.values():
            if playbook.meeting and isinstance(playbook, MarkdownPlaybook):
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

    def get_meeting_playbooks(self, playbooks: Dict[str, Any]) -> List[str]:
        """Get list of meeting playbook names.

        Args:
            playbooks: Dictionary of available playbooks

        Returns:
            List of playbook names that are marked as meeting playbooks
        """
        meeting_playbooks = []
        for playbook in playbooks.values():
            if playbook.meeting:
                meeting_playbooks.append(playbook.name)
        return meeting_playbooks

    def is_meeting_playbook(
        self, playbook_name: str, playbooks: Dict[str, Any]
    ) -> bool:
        """Check if a playbook is a meeting playbook.

        Args:
            playbook_name: Name of the playbook to check
            playbooks: Dictionary of available playbooks

        Returns:
            True if the playbook is a meeting playbook
        """
        playbook = playbooks.get(playbook_name)
        if not playbook:
            return False
        return playbook.meeting

    def get_playbook_attendees(
        self, playbook_name: str, playbooks: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """Get required and optional attendees for a meeting playbook.

        Args:
            playbook_name: Name of the meeting playbook
            playbooks: Dictionary of available playbooks

        Returns:
            Tuple of (required_attendees, optional_attendees)
        """
        playbook = playbooks.get(playbook_name)
        if not playbook:
            return [], []

        required = playbook.required_attendees
        optional = playbook.optional_attendees
        return required, optional

    async def create_meeting(
        self,
        invited_agents: List[str],
        topic: Optional[str],
        meeting_registry: MeetingRegistry,
    ) -> str:
        """Create meeting and prepare for invitations.

        Args:
            invited_agents: List of agent types/IDs to invite
            topic: Optional meeting topic
            meeting_registry: Registry to generate meeting ID

        Returns:
            Generated meeting ID
        """
        meeting_id = meeting_registry.generate_meeting_id(self.agent_id)

        # Create meeting record
        meeting = Meeting(
            meeting_id=meeting_id,
            initiator_id=self.agent_id,
            participants={self.agent_id: self.agent_klass},
            created_at=datetime.now(),
            topic=topic,
        )

        # Track pending invitations
        for agent_spec in invited_agents:
            meeting.pending_invitations.add(agent_spec)

        self.owned_meetings[meeting_id] = meeting
        return meeting_id

    def get_meeting(self, meeting_id: str) -> Optional[Meeting]:
        """Get a meeting by ID.

        Args:
            meeting_id: The meeting ID to look up

        Returns:
            Meeting instance if found, None otherwise
        """
        return self.owned_meetings.get(meeting_id)

    def add_participant_to_meeting(
        self, meeting_id: str, agent_id: str, agent_type: str
    ) -> bool:
        """Add a participant to a meeting.

        Args:
            meeting_id: The meeting ID
            agent_id: The agent ID to add
            agent_type: The agent type

        Returns:
            True if participant was added, False if meeting not found
        """
        meeting = self.owned_meetings.get(meeting_id)
        if not meeting:
            return False

        meeting.add_participant(agent_id, agent_type)
        return True

    def remove_participant_from_meeting(self, meeting_id: str, agent_id: str) -> bool:
        """Remove a participant from a meeting.

        Args:
            meeting_id: The meeting ID
            agent_id: The agent ID to remove

        Returns:
            True if participant was removed, False if meeting not found
        """
        meeting = self.owned_meetings.get(meeting_id)
        if not meeting:
            return False

        meeting.remove_participant(agent_id)
        return True

    def add_message_to_meeting(self, meeting_id: str, message: Message) -> bool:
        """Add a message to a meeting.

        Args:
            meeting_id: The meeting ID
            message: The message to add

        Returns:
            True if message was added, False if meeting not found
        """
        meeting = self.owned_meetings.get(meeting_id)
        if not meeting:
            return False

        meeting.add_message(message)
        return True

    def get_current_meeting_from_call_stack(self, call_stack) -> Optional[str]:
        """Get meeting ID from top meeting playbook in call stack.

        Args:
            call_stack: The agent's call stack

        Returns:
            Meeting ID if currently in a meeting, None otherwise
        """
        for frame in reversed(call_stack.frames):
            if frame.is_meeting and frame.meeting_id:
                return frame.meeting_id
        return None

    def inject_meeting_parameters(
        self, playbook_name: str, kwargs: Dict[str, Any], call_stack
    ) -> Dict[str, Any]:
        """Auto-inject meeting_id parameter for meeting playbooks.

        Args:
            playbook_name: Name of the meeting playbook
            kwargs: Current keyword arguments
            call_stack: The agent's call stack

        Returns:
            Updated kwargs with injected meeting parameters
        """
        # Only inject meeting_id for context if not already provided
        current_meeting_id = self.get_current_meeting_from_call_stack(call_stack)
        if current_meeting_id and "meeting_id" not in kwargs:
            kwargs["meeting_id"] = current_meeting_id

        return kwargs

    async def initialize_meeting_playbook(
        self,
        playbook_name: str,
        kwargs: Dict[str, Any],
        playbooks: Dict[str, Any],
        meeting_registry: MeetingRegistry,
        session_log,
        wait_for_attendees_callback,
    ):
        """Initialize meeting before executing meeting playbook.

        This method is called implicitly before any meeting playbook executes.
        For new meetings, it creates the meeting, sends invitations, and waits for required participants.
        For existing meetings (when meeting_id is provided), it joins the existing meeting.

        Args:
            playbook_name: Name of the meeting playbook being executed
            kwargs: Keyword arguments passed to the playbook
            playbooks: Dictionary of available playbooks
            meeting_registry: Registry for meeting IDs
            session_log: Session log for recording events
            wait_for_attendees_callback: Callback to wait for required attendees
        """
        # Check if we're joining an existing meeting (meeting_id provided) or creating a new one
        existing_meeting_id = kwargs.get("meeting_id")

        if existing_meeting_id:
            # Joining an existing meeting - just proceed with execution
            session_log.append(
                f"Joining existing meeting {existing_meeting_id} for playbook {playbook_name}"
            )
            return  # No need to create meeting or wait for attendees

        # Creating a new meeting
        kwargs_attendees = kwargs.get("attendees", [])
        topic = kwargs.get("topic", f"{playbook_name} meeting")

        # Determine attendee strategy: kwargs attendees take precedence
        if kwargs_attendees:
            # If attendees specified in kwargs, treat them as required
            required_attendees = kwargs_attendees
            all_attendees = kwargs_attendees
            session_log.append(
                f"Using kwargs attendees as required for meeting {playbook_name}: {required_attendees}"
            )
        else:
            # If no kwargs attendees, use metadata-defined attendees
            metadata_required, metadata_optional = self.get_playbook_attendees(
                playbook_name, playbooks
            )
            required_attendees = metadata_required
            all_attendees = list(set(metadata_required + metadata_optional))
            session_log.append(
                f"Using metadata attendees for meeting {playbook_name}: required={metadata_required}, optional={metadata_optional}"
            )

        # Filter out the requester from required attendees (they're already present)
        required_attendees_to_wait_for = [
            attendee
            for attendee in required_attendees
            if attendee != self.agent_klass and attendee != self.agent_id
        ]

        # Create the meeting
        meeting_id = await self.create_meeting(
            invited_agents=all_attendees, topic=topic, meeting_registry=meeting_registry
        )

        # Store meeting_id in kwargs for the playbook to access
        kwargs["meeting_id"] = meeting_id

        # Log the meeting initialization
        session_log.append(
            f"Initialized meeting {meeting_id} for playbook {playbook_name}"
        )

        # Wait for required attendees to join before proceeding
        await wait_for_attendees_callback(meeting_id, required_attendees_to_wait_for)

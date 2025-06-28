"""Meeting message handling functionality."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.spec_utils import SpecUtils
from .meeting import Meeting, Message

logger = logging.getLogger(__name__)


class MeetingMessageHandler:
    """Handles meeting message processing and distribution."""

    def __init__(self, agent_id: str, agent_klass: str):
        """Initialize meeting message handler.

        Args:
            agent_id: The agent's unique ID
            agent_klass: The agent's class/type
        """
        self.agent_id = agent_id
        self.agent_klass = agent_klass

    def format_meeting_messages(self, messages: List[Message]) -> str:
        """Format a list of meeting messages for display.

        Args:
            messages: List of Message objects

        Returns:
            Formatted string representation
        """
        if not messages:
            return "No messages"

        formatted = []
        for msg in messages:
            formatted.append(f"{msg.sender_type}: {msg.content}")

        return "\n".join(formatted)

    async def distribute_meeting_messages(
        self, owned_meetings: Dict[str, Meeting], route_message_callback
    ):
        """Distribute meeting messages to participants.

        Args:
            owned_meetings: Dictionary of meetings owned by the agent
            route_message_callback: Callback function to route messages
        """
        for meeting_id, meeting in owned_meetings.items():
            # Check each participant for unsent messages
            for participant_id, participant_type in meeting.participants.items():
                last_sent_index = meeting.agent_last_message_index.get(
                    participant_id, -1
                )

                # Check if there are unsent messages
                if len(meeting.message_history) > last_sent_index + 1:
                    # Send new messages as structured AgentMessage objects
                    for i in range(last_sent_index + 1, len(meeting.message_history)):
                        msg = meeting.message_history[i]
                        # Don't send participant's own messages back to them
                        if msg.sender_id != participant_id:
                            await route_message_callback(
                                self.agent_id,
                                participant_id,
                                msg.content,
                                message_type="meeting_message",
                                meeting_id=meeting_id,
                            )

                    # Update last sent index
                    meeting.agent_last_message_index[participant_id] = (
                        len(meeting.message_history) - 1
                    )

    async def handle_meeting_message(
        self,
        sender_id: str,
        message: str,
        owned_meetings: Dict[str, Meeting],
        session_log,
    ) -> bool:
        """Handle messages that might be meeting participant messages.

        Args:
            sender_id: ID of the message sender
            message: Message content
            owned_meetings: Dictionary of meetings owned by the agent
            session_log: Session log for recording events

        Returns:
            True if message was handled as a meeting message, False otherwise
        """
        if not message.startswith("MEETING:"):
            return False

        try:
            # Parse: "MEETING:meeting_id:escaped_content"
            parts = message.split(":", 2)
            if len(parts) != 3:
                return False

            meeting_id = parts[1]
            escaped_content = parts[2]

            # Verify this is a meeting I own
            if meeting_id not in owned_meetings:
                if session_log:
                    session_log.append(
                        f"Ignored meeting message for meeting {meeting_id} - not owned by me"
                    )
                return False

            meeting = owned_meetings[meeting_id]

            # Verify sender is a participant
            if sender_id not in meeting.participants:
                if session_log:
                    session_log.append(
                        f"Ignored meeting message from non-participant {sender_id} in meeting {meeting_id}"
                    )
                return False

            # Add message to meeting history
            sender_type = meeting.participants[sender_id]
            msg = Message(
                sender_id=sender_id,
                sender_type=sender_type,
                content=escaped_content,
                timestamp=datetime.now(),
                meeting_id=meeting_id,
                message_type="text",
            )

            meeting.add_message(msg)

            if session_log:
                session_log.append(
                    f"Received meeting message from {sender_type} in meeting {meeting_id}: {escaped_content}"
                )

            return True

        except Exception as e:
            if session_log:
                session_log.append(f"Error handling meeting message: {e}")
            return False

    async def handle_meeting_response(
        self, agent_message, owned_meetings: Dict[str, Meeting], session_log
    ) -> bool:
        """Handle meeting invitation responses.

        Args:
            agent_message: The agent message containing the response
            owned_meetings: Dictionary of meetings owned by the agent
            session_log: Session log for recording events

        Returns:
            True if response was handled, False otherwise
        """
        if agent_message.message_type != "meeting_response":
            return False

        meeting_id = agent_message.meeting_id
        if not meeting_id or meeting_id not in owned_meetings:
            return False

        meeting = owned_meetings[meeting_id]
        sender_id = agent_message.sender_id
        content = agent_message.content

        if content == "accept":
            # Add participant to meeting
            meeting.add_participant(sender_id, "Agent")  # Default type
            if session_log:
                session_log.append(f"Agent {sender_id} joined meeting {meeting_id}")
        elif content == "reject":
            # Remove from pending invitations
            meeting.pending_invitations.discard(sender_id)
            if session_log:
                session_log.append(f"Agent {sender_id} declined meeting {meeting_id}")

        return True

    async def invite_to_meeting(
        self,
        meeting_id: str,
        attendees: List[str],
        owned_meetings: Dict[str, Meeting],
        send_invitation_callback,
    ) -> Optional[str]:
        """Invite additional agents to an existing meeting.

        Args:
            meeting_id: ID of the meeting to invite to
            attendees: List of agent specs to invite
            owned_meetings: Dictionary of meetings owned by the agent
            send_invitation_callback: Callback to send invitations

        Returns:
            Error message if any, None if successful
        """
        # Handle "meeting " prefix if present
        if SpecUtils.is_meeting_spec(meeting_id):
            meeting_id = SpecUtils.extract_meeting_id(meeting_id)

        if meeting_id in owned_meetings:
            meeting = owned_meetings[meeting_id]
            for attendee in attendees:
                # if already a participant, don't invite again
                if (
                    meeting.participants.get(SpecUtils.extract_agent_id(attendee))
                    is not None
                ):
                    continue

                # if already invited, don't invite again
                if attendee in meeting.pending_invitations:
                    continue

                # send invitation
                await send_invitation_callback(meeting_id, attendee)

            return None
        else:
            return f"Agent {self.agent_id} doesn't own meeting {meeting_id}, so cannot invite {attendees} to it"

    async def broadcast_to_meeting(
        self,
        meeting_id: str,
        message: str,
        owned_meetings: Dict[str, Meeting],
        route_message_callback,
        session_log,
    ):
        """Broadcast a message to all meeting participants.

        Args:
            meeting_id: ID of the meeting to broadcast to
            message: Message to broadcast
            owned_meetings: Dictionary of meetings owned by the agent
            route_message_callback: Callback to route messages
            session_log: Session log for recording events
        """
        if meeting_id not in owned_meetings:
            if session_log:
                session_log.append(
                    f"Cannot broadcast to meeting {meeting_id} - not owned by this agent"
                )
            return

        meeting = owned_meetings[meeting_id]

        # Add message to meeting history
        msg = Message(
            sender_id=self.agent_id,
            sender_type=self.agent_klass,
            content=message,
            timestamp=datetime.now(),
            meeting_id=meeting_id,
            message_type="text",
        )

        meeting.add_message(msg)

        # Send to all participants except self
        for participant_id in meeting.participants:
            if participant_id != self.agent_id:
                await route_message_callback(
                    self.agent_id,
                    participant_id,
                    f"MEETING:{meeting_id}:{message}",
                    message_type="meeting_message",
                )

        if session_log:
            session_log.append(f"Broadcast message to meeting {meeting_id}: {message}")

    async def process_meeting_invitation(
        self,
        invitation_message,
        joined_meetings: Dict[str, Dict[str, Any]],
        resolve_target_callback,
        route_message_callback,
        session_log,
    ):
        """Process an incoming meeting invitation.

        Args:
            invitation_message: The invitation message
            joined_meetings: Dictionary of meetings this agent has joined
            resolve_target_callback: Callback to resolve agent targets
            route_message_callback: Callback to route messages
            session_log: Session log for recording events
        """
        meeting_id = invitation_message.meeting_id
        sender_id = invitation_message.sender_id

        if not meeting_id:
            if session_log:
                session_log.append("Received meeting invitation without meeting_id")
            return

        # Check if already in this meeting
        if meeting_id in joined_meetings:
            if session_log:
                session_log.append(
                    f"Already in meeting {meeting_id}, ignoring invitation"
                )
            return

        # Accept the invitation automatically
        joined_meetings[meeting_id] = {
            "owner_agent_id": sender_id,
            "joined_at": datetime.now(),
        }

        # Send acceptance response
        resolved_sender = resolve_target_callback(sender_id, allow_fallback=False)
        if resolved_sender:
            await route_message_callback(
                self.agent_id,
                resolved_sender,
                "accept",
                message_type="meeting_response",
                meeting_id=meeting_id,
            )

            if session_log:
                session_log.append(
                    f"Accepted invitation to meeting {meeting_id} from {sender_id}"
                )
        else:
            if session_log:
                session_log.append(f"Could not resolve invitation sender: {sender_id}")

    async def wait_for_meeting_messages(
        self, timeout: float, message_buffer: List, session_log
    ) -> Optional[str]:
        """Wait for meeting messages with buffering.

        Args:
            timeout: Timeout in seconds
            message_buffer: Buffer to store messages
            session_log: Session log for recording events

        Returns:
            Formatted meeting messages or None if timeout
        """
        import asyncio

        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if message_buffer:
                # Format and return all buffered messages
                formatted_messages = []
                for msg_data in message_buffer:
                    if isinstance(msg_data, dict) and "content" in msg_data:
                        formatted_messages.append(msg_data["content"])
                    else:
                        formatted_messages.append(str(msg_data))

                # Clear the buffer after reading
                message_buffer.clear()

                result = "\n".join(formatted_messages)
                if session_log:
                    session_log.append(
                        f"Retrieved {len(formatted_messages)} meeting messages"
                    )
                return result

            await asyncio.sleep(0.1)  # Small delay to prevent busy waiting

        if session_log:
            session_log.append(f"Meeting message wait timed out after {timeout}s")
        return None

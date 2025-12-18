"""Meeting message handling functionality."""

import logging
from typing import TYPE_CHECKING

from playbooks.agents.base_agent import BaseAgent
from playbooks.core.message import MessageType

if TYPE_CHECKING:
    from playbooks.core.message import Message

logger = logging.getLogger(__name__)


class MeetingMessageHandler:
    """Handles meeting message processing and distribution.

    Processes meeting-related messages including invitation responses
    and manages meeting state updates.
    """

    def __init__(self, agent_id: str, agent_klass: str) -> None:
        """Initialize meeting message handler.

        Args:
            agent_id: The agent's unique ID
            agent_klass: The agent's class/type
        """
        self.agent_id = agent_id
        self.agent_klass = agent_klass

    async def handle_meeting_response(
        self, agent_message: "Message", agent: BaseAgent
    ) -> bool:
        """Handle meeting invitation responses.

        Processes MEETING_INVITATION_RESPONSE messages and updates meeting
        state (adds participants who joined, marks rejections).

        Args:
            agent_message: The message containing the meeting response
            agent: The agent receiving the response (must own the meeting)

        Returns:
            True if response was handled, False if message type doesn't match
                or agent doesn't own the meeting
        """
        if agent_message.message_type != MessageType.MEETING_INVITATION_RESPONSE:
            return False

        meeting_id_obj = agent_message.meeting_id
        if not meeting_id_obj:
            return False

        meeting_id = meeting_id_obj.id
        if meeting_id not in agent.owned_meetings:
            return False

        session_log = agent.session_log
        meeting = agent.owned_meetings[meeting_id]
        sender_id = agent_message.sender_id.id
        sender = agent.program.agents_by_id.get(sender_id)
        content = agent_message.content

        if content.startswith("JOINED "):
            # Add participant to meeting
            meeting.agent_joined(sender)
            if session_log:
                session_log.append(f"{str(sender)} joined meeting {meeting_id}")
        elif content.startswith("REJECTED "):
            # Remove from pending invitations
            meeting.agent_rejected(sender)
            if session_log:
                session_log.append(f"{str(sender)} declined meeting {meeting_id}")

        return True

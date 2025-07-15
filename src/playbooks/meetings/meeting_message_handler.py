"""Meeting message handling functionality."""

import logging
from typing import TYPE_CHECKING

from playbooks.agents.base_agent import BaseAgent
from playbooks.message import MessageType

if TYPE_CHECKING:
    pass

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

    async def handle_meeting_response(self, agent_message, agent: BaseAgent) -> bool:
        """Handle meeting invitation responses.

        Args:
            agent_message: The agent message containing the response
            owned_meetings: Dictionary of meetings owned by the agent
            session_log: Session log for recording events

        Returns:
            True if response was handled, False otherwise
        """
        if agent_message.message_type != MessageType.MEETING_INVITATION_RESPONSE:
            return False

        meeting_id = agent_message.meeting_id
        if not meeting_id or meeting_id not in agent.state.owned_meetings:
            return False

        session_log = agent.state.session_log
        meeting = agent.state.owned_meetings[meeting_id]
        sender_id = agent_message.sender_id
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

"""Meeting data structure and related functionality."""

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ..agents.base_agent import BaseAgent
from ..message import Message


class MeetingInvitationStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class MeetingInvitation:
    """Represents an invitation to a meeting."""

    agent: BaseAgent
    created_at: datetime
    status: MeetingInvitationStatus = MeetingInvitationStatus.PENDING
    resolved_at: Optional[datetime] = None


@dataclass
class Meeting:
    """Represents an active meeting."""

    id: str
    created_at: datetime
    owner_id: str
    topic: Optional[str] = None

    required_attendees: List[BaseAgent] = field(default_factory=list)
    optional_attendees: List[BaseAgent] = field(default_factory=list)
    joined_attendees: List[BaseAgent] = field(default_factory=list)
    invitations: Dict[str, MeetingInvitation] = field(default_factory=dict)

    message_history: List["Message"] = field(
        default_factory=list
    )  # All messages in this meeting
    agent_last_message_index: Dict[str, int] = field(default_factory=dict)

    def agent_joined(self, agent: BaseAgent) -> None:
        """Add a participant to the meeting."""
        self.joined_attendees.append(agent)
        invitation = self.invitations.get(agent.id)
        if invitation:
            invitation.status = MeetingInvitationStatus.ACCEPTED
            invitation.resolved_at = datetime.now()

    def agent_rejected(self, agent: BaseAgent) -> None:
        invitation = self.invitations.get(agent.id)
        if invitation:
            invitation.status = MeetingInvitationStatus.REJECTED
            invitation.resolved_at = datetime.now()

    def agent_left(self, agent: BaseAgent) -> None:
        """Remove a participant from the meeting."""
        self.joined_attendees.remove(agent)
        self.agent_last_message_index.pop(agent.id, None)

    def has_pending_invitations(self) -> bool:
        """Check if there are any pending invitations."""
        return any(
            invitation.status == MeetingInvitationStatus.PENDING
            for invitation in self.invitations.values()
        )

    def missing_required_attendees(self) -> List[BaseAgent]:
        """Get the list of required attendees that are not present."""
        return [
            attendee
            for attendee in self.required_attendees
            if attendee not in self.joined_attendees
        ]

    def log_message(self, message: "Message") -> None:
        """Add a message to the meeting history."""
        self.message_history.append(message)

    def get_unread_messages(self, agent: BaseAgent) -> List["Message"]:
        """Get unread messages for a specific agent."""
        last_index = self.agent_last_message_index.get(agent.id, 0)
        return self.message_history[last_index:]

    def mark_messages_read(self, agent: BaseAgent) -> None:
        """Mark all messages as read for a specific agent."""
        self.agent_last_message_index[agent.id] = len(self.message_history)

    def is_participant(self, agent: BaseAgent) -> bool:
        """Check if an agent is a participant in the meeting."""
        return agent in self.joined_attendees

    def has_pending_invitation(self, agent: BaseAgent) -> bool:
        """Check if an agent has a pending invitation."""
        return (
            agent.id in self.invitations
            and self.invitations[agent.id].status == MeetingInvitationStatus.PENDING
        )


@dataclass
class JoinedMeeting:
    """Represents a meeting that an agent has joined."""

    id: str
    owner_id: str
    joined_at: datetime
    topic: Optional[str] = None

"""Meeting data structure and related functionality."""

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from box import Box

from playbooks.agents.base_agent import BaseAgent
from playbooks.core.message import Message


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

    shared_state: Box = field(default_factory=lambda: Box(default_box=True))

    def __repr__(self) -> str:
        """Return a string representation of the meeting."""
        attendee_strs = [f"{a.klass}(agent {a.id})" for a in self.joined_attendees]
        topic_str = f'"{self.topic}"' if self.topic else "None"
        return f'Meeting<id="{self.id}", topic={topic_str}, owner="agent {self.owner_id}", attendees={attendee_strs}>'

    def agent_joined(self, agent: BaseAgent) -> None:
        """Add a participant to the meeting."""
        self.joined_attendees.append(agent)
        invitation = self.invitations.get(agent.id)
        if invitation:
            invitation.status = MeetingInvitationStatus.ACCEPTED
            invitation.resolved_at = datetime.now()

    def get_humans(self) -> List["BaseAgent"]:
        """Get all human participants in the meeting.

        Returns:
            List of HumanAgent instances in joined_attendees
        """
        from playbooks.agents.human_agent import HumanAgent

        return [
            agent for agent in self.joined_attendees if isinstance(agent, HumanAgent)
        ]

    def should_stream_to_human(self, human_id: str, message: "Message") -> bool:
        """Determine if a message should be streamed to a specific human.

        Checks the human's delivery preferences to decide if streaming should
        be used for this message.

        Args:
            human_id: The human agent ID to check
            message: The message being sent

        Returns:
            True if message should be streamed to this human, False otherwise
        """
        from playbooks.agents.human_agent import HumanAgent

        # Find the human in participants
        human = None
        for agent in self.joined_attendees:
            if isinstance(agent, HumanAgent) and agent.id == human_id:
                human = agent
                break

        if not human:
            return False

        # Check if streaming is enabled for this human
        if not human.delivery_preferences.streaming_enabled:
            return False

        # Check meeting notification preferences
        prefs = human.delivery_preferences.meeting_notifications

        if prefs == "none":
            # Human doesn't want meeting notifications
            return False

        if prefs == "all":
            # Human wants all meeting messages
            return True

        # prefs == "targeted" - only stream if human is targeted
        if message.target_agent_ids and human_id in [
            aid.id for aid in message.target_agent_ids
        ]:
            return True

        # Check if human is mentioned in message content
        if human.name.lower() in message.content.lower():
            return True

        if human.klass.lower() in message.content.lower():
            return True

        # Not targeted - don't stream
        return False

    def agent_rejected(self, agent: BaseAgent) -> None:
        """Mark an agent's invitation as rejected.

        Args:
            agent: The agent that rejected the invitation
        """
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
        """Add a message to the meeting history.

        Args:
            message: Message to add to the history
        """
        self.message_history.append(message)

    def get_unread_messages(self, agent: BaseAgent) -> List["Message"]:
        """Get unread messages for a specific agent.

        Args:
            agent: Agent to get unread messages for

        Returns:
            List of unread messages since the agent's last read index
        """
        last_index = self.agent_last_message_index.get(agent.id, 0)
        return self.message_history[last_index:]

    def mark_messages_read(self, agent: BaseAgent) -> None:
        """Mark all messages as read for a specific agent.

        Args:
            agent: Agent whose messages should be marked as read
        """
        self.agent_last_message_index[agent.id] = len(self.message_history)

    def is_participant(self, agent_id: str) -> bool:
        """Check if an agent is a participant in the meeting.

        Args:
            agent_id: Agent id to check

        Returns:
            True if agent is in joined_attendees, False otherwise
        """
        return any(a.id == agent_id for a in self.joined_attendees)

    def has_pending_invitation(self, agent: BaseAgent) -> bool:
        """Check if an agent has a pending invitation.

        Args:
            agent: Agent to check

        Returns:
            True if agent has a pending invitation, False otherwise
        """
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
    shared_state: Box = field(default_factory=lambda: Box(default_box=True))

    def __repr__(self) -> str:
        """Return a string representation of the joined meeting."""
        topic_str = f'"{self.topic}"' if self.topic else "None"
        return f'JoinedMeeting<id="{self.id}", topic={topic_str}, owner="agent {self.owner_id}">'

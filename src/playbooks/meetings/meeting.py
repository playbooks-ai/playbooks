"""Meeting data structure and related functionality."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set


@dataclass
class Meeting:
    """Represents an active meeting."""

    meeting_id: str
    initiator_id: str
    participants: Dict[str, str]  # agent_id -> agent_type
    created_at: datetime
    topic: Optional[str] = None
    message_history: List["Message"] = None  # All messages in this meeting
    agent_last_message_index: Dict[
        str, int
    ] = None  # agent_id -> last message index they received
    pending_invitations: Set[
        str
    ] = None  # set of agent_specs that have been invited but not yet joined/rejected

    def __post_init__(self):
        if self.message_history is None:
            self.message_history = []
        if self.agent_last_message_index is None:
            self.agent_last_message_index = {}
        if self.pending_invitations is None:
            self.pending_invitations = set()

    def add_participant(self, agent_id: str, agent_type: str) -> None:
        """Add a participant to the meeting."""
        self.participants[agent_id] = agent_type
        self.pending_invitations.discard(agent_id)

    def remove_participant(self, agent_id: str) -> None:
        """Remove a participant from the meeting."""
        self.participants.pop(agent_id, None)
        self.agent_last_message_index.pop(agent_id, None)

    def add_message(self, message: "Message") -> None:
        """Add a message to the meeting history."""
        self.message_history.append(message)

    def get_unread_messages(self, agent_id: str) -> List["Message"]:
        """Get unread messages for a specific agent."""
        last_index = self.agent_last_message_index.get(agent_id, 0)
        return self.message_history[last_index:]

    def mark_messages_read(self, agent_id: str) -> None:
        """Mark all messages as read for a specific agent."""
        self.agent_last_message_index[agent_id] = len(self.message_history)

    def is_participant(self, agent_id: str) -> bool:
        """Check if an agent is a participant in the meeting."""
        return agent_id in self.participants

    def has_pending_invitation(self, agent_id: str) -> bool:
        """Check if an agent has a pending invitation."""
        return agent_id in self.pending_invitations


@dataclass
class Message:
    """Represents a message in the system."""

    sender_id: str
    sender_type: str
    content: str
    timestamp: datetime
    meeting_id: Optional[str] = None
    message_type: str = "text"

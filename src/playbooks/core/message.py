"""Message classes and types for inter-agent communication.

This module defines the message structures used for communication between
agents, including different message types for direct communication,
meetings, and system messages.
"""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from playbooks.core.identifiers import AgentID, MeetingID
from playbooks.utils.text_utils import simple_shorten


class MessageType(enum.Enum):
    """Types of messages in the system.

    Attributes:
        DIRECT: Direct agent-to-agent message
        MEETING_BROADCAST_REQUEST: Request to broadcast to a meeting
        MEETING_BROADCAST: Broadcast message within a meeting
        MEETING_INVITATION: Invitation to join a meeting
        MEETING_INVITATION_RESPONSE: Response to a meeting invitation
    """

    DIRECT = "direct"
    MEETING_BROADCAST_REQUEST = "meeting_broadcast_request"
    MEETING_BROADCAST = "meeting_broadcast"
    MEETING_INVITATION = "meeting_invitation"
    MEETING_INVITATION_RESPONSE = "meeting_invitation_response"


@dataclass
class Message:
    """Represents a message in the system.

    Messages are used for inter-agent communication, meeting broadcasts,
    and system notifications. Supports both direct and meeting-based routing.

    Attributes:
        sender_id: ID of the sending agent
        sender_klass: Class name of the sending agent
        recipient_id: ID of the recipient agent (None for broadcasts)
        recipient_klass: Class name of the recipient agent (None for broadcasts)
        message_type: Type of message (direct, meeting broadcast, etc.)
        content: Message content text
        meeting_id: Meeting ID if this is a meeting message (None otherwise)
        target_agent_ids: List of agent IDs explicitly targeted in meetings
            (used for differential timeouts - targeted agents respond faster)
        stream_id: Unique identifier for streaming operations (None if not streaming)
        id: Unique message identifier (auto-generated UUID)
        created_at: Timestamp when message was created
    """

    sender_id: AgentID
    sender_klass: str

    recipient_id: Optional[AgentID]
    recipient_klass: Optional[str]

    message_type: MessageType
    content: str

    meeting_id: Optional[MeetingID]

    # Agent targeting for differential timeouts in meetings
    target_agent_ids: Optional[List[AgentID]] = None

    # Streaming support
    stream_id: Optional[str] = None

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    def __str__(self, compact: bool = False) -> str:
        """Return human-readable string representation of the message."""
        message_type = (
            "MEETING INVITATION"
            if self.message_type == MessageType.MEETING_INVITATION
            else "Message"
        )

        if self.sender_klass is None:
            sender = ""
        elif self.sender_id.id == "human" or self.sender_klass == "HumanAgent":
            sender = "from human"
        else:
            sender = f"from {self.sender_klass}({self.sender_id.id})"

        if self.recipient_klass is None or self.recipient_id is None:
            target = "to everyone"
        elif self.recipient_id.id == "human" or self.recipient_klass == "HumanAgent":
            target = "to human"
        else:
            target = f"to {self.recipient_klass}({self.recipient_id.id})"

        meeting_message = f"in meeting {self.meeting_id.id}" if self.meeting_id else ""

        content = self.content
        if compact:
            content = simple_shorten(content, 100)

        return " ".join([message_type, sender, target, meeting_message, ":", content])

    def to_compact_str(self) -> str:
        """Return compact string representation for LLM context.

        Format: "SenderKlass(sender_id) → RecipientKlass(recipient_id): content"
        Example: "StoryTeller(1000) → CharacterCreator(1001): Hi! Could you..."
        For meeting invitations: includes "[MEETING_INVITATION for meeting {meeting_id}]"
        Human agents show as just "User" without ID.

        Returns:
            Compact string representation similar to CLI output format
        """
        # Format sender
        if self.sender_id.id == "human" or self.sender_klass == "HumanAgent":
            sender = "User"
        else:
            sender = f"{self.sender_klass}({self.sender_id.id})"

        # Format recipient
        if self.recipient_id and self.recipient_id.id == "human":
            recipient = "User"
        elif self.recipient_klass is None or self.recipient_id is None:
            recipient = "Everyone"
        else:
            recipient = f"{self.recipient_klass}({self.recipient_id.id})"

        # Add meeting invitation indicator
        if self.message_type == MessageType.MEETING_INVITATION:
            meeting_info = (
                f" [MEETING_INVITATION for meeting {self.meeting_id.id}]"
                if self.meeting_id
                else ""
            )
        elif self.message_type == MessageType.MEETING_BROADCAST:
            meeting_info = (
                f" [in meeting {self.meeting_id.id}]" if self.meeting_id else ""
            )
        else:
            meeting_info = ""

        # Shorten content
        content = simple_shorten(self.content, 100)

        return f"{sender} → {recipient}{meeting_info}: {content}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation.

        Returns:
            Dictionary with message fields (excludes streaming and targeting metadata)
        """
        return {
            "sender_id": self.sender_id.id,
            "sender_klass": self.sender_klass,
            "recipient_id": self.recipient_id.id if self.recipient_id else None,
            "recipient_klass": self.recipient_klass,
            "message_type": self.message_type.value,
            "content": self.content,
            "meeting_id": self.meeting_id.id if self.meeting_id else None,
        }

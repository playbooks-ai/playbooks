"""Message classes and types for inter-agent communication.

This module defines the message structures used for communication between
agents, including different message types for direct communication,
meetings, and system messages.
"""

import enum
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


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

    sender_id: str
    sender_klass: str

    recipient_id: Optional[str]
    recipient_klass: Optional[str]

    message_type: MessageType
    content: str

    meeting_id: Optional[str]

    # Agent targeting for differential timeouts in meetings
    target_agent_ids: Optional[List[str]] = None

    # Streaming support
    stream_id: Optional[str] = None

    id: str = uuid.uuid4()
    created_at: datetime = datetime.now()

    def __str__(self) -> str:
        """Return human-readable string representation of the message."""
        meeting_message = f", in meeting {self.meeting_id}" if self.meeting_id else ""
        message_type = (
            "[MEETING INVITATION] "
            if self.message_type == MessageType.MEETING_INVITATION
            else ""
        )
        return f"{message_type}Message from {self.sender_klass}(agent {self.sender_id}) to {self.recipient_klass}(agent {self.recipient_id}){meeting_message}: {self.content}"

    def to_compact_str(self) -> str:
        """Return compact string representation for LLM context.

        Format: "SenderKlass(agent sender_id) → RecipientKlass(recipient_id): content"
        Example: "StoryTeller(agent 1000) → CharacterCreator(agent 1001): Hi! Could you..."

        Returns:
            Compact string representation similar to CLI output format
        """
        # Format sender
        sender = f"{self.sender_klass}(agent {self.sender_id})"

        # Format recipient
        if self.recipient_id and self.recipient_klass:
            if self.recipient_id == "user" or self.recipient_klass == "Human":
                recipient = f"{self.recipient_klass}({self.recipient_id})"
            else:
                recipient = f"{self.recipient_klass}(agent {self.recipient_id})"
        else:
            recipient = "all"

        # Format message content (truncate if very long)
        content = self.content
        if len(content) > 100:
            content = content[:97] + "..."

        return f"{sender} → {recipient}: {content}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation.

        Returns:
            Dictionary with message fields (excludes streaming and targeting metadata)
        """
        return {
            "sender_id": self.sender_id,
            "sender_klass": self.sender_klass,
            "recipient_id": self.recipient_id,
            "recipient_klass": self.recipient_klass,
            "message_type": self.message_type.value,
            "content": self.content,
            "meeting_id": self.meeting_id,
        }

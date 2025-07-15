import enum
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class MessageType(enum.Enum):
    DIRECT = "direct"
    MEETING_BROADCAST_REQUEST = "meeting_broadcast_request"
    MEETING_BROADCAST = "meeting_broadcast"
    MEETING_INVITATION = "meeting_invitation"
    MEETING_INVITATION_RESPONSE = "meeting_invitation_response"


@dataclass
class Message:
    """Represents a message in the system."""

    sender_id: str
    sender_klass: str

    recipient_id: Optional[str]
    recipient_klass: Optional[str]

    message_type: MessageType
    content: str

    meeting_id: Optional[str]

    id: str = uuid.uuid4()
    created_at: datetime = datetime.now()

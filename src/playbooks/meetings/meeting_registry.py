"""Meeting ID registry for generating unique meeting identifiers."""

from typing import Optional


class MeetingRegistry:
    """Registry for managing meeting ID generation and lookup."""

    def __init__(self, start_id: int = 100):
        """Initialize the registry with a starting ID.

        Args:
            start_id: The starting ID for meetings (default: 100)
        """
        self._next_id = start_id
        self._meeting_owners = {}  # meeting_id -> owner_agent_id

    def generate_meeting_id(self, owner_agent_id: str) -> str:
        """Generate a new unique meeting ID.

        Args:
            owner_agent_id: The ID of the agent creating the meeting

        Returns:
            New unique meeting ID as string
        """
        meeting_id = str(self._next_id)
        self._next_id += 1
        self._meeting_owners[meeting_id] = owner_agent_id
        return meeting_id

    def get_meeting_owner(self, meeting_id: str) -> Optional[str]:
        """Get the owner agent ID for a meeting.

        Args:
            meeting_id: The meeting ID to look up

        Returns:
            Owner agent ID if found, None otherwise
        """
        return self._meeting_owners.get(meeting_id)

    def register_meeting(self, meeting_id: str, owner_agent_id: str) -> None:
        """Register a meeting with its owner.

        Args:
            meeting_id: The meeting ID
            owner_agent_id: The owner agent ID
        """
        self._meeting_owners[meeting_id] = owner_agent_id

    def unregister_meeting(self, meeting_id: str) -> None:
        """Unregister a meeting.

        Args:
            meeting_id: The meeting ID to unregister
        """
        self._meeting_owners.pop(meeting_id, None)

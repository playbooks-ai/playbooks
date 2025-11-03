"""Meeting ID registry for generating unique meeting identifiers."""


class MeetingRegistry:
    """Registry for managing meeting ID generation and lookup."""

    def __init__(self, start_id: int = 100):
        """Initialize the registry with a starting ID.

        Args:
            start_id: The starting ID for meetings (default: 100)
        """
        self._next_id = start_id

    def generate_meeting_id(self) -> str:
        """Generate a new unique meeting ID.

        Returns:
            New unique meeting ID as string (sequential, starting from start_id)
        """
        meeting_id = str(self._next_id)
        self._next_id += 1
        return meeting_id

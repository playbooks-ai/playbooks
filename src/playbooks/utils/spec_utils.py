"""Utilities for handling agent and meeting specifications and IDs."""


class SpecUtils:
    """Centralized utilities for handling agent and meeting specs/IDs."""

    # Constants for prefixes
    AGENT_PREFIX = "agent "
    MEETING_PREFIX = "meeting "

    @classmethod
    def is_agent_spec(cls, value: str) -> bool:
        """Check if value is an agent specification."""
        return value.startswith(cls.AGENT_PREFIX)

    @classmethod
    def is_meeting_spec(cls, value: str) -> bool:
        """Check if value is a meeting specification."""
        return value.startswith(cls.MEETING_PREFIX)

    @classmethod
    def extract_agent_id(cls, agent_spec: str) -> str:
        """Extract agent ID from agent specification.

        Args:
            agent_spec: Agent specification (e.g., "agent 1000") or raw ID (e.g., "1000")

        Returns:
            Agent ID without prefix (e.g., "1000")
        """
        if cls.is_agent_spec(agent_spec):
            return agent_spec[len(cls.AGENT_PREFIX) :].strip()
        return agent_spec  # Already an ID

    @classmethod
    def extract_meeting_id(cls, meeting_spec: str) -> str:
        """Extract meeting ID from meeting specification.

        Args:
            meeting_spec: Meeting specification (e.g., "meeting 123") or raw ID (e.g., "123")

        Returns:
            Meeting ID without prefix (e.g., "123")
        """
        if cls.is_meeting_spec(meeting_spec):
            return meeting_spec[len(cls.MEETING_PREFIX) :].strip()
        return meeting_spec  # Already an ID

    @classmethod
    def to_agent_spec(cls, agent_id: str) -> str:
        """Convert agent ID to agent specification.

        Args:
            agent_id: Agent ID (e.g., "1000") or existing spec (e.g., "agent 1000")

        Returns:
            Agent specification with prefix (e.g., "agent 1000")
        """
        if cls.is_agent_spec(agent_id):
            return agent_id  # Already a spec
        return f"{cls.AGENT_PREFIX}{agent_id}"

    @classmethod
    def to_meeting_spec(cls, meeting_id: str) -> str:
        """Convert meeting ID to meeting specification.

        Args:
            meeting_id: Meeting ID (e.g., "123") or existing spec (e.g., "meeting 123")

        Returns:
            Meeting specification with prefix (e.g., "meeting 123")
        """
        if cls.is_meeting_spec(meeting_id):
            return meeting_id  # Already a spec
        return f"{cls.MEETING_PREFIX}{meeting_id}"

"""Structured identifier types for type-safe entity references.

This module provides structured types to replace stringly-typed agent and meeting IDs
throughout the codebase. Parse once at API boundaries, use structured types internally.
"""

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class AgentID:
    """Structured agent identifier.

    Replaces ambiguous string formats like "agent 1234", "1234", "human", etc.
    with a single, unambiguous type.

    Examples:
        AgentID.parse("agent 1234") -> AgentID(id="1234")
        AgentID.parse("1234") -> AgentID(id="1234")
        AgentID.parse("human") -> AgentID(id="human")
        str(AgentID("1234")) -> "agent 1234"
    """

    id: str

    def __str__(self) -> str:
        """Return spec format for LLM consumption and display."""
        return f"agent {self.id}"

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return f"AgentID({self.id!r})"

    @classmethod
    def parse(cls, spec_or_id: str) -> "AgentID":
        """Parse agent ID from any accepted format.

        Args:
            spec_or_id: Agent specification in any format:
                - "agent 1234" (spec format)
                - "1234" (raw ID)
                - "human" or "user" (human aliases)

        Returns:
            AgentID instance

        Raises:
            ValueError: If spec_or_id is empty or invalid
        """
        if not spec_or_id:
            raise ValueError("Agent spec/ID cannot be empty")

        # Strip whitespace first for consistent parsing
        spec_or_id = spec_or_id.strip()

        if not spec_or_id:
            raise ValueError("Agent spec/ID cannot be empty (whitespace only)")

        # Handle human aliases - normalize to "human"
        if spec_or_id.lower() in ("human", "user"):
            return cls(id="human")

        # Handle spec format "agent 1234"
        if spec_or_id.startswith("agent "):
            agent_id = spec_or_id[6:].strip()
            if not agent_id:
                raise ValueError(f"Invalid agent spec: '{spec_or_id}' (missing ID)")
            return cls(id=agent_id)

        # Assume raw ID (already validated non-empty above)
        return cls(id=spec_or_id)

    def __eq__(self, other: object) -> bool:
        """Equality based on ID only.

        Args:
            other: Object to compare

        Returns:
            True if other is an AgentID with the same id, False otherwise
        """
        if isinstance(other, AgentID):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        """Hash based on ID for use in sets and dicts."""
        return hash(self.id)


@dataclass(frozen=True)
class MeetingID:
    """Structured meeting identifier.

    Replaces ambiguous string formats like "meeting 112", "112", etc.
    with a single, unambiguous type.

    Examples:
        MeetingID.parse("meeting 112") -> MeetingID(id="112")
        MeetingID.parse("112") -> MeetingID(id="112")
        str(MeetingID("112")) -> "meeting 112"
    """

    id: str

    def __str__(self) -> str:
        """Return spec format for LLM consumption and display."""
        return f"meeting {self.id}"

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return f"MeetingID({self.id!r})"

    @classmethod
    def parse(cls, spec_or_id: str) -> "MeetingID":
        """Parse meeting ID from any accepted format.

        Args:
            spec_or_id: Meeting specification in any format:
                - "meeting 112" (spec format)
                - "112" (raw ID)

        Returns:
            MeetingID instance

        Raises:
            ValueError: If spec_or_id is empty or invalid
        """
        if not spec_or_id:
            raise ValueError("Meeting spec/ID cannot be empty")

        # Strip whitespace first for consistent parsing
        spec_or_id = spec_or_id.strip()

        if not spec_or_id:
            raise ValueError("Meeting spec/ID cannot be empty (whitespace only)")

        # Handle spec format "meeting 112"
        if spec_or_id.startswith("meeting "):
            meeting_id = spec_or_id[8:].strip()
            if not meeting_id:
                raise ValueError(f"Invalid meeting spec: '{spec_or_id}' (missing ID)")
            return cls(id=meeting_id)

        # Assume raw ID (already validated non-empty above)
        return cls(id=spec_or_id)

    def __eq__(self, other: object) -> bool:
        """Equality based on ID only.

        Args:
            other: Object to compare

        Returns:
            True if other is a MeetingID with the same id, False otherwise
        """
        if isinstance(other, MeetingID):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        """Hash based on ID for use in sets and dicts."""
        return hash(self.id)


# Union type for routing - an entity can be either an agent or a meeting
EntityID = Union[AgentID, MeetingID]


class IDParser:
    """Parser for converting string specs to structured ID types.

    Use this at API boundaries to parse user/LLM input once,
    then use structured types internally throughout the codebase.
    """

    @staticmethod
    def parse(spec: str) -> EntityID:
        """Parse a spec string into the appropriate structured ID type.

        Args:
            spec: Entity specification (agent or meeting):
                - "agent 1234" -> AgentID
                - "meeting 112" -> MeetingID
                - "human" -> AgentID
                - "1234" -> AgentID (default to agent if ambiguous)

        Returns:
            AgentID or MeetingID

        Raises:
            ValueError: If spec is empty or invalid
        """
        if not spec:
            raise ValueError("Entity spec cannot be empty")

        spec = spec.strip()

        # Meeting specs are explicit
        if spec.startswith("meeting "):
            return MeetingID.parse(spec)

        # Everything else defaults to agent
        return AgentID.parse(spec)

    @staticmethod
    def parse_agent(spec_or_id: str) -> AgentID:
        """Parse an agent ID (alias for AgentID.parse for clarity)."""
        return AgentID.parse(spec_or_id)

    @staticmethod
    def parse_meeting(spec_or_id: str) -> MeetingID:
        """Parse a meeting ID (alias for MeetingID.parse for clarity)."""
        return MeetingID.parse(spec_or_id)

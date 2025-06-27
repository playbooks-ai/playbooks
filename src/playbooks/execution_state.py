"""Execution state management for the interpreter.

This module provides the ExecutionState class, which encapsulates the state
tracked during interpreter execution, including call stack, exit conditions,
and execution control flags.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from playbooks.artifacts import Artifacts
from playbooks.call_stack import CallStack
from playbooks.event_bus import EventBus
from playbooks.session_log import SessionLog
from playbooks.variables import Variables


@dataclass
class Meeting:
    """Represents an active meeting."""

    meeting_id: str
    playbook_name: str
    initiator_id: str
    participants: Dict[str, str]  # agent_id -> agent_type
    created_at: datetime
    topic: Optional[str] = None


@dataclass
class Message:
    """Represents a message in the system."""

    sender_id: str
    sender_type: str
    content: str
    timestamp: datetime
    meeting_id: Optional[str] = None
    message_type: str = "text"


class MeetingManager:
    """Mixin for managing meeting state data only."""

    def __init__(self):
        self.meetings: Dict[str, Meeting] = {}
        self.invitations: Dict[str, Set[str]] = {}  # agent_id -> meeting_ids

    def handle_join_request(
        self, agent_id: str, agent_type: str, meeting_id: str
    ) -> bool:
        """Process agent joining meeting (state update only).

        Args:
            agent_id: ID of the agent joining
            agent_type: Type of the joining agent
            meeting_id: ID of the meeting to join

        Returns:
            True if successfully joined, False otherwise
        """
        if meeting_id not in self.meetings:
            return False

        meeting = self.meetings[meeting_id]
        meeting.participants[agent_id] = agent_type

        # Remove from pending invitations
        if agent_id in self.invitations:
            self.invitations[agent_id].discard(meeting_id)
            if not self.invitations[agent_id]:
                del self.invitations[agent_id]

        return True


class ExecutionState(MeetingManager):
    """Encapsulates execution state including call stack, variables, and artifacts.

    Attributes:
        bus: The event bus
        session_log: Log of session activity
        call_stack: Stack tracking the execution path
        variables: Collection of variables with change history
        artifacts: Store for execution artifacts
    """

    def __init__(self, event_bus: EventBus):
        """Initialize execution state with an event bus.

        Args:
            bus: The event bus to use for all components
        """
        MeetingManager.__init__(self)
        self.event_bus = event_bus
        self.session_log = SessionLog()
        self.call_stack = CallStack(event_bus)
        self.variables = Variables(event_bus)
        self.artifacts = Artifacts()
        self.agents: List[Dict[str, Any]] = []
        self.last_llm_response = ""
        self.last_message_target = (
            None  # Track last 1:1 message target for Say() fallback
        )

    def __repr__(self) -> str:
        """Return a string representation of the execution state."""
        return f"{self.call_stack.__repr__()};{self.variables.__repr__()};{self.artifacts.__repr__()}"

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the execution state."""
        # Build meetings list for LLM visibility
        meetings_list = []
        for meeting_id, meeting in self.meetings.items():
            participants_list = []
            for participant_id, participant_type in meeting.participants.items():
                participants_list.append(
                    {"type": participant_type, "agent_id": participant_id}
                )

            meetings_list.append(
                {"meeting_id": meeting_id, "participants": participants_list}
            )

        return {
            "call_stack": [
                frame.instruction_pointer.to_compact_str()
                for frame in self.call_stack.frames
            ],
            "variables": self.variables.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "agents": self.agents,
            "meetings": meetings_list,
        }

    def __str__(self) -> str:
        """Return a string representation of the execution state."""
        return f"ExecutionState(call_stack={self.call_stack}, variables={self.variables}, session_log={self.session_log})"

    def get_current_meeting(self) -> Optional[str]:
        """Get meeting ID from top meeting playbook in call stack.

        Returns:
            Meeting ID if currently in a meeting, None otherwise
        """
        for frame in reversed(self.call_stack.frames):
            if frame.is_meeting and frame.meeting_id:
                return frame.meeting_id
        return None

"""Execution state management for the interpreter.

This module provides the ExecutionState class, which encapsulates the state
tracked during interpreter execution, including call stack, exit conditions,
and execution control flags.
"""

from typing import Any, Dict, List, Optional

from playbooks.call_stack import CallStack
from playbooks.event_bus import EventBus
from playbooks.meetings import JoinedMeeting, Meeting
from playbooks.session_log import SessionLog
from playbooks.variables import Variables


class ExecutionState:
    """Encapsulates execution state including call stack, variables, and artifacts.

    Attributes:
        bus: The event bus
        session_log: Log of session activity
        call_stack: Stack tracking the execution path
        variables: Collection of variables with change history
        artifacts: Store for execution artifacts
    """

    def __init__(self, event_bus: EventBus, klass: str, agent_id: str) -> None:
        """Initialize execution state with an event bus.

        Args:
            event_bus: The event bus to use for all components
            klass: Agent class name
            agent_id: Agent identifier
        """
        self.event_bus = event_bus
        self.klass = klass
        self.agent_id = agent_id
        self.session_log = SessionLog(klass, agent_id)
        self.call_stack = CallStack(event_bus, agent_id)
        self.variables = Variables(event_bus, agent_id)
        self.agents: List[Dict[str, Any]] = []
        self.last_llm_response = ""
        self.last_message_target = (
            None  # Track last 1:1 message target for Say() fallback
        )

        # Meetings initiated by this agent (agent is the owner/host)
        self.owned_meetings: Dict[str, "Meeting"] = {}  # meeting_id -> Meeting

        # Meetings this agent has joined as a participant
        self.joined_meetings: Dict[str, JoinedMeeting] = {}

    def __repr__(self) -> str:
        """Return a string representation of the execution state."""
        return f"{self.call_stack.__repr__()};{self.variables.__repr__()}"

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the execution state.

        Returns:
            Dictionary containing call stack, variables, agents, and meetings
        """
        # Owned meetings
        owned_meetings_list = []
        joined_meetings_list = []

        for meeting_id, meeting in self.owned_meetings.items():
            participants_list = []
            for participant in meeting.joined_attendees:
                participants_list.append(f"{participant.klass}(agent {participant.id})")
            owned_meetings_list.append(
                {
                    "meeting_id": meeting_id,
                    "participants": participants_list,
                    "topic": meeting.topic,
                }
            )
            joined_meetings_list.append(
                {
                    "meeting_id": meeting_id,
                    "owner": f"Owned by me - agent {meeting.owner_id}",
                    "topic": meeting.topic,
                }
            )

        # Joined meetings
        for meeting_id, meeting in self.joined_meetings.items():
            joined_meetings_list.append(
                {
                    "meeting_id": meeting_id,
                    "owner": f"agent {meeting.owner_id}",
                    "topic": meeting.topic,
                }
            )

        return {
            "call_stack": [
                frame.instruction_pointer.to_compact_str()
                for frame in self.call_stack.frames
            ],
            "variables": self.variables.to_dict(),
            "agents": self.agents,
            "owned_meetings": owned_meetings_list,
            "joined_meetings": joined_meetings_list,
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

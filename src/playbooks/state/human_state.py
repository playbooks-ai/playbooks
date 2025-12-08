"""Human agent state management.

This module provides HumanState, a minimal state class for human agents.
Unlike AI agents, humans don't execute playbooks, so they don't need
call stacks, variables, or session logs.
"""

from typing import Dict, Optional

from playbooks.infrastructure.event_bus import EventBus
from playbooks.meetings import JoinedMeeting


class HumanState:
    """Minimal state for human agents.

    Human agents don't execute playbooks, so they only need:
    - Meeting participation tracking (joined meetings)
    - Basic identification (klass, agent_id)

    Unlike AIAgent state, this doesn't include:
    - CallStack (humans don't execute playbooks)
    - Variables (humans don't have execution variables)
    - SessionLog (humans don't have LLM execution history)
    """

    def __init__(self, event_bus: EventBus, klass: str, agent_id: str) -> None:
        """Initialize human state.

        Args:
            event_bus: The event bus (for consistency with AIAgent interface)
            klass: The human agent class name
            agent_id: The human agent ID
        """
        self.event_bus = event_bus
        self.klass = klass
        self.agent_id = agent_id

        # Track meetings this human has joined
        self.joined_meetings: Dict[str, JoinedMeeting] = {}

    def get_current_meeting(self) -> Optional[str]:
        """Get the current meeting ID if in a meeting.

        Returns:
            Meeting ID if in a meeting, None otherwise
        """
        # Humans can only be in one meeting at a time
        # Return the most recently joined meeting that's still active
        if self.joined_meetings:
            # Return the first (and should be only) meeting
            return next(iter(self.joined_meetings.keys()))
        return None

    def __repr__(self) -> str:
        """Return a string representation of the human state."""
        return f"HumanState(klass={self.klass}, agent_id={self.agent_id}, meetings={len(self.joined_meetings)})"

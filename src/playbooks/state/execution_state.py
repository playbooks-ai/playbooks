"""Execution state management for the interpreter.

This module provides the ExecutionState class, which encapsulates the state
tracked during interpreter execution, including call stack, exit conditions,
and execution control flags.
"""

from typing import Any, Dict, List, Optional

from dotmap import DotMap

from playbooks.config import config as global_config
from playbooks.infrastructure.event_bus import EventBus
from playbooks.llm.messages.types import FrameType
from playbooks.meetings import JoinedMeeting, Meeting
from playbooks.state.call_stack import CallStack
from playbooks.state.session_log import SessionLog
from playbooks.state.variables import VariablesTracker


class ExecutionState:
    """Encapsulates execution state including call stack, variables, and artifacts.

    Attributes:
        bus: The event bus
        session_log: Log of session activity
        call_stack: Stack tracking the execution path (includes top-level messages)
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
        self.variables = DotMap()
        self.previous_variables: Optional[Dict[str, Any]] = None
        self.agents: List[Dict[str, Any]] = []
        self.last_llm_response = ""
        self.last_message_target = None

        # Meetings
        self.owned_meetings: Dict[str, "Meeting"] = {}
        self.joined_meetings: Dict[str, JoinedMeeting] = {}

        # State compression tracking (I-frame/P-frame strategy)
        self.last_sent_state: Optional[Dict[str, Any]] = None
        self.last_i_frame_execution_id: Optional[int] = None

    def __repr__(self) -> str:
        """Return a string representation of the execution state."""
        return f"{self.call_stack.__repr__()};{self.variables.__repr__()}"

    def to_dict(self, full: bool = True) -> Dict[str, Any]:
        """Return a dictionary representation of the execution state.

        Args:
            full: If True, return full state. If False, return delta from last_sent_state.

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

        full_state = {
            "call_stack": [
                frame.instruction_pointer.to_compact_str()
                for frame in self.call_stack.frames
            ],
            "variables": VariablesTracker.to_dict(self.variables),
            "agents": self.agents.copy() if self.agents else [],
            "owned_meetings": owned_meetings_list,
            "joined_meetings": joined_meetings_list,
        }

        if not full and self.last_sent_state is not None:
            return self._compute_delta(full_state)

        return full_state

    def _compute_delta(self, current_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Compute delta between current state and last sent state.

        Args:
            current_state: The current full state dictionary

        Returns:
            Delta state dictionary with only changes, or None if no changes
        """
        if self.last_sent_state is None:
            return current_state

        delta: Dict[str, Any] = {}

        # Call stack: Always include full call stack if changed
        current_call_stack = current_state.get("call_stack", [])
        last_call_stack = self.last_sent_state.get("call_stack", [])
        if current_call_stack != last_call_stack:
            delta["call_stack"] = current_call_stack

        # Variables: Use explicit delta keys
        current_vars = current_state.get("variables", {})
        last_vars = self.last_sent_state.get("variables", {})
        self._add_variable_delta_to_dict(delta, current_vars, last_vars)

        # Agents: Use explicit delta keys
        current_agents = current_state.get("agents", [])
        last_agents = self.last_sent_state.get("agents", [])
        self._add_agent_delta_to_dict(delta, current_agents, last_agents)

        # Owned meetings: Always include full list if changed
        current_owned = current_state.get("owned_meetings", [])
        last_owned = self.last_sent_state.get("owned_meetings", [])
        if current_owned != last_owned:
            delta["owned_meetings"] = current_owned

        # Joined meetings: Always include full list if changed
        current_joined = current_state.get("joined_meetings", [])
        last_joined = self.last_sent_state.get("joined_meetings", [])
        if current_joined != last_joined:
            delta["joined_meetings"] = current_joined

        # If delta is empty (no changes), return None
        if not delta:
            return None

        return delta

    def _add_variable_delta_to_dict(
        self,
        delta: Dict[str, Any],
        current_vars: Dict[str, Any],
        last_vars: Dict[str, Any],
    ) -> None:
        """Add variable delta to the delta dictionary using explicit keys.

        Args:
            delta: Delta dictionary to update
            current_vars: Current variables dictionary
            last_vars: Last sent variables dictionary
        """
        new_vars = {}
        changed_vars = {}
        deleted_vars = []

        # Find added and modified variables
        for key, value in current_vars.items():
            if key not in last_vars:
                new_vars[key] = value
            elif value != last_vars[key]:
                changed_vars[key] = value

        # Find deleted variables
        for key in last_vars:
            if key not in current_vars:
                deleted_vars.append(key)

        # Add to delta with explicit key names
        if new_vars:
            delta["new_variables"] = new_vars
        if changed_vars:
            delta["changed_variables"] = changed_vars
        if deleted_vars:
            delta["deleted_variables"] = deleted_vars

    def _add_agent_delta_to_dict(
        self, delta: Dict[str, Any], current_agents: List[Any], last_agents: List[Any]
    ) -> None:
        """Add agent delta to the delta dictionary using explicit keys.

        Args:
            delta: Delta dictionary to update
            current_agents: Current agents list
            last_agents: Last sent agents list
        """
        new_agents = [a for a in current_agents if a not in last_agents]

        # For now, we only track new agents (no changed or deleted)
        if new_agents:
            delta["new_agents"] = new_agents

    def get_state_for_llm(
        self, execution_id: Optional[int], compression_config: Optional[Any] = None
    ) -> tuple[Optional[Dict[str, Any]], "FrameType"]:
        """Get state for LLM with compression applied.

        Determines whether to send full state or delta based on execution_id
        and compression settings. Updates tracking state as needed.

        Args:
            execution_id: Current execution ID (LLM call counter)
            compression_config: StateCompressionConfig object (if None, uses default)

        Returns:
            Tuple of (state_dict, frame_type):
            - (full_state_dict, FrameType.I) for I-frame (full state)
            - (delta_dict, FrameType.P) for P-frame with changes
            - (None, FrameType.P) for P-frame with no changes (empty delta)
        """
        # Import here to avoid circular dependency
        if compression_config is None:
            compression_config = global_config.state_compression

        # Determine if we should send full state or delta
        compression_enabled = compression_config.enabled
        send_full_state = True

        if compression_enabled and execution_id is not None:
            # Send full state at intervals or if this is the first call
            if (
                self.last_i_frame_execution_id is None
                or (execution_id - self.last_i_frame_execution_id)
                >= compression_config.full_state_interval
            ):
                send_full_state = True
                self.last_i_frame_execution_id = execution_id
            else:
                send_full_state = False

        # Get state (full or delta)
        state_dict = self.to_dict(full=send_full_state)

        # Always update last_sent_state to current full state (cumulative)
        # This ensures P-frames are deltas from the immediate previous state, not from last I-frame
        # Cumulative chain: I + P + P + P = current full state
        self.last_sent_state = self.to_dict(full=True)

        if send_full_state:
            return state_dict, FrameType.I
        else:
            # Delta state (could be None if no changes)
            return state_dict, FrameType.P

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

    def snapshot_variables(self) -> None:
        """Snapshot current variables for diff computation."""
        self.previous_variables = VariablesTracker.snapshot(self.variables)

    def publish_variable_changes(self) -> None:
        """Publish events for any variable changes since last snapshot."""
        VariablesTracker.publish_changes(
            self.event_bus, self.agent_id, self.variables, self.previous_variables
        )

"""Tests for HumanState class."""

from datetime import datetime

import pytest

from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.human_state import HumanState
from playbooks.meetings import JoinedMeeting


@pytest.fixture
def event_bus():
    """Create an EventBus for testing."""
    return EventBus(session_id="test_session")


class TestHumanStateInit:
    """Test HumanState initialization."""

    def test_create_human_state(self, event_bus):
        """Test creating a HumanState instance."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        assert state.klass == "TestHuman"
        assert state.agent_id == "human_1"
        assert state.event_bus is event_bus
        assert state.joined_meetings == {}

    def test_initial_state_has_no_meetings(self, event_bus):
        """Test that new human state has no meetings."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        assert len(state.joined_meetings) == 0
        assert state.get_current_meeting() is None


class TestHumanStateMeetings:
    """Test meeting tracking in HumanState."""

    def test_get_current_meeting_with_no_meetings(self, event_bus):
        """Test get_current_meeting returns None when not in any meeting."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        assert state.get_current_meeting() is None

    def test_get_current_meeting_with_one_meeting(self, event_bus):
        """Test get_current_meeting returns the meeting ID when in one meeting."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        # Add a meeting
        meeting_id = "meeting_123"
        state.joined_meetings[meeting_id] = JoinedMeeting(
            id=meeting_id,
            owner_id="agent_1",
            joined_at=datetime.now(),
            topic="Test Meeting",
        )

        assert state.get_current_meeting() == meeting_id

    def test_get_current_meeting_returns_first_when_multiple(self, event_bus):
        """Test that get_current_meeting returns a meeting ID when multiple exist."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        # Add multiple meetings (edge case - humans should only be in one at a time)
        meeting_id_1 = "meeting_123"
        meeting_id_2 = "meeting_456"

        state.joined_meetings[meeting_id_1] = JoinedMeeting(
            id=meeting_id_1,
            owner_id="agent_1",
            joined_at=datetime.now(),
            topic="Test Meeting 1",
        )
        state.joined_meetings[meeting_id_2] = JoinedMeeting(
            id=meeting_id_2,
            owner_id="agent_2",
            joined_at=datetime.now(),
            topic="Test Meeting 2",
        )

        # Should return one of the meetings (first in dict iteration)
        result = state.get_current_meeting()
        assert result in [meeting_id_1, meeting_id_2]

    def test_joined_meetings_dict_is_mutable(self, event_bus):
        """Test that joined_meetings can be modified."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        meeting_id = "meeting_789"
        meeting = JoinedMeeting(
            id=meeting_id,
            owner_id="agent_1",
            joined_at=datetime.now(),
            topic="Mutable Test",
        )

        # Add meeting
        state.joined_meetings[meeting_id] = meeting
        assert len(state.joined_meetings) == 1

        # Remove meeting
        del state.joined_meetings[meeting_id]
        assert len(state.joined_meetings) == 0
        assert state.get_current_meeting() is None


class TestHumanStateRepr:
    """Test HumanState string representation."""

    def test_repr_with_no_meetings(self, event_bus):
        """Test __repr__ with no meetings."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        repr_str = repr(state)
        assert "TestHuman" in repr_str
        assert "human_1" in repr_str
        assert "meetings=0" in repr_str

    def test_repr_with_meetings(self, event_bus):
        """Test __repr__ with meetings."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        # Add a meeting
        state.joined_meetings["meeting_123"] = JoinedMeeting(
            id="meeting_123", owner_id="agent_1", joined_at=datetime.now(), topic="Test"
        )

        repr_str = repr(state)
        assert "TestHuman" in repr_str
        assert "human_1" in repr_str
        assert "meetings=1" in repr_str


class TestHumanStateVsExecutionState:
    """Test that HumanState is minimal compared to ExecutionState."""

    def test_human_state_has_no_call_stack(self, event_bus):
        """Test that HumanState doesn't have a call_stack attribute."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        assert not hasattr(state, "call_stack")

    def test_human_state_has_no_variables(self, event_bus):
        """Test that HumanState doesn't have a variables attribute."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        assert not hasattr(state, "variables")

    def test_human_state_has_no_session_log(self, event_bus):
        """Test that HumanState doesn't have a session_log attribute."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        assert not hasattr(state, "session_log")

    def test_human_state_has_no_owned_meetings(self, event_bus):
        """Test that HumanState doesn't have owned_meetings (humans don't own meetings)."""
        state = HumanState(event_bus, "TestHuman", "human_1")

        # HumanState only has joined_meetings, not owned_meetings
        assert hasattr(state, "joined_meetings")
        assert not hasattr(state, "owned_meetings")

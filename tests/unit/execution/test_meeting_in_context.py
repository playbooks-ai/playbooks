"""Test that meeting object appears in Python Code Context."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from box import Box

from playbooks.execution.interpreter_prompt import InterpreterPrompt
from playbooks.meetings.meeting import JoinedMeeting, Meeting
from playbooks.state.call_stack import CallStack, CallStackFrame


@pytest.fixture
def mock_agent_in_owned_meeting():
    """Create a mock agent that owns a meeting."""
    agent = Mock()
    agent.id = "agent_1000"
    agent.klass = "Host"

    # Create a meeting with shared_state
    meeting = Meeting(
        id="meeting_100",
        created_at=datetime.now(),
        owner_id=agent.id,
        topic="Test Meeting",
        shared_state={"game_board": [[1, 2, 3]], "turn": 1},
    )
    agent.owned_meetings = {"meeting_100": meeting}
    agent.joined_meetings = {}
    agent.active_meetings = [meeting]  # Combined list of owned + joined meetings
    agent.state = {}

    # Create call stack with meeting frame
    agent.call_stack = Mock(spec=CallStack)
    frame = Mock(spec=CallStackFrame)
    frame.meeting_id = "meeting_100"
    frame.locals = {}
    agent.call_stack.peek = Mock(return_value=frame)

    # Mock namespace manager
    agent.namespace_manager = Mock()
    agent.namespace_manager.namespace = {}

    # Mock meeting manager
    agent.meeting_manager = Mock()
    agent.meeting_manager.get_current_meeting_from_call_stack = Mock(
        return_value="meeting_100"
    )

    return agent


@pytest.fixture
def mock_agent_in_joined_meeting():
    """Create a mock agent that joined a meeting."""
    agent = Mock()
    agent.id = "agent_2000"
    agent.klass = "Player"

    # Create joined meeting with shared_state reference
    shared_state = Box({"game_board": [[1, 2, 3]], "turn": 1})
    joined_meeting = JoinedMeeting(
        id="meeting_100",
        owner_id="agent_1000",
        joined_at=datetime.now(),
        topic="Test Meeting",
        shared_state=shared_state,
    )
    agent.owned_meetings = {}
    agent.joined_meetings = {"meeting_100": joined_meeting}
    agent.active_meetings = [joined_meeting]  # Combined list of owned + joined meetings
    agent.state = {}

    # Create call stack with meeting frame
    agent.call_stack = Mock(spec=CallStack)
    frame = Mock(spec=CallStackFrame)
    frame.meeting_id = "meeting_100"
    frame.locals = {}
    agent.call_stack.peek = Mock(return_value=frame)

    # Mock namespace manager
    agent.namespace_manager = Mock()
    agent.namespace_manager.namespace = {}

    # Mock meeting manager
    agent.meeting_manager = Mock()
    agent.meeting_manager.get_current_meeting_from_call_stack = Mock(
        return_value="meeting_100"
    )

    return agent


class TestMeetingInContext:
    """Test that meeting object appears in context prefix."""

    def test_owned_meeting_appears_in_context(self, mock_agent_in_owned_meeting):
        """Test that owned meeting appears in Python Code Context."""
        prompt = InterpreterPrompt(
            agent=mock_agent_in_owned_meeting,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        context = prompt._build_context_prefix()

        # Verify meeting object is declared with repr format
        assert "self.current_meeting: Meeting =" in context
        assert 'Meeting<id="meeting_100"' in context

        # Verify shared_state is shown as Box
        assert "self.current_meeting.shared_state: Box = Box(" in context
        assert '"game_board"' in context
        assert '"turn": 1' in context

    def test_joined_meeting_appears_in_context(self, mock_agent_in_joined_meeting):
        """Test that joined meeting appears in Python Code Context."""
        prompt = InterpreterPrompt(
            agent=mock_agent_in_joined_meeting,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        context = prompt._build_context_prefix()

        # Verify meeting object is declared with repr format
        assert "self.current_meeting: Meeting =" in context
        assert 'JoinedMeeting<id="meeting_100"' in context

        # Verify shared_state is shown as Box
        assert "self.current_meeting.shared_state: Box = Box(" in context
        assert '"game_board"' in context
        assert '"turn": 1' in context

    def test_no_meeting_no_context(self):
        """Test that no meeting shows when not in a meeting."""
        agent = Mock()
        agent.owned_meetings = {}
        agent.joined_meetings = {}
        agent.active_meetings = []  # No meetings
        agent.state = {}
        agent.call_stack = Mock(spec=CallStack)
        agent.call_stack.peek = Mock(return_value=None)  # No current frame
        agent.namespace_manager = Mock()
        agent.namespace_manager.namespace = {}

        prompt = InterpreterPrompt(
            agent=agent,
            playbooks={},
            current_playbook=None,
            instruction="Test",
            agent_instructions="",
            artifacts_to_load=[],
            agent_information="",
            other_agent_klasses_information=[],
        )

        context = prompt._build_context_prefix()

        # Verify no meeting is shown
        assert "meeting = ..." not in context
        assert "meeting.shared_state" not in context

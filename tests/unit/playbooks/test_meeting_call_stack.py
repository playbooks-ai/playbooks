"""Test that meeting_id is correctly set in call stack when attendee joins."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from playbooks.agents.ai_agent import AIAgent
from playbooks.playbook import PythonPlaybook
from playbooks.event_bus import EventBus


class MeetingTestAgent(AIAgent):
    """Test agent implementation for meeting tests."""

    klass = "MeetingTestAgent"
    description = "Test agent for meeting tests"
    playbooks = {}
    metadata = {}

    async def discover_playbooks(self):
        pass


@pytest.fixture
def event_bus():
    """Create event bus for testing."""
    return EventBus(session_id="test-session")


@pytest.fixture
def agent(event_bus):
    """Create a test agent."""
    agent = MeetingTestAgent(event_bus=event_bus, agent_id="test_agent_1", program=None)

    # Create a mock meeting playbook
    mock_playbook = Mock(spec=PythonPlaybook)
    mock_playbook.name = "TestMeetingPlaybook"
    mock_playbook.meeting = True  # This IS a meeting playbook
    mock_playbook.execute = AsyncMock(return_value="executed")
    mock_playbook.source_file_path = "test.py"
    mock_playbook.code = "# test code"

    agent.playbooks["TestMeetingPlaybook"] = mock_playbook

    # Mock the _accept_meeting_invitation method
    agent.meeting_manager._accept_meeting_invitation = AsyncMock()

    return agent


@pytest.mark.asyncio
async def test_meeting_id_in_call_stack_when_joining_meeting(agent):
    """Test that meeting_id is accessible from call stack when joining a meeting."""

    # Mock langfuse
    with patch("playbooks.agents.ai_agent.LangfuseHelper") as mock_langfuse:
        mock_span = Mock()
        mock_span.span = Mock(return_value=mock_span)
        mock_span.update = Mock()
        mock_langfuse.instance.return_value.trace.return_value = mock_span

        check_result = {"meeting_id": None, "accepted": False}
        meeting_id = "meeting_123"

        async def check_meeting_during_execution(*args, **kwargs):
            """Check meeting_id during execution."""
            check_result["meeting_id"] = (
                agent.meeting_manager.get_current_meeting_from_call_stack()
            )
            return "executed"

        agent.playbooks["TestMeetingPlaybook"].execute = check_meeting_during_execution

        # Execute meeting playbook with meeting_id (simulating joining)
        await agent.execute_playbook(
            "TestMeetingPlaybook",
            args=[],
            kwargs={
                "meeting_id": meeting_id,
                "inviter_id": "1000",
                "topic": "Test Meeting",
            },
        )

        # Verify that _accept_meeting_invitation was called (auto-accept)
        agent.meeting_manager._accept_meeting_invitation.assert_called_once_with(
            meeting_id, "1000", "Test Meeting", "TestMeetingPlaybook"
        )

        # Verify that during execution, get_current_meeting_from_call_stack returned the correct meeting_id
        assert (
            check_result["meeting_id"] == meeting_id
        ), f"Expected meeting_id '{meeting_id}' in call stack, but got '{check_result['meeting_id']}'"


@pytest.mark.asyncio
async def test_meeting_id_accessible_via_state_get_current_meeting(agent):
    """Test that meeting_id is accessible via state.get_current_meeting when joining a meeting."""

    # Mock langfuse
    with patch("playbooks.agents.ai_agent.LangfuseHelper") as mock_langfuse:
        mock_span = Mock()
        mock_span.span = Mock(return_value=mock_span)
        mock_span.update = Mock()
        mock_langfuse.instance.return_value.trace.return_value = mock_span

        check_result = {"meeting_id": None}
        meeting_id = "meeting_456"

        async def check_state_meeting_during_execution(*args, **kwargs):
            """Check state.get_current_meeting during execution."""
            check_result["meeting_id"] = agent.state.get_current_meeting()
            return "executed"

        agent.playbooks["TestMeetingPlaybook"].execute = (
            check_state_meeting_during_execution
        )

        # Execute meeting playbook with meeting_id
        await agent.execute_playbook(
            "TestMeetingPlaybook",
            args=[],
            kwargs={
                "meeting_id": meeting_id,
                "inviter_id": "1000",
                "topic": "Test Meeting",
            },
        )

        # Verify that during execution, state.get_current_meeting() returned the correct meeting_id
        assert (
            check_result["meeting_id"] == meeting_id
        ), f"Expected meeting_id '{meeting_id}' from state.get_current_meeting(), but got '{check_result['meeting_id']}'"


@pytest.mark.asyncio
async def test_auto_accept_not_called_when_already_joined(agent):
    """Test that _accept_meeting_invitation is not called when already in the meeting."""

    # Mock langfuse
    with patch("playbooks.agents.ai_agent.LangfuseHelper") as mock_langfuse:
        mock_span = Mock()
        mock_span.span = Mock(return_value=mock_span)
        mock_span.update = Mock()
        mock_langfuse.instance.return_value.trace.return_value = mock_span

        meeting_id = "meeting_789"

        # Simulate that we've already joined this meeting
        from playbooks.meetings import JoinedMeeting
        from datetime import datetime

        agent.state.joined_meetings[meeting_id] = JoinedMeeting(
            id=meeting_id,
            owner_id="1000",
            topic="Test Meeting",
            joined_at=datetime.now(),
        )

        # Reset the mock to clear any previous calls
        agent.meeting_manager._accept_meeting_invitation.reset_mock()

        # Execute meeting playbook with meeting_id that we've already joined
        await agent.execute_playbook(
            "TestMeetingPlaybook",
            args=[],
            kwargs={
                "meeting_id": meeting_id,
                "inviter_id": "1000",
                "topic": "Test Meeting",
            },
        )

        # Verify that _accept_meeting_invitation was NOT called (we're already in the meeting)
        agent.meeting_manager._accept_meeting_invitation.assert_not_called()

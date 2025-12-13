from unittest.mock import Mock

import pytest

from playbooks.agents.builtin_playbooks import BuiltinPlaybooks
from playbooks.agents.ai_agent import AIAgent
from playbooks.infrastructure.event_bus import EventBus


def test_processmessages_instructions_never_create_new_meeting_from_meeting_message():
    """Regression: meeting-broadcast handling should not spawn new meetings (e.g. meeting 101)."""
    md = BuiltinPlaybooks.get_llm_playbooks_markdown()
    assert "If $message was sent to a meeting we have joined" in md
    # Verify that the instructions mention finding an existing meeting playbook rather than creating new ones
    assert "Try to find the appropriate meeting playbook" in md


class _StubMeetingPlaybook:
    """Minimal playbook stub to exercise meeting-init error handling without full runtime."""

    def __init__(self, name: str):
        self.name = name
        self.meeting = True
        self.public = False
        self.source_file_path = "[unit-test]"
        self.first_step_line_number = 0

    async def execute(self, *args, **kwargs):
        return "ok"


class _TestAgent(AIAgent):
    klass = "TestAgent"
    description = "Test agent"
    metadata = {}
    playbooks = {}
    namespace_manager = None

    async def discover_playbooks(self):
        return


@pytest.mark.asyncio
async def test_meeting_attendee_rejection_is_handled_as_failure_not_exception(
    monkeypatch,
):
    """If required attendees reject meeting creation, execute_playbook should not raise."""
    agent = _TestAgent(EventBus(session_id="unit-test"))
    agent.playbooks = {"Meeting": _StubMeetingPlaybook("Meeting")}

    # Avoid real meeting creation; return a minimal meeting object.
    meeting = Mock()
    meeting.id = "101"
    meeting.topic = "Unit test"

    async def _fake_create_meeting(playbook, kwargs):
        return meeting

    async def _fake_wait_for_required_attendees(_meeting, timeout_seconds: int = 30):
        raise ValueError("Required attendee(s) rejected meeting 101: ['AgentX']")

    monkeypatch.setattr(agent.meeting_manager, "create_meeting", _fake_create_meeting)
    monkeypatch.setattr(
        agent.meeting_manager,
        "_wait_for_required_attendees",
        _fake_wait_for_required_attendees,
    )

    success, result = await agent.execute_playbook("Meeting", args=[], kwargs={})
    assert success is False
    assert "Meeting initialization failed" in str(result)
    assert "rejected meeting 101" in str(result)

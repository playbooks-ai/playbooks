import types

import pytest

from playbooks.agents.base_agent import BaseAgent
from playbooks.core.message import MessageType
from playbooks.core.stream_result import StreamResult


class _DummyProgram:
    def __init__(self) -> None:
        self.calls = []

    async def route_message(
        self,
        *,
        sender_id: str,
        sender_klass: str,
        receiver_spec: str,
        message: str,
        message_type=None,
        meeting_id=None,
        **kwargs,
    ) -> None:
        self.calls.append(
            {
                "sender_id": sender_id,
                "sender_klass": sender_klass,
                "receiver_spec": receiver_spec,
                "message": message,
                "message_type": message_type,
                "meeting_id": meeting_id,
                "kwargs": kwargs,
            }
        )


class _TestAgent(BaseAgent):
    klass = "TestAgent"
    description = "Test agent"
    metadata = {}


@pytest.mark.asyncio
async def test_base_agent_meeting_broadcast_uses_message_type_without_nameerror() -> (
    None
):
    program = _DummyProgram()
    agent = _TestAgent(agent_id="a1", program=program)
    # In real runtime, agents always have a playbooks registry; our minimalist
    # unit test sets it to avoid BaseAgent.__getattr__ recursion on missing attrs.
    agent.playbooks = {}
    agent._currently_streaming = False

    await agent._say_meeting_without_streaming("meeting 123", "hello")

    assert len(program.calls) == 1
    assert program.calls[0]["message_type"] == MessageType.MEETING_BROADCAST
    assert program.calls[0]["meeting_id"] is not None


@pytest.mark.asyncio
async def test_base_agent_meeting_streaming_skip_routes_with_meeting_broadcast_type() -> (
    None
):
    program = _DummyProgram()
    agent = _TestAgent(agent_id="a1", program=program)
    agent.playbooks = {}
    agent._currently_streaming = False

    async def _fake_start_streaming_say_via_channel(self, target: str) -> StreamResult:
        return StreamResult.skip()

    agent.start_streaming_say_via_channel = types.MethodType(
        _fake_start_streaming_say_via_channel, agent
    )

    await agent._say_meeting_with_streaming("meeting 123", "hello")

    assert len(program.calls) == 1
    assert program.calls[0]["message_type"] == MessageType.MEETING_BROADCAST
    assert program.calls[0]["meeting_id"] is not None

import pytest
from autogen_core import (
    DefaultTopicId,
    SingleThreadedAgentRuntime,
)

from tests.autogen.helpers import Task, TestProcessor


@pytest.mark.asyncio
async def test_one_autogen_agent():
    runtime = SingleThreadedAgentRuntime()

    # Create a shared list to store completed tasks
    completed_tasks = []

    # Register agents with the runtime
    await TestProcessor.register(
        runtime, "agent", lambda: TestProcessor("Agent", completed_tasks)
    )

    runtime.start()

    task = Task(task_id="123")
    await runtime.publish_message(task, topic_id=DefaultTopicId())

    # Process all messages and wait for idle
    await runtime.stop_when_idle()

    assert "123" in completed_tasks


@pytest.mark.asyncio
async def test_two_autogen_agents():
    runtime = SingleThreadedAgentRuntime()

    # Create a shared list to store completed tasks
    completed_tasks = []

    # Register agents with the runtime
    await TestProcessor.register(
        runtime, "agent_1", lambda: TestProcessor("Agent 1", completed_tasks)
    )
    await TestProcessor.register(
        runtime, "agent_2", lambda: TestProcessor("Agent 2", completed_tasks)
    )

    runtime.start()

    task = Task(task_id="123")
    await runtime.publish_message(task, topic_id=DefaultTopicId())

    # Process all messages and wait for idle
    await runtime.stop_when_idle()

    assert "123" in completed_tasks

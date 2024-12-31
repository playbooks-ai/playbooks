from dataclasses import dataclass

import pytest
from autogen_core import (
    DefaultTopicId,
    MessageContext,
    RoutedAgent,
    SingleThreadedAgentRuntime,
    default_subscription,
    message_handler,
)
from playbooks.core.runtime import SingleThreadedPlaybooksRuntime
from litellm import completion

@dataclass
class Task:
    task_id: str


@dataclass
class TaskResponse:
    task_id: str
    result: str


@default_subscription
class TestPlaybooksProcessor(RoutedAgent):
    def __init__(self, description, completed_tasks, playbooks_runtime):
        super().__init__(description)
        self._description = description
        self.completed_tasks = completed_tasks
        self.playbooks_runtime = playbooks_runtime

    @message_handler
    async def on_task(self, message: Task, ctx: MessageContext) -> None:
        print(f"{self._description} starting task {message.task_id}")
        # Send event to playbooks runtime to run the HelloWorld playbook
        await self.playbooks_runtime.run()
        self.completed_tasks.append(message.task_id)
        print(f"{self._description} finished task {message.task_id}")


@pytest.mark.asyncio
async def test_one_autogen_agent():
    runtime = SingleThreadedAgentRuntime()

    # Start playbooks runtime with a single agent
    playbooks_runtime = SingleThreadedPlaybooksRuntime()
    playbooks_runtime.load("examples/playbooks/hello.md", mock_llm_response="Hello! I am a mock response from the test.")
    assert len(playbooks_runtime.agents) == 1
    assert playbooks_runtime.agents[0].name == "HelloWorld Agent"

    # Create a shared list to store completed tasks
    completed_tasks = []

    # Register agents with the runtime
    agent_id = await TestPlaybooksProcessor.register(
        runtime,
        "agent",
        lambda: TestPlaybooksProcessor("Agent", completed_tasks, playbooks_runtime),
    )

    runtime.start()

    task = Task(task_id="123")
    await runtime.publish_message(task, topic_id=DefaultTopicId())

    # Process all messages and wait for idle
    await runtime.stop_when_idle()

    # Verify task was completed
    assert "123" in completed_tasks

    # Verify that runtime has an agent_message event
    assert (
        next(
            (
                event
                for event in playbooks_runtime.events
                if event["type"] == "agent_message"
            ),
            None,
        )
        is not None
    )

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
from tests.autogen.helpers import MockChatCompletionClient, MockLLMResponse


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

    # Create mock LLM client
    mock_llm = MockChatCompletionClient(
        [
            MockLLMResponse(content="Hello, I'm the HelloWorld Agent!"),
            MockLLMResponse(content="I'm here to help with your tasks."),
        ]
    )

    # Start playbooks runtime with a single agent
    playbooks_runtime = SingleThreadedPlaybooksRuntime()
    playbooks_runtime.load(
        "examples/playbooks/hello.md",
        llm_client=mock_llm,  # Pass the mock LLM client
    )
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

    # Verify that runtime has an agent_response event
    assert (
        next(
            (
                event
                for event in playbooks_runtime.events
                if event["type"] == "agent_response"
            ),
            None,
        )
        is not None
    )


@pytest.mark.asyncio
async def test_one_autogen_agent_with_streaming():
    runtime = SingleThreadedAgentRuntime()

    # Create mock LLM client with streaming chunks
    mock_llm = MockChatCompletionClient(
        [
            MockLLMResponse(
                content="Hello from streaming!",
                chunks=["Hello", " from", " streaming!"],
            ),
            MockLLMResponse(content="Another response"),
        ]
    )

    # Start playbooks runtime with a single agent
    playbooks_runtime = SingleThreadedPlaybooksRuntime()
    playbooks_runtime.load(
        "examples/playbooks/hello.md",
        llm_client=mock_llm,
    )
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

    task = Task(task_id="stream-123")
    await runtime.publish_message(task, topic_id=DefaultTopicId())

    # Process all messages and wait for idle
    await runtime.stop_when_idle()

    # Verify task was completed
    assert "stream-123" in completed_tasks

    # Verify LLM was called
    assert mock_llm.num_calls > 0

    # Reset mock for next test
    mock_llm.reset()
    assert mock_llm.num_calls == 0
    assert mock_llm.current_index == 0


@pytest.mark.asyncio
async def test_one_autogen_agent_no_more_responses():
    runtime = SingleThreadedAgentRuntime()

    # Create mock LLM client with only one response
    mock_llm = MockChatCompletionClient(
        [
            MockLLMResponse(content="First and only response"),
        ]
    )

    # Start playbooks runtime with a single agent
    playbooks_runtime = SingleThreadedPlaybooksRuntime()
    playbooks_runtime.load(
        "examples/playbooks/hello.md",
        llm_client=mock_llm,
    )

    # Create a shared list to store completed tasks
    completed_tasks = []

    # Register agents with the runtime
    agent_id = await TestPlaybooksProcessor.register(
        runtime,
        "agent",
        lambda: TestPlaybooksProcessor("Agent", completed_tasks, playbooks_runtime),
    )

    runtime.start()

    # First task should work
    task1 = Task(task_id="first")
    await runtime.publish_message(task1, topic_id=DefaultTopicId())
    await runtime.stop_when_idle()
    assert "first" in completed_tasks

    # Second task should fail due to no more responses
    with pytest.raises(ValueError, match="No more mock responses available"):
        task2 = Task(task_id="second")
        await runtime.publish_message(task2, topic_id=DefaultTopicId())
        await runtime.stop_when_idle()

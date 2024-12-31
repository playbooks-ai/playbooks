from dataclasses import dataclass

from autogen_core import (
    MessageContext,
    RoutedAgent,
    default_subscription,
    message_handler,
)


@dataclass
class Task:
    task_id: str


@dataclass
class TaskResponse:
    task_id: str
    result: str


@default_subscription
class TestProcessor(RoutedAgent):
    def __init__(self, description, completed_tasks):
        super().__init__(description)
        self._description = description
        self.completed_tasks = completed_tasks

    @message_handler
    async def on_task(self, message: Task, ctx: MessageContext) -> None:
        print(f"{self._description} starting task {message.task_id}")
        # await asyncio.sleep(2)  # Simulate work
        self.completed_tasks.append(message.task_id)
        print(f"{self._description} finished task {message.task_id}")


from dataclasses import dataclass
from typing import Any, AsyncGenerator, List

from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
)


@dataclass
class MockLLMResponse:
    content: str
    chunks: List[str] | None = None


class MockChatCompletionClient(ChatCompletionClient):
    """Mock chat completion client that returns predefined responses."""

    def __init__(self, responses: List[MockLLMResponse]) -> None:
        self.responses = responses
        self.current_index = 0
        self.num_calls = 0

    async def create(self, messages: List[Any], **kwargs: Any) -> CreateResult:
        """Return a predefined response."""
        if self.current_index >= len(self.responses):
            raise ValueError("No more mock responses available")

        response = self.responses[self.current_index]
        self.current_index += 1
        self.num_calls += 1

        return CreateResult(content=response.content)

    async def create_stream(
        self, messages: List[Any], **kwargs: Any
    ) -> AsyncGenerator[CreateResult | str, None]:
        """Stream a predefined response in chunks."""
        if self.current_index >= len(self.responses):
            raise ValueError("No more mock responses available")

        response = self.responses[self.current_index]
        self.current_index += 1
        self.num_calls += 1

        if response.chunks:
            for chunk in response.chunks:
                yield chunk
        else:
            # If no chunks specified, yield the entire content as one chunk
            yield response.content

    def reset(self) -> None:
        """Reset the client state."""
        self.current_index = 0
        self.num_calls = 0

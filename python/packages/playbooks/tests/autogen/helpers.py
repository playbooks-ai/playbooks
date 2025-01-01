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
        self.completed_tasks.append(message.task_id)
        print(f"{self._description} finished task {message.task_id}")

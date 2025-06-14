import asyncio
import uuid
from abc import ABC
from collections import defaultdict
from typing import TYPE_CHECKING

from playbooks.constants import EOM

if TYPE_CHECKING:
    from src.playbooks.program import Program


class AgentCommunicationMixin:
    def __init__(self):
        self.program: Program | None = None
        self.inboxes = defaultdict(asyncio.Queue)

    async def SendMessage(self, target_agent_id: str, message: str):
        await self.program.route_message(self.id, target_agent_id, message)

    async def WaitForMessage(self, source_agent_id: str) -> str | None:
        messages = []

        while not self.inboxes[source_agent_id].empty():
            message = self.inboxes[source_agent_id].get_nowait()
            if message == EOM:
                break
            messages.append(message)

        if not messages:
            messages.append(await self.inboxes[source_agent_id].get())

        for message in messages:
            self.state.session_log.append(
                f"Received message from {source_agent_id}: {message}"
            )
        return "\n".join(messages)


class BaseAgent(AgentCommunicationMixin, ABC):
    """
    Abstract base class for all agent implementations.

    Agents are entities that can process messages and generate responses. This class
    defines the common interface that all agent implementations must adhere to.

    Attributes:
        klass: A string identifier for the agent class/type.
    """

    def __init__(self, klass: str):
        """
        Initialize a new BaseAgent.

        Args:
            klass: The class/type identifier for this agent.
        """
        super().__init__()
        self.id = str(uuid.uuid4())
        self.klass = klass

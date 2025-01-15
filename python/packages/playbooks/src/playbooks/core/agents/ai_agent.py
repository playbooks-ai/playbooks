from typing import TYPE_CHECKING, Any, Dict, Optional

from playbooks.core.agents.ai_agent_thread import AIAgentThread
from playbooks.core.agents.base_agent import Agent
from playbooks.core.exceptions import (
    AgentAlreadyRunningError,
    AgentConfigurationError,
    AgentError,
)
from playbooks.core.playbook import Playbook
from playbooks.enums import AgentType

if TYPE_CHECKING:
    from playbooks.core.runtime import PlaybooksRuntime


class AIAgent(Agent):
    """AI agent."""

    # static method factory that creates an AIAgent for
    # a given H1 header
    @classmethod
    def from_h1(cls, h1: Dict):
        """Create an AIAgent from an H1 AST node.

        Args:
            h1: Dictionary representing an H1 AST node
        """
        agent = cls(klass=h1["text"], description=h1.get("description", ""))
        agent.playbooks = [
            Playbook.from_h2(h2)
            for h2 in h1.get("children", [])
            if h2.get("type") == "h2"
        ]
        return agent

    def __init__(self, klass: str, description: str):
        super().__init__(klass, AgentType.AI)
        self.description = description
        self.playbooks: list[Playbook] = []
        self.main_thread: Optional[Any] = None

    def run(self, runtime: "PlaybooksRuntime" = None):
        """Run the agent."""
        # raise custom exception AgentConfigurationError if no playbooks are defined
        if len(self.playbooks) == 0:
            raise AgentConfigurationError("No playbooks defined for AI agent")

        # raise custom exception AgentAlreadyRunningError if agent is already running
        if self.main_thread is not None:
            raise AgentAlreadyRunningError("AI agent is already running")

        # raise custom exception AgentError if runtime is not provided
        if runtime is None:
            raise AgentError("Runtime is not provided")

        # create self.main_thread of type AgentThread
        self.main_thread = AIAgentThread(self)

        # run the main thread
        # TODO: add support for filtering playbooks
        for chunk in self.main_thread.run(
            runtime=runtime,
            included_playbooks=self.playbooks,
            instruction="Begin",
        ):
            yield chunk

    def process_message(
        self,
        message: str,
        from_agent: "Agent",
        routing_type: str,
        runtime: "PlaybooksRuntime",
    ):
        # Process the message on main thread
        for chunk in self.main_thread.run(
            runtime=runtime,
            included_playbooks=self.playbooks,
            instruction=f"Received the following message from {from_agent.klass}: {message}",
        ):
            yield chunk

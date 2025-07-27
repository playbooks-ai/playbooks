"""Base LLM execution strategy."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..agents.base_agent import Agent
    from ..playbook.llm_playbook import LLMPlaybook


class LLMExecution(ABC):
    """Base class for LLM execution strategies."""

    def __init__(self, agent: "Agent", playbook: "LLMPlaybook"):
        """Initialize the execution strategy.

        Args:
            agent: The agent executing the playbook
            playbook: The LLM playbook to execute
        """
        self.agent = agent
        self.playbook = playbook
        self.state = agent.state  # Direct access to ExecutionState

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the playbook with the given strategy.

        Args:
            *args: Positional arguments for the playbook
            **kwargs: Keyword arguments for the playbook

        Returns:
            The execution result
        """
        pass

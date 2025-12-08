"""Base LLM execution strategy."""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from playbooks.compilation.expression_engine import (
    ExpressionContext,
    resolve_description_placeholders,
)
from playbooks.execution.call import PlaybookCall

if TYPE_CHECKING:
    from playbooks.agents.local_ai_agent import LocalAIAgent
    from playbooks.playbook import LLMPlaybook


class LLMExecution(ABC):
    """Base class for LLM execution strategies."""

    def __init__(self, agent: "LocalAIAgent", playbook: "LLMPlaybook"):
        """Initialize the execution strategy.

        Args:
            agent: The agent executing the playbook
            playbook: The LLM playbook to execute
        """
        self.agent: "LocalAIAgent" = agent
        self.playbook: "LLMPlaybook" = playbook

    async def resolve_description_placeholders(
        self, description: str, *args, **kwargs
    ) -> str:
        """Resolve description placeholders if present.

        Args:
            description: The description potentially containing placeholders
            *args: Positional arguments for the playbook call context
            **kwargs: Keyword arguments for the playbook call context

        Returns:
            Description with placeholders resolved
        """
        if not description or "{" not in description:
            return description

        try:
            # Create a PlaybookCall for context
            call = PlaybookCall(self.playbook.name, list(args), kwargs)
            context = ExpressionContext(self.agent, call=call)
            return await resolve_description_placeholders(description, context)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to resolve description placeholders: {e}")
            return description

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

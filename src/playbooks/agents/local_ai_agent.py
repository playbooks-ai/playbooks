import logging
from typing import Dict

from ..event_bus import EventBus
from ..playbook import Playbook
from .ai_agent import AIAgent

logger = logging.getLogger(__name__)


class LocalAIAgent(AIAgent):
    """
    Local AI agent that executes playbooks locally.

    This agent executes markdown and Python playbooks within the local process,
    using the existing execution infrastructure.
    """

    def __init__(
        self,
        klass: str,
        description: str,
        event_bus: EventBus,
        playbooks: Dict[str, Playbook] = None,
        source_line_number: int = None,
        agent_id: str = None,
    ):
        """Initialize a new LocalAIAgent.

        Args:
            klass: The class/type of this agent.
            description: Human-readable description of the agent.
            event_bus: The event bus for publishing events.
            playbooks: Dictionary of playbooks available to this agent.
            source_line_number: The line number in the source markdown where this
                agent is defined.
            agent_id: Optional agent ID. If not provided, will generate UUID.
        """
        super().__init__(
            klass, description, event_bus, playbooks, source_line_number, agent_id
        )
        # Set up agent reference for playbooks that need it
        for playbook in self.playbooks.values():
            if hasattr(playbook, "func") and playbook.func:
                playbook.func.__globals__.update({"agent": self})

    async def discover_playbooks(self) -> None:
        """Discover playbooks for local agent.

        For LocalAIAgent, playbooks are already provided during initialization,
        so this method is a no-op.
        """
        pass

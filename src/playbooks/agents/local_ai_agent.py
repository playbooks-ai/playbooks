import logging
from typing import TYPE_CHECKING, Any, Dict, Type

from playbooks.agents.namespace_manager import AgentNamespaceManager
from playbooks.event_bus import EventBus
from playbooks.exceptions import AgentConfigurationError
from playbooks.playbook import MarkdownPlaybook, PythonPlaybook
from playbooks.utils.markdown_to_ast import refresh_markdown_attributes

from .ai_agent import AIAgent
from .registry import AgentClassRegistry

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..program import Program


class LocalAIAgent(AIAgent):
    """
    Local AI agent that executes playbooks locally.

    This agent executes markdown and Python playbooks within the local process,
    using the existing execution infrastructure.
    """

    @classmethod
    def can_handle(cls, metadata: Dict[str, Any]) -> bool:
        """Check if this agent class can handle the given metadata.

        LocalAIAgent handles configurations without remote settings,
        or any configuration that other agents can't handle (fallback).

        Args:
            metadata: Agent metadata from playbook

        Returns:
            bool: True if this agent can handle the metadata
        """
        # LocalAIAgent handles any configuration without remote settings
        return "remote" not in metadata

    @staticmethod
    def create_class(
        klass: str,
        description: str,
        metadata: Dict[str, Any],
        h1: Dict,
        source_line_number: int,
        namespace_manager: AgentNamespaceManager = None,
    ) -> Type["LocalAIAgent"]:
        """Create and return a new local Agent class.

        Args:
            klass: Agent class name (from source)
            description: Agent description
            metadata: Agent metadata
            source_line_number: Line number in source where agent is defined

        Returns:
            Type[LocalAIAgent]: Dynamically created Agent class

        Raises:
            AgentConfigurationError: If agent class already exists
        """

        playbooks = {}
        python_playbooks = PythonPlaybook.create_playbooks_from_h1(
            h1, namespace_manager
        )
        markdown_playbooks = MarkdownPlaybook.create_playbooks_from_h1(
            h1, namespace_manager
        )

        playbooks.update(python_playbooks)
        playbooks.update(markdown_playbooks)

        if not playbooks:
            raise AgentConfigurationError(f"No playbooks defined for AI agent {klass}")

        # Refresh markdown attributes to ensure Python code is not sent to the LLM
        refresh_markdown_attributes(h1)

        # Define __init__ for the new class
        def __init__(self, event_bus: EventBus, agent_id: str = None, **kwargs):
            LocalAIAgent.__init__(
                self,
                event_bus=event_bus,
                source_line_number=source_line_number,
                agent_id=agent_id,
                **kwargs,
            )

        # Create and return the new Agent class
        return type(
            klass,
            (LocalAIAgent,),
            {
                "__init__": __init__,
                "klass": klass,
                "description": description,
                "playbooks": playbooks,
                "metadata": metadata,
                "namespace_manager": namespace_manager,
            },
        )

    def __init__(
        self,
        event_bus: EventBus,
        source_line_number: int = None,
        agent_id: str = None,
        program: "Program" = None,
        **kwargs,
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
            event_bus=event_bus,
            source_line_number=source_line_number,
            agent_id=agent_id,
            program=program,
            **kwargs,
        )
        # Namespace setup is now handled in AIAgent.__init__

    async def discover_playbooks(self) -> None:
        """Discover playbooks for local agent.

        For LocalAIAgent, playbooks are already provided during initialization,
        so this method is a no-op.
        """
        pass


# Register LocalAIAgent with the registry as a fallback (lowest priority)
AgentClassRegistry.register(LocalAIAgent, priority=0)

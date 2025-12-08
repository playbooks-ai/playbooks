"""Human agent implementation for user interaction.

This module provides the HumanAgent class that represents human participants
in playbook execution, handling user input and state management.
"""

from typing import TYPE_CHECKING, Any, Optional

from playbooks.agents.delivery_preferences import DeliveryPreferences
from playbooks.core.constants import HUMAN_AGENT_KLASS
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.human_state import HumanState

from .base_agent import BaseAgent

if TYPE_CHECKING:
    from playbooks.program import Program


class HumanAgent(BaseAgent):
    """Agent representing a human participant in playbook execution.

    Human agents handle user input and maintain minimal state for
    human-computer interaction in playbooks.

    Attributes set by AgentBuilder for declaratively defined humans:
        klass: Agent class name (e.g. "Alice", "Bob", "User")
        description: Human-readable description
        metadata: Agent metadata from playbook
        human_name: Display name for the human (e.g. "Alice Chen")
        delivery_preferences: DeliveryPreferences instance
    """

    klass = HUMAN_AGENT_KLASS  # Default, overridden by subclasses
    description = "A human agent."  # Default, overridden by subclasses
    metadata = {}  # Default, overridden by subclasses
    playbooks = {}  # Human agents don't execute playbooks
    human_name = None  # Set by subclasses
    delivery_preferences = None  # Set by subclasses

    @classmethod
    def should_create_instance_at_start(cls) -> bool:
        """Human agents are always created at start.

        Unlike AI agents which may have dynamic instantiation via triggers,
        human agents represent users who should be available from the start.

        Returns:
            Always True for human agents
        """
        return True

    def __init__(
        self,
        event_bus: EventBus,
        agent_id: Optional[str] = None,
        program: Optional["Program"] = None,
        klass: Optional[str] = None,
        name: Optional[str] = None,
        delivery_preferences: Optional[DeliveryPreferences] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a HumanAgent.

        Args:
            event_bus: Event bus for communication
            agent_id: Unique agent identifier (generated if not provided)
            program: Program instance
            klass: Agent class identifier (overrides class attribute if provided)
            name: Human-readable name (defaults to klass if not provided)
            delivery_preferences: Delivery preferences (defaults to streaming if not provided)
        """
        super().__init__(agent_id=agent_id, program=program, **kwargs)
        self.id = agent_id

        # Get klass from parameter or class attribute (set by AgentBuilder)
        self.klass = klass or self.__class__.klass

        # Set human-readable name (use provided name, class attribute, or klass)
        self.name = name or self.__class__.human_name or self.klass

        # Set delivery preferences (use provided, class attribute, or default to streaming)
        self.delivery_preferences = (
            delivery_preferences
            or self.__class__.delivery_preferences
            or DeliveryPreferences.streaming_default()
        )

        # Use minimal HumanState instead of full AIAgent state
        # Humans don't execute playbooks, so don't need call stacks, variables, or session logs
        self.state = HumanState(event_bus, self.klass, self.id)

    async def begin(self) -> None:
        """Begin execution for human agent (no-op).

        Human agents do not process messages or execute playbooks, so this is a no-op.
        """
        pass

    def __str__(self) -> str:
        """String representation of the human agent.

        Returns:
            String representation (same as __repr__)
        """
        return self.__repr__()

    def __repr__(self) -> str:
        """Detailed string representation of the human agent.

        Returns:
            String in format "HumanAgent(name, klass, id)"
        """
        return f"HumanAgent({self.name}, {self.klass}, {self.id})"

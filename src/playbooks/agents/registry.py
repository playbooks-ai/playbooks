"""Agent registry for managing agent class registration and discovery."""

from typing import Dict, List, Optional, Type


class AgentClassRegistry:
    """Registry for agent classes that can create agent instances based on configuration."""

    _agents: List[Dict] = []

    @classmethod
    def register(cls, agent_class: Type, priority: int = 0) -> None:
        """Register an agent class with the registry.

        Args:
            agent_class: The agent class to register
            priority: Priority for conflict resolution (higher = more priority)
        """
        # Remove existing registration if present
        cls._agents = [a for a in cls._agents if a["class"] != agent_class]

        # Add new registration
        cls._agents.append({"class": agent_class, "priority": priority})

        # Sort by priority (highest first)
        cls._agents.sort(key=lambda x: x["priority"], reverse=True)

    @classmethod
    def find_agent_class(cls, metadata: Dict) -> Optional[Type]:
        """Find the appropriate agent class for the given metadata.

        Args:
            metadata: Agent metadata from playbook

        Returns:
            Agent class that can handle the metadata, or None if none found
        """
        for agent_info in cls._agents:
            agent_class = agent_info["class"]
            if hasattr(agent_class, "can_handle") and agent_class.can_handle(metadata):
                return agent_class
        return None

    @classmethod
    def get_registered_agents(cls) -> List[Type]:
        """Get list of all registered agent classes."""
        return [a["class"] for a in cls._agents]

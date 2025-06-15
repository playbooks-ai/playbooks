import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List

from ..call_stack import InstructionPointer
from ..event_bus import EventBus
from ..execution_state import ExecutionState
from ..playbook import Playbook
from ..utils.parse_utils import parse_metadata_and_description
from .base_agent import BaseAgent

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AIAgent(BaseAgent, ABC):
    """
    Abstract base class for AI agents.

    An Agent represents an AI entity capable of processing messages through playbooks
    using a main execution thread. This class defines the interface that all AI agent
    implementations must adhere to.

    Attributes:
        klass: The class/type of this agent.
        description: Human-readable description of the agent.
        playbooks: Dictionary of playbooks available to this agent.
        other_agents: Dictionary of other agents for direct communication.
    """

    def __init__(
        self,
        klass: str,
        description: str,
        event_bus: EventBus,
        playbooks: Dict[str, Playbook] = None,
        source_line_number: int = None,
    ):
        """Initialize a new AIAgent.

        Args:
            klass: The class/type of this agent.
            description: Human-readable description of the agent.
            event_bus: The event bus for publishing events.
            playbooks: Dictionary of playbooks available to this agent.
            source_line_number: The line number in the source markdown where this
                agent is defined.
        """
        super().__init__(klass)
        self.metadata, self.description = parse_metadata_and_description(description)
        self.playbooks: Dict[str, Playbook] = playbooks or {}
        self.state = ExecutionState(event_bus)
        self.source_line_number = source_line_number
        self.public_json = None
        self.other_agents: Dict[str, "AIAgent"] = {}

    @abstractmethod
    async def discover_playbooks(self) -> None:
        """Discover and load playbooks for this agent.

        This method should populate the self.playbooks dictionary with
        available playbooks for this agent.
        """
        pass

    @abstractmethod
    async def execute_playbook(
        self, playbook_name: str, args: List[Any] = [], kwargs: Dict[str, Any] = {}
    ) -> Any:
        """Execute a playbook with the given arguments.

        Args:
            playbook_name: Name of the playbook to execute
            args: Positional arguments for the playbook
            kwargs: Keyword arguments for the playbook

        Returns:
            The result of executing the playbook
        """
        pass

    def register_agent(self, agent_name: str, agent: "AIAgent") -> None:
        """Register another agent for direct communication.

        Args:
            agent_name: Name/identifier of the agent
            agent: The agent instance to register
        """
        self.other_agents[agent_name] = agent

    def get_available_playbooks(self) -> List[str]:
        """Get a list of available playbook names.

        Returns:
            List of playbook names available to this agent
        """
        return list(self.playbooks.keys())

    async def begin(self):
        """Execute playbooks with BGN trigger."""
        # Find playbooks with a BGN trigger and execute them
        playbooks_to_execute = []
        for playbook in self.playbooks.values():
            if hasattr(playbook, "triggers") and playbook.triggers:
                for trigger in playbook.triggers.triggers:
                    if trigger.is_begin:
                        playbooks_to_execute.append(playbook)

        # TODO: execute the playbooks in parallel
        for playbook in playbooks_to_execute:
            await self.execute_playbook(playbook.name)

    def parse_instruction_pointer(self, step: str) -> InstructionPointer:
        """Parse a step string into an InstructionPointer.

        Args:
            step: Step string to parse

        Returns:
            InstructionPointer: Parsed instruction pointer
        """
        # Extract the step number from the step string
        step_number = step.split(".")[0]
        return InstructionPointer(self.klass, step_number, 0)

    def trigger_instructions(
        self, with_namespace: bool = False, public_only: bool = False
    ) -> List[str]:
        """Get trigger instructions for this agent's playbooks.

        Args:
            with_namespace: Whether to include namespace in instructions
            public_only: Whether to only include public playbooks

        Returns:
            List of trigger instruction strings
        """
        instructions = []
        for playbook in self.playbooks.values():
            if public_only and not getattr(playbook, "public", False):
                continue
            # Use the playbook's trigger_instructions method if available
            if hasattr(playbook, "trigger_instructions"):
                namespace = self.klass if with_namespace else None
                playbook_instructions = playbook.trigger_instructions(namespace)
                instructions.extend(playbook_instructions)
        return instructions

    @property
    def other_agents_list(self) -> List["AIAgent"]:
        """Get list of other registered agents.

        Returns:
            List of other agent instances
        """
        return list(self.other_agents.values())

    def all_trigger_instructions(self) -> List[str]:
        """Get all trigger instructions including from other agents.

        Returns:
            List of all trigger instruction strings
        """
        instructions = self.trigger_instructions(with_namespace=True)
        for agent in self.other_agents.values():
            instructions.extend(agent.trigger_instructions(with_namespace=True))
        return instructions

    def get_public_information(self) -> str:
        """Get public information about this agent.

        Returns:
            String containing public agent information
        """
        info_parts = []
        info_parts.append(f"Agent: {self.klass}")
        if self.description:
            info_parts.append(f"Description: {self.description}")

        public_playbooks = self.public_playbooks
        if public_playbooks:
            info_parts.append("Public Playbooks:")
            for playbook in public_playbooks:
                info_parts.append(f"  - {playbook['name']}: {playbook['description']}")

        return "\n".join(info_parts)

    def other_agents_information(self) -> List[str]:
        """Get information about other registered agents.

        Returns:
            List of information strings for other agents
        """
        return [agent.get_public_information() for agent in self.other_agents.values()]

    @property
    def public_playbooks(self) -> List[Dict[str, Any]]:
        """Get list of public playbooks with their information.

        Returns:
            List of dictionaries containing public playbook information
        """
        public_playbooks = []
        for playbook in self.playbooks.values():
            if getattr(playbook, "public", False):
                public_playbooks.append(
                    {
                        "name": playbook.name,
                        "description": (
                            playbook.get_description()
                            if hasattr(playbook, "get_description")
                            else playbook.description or ""
                        ),
                    }
                )
        return public_playbooks

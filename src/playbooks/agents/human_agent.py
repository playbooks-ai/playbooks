from typing import TYPE_CHECKING

from ..event_bus import EventBus
from ..execution_state import ExecutionState
from .base_agent import BaseAgent

if TYPE_CHECKING:
    from ..program import Program


class HumanAgent(BaseAgent):
    klass = "HumanAgent"
    description = "A human agent."
    metadata = {}

    def __init__(
        self, klass: str, event_bus: EventBus, agent_id: str, program: "Program"
    ):
        super().__init__(agent_id=agent_id, program=program)
        self.id = agent_id

        # TODO: HumanAgent should not have the same state as AI agents. Use a different state class.
        self.state = ExecutionState(event_bus, klass, agent_id)

    async def begin(self):
        # Human agent does not process messages, nor has BGN playbooks, so we do nothing
        pass

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "HumanAgent(agent user)"

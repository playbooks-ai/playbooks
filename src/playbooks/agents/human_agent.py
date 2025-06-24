from ..event_bus import EventBus
from ..execution_state import ExecutionState
from .base_agent import BaseAgent


class HumanAgent(BaseAgent):
    def __init__(self, klass: str, event_bus: EventBus, agent_id: str):
        super().__init__(klass, agent_id)
        self.id = agent_id

        # TODO: HumanAgent should not have the same state as AI agents. Use a different state class.
        self.state = ExecutionState(event_bus)

    def __str__(self):
        return "user"

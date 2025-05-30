from playbooks.base_agent import BaseAgent
from playbooks.event_bus import EventBus
from playbooks.execution_state import ExecutionState


class HumanAgent(BaseAgent):
    def __init__(self, klass: str, event_bus: EventBus):
        super().__init__(klass)
        self.id = "human"

        # TODO: HumanAgent should not have the same state as AI agents. Use a different state class.
        self.state = ExecutionState(event_bus)

    async def begin(self):
        pass

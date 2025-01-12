from typing import TYPE_CHECKING

from playbooks.core.agents.base_agent import Agent
from playbooks.enums import AgentType

if TYPE_CHECKING:
    from playbooks.core.runtime import PlaybooksRuntime


class HumanAgent(Agent):
    def __init__(self, klass: str = "Human"):
        super().__init__(klass, AgentType.HUMAN)

    def process_message(
        self,
        message: str,
        from_agent: "Agent",
        routing_type: str,
        runtime: "PlaybooksRuntime",
        stream: bool = True,
    ):
        print(message)

import uuid
from typing import TYPE_CHECKING

from playbooks.enums import AgentType

if TYPE_CHECKING:
    from playbooks.core.runtime import PlaybooksRuntime


class Agent:
    def __init__(self, klass: str, type: AgentType):
        self.id = uuid.uuid4()
        self.klass = klass
        self.type = type

    def process_message(
        self,
        message: str,
        from_agent: "Agent",
        routing_type: str,
        runtime: "PlaybooksRuntime",
        stream: bool = True,
    ):
        raise NotImplementedError

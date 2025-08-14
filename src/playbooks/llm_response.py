from typing import TYPE_CHECKING, List

from playbooks.event_bus import EventBus
from playbooks.llm_response_line import LLMResponseLine

if TYPE_CHECKING:
    from playbooks.agents import LocalAIAgent


class LLMResponse:
    def __init__(self, response: str, event_bus: EventBus, agent: "LocalAIAgent"):
        self.response = response
        self.event_bus = event_bus
        self.agent = agent
        self.lines: List[LLMResponseLine] = []
        self.parse_response()
        self.agent.state.last_llm_response = self.response

    def parse_response(self):
        lines = self.response.split("\n")
        for line in lines:
            self.lines.append(LLMResponseLine(line, self.event_bus, self.agent))

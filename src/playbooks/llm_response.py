from typing import TYPE_CHECKING, List

from playbooks.event_bus import EventBus
from playbooks.llm_response_line import LLMResponseLine
from playbooks.utils.async_init_mixin import AsyncInitMixin

if TYPE_CHECKING:
    from playbooks.agents import LocalAIAgent


class LLMResponse(AsyncInitMixin):
    def __init__(self, response: str, event_bus: EventBus, agent: "LocalAIAgent"):
        super().__init__()
        self.response = response
        self.event_bus = event_bus
        self.agent = agent
        self.lines: List[LLMResponseLine] = []
        self.agent.state.last_llm_response = self.response

    async def _async_init(self):
        await self.parse_response()

    async def parse_response(self):
        lines = self.response.split("\n")
        for line in lines:
            self.lines.append(
                await LLMResponseLine.create(line, self.event_bus, self.agent)
            )

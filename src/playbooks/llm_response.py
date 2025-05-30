from playbooks.ai_agent import AIAgent
from playbooks.event_bus import EventBus
from playbooks.llm_response_line import LLMResponseLine


class LLMResponse:
    def __init__(self, response: str, event_bus: EventBus, agent: AIAgent):
        self.response = response
        self.event_bus = event_bus
        self.agent = agent
        self.parse_llm_response(response, agent)
        self.agent.state.last_llm_response = self.response

    def parse_llm_response(self, response, agent):
        self.lines = [
            LLMResponseLine(line, self.event_bus, agent)
            for line in response.split("\n")
        ]

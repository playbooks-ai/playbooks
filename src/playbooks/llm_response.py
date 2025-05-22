from playbooks.event_bus import EventBus
from playbooks.llm_response_line import LLMResponseLine


class LLMResponse:
    def __init__(self, response: str, event_bus: EventBus):
        self.response = response
        self.event_bus = event_bus
        self.parse_llm_response(response)

    def parse_llm_response(self, response):
        self.lines = [
            LLMResponseLine(line, self.event_bus) for line in response.split("\n")
        ]

from playbooks.llm_response_line import LLMResponseLine


class LLMResponse:
    def __init__(self, response: str):
        self.response = response
        self.parse_llm_response(response)

    def parse_llm_response(self, response):
        self.lines = [LLMResponseLine(line) for line in response.split("\n")]

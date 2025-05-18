import re

from playbooks.llm_response_line import LLMResponseLine


class LLMResponse:
    def __init__(self, response: str):
        self.response = response
        self.parse_llm_response(response)

    def parse_llm_response(self, response):
        lines = []
        buffer = []
        in_artifact = False
        for line in response.split("\n"):
            if in_artifact:
                buffer.append(line)
                if re.search(r"`Artifact\[[^\]]+\] END`", line):
                    lines.append("\n".join(buffer))
                    buffer = []
                    in_artifact = False
                continue

            if re.search(r"`Artifact\[[^\]]+\] (CREATE|MODIFY)`", line):
                in_artifact = True
                buffer.append(line)
                if re.search(r"`Artifact\[[^\]]+\] END`", line):
                    lines.append("\n".join(buffer))
                    buffer = []
                    in_artifact = False
            else:
                lines.append(line)

        if buffer:
            lines.append("\n".join(buffer))

        self.lines = [LLMResponseLine(line) for line in lines]

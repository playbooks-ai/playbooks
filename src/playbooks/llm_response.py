import re
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
        # Handle multi-line blocks (artifacts, vars, and playbook calls) by keeping lines together

        # Find all artifact blocks with triple quotes (can span multiple lines)
        artifact_pattern = r'`Artifact\[\$[^,\]]+,\s*"[^"]+",\s*""".*?"""\]`'

        # Find all Var blocks with triple quotes (can span multiple lines)
        var_multiline_pattern = r'`Var\[\$[^,\]]+,\s*""".*?"""\]`'

        # Find all playbook calls with triple quotes (can span multiple lines)
        # Matches: `PlaybookName("""...""")` or `$var = PlaybookName("""...""")`
        playbook_call_pattern = r'`(?:\$[a-zA-Z_][a-zA-Z0-9_]*(?::[a-zA-Z_][a-zA-Z0-9_]*)?\s*=\s*)?[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*\([^`]*?""".*?"""[^`]*?\)`'

        # Check if there are any multi-line blocks in the response
        has_artifacts = re.search(artifact_pattern, self.response, re.DOTALL)
        has_var_multiline = re.search(var_multiline_pattern, self.response, re.DOTALL)
        has_playbook_calls = re.search(playbook_call_pattern, self.response, re.DOTALL)

        if has_artifacts or has_var_multiline or has_playbook_calls:
            # Replace newlines within blocks with placeholders
            # so they don't get split when we split by \n
            def replace_newlines(match):
                return match.group(0).replace("\n", "<<<MULTILINE_NEWLINE>>>")

            modified_text = self.response

            # Replace newlines in artifact blocks
            if has_artifacts:
                modified_text = re.sub(
                    artifact_pattern, replace_newlines, modified_text, flags=re.DOTALL
                )

            # Replace newlines in Var multiline blocks
            if has_var_multiline:
                modified_text = re.sub(
                    var_multiline_pattern,
                    replace_newlines,
                    modified_text,
                    flags=re.DOTALL,
                )

            # Replace newlines in playbook call blocks
            if has_playbook_calls:
                modified_text = re.sub(
                    playbook_call_pattern,
                    replace_newlines,
                    modified_text,
                    flags=re.DOTALL,
                )

            # Now split by actual newlines
            lines = modified_text.split("\n")

            # Restore the newlines in blocks
            lines = [line.replace("<<<MULTILINE_NEWLINE>>>", "\n") for line in lines]
        else:
            # No multi-line blocks, just split by lines normally
            lines = self.response.split("\n")

        for line in lines:
            self.lines.append(
                await LLMResponseLine.create(line, self.event_bus, self.agent)
            )

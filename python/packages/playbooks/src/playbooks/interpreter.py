import os
from typing import TYPE_CHECKING, List

from .constants import INTERPRETER_TRACE_HEADER
from .utils.llm_helper import get_completion

if TYPE_CHECKING:
    from .playbook import Playbook


class Interpreter:
    def __init__(self):
        pass

    def run(
        self,
        included_playbooks: List["Playbook"],
        instruction: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        messages = [
            {
                "role": "system",
                "content": self.get_system_prompt(included_playbooks),
            },
            {"role": "user", "content": instruction},
        ]

        # Get response from LLM
        for chunk in get_completion(
            llm_config=llm_config, messages=messages, stream=stream
        ):
            yield chunk

    def get_system_prompt(self, include_playbooks: List["Playbook"]) -> str:
        playbooks = "\n".join([playbook.markdown for playbook in include_playbooks])

        # load prompt from {os.path.dirname(__file__)}/prompts/interpreter_run.txt
        prompt = open(
            os.path.join(os.path.dirname(__file__), "prompts/interpreter_run.txt"),
            "r",
        ).read()
        prompt = prompt.replace(
            "{{INTERPRETER_TRACE_HEADER}}", INTERPRETER_TRACE_HEADER
        )
        prompt = prompt.replace("{{playbooks}}", playbooks)

        return prompt

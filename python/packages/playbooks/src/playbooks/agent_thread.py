from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .agent import Agent

from .interpreter import Interpreter
from .playbook import Playbook


class AgentThread:
    def __init__(self, agent: "Agent"):
        self.agent = agent
        self.interpreter = Interpreter()

    def run(
        self,
        included_playbooks: List[Playbook],
        instruction: str,
        llm_config: dict = None,
        stream: bool = False,
    ):
        for chunk in self.interpreter.run(
            included_playbooks=included_playbooks,
            instruction=instruction,
            llm_config=llm_config,
            stream=stream,
        ):
            yield chunk

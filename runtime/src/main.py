from typing import Generator

from .llm import LLM
from .playbook import create_system_prompt, load_playbooks


class PlaybookRuntime:
    def __init__(
        self, project_path: str, model: str = "anthropic/claude-3-sonnet-20240229"
    ):
        self.llm = LLM(model)
        self.playbooks, self.config = load_playbooks(project_path)
        self.system_prompt = create_system_prompt(self.playbooks, self.config)
        self.session = None

    def start_conversation(self):
        self.session = self.llm.create_chat_session(self.system_prompt)

    def chat(self, message: str) -> Generator[str, None, None]:
        if not self.session:
            self.start_conversation()
        return self.llm.chat(self.session, message)

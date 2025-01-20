from typing import List

from .agent_builder import AgentBuilder
from .exceptions import PlaybookError
from .playbook_loader import PlaybookLoader


class AgentFactory:
    @staticmethod
    def from_playbooks_paths(playbooks_paths: List[str]):
        try:
            ast = PlaybookLoader.load_and_parse(playbooks_paths)
        except PlaybookError as e:
            raise e

        return AgentBuilder.create_agents_from_ast(ast)

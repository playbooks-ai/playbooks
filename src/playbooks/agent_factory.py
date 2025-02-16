from typing import Dict, List, Type

from .agent_builder import AgentBuilder
from .config import LLMConfig
from .exceptions import PlaybookError
from .playbook_loader import PlaybookLoader
from .types import Agent


class AgentFactory:
    @staticmethod
    def from_playbooks_paths(
        playbooks_paths: List[str], llm_config: LLMConfig
    ) -> Dict[str, Type[Agent]]:
        try:
            ast = PlaybookLoader.load_from_files(playbooks_paths, llm_config)
        except PlaybookError as e:
            raise e
        except ValueError as e:
            raise PlaybookError(f"Failed to parse playbook: {str(e)}") from e

        return AgentBuilder.create_agents_from_ast(ast)

    @staticmethod
    def from_playbooks_content(
        playbooks_content: str, llm_config: LLMConfig
    ) -> Dict[str, Type[Agent]]:
        try:
            ast = PlaybookLoader.load(playbooks_content, llm_config)
        except PlaybookError as e:
            raise e
        except ValueError as e:
            raise PlaybookError(f"Failed to parse playbook: {str(e)}") from e

        return AgentBuilder.create_agents_from_ast(ast)

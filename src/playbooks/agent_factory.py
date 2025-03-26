from typing import Dict, List, Type

from .agent_builder import AgentBuilder
from .config import LLMConfig
from .exceptions import PlaybookError
from .playbook_loader import PlaybookLoader
from .types import Agent


class AgentFactory:
    """
    Factory class for creating Agent instances from playbook definitions.

    This class provides static methods to load playbooks from files or content
    and convert them into Agent classes.
    """

    @staticmethod
    def from_playbooks_paths(
        playbooks_paths: List[str], llm_config: LLMConfig
    ) -> Dict[str, Type[Agent]]:
        """
        Create Agent classes from playbook files.

        Args:
            playbooks_paths: List of file paths or glob patterns to load
            llm_config: LLM configuration for processing the playbooks

        Returns:
            Dictionary mapping agent names to their dynamically created classes

        Raises:
            PlaybookError: If there are issues loading or parsing the playbooks
        """
        try:
            ast = PlaybookLoader.load_from_files(playbooks_paths, llm_config)
            return AgentBuilder.create_agents_from_ast(ast)
        except ValueError as e:
            raise PlaybookError(f"Failed to parse playbook: {str(e)}") from e

    @staticmethod
    def from_playbooks_content(
        playbooks_content: str, llm_config: LLMConfig
    ) -> Dict[str, Type[Agent]]:
        """
        Create Agent classes from playbook content string.

        Args:
            playbooks_content: String containing playbook definitions
            llm_config: LLM configuration for processing the playbooks

        Returns:
            Dictionary mapping agent names to their dynamically created classes

        Raises:
            PlaybookError: If there are issues parsing the playbook content
        """
        try:
            ast = PlaybookLoader.load(playbooks_content, llm_config)
            return AgentBuilder.create_agents_from_ast(ast)
        except ValueError as e:
            raise PlaybookError(f"Failed to parse playbook: {str(e)}") from e

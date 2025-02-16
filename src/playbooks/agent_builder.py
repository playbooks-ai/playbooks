import re
from typing import Dict, Type

from .agent import Agent
from .exceptions import AgentConfigurationError
from .playbook import Playbook
from .utils.markdown_to_ast import refresh_markdown_attributes


class AgentBuilder:
    """Responsible for dynamically generating Agent classes from playbook AST."""

    @staticmethod
    def create_agents_from_ast(ast: Dict) -> Dict[str, Type[Agent]]:
        """
        Create agent classes from the AST representation of playbooks.

        Args:
            ast: AST dictionary containing playbook definitions

        Returns:
            Dict[str, Type[Agent]]: Dictionary mapping agent names to their classes
        """
        agents = {
            h1["text"]: AgentBuilder.create_agent_class_from_h1(h1)
            for h1 in ast.get("children", [])
            if h1.get("type") == "h1"
        }

        return agents

    @staticmethod
    def create_agent_class_from_h1(h1: Dict) -> Type[Agent]:
        """
        Create an Agent class from an H1 section in the AST.

        Args:
            h1: Dictionary representing an H1 section from the AST

        Returns:
            Type[Agent]: Dynamically created Agent class

        Raises:
            AgentConfigurationError: If agent configuration is invalid
        """
        klass = h1["text"]
        if not klass:
            raise AgentConfigurationError("Agent name is required")

        description = h1.get("description", "")

        playbooks = [
            Playbook.from_h2(h2)
            for h2 in h1.get("children", [])
            if h2.get("type") == "h2"
        ]

        # Python code blocks were removed from EXT playbooks,
        # so we need to refresh the markdown attributes to ensure that
        # python code is not sent to the LLM with playbooks
        refresh_markdown_attributes(h1)

        if not playbooks:
            raise AgentConfigurationError(f"No playbooks defined for AI agent {klass}")

        agent_class_name = AgentBuilder.make_agent_class_name(klass)

        # if class already exists, raise exception
        if agent_class_name in globals():
            raise AgentConfigurationError(
                f'Agent class {agent_class_name} already exists for agent "{klass}"'
            )

        def __init__(self):
            Agent.__init__(
                self, klass=klass, description=description, playbooks=playbooks
            )

        # print(f'Creating agent class {agent_class_name} for agent "{klass}"')
        return type(
            agent_class_name,
            (Agent,),
            {
                "__init__": __init__,
            },
        )

    @staticmethod
    def make_agent_class_name(klass: str) -> str:
        """
        Given a string (klass), return a CamelCase class name prefixed with "Agent".
        Non-alphanumeric characters are removed; multiple spaces are collapsed.

        Args:
            klass: Input string to convert to class name

        Returns:
            str: CamelCase class name prefixed with "Agent"

        Example:
            Input:  "This    is my agent!"
            Output: "AgentThisIsMyAgent"
        """
        # Replace any non-alphanumeric sequence with a single space
        cleaned = re.sub(r"[^A-Za-z0-9]+", " ", klass)

        # Split on whitespace, filter out empties
        words = cleaned.split()

        # Capitalize each word
        capitalized_words = [w.capitalize() for w in words]

        # Join and prefix with "Agent"
        return "Agent" + "".join(capitalized_words)

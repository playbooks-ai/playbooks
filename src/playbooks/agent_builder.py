import re
from typing import Dict, Type

from .agent import Agent
from .exceptions import AgentConfigurationError
from .playbook import Playbook
from .utils.markdown_to_ast import refresh_markdown_attributes


class AgentBuilder:
    """
    Responsible for dynamically generating Agent classes from playbook AST.
    This class provides static methods to create Agent classes based on
    the Abstract Syntax Tree representation of playbooks.
    """

    @staticmethod
    def create_agents_from_ast(ast: Dict) -> Dict[str, Type[Agent]]:
        """
        Create agent classes from the AST representation of playbooks.

        Args:
            ast: AST dictionary containing playbook definitions

        Returns:
            Dict[str, Type[Agent]]: Dictionary mapping agent names to their classes
        """
        agents = {}
        for h1 in ast.get("children", []):
            if h1.get("type") == "h1":
                agent_name = h1["text"]
                agents[agent_name] = AgentBuilder.create_agent_class_from_h1(h1)

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

        description, h2s = AgentBuilder._extract_description_and_h2s(h1)

        # Create playbooks from H2 sections
        playbooks = [Playbook.from_h2(h2) for h2 in h2s]
        if not playbooks:
            raise AgentConfigurationError(f"No playbooks defined for AI agent {klass}")

        # Map playbooks by their class name
        playbooks = {playbook.klass: playbook for playbook in playbooks}

        # Refresh markdown attributes to ensure Python code is not sent to the LLM
        refresh_markdown_attributes(h1)

        # Create a valid Python class name
        agent_class_name = AgentBuilder.make_agent_class_name(klass)

        # Check if class already exists
        if agent_class_name in globals():
            raise AgentConfigurationError(
                f'Agent class {agent_class_name} already exists for agent "{klass}"'
            )

        # Define __init__ for the new class
        def __init__(self):
            Agent.__init__(
                self, klass=klass, description=description, playbooks=playbooks
            )

        # Create and return the new Agent class
        return type(
            agent_class_name,
            (Agent,),
            {
                "__init__": __init__,
            },
        )

    @staticmethod
    def _extract_description_and_h2s(h1: Dict) -> tuple:
        """
        Extract description and h2 sections from H1 node.

        Args:
            h1: Dictionary representing an H1 section from the AST

        Returns:
            tuple: (description, list of h2 sections)
        """
        description_parts = []
        h2s = []

        for child in h1.get("children", []):
            if child.get("type") == "h2":
                h2s.append(child)
            else:
                description_text = child.get("text", "").strip()
                if description_text:
                    description_parts.append(description_text)

        description = "\n".join(description_parts).strip() or None
        return description, h2s

    @staticmethod
    def make_agent_class_name(klass: str) -> str:
        """
        Convert a string to a valid CamelCase class name prefixed with "Agent".

        Args:
            klass: Input string to convert to class name

        Returns:
            str: CamelCase class name prefixed with "Agent"

        Example:
            Input:  "This    is my agent!"
            Output: "AgentThisIsMyAgent"
        """
        # Replace any non-alphanumeric characters with a single space
        cleaned = re.sub(r"[^A-Za-z0-9]+", " ", klass)

        # Split on whitespace and filter out empty strings
        words = [w for w in cleaned.split() if w]

        # Capitalize each word and join
        capitalized_words = [w.capitalize() for w in words]

        # Prefix with "Agent" and return
        return "Agent" + "".join(capitalized_words)

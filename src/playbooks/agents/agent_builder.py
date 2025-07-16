import re
from typing import TYPE_CHECKING, Dict, Optional, Type, Union

from playbooks.exceptions import AgentConfigurationError
from playbooks.utils.parse_utils import parse_metadata_and_description

from . import LocalAIAgent, MCPAgent
from .builtin_playbooks import BuiltinPlaybooks
from .namespace_manager import AgentNamespaceManager
from .registry import AgentClassRegistry

if TYPE_CHECKING:
    pass


class AgentBuilder:
    """
    This class creates Agent classes based on the Abstract Syntax Tree
    representation of playbooks.
    """

    def __init__(self):
        """Initialize a new AgentBuilder instance."""
        self.namespace_manager = AgentNamespaceManager()
        self.builtin_playbooks = BuiltinPlaybooks()
        self.playbooks = {}

    @classmethod
    def create_agent_classes_from_ast(
        cls, ast: Dict
    ) -> Dict[str, Type[Union[LocalAIAgent, MCPAgent]]]:
        """
        Create agent classes from the AST representation of playbooks.

        Args:
            ast: AST dictionary containing playbook definitions

        Returns:
            Dict[str, Type[Union[LocalAIAgent, MCPAgent]]]: Dictionary mapping agent names to their classes
        """
        agents = {}
        for h1 in ast.get("children", []):
            if h1.get("type") == "h1":
                agent_name = h1["text"].strip()
                builder = cls()
                h1["children"].extend(builder.builtin_playbooks.get_ast_nodes())
                agents[agent_name] = builder.create_agent_class_from_h1(h1)

        return agents

    def create_agent_class_from_h1(
        self, h1: Dict
    ) -> Type[Union[LocalAIAgent, MCPAgent]]:
        """
        Create an Agent class from an H1 section in the AST.

        Args:
            h1: Dictionary representing an H1 section from the AST

        Returns:
            Type[Union[LocalAIAgent, MCPAgent]]: Dynamically created Agent class

        Raises:
            AgentConfigurationError: If agent configuration is invalid
        """
        klass = h1["text"].strip()

        # Check if agent name is provided
        if not klass:
            raise AgentConfigurationError("Agent name is required")

        # Check if class name is a valid CamelCase class name
        if not self.check_camelcase(klass):
            raise AgentConfigurationError(
                f"Agent name '{klass}' is not a valid CamelCase class name"
            )

        # Check if class already exists
        if klass in globals():
            raise AgentConfigurationError(f"Duplicate agent class {klass}")

        description = self._extract_description(h1)

        # Parse metadata to check for remote configuration
        metadata, description = parse_metadata_and_description(description)

        # Find appropriate agent class using registry
        agent_class = AgentClassRegistry.find_agent_class(metadata)
        if agent_class is None:
            raise AgentConfigurationError(
                f"No agent class can handle the configuration for agent {klass}. "
                f"Metadata: {metadata}"
            )

        # Create agent class using the found agent class factory
        return agent_class.create_class(
            klass,
            description,
            metadata,
            h1,
            h1.get("line_number"),
            self.namespace_manager,
        )

    @staticmethod
    def _extract_description(h1: Dict) -> Optional[str]:
        """
        Extract description from H1 node.

        Args:
            h1: Dictionary representing an H1 section from the AST

        Returns:
            Optional[str]: description or None if no description
        """
        description_parts = []

        for child in h1.get("children", []):
            if child.get("type") == "paragraph" or child.get("type") == "hr":
                description_text = child.get("text", "").strip()
                if description_text:
                    description_parts.append(description_text)

        description = "\n".join(description_parts).strip() or None
        return description

    # @staticmethod
    # def make_agent_class_name(klass: str) -> str:
    #     """Convert a string to a valid CamelCase class name prefixed with "Agent".

    #     Args:
    #         klass: Input string to convert to class name

    #     Returns:
    #         str: CamelCase class name prefixed with "Agent"

    #     Example:
    #         Input:  "This    is my agent!"
    #         Output: "AgentThisIsMyAgent"
    #     """
    #     import re

    #     # Replace any non-alphanumeric characters with a single space
    #     cleaned = re.sub(r"[^A-Za-z0-9]+", " ", klass)

    #     # Split on whitespace and filter out empty strings
    #     words = [w for w in cleaned.split() if w]

    #     # Capitalize each word and join
    #     capitalized_words = [w.capitalize() for w in words]

    #     # Prefix with "Agent" and return
    #     return "Agent" + "".join(capitalized_words)

    def check_camelcase(self, str: str) -> bool:
        """Check if a string is a valid CamelCase class name."""
        # Allow standard PascalCase with letters and numbers
        pattern = "^[A-Z][a-zA-Z0-9]*$"
        if re.match(pattern, str):
            return True
        else:
            return False

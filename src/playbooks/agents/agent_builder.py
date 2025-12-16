"""Agent builder for creating agent classes from playbook AST.

This module provides the AgentBuilder class that converts abstract syntax tree
representations of playbooks into executable agent classes with proper metadata
and configuration.
"""

import re
from typing import TYPE_CHECKING, Dict, Optional, Type, Union

from playbooks.agents.delivery_preferences import DeliveryPreferences
from playbooks.compilation.markdown_to_ast import refresh_markdown_attributes
from playbooks.compilation.parse_utils import parse_metadata_and_description
from playbooks.core.exceptions import AgentConfigurationError
from playbooks.utils.text_utils import is_camel_case, to_camel_case

from . import LocalAIAgent, MCPAgent
from .builtin_playbooks import BuiltinPlaybooks
from .human_agent import HumanAgent
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

    @staticmethod
    def parse_agent_header(header_text: str) -> tuple[str, str]:
        """Parse H1 header to extract agent name and type.

        Supports type annotations in the format "AgentName:Type".

        Examples:
            "Host" → ("Host", "AI")
            "Host:AI" → ("Host", "AI")
            "User:Human" → ("User", "Human")
            "FileSystem:MCP" → ("FileSystem", "MCP")

        Args:
            header_text: The H1 header text (already stripped of #)

        Returns:
            Tuple of (agent_name, agent_type) where agent_type defaults to "AI"

        Raises:
            AgentConfigurationError: If agent type is invalid
        """
        clean_header = header_text.strip()

        # Check for type annotation
        if ":" in clean_header:
            name, agent_type = clean_header.split(":", 1)
            name = name.strip()
            agent_type = agent_type.strip()

            # Validate agent type
            valid_types = ["AI", "Human", "MCP"]
            if agent_type not in valid_types:
                raise AgentConfigurationError(
                    f"Invalid agent type: '{agent_type}'. Must be one of {valid_types}"
                )

            return name, agent_type
        else:
            # No type annotation - default to AI
            return clean_header, "AI"

    @staticmethod
    def _extract_delivery_preferences(metadata: Dict) -> DeliveryPreferences:
        """Extract delivery preferences from agent metadata.

        Parses metadata dict to create DeliveryPreferences for human agents.
        Missing fields use sensible defaults.

        Args:
            metadata: Agent metadata dictionary from playbook

        Returns:
            DeliveryPreferences instance

        Examples:
            metadata = {
                "delivery_channel": "streaming",
                "meeting_notifications": "all"
            }
            prefs = _extract_delivery_preferences(metadata)
        """
        return DeliveryPreferences(
            channel=metadata.get("delivery_channel", "streaming"),
            streaming_enabled=metadata.get("streaming_enabled", True),
            streaming_chunk_size=metadata.get("streaming_chunk_size", 1),
            buffer_messages=metadata.get("buffer_messages", False),
            buffer_timeout=metadata.get("buffer_timeout", 5.0),
            meeting_notifications=metadata.get("meeting_notifications", "targeted"),
            custom_handler=metadata.get("delivery_handler"),
        )

    def _create_human_agent_class(
        self,
        klass: str,
        description: str,
        metadata: Dict,
        h1: Dict,
    ) -> Type[HumanAgent]:
        """Create a HumanAgent subclass from AST.

        Creates a dynamic HumanAgent subclass with instance-specific attributes
        for name, description, metadata, and delivery preferences.

        Args:
            klass: Agent class name (e.g. "Alice", "Bob")
            description: Agent description from playbook
            metadata: Agent metadata dictionary
            h1: H1 node from AST

        Returns:
            Dynamically created HumanAgent subclass

        Examples:
            From playbook:
                # Alice:Human
                Description: Project manager who coordinates team activities
                metadata:
                  name: Alice Chen
                  delivery_channel: streaming

            Usage:
                agent_class = _create_human_agent_class("Alice", "Project manager...", metadata, h1)
        """
        # Extract human-readable name from metadata
        human_name = metadata.get("name", klass)

        # Extract delivery preferences from metadata
        delivery_preferences = self._extract_delivery_preferences(metadata)

        # Create HumanAgent subclass dynamically
        class DynamicHumanAgent(HumanAgent):
            """Dynamically created HumanAgent subclass."""

            pass

        # Set class attributes
        DynamicHumanAgent.klass = klass
        DynamicHumanAgent.description = description or f"Human agent {klass}"
        DynamicHumanAgent.metadata = metadata
        DynamicHumanAgent.human_name = human_name
        DynamicHumanAgent.delivery_preferences = delivery_preferences

        # Set class name for better debugging
        DynamicHumanAgent.__name__ = klass
        DynamicHumanAgent.__qualname__ = klass

        return DynamicHumanAgent

    @classmethod
    async def create_agent_classes_from_ast(
        cls, ast: Dict
    ) -> Dict[str, Type[Union[LocalAIAgent, MCPAgent, HumanAgent]]]:
        """
        Create agent classes from the AST representation of playbooks.

        Supports agent type annotations in H1 headers (e.g. "# User:Human").

        Args:
            ast: AST dictionary containing playbook definitions

        Returns:
            Dict[str, Type[Union[LocalAIAgent, MCPAgent, HumanAgent]]]: Dictionary mapping agent names to their classes
        """
        agents = {}
        for h1 in ast.get("children", []):
            if h1.get("type") == "h1":
                # Parse header for agent name and type
                agent_name, agent_type = cls.parse_agent_header(h1["text"])

                # Store agent type in H1 node for later use
                h1["agent_type"] = agent_type

                # Ensure agent name is CamelCase
                if not is_camel_case(agent_name):
                    agent_name = to_camel_case(agent_name)

                # Update H1 text to just the agent name (remove type annotation)
                h1["text"] = agent_name
                refresh_markdown_attributes(h1)

                builder = cls()
                builtin_nodes = await builder.builtin_playbooks.get_ast_nodes()
                h1["children"].extend(builtin_nodes)
                agents[agent_name] = builder.create_agent_class_from_h1(h1)

        return agents

    def create_agent_class_from_h1(
        self, h1: Dict
    ) -> Type[Union[LocalAIAgent, MCPAgent, HumanAgent]]:
        """
        Create an Agent class from an H1 section in the AST.

        Routes to appropriate factory based on agent type:
        - :Human → _create_human_agent_class()
        - :AI/:MCP → Registry-based creation

        Args:
            h1: Dictionary representing an H1 section from the AST

        Returns:
            Type[Union[LocalAIAgent, MCPAgent, HumanAgent]]: Dynamically created Agent class

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

        # Parse metadata
        metadata, description = parse_metadata_and_description(description)

        # Get agent type (set by create_agent_classes_from_ast)
        agent_type = h1.get("agent_type", "AI")

        # Route to appropriate factory based on agent type
        if agent_type == "Human":
            # Create HumanAgent subclass
            return self._create_human_agent_class(klass, description, metadata, h1)

        # For AI and MCP agents, use registry-based creation
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

import ast
import inspect
import re
import types
from typing import Any, Callable, Dict, List, Optional, Type, Union

from playbooks.event_bus import EventBus
from playbooks.markdown_playbook_execution import MarkdownPlaybookExecution

from .agents import LocalAIAgent, MCPAgent
from .config import LLMConfig
from .exceptions import AgentConfigurationError
from .playbook import MarkdownPlaybook, PlaybookTriggers, PythonPlaybook
from .playbook_decorator import playbook_decorator
from .utils.markdown_to_ast import markdown_to_ast, refresh_markdown_attributes
from .utils.parse_utils import parse_metadata_and_description


class AgentBuilder:
    """
    Responsible for dynamically generating Agent classes from playbook AST.
    This class creates Agent classes based on the Abstract Syntax Tree
    representation of playbooks.
    """

    def __init__(self):
        """Initialize a new AgentBuilder instance."""
        self.playbooks = {}
        self.agent_python_namespace = {}

    @classmethod
    def create_agents_from_ast(
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
                agent_name = h1["text"]
                builder = cls()
                h1["children"].extend(AgentBuilder._get_builtin_playbooks())
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
        klass = h1["text"]
        if not klass:
            raise AgentConfigurationError("Agent name is required")

        description = self._extract_description(h1)

        # Parse metadata to check for remote configuration
        metadata, _ = parse_metadata_and_description(description)

        # Check if this is a remote MCP agent
        if "remote" in metadata and metadata["remote"].get("type") == "mcp":
            return self._create_mcp_agent_class(
                klass, description, h1, metadata["remote"]
            )

        # Default to local agent
        self.playbooks = {}
        self.agent_python_namespace = {}

        # Process all children nodes
        self._process_code_blocks(h1)
        self._process_markdown_playbooks(h1)

        if not self.playbooks:
            raise AgentConfigurationError(f"No playbooks defined for AI agent {klass}")

        # Refresh markdown attributes to ensure Python code is not sent to the LLM
        refresh_markdown_attributes(h1)

        # Create Agent class
        return self._create_local_agent_class(klass, description, h1)

    def _create_mcp_agent_class(
        self,
        klass: str,
        description: str,
        h1: Dict,
        remote_config: Dict[str, Any],
    ) -> Type[MCPAgent]:
        """Create an MCP agent class."""
        agent_class_name = self.make_agent_class_name(klass)

        # Check if class already exists
        if agent_class_name in globals():
            raise AgentConfigurationError(
                f'Agent class {agent_class_name} already exists for agent "{klass}"'
            )

        # Comprehensive MCP configuration validation
        self._validate_mcp_configuration(klass, remote_config)

        source_line_number = h1.get("line_number")

        # Define __init__ for the new MCP agent class
        def __init__(self, event_bus: EventBus, agent_id: str = None):
            MCPAgent.__init__(
                self,
                klass=klass,
                description=description,
                event_bus=event_bus,
                remote_config=remote_config,
                source_line_number=source_line_number,
                agent_id=agent_id,
            )

        # Create and return the new MCP Agent class
        return type(
            agent_class_name,
            (MCPAgent,),
            {
                "__init__": __init__,
            },
        )

    def _validate_mcp_configuration(
        self, agent_name: str, remote_config: Dict[str, Any]
    ) -> None:
        """Validate MCP agent configuration comprehensively.

        Args:
            agent_name: Name of the agent being configured
            remote_config: Remote configuration dictionary

        Raises:
            AgentConfigurationError: If configuration is invalid
        """
        # Check if URL is present
        if "url" not in remote_config:
            raise AgentConfigurationError(
                f"MCP agent '{agent_name}' requires 'url' in remote configuration"
            )

        # Validate URL format
        url = remote_config["url"]
        if not isinstance(url, str):
            raise AgentConfigurationError(
                f"MCP agent '{agent_name}' requires a valid URL string, got: {type(url).__name__}"
            )

        if not url.strip():
            raise AgentConfigurationError(
                f"MCP agent '{agent_name}' requires a valid URL string, got empty string"
            )

        # Validate transport type if specified
        transport = remote_config.get("transport")
        if transport is not None:
            valid_transports = [
                "sse",
                "stdio",
                "websocket",
                "streamable-http",
                "memory",
            ]
            if transport not in valid_transports:
                raise AgentConfigurationError(
                    f"MCP agent '{agent_name}' has invalid transport '{transport}'. "
                    f"Valid options: {', '.join(valid_transports)}"
                )

        # Validate timeout if specified
        timeout = remote_config.get("timeout")
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise AgentConfigurationError(
                    f"MCP agent '{agent_name}' timeout must be a positive number, got: {timeout}"
                )

        # Validate auth configuration if specified
        auth = remote_config.get("auth")
        if auth is not None:
            if not isinstance(auth, dict):
                raise AgentConfigurationError(
                    f"MCP agent '{agent_name}' auth configuration must be a dictionary, got: {type(auth).__name__}"
                )

            # Validate auth type if specified
            auth_type = auth.get("type")
            if auth_type is not None:
                valid_auth_types = ["api_key", "bearer", "basic", "mtls"]
                if auth_type not in valid_auth_types:
                    raise AgentConfigurationError(
                        f"MCP agent '{agent_name}' has invalid auth type '{auth_type}'. "
                        f"Valid options: {', '.join(valid_auth_types)}"
                    )

                # Validate required fields for each auth type
                if auth_type == "api_key" and not auth.get("key"):
                    raise AgentConfigurationError(
                        f"MCP agent '{agent_name}' with api_key auth requires 'key' field"
                    )
                elif auth_type == "bearer" and not auth.get("token"):
                    raise AgentConfigurationError(
                        f"MCP agent '{agent_name}' with bearer auth requires 'token' field"
                    )
                elif auth_type == "basic" and (
                    not auth.get("username") or not auth.get("password")
                ):
                    raise AgentConfigurationError(
                        f"MCP agent '{agent_name}' with basic auth requires 'username' and 'password' fields"
                    )
                elif auth_type == "mtls" and (
                    not auth.get("cert") or not auth.get("key")
                ):
                    raise AgentConfigurationError(
                        f"MCP agent '{agent_name}' with mtls auth requires 'cert' and 'key' fields"
                    )

        # Validate URL scheme matches transport
        if transport == "stdio":
            # For stdio, URL should be a file path or command
            if url.startswith(("http://", "https://", "ws://", "wss://")):
                raise AgentConfigurationError(
                    f"MCP agent '{agent_name}' with stdio transport should not use HTTP/WebSocket URL"
                )
        elif transport in ["sse", "streamable-http"]:
            # For HTTP-based transports, URL should be HTTP(S)
            if not url.startswith(("http://", "https://")):
                raise AgentConfigurationError(
                    f"MCP agent '{agent_name}' with {transport} transport requires HTTP(S) URL"
                )
        elif transport == "websocket":
            # For WebSocket, URL should be ws(s)://
            if not url.startswith(("ws://", "wss://", "http://", "https://")):
                raise AgentConfigurationError(
                    f"MCP agent '{agent_name}' with websocket transport requires WebSocket or HTTP URL"
                )

    def _process_code_blocks(self, h1: Dict) -> None:
        """Process code blocks in the AST and extract playbooks."""
        for child in h1.get("children", []):
            if child.get("type") == "code-block":
                new_playbooks = self.playbooks_from_code_block(child["text"])
                self.playbooks.update(new_playbooks)

    def _process_markdown_playbooks(self, h1: Dict) -> None:
        """Process H2 sections in the AST and extract markdown playbooks."""
        for child in h1["children"]:
            if child.get("type") == "h2":
                playbook = MarkdownPlaybook.from_h2(child)
                self.playbooks[playbook.name] = playbook
                wrapper = self.create_markdown_playbook_python_wrapper(playbook)
                playbook.func = wrapper
                playbook.func.__globals__.update(self.agent_python_namespace)

                def create_call_through_agent(agent_python_namespace, playbook):
                    def call_through_agent(*args, **kwargs):
                        return agent_python_namespace["agent"].execute_playbook(
                            playbook.name, args, kwargs
                        )

                    return call_through_agent

                self.agent_python_namespace[playbook.name] = create_call_through_agent(
                    self.agent_python_namespace, playbook
                )

    def _create_local_agent_class(
        self,
        klass: str,
        description: Optional[str],
        h1: Dict,
    ) -> Type[LocalAIAgent]:
        """Create and return a new local Agent class."""
        agent_class_name = self.make_agent_class_name(klass)

        # Check if class already exists
        if agent_class_name in globals():
            raise AgentConfigurationError(
                f'Agent class {agent_class_name} already exists for agent "{klass}"'
            )

        # Store references to playbooks and namespace for closure
        playbooks = self.playbooks
        source_line_number = h1.get("line_number")

        # Define __init__ for the new class
        def __init__(self, event_bus: EventBus, agent_id: str = None):
            LocalAIAgent.__init__(
                self,
                klass=klass,
                description=description,
                playbooks=playbooks,
                event_bus=event_bus,
                source_line_number=source_line_number,
                agent_id=agent_id,
            )

        # Create and return the new Agent class
        return type(
            agent_class_name,
            (LocalAIAgent,),
            {
                "__init__": __init__,
            },
        )

    def playbooks_from_code_block(self, code_block: str) -> Dict[str, PythonPlaybook]:
        """
        Create playbooks from a code block.

        Args:
            code_block: Python code containing @playbook decorated functions

        Returns:
            Dict[str, PythonPlaybook]: Discovered playbooks
        """
        # Set up the execution environment
        existing_keys = list(self.agent_python_namespace.keys())
        environment = self._prepare_execution_environment()
        self.agent_python_namespace.update(environment)

        # Execute the code block in the isolated namespace
        python_local_namespace = {}
        exec(code_block, self.agent_python_namespace, python_local_namespace)
        self.agent_python_namespace.update(python_local_namespace)

        # Get code for each function
        function_code = {}
        parsed_code = ast.parse(code_block)
        for item in parsed_code.body:
            if isinstance(item, ast.AsyncFunctionDef) or isinstance(
                item, ast.FunctionDef
            ):
                function_code[item.name] = ast.unparse(item)

        # Discover all @playbook-decorated functions
        playbooks = self._discover_playbook_functions(existing_keys)

        # Add function code to playbooks
        for playbook in playbooks.values():
            playbook.code = function_code[playbook.name]

        return playbooks

    def _prepare_execution_environment(self) -> Dict[str, Any]:
        """Prepare the execution environment for code blocks."""
        environment = {}

        environment.update(
            {
                "playbook": playbook_decorator,  # Inject decorator
                "__builtins__": __builtins__,  # Safe default
            }
        )

        return environment

    def _discover_playbook_functions(
        self, existing_keys: List[str]
    ) -> Dict[str, PythonPlaybook]:
        """Discover playbook-decorated functions in the namespace."""
        playbooks = {}
        wrappers = {}

        for obj_name, obj in self.agent_python_namespace.items():
            if (
                isinstance(obj, types.FunctionType)
                and obj_name not in existing_keys
                and getattr(obj, "__is_playbook__", False)
            ):
                # Create playbook from decorated function
                playbooks[obj.__name__] = self._create_playbook_from_function(obj)

                def create_call_through_agent(agent_python_namespace, playbook):
                    def call_through_agent(*args, **kwargs):
                        return agent_python_namespace["agent"].execute_playbook(
                            playbook.name, args, kwargs
                        )

                    return call_through_agent

                wrappers[obj.__name__] = create_call_through_agent(
                    self.agent_python_namespace, playbooks[obj.__name__]
                )

        self.agent_python_namespace.update(wrappers)

        return playbooks

    @staticmethod
    def _create_playbook_from_function(func: Callable) -> PythonPlaybook:
        """Create a PythonPlaybook object from a decorated function."""
        sig = inspect.signature(func)
        signature = func.__name__ + str(sig)
        doc = inspect.getdoc(func)
        description = doc.split("\n")[0] if doc is not None else None
        triggers = getattr(func, "__triggers__", [])
        metadata = getattr(func, "__metadata__", {})

        # If triggers are not prefixed with T1:BGN, T1:CND, etc., add T{i}:CND
        # Use regex to find if prefix is missing
        triggers = [
            (
                f"T{i+1}:CND {trigger}"
                if not re.match(r"^T\d+:[A-Z]{3} ", trigger)
                else trigger
            )
            for i, trigger in enumerate(triggers)
        ]

        if triggers:
            triggers = PlaybookTriggers(
                playbook_klass=func.__name__,
                playbook_signature=signature,
                triggers=triggers,
            )
        else:
            triggers = None

        return PythonPlaybook(
            name=func.__name__,
            func=func,
            signature=signature,
            description=description,
            triggers=triggers,
            metadata=metadata,
        )

    @staticmethod
    def create_markdown_playbook_python_wrapper(playbook: MarkdownPlaybook) -> Callable:
        """
        Create an async python function with the markdown playbook's name and
        inject the function into the agent_python_namespace.
        This will allow python playbooks to call markdown playbooks.

        Args:
            playbook: The markdown playbook to create a wrapper for

        Returns:
            An async wrapper function
        """

        async def wrapper(*args, **kwargs):
            # TODO: Implement actual wrapper logic to call markdown playbooks
            agent = playbook.func.__globals__["agent"]
            execution = MarkdownPlaybookExecution(agent, playbook.name, LLMConfig())
            return await execution.execute(*args, **kwargs)

        return wrapper

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

    @staticmethod
    def _get_builtin_playbooks():
        """Add Say() Python playbook that prints given message."""
        code_block = """
```python
@playbook
async def SendMessage(target_agent_id: str, message: str):
    await agent.SendMessage(target_agent_id, message)

@playbook
async def WaitForMessage(source_agent_id: str) -> str | None:
    return await agent.WaitForMessage(source_agent_id)

@playbook
async def Say(target: str,message: str):
    resolved_target = agent.resolve_say_target(target)
    
    # Track last message target (only for 1:1 messages, not meetings)
    if not (resolved_target.startswith("meeting ") or resolved_target == "human"):
        agent.state.last_message_target = resolved_target
    
    await SendMessage(resolved_target, message)

@playbook
async def SaveArtifact(artifact_name: str, artifact_summary: str, artifact_content: str):
    agent.state.artifacts.set(artifact_name, artifact_summary, artifact_content)

@playbook
async def LoadArtifact(artifact_name: str):
    return agent.state.artifacts[artifact_name]
```        
"""

        return markdown_to_ast(code_block)["children"]

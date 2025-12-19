"""MCP (Model Context Protocol) agent implementation.

This module provides agents that communicate with external MCP servers
for tool execution and remote playbook processing.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Type

from playbooks.core.exceptions import AgentConfigurationError
from playbooks.infrastructure.event_bus import EventBus
from playbooks.playbook import RemotePlaybook
from playbooks.transport import MCPTransport

from .ai_agent import AIAgentMeta
from .registry import AgentClassRegistry
from .remote_ai_agent import RemoteAIAgent

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from playbooks.program import Program


class MCPAgentMeta(AIAgentMeta):
    """Meta class for MCPAgent."""

    def should_create_instance_at_start(self) -> bool:
        """Whether to create an instance of the agent at start.

        MCP agents are always created at start in standby mode.
        """
        return True


class MCPAgent(RemoteAIAgent, metaclass=MCPAgentMeta):
    """
    MCP (Model Context Protocol) agent implementation.

    This agent connects to MCP servers and exposes their tools as playbooks.
    """

    @classmethod
    def can_handle(cls, metadata: Dict[str, Any]) -> bool:
        """Check if this agent class can handle the given metadata.

        MCPAgent handles configurations with remote.type == "mcp".

        Args:
            metadata: Agent metadata from playbook

        Returns:
            bool: True if this agent can handle the metadata
        """
        return (
            "remote" in metadata
            and isinstance(metadata["remote"], dict)
            and metadata["remote"].get("type") == "mcp"
        )

    @staticmethod
    def create_class(
        klass: str,
        description: str,
        metadata: Dict[str, Any],
        h1: Dict,
        source_line_number: int,
        namespace_manager=None,
    ) -> Type["MCPAgent"]:
        """Create an MCP agent class.

        Args:
            klass: Agent class name
            description: Agent description
            metadata: Agent metadata containing remote config
            h1: AST node for the agent definition
            source_line_number: Line number in source where agent is defined

        Returns:
            Type[MCPAgent]: Dynamically created MCP Agent class

        Raises:
            AgentConfigurationError: If agent class already exists
        """
        MCPAgent.validate(klass, metadata["remote"])

        remote_config = metadata["remote"]

        # Extract source file path from h1 node
        source_file_path = h1.get("source_file_path")

        # Define __init__ for the new MCP agent class
        def __init__(
            self,
            event_bus: EventBus,
            agent_id: str = None,
            **kwargs,
        ):
            MCPAgent.__init__(
                self,
                event_bus=event_bus,
                remote_config=remote_config,
                source_line_number=source_line_number,
                source_file_path=source_file_path,
                agent_id=agent_id,
                **kwargs,
            )

        # Create and return the new MCP Agent class
        return type(
            klass,
            (MCPAgent,),
            {
                "__init__": __init__,
                "klass": klass,
                "description": description,
                "playbooks": {},
                "metadata": metadata,
            },
        )

    @staticmethod
    def validate(agent_name: str, remote_config: Dict[str, Any]) -> None:
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
            if url.startswith(("http://", "https://", "ws://", "wss://", "memory://")):
                raise AgentConfigurationError(
                    f"MCP agent '{agent_name}' with stdio transport should not use HTTP/WebSocket/Memory URL"
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
        elif transport == "memory":
            # For memory transport, URL should use memory:// scheme
            if not url.startswith("memory://"):
                raise AgentConfigurationError(
                    f"MCP agent '{agent_name}' with memory transport requires memory:// URL. "
                    f"Example: memory://path/to/server.py or memory://path/to/server.py?var=mcp"
                )

    def __init__(
        self,
        event_bus: EventBus,
        remote_config: Dict[str, Any],
        source_line_number: int = None,
        source_file_path: str = None,
        agent_id: str = None,
        program: "Program" = None,
        **kwargs,
    ):
        """Initialize an MCP agent.

        Args:
            event_bus: The event bus for publishing events.
            remote_config: MCP server configuration containing:
                - url: MCP server URL or command
                - transport: Transport type (sse, stdio, etc.)
                - auth: Optional authentication config
                - timeout: Optional timeout in seconds
            source_line_number: The line number in the source markdown where this
                agent is defined.
            source_file_path: The path to the source file where this agent is defined.
            agent_id: Optional agent ID. If not provided, will generate UUID.
        """
        super().__init__(
            event_bus=event_bus,
            remote_config=remote_config,
            source_line_number=source_line_number,
            source_file_path=source_file_path,
            agent_id=agent_id,
            program=program,
            **kwargs,
        )
        self.transport = MCPTransport(remote_config, source_file_path=source_file_path)

        # Initialize _busy variable to False
        self.state._busy = False

    async def discover_playbooks(self) -> None:
        """Discover MCP tools and create RemotePlaybook instances for each."""
        if self._discovered:
            return

        if not self._connected:
            await self.connect()

        try:
            logger.debug(f"Discovering MCP tools for agent {self.klass}")
            tools = await self.transport.list_tools()

            # Clear existing playbooks
            self.playbooks.clear()

            # Create RemotePlaybook for each MCP tool
            for tool in tools:
                # Handle both dict-style and object-style tool representations
                if hasattr(tool, "name"):
                    # FastMCP Tool object
                    tool_name = tool.name
                    tool_description = getattr(
                        tool, "description", f"MCP tool: {tool.name}"
                    )

                    # Handle input schema properly
                    if hasattr(tool, "inputSchema"):
                        if hasattr(tool.inputSchema, "model_dump"):
                            input_schema = tool.inputSchema.model_dump()
                        elif hasattr(tool.inputSchema, "dict"):
                            input_schema = tool.inputSchema.dict()
                        else:
                            input_schema = tool.inputSchema
                    else:
                        input_schema = {}
                else:
                    # Dict-style tool
                    tool_name = tool.get("name")
                    tool_description = tool.get("description", f"MCP tool: {tool_name}")
                    input_schema = tool.get("inputSchema", {})

                if not tool_name:
                    logger.warning(f"MCP tool missing name: {tool}")
                    continue

                # Create execution function for this tool - fix closure issue
                def create_execute_fn(tool_name, schema, agent):
                    async def execute_fn(*args, **kwargs):
                        # Set _busy to True when starting execution
                        agent.state._busy = True
                        try:
                            # Convert positional args to kwargs if needed
                            if args:
                                properties = schema.get("properties", {})
                                param_names = list(properties.keys())
                                # Map positional args to parameter names from schema in order
                                for i, arg in enumerate(args):
                                    if i < len(param_names):
                                        param_name = param_names[i]
                                        # Only set if not already in kwargs (kwargs take precedence)
                                        if param_name not in kwargs:
                                            kwargs[param_name] = arg

                            result = await self.transport.call_tool(tool_name, kwargs)
                            result_str = str(result.content[0].text)
                            if result.is_error:
                                result_str = f"Error: {result_str}"
                            return result_str
                        finally:
                            # Set _busy to False when execution completes (or on error)
                            agent.state._busy = False

                    return execute_fn

                execute_fn = create_execute_fn(tool_name, input_schema, self)

                # Extract parameter schema
                parameters = (
                    input_schema.get("properties", {})
                    if isinstance(input_schema, dict)
                    else {}
                )

                # Create RemotePlaybook
                playbook = RemotePlaybook(
                    name=tool_name,
                    description=tool_description,
                    agent_name=self.klass,
                    execute_fn=execute_fn,
                    parameters=parameters,
                    timeout=self.remote_config.get("timeout"),
                    metadata={"public": True},  # MCP tools are public by default
                )

                self.playbooks[tool_name] = playbook

            logger.info(
                f"Discovered {len(self.playbooks)} MCP tools for agent {self.klass}"
            )

            self.__class__.playbooks = self.playbooks
            self._discovered = True
        except Exception as e:
            logger.error(
                f"Failed to discover MCP tools for agent {self.klass}: {str(e)}"
            )
            raise

    async def begin(self):
        # MCP agent does not receive messages, nor has BGN playbooks, so we do nothing
        pass


# Register MCPAgent with the registry with higher priority than LocalAIAgent
AgentClassRegistry.register(MCPAgent, priority=10)

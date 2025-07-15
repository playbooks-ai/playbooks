import logging
from typing import TYPE_CHECKING, Any, Dict

from ..event_bus import EventBus
from ..playbook import RemotePlaybook
from ..transport import MCPTransport
from .ai_agent import AIAgentMeta
from .remote_ai_agent import RemoteAIAgent

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..program import Program


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

    def __init__(
        self,
        klass: str,
        description: str,
        event_bus: EventBus,
        remote_config: Dict[str, Any],
        source_line_number: int = None,
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
            agent_id: Optional agent ID. If not provided, will generate UUID.
        """
        self.__class__.klass = klass
        self.__class__.description = description
        self.__class__.playbooks = {}
        super().__init__(
            event_bus=event_bus,
            remote_config=remote_config,
            source_line_number=source_line_number,
            agent_id=agent_id,
            program=program,
            **kwargs,
        )
        self.transport = MCPTransport(remote_config)

    async def discover_playbooks(self) -> None:
        """Discover MCP tools and create RemotePlaybook instances for each."""
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
                def create_execute_fn(tool_name, schema):
                    async def execute_fn(*args, **kwargs):
                        # Convert positional args to kwargs if needed
                        if args and not kwargs:
                            # If only positional args, try to map them to the first parameter
                            properties = schema.get("properties", {})
                            if len(args) == 1 and len(properties) == 1:
                                param_name = list(properties.keys())[0]
                                kwargs = {param_name: args[0]}
                            else:
                                # Multiple args - create numbered parameters
                                kwargs = {f"arg_{i}": arg for i, arg in enumerate(args)}

                        result = await self.transport.call_tool(tool_name, kwargs)
                        result_str = str(result.data)
                        if result.is_error:
                            result_str = f"Error: {result_str}"
                        return result_str

                    return execute_fn

                execute_fn = create_execute_fn(tool_name, input_schema)

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
        except Exception as e:
            logger.error(
                f"Failed to discover MCP tools for agent {self.klass}: {str(e)}"
            )
            raise

    async def begin(self):
        # MCP agent does not receive messages, nor has BGN playbooks, so we do nothing
        pass

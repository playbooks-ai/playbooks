"""MCP transport implementation using FastMCP client."""

import logging
from typing import Any, Dict, List, Optional

from fastmcp import Client
from fastmcp.client.transports import (
    PythonStdioTransport,
    SSETransport,
    StreamableHttpTransport,
)

from .protocol import TransportProtocol

logger = logging.getLogger(__name__)


class MCPTransport(TransportProtocol):
    """Transport implementation for MCP (Model Context Protocol) using FastMCP.

    This transport can connect to MCP servers using various underlying transports
    like SSE (Server-Sent Events), stdio, or WebSocket.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize MCP transport.

        Args:
            config: Configuration dictionary containing:
                - url: The MCP server URL or command
                - transport: Transport type ('sse', 'stdio', 'websocket', etc.)
                - auth: Optional authentication configuration
                - timeout: Optional timeout in seconds
        """
        super().__init__(config)
        self.url = config.get("url")
        self.transport_type = config.get("transport", "sse")  # Default to SSE
        self.auth = config.get("auth", {})
        self.timeout = config.get("timeout", 30.0)

        self.client: Optional[Client] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

        if not self.url:
            raise ValueError("MCP transport requires 'url' in configuration")

    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        if self._connected:
            return

        try:
            logger.debug(
                f"Connecting to MCP server at {self.url} using {self.transport_type}"
            )

            # Create the appropriate transport based on configuration
            if self.transport_type.lower() == "streamable-http":
                # Use StreamableHttpTransport for streamable-http servers
                transport = StreamableHttpTransport(self.url)
                self.client = Client(transport)
            elif self.transport_type.lower() == "sse":
                # Use SSETransport for traditional SSE servers
                transport = SSETransport(self.url)
                self.client = Client(transport)
            elif self.transport_type.lower() == "stdio":
                # For stdio, the URL should be a command/script path
                transport = PythonStdioTransport(self.url)
                self.client = Client(transport)
            else:
                # Let FastMCP auto-detect the transport
                self.client = Client(self.url)

            # Connect to the server
            await self.client.__aenter__()
            self._connected = True

            logger.info(f"Successfully connected to MCP server at {self.url}")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server at {self.url}: {str(e)}")
            raise ConnectionError(f"MCP connection failed: {str(e)}") from e

    async def disconnect(self) -> None:
        """Close connection to the MCP server."""
        if not self._connected or not self.client:
            return

        try:
            await self.client.__aexit__(None, None, None)
            logger.debug(f"Disconnected from MCP server at {self.url}")
        except Exception as e:
            logger.warning(f"Error during MCP disconnect: {str(e)}")
        finally:
            self.client = None
            self._connected = False
            self._tools_cache = None

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make a remote call using MCP protocol.

        Args:
            method: The method to call. For MCP, this can be:
                - 'list_tools': List available tools
                - 'call_tool': Call a specific tool (requires tool_name in params)
                - 'list_resources': List available resources
                - 'read_resource': Read a specific resource (requires uri in params)
                - 'get_prompt': Get a prompt (requires name in params)
            params: Parameters for the method call

        Returns:
            The result of the MCP call

        Raises:
            ConnectionError: If not connected
            ValueError: If method or params are invalid
            Exception: If the MCP call fails
        """
        if not self._connected or not self.client:
            raise ConnectionError("MCP transport not connected")

        if not method:
            raise ValueError("Method name is required")

        params = params or {}

        try:
            logger.debug(f"MCP call: {method} with params: {params}")

            if method == "list_tools":
                result = await self.client.list_tools()
                # Cache tools for later use
                self._tools_cache = result
                return result

            elif method == "call_tool":
                tool_name = params.get("tool_name")
                tool_args = params.get("arguments", {})
                if not tool_name:
                    raise ValueError("call_tool requires 'tool_name' parameter")
                result = await self.client.call_tool(tool_name, tool_args)
                return result

            elif method == "list_resources":
                result = await self.client.list_resources()
                return result

            elif method == "read_resource":
                uri = params.get("uri")
                if not uri:
                    raise ValueError("read_resource requires 'uri' parameter")
                result = await self.client.read_resource(uri)
                return result

            elif method == "get_prompt":
                name = params.get("name")
                prompt_args = params.get("arguments", {})
                if not name:
                    raise ValueError("get_prompt requires 'name' parameter")
                result = await self.client.get_prompt(name, prompt_args)
                return result

            elif method == "ping":
                result = await self.client.ping()
                return result

            else:
                raise ValueError(f"Unsupported MCP method: {method}")

        except Exception as e:
            logger.error(f"MCP call failed - method: {method}, error: {str(e)}")
            raise

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Convenience method to list available MCP tools."""
        return await self.call("list_tools")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Convenience method to call an MCP tool."""
        return await self.call(
            "call_tool", {"tool_name": tool_name, "arguments": arguments}
        )

    async def list_resources(self) -> List[Dict[str, Any]]:
        """Convenience method to list available MCP resources."""
        return await self.call("list_resources")

    async def read_resource(self, uri: str) -> Any:
        """Convenience method to read an MCP resource."""
        return await self.call("read_resource", {"uri": uri})

    def get_cached_tools(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached tools list if available."""
        return self._tools_cache

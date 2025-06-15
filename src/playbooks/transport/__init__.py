"""Transport layer for remote playbook execution.

This module provides the transport protocol interface and implementations
for communicating with remote agents and services.
"""

from .mcp_transport import MCPTransport
from .protocol import TransportProtocol

__all__ = ["TransportProtocol", "MCPTransport"]

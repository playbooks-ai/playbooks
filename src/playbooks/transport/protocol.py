"""Abstract transport protocol interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class TransportProtocol(ABC):
    """Abstract base class for transport protocols.

    This interface defines the contract that all transport implementations
    must follow, whether they use HTTP, gRPC, WebSocket, stdio, or other protocols.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the transport with configuration.

        Args:
            config: Transport-specific configuration dictionary
        """
        self.config = config
        self._connected = False

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the remote service.

        Raises:
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the remote service.

        This should be safe to call multiple times.
        """
        pass

    @abstractmethod
    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make a remote call using this transport.

        Args:
            method: The method/endpoint to call
            params: Parameters to pass to the remote method

        Returns:
            The result of the remote call

        Raises:
            ConnectionError: If not connected or connection fails
            ValueError: If method or params are invalid
            Exception: If the remote call fails
        """
        pass

    @property
    def is_connected(self) -> bool:
        """Check if the transport is currently connected."""
        return self._connected

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

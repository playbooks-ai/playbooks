"""Tests for the transport protocol interface."""

from typing import Any, Dict, Optional

import pytest

from src.playbooks.transport.protocol import TransportProtocol


class MockTransport(TransportProtocol):
    """Mock transport implementation for testing."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connect_called = False
        self.disconnect_called = False
        self.call_history = []

    async def connect(self) -> None:
        """Mock connect implementation."""
        self.connect_called = True
        self._connected = True

    async def disconnect(self) -> None:
        """Mock disconnect implementation."""
        self.disconnect_called = True
        self._connected = False

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Mock call implementation."""
        if not self._connected:
            raise ConnectionError("Not connected")
        self.call_history.append((method, params))
        return f"mock_result_{method}"


class TestTransportProtocol:
    """Test cases for the TransportProtocol interface."""

    def test_init(self):
        """Test transport initialization."""
        config = {"url": "test://example.com"}
        transport = MockTransport(config)

        assert transport.config == config
        assert not transport.is_connected

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        """Test connect and disconnect functionality."""
        transport = MockTransport({"url": "test://example.com"})

        # Initially not connected
        assert not transport.is_connected
        assert not transport.connect_called

        # Connect
        await transport.connect()
        assert transport.is_connected
        assert transport.connect_called

        # Disconnect
        await transport.disconnect()
        assert not transport.is_connected
        assert transport.disconnect_called

    @pytest.mark.asyncio
    async def test_call_when_connected(self):
        """Test making calls when connected."""
        transport = MockTransport({"url": "test://example.com"})
        await transport.connect()

        result = await transport.call("test_method", {"param": "value"})

        assert result == "mock_result_test_method"
        assert len(transport.call_history) == 1
        assert transport.call_history[0] == ("test_method", {"param": "value"})

    @pytest.mark.asyncio
    async def test_call_when_not_connected(self):
        """Test that calls fail when not connected."""
        transport = MockTransport({"url": "test://example.com"})

        with pytest.raises(ConnectionError, match="Not connected"):
            await transport.call("test_method")

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using transport as async context manager."""
        transport = MockTransport({"url": "test://example.com"})

        async with transport as t:
            assert t is transport
            assert transport.is_connected
            assert transport.connect_called

            # Should be able to make calls
            result = await t.call("test_method")
            assert result == "mock_result_test_method"

        # Should be disconnected after context
        assert not transport.is_connected
        assert transport.disconnect_called

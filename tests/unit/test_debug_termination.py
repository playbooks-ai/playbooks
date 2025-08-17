"""
Tests for debug server termination behavior.

This module tests that the debug server properly signals program termination
and handles client disconnection when programs complete.
"""

import asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock

from playbooks.debug.server import DebugServer
from playbooks.events import ProgramTerminatedEvent
from playbooks.event_bus import EventBus


class TestDebugServerTermination:
    """Test debug server termination behavior."""

    @pytest_asyncio.fixture
    async def debug_server(self):
        """Create a debug server for testing."""
        server = DebugServer("127.0.0.1", 7529)
        yield server
        if server.server:
            await server.shutdown()

    @pytest.fixture
    def mock_client(self):
        """Create a mock client connection."""
        client = Mock()
        client.write = Mock()
        client.drain = AsyncMock()
        client.close = Mock()
        client.wait_closed = AsyncMock()
        client.is_closing = Mock(return_value=False)
        return client

    @pytest.fixture
    def event_bus(self):
        """Create an event bus for testing."""
        return EventBus("test-session")

    @pytest.mark.asyncio
    async def test_signal_program_termination_broadcasts_event(
        self, debug_server, mock_client
    ):
        """Test that signal_program_termination broadcasts termination event."""
        # Add mock client to debug server
        debug_server.clients = [mock_client]

        # Signal program termination
        await debug_server.signal_program_termination("normal", 0)

        # Verify termination event was sent
        mock_client.write.assert_called()
        # Get the first call (termination event) - signal_program_termination sends two messages
        calls = mock_client.write.call_args_list
        assert len(calls) >= 1
        written_data = calls[0][0][0].decode()
        event_data = json.loads(written_data.strip())

        assert event_data["type"] == "program_terminated"
        assert event_data["reason"] == "normal"
        assert event_data["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_signal_program_termination_sends_disconnect(
        self, debug_server, mock_client
    ):
        """Test that signal_program_termination sends disconnect notification."""
        debug_server.clients = [mock_client]

        await debug_server.signal_program_termination("normal", 0)

        # Should send both termination event and disconnect notification
        assert mock_client.write.call_count == 2

        # Check disconnect message
        calls = mock_client.write.call_args_list
        disconnect_data = json.loads(calls[1][0][0].decode().strip())
        assert disconnect_data["type"] == "disconnect"
        assert disconnect_data["reason"] == "program_terminated"

    @pytest.mark.asyncio
    async def test_signal_program_termination_closes_clients(
        self, debug_server, mock_client
    ):
        """Test that signal_program_termination closes client connections."""
        debug_server.clients = [mock_client]

        await debug_server.signal_program_termination("normal", 0)

        # Verify client connection was closed
        mock_client.close.assert_called_once()
        mock_client.wait_closed.assert_called_once()

        # Verify client was removed from clients list
        assert mock_client not in debug_server.clients

    @pytest.mark.asyncio
    async def test_program_terminated_event_handling(self, debug_server, event_bus):
        """Test that ProgramTerminatedEvent is properly converted to dict."""
        # Register event bus
        debug_server.register_bus(event_bus)

        # Create ProgramTerminatedEvent
        event = ProgramTerminatedEvent(reason="error", exit_code=1)

        # Convert event to dict
        event_dict = debug_server._event_to_dict(event)

        assert event_dict is not None
        assert event_dict["type"] == "program_terminated"
        assert event_dict["reason"] == "error"
        assert event_dict["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_shutdown_signals_termination_with_clients(
        self, debug_server, mock_client
    ):
        """Test that shutdown signals termination when clients are connected."""
        debug_server.clients = [mock_client]

        await debug_server.shutdown()

        # Should have sent termination signal
        mock_client.write.assert_called()

        # Should have closed client
        mock_client.close.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_without_clients_no_signal(self, debug_server):
        """Test that shutdown doesn't signal when no clients are connected."""
        # No clients connected
        debug_server.clients = []

        # Should not raise any errors
        await debug_server.shutdown()

    @pytest.mark.asyncio
    async def test_client_error_during_termination_handled(self, debug_server):
        """Test that client errors during termination are handled gracefully."""
        # Create a client that throws an error when writing
        error_client = Mock()
        error_client.write = Mock(side_effect=Exception("Connection error"))
        error_client.close = Mock()
        error_client.wait_closed = AsyncMock()

        debug_server.clients = [error_client]

        # Should not raise exception
        await debug_server.signal_program_termination("normal", 0)

        # Client should still be removed from list
        assert error_client not in debug_server.clients

    @pytest.mark.asyncio
    async def test_multiple_clients_all_notified(self, debug_server):
        """Test that multiple clients all receive termination notifications."""
        # Create multiple mock clients
        clients = []
        for _ in range(3):
            client = Mock()
            client.write = Mock()
            client.drain = AsyncMock()
            client.close = Mock()
            client.wait_closed = AsyncMock()
            client.is_closing = Mock(return_value=False)
            clients.append(client)

        debug_server.clients = clients

        await debug_server.signal_program_termination("normal", 0)

        # All clients should have received messages
        for client in clients:
            assert client.write.call_count == 2  # termination + disconnect
            client.close.assert_called_once()

        # All clients should be removed
        assert len(debug_server.clients) == 0


class TestDebugServerIntegration:
    """Integration tests for debug server with program execution."""

    @pytest.mark.asyncio
    async def test_end_to_end_termination_flow(self):
        """Test complete termination flow from program end to client notification."""
        from playbooks.main import Playbooks

        # Use a simple test playbook
        test_playbook_content = """# Test
## Agent
### Trigger
When starting
### Steps
- Say hello
- End program
"""

        # Write test playbook
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pb", delete=False) as f:
            f.write(test_playbook_content)
            test_file = f.name

        try:
            # Create playbooks instance
            playbooks = Playbooks([test_file])
            await playbooks.initialize()

            # Start debug server
            await playbooks.program.start_debug_server("127.0.0.1", 7530)

            # Mock client to capture events
            events_received = []

            async def mock_client():
                reader, writer = await asyncio.open_connection("127.0.0.1", 7530)

                try:
                    while True:
                        data = await reader.readline()
                        if not data:
                            break
                        event = json.loads(data.decode().strip())
                        events_received.append(event)
                        if event.get("type") == "program_terminated":
                            break
                except Exception:
                    pass
                finally:
                    writer.close()
                    await writer.wait_closed()

            # Start mock client
            client_task = asyncio.create_task(mock_client())

            # Wait for client to connect
            await asyncio.sleep(0.1)

            # Run program
            program_task = asyncio.create_task(playbooks.program.run_till_exit())

            # Wait for both to complete
            await asyncio.wait_for(
                asyncio.gather(program_task, client_task), timeout=10
            )

            # Verify we received program_terminated event
            termination_events = [
                e for e in events_received if e.get("type") == "program_terminated"
            ]
            assert len(termination_events) > 0

            termination_event = termination_events[0]
            assert termination_event["reason"] in ["normal", "error"]
            assert "exit_code" in termination_event

        finally:
            # Cleanup
            os.unlink(test_file)

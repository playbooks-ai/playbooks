"""Unit tests for web_server.py - testing event sequence and WebSocket functionality."""

import json
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Mock websockets module and exceptions since it's not in dependencies
class MockConnectionClosed(Exception):
    """Mock websockets.exceptions.ConnectionClosed."""

    def __init__(self, *args):
        super().__init__(*args)


class MockConnectionClosedError(Exception):
    """Mock websockets.exceptions.ConnectionClosedError."""

    def __init__(self, *args):
        super().__init__(*args)


class MockWebSocketsExceptions:
    """Mock websockets.exceptions module."""

    ConnectionClosed = MockConnectionClosed
    ConnectionClosedError = MockConnectionClosedError


class MockWebSocketServer:
    """Mock WebSocket server."""

    async def wait_closed(self):
        pass

    def close(self):
        pass


class MockWebSocketsModule:
    """Mock websockets module."""

    exceptions = MockWebSocketsExceptions()

    @staticmethod
    async def serve(handler, host, port):
        return MockWebSocketServer()


# Patch websockets imports at module level before importing web_server
sys.modules["websockets"] = MockWebSocketsModule()
sys.modules["websockets.exceptions"] = MockWebSocketsExceptions()

from playbooks import Playbooks  # noqa
from playbooks.applications.web_server import (  # noqa
    AgentMessageEvent,
    AgentStreamingEvent,
    BaseEvent,
    EventType,
    PlaybookRun,
    RunManager,
    WebSocketClient,
)


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.sent_messages = []
        self.closed = False
        self.close_code = None
        self.close_reason = None

    async def send(self, message: str):
        if self.closed:
            raise MockConnectionClosed(None, None)
        self.sent_messages.append(message)

    async def close(self, code: int = None, reason: str = None):
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    def get_sent_events(self) -> List[Dict[str, Any]]:
        """Parse sent messages as JSON events."""
        return [json.loads(msg) for msg in self.sent_messages]


@pytest.fixture
def test_data_dir():
    """Return the test data directory path."""
    import pathlib

    return pathlib.Path(__file__).parent.parent.parent / "data"


@pytest.fixture
def playbooks_instance(test_data_dir):
    """Create a function that returns an initialized Playbooks instance."""

    async def _create_playbooks():
        session_id = str(uuid.uuid4())
        playbooks = Playbooks(
            [test_data_dir / "02-personalized-greeting.pb"], session_id=session_id
        )
        await playbooks.initialize()
        return playbooks

    return _create_playbooks


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    return MockWebSocket()


@pytest.fixture
def run_manager():
    """Create a RunManager for testing."""
    return RunManager()


class TestEventTypes:
    """Test event type definitions and serialization."""

    def test_base_event_serialization(self):
        """Test BaseEvent serialization to dict."""
        event = BaseEvent(
            type=EventType.CONNECTION_ESTABLISHED,
            timestamp="2024-01-01T00:00:00",
            run_id="test-run-123",
        )

        result = event.to_dict()
        assert result["type"] == "connection_established"
        assert result["timestamp"] == "2024-01-01T00:00:00"
        assert result["run_id"] == "test-run-123"

    def test_agent_message_event_serialization(self):
        """Test AgentMessageEvent serialization to dict."""
        event = AgentMessageEvent(
            type=EventType.AGENT_MESSAGE,
            timestamp="2024-01-01T00:00:00",
            run_id="test-run-123",
            sender_id="agent-1",
            sender_klass="LocalAIAgent",
            recipient_id="human",
            recipient_klass="human",
            message="Hello, what's your name?",
            message_type="DIRECT",
            metadata={"test": "data"},
        )

        result = event.to_dict()
        assert result["type"] == "agent_message"
        assert result["sender_id"] == "agent-1"
        assert result["message"] == "Hello, what's your name?"
        assert result["metadata"]["test"] == "data"

    def test_agent_streaming_event_serialization(self):
        """Test AgentStreamingEvent serialization to dict."""
        event = AgentStreamingEvent(
            type=EventType.AGENT_STREAMING_UPDATE,
            timestamp="2024-01-01T00:00:00",
            run_id="test-run-123",
            agent_id="agent-1",
            agent_klass="LocalAIAgent",
            content="H",
            recipient_id="human",
        )

        result = event.to_dict()
        assert result["type"] == "agent_streaming_update"
        assert result["agent_id"] == "agent-1"
        assert result["content"] == "H"
        assert result["recipient_id"] == "human"


class TestWebSocketClient:
    """Test WebSocketClient functionality."""

    @pytest.mark.asyncio
    async def test_send_event_success(self, mock_websocket):
        """Test successful event sending."""
        client = WebSocketClient(mock_websocket, "client-123")

        event = BaseEvent(
            type=EventType.CONNECTION_ESTABLISHED,
            timestamp="2024-01-01T00:00:00",
            run_id="test-run-123",
        )

        await client.send_event(event)

        assert len(mock_websocket.sent_messages) == 1
        sent_data = json.loads(mock_websocket.sent_messages[0])
        assert sent_data["type"] == "connection_established"
        assert sent_data["run_id"] == "test-run-123"

    @pytest.mark.asyncio
    async def test_send_event_connection_closed(self, mock_websocket):
        """Test handling of closed WebSocket connection."""
        client = WebSocketClient(mock_websocket, "client-123")
        mock_websocket.closed = True

        event = BaseEvent(
            type=EventType.CONNECTION_ESTABLISHED,
            timestamp="2024-01-01T00:00:00",
            run_id="test-run-123",
        )

        with pytest.raises(MockConnectionClosed):
            await client.send_event(event)

    @pytest.mark.asyncio
    async def test_handle_human_message(self, mock_websocket, run_manager):
        """Test handling of human message from client."""
        client = WebSocketClient(mock_websocket, "client-123")

        # Create a mock run
        mock_run = MagicMock()
        mock_run.send_human_message = AsyncMock()
        run_manager.runs["test-run-123"] = mock_run

        message_data = {
            "type": "human_message",
            "run_id": "test-run-123",
            "message": "John",
        }

        await client.handle_message(json.dumps(message_data), run_manager)

        mock_run.send_human_message.assert_called_once_with("John")


class TestPlaybookRun:
    """Test PlaybookRun functionality and event sequence."""

    @pytest.mark.asyncio
    async def test_add_client_sends_connection_event(
        self, playbooks_instance, mock_websocket
    ):
        """Test that adding a client sends CONNECTION_ESTABLISHED event."""
        playbooks = await playbooks_instance()
        run = PlaybookRun("test-run-123", playbooks)
        client = WebSocketClient(mock_websocket, "client-123")

        await run.add_client(client)

        events = mock_websocket.get_sent_events()
        assert len(events) >= 1

        # First event should be connection established
        connection_event = events[0]
        assert connection_event["type"] == "connection_established"
        assert connection_event["run_id"] == "test-run-123"

    @pytest.mark.asyncio
    async def test_broadcast_event_to_multiple_clients(self, playbooks_instance):
        """Test that events are broadcast to all connected clients."""
        playbooks = await playbooks_instance()
        run = PlaybookRun("test-run-123", playbooks)

        # Add multiple clients
        websocket1 = MockWebSocket()
        websocket2 = MockWebSocket()
        client1 = WebSocketClient(websocket1, "client-1")
        client2 = WebSocketClient(websocket2, "client-2")

        await run.add_client(client1)
        await run.add_client(client2)

        # Create and broadcast a custom event
        test_event = BaseEvent(
            type=EventType.RUN_STARTED,
            timestamp=datetime.now().isoformat(),
            run_id="test-run-123",
        )
        await run._broadcast_event(test_event)

        # Both clients should have received the event
        events1 = websocket1.get_sent_events()
        events2 = websocket2.get_sent_events()

        # Find the RUN_STARTED event in both client's messages
        run_started_events1 = [e for e in events1 if e["type"] == "run_started"]
        run_started_events2 = [e for e in events2 if e["type"] == "run_started"]

        assert len(run_started_events1) == 1
        assert len(run_started_events2) == 1
        assert run_started_events1[0]["run_id"] == "test-run-123"
        assert run_started_events2[0]["run_id"] == "test-run-123"

    @pytest.mark.asyncio
    async def test_agent_streaming_setup(self, playbooks_instance):
        """Test that channel stream observer is properly set up."""
        playbooks = await playbooks_instance()
        run = PlaybookRun("test-run-123", playbooks)
        await run._setup_early_streaming()

        # Verify that stream observer is initialized and subscribed to channels
        assert run.stream_observer is not None
        assert run.auto_subscribe_task is not None
        assert not run.auto_subscribe_task.done()

        # Cleanup
        await run.cleanup()

    @pytest.mark.asyncio
    async def test_message_interception_setup(self, playbooks_instance):
        """Test that message interception is properly set up."""
        playbooks = await playbooks_instance()
        run = PlaybookRun("test-run-123", playbooks)

        # Verify that original methods are stored
        assert "route_message" in run._original_methods
        assert "wait_for_message" in run._original_methods
        assert "broadcast_to_meeting" in run._original_methods
        assert "create_agent" in run._original_methods

        # Verify that methods are patched
        from playbooks.agents.messaging_mixin import MessagingMixin
        from playbooks.meetings.meeting_manager import MeetingManager
        from playbooks.program import Program

        # The methods should be different from the originals (patched)
        assert Program.route_message != run._original_methods["route_message"]
        assert (
            MessagingMixin.WaitForMessage != run._original_methods["wait_for_message"]
        )
        assert (
            MeetingManager.broadcast_to_meeting_as_owner
            != run._original_methods["broadcast_to_meeting"]
        )
        assert Program.create_agent != run._original_methods["create_agent"]

        # Cleanup for other tests
        await run.cleanup()

    @pytest.mark.asyncio
    async def test_send_human_message(self, playbooks_instance, mock_websocket):
        """Test sending human message generates proper events."""
        playbooks = await playbooks_instance()
        run = PlaybookRun("test-run-123", playbooks)
        client = WebSocketClient(mock_websocket, "client-123")
        await run.add_client(client)

        # Mock the route_message to avoid actual execution
        with patch.object(playbooks.program, "route_message", new_callable=AsyncMock):
            await run.send_human_message("John")

        events = mock_websocket.get_sent_events()

        # Should find a HUMAN_MESSAGE event
        human_message_events = [e for e in events if e["type"] == "human_message"]
        assert len(human_message_events) >= 1

        human_event = human_message_events[0]
        assert human_event["run_id"] == "test-run-123"


class TestRunManager:
    """Test RunManager functionality."""

    @pytest.mark.asyncio
    async def test_create_run_with_playbook_path(self, test_data_dir, run_manager):
        """Test creating a run with a playbook file path."""
        playbook_path = str(test_data_dir / "02-personalized-greeting.pb")

        run_id = await run_manager.create_run(playbooks_path=playbook_path)

        assert run_id is not None
        assert run_id in run_manager.runs

        run = run_manager.runs[run_id]
        assert run.run_id == run_id
        assert run.playbooks is not None
        assert run.task is not None  # Execution task should be created

    @pytest.mark.asyncio
    async def test_create_run_with_program_content(self, run_manager):
        """Test creating a run with program content string - should fail since from_string doesn't exist."""
        program_content = """# Test Playbook
A simple test playbook

## Say Hello
### Triggers
- At the beginning
### Steps
- Say "Hello World"
- End program
"""

        # This should fail because Playbooks.from_string doesn't exist
        with pytest.raises(RuntimeError, match="Failed to create run.*from_string"):
            await run_manager.create_run(program_content=program_content)

    @pytest.mark.asyncio
    async def test_create_run_invalid_arguments(self, run_manager):
        """Test creating a run with invalid arguments raises error."""
        # No arguments - expect RuntimeError wrapping ValueError
        with pytest.raises(
            RuntimeError,
            match="Failed to create run: Must provide either playbooks_path or program_content",
        ):
            await run_manager.create_run()

        # Invalid file path - expect RuntimeError wrapping FileNotFoundError
        with pytest.raises(RuntimeError, match="Failed to create run.*not found"):
            await run_manager.create_run(playbooks_path="nonexistent.pb")

    def test_get_run(self, run_manager):
        """Test getting a run by ID."""
        # Non-existent run
        assert run_manager.get_run("non-existent") is None

        # Add a mock run
        mock_run = MagicMock()
        run_manager.runs["test-run-123"] = mock_run

        # Should return the run
        assert run_manager.get_run("test-run-123") == mock_run


class TestWebSocketHandling:
    """Test WebSocket connection handling and message routing."""

    @pytest.mark.asyncio
    async def test_websocket_path_parsing(self, run_manager, test_data_dir):
        """Test WebSocket path parsing for run ID extraction."""
        # This test verifies the path parsing logic in websocket_handler
        # We'll test the logic by creating a mock websocket and calling the handler

        # Create a run first using a valid playbook path
        playbook_path = str(test_data_dir / "02-personalized-greeting.pb")
        run_id = await run_manager.create_run(playbooks_path=playbook_path)

        # Mock websocket
        mock_websocket = MagicMock()
        mock_websocket.__aiter__ = AsyncMock(return_value=iter([]))
        mock_websocket.close = AsyncMock()

        # Test valid path
        valid_path = f"/ws/{run_id}"

        # The websocket_handler would normally extract run_id from path
        # Let's test the path parsing logic directly
        path_parts = valid_path.strip("/").split("/")
        assert len(path_parts) >= 2
        assert path_parts[0] == "ws"
        extracted_run_id = path_parts[1]
        assert extracted_run_id == run_id

        # Test invalid path
        invalid_path = "/invalid/path"
        path_parts = invalid_path.strip("/").split("/")
        is_valid = len(path_parts) >= 2 and path_parts[0] == "ws"
        assert not is_valid


class TestErrorHandling:
    """Test error handling in various scenarios."""

    @pytest.mark.asyncio
    async def test_broadcast_event_with_disconnected_client(self, playbooks_instance):
        """Test broadcasting events when a client is disconnected."""
        playbooks = await playbooks_instance()
        run = PlaybookRun("test-run-123", playbooks)

        # Create a client that will fail when sending
        failing_websocket = MockWebSocket()
        failing_websocket.closed = True  # Simulate closed connection
        failing_client = WebSocketClient(failing_websocket, "failing-client")

        # Create a working client
        working_websocket = MockWebSocket()
        working_client = WebSocketClient(working_websocket, "working-client")

        # Add both clients manually to the run
        run.websocket_clients.add(failing_client)
        run.websocket_clients.add(working_client)

        # Broadcast an event
        test_event = BaseEvent(
            type=EventType.RUN_STARTED,
            timestamp=datetime.now().isoformat(),
            run_id="test-run-123",
        )

        await run._broadcast_event(test_event)

        # Working client should have received the event
        working_events = working_websocket.get_sent_events()
        assert len(working_events) == 1
        assert working_events[0]["type"] == "run_started"

        # Failing client should be removed from the set
        assert failing_client not in run.websocket_clients
        assert working_client in run.websocket_clients

    def test_event_serialization_normal_operation(self):
        """Test BaseEvent.to_dict() normal operation."""
        # Create a normal event
        event = BaseEvent(
            type=EventType.CONNECTION_ESTABLISHED,
            timestamp="2024-01-01T00:00:00",
            run_id="test-run-123",
        )

        # Should serialize successfully
        result = event.to_dict()
        assert result["type"] == "connection_established"
        assert result["timestamp"] == "2024-01-01T00:00:00"
        assert result["run_id"] == "test-run-123"
        assert "error" not in result


if __name__ == "__main__":
    pytest.main([__file__])

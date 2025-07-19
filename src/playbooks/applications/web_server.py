"""WebSocket-first Playbooks web server with comprehensive multi-agent visibility."""

import asyncio
import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Set

import websockets

from playbooks import Playbooks
from playbooks.agents.messaging_mixin import MessagingMixin
from playbooks.constants import EOM
from playbooks.exceptions import ExecutionFinished
from playbooks.meetings.meeting_manager import MeetingManager
from playbooks.message import MessageType
from playbooks.program import Program
from playbooks.utils.spec_utils import SpecUtils


class EventType(Enum):
    # Connection events
    CONNECTION_ESTABLISHED = "connection_established"
    RUN_STARTED = "run_started"
    RUN_TERMINATED = "run_terminated"

    # Agent events
    AGENT_MESSAGE = "agent_message"
    AGENT_STREAMING_START = "agent_streaming_start"
    AGENT_STREAMING_UPDATE = "agent_streaming_update"
    AGENT_STREAMING_COMPLETE = "agent_streaming_complete"

    # Meeting events
    MEETING_CREATED = "meeting_created"
    MEETING_BROADCAST = "meeting_broadcast"
    MEETING_PARTICIPANT_JOINED = "meeting_participant_joined"
    MEETING_PARTICIPANT_LEFT = "meeting_participant_left"

    # Human interaction
    HUMAN_MESSAGE = "human_message"
    HUMAN_INPUT_REQUESTED = "human_input_requested"

    # System events
    ERROR = "error"
    DEBUG = "debug"


@dataclass
class BaseEvent:
    type: EventType
    timestamp: str
    run_id: str

    def to_dict(self):
        try:
            data = asdict(self)
            data["type"] = self.type.value
            return data
        except Exception as e:
            print(f"Error serializing event: {e}")
            # Return a minimal event on error
            return {
                "type": self.type.value,
                "timestamp": self.timestamp,
                "run_id": self.run_id,
                "error": f"Serialization error: {str(e)}",
            }


@dataclass
class AgentMessageEvent(BaseEvent):
    sender_id: str
    sender_klass: str
    recipient_id: str
    recipient_klass: str
    message: str
    message_type: str
    metadata: Optional[Dict] = None


@dataclass
class MeetingBroadcastEvent(BaseEvent):
    meeting_id: str
    sender_id: str
    sender_klass: str
    message: str
    participants: List[str]


@dataclass
class AgentStreamingEvent(BaseEvent):
    agent_id: str
    agent_klass: str
    content: str
    recipient_id: Optional[str] = None
    total_content: Optional[str] = None


class PlaybookRun:
    """Enhanced run management with comprehensive event tracking."""

    def __init__(self, run_id: str, playbooks: Playbooks):
        self.run_id = run_id
        self.playbooks = playbooks
        self.websocket_clients: Set["WebSocketClient"] = set()
        self.event_history: List[BaseEvent] = []
        self.terminated = False
        self.task: Optional[asyncio.Task] = None

        # Store original methods for restoration
        self._original_methods = {}

        # Setup message interception
        self._setup_message_interception()

    def _setup_message_interception(self):
        """Setup comprehensive message interception."""

        # Store original methods
        self._original_methods["route_message"] = Program.route_message
        self._original_methods["wait_for_message"] = MessagingMixin.WaitForMessage
        self._original_methods[
            "broadcast_to_meeting"
        ] = MeetingManager.broadcast_to_meeting_as_owner

        # Create bound methods for this specific run
        async def patched_route_message(
            program_self,
            sender_id,
            sender_klass,
            receiver_spec,
            message,
            message_type=MessageType.DIRECT,
            meeting_id=None,
        ):
            await self._intercept_route_message(
                sender_id,
                sender_klass,
                receiver_spec,
                message,
                message_type,
                meeting_id,
            )
            return await self._original_methods["route_message"](
                program_self,
                sender_id,
                sender_klass,
                receiver_spec,
                message,
                message_type,
                meeting_id,
            )

        async def patched_wait_for_message(agent_self, source_agent_id: str):
            await self._intercept_wait_for_message(source_agent_id)
            return await self._original_methods["wait_for_message"](
                agent_self, source_agent_id
            )

        async def patched_broadcast_to_meeting(
            manager_self, meeting_id, message, from_agent_id=None, from_agent_klass=None
        ):
            await self._intercept_meeting_broadcast(
                meeting_id, message, from_agent_id, from_agent_klass
            )
            return await self._original_methods["broadcast_to_meeting"](
                manager_self, meeting_id, message, from_agent_id, from_agent_klass
            )

        # Patch methods
        Program.route_message = patched_route_message
        MessagingMixin.WaitForMessage = patched_wait_for_message
        MeetingManager.broadcast_to_meeting_as_owner = patched_broadcast_to_meeting

        # Setup streaming for all AI agents
        for agent in self.playbooks.program.agents:
            if hasattr(agent, "klass") and agent.klass != "human":
                self._setup_agent_streaming(agent)

    def _setup_agent_streaming(self, agent):
        """Setup streaming capabilities for an agent."""

        async def start_streaming_say(recipient=None):
            event = AgentStreamingEvent(
                type=EventType.AGENT_STREAMING_START,
                timestamp=datetime.now().isoformat(),
                run_id=self.run_id,
                agent_id=agent.id,
                agent_klass=agent.klass,
                content="",
                recipient_id=recipient,
            )
            await self._broadcast_event(event)

        async def stream_say_update(content: str):
            event = AgentStreamingEvent(
                type=EventType.AGENT_STREAMING_UPDATE,
                timestamp=datetime.now().isoformat(),
                run_id=self.run_id,
                agent_id=agent.id,
                agent_klass=agent.klass,
                content=content,
            )
            await self._broadcast_event(event)

        async def complete_streaming_say():
            event = AgentStreamingEvent(
                type=EventType.AGENT_STREAMING_COMPLETE,
                timestamp=datetime.now().isoformat(),
                run_id=self.run_id,
                agent_id=agent.id,
                agent_klass=agent.klass,
                content="",
            )
            await self._broadcast_event(event)

        agent.start_streaming_say = start_streaming_say
        agent.stream_say_update = stream_say_update
        agent.complete_streaming_say = complete_streaming_say

    async def _intercept_route_message(
        self,
        sender_id,
        sender_klass,
        receiver_spec,
        message,
        message_type=MessageType.DIRECT,
        meeting_id=None,
    ):
        """Intercept and broadcast route_message calls."""

        # Extract recipient info
        recipient_id = SpecUtils.extract_agent_id(receiver_spec)
        recipient = self.playbooks.program.agents_by_id.get(recipient_id)
        recipient_klass = recipient.klass if recipient else "Unknown"

        # Skip EOM messages but allow agent-to-human messages
        if message != EOM and not (sender_id == "human" and recipient_id != "human"):
            event = AgentMessageEvent(
                type=EventType.AGENT_MESSAGE,
                timestamp=datetime.now().isoformat(),
                run_id=self.run_id,
                sender_id=sender_id,
                sender_klass=sender_klass,
                recipient_id=recipient_id,
                recipient_klass=recipient_klass,
                message=message,
                message_type=message_type.name,
                metadata={"receiver_spec": receiver_spec, "meeting_id": meeting_id},
            )
            await self._broadcast_event(event)

    async def _intercept_wait_for_message(self, source_agent_id: str):
        """Intercept and broadcast wait_for_message calls."""

        if source_agent_id == "human":
            # Send human input request event
            event = BaseEvent(
                type=EventType.HUMAN_INPUT_REQUESTED,
                timestamp=datetime.now().isoformat(),
                run_id=self.run_id,
            )
            await self._broadcast_event(event)

    async def _intercept_meeting_broadcast(
        self, meeting_id, message, from_agent_id=None, from_agent_klass=None
    ):
        """Intercept and broadcast meeting_broadcast calls."""

        # Get meeting participants (simplified - would need actual meeting manager integration)
        participants = []

        event = MeetingBroadcastEvent(
            type=EventType.MEETING_BROADCAST,
            timestamp=datetime.now().isoformat(),
            run_id=self.run_id,
            meeting_id=meeting_id,
            sender_id=from_agent_id or "system",
            sender_klass=from_agent_klass or "system",
            message=message,
            participants=participants,
        )
        await self._broadcast_event(event)

    async def _broadcast_event(self, event: BaseEvent):
        """Broadcast event to all connected clients."""
        self.event_history.append(event)

        # Send to all WebSocket clients
        disconnected_clients = set()
        for client in self.websocket_clients:
            try:
                await client.send_event(event)
            except (
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.ConnectionClosedError,
            ):
                disconnected_clients.add(client)

        # Remove disconnected clients
        self.websocket_clients -= disconnected_clients

    async def add_client(self, client: "WebSocketClient"):
        """Add a WebSocket client to this run."""
        try:
            self.websocket_clients.add(client)
            print(
                f"Added client to run {self.run_id}, total clients: {len(self.websocket_clients)}"
            )

            # Send connection established event
            event = BaseEvent(
                type=EventType.CONNECTION_ESTABLISHED,
                timestamp=datetime.now().isoformat(),
                run_id=self.run_id,
            )
            print(f"Sending connection established event: {event.to_dict()}")
            await client.send_event(event)

            # Send event history
            print(f"Sending {len(self.event_history)} historical events")
            for event in self.event_history:
                await client.send_event(event)

            print(f"Client successfully added and initialized for run {self.run_id}")
        except Exception as e:
            print(f"Error adding client to run {self.run_id}: {e}")
            raise

    async def send_human_message(self, message: str):
        """Send a message from human to the main agent."""
        main_agent = self.playbooks.program.agents[0]  # Assume first agent is main

        # Broadcast human message event
        event = BaseEvent(
            type=EventType.HUMAN_MESSAGE,
            timestamp=datetime.now().isoformat(),
            run_id=self.run_id,
        )
        await self._broadcast_event(event)

        # Route the message
        await self.playbooks.program.route_message(
            sender_id="human",
            sender_klass="human",
            receiver_spec=f"agent {main_agent.id}",
            message=message,
        )

    def cleanup(self):
        """Cleanup resources and restore original methods."""
        Program.route_message = self._original_methods["route_message"]
        MessagingMixin.WaitForMessage = self._original_methods["wait_for_message"]
        MeetingManager.broadcast_to_meeting_as_owner = self._original_methods[
            "broadcast_to_meeting"
        ]


class WebSocketClient:
    """Represents a connected WebSocket client."""

    def __init__(self, websocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.subscriptions = {
            EventType.AGENT_MESSAGE: True,
            EventType.MEETING_BROADCAST: True,
            EventType.AGENT_STREAMING_START: True,
            EventType.AGENT_STREAMING_UPDATE: True,
            EventType.AGENT_STREAMING_COMPLETE: True,
            EventType.HUMAN_INPUT_REQUESTED: True,
            EventType.HUMAN_MESSAGE: True,
        }

    async def send_event(self, event: BaseEvent):
        """Send event to client if subscribed."""
        if self.subscriptions.get(event.type, False):
            try:
                event_data = event.to_dict()
                print(f"Sending event to client {self.client_id}: {event_data}")
                await self.websocket.send(json.dumps(event_data))
            except (
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.ConnectionClosedError,
            ):
                print(f"Client {self.client_id} connection closed during send")
                raise  # Re-raise to trigger cleanup
            except Exception as e:
                print(f"Error sending event to client {self.client_id}: {e}")
                raise

    async def handle_message(self, message: str, run_manager: "RunManager"):
        """Handle incoming message from client."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "subscribe":
                # Update subscriptions
                for event_type_str, enabled in data.get("events", {}).items():
                    try:
                        event_type = EventType(event_type_str)
                        self.subscriptions[event_type] = enabled
                    except ValueError:
                        pass  # Invalid event type

            elif msg_type == "human_message":
                # Send human message to run
                run_id = data.get("run_id")
                message = data.get("message")
                if run_id and message:
                    run = run_manager.get_run(run_id)
                    if run:
                        await run.send_human_message(message)

        except json.JSONDecodeError:
            pass  # Invalid JSON


class RunManager:
    """Manages all playbook runs."""

    def __init__(self):
        self.runs: Dict[str, PlaybookRun] = {}
        self.clients: Dict[str, WebSocketClient] = {}

    async def create_run(
        self, playbook_path: str = None, program_content: str = None
    ) -> str:
        """Create a new playbook run."""
        run_id = str(uuid.uuid4())

        try:
            if playbook_path:
                playbooks = Playbooks([playbook_path], session_id=run_id)
            elif program_content:
                playbooks = Playbooks.from_string(program_content, session_id=run_id)
            else:
                raise ValueError("Must provide either playbook_path or program_content")

            await playbooks.initialize()

            run = PlaybookRun(run_id, playbooks)
            self.runs[run_id] = run

            # Start the playbook execution
            run.task = asyncio.create_task(self._run_playbook(run))

            return run_id

        except Exception as e:
            raise RuntimeError(f"Failed to create run: {str(e)}")

    async def _run_playbook(self, run: PlaybookRun):
        """Execute a playbook run."""
        try:
            await run.playbooks.program.run_till_exit()
        except ExecutionFinished:
            pass  # Normal termination
        except Exception:
            # Send error event
            error_event = BaseEvent(
                type=EventType.ERROR,
                timestamp=datetime.now().isoformat(),
                run_id=run.run_id,
            )
            await run._broadcast_event(error_event)
        finally:
            run.terminated = True
            # Send termination event
            term_event = BaseEvent(
                type=EventType.RUN_TERMINATED,
                timestamp=datetime.now().isoformat(),
                run_id=run.run_id,
            )
            await run._broadcast_event(term_event)
            # Cleanup
            run.cleanup()

    async def websocket_handler(self, websocket, path):
        """Handle new WebSocket connection."""
        client_id = str(uuid.uuid4())
        client = WebSocketClient(websocket, client_id)
        self.clients[client_id] = client
        run_id = None

        try:
            print(f"WebSocket connection attempt with path: {path}")

            # Extract run_id from path: /ws/{run_id}
            path_parts = path.strip("/").split("/")
            if len(path_parts) >= 2 and path_parts[0] == "ws":
                run_id = path_parts[1]
                print(f"Extracted run_id: {run_id}")
            else:
                print(f"Invalid path format: {path}")
                await websocket.close(
                    code=1008, reason="Invalid path format. Use /ws/{run_id}"
                )
                return

            run = self.runs.get(run_id)
            if not run:
                print(
                    f"Run not found: {run_id}. Available runs: {list(self.runs.keys())}"
                )
                await websocket.close(code=1008, reason="Run not found")
                return

            print(f"Adding client to run {run_id}")
            await run.add_client(client)
            print("Client added successfully, starting message loop")

            # Handle incoming messages
            async for message in websocket:
                print(f"Received message from client {client_id}: {message}")
                await client.handle_message(message, self)

        except (
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.ConnectionClosedError,
        ):
            print(f"WebSocket connection closed for client {client_id}")
        except Exception as e:
            print(f"WebSocket error for client {client_id}: {e}")
            import traceback

            traceback.print_exc()
        finally:
            # Cleanup
            print(f"Cleaning up client {client_id}")
            if client_id in self.clients:
                del self.clients[client_id]
            if run_id and run_id in self.runs:
                self.runs[run_id].websocket_clients.discard(client)

    def get_run(self, run_id: str) -> Optional[PlaybookRun]:
        """Get a run by ID."""
        return self.runs.get(run_id)


class HTTPHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for run creation."""

    def _send_response(
        self, code: int, body: str = "", content_type: str = "application/json"
    ):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if body:
            self.wfile.write(body.encode())

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self._send_response(200)

    def do_POST(self):
        if self.path == "/runs/new":
            self._handle_new_run()
        else:
            self._send_response(404, json.dumps({"error": "Not Found"}))

    def _handle_new_run(self):
        """Handle new run creation."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length)) if length else {}

            path = data.get("path")
            program = data.get("program")

            if (path is None and program is None) or (path and program):
                self._send_response(
                    400, json.dumps({"error": "Specify either 'path' or 'program'"})
                )
                return

            # Create run using the shared run manager
            run_manager = self.server.run_manager

            if path:
                run_id = asyncio.run_coroutine_threadsafe(
                    run_manager.create_run(playbook_path=path), self.server.loop
                ).result()
            else:
                run_id = asyncio.run_coroutine_threadsafe(
                    run_manager.create_run(program_content=program), self.server.loop
                ).result()

            response = {"run_id": run_id}
            self._send_response(200, json.dumps(response))

        except Exception as e:
            self._send_response(500, json.dumps({"error": str(e)}))

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        return


class HTTPServer(ThreadingHTTPServer):
    """HTTP server with shared run manager."""

    def __init__(self, addr, handler, run_manager, loop):
        super().__init__(addr, handler)
        self.run_manager = run_manager
        self.loop = loop


class PlaybooksWebServer:
    """WebSocket-first Playbooks web server."""

    def __init__(self, host="localhost", http_port=8000, ws_port=8001):
        self.host = host
        self.http_port = http_port
        self.ws_port = ws_port
        self.run_manager = RunManager()
        self.loop = None
        self.http_server = None
        self.ws_server = None

    async def start(self):
        """Start both HTTP and WebSocket servers."""
        self.loop = asyncio.get_event_loop()

        # Create a wrapper function that matches websockets signature
        async def ws_handler(websocket):
            # In websockets 15.x, path is accessed via websocket.request.path
            path = websocket.request.path if hasattr(websocket, "request") else "/"
            await self.run_manager.websocket_handler(websocket, path)

        # Start WebSocket server
        self.ws_server = await websockets.serve(ws_handler, self.host, self.ws_port)

        # Start HTTP server in background thread
        http_server = HTTPServer(
            (self.host, self.http_port), HTTPHandler, self.run_manager, self.loop
        )
        self.http_server = http_server

        def run_http_server():
            http_server.serve_forever()

        http_thread = threading.Thread(target=run_http_server, daemon=True)
        http_thread.start()

        print("🚀 Playbooks Web Server started:")
        print(f"   HTTP API: http://{self.host}:{self.http_port}")
        print(f"   WebSocket: ws://{self.host}:{self.ws_port}")
        print(f"   Example: POST http://{self.host}:{self.http_port}/runs/new")
        print("Press Ctrl+C to stop")

        # Keep WebSocket server running
        await self.ws_server.wait_closed()

    def stop(self):
        """Stop both servers."""
        if self.http_server:
            self.http_server.shutdown()
        if self.ws_server:
            self.ws_server.close()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Playbooks WebSocket-first web server")
    parser.add_argument(
        "--host", default="localhost", help="Host address (default: localhost)"
    )
    parser.add_argument(
        "--http-port", type=int, default=8000, help="HTTP port (default: 8000)"
    )
    parser.add_argument(
        "--ws-port", type=int, default=8001, help="WebSocket port (default: 8001)"
    )

    args = parser.parse_args()

    server = PlaybooksWebServer(args.host, args.http_port, args.ws_port)

    try:
        await server.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        server.stop()


if __name__ == "__main__":
    asyncio.run(main())

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
from urllib.parse import urlparse

import websockets

from playbooks import Playbooks
from playbooks.agents.ai_agent import AIAgent
from playbooks.applications.streaming_observer import (
    ChannelStreamObserver as BaseChannelStreamObserver,
)
from playbooks.channels.stream_events import (
    StreamChunkEvent,
    StreamCompleteEvent,
    StreamStartEvent,
)
from playbooks.core.constants import EOM
from playbooks.core.events import (
    AgentCreatedEvent,
    MessageRoutedEvent,
    WaitForMessageEvent,
)
from playbooks.core.exceptions import ExecutionFinished
from playbooks.core.identifiers import AgentID
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.state.streaming_log import StreamingSessionLog


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
    AGENT_ERRORS = "agent_errors"

    # Session log events
    SESSION_LOG_ENTRY = "session_log_entry"

    # Agent lifecycle events
    AGENT_CREATED = "agent_created"


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
            debug("Error serializing event", error=str(e))
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


@dataclass
class SessionLogEvent(BaseEvent):
    agent_id: str
    agent_klass: str
    level: str
    content: str
    item_type: str
    metadata: Optional[Dict] = None
    log_full: Optional[str] = None
    log_compact: Optional[str] = None
    log_minimal: Optional[str] = None


class ChannelStreamObserver(BaseChannelStreamObserver):
    """WebSocket-based streaming observer - broadcasts to connected clients."""

    def __init__(self, playbook_run: "PlaybookRun", target_human_id: str = None):
        super().__init__(
            playbook_run.playbooks.program,
            streaming_enabled=True,
            target_human_id=target_human_id,
        )
        self.playbook_run = playbook_run

    async def _display_start(self, event: StreamStartEvent, agent_name: str) -> None:
        """Broadcast stream start to WebSocket clients."""
        web_event = AgentStreamingEvent(
            type=EventType.AGENT_STREAMING_START,
            timestamp=datetime.now().isoformat(),
            run_id=self.playbook_run.run_id,
            agent_id=event.sender_id,
            agent_klass=agent_name,
            content="",
        )
        await self.playbook_run._broadcast_event(web_event)

    async def _display_chunk(self, event: StreamChunkEvent) -> None:
        """Broadcast stream chunk to WebSocket clients."""
        # Need to get agent info from stream_id
        sender = (
            self.program.agents_by_id.get(event.sender_id)
            if hasattr(event, "sender_id")
            else None
        )
        agent_klass = sender.klass if sender else "Agent"

        # Get sender from active stream tracking
        for stream_id, channel in self.program.channels.items():
            if event.stream_id in getattr(channel, "_active_streams", {}):
                stream_info = channel._active_streams[event.stream_id]
                sender_id = stream_info.get("sender_id")
                sender = self.program.agents_by_id.get(sender_id)
                agent_klass = sender.klass if sender else agent_klass
                agent_id = sender_id
                break
        else:
            agent_id = "unknown"

        web_event = AgentStreamingEvent(
            type=EventType.AGENT_STREAMING_UPDATE,
            timestamp=datetime.now().isoformat(),
            run_id=self.playbook_run.run_id,
            agent_id=agent_id,
            agent_klass=agent_klass,
            content=event.chunk,
        )
        await self.playbook_run._broadcast_event(web_event)

    async def _display_complete(self, event: StreamCompleteEvent) -> None:
        """Broadcast stream completion to WebSocket clients."""
        # Get sender info from final message
        sender_id = event.final_message.sender_id.id
        sender = self.program.agents_by_id.get(sender_id)
        agent_klass = sender.klass if sender else "Agent"

        web_event = AgentStreamingEvent(
            type=EventType.AGENT_STREAMING_COMPLETE,
            timestamp=datetime.now().isoformat(),
            run_id=self.playbook_run.run_id,
            agent_id=sender_id,
            agent_klass=agent_klass,
            content=event.final_message.content or "",
        )
        await self.playbook_run._broadcast_event(web_event)

    async def _display_buffered(self, event: StreamCompleteEvent) -> None:
        """Display buffered complete message (same as streaming for WebSocket)."""
        await self._display_complete(event)


class PlaybookRun:
    """Enhanced run management with comprehensive event tracking."""

    def __init__(self, run_id: str, playbooks: Playbooks):
        self.run_id = run_id
        self.playbooks = playbooks
        self.websocket_clients: Set["WebSocketClient"] = set()
        self.event_history: List[BaseEvent] = []
        self.terminated = False
        self.task: Optional[asyncio.Task] = None
        self.execution_started = False
        self.client_connected_event = asyncio.Event()

        # Initialize channel stream observer
        self.stream_observer = ChannelStreamObserver(self)
        # Subscribe to core events for message/wait/agent tracking (no monkey-patching)
        self._setup_event_subscriptions()

    def _setup_event_subscriptions(self) -> None:
        """Subscribe to core EventBus for observability instead of monkey-patching."""

        program = self.playbooks.program

        def on_agent_created(event: AgentCreatedEvent) -> None:
            # Broadcast agent created event to clients
            asyncio.create_task(self._handle_agent_created(event))

        def on_message_routed(event: MessageRoutedEvent) -> None:
            asyncio.create_task(self._handle_message_routed(event))

        def on_wait(event: WaitForMessageEvent) -> None:
            asyncio.create_task(self._handle_wait_for_message(event))

        program.event_bus.subscribe(AgentCreatedEvent, on_agent_created)
        program.event_bus.subscribe(MessageRoutedEvent, on_message_routed)
        program.event_bus.subscribe(WaitForMessageEvent, on_wait)

        # Store for unsubscribe on shutdown
        self._event_subscriptions = [
            (AgentCreatedEvent, on_agent_created),
            (MessageRoutedEvent, on_message_routed),
            (WaitForMessageEvent, on_wait),
        ]

    async def _handle_agent_created(self, event: AgentCreatedEvent) -> None:
        web_event = AgentCreatedEvent(
            type=EventType.AGENT_CREATED,
            timestamp=datetime.now().isoformat(),
            run_id=self.run_id,
            agent_id=event.agent_id,
            agent_klass=event.agent_klass,
        )
        await self._broadcast_event(web_event)

    async def _handle_message_routed(self, event: MessageRoutedEvent) -> None:
        msg = event.message
        if not msg:
            return
        # Skip EOM messages but allow agent-to-human messages
        if msg.content != EOM and not (
            msg.sender_id.id == "human"
            and (msg.recipient_id and msg.recipient_id.id != "human")
        ):
            recipient_id = msg.recipient_id.id if msg.recipient_id else "broadcast"
            recipient_klass = msg.recipient_klass or "Unknown"
            web_event = AgentMessageEvent(
                type=EventType.AGENT_MESSAGE,
                timestamp=datetime.now().isoformat(),
                run_id=self.run_id,
                sender_id=msg.sender_id.id,
                sender_klass=msg.sender_klass,
                recipient_id=recipient_id,
                recipient_klass=recipient_klass,
                message=msg.content,
                message_type=msg.message_type.name,
                metadata={
                    "channel_id": event.channel_id,
                    "meeting_id": msg.meeting_id.id if msg.meeting_id else None,
                },
            )
            await self._broadcast_event(web_event)

    async def _handle_wait_for_message(self, event: WaitForMessageEvent) -> None:
        if event.wait_for_message_from in ("human", "user"):
            web_event = BaseEvent(
                type=EventType.HUMAN_INPUT_REQUESTED,
                timestamp=datetime.now().isoformat(),
                run_id=self.run_id,
            )
            await self._broadcast_event(web_event)

    def _setup_streaming_session_logs(self):
        """Replace agent session logs with streaming versions."""

        def create_session_log_callback(agent_id, agent_klass):
            """Create a callback for a specific agent's session log."""

            async def callback(event_data):
                debug(
                    "Session log callback",
                    agent=f"{agent_klass}({agent_id})",
                    item_type=event_data.get("item_type", "unknown"),
                )
                # Create SessionLogEvent
                event = SessionLogEvent(
                    type=EventType.SESSION_LOG_ENTRY,
                    timestamp=event_data["timestamp"],
                    run_id=self.run_id,
                    agent_id=agent_id,
                    agent_klass=agent_klass,
                    level=event_data["level"],
                    content=event_data["content"],
                    item_type=event_data["item_type"],
                    metadata=event_data.get("metadata"),
                    log_full=event_data.get("log_full"),
                )
                await self._broadcast_event(event)

            return callback

        # Replace session logs for all agents
        debug(
            "Setting up streaming session logs",
            agent_count=len(self.playbooks.program.agents),
        )
        for agent in self.playbooks.program.agents:
            if hasattr(agent, "session_log"):
                debug(
                    "Setting up streaming for agent",
                    agent_id=agent.id,
                    agent_klass=agent.klass,
                )
                # Create streaming callback for this agent
                callback = create_session_log_callback(agent.id, agent.klass)

                # Replace with streaming version, preserving existing data
                original_log = agent.session_log
                streaming_log = StreamingSessionLog(
                    original_log.klass, original_log.agent_id, callback
                )
                # Copy existing log entries
                streaming_log.log = original_log.log.copy()
                agent.session_log = streaming_log
                debug(
                    "Replaced session log for agent",
                    agent_id=agent.id,
                    existing_entries=len(streaming_log.log),
                )
            else:
                debug("Agent has no session_log or state", agent_id=agent.id)

    async def _setup_early_streaming(self):
        """Setup streaming before execution starts to catch all events."""
        debug("Setting up early streaming", run_id=self.run_id)

        # Setup session log streaming for all agents
        self._setup_streaming_session_logs()

        # Setup channel stream observer for agent messages
        # The observer automatically subscribes to ChannelCreatedEvent via EventBus
        await self.stream_observer.subscribe_to_all_channels()

    async def _setup_streaming_for_new_agent(self, agent):
        """Set up streaming for a newly created agent."""
        debug(
            "Setting up streaming for newly created agent",
            agent_id=agent.id,
            agent_klass=agent.klass,
        )

        # Set up session log streaming if the agent has one
        if hasattr(agent, "session_log"):
            debug("Setting up session log streaming for new agent", agent_id=agent.id)

            def create_session_log_callback(agent_id, agent_klass):
                """Create a callback for a specific agent's session log."""

                async def callback(event_data):
                    debug(
                        "Session log callback for newly created agent",
                        agent_klass=agent_klass,
                        agent_id=agent_id,
                        item_type=event_data.get("item_type", "unknown"),
                    )
                    # Create SessionLogEvent
                    event = SessionLogEvent(
                        type=EventType.SESSION_LOG_ENTRY,
                        timestamp=event_data["timestamp"],
                        run_id=self.run_id,
                        agent_id=agent_id,
                        agent_klass=agent_klass,
                        level=event_data["level"],
                        content=event_data["content"],
                        item_type=event_data["item_type"],
                        metadata=event_data.get("metadata"),
                        log_full=event_data.get("log_full"),
                    )
                    await self._broadcast_event(event)

                return callback

            # Create streaming callback for this agent
            callback = create_session_log_callback(agent.id, agent.klass)

            # Replace with streaming version, preserving existing data
            original_log = agent.session_log
            streaming_log = StreamingSessionLog(
                original_log.klass, original_log.agent_id, callback
            )
            # Copy existing log entries
            streaming_log.log = original_log.log.copy()
            agent.session_log = streaming_log
            debug(
                "Replaced session log for new agent",
                agent_id=agent.id,
                existing_entries=len(streaming_log.log),
            )

        # Broadcast agent created event
        agent_created_event = AgentCreatedEvent(
            type=EventType.AGENT_CREATED,
            timestamp=datetime.now().isoformat(),
            run_id=self.run_id,
            agent_id=agent.id,
            agent_klass=agent.klass,
        )
        await self._broadcast_event(agent_created_event)

    # NOTE: legacy interception methods removed; PlaybookRun now subscribes to core EventBus events.

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
            debug(
                "Added client to run",
                run_id=self.run_id,
                total_clients=len(self.websocket_clients),
            )

            # Signal that a client has connected
            self.client_connected_event.set()

            # Send connection established event
            event = BaseEvent(
                type=EventType.CONNECTION_ESTABLISHED,
                timestamp=datetime.now().isoformat(),
                run_id=self.run_id,
            )
            debug("Sending connection established event", event=event.to_dict())
            await client.send_event(event)

            # Send event history
            debug("Sending historical events", event_count=len(self.event_history))
            for event in self.event_history:
                await client.send_event(event)

            # Always send existing session logs
            await self._send_existing_session_logs(client)

            debug("Client successfully added and initialized", run_id=self.run_id)
        except Exception as e:
            debug("Error adding client to run", run_id=self.run_id, error=str(e))
            raise

    async def _send_existing_session_logs(self, client):
        """Send existing session log entries to a newly connected client."""
        debug("Sending existing session logs to client", client_id=client.client_id)

        for agent in self.playbooks.program.agents:
            if (
                isinstance(agent, AIAgent)
                and hasattr(agent, "state")
                and "session_log" in agent.state
            ):
                session_log = agent.session_log
                debug(
                    "Agent session log entries",
                    agent_id=agent.id,
                    entry_count=len(session_log.log),
                )

                for entry in session_log.log:
                    item = entry["item"]
                    level = entry["level"]

                    # Create event data similar to what StreamingSessionLog creates
                    event_data = {
                        "timestamp": datetime.now().isoformat(),
                        "agent_id": agent.id,
                        "agent_klass": agent.klass,
                        "level": level.name,
                        "content": str(item),
                    }

                    # Add metadata if it's an enhanced SessionLogItem
                    if hasattr(item, "to_metadata"):
                        event_data["metadata"] = item.to_metadata()
                        event_data["item_type"] = item.item_type
                    elif hasattr(item, "__class__"):
                        event_data["item_type"] = item.__class__.__name__.lower()
                    else:
                        event_data["item_type"] = "message"

                    # Add full log representation
                    if hasattr(item, "to_log_full"):
                        event_data["log_full"] = item.to_log_full()

                    # Create SessionLogEvent
                    event = SessionLogEvent(
                        type=EventType.SESSION_LOG_ENTRY,
                        timestamp=event_data["timestamp"],
                        run_id=self.run_id,
                        agent_id=agent.id,
                        agent_klass=agent.klass,
                        level=event_data["level"],
                        content=event_data["content"],
                        item_type=event_data["item_type"],
                        metadata=event_data.get("metadata"),
                        log_full=event_data.get("log_full"),
                    )

                    # Send to client
                    await client.send_event(event)

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
            receiver_spec=str(AgentID.parse(main_agent.id)),
            message=message,
        )

    async def cleanup(self):
        """Cleanup resources and unsubscribe from EventBus."""
        for event_type, handler in getattr(self, "_event_subscriptions", []):
            try:
                self.playbooks.program.event_bus.unsubscribe(event_type, handler)
            except Exception:
                pass


class WebSocketClient:
    """Represents a connected WebSocket client."""

    def __init__(self, websocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        # Always send all events - filtering now handled by CSS in the client
        self.subscriptions = {
            EventType.AGENT_MESSAGE: True,
            EventType.MEETING_BROADCAST: True,
            EventType.AGENT_STREAMING_START: True,
            EventType.AGENT_STREAMING_UPDATE: True,
            EventType.AGENT_STREAMING_COMPLETE: True,
            EventType.HUMAN_INPUT_REQUESTED: True,
            EventType.HUMAN_MESSAGE: True,
            EventType.SESSION_LOG_ENTRY: True,  # Always send, let client control display
        }

    async def send_event(self, event: BaseEvent):
        """Send event to client - always send all events."""
        try:
            event_data = event.to_dict()
            debug(
                "Sending event to client",
                client_id=self.client_id,
                event_data=event_data,
            )
            await self.websocket.send(json.dumps(event_data))
        except (
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.ConnectionClosedError,
        ):
            debug("Client connection closed during send", client_id=self.client_id)
            raise  # Re-raise to trigger cleanup
        except Exception as e:
            debug(
                "Error sending event to client", client_id=self.client_id, error=str(e)
            )
            raise

    async def handle_message(self, message: str, run_manager: "RunManager"):
        """Handle incoming message from client."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "human_message":
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
        self, playbooks_path: str = None, program_content: str = None
    ) -> str:
        """Create a new playbook run."""
        run_id = str(uuid.uuid4())
        debug("Creating run", run_id=run_id)
        debug("Playbooks path", playbooks_path=playbooks_path)

        try:
            if playbooks_path:
                if "," in playbooks_path:
                    playbooks_paths = playbooks_path.split(",")
                else:
                    playbooks_paths = [playbooks_path]

                debug("Playbooks paths", playbooks_paths=playbooks_paths)
                playbooks = Playbooks(playbooks_paths, session_id=run_id)
            elif program_content:
                playbooks = Playbooks.from_string(program_content, session_id=run_id)
            else:
                raise ValueError(
                    "Must provide either playbooks_path or program_content"
                )

            await playbooks.initialize()

            run = PlaybookRun(run_id, playbooks)
            self.runs[run_id] = run

            # Setup streaming BEFORE starting execution to catch all events
            await run._setup_early_streaming()

            # Start the playbook execution
            run.task = asyncio.create_task(self._run_playbook(run))

            return run_id

        except Exception as e:
            raise RuntimeError(f"Failed to create run: {str(e)}")

    async def _run_playbook(self, run: PlaybookRun):
        """Execute a playbook run."""
        try:
            # Wait for at least one WebSocket client to connect before starting execution
            debug("Waiting for WebSocket client to connect", run_id=run.run_id)
            await run.client_connected_event.wait()
            debug("Client connected, starting execution", run_id=run.run_id)

            # Mark execution as started
            run.execution_started = True

            # Send RUN_STARTED event
            start_event = BaseEvent(
                type=EventType.RUN_STARTED,
                timestamp=datetime.now().isoformat(),
                run_id=run.run_id,
            )
            await run._broadcast_event(start_event)

            await run.playbooks.program.run_till_exit()

            # Check for agent errors after successful completion
            if run.playbooks.has_agent_errors():
                agent_errors = run.playbooks.get_agent_errors()
                error_event = BaseEvent(
                    type=EventType.AGENT_ERRORS,
                    timestamp=datetime.now().isoformat(),
                    run_id=run.run_id,
                    data={
                        "error_count": len(agent_errors),
                        "errors": agent_errors,
                        "message": f"⚠️ {len(agent_errors)} agent error(s) detected during execution",
                    },
                )
                await run._broadcast_event(error_event)

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

            # Also check for agent errors that occurred before the exception
            if run.playbooks and run.playbooks.has_agent_errors():
                agent_errors = run.playbooks.get_agent_errors()
                agent_error_event = BaseEvent(
                    type=EventType.AGENT_ERRORS,
                    timestamp=datetime.now().isoformat(),
                    run_id=run.run_id,
                    data={
                        "error_count": len(agent_errors),
                        "errors": agent_errors,
                        "message": f"Additional agent errors detected: {len(agent_errors)}",
                    },
                )
                await run._broadcast_event(agent_error_event)
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
            await run.cleanup()

    async def websocket_handler(self, websocket, path):
        """Handle new WebSocket connection."""
        client_id = str(uuid.uuid4())
        client = WebSocketClient(websocket, client_id)
        self.clients[client_id] = client
        run_id = None

        try:
            debug("WebSocket connection attempt", path=path)

            # Extract run_id from path: /ws/{run_id}
            path_parts = path.strip("/").split("/")
            if len(path_parts) >= 2 and path_parts[0] == "ws":
                run_id = path_parts[1]
                debug("Extracted run_id", run_id=run_id)
            else:
                debug("Invalid path format", path=path)
                await websocket.close(
                    code=1008, reason="Invalid path format. Use /ws/{run_id}"
                )
                return

            run = self.runs.get(run_id)
            if not run:
                debug(
                    "Run not found",
                    run_id=run_id,
                    available_runs=list(self.runs.keys()),
                )
                await websocket.close(code=1008, reason="Run not found")
                return

            debug("Adding client to run", run_id=run_id)
            await run.add_client(client)
            debug("Client added successfully, starting message loop")

            # Handle incoming messages
            async for message in websocket:
                debug(
                    "Received message from client",
                    client_id=client_id,
                    raw_message=message,
                )
                await client.handle_message(message, self)

        except (
            websockets.exceptions.ConnectionClosed,
            websockets.exceptions.ConnectionClosedError,
        ):
            debug("WebSocket connection closed", client_id=client_id)
        except Exception as e:
            debug("WebSocket error for client", client_id=client_id, error=str(e))
            import traceback

            traceback.print_exc()
        finally:
            # Cleanup
            debug("Cleaning up client", client_id=client_id)
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

    def do_GET(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path.startswith("/runs/") and parsed_path.path.endswith(
            "/program"
        ):
            self._handle_get_program(parsed_path)
        else:
            self._send_response(404, json.dumps({"error": "Not Found"}))

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
                    run_manager.create_run(playbooks_path=path), self.server.loop
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

    def _handle_get_program(self, parsed_path):
        """Return the program content and paths for a given run."""
        parts = parsed_path.path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "runs" or parts[2] != "program":
            self._send_response(400, json.dumps({"error": "Invalid path"}))
            return

        run_id = parts[1]
        run = self.server.run_manager.get_run(run_id)
        if not run:
            self._send_response(404, json.dumps({"error": "Run not found"}))
            return

        playbooks = run.playbooks
        response = {
            "program_content": getattr(playbooks, "program_content", None),
            "program_paths": getattr(playbooks, "program_paths", []),
        }
        self._send_response(200, json.dumps(response))


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
        debug("Shutting down server")
        server.stop()


if __name__ == "__main__":
    asyncio.run(main())

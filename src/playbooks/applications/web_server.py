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
from playbooks.debug_logger import debug
from playbooks.agents.messaging_mixin import MessagingMixin
from playbooks.constants import EOM
from playbooks.exceptions import ExecutionFinished
from playbooks.meetings.meeting_manager import MeetingManager
from playbooks.message import MessageType
from playbooks.program import Program
from playbooks.streaming_session_log import StreamingSessionLog
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


@dataclass
class AgentCreatedEvent(BaseEvent):
    agent_id: str
    agent_klass: str


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

        # Store original methods for restoration
        self._original_methods = {}

        # Setup message interception (but not streaming logs yet)
        self._setup_message_interception()

    def _setup_message_interception(self):
        """Setup comprehensive message interception."""

        # Store original methods
        self._original_methods["route_message"] = Program.route_message
        self._original_methods["wait_for_message"] = MessagingMixin.WaitForMessage
        self._original_methods["broadcast_to_meeting"] = (
            MeetingManager.broadcast_to_meeting_as_owner
        )
        self._original_methods["create_agent"] = Program.create_agent

        # Note: Session log streaming is now setup in _setup_early_streaming

        # Create bound methods for this specific run
        # Capture self in local variable to ensure proper closure
        playbook_run = self

        async def patched_route_message(
            program_self,
            sender_id,
            sender_klass,
            receiver_spec,
            message,
            message_type=MessageType.DIRECT,
            meeting_id=None,
        ):
            # Check if playbook_run is properly captured and not corrupted
            try:
                # Validate that playbook_run has the expected attributes
                if (
                    hasattr(playbook_run, "playbooks")
                    and hasattr(playbook_run.playbooks, "program")
                    and hasattr(playbook_run, "_intercept_route_message")
                ):
                    await playbook_run._intercept_route_message(
                        sender_id,
                        sender_klass,
                        receiver_spec,
                        message,
                        message_type,
                        meeting_id,
                    )
                # If playbook_run is corrupted or doesn't have expected attributes,
                # skip interception and just call original method
            except AttributeError:
                # If there's an AttributeError, just skip the interception
                pass
            return await playbook_run._original_methods["route_message"](
                program_self,
                sender_id,
                sender_klass,
                receiver_spec,
                message,
                message_type,
                meeting_id,
            )

        async def patched_wait_for_message(agent_self, source_agent_id: str):
            await playbook_run._intercept_wait_for_message(source_agent_id)
            return await playbook_run._original_methods["wait_for_message"](
                agent_self, source_agent_id
            )

        async def patched_broadcast_to_meeting(
            manager_self, meeting_id, message, from_agent_id=None, from_agent_klass=None
        ):
            await playbook_run._intercept_meeting_broadcast(
                meeting_id, message, from_agent_id, from_agent_klass
            )
            return await playbook_run._original_methods["broadcast_to_meeting"](
                manager_self, meeting_id, message, from_agent_id, from_agent_klass
            )

        async def patched_create_agent(program_self, agent_klass, **kwargs):
            # Call original create_agent method
            agent = await playbook_run._original_methods["create_agent"](
                program_self, agent_klass, **kwargs
            )

            # Set up streaming for the newly created agent
            await playbook_run._setup_streaming_for_new_agent(agent)

            return agent

        # Patch methods
        Program.route_message = patched_route_message
        MessagingMixin.WaitForMessage = patched_wait_for_message
        MeetingManager.broadcast_to_meeting_as_owner = patched_broadcast_to_meeting
        Program.create_agent = patched_create_agent

        # Note: Agent streaming is now setup in _setup_early_streaming

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
                    log_compact=event_data.get("log_compact"),
                    log_minimal=event_data.get("log_minimal"),
                )
                await self._broadcast_event(event)

            return callback

        # Replace session logs for all agents
        debug(
            "Setting up streaming session logs",
            agent_count=len(self.playbooks.program.agents),
        )
        for agent in self.playbooks.program.agents:
            if hasattr(agent, "state") and hasattr(agent.state, "session_log"):
                debug(
                    "Setting up streaming for agent",
                    agent_id=agent.id,
                    agent_klass=agent.klass,
                )
                # Create streaming callback for this agent
                callback = create_session_log_callback(agent.id, agent.klass)

                # Replace with streaming version, preserving existing data
                original_log = agent.state.session_log
                streaming_log = StreamingSessionLog(
                    original_log.klass, original_log.agent_id, callback
                )
                # Copy existing log entries
                streaming_log.log = original_log.log.copy()
                agent.state.session_log = streaming_log
                debug(
                    "Replaced session log for agent",
                    agent_id=agent.id,
                    existing_entries=len(streaming_log.log),
                )
            else:
                debug("Agent has no session_log or state", agent_id=agent.id)

    def _setup_early_streaming(self):
        """Setup streaming before execution starts to catch all events."""
        debug("Setting up early streaming", run_id=self.run_id)

        # Setup session log streaming for all agents
        self._setup_streaming_session_logs()

        # Setup agent streaming for AI agents
        for agent in self.playbooks.program.agents:
            if hasattr(agent, "klass") and agent.klass != "human":
                self._setup_agent_streaming(agent)

    async def _setup_streaming_for_new_agent(self, agent):
        """Set up streaming for a newly created agent."""
        debug(
            "Setting up streaming for newly created agent",
            agent_id=agent.id,
            agent_klass=agent.klass,
        )

        # Set up session log streaming if the agent has one
        if hasattr(agent, "state") and hasattr(agent.state, "session_log"):
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
                        log_compact=event_data.get("log_compact"),
                        log_minimal=event_data.get("log_minimal"),
                    )
                    await self._broadcast_event(event)

                return callback

            # Create streaming callback for this agent
            callback = create_session_log_callback(agent.id, agent.klass)

            # Replace with streaming version, preserving existing data
            original_log = agent.state.session_log
            streaming_log = StreamingSessionLog(
                original_log.klass, original_log.agent_id, callback
            )
            # Copy existing log entries
            streaming_log.log = original_log.log.copy()
            agent.state.session_log = streaming_log
            debug(
                "Replaced session log for new agent",
                agent_id=agent.id,
                existing_entries=len(streaming_log.log),
            )

        # Set up agent message streaming if it's not a human agent
        if hasattr(agent, "klass") and agent.klass != "human":
            debug("Setting up agent message streaming for new agent", agent_id=agent.id)
            self._setup_agent_streaming(agent)

        # Broadcast agent created event
        agent_created_event = AgentCreatedEvent(
            type=EventType.AGENT_CREATED,
            timestamp=datetime.now().isoformat(),
            run_id=self.run_id,
            agent_id=agent.id,
            agent_klass=agent.klass,
        )
        await self._broadcast_event(agent_created_event)

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
            if hasattr(agent, "state") and hasattr(agent.state, "session_log"):
                session_log = agent.state.session_log
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

                    # Add different log representations
                    if hasattr(item, "to_log_full"):
                        event_data["log_full"] = item.to_log_full()
                    if hasattr(item, "to_log_compact"):
                        event_data["log_compact"] = item.to_log_compact()
                    if hasattr(item, "to_log_minimal"):
                        event_data["log_minimal"] = item.to_log_minimal()

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
                        log_compact=event_data.get("log_compact"),
                        log_minimal=event_data.get("log_minimal"),
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
        Program.create_agent = self._original_methods["create_agent"]


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
            run._setup_early_streaming()

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
            run.cleanup()

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

"""Debug server for VSCode debugging integration."""

import asyncio
import json
import socket
import sys
import traceback
from logging import error
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.infrastructure.logging.debug_logger import debug

if TYPE_CHECKING:
    from playbooks.program import Program

# Constants
MESSAGE_TIMEOUT = 1.0  # Seconds for message receive timeout
COMMAND_QUEUE_TIMEOUT = 30.0  # Seconds for queued commands
CONNECTION_TIMEOUT = 15.0  # Seconds for client connection


class BreakpointInfo:
    """Information about a single breakpoint."""

    def __init__(
        self,
        id: int,
        line: int,
        condition: Optional[str] = None,
        hit_condition: Optional[str] = None,
        log_message: Optional[str] = None,
    ):
        self.id = id
        self.line = line
        self.condition = condition
        self.hit_condition = hit_condition
        self.log_message = log_message
        self.hit_counts: Dict[str, int] = {}  # {agent_id: count}
        self.verified = False

    def should_break(self, agent_id: str, variables: Dict[str, Any]) -> bool:
        """Check if breakpoint should trigger for this agent."""
        # Update hit count
        self.hit_counts[agent_id] = self.hit_counts.get(agent_id, 0) + 1

        # Check hit condition first
        if self.hit_condition:
            if not self._evaluate_hit_condition(agent_id):
                return False

        # Check regular condition
        if self.condition:
            try:
                # Evaluate condition in agent's variable context
                # Use a restricted eval for safety
                return eval(self.condition, {"__builtins__": {}}, variables)
            except Exception as e:
                debug(f"Failed to evaluate breakpoint condition: {e}")
                return False

        return True

    def _evaluate_hit_condition(self, agent_id: str) -> bool:
        """Evaluate hit count expressions like '>= 5' or '% 10 == 0'."""
        if not self.hit_condition:
            return True

        expr = self.hit_condition.strip()
        count = self.hit_counts.get(agent_id, 0)

        try:
            # Simple number means exact match
            if expr.isdigit():
                return count == int(expr)

            # Handle expressions like "== 5", ">= 10", "% 2 == 0"
            # Replace @HIT@ placeholder with actual count
            expr = expr.replace("@HIT@", str(count))

            # For safety, evaluate with restricted globals
            return eval(expr, {"__builtins__": {}}, {})
        except Exception as e:
            debug(f"Failed to evaluate hit condition: {e}")
            return True  # Default to breaking if expression invalid


class DebugServer:
    """Debug server that provides DAP-like interface for VSCode debugging."""

    def __init__(self, program: "Program", host: str = "127.0.0.1", port: int = 7529):
        self.host = host
        self.port = port
        self.program = program
        self.sequence = 1
        self.client_socket: Optional[socket.socket] = None
        self.server_socket: Optional[socket.socket] = None
        self.is_running = False
        self.debug_session_active = False  # Controls message handler lifecycle
        self.stop_on_entry = False
        # Per-agent continue events - managed by debug handler
        # self._continue_event removed - now using per-agent events in debug_handler
        # self._all_threads_stopped = (
        #     False  # Flag to indicate all threads/agents are stopped
        # )
        self._step_mode = None  # None, 'over', 'into', 'out'
        self._step_events = {}  # Dict of agent_id -> Event for stepping

        # Registration state management
        self._agents_ready = False
        self._pending_commands: List[Dict[str, Any]] = []

        # Breakpoint storage
        self._breakpoints: Dict[str, Dict[int, BreakpointInfo]] = (
            {}
        )  # {file_path: {line: BreakpointInfo}}
        self._breakpoint_id_counter = 1

        self._pause_requested: Dict[str, bool] = {}  # agent_id -> pause_requested
        self.agent_stopped_on_entry: Dict[str, bool] = (
            {}
        )  # agent_id -> stopped_on_entry

        # Debug handler - will be set later
        self.debug_handler = None

    async def start(self) -> Dict[str, Any]:
        """Connect to VSCode debug adapter or start our own server."""
        try:
            await self._start_server()
            # debug("Debug server started successfully")
        except Exception as error:
            debug(
                f"Failed to start debug server: {error} - continuing without debugging"
            )
            debug("Debug server error", error=traceback.format_exc())
            self.is_running = True

        return {}

    async def _handle_messages(self):
        """Handle incoming messages from debug adapter."""
        # debug("Starting message handler")
        if not self.client_socket:
            debug("No client socket - exiting message handler")
            return

        loop = asyncio.get_event_loop()
        buffer = b""
        self.is_running = True  # Ensure the flag is set
        self.debug_session_active = (
            True  # Keep message handler alive during debug session
        )

        try:
            debug(
                f"[DEBUG] About to start message loop - debug_session_active={self.debug_session_active}",
            )
            # debug("[MESSAGE_HANDLER] Starting message loop")
            while self.debug_session_active:
                # print("[DEBUG] Message loop iteration", file=sys.stderr)
                try:
                    # Read data with a timeout to check is_running periodically
                    # Don't break on empty data - VSCode might not send anything initially
                    data = await asyncio.wait_for(
                        loop.sock_recv(self.client_socket, 1024),
                        timeout=MESSAGE_TIMEOUT,
                    )

                    if not data:
                        # Connection closed by client
                        # print(
                        #     "[DEBUG] No data received - connection closed by client",
                        #     file=sys.stderr,
                        # )
                        debug("[MESSAGE_HANDLER] Connection closed by client")
                        # Terminate the debug session and shutdown the program
                        await self._handle_client_disconnection()
                        break

                    # print(
                    #     f"[DEBUG] Received {len(data)} bytes of data", file=sys.stderr
                    # )
                    # debug(f"[MESSAGE_HANDLER] Received {len(data)} bytes: {data[:100]}")
                    buffer += data
                    # print(
                    #     f"[DEBUG] Buffer now has {len(buffer)} bytes", file=sys.stderr
                    # )

                    # Process complete messages
                    # print(
                    #     "[DEBUG] Checking for complete messages in buffer",
                    #     file=sys.stderr,
                    # )
                    while b"\n" in buffer:
                        # print(
                        #     "[DEBUG] Found newline in buffer, extracting message",
                        #     file=sys.stderr,
                        # )
                        line, buffer = buffer.split(b"\n", 1)
                        if line.strip():
                            # print(
                            #     f"[DEBUG] Processing line: {line[:100]}",
                            #     file=sys.stderr,
                            # )
                            try:
                                message = json.loads(line.decode("utf-8"))
                                # print(
                                #     f"[DEBUG] Parsed JSON message: {message}",
                                #     file=sys.stderr,
                                # )
                                # debug(f"[SOCKET] Received raw message: {message}")
                                # print(
                                #     "[DEBUG] Calling _process_message", file=sys.stderr
                                # )
                                await self._process_message(message)
                                # print(
                                #     "[DEBUG] _process_message returned", file=sys.stderr
                                # )
                            except json.JSONDecodeError:
                                debug(
                                    "Invalid JSON received", data=line.decode("utf-8")
                                )

                except asyncio.TimeoutError:
                    # Timeout is normal - just check if we should continue
                    # debug("[MESSAGE_HANDLER] Timeout - continuing loop...")
                    continue
                except ConnectionResetError:
                    debug("Connection reset by client")
                    # Terminate the debug session and shutdown the program
                    await self._handle_client_disconnection()
                    break

        except Exception as e:
            debug("Message handling error", error=str(e))
            debug(traceback.format_exc())
        finally:
            # debug(
            #     f"[MESSAGE_HANDLER] Exiting - debug_session_active={self.debug_session_active}, has_socket={self.client_socket is not None}"
            # )
            # Only close the socket when we're shutting down or connection is lost
            if not self.debug_session_active or not self.client_socket:
                if self.client_socket:
                    self.client_socket.close()
                    self.client_socket = None
                    # print(
                    #     "[DEBUG] Client socket closed in message handler",
                    #     file=sys.stderr,
                    # )

    async def _process_message(self, message: Dict[str, Any]):
        """Process a message from the debug adapter."""
        command = message.get("command")
        # debug("Received debug command", command=command, message=message)

        # if command == "get_threads":
        #     debug("*** GET_THREADS COMMAND DETECTED ***")
        debug(f"[red]Command:{command}[/red] {json.dumps(message, indent=2)}")

        # Handle setBreakpoints request (global command - doesn't need debug_handler)
        if command == "setBreakpoints":
            await self._handle_set(message)
            return

        # Handle get_threads request (doesn't need debug_handler or threadId)
        if command == "get_threads":
            await self._handle_get_threads(message)
            return

        # For other commands, we need the debug_handler
        if not self.debug_handler:
            error(f"No debug handler available for command: {command}")
            return

        # For execution control commands, we need a threadId
        thread_id = message.get("body", {}).get("threadId")
        if thread_id is None:
            error("No threadId provided in debug command")
            return

        agent_id = self.thread_id_to_agent_id(thread_id)

        # Handle basic debug commands
        if command == "continue":
            debug(
                f"Processing continue command for agent {agent_id} (thread {thread_id})"
            )

            # Signal that continue has been received
            self.clear_pause_request(agent_id)
            # Use per-agent continue events via debug handler
            # self._continue_event.set()  # Removed global event

            # Clear the all threads stopped flag since we're resuming
            # self.set_all_threads_stopped(False)

            # Continue execution - signal the debug handler
            self.debug_handler.signal_continue(agent_id)

            # For per-agent debugging, we should always continue only the specific thread
            # DAP compliance: allThreadsContinued should be False for single-thread continues
            all_threads_continued = False  # Only continue the specific agent/thread

            # Send response back to VSCode with proper DAP semantics
            await self._send_message(
                {
                    "type": "response",
                    "command": "continue",
                    "request_seq": message["seq"],
                    "success": True,
                    "body": {"allThreadsContinued": all_threads_continued},
                }
            )

            # Send continued event for this specific thread (DAP compliance)
            await self._send_message(
                {
                    "type": "event",
                    "event": "continued",
                    "body": {
                        "threadId": thread_id,
                        "allThreadsContinued": all_threads_continued,
                    },
                }
            )

            self.program.agents_by_id[agent_id].paused = None
            await self.debug_handler.refresh_stopped_status(agent_id)
        elif command == "next":
            await self.debug_handler.handle_step(
                agent_id, command, request_seq=message["seq"]
            )
        elif command == "stepIn":
            await self.debug_handler.handle_step(
                agent_id, command, request_seq=message["seq"]
            )

        elif command == "stepOut":
            await self.debug_handler.handle_step(
                agent_id, command, request_seq=message["seq"]
            )
        elif command == "pause":
            await self._send_message(
                {
                    "type": "response",
                    "command": "pause",
                    "request_seq": message["seq"],
                    "success": True,
                    "body": {},
                }
            )
            self.set_pause_request(agent_id)

        elif command == "get_variables":
            # Get variables from agent's execution state
            # debug(f"Get variables command received for agent_id: {agent_id}")
            variables = {}

            try:
                agent = self.program.agents_by_id[agent_id]
                variables = agent.state.to_dict()
                # debug(f"Retrieved {len(variables)} variables from agent {agent_id}")
            except Exception as e:
                debug(f"Error retrieving variables for agent {agent_id}: {e}")
                variables = {}

            # Send response with variables
            await self._send_message(
                {
                    "type": "response",
                    "command": "get_variables",
                    "seq": message.get("seq", self.sequence),
                    "body": {"variables": variables},
                }
            )
            # debug(f"Sent variables response with {len(variables)} variables")
        elif command == "get_stack_trace":
            # Get stack trace from agent's execution state
            # debug(f"Get stack trace command received for agent_id: {agent_id}")
            stack_trace = []
            try:
                agent = self.program.agents_by_id[agent_id]
                for frame in reversed(agent.call_stack.frames):
                    name = frame.instruction_pointer.to_compact_str()
                    if frame.is_meeting:
                        name = f"{name}[meeting {frame.meeting_id}]"

                    stack_trace.append(
                        {
                            "name": name,
                            "file": str(
                                Path(
                                    frame.instruction_pointer.source_file_path
                                ).absolute()
                            ),
                            "playbook": frame.instruction_pointer.playbook,
                            "playbook_line_number": frame.instruction_pointer.line_number,
                            "source_line_number": frame.instruction_pointer.source_line_number,
                        }
                    )

                # debug(
                #     f"Retrieved {len(stack_trace)} stack frames from agent {agent_id}"
                # )
            except Exception as e:
                debug(f"Error retrieving stack trace for agent {agent_id}: {e}")

            # Send response with stack trace
            await self._send_message(
                {
                    "type": "response",
                    "command": "get_stack_trace",
                    "seq": message.get("seq", self.sequence),
                    "body": {"stackTrace": stack_trace, "threadId": thread_id},
                }
            )
            # debug(f"Sent stack trace response with {len(stack_trace)} frames")

    async def _send_message(self, message: Dict[str, Any]):
        """Send a message to the debug adapter."""
        # Check if client socket is available
        # print(
        #     f"[DEBUG] _send_message called, client_socket={self.client_socket is not None}, message type={message.get('type')}, event={message.get('event')}",
        #     file=sys.stderr,
        # )
        if not self.client_socket:
            print(
                f"[WARNING] Client socket not available, cannot send message: {message}",
                file=sys.stderr,
            )
            # Don't wait indefinitely - this could be called from different async contexts
            return

        if message.get("type") == "event":
            content = f"[yellow]Event: {message.get('event')}[/yellow]"
        elif message.get("type") == "response":
            content = f"[green]Response: {message.get('command')}[/green]"
        else:
            content = f"[purple]Message: {message.get('type')}[/purple]"
        debug(str(message))
        debug(
            f"{content}: {json.dumps(message, indent=2)}",
        )
        try:
            data = (json.dumps(message) + "\n").encode("utf-8")
            loop = asyncio.get_event_loop()
            await loop.sock_sendall(self.client_socket, data)
        except Exception as e:
            debug("Failed to send message to debug adapter", error=str(e))
            print(
                f"[ERROR] Failed to send message: {e}",
                file=sys.stderr,
            )

    async def send_thread_started_event(self, agent_id: str):
        thread_id = self.agent_id_to_thread_id(agent_id)
        await self._send_message(
            {
                "type": "event",
                "event": "thread",
                "body": {
                    "reason": "started",
                    "threadId": thread_id,
                },
            }
        )

    async def send_thread_exited_event(self, agent_id: str):
        thread_id = self.agent_id_to_thread_id(agent_id)
        await self._send_message(
            {
                "type": "event",
                "event": "thread",
                "body": {
                    "reason": "exited",
                    "threadId": thread_id,
                },
            }
        )

    def get_stop_on_entry(self) -> bool:
        """Get stop on entry flag."""
        return self.stop_on_entry

    def set_stop_on_entry(self, stop: bool):
        """Set stop on entry flag."""
        # print(f"[DEBUG] set_stop_on_entry called with: {stop}", file=sys.stderr)
        self.stop_on_entry = stop

    def has_agent_stopped_on_entry(self, agent_id: str) -> bool:
        """Check if agent has already stopped on entry."""
        return self.agent_stopped_on_entry.get(agent_id, False)

    def set_agent_stopped_on_entry(self, agent_id: str, stopped: bool = True):
        """Set that agent has stopped on entry."""
        self.agent_stopped_on_entry[agent_id] = stopped

    def reset_agent_stop_on_entry_flags(self):
        """Reset all agent stop-on-entry flags (for new debug session)."""
        self.agent_stopped_on_entry.clear()

    async def wait_for_continue(self, agent_id: str = None):
        """Wait for continue command from VSCode for a specific agent."""
        if not agent_id:
            agent_id = "default"

        # Use the debug handler's per-agent continue events
        if hasattr(self, "debug_handler") and self.debug_handler:
            await self.debug_handler._wait_for_continue(agent_id)
        else:
            # Fallback - should not happen in normal operation
            import asyncio

            await asyncio.Event().wait()  # This will wait forever - should be avoided

    def set_pause_request(self, agent_id: str):
        """Set pause request flag."""
        self._pause_requested[agent_id] = True

    def is_pause_requested(self, agent_id: str) -> bool:
        """Check if pause was requested."""
        return self._pause_requested.get(agent_id, False)

    def clear_pause_request(self, agent_id: str):
        """Clear pause request flag."""
        self._pause_requested[agent_id] = False

    def get_step_mode(self) -> str:
        """Get current step mode."""
        return self._step_mode

    def clear_step_mode(self):
        """Clear step mode."""
        self._step_mode = None

    async def wait_for_client(self):
        """Wait for client connection - compatibility method."""
        # In the new implementation, we handle this in start()
        pass

    def set_program(self, program):
        """Set program reference."""
        self.program = program

    def set_debug_handler(self, debug_handler):
        """Set debug handler reference."""
        self.debug_handler = debug_handler

    def register_bus(self, _event_bus) -> None:
        """Register event bus."""
        # Not needed for this implementation - parameter kept for compatibility
        pass

    async def _start_server(self):
        """Start a server that VSCode can connect to (reverse of normal connection)."""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.setblocking(False)

            # Bind to the configured host and port
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)

            # print(
            #     "Debug server listening on 127.0.0.1:7529 for VSCode connection",
            #     file=sys.stderr,
            # )

            # Wait for VSCode to connect (with timeout)
            loop = asyncio.get_event_loop()
            try:
                self.client_socket, addr = await asyncio.wait_for(
                    loop.sock_accept(self.server_socket), timeout=CONNECTION_TIMEOUT
                )
                # print(f"VSCode connected from {addr}", file=sys.stderr)
                # print(
                #     f"[DEBUG] Client socket established: {self.client_socket}",
                #     file=sys.stderr,
                # )

                # Start message handling FIRST, before sending any events
                # print(
                #     "[DEBUG] Starting _handle_messages as background task",
                #     file=sys.stderr,
                # )
                asyncio.create_task(self._handle_messages())
                # print("[DEBUG] Background task created", file=sys.stderr)
                # Give the message handler a small delay to start its loop
                await asyncio.sleep(0.1)
                # print("[DEBUG] Message handler should be ready now", file=sys.stderr)

                # NOW send initial connection message
                await self._send_message(
                    {"type": "event", "event": "connected", "data": {}}
                )

                # Send initialization event (this triggers VSCode to send breakpoints)
                await self._send_message(
                    {"type": "event", "event": "initialized", "body": {}}
                )

                await self._send_message(
                    {
                        "type": "event",
                        "event": "compiledProgramPaths",
                        "body": {
                            "compiled_program_paths": self.program.compiled_program_paths,
                        },
                    }
                )

                # Debug server is now ready for breakpoints and execution control

            except asyncio.TimeoutError:
                print(
                    "Timeout waiting for VSCode to connect - continuing without debugging",
                    file=sys.stderr,
                )
                if self.server_socket:
                    self.server_socket.close()
                    self.server_socket = None

        except Exception as e:
            print(f"Failed to start reverse server: {e}", file=sys.stderr)
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
            raise

    async def _handle_client_disconnection(self):
        """Handle client disconnection by terminating debug session and program."""
        debug("[DEBUG] Handling client disconnection - terminating debug session")

        # Mark debug session as inactive
        self.debug_session_active = False

        # Shutdown the debug server
        await self.shutdown()

        # Trigger program shutdown if we have a program reference
        if self.program:
            debug(
                "[DEBUG] Triggering program shutdown due to debug client disconnection"
            )
            # Set execution finished to trigger clean shutdown
            await self.program.set_execution_finished(
                reason="debug_client_disconnected", exit_code=0
            )

    async def shutdown(self):
        """Shutdown the debug server."""
        # print("[DEBUG] Debug server shutdown called", file=sys.stderr)
        self.is_running = False
        self.debug_session_active = False  # This will stop the message handler
        if self.client_socket:
            # print("[DEBUG] Closing client socket in shutdown", file=sys.stderr)
            self.client_socket.close()
            self.client_socket = None
        if self.server_socket:
            # print("[DEBUG] Closing server socket in shutdown", file=sys.stderr)
            self.server_socket.close()
            self.server_socket = None
        # debug("Debug connection shutdown")

    @property
    def compiled_file_path(self) -> str:
        """Get the compiled file path."""
        return str(self.program.compiled_program_paths[0])

    async def _handle_set(self, message: Dict[str, Any]):
        """Handle setBreakpoints command from the debug adapter."""
        # debug(f"_handle_set_breakpoints called with message: {message}")
        body = message.get("body", {})
        source = body.get("source")
        breakpoints = body.get("breakpoints", [])
        # debug(f"Extracted: source={source}, breakpoints={breakpoints}")
        # debug(f"Source type: {type(source)}, length: {len(source) if source else 0}")
        # debug(f"Source repr: {repr(source)}")

        if not source:
            # Send error response
            await self._send_message(
                {
                    "type": "response",
                    "command": "setBreakpoints",
                    "request_seq": message["seq"],
                    "success": False,
                    "message": "No source file specified",
                    "body": {"breakpoints": []},
                }
            )
            return

        # Clear existing breakpoints for this file
        if source in self._breakpoints:
            del self._breakpoints[source]

        # Add new breakpoints
        verified_breakpoints = []
        if breakpoints:
            file_breakpoints = {}
            for bp in breakpoints:
                bp_info = BreakpointInfo(
                    id=bp.get("id", self._breakpoint_id_counter),
                    line=bp["line"],
                    condition=bp.get("condition"),
                    hit_condition=bp.get("hitCondition"),
                    log_message=bp.get("logMessage"),
                )
                self._breakpoint_id_counter += 1

                # Verify breakpoint (check if line is executable)
                bp_info.verified = self._verify_breakpoint(source, bp["line"])
                file_breakpoints[bp["line"]] = bp_info

                verified_breakpoints.append(
                    {"id": bp_info.id, "verified": bp_info.verified, "line": bp["line"]}
                )

                # debug(
                #     f"Set breakpoint at {source}:{bp['line']} - verified: {bp_info.verified}"
                # )

            self._breakpoints[source] = file_breakpoints

        # Send response with verification status
        await self._send_message(
            {
                "type": "response",
                "command": "setBreakpoints",
                "seq": message.get("seq", self.sequence),
                "success": True,
                "body": {"breakpoints": verified_breakpoints},
            }
        )

        # debug(f"Set {len(verified_breakpoints)} breakpoints in {source}")

    def agent_id_to_thread_id(self, agent_id: str) -> int:
        """Convert an agent ID to a thread ID."""
        try:
            return int(agent_id)
        except ValueError:
            return 0

    def thread_id_to_agent_id(self, thread_id: int) -> str:
        """Convert a thread ID to an agent ID."""
        return str(thread_id)

    async def _handle_get_threads(self, message: Dict[str, Any]):
        """Handle get_threads command from the debug adapter."""
        # debug("get_threads command received - discovering agents from program")
        # debug(f"Current state: _agents_ready={self._agents_ready}")

        threads = []
        # new_threads = []  # Track newly discovered threads for lifecycle events

        if self.program and hasattr(self.program, "agents_by_id"):
            # debug(
            #     f"Program found with {len(self.program.agents_by_id)} agents: {list(self.program.agents_by_id.keys())}"
            # )
            # Dynamically discover threads from active agents
            for agent_id, agent in self.program.agents_by_id.items():
                # Create thread name from agent info
                agent_name = str(agent)

                threads.append(
                    {
                        "id": self.agent_id_to_thread_id(agent_id),
                        "name": agent_name,
                    }
                )

        # Mark agents as ready if we found any
        if threads:
            self._agents_ready = True
            # debug(
            #     f"Agents discovered - now ready for debugging. {len(threads)} threads registered: {[t['id'] for t in threads]}"
            # )

            # Send agents ready event to VSCode
            if self.client_socket:
                await self._send_message(
                    {
                        "type": "event",
                        "event": "agents_ready",
                        "body": {"agentCount": len(threads)},
                    }
                )

            # Process any pending commands
            await self._process_pending_commands()

        # Send response with threads
        await self._send_message(
            {
                "type": "response",
                "command": "get_threads",
                "request_seq": message["seq"],
                "success": True,
                "threads": threads,
            }
        )

        # debug(
        #     f"Sent threads response with {len(threads)} dynamically discovered threads"
        # )

    async def _send_error_response(
        self, original_message: Dict[str, Any], error_message: str, error_code: str
    ):
        """Send a DAP-compliant error response."""
        command = original_message.get("command", "unknown")
        seq = original_message.get("seq", self.sequence)

        error_response = {
            "type": "response",
            "command": command,
            "request_seq": seq,
            "success": False,
            "message": error_message,
            "body": {"error": {"id": 1, "format": error_message, "code": error_code}},
        }

        await self._send_message(error_response)
        debug(f"Sent error response for {command}: {error_message}")

    async def _queue_command(self, message: Dict[str, Any]):
        """Queue a command to be processed when agents are ready."""
        # command = message.get("command", "unknown")
        self._pending_commands.append(message)
        # debug(f"Queued {command} command. Queue size: {len(self._pending_commands)}")

        # Set up timeout for this command
        asyncio.create_task(self._timeout_queued_command(message))

    async def _timeout_queued_command(self, message: Dict[str, Any]):
        """Handle timeout for queued commands."""
        await asyncio.sleep(COMMAND_QUEUE_TIMEOUT)

        # If command is still in queue after timeout, send error response
        if message in self._pending_commands:
            self._pending_commands.remove(message)
            # command = message.get("command", "unknown")
            # debug(f"Command {command} timed out waiting for agents")
            await self._send_error_response(
                message, "Timed out waiting for agents to be ready", "AGENT_TIMEOUT"
            )

    async def _process_pending_commands(self):
        """Process all queued commands now that agents are ready."""
        if not self._pending_commands:
            return

        # debug(f"Processing {len(self._pending_commands)} pending commands")
        commands_to_process = self._pending_commands.copy()
        self._pending_commands.clear()

        for message in commands_to_process:
            command = message.get("command", "unknown")
            # debug(f"Processing queued {command} command")
            try:
                await self._process_message(message)
            except Exception as e:
                error(f"Error processing queued {command} command: {e}")
                await self._send_error_response(
                    message, f"Error processing command: {e}", "PROCESSING_ERROR"
                )

    def _verify_breakpoint(self, file_path: str, line_number: int) -> bool:
        """Verify if line is valid for breakpoint."""
        try:
            # Check if file exists and line is within range
            import os

            if not os.path.exists(file_path):
                return False

            with open(file_path, "r") as f:
                lines = f.readlines()
                if 0 < line_number <= len(lines):
                    # Check if line contains executable instruction
                    line = lines[line_number - 1].strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        # In .pbasm files, most non-empty, non-comment lines are executable
                        return True
        except Exception as e:
            debug(f"Error verifying breakpoint: {e}")
        return False

    async def check_breakpoint(
        self, agent_id: str, file_path: str, line_number: int
    ) -> bool:
        debug(f"Checking breakpoint for agent {agent_id} at {file_path}:{line_number}")
        debug(f"Breakpoints: {self._breakpoints}")
        debug(f"Stored breakpoint file paths: {list(self._breakpoints.keys())}")
        debug(f"Looking for file path: '{file_path}'")
        debug(f"File path type: {type(file_path)}, length: {len(file_path)}")
        """Check if we should break at this location."""

        # Normalize the file path to handle absolute vs relative path mismatches
        normalized_file_path = self._normalize_breakpoint_path(file_path)
        debug(f"Normalized file path: '{normalized_file_path}'")

        if normalized_file_path not in self._breakpoints:
            debug(f"No breakpoints set for file: {normalized_file_path}")
            return False

        file_breakpoints = self._breakpoints[normalized_file_path]
        if line_number not in file_breakpoints:
            debug(
                f"No breakpoint set for line: {line_number} in file: {normalized_file_path}"
            )
            return False

        bp_info = file_breakpoints[line_number]

        # Get agent's variables for condition evaluation
        try:
            agent = self.program.agents_by_id[agent_id]
            from playbooks.state.variables import VariablesTracker

            variables = VariablesTracker.to_dict(agent.state)
        except Exception as e:
            debug(f"Failed to get agent variables: {e}")
            variables = {}

        if bp_info.should_break(agent_id, variables):
            if bp_info.log_message:
                # Handle logpoint - don't stop, just log
                message = self._interpolate_log_message(bp_info.log_message, variables)
                await self._send_message(
                    {
                        "type": "event",
                        "event": "output",
                        "body": {
                            "category": "console",
                            "output": f"[Agent {agent_id}] {message}\n",
                        },
                    }
                )
                return False
            else:
                return True

        return False

    def _interpolate_log_message(self, message: str, variables: Dict[str, Any]) -> str:
        """Interpolate variables in log message using {variable} syntax."""
        import re

        def replace_var(match):
            var_name = match.group(1)
            value = variables.get(var_name, f"<undefined:{var_name}>")
            return str(value)

        # Replace {variable} with actual values
        return re.sub(r"\{(\w+)\}", replace_var, message)

    def _normalize_breakpoint_path(self, file_path: str) -> str:
        """Normalize file path for breakpoint matching.

        This handles the mismatch between absolute paths stored by VS Code
        and relative paths used during execution.
        """
        import os

        # If it's already an absolute path that exists in breakpoints, use it as-is
        if os.path.isabs(file_path) and file_path in self._breakpoints:
            return file_path

        # If it's a relative path, try to find matching absolute path in breakpoints
        if not os.path.isabs(file_path):
            # Normalize separators for comparison
            normalized_input = file_path.replace("\\", "/")
            for stored_path in self._breakpoints.keys():
                if stored_path.endswith(normalized_input) or stored_path.replace(
                    "\\", "/"
                ).endswith(normalized_input):
                    return stored_path

        # If it's an absolute path, try to find matching relative path in breakpoints
        if os.path.isabs(file_path):
            # Extract the relative part (e.g., get ".pbasm_cache/file.pbasm" from full path)
            for stored_path in self._breakpoints.keys():
                if file_path.endswith(stored_path.replace(os.path.sep, "/")):
                    return stored_path

        # If no match found, return original path
        return file_path

    @property
    def current_call_stack(self) -> List[Dict[str, Any]]:
        """Get the current stack."""
        if not self.program.agents:
            return []
        agent = self.program.agents[0]
        stack = agent.call_stack.to_dict()
        if not stack:
            return []
        for frame in stack:
            frame["file_path"] = self.compiled_file_path
        return stack

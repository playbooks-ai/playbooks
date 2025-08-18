"""
Debug server for Playbooks.

This module provides a debug server that can be embedded in playbook execution
to provide debugging capabilities through a simple TCP protocol.
"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from ..debug_logger import debug
from ..event_bus import EventBus
from ..events import (
    AgentPausedEvent,
    AgentResumedEvent,
    AgentStartedEvent,
    AgentStoppedEvent,
    AgentVariableUpdateEvent,
    BreakpointHitEvent,
    ExecutionPausedEvent,
    LineExecutedEvent,
    PlaybookEndEvent,
    PlaybookStartEvent,
    ProgramTerminatedEvent,
    StepCompleteEvent,
    VariableUpdateEvent,
)

if TYPE_CHECKING:
    from ..program import Program


class DebugServer:
    """
    Debug server that provides debugging capabilities for playbook execution.

    This server communicates with the debug adapter through a simple JSON
    protocol over TCP, allowing for breakpoint management, stepping, and
    variable inspection.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7529) -> None:
        """Initialize the debug server."""
        self.host = host
        self.port = port
        self.server: Optional[asyncio.AbstractServer] = None
        self.clients: List[asyncio.StreamWriter] = []
        self.logger = logging.getLogger(__name__)

        # Debug state
        self._program: Program = None
        self._breakpoints: Dict[str, Set[int]] = {}
        self._step_mode: Optional[str] = None  # "next", "step_in", "step_out"
        self._step_initial_frame: Optional[Dict[str, Any]] = None
        self._stop_on_entry: bool = False

        # Agent and thread management
        self._agents: Dict[str, Dict[str, Any]] = {}  # agent_id -> agent info
        self._thread_counter: int = 1  # Start thread IDs at 1
        self._thread_to_agent: Dict[int, str] = {}  # thread_id -> agent_id
        self._agent_to_thread: Dict[str, int] = {}  # agent_id -> thread_id
        self._agent_step_modes: Dict[str, Optional[str]] = {}  # per-agent step modes
        self._agent_continue_events: Dict[str, asyncio.Event] = (
            {}
        )  # per-agent continue events
        self._agent_step_initial_frames: Dict[str, Optional[Dict[str, Any]]] = (
            {}
        )  # per-agent initial frames

        # Synchronization
        self._continue_event = asyncio.Event()

        # Event bus for receiving playbook events
        self._event_bus: Optional[EventBus] = None

    def set_program(self, program) -> None:
        """Set the program being debugged."""
        self._program = program
        self.logger.info(f"Debug server attached to program: {program}")

    def register_bus(self, bus: EventBus) -> None:
        """Register the event bus to receive playbook events."""
        # Prevent duplicate registration of the same bus
        if self._event_bus is bus:
            self.logger.debug(
                "Event bus already registered, skipping duplicate registration"
            )
            return

        # Unsubscribe from previous bus if one was registered
        if self._event_bus:
            self._event_bus.unsubscribe("*", self._on_event)
            self.logger.debug("Unsubscribed from previous event bus")

        self._event_bus = bus
        if bus:
            # Register for all events that might be relevant for debugging
            bus.subscribe("*", self._on_event)
            self.logger.info("Debug server registered with event bus")

    def set_stop_on_entry(self, stop_on_entry: bool) -> None:
        """Set whether to stop on entry."""
        self._stop_on_entry = stop_on_entry
        self.logger.debug(f"set_stop_on_entry called with: {stop_on_entry}")
        self.logger.info(f"Stop on entry set to: {stop_on_entry}")

    def register_agent(self, agent_id: str, agent_name: str, agent_type: str) -> int:
        """Register an agent and assign it a thread ID."""
        if agent_id in self._agent_to_thread:
            # Agent already registered, return existing thread ID
            return self._agent_to_thread[agent_id]

        thread_id = self._thread_counter
        self._thread_counter += 1

        self._agents[agent_id] = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "thread_id": thread_id,
            "status": "starting",
            "variables": {},
            "call_stack": [],
        }

        self._thread_to_agent[thread_id] = agent_id
        self._agent_to_thread[agent_id] = thread_id
        self._agent_step_modes[agent_id] = None
        self._agent_continue_events[agent_id] = asyncio.Event()

        self.logger.info(
            f"Registered agent {agent_id} ({agent_name}) as thread {thread_id}"
        )
        return thread_id

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent and clean up its resources."""
        if agent_id not in self._agent_to_thread:
            return

        thread_id = self._agent_to_thread[agent_id]

        # Clean up mappings
        del self._agents[agent_id]
        del self._thread_to_agent[thread_id]
        del self._agent_to_thread[agent_id]
        del self._agent_step_modes[agent_id]
        del self._agent_continue_events[agent_id]
        if agent_id in self._agent_step_initial_frames:
            del self._agent_step_initial_frames[agent_id]

        self.logger.info(f"Unregistered agent {agent_id} (thread {thread_id})")

    def get_agent_threads(self) -> List[Dict[str, Any]]:
        """Get all registered agent threads."""
        threads = []
        for agent_id, agent_info in self._agents.items():
            status_suffix = (
                f" ({agent_info['status']})"
                if agent_info["status"] != "running"
                else ""
            )
            thread_name = f"{agent_info['agent_name']}{status_suffix}"
            threads.append(
                {
                    "id": agent_info["thread_id"],
                    "name": thread_name,
                    "agent_id": agent_id,
                    "status": agent_info["status"],
                }
            )
        return threads

    def update_agent_status(self, agent_id: str, status: str) -> None:
        """Update an agent's status."""
        if agent_id in self._agents:
            self._agents[agent_id]["status"] = status
            self.logger.debug(f"Updated agent {agent_id} status to {status}")

    def get_agent_by_thread(self, thread_id: int) -> Optional[str]:
        """Get agent ID by thread ID."""
        return self._thread_to_agent.get(thread_id)

    def get_thread_by_agent(self, agent_id: str) -> Optional[int]:
        """Get thread ID by agent ID."""
        return self._agent_to_thread.get(agent_id)

    def update_agent_execution_state(
        self,
        agent_id: str,
        call_stack: List[Dict[str, Any]] = None,
        variables: Dict[str, Any] = None,
    ) -> None:
        """Update an agent's execution state (call stack and variables)."""
        if agent_id not in self._agents:
            return

        if call_stack is not None:
            self._agents[agent_id]["call_stack"] = call_stack

        if variables is not None:
            self._agents[agent_id]["variables"] = variables

        self.logger.debug(f"Updated execution state for agent {agent_id}")

    def update_agent_from_program_state(self, agent_id: str) -> None:
        """Update agent execution state from the program's current state."""
        if not self._program or agent_id not in self._agents:
            return

        # Find the agent in the program
        agent = self._program.agents_by_id.get(agent_id)
        if not agent:
            return

        # Update call stack if available
        if hasattr(agent, "state") and hasattr(agent.state, "call_stack"):
            call_stack = agent.state.call_stack.to_dict()
            self._agents[agent_id]["call_stack"] = call_stack

        # Update variables if available
        if hasattr(agent, "state") and hasattr(agent.state, "variables"):
            variables = agent.state.variables.to_dict()
            # Also add last_llm_response if available
            if hasattr(agent.state, "last_llm_response"):
                variables["last_llm_response"] = agent.state.last_llm_response
            self._agents[agent_id]["variables"] = variables

        self.logger.debug(f"Updated agent {agent_id} from program state")

    async def start(self) -> None:
        """Start the debug server."""
        try:
            self.server = await asyncio.start_server(
                self._handle_client, self.host, self.port
            )
            msg = f"Debug server started on {self.host}:{self.port}"
            self.logger.info(msg)
        except Exception as e:
            self.logger.error(f"Failed to start debug server: {e}")
            raise

    async def signal_program_termination(
        self, reason: str = "normal", exit_code: int = 0
    ) -> None:
        """Signal that the program has terminated to all connected clients."""
        self.logger.debug(
            f"Signaling program termination: {reason}, exit_code: {exit_code}"
        )
        termination_event = {
            "type": "program_terminated",
            "reason": reason,
            "exit_code": exit_code,
        }
        await self._broadcast_event(termination_event)

        # Give clients a moment to process the termination event
        await asyncio.sleep(0.1)

        # Force close all client connections after termination signal
        self.logger.debug(f"Closing {len(self.clients)} client connections")
        disconnected_clients = []
        for client in self.clients:
            try:
                # Send explicit disconnect notification
                disconnect_event = {
                    "type": "disconnect",
                    "reason": "program_terminated",
                }
                message = json.dumps(disconnect_event) + "\n"
                client.write(message.encode())
                await client.drain()

                # Close the connection
                client.close()
                await client.wait_closed()
                disconnected_clients.append(client)
                self.logger.debug("Client connection closed successfully")
            except Exception as e:
                self.logger.debug(f"Error closing client connection: {e}")
                disconnected_clients.append(client)

        # Remove all disconnected clients
        for client in disconnected_clients:
            if client in self.clients:
                self.clients.remove(client)

    async def shutdown(self) -> None:
        """Shutdown the debug server."""
        self.logger.debug("DebugServer.shutdown called")

        # Only signal termination if we still have clients (avoid double signaling)
        if self.clients:
            await self.signal_program_termination("normal", 0)

        if self.server:
            self.logger.debug("Closing debug server")
            self.server.close()
            await self.server.wait_closed()
            self.logger.info("Debug server shutdown")

        # Ensure all client connections are closed
        for client in self.clients[
            :
        ]:  # Copy list to avoid modification during iteration
            try:
                if not client.is_closing():
                    client.close()
                    await client.wait_closed()
            except Exception as e:
                self.logger.debug(f"Error closing client during shutdown: {e}")
        self.clients.clear()
        self.logger.debug("DebugServer.shutdown completed")

    async def wait_for_client(self) -> None:
        """Wait for at least one client to connect."""
        while not self.clients:
            await asyncio.sleep(0.1)
        self.logger.info("Debug client connected")

    async def wait_for_continue(self) -> None:
        """Wait for a continue command from the debug client."""
        self._continue_event.clear()
        await self._continue_event.wait()

    async def wait_for_continue_agent(self, agent_id: str) -> None:
        """Wait for a continue command for a specific agent."""
        if agent_id not in self._agent_continue_events:
            self._agent_continue_events[agent_id] = asyncio.Event()

        self._agent_continue_events[agent_id].clear()
        await self._agent_continue_events[agent_id].wait()

    def should_pause_for_step(self, current_frame: Dict[str, Any]) -> bool:
        """Check if execution should pause based on step mode."""
        try:
            if not self._step_mode or not current_frame:
                return False

            debug("Step mode", step_mode=self._step_mode)
            debug("Current frame", current_frame=current_frame)
            debug("Initial frame", initial_frame=self._step_initial_frame)

            if self._step_mode == "step_in":
                # Always pause on next instruction
                debug("Step in: pausing on next instruction")
                return True

            elif self._step_mode == "next":
                # For step over, we should pause when:
                # 1. We're in the same frame but on a different line
                # 2. We've returned to the caller frame or a shallower frame

                if self._is_same_frame(current_frame, self._step_initial_frame):
                    # Check if we've moved to a different line
                    current_line = current_frame.get("line_number", 0)
                    initial_line = self._step_initial_frame.get("line_number", 0)

                    if current_line != initial_line:
                        debug(
                            "Step over: same frame, different line, pausing",
                            initial_line=initial_line,
                            current_line=current_line,
                        )
                        return True
                    else:
                        print(
                            f"Step over: same frame, same line ({current_line}), continuing"
                        )
                        return False

                # Pause if we've returned to the caller frame or any shallower frame
                current_depth = current_frame.get("depth", 0)
                initial_depth = self._step_initial_frame.get("depth", 0)

                if current_depth <= initial_depth:
                    # We're at the same level or shallower than when we started stepping
                    # This handles both direct returns and cases where we step through multiple frames
                    print(
                        f"Step over: returned to same or shallower level ({initial_depth} -> {current_depth}), pausing"
                    )
                    return True

                print("Step over: deeper frame, continuing")
                return False

            elif self._step_mode == "step_out":
                # Only pause when we've returned to the caller frame
                should_pause = self._is_caller_frame(
                    current_frame, self._step_initial_frame
                )
                print(f"Step out: should pause = {should_pause}")
                return should_pause

            return False
        except Exception as e:
            self.logger.error(f"Error in should_pause_for_step: {e}")
            # Default to not pausing if there's an error
            return False

    def should_pause_for_step_agent(
        self, agent_id: str, current_frame: Dict[str, Any]
    ) -> bool:
        """Check if execution should pause based on agent-specific step mode."""
        try:
            print(f"[DebugServer] Agent {agent_id} current frame: {current_frame}")
            step_mode = self._agent_step_modes.get(agent_id)
            print(f"[DebugServer] Agent {agent_id} step mode: {step_mode}")
            if not step_mode or not current_frame:
                return False

            initial_frame = self._agent_step_initial_frames.get(agent_id)
            print(f"[DebugServer] Agent {agent_id} initial frame: {initial_frame}")

            if step_mode == "step_in":
                # Always pause on next instruction
                print(
                    f"[DebugServer] Agent {agent_id} step in: pausing on next instruction"
                )
                return True

            elif step_mode == "next":
                # For step over, we should pause when:
                # 1. We're in the same frame but on a different line
                # 2. We've returned to the caller frame or a shallower frame

                if self._is_same_frame(current_frame, initial_frame):
                    # Check if we've moved to a different line
                    current_line = current_frame.get("line_number", 0)
                    initial_line = (
                        initial_frame.get("line_number", 0) if initial_frame else 0
                    )

                    if current_line != initial_line:
                        print(
                            f"[DebugServer] Agent {agent_id} step over: same frame, different line ({initial_line} -> {current_line}), pausing"
                        )
                        return True
                    else:
                        print(
                            f"[DebugServer] Agent {agent_id} step over: same frame, same line ({current_line}), continuing"
                        )
                        return False

                # Pause if we've returned to the caller frame or any shallower frame
                current_depth = current_frame.get("depth", 0)
                initial_depth = initial_frame.get("depth", 0) if initial_frame else 0

                if current_depth <= initial_depth:
                    # We're at the same level or shallower than when we started stepping
                    # This handles both direct returns and cases where we step through multiple frames
                    print(
                        f"[DebugServer] Agent {agent_id} step over: returned to same or shallower level ({initial_depth} -> {current_depth}), pausing"
                    )
                    return True

                print(
                    f"[DebugServer] Agent {agent_id} step over: deeper frame, continuing"
                )
                return False

            elif step_mode == "step_out":
                # Only pause when we've returned to the caller frame
                should_pause = self._is_caller_frame(current_frame, initial_frame)
                print(
                    f"[DebugServer] Agent {agent_id} step out: should pause = {should_pause}"
                )
                return should_pause

            return False
        except Exception as e:
            self.logger.error(
                f"Error in should_pause_for_step_agent for {agent_id}: {e}"
            )
            # Default to not pausing if there's an error
            return False

    def _is_same_frame(self, frame1: Dict[str, Any], frame2: Dict[str, Any]) -> bool:
        """Check if two frames represent the same execution context."""
        if not frame1 or not frame2:
            return False
        return frame1.get("playbook") == frame2.get("playbook") and frame1.get(
            "depth"
        ) == frame2.get("depth")

    def _is_caller_frame(
        self, current_frame: Dict[str, Any], initial_frame: Dict[str, Any]
    ) -> bool:
        """Check if current frame is the caller of the initial frame."""
        if not current_frame or not initial_frame:
            return False
        # Check if we're one level up in the call stack
        current_depth = current_frame.get("depth", 0)
        initial_depth = initial_frame.get("depth", 0)
        return current_depth == initial_depth - 1

    def clear_step_mode(self) -> None:
        """Clear the current step mode."""
        self._step_mode = None
        self._step_initial_frame = None

    def _get_current_frame(self) -> Optional[Dict[str, Any]]:
        """Get the current execution frame."""
        try:
            if (
                self._program
                and hasattr(self._program, "agents")
                and self._program.agents
            ):
                agent = self._program.agents[0]
                if hasattr(agent, "state") and hasattr(agent.state, "call_stack"):
                    frame = agent.state.call_stack.peek()
                    if frame and frame.instruction_pointer:
                        # Create a frame snapshot that includes all
                        # relevant info
                        return {
                            "playbook": getattr(
                                frame.instruction_pointer, "playbook", "unknown"
                            ),
                            "depth": len(agent.state.call_stack.frames),
                            "line_number": getattr(
                                frame.instruction_pointer, "source_line_number", 0
                            ),
                            "instruction_pointer": (
                                frame.instruction_pointer.to_dict()
                                if hasattr(frame.instruction_pointer, "to_dict")
                                else str(frame.instruction_pointer)
                            ),
                        }
        except Exception as e:
            self.logger.error(f"Error getting current frame: {e}")
            # Return a basic frame so debugging can continue
            return {
                "playbook": "error",
                "depth": 1,
                "line_number": 0,
                "instruction_pointer": None,
            }
        return None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a new client connection."""
        print("[DEBUG] DebugServer._handle_client - new client connection")
        self.clients.append(writer)
        client_addr = writer.get_extra_info("peername")
        self.logger.info(f"Debug client connected from {client_addr}")
        print(
            f"[DEBUG] DebugServer._handle_client - client connected from {client_addr}"
        )

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                command_str = data.decode().strip()
                if command_str:
                    await self._handle_command(command_str, writer)

        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:
            if writer in self.clients:
                self.clients.remove(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            self.logger.info(f"Debug client {client_addr} disconnected")

    async def _handle_command(
        self, command_str: str, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming commands from debug clients."""
        print(f"[DEBUG] DebugServer._handle_command - received command: {command_str}")
        try:
            command = json.loads(command_str)
            command_type = command.get("command")

            if command_type == "set_breakpoints":
                await self._handle_set_breakpoints(command, writer)
            elif command_type == "continue":
                await self._handle_continue(command, writer)
            elif command_type == "next":
                await self._handle_next(command, writer)
            elif command_type == "step_in":
                await self._handle_step_in(command, writer)
            elif command_type == "step_out":
                await self._handle_step_out(command, writer)
            elif command_type == "get_compiled_program":
                await self._handle_get_compiled_program(command, writer)
            elif command_type == "get_variables":
                await self._handle_get_variables(command, writer)
            elif command_type == "get_call_stack":
                await self._handle_get_call_stack(command, writer)
            elif command_type == "get_threads":
                await self._handle_get_threads(command, writer)
            else:
                msg = f"Unknown command: {command_type}"
                print(msg)
                await self._send_error(writer, msg)

        except (json.JSONDecodeError, KeyError) as e:
            error_msg = f"Invalid command format: {e}"
            self.logger.error(error_msg)
            print(error_msg)
            await self._send_error(writer, error_msg)
        except Exception as e:
            error_msg = f"Error processing command '{command_str}': {e}"
            self.logger.error(error_msg)
            await self._send_error(writer, error_msg)

    async def _handle_set_breakpoints(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle set_breakpoints command."""
        print("[DEBUG] DebugServer._handle_set_breakpoints - entering handler")
        file_path = command.get("file", "")
        lines = set(command.get("lines", []))
        self._breakpoints[file_path] = lines
        print(
            f"[DEBUG] DebugServer._handle_set_breakpoints - set breakpoints for {file_path} at lines {lines}"
        )

        response = {
            "type": "response",
            "command": "set_breakpoints",
            "success": True,
            "file": file_path,
            "lines": list(lines),
        }
        await self._send_response(writer, response)

    async def _handle_continue(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle continue command."""
        print("[DEBUG] DebugServer._handle_continue - entering handler")
        thread_id = command.get("threadId", 1)
        agent_id = self.get_agent_by_thread(thread_id)

        if agent_id:
            # Clear step mode for specific agent
            self._agent_step_modes[agent_id] = None
            self._agent_step_initial_frames[agent_id] = None
            if agent_id in self._agent_continue_events:
                self._agent_continue_events[agent_id].set()
            print(
                f"[DEBUG] DebugServer._handle_continue - cleared step mode for agent {agent_id} (thread {thread_id})"
            )
        else:
            # Fallback to global continue
            self.clear_step_mode()
            self._continue_event.set()
            print(
                "[DEBUG] DebugServer._handle_continue - cleared global step mode and set continue event"
            )

        response = {"type": "response", "command": "continue", "success": True}
        await self._send_response(writer, response)

    async def _handle_next(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle next (step over) command."""
        try:
            self.logger.info("Handling 'next' command")
            print("[DEBUG] DebugServer._handle_next - entering next command handler")

            thread_id = command.get("threadId", 1)
            agent_id = self.get_agent_by_thread(thread_id)

            # Diagnose frame structure
            diagnosis = self.diagnose_frame_structure()
            self.logger.info(f"Frame diagnosis: {diagnosis}")

            if agent_id:
                # Set step mode for specific agent
                self._agent_step_modes[agent_id] = "next"
                self._agent_step_initial_frames[agent_id] = self._get_current_frame()
                if agent_id in self._agent_continue_events:
                    self._agent_continue_events[agent_id].set()
                print(
                    f"[DEBUG] DebugServer._handle_next - set step_mode=next for agent {agent_id} (thread {thread_id})"
                )
                print(
                    f"[DEBUG] DebugServer._handle_next - set initial frame for agent {agent_id}: {self._agent_step_initial_frames[agent_id]}"
                )
            else:
                # Fallback to global step mode
                self._step_mode = "next"
                self._step_initial_frame = self._get_current_frame()
                self._continue_event.set()
                print("[DEBUG] DebugServer._handle_next - set global step_mode=next")

            response = {"type": "response", "command": "next", "success": True}
            await self._send_response(writer, response)
            self.logger.info("Successfully sent 'next' response")
            print("[DEBUG] DebugServer._handle_next - sent response")

        except Exception as e:
            self.logger.error(f"Error in _handle_next: {e}")
            print(f"[DEBUG] DebugServer._handle_next - error: {e}")
            error_response = {
                "type": "response",
                "command": "next",
                "success": False,
                "error": str(e),
            }
            await self._send_response(writer, error_response)

    async def _handle_step_in(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle step_in command."""
        print("[DEBUG] DebugServer._handle_step_in - entering step_in command handler")
        thread_id = command.get("threadId", 1)
        agent_id = self.get_agent_by_thread(thread_id)

        if agent_id:
            # Set step mode for specific agent
            self._agent_step_modes[agent_id] = "step_in"
            self._agent_step_initial_frames[agent_id] = self._get_current_frame()
            if agent_id in self._agent_continue_events:
                self._agent_continue_events[agent_id].set()
            print(
                f"[DEBUG] DebugServer._handle_step_in - set step_mode=step_in for agent {agent_id} (thread {thread_id})"
            )
        else:
            # Fallback to global step mode
            self._step_mode = "step_in"
            self._step_initial_frame = self._get_current_frame()
            self._continue_event.set()
            print("[DEBUG] DebugServer._handle_step_in - set global step_mode=step_in")

        response = {"type": "response", "command": "step_in", "success": True}
        await self._send_response(writer, response)

    async def _handle_step_out(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle step_out command."""
        print(
            "[DEBUG] DebugServer._handle_step_out - entering step_out command handler"
        )
        thread_id = command.get("threadId", 1)
        agent_id = self.get_agent_by_thread(thread_id)

        if agent_id:
            # Set step mode for specific agent
            self._agent_step_modes[agent_id] = "step_out"
            self._agent_step_initial_frames[agent_id] = self._get_current_frame()
            if agent_id in self._agent_continue_events:
                self._agent_continue_events[agent_id].set()
            print(
                f"[DEBUG] DebugServer._handle_step_out - set step_mode=step_out for agent {agent_id} (thread {thread_id})"
            )
        else:
            # Fallback to global step mode
            self._step_mode = "step_out"
            self._step_initial_frame = self._get_current_frame()
            self._continue_event.set()
            print(
                "[DEBUG] DebugServer._handle_step_out - set global step_mode=step_out"
            )

        response = {"type": "response", "command": "step_out", "success": True}
        await self._send_response(writer, response)

    async def _handle_get_compiled_program(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle get_compiled_program command."""
        print("[DEBUG] DebugServer._handle_get_compiled_program - entering handler")
        if self._program:
            compiled_file_path = getattr(
                self._program, "_get_compiled_file_name", lambda: None
            )()
            response = {
                "type": "compiled_program_response",
                "success": True,
                "compiled_file": compiled_file_path,
                "content": getattr(self._program, "full_program", ""),
                "original_files": getattr(self._program, "program_paths", []),
            }
        else:
            response = {
                "type": "compiled_program_response",
                "success": False,
                "error": "No program available",
            }

        await self._send_response(writer, response)

    async def _handle_get_variables(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle get_variables command."""
        print("[DEBUG] DebugServer._handle_get_variables - entering handler")
        thread_id = command.get("threadId", 1)
        agent_id = self.get_agent_by_thread(thread_id)

        if agent_id and agent_id in self._agents:
            variables = self._agents[agent_id]["variables"]
        else:
            variables = self._get_current_variables()  # Fallback to original logic

        print(
            f"[DEBUG] DebugServer._handle_get_variables - retrieved {len(variables)} variables for thread {thread_id}"
        )
        response = {
            "type": "variables_response",
            "success": True,
            "variables": variables,
            "requestId": command.get("requestId"),
        }
        await self._send_response(writer, response)

    async def _handle_get_call_stack(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle get_call_stack command."""
        print("[DEBUG] DebugServer._handle_get_call_stack - entering handler")
        thread_id = command.get("threadId", 1)
        agent_id = self.get_agent_by_thread(thread_id)

        if agent_id and agent_id in self._agents:
            call_stack = self._agents[agent_id]["call_stack"]
        else:
            call_stack = self._get_current_call_stack()  # Fallback to original logic

        print(
            f"[DEBUG] DebugServer._handle_get_call_stack - retrieved call stack with {len(call_stack)} frames for thread {thread_id}"
        )
        response = {
            "type": "call_stack_response",
            "success": True,
            "call_stack": list(reversed(call_stack)),
            "requestId": command.get("requestId"),
        }
        await self._send_response(writer, response)

    async def _handle_get_threads(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle get_threads command."""
        print("[DEBUG] DebugServer._handle_get_threads - entering handler")
        threads = self.get_agent_threads()

        # If no agents registered, provide a default "Main" thread for compatibility
        if not threads:
            threads = [
                {"id": 1, "name": "Main", "agent_id": "main", "status": "running"}
            ]

        print(
            f"[DEBUG] DebugServer._handle_get_threads - returning {len(threads)} threads"
        )
        response = {
            "type": "threads_response",
            "success": True,
            "threads": threads,
            "requestId": command.get("requestId"),
        }
        await self._send_response(writer, response)

    async def _send_response(
        self, writer: asyncio.StreamWriter, response: Dict[str, Any]
    ) -> None:
        """Send a response to a client."""
        try:
            message = json.dumps(response) + "\n"
            writer.write(message.encode())
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError, OSError):
            # Client disconnected - remove from clients list if present
            if writer in self.clients:
                self.clients.remove(writer)
            # msg = f"Client disconnected while sending response: {e}"
        except Exception as e:
            self.logger.error(f"Error sending response: {e}")

    async def _send_error(self, writer: asyncio.StreamWriter, message: str) -> None:
        """Send an error response to a client."""
        error_response = {"type": "error", "message": message}
        await self._send_response(writer, error_response)

    def _get_current_call_stack_depth(self) -> int:
        """Get the current call stack depth from the first agent."""
        if self._program and hasattr(self._program, "agents") and self._program.agents:
            agent = self._program.agents[0]
            if hasattr(agent, "state") and hasattr(agent.state, "call_stack"):
                return len(agent.state.call_stack.frames)
        return 0

    def _get_current_variables(self) -> Dict[str, Any]:
        """Get current variables from the first agent."""
        if self._program and hasattr(self._program, "agents") and self._program.agents:
            agent = self._program.agents[0]
            if hasattr(agent, "state") and hasattr(agent.state, "variables"):
                vars = agent.state.variables.to_dict()
        else:
            vars = {}

        vars["last_llm_response"] = agent.state.last_llm_response
        return vars

    def _get_current_call_stack(self) -> List[Dict[str, Any]]:
        """Get current call stack from the first agent."""
        if self._program and hasattr(self._program, "agents") and self._program.agents:
            agent = self._program.agents[0]
            return agent.state.call_stack.to_dict()
        return []

    def should_pause_at_line(
        self, source_line_number: int, file_path: str = None
    ) -> bool:
        """Check if execution should pause at the given file and line."""
        if file_path:
            return source_line_number in self._breakpoints.get(file_path, set())

        # Check all files if no specific file provided
        for file_breakpoints in self._breakpoints.values():
            if source_line_number in file_breakpoints:
                return True
        return False

    def has_breakpoint(self, source_line_number: int, file_path: str = None) -> bool:
        """Check if there's a breakpoint for the given step or location."""
        return self.should_pause_at_line(source_line_number, file_path)

    def get_breakpoints(self, file_path: str = None) -> Dict[str, Set[int]]:
        """Get all breakpoints or breakpoints for a specific file."""
        if file_path:
            return {file_path: self._breakpoints.get(file_path, set())}
        return self._breakpoints.copy()

    def should_stop_on_entry(self) -> bool:
        """Check if execution should stop on entry."""
        return self._stop_on_entry

    def _on_event(self, event: Any) -> None:
        """Handle an event by sending it to all connected clients."""
        print(
            f"[DEBUG] DebugServer._on_event - handling event of type {type(event).__name__}"
        )
        # Convert event to JSON and broadcast to all clients
        try:
            event_data = self._event_to_dict(event)
            if event_data:
                print(
                    f"[DEBUG] DebugServer._on_event - broadcasting event type: {event_data.get('type')}"
                )
                asyncio.create_task(self._broadcast_event(event_data))
        except Exception as e:
            self.logger.error(f"Error handling event: {e}")

    def _event_to_dict(self, event: Any) -> Optional[Dict[str, Any]]:
        """Convert an event object to a dictionary for JSON serialization."""
        if hasattr(event, "__class__"):
            # Map specific event types to debug protocol events
            if isinstance(event, BreakpointHitEvent):
                # Update agent execution state when breakpoint is hit
                if (
                    self._program
                    and hasattr(self._program, "agents")
                    and self._program.agents
                ):
                    main_agent = self._program.agents[0]
                    if main_agent and main_agent.id in self._agents:
                        self.update_agent_from_program_state(main_agent.id)
                        thread_id = self.get_thread_by_agent(main_agent.id) or 1

                        return {
                            "type": "breakpoint_hit",
                            "thread_id": thread_id,
                            "threadId": thread_id,
                            "file_path": getattr(event, "file_path", ""),
                            "line_number": getattr(event, "line_number", 0),
                            "source_line_number": getattr(
                                event, "source_line_number", 0
                            ),
                            "reason": "breakpoint",
                        }

                return {
                    "type": "breakpoint_hit",
                    "thread_id": 1,
                    "threadId": 1,
                    "file_path": getattr(event, "file_path", ""),
                    "line_number": getattr(event, "line_number", 0),
                    "source_line_number": getattr(event, "source_line_number", 0),
                    "reason": "breakpoint",
                }
            elif isinstance(event, StepCompleteEvent):
                # Update agent execution state when step completes
                if (
                    self._program
                    and hasattr(self._program, "agents")
                    and self._program.agents
                ):
                    main_agent = self._program.agents[0]
                    if main_agent and main_agent.id in self._agents:
                        self.update_agent_from_program_state(main_agent.id)
                        # Get the thread ID for this agent
                        thread_id = self.get_thread_by_agent(main_agent.id) or 1

                        return {
                            "type": "step_complete",
                            "thread_id": thread_id,
                            "threadId": thread_id,  # For backwards compatibility
                            "source_line_number": getattr(
                                event, "source_line_number", 0
                            ),
                            "reason": "step",
                        }

                return {
                    "type": "step_complete",
                    "thread_id": 1,
                    "threadId": 1,
                    "source_line_number": getattr(event, "source_line_number", 0),
                    "reason": "step",
                }
            elif isinstance(event, ExecutionPausedEvent):
                # Update agent execution state when pausing
                if (
                    self._program
                    and hasattr(self._program, "agents")
                    and self._program.agents
                ):
                    # For now, update the first agent's state (main agent)
                    # In a true multi-agent system, we'd need to identify which agent paused
                    main_agent = self._program.agents[0]
                    if main_agent and main_agent.id in self._agents:
                        self.update_agent_from_program_state(main_agent.id)

                return {
                    "type": "execution_paused",
                    "reason": getattr(event, "reason", "pause"),
                    "source_line_number": getattr(event, "source_line_number", 0),
                    "step": getattr(event, "step", ""),
                }
            elif isinstance(event, PlaybookEndEvent):
                return {
                    "type": "playbook_end",
                    "call_stack_depth": getattr(event, "call_stack_depth", 0),
                }
            elif isinstance(event, PlaybookStartEvent):
                return {
                    "type": "playbook_start",
                }
            elif isinstance(event, VariableUpdateEvent):
                return {
                    "type": "variable_update",
                    "variable_name": getattr(event, "variable_name", ""),
                    "variable_value": getattr(event, "variable_value", None),
                }
            elif isinstance(event, LineExecutedEvent):
                # Update agent execution state when a line is executed
                if (
                    self._program
                    and hasattr(self._program, "agents")
                    and self._program.agents
                ):
                    main_agent = self._program.agents[0]
                    if main_agent and main_agent.id in self._agents:
                        self.update_agent_from_program_state(main_agent.id)

                # Get the file path from the program if available
                file_path = ""
                if (
                    self._program
                    and hasattr(self._program, "program_paths")
                    and self._program.program_paths
                ):
                    # Use the first program path as the primary file
                    file_path = self._program.program_paths[0]

                return {
                    "type": "line_executed",
                    "file_path": file_path,
                    "line_number": getattr(event, "source_line_number", 0),
                }
            elif isinstance(event, ProgramTerminatedEvent):
                return {
                    "type": "program_terminated",
                    "reason": getattr(event, "reason", "normal"),
                    "exit_code": getattr(event, "exit_code", 0),
                }
            elif isinstance(event, AgentStartedEvent):
                return {
                    "type": "agent_started",
                    "agent_id": getattr(event, "agent_id", ""),
                    "agent_name": getattr(event, "agent_name", ""),
                    "thread_id": getattr(event, "thread_id", 1),
                    "agent_type": getattr(event, "agent_type", ""),
                }
            elif isinstance(event, AgentStoppedEvent):
                return {
                    "type": "agent_stopped",
                    "agent_id": getattr(event, "agent_id", ""),
                    "agent_name": getattr(event, "agent_name", ""),
                    "thread_id": getattr(event, "thread_id", 1),
                    "reason": getattr(event, "reason", "normal"),
                }
            elif isinstance(event, AgentPausedEvent):
                return {
                    "type": "agent_paused",
                    "agent_id": getattr(event, "agent_id", ""),
                    "agent_name": getattr(event, "agent_name", ""),
                    "thread_id": getattr(event, "thread_id", 1),
                    "reason": getattr(event, "reason", "pause"),
                    "source_line_number": getattr(event, "source_line_number", 0),
                }
            elif isinstance(event, AgentResumedEvent):
                return {
                    "type": "agent_resumed",
                    "agent_id": getattr(event, "agent_id", ""),
                    "agent_name": getattr(event, "agent_name", ""),
                    "thread_id": getattr(event, "thread_id", 1),
                }
            elif isinstance(event, AgentVariableUpdateEvent):
                return {
                    "type": "agent_variable_update",
                    "agent_id": getattr(event, "agent_id", ""),
                    "thread_id": getattr(event, "thread_id", 1),
                    "variable_name": getattr(event, "variable_name", ""),
                    "variable_value": getattr(event, "variable_value", None),
                }

        return None

    async def _broadcast_event(self, event_data: Dict[str, Any]) -> None:
        """Broadcast an event to all connected clients."""
        if not self.clients:
            return

        #     f"[DEBUG] Broadcasting event to {len(self.clients)} clients: {event_data}"
        # )
        message = json.dumps(event_data) + "\n"

        # Send to all clients
        disconnected_clients = []
        for client in self.clients:
            try:
                client.write(message.encode())
                await client.drain()
                #     f"[DEBUG] Successfully sent event to client: {event_data['type']}"
                # )
            except (ConnectionResetError, BrokenPipeError, OSError):
                # msg = f"Client disconnected while sending event: {e}"
                disconnected_clients.append(client)
            except Exception as e:
                self.logger.warning(f"Failed to send event to client: {e}")
                disconnected_clients.append(client)

        # Remove disconnected clients
        for client in disconnected_clients:
            if client in self.clients:
                self.clients.remove(client)

    def diagnose_frame_structure(self) -> str:
        """Diagnose the current frame structure for debugging."""
        try:
            if not self._program:
                return "No program attached"

            if not hasattr(self._program, "agents") or not self._program.agents:
                return "No agents in program"

            agent = self._program.agents[0]
            if not hasattr(agent, "state"):
                return "Agent has no state"

            if not hasattr(agent.state, "call_stack"):
                return "Agent state has no call_stack"

            frame = agent.state.call_stack.peek()
            if not frame:
                return "Call stack is empty"

            frame_info = {
                "frame_type": type(frame).__name__,
                "has_instruction_pointer": hasattr(frame, "instruction_pointer"),
                "instruction_pointer_type": (
                    type(frame.instruction_pointer).__name__
                    if hasattr(frame, "instruction_pointer")
                    else "None"
                ),
                "frame_attrs": [
                    attr for attr in dir(frame) if not attr.startswith("_")
                ],
            }

            if hasattr(frame, "instruction_pointer") and frame.instruction_pointer:
                ip = frame.instruction_pointer
                frame_info["ip_attrs"] = [
                    attr for attr in dir(ip) if not attr.startswith("_")
                ]
                frame_info["has_playbook"] = hasattr(ip, "playbook")
                frame_info["has_source_line_number"] = hasattr(ip, "source_line_number")
                frame_info["has_to_dict"] = hasattr(ip, "to_dict")

            return f"Frame structure: {frame_info}"
        except Exception as e:
            return f"Error diagnosing frame: {e}"

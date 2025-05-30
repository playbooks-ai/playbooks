"""
Debug server for Playbooks.

This module provides a debug server that can be embedded in playbook execution
to provide debugging capabilities through a simple TCP protocol.
"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from ..event_bus import EventBus
from ..events import (
    BreakpointHitEvent,
    ExecutionPausedEvent,
    LineExecutedEvent,
    PlaybookEndEvent,
    PlaybookStartEvent,
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
        self._event_bus = bus
        if bus:
            # Register for all events that might be relevant for debugging
            bus.subscribe("*", self._on_event)
            self.logger.info("Debug server registered with event bus")

    def set_stop_on_entry(self, stop_on_entry: bool) -> None:
        """Set whether to stop on entry."""
        self._stop_on_entry = stop_on_entry
        # print(f"[DEBUG] DebugServer.set_stop_on_entry called with: {stop_on_entry}")
        self.logger.info(f"Stop on entry set to: {stop_on_entry}")

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

    async def shutdown(self) -> None:
        """Shutdown the debug server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.logger.info("Debug server shutdown")

        # Close all client connections
        for client in self.clients:
            client.close()
            await client.wait_closed()
        self.clients.clear()

    async def wait_for_client(self) -> None:
        """Wait for at least one client to connect."""
        while not self.clients:
            await asyncio.sleep(0.1)
        self.logger.info("Debug client connected")

    async def wait_for_continue(self) -> None:
        """Wait for a continue command from the debug client."""
        self._continue_event.clear()
        await self._continue_event.wait()

    def should_pause_for_step(self, current_frame: Dict[str, Any]) -> bool:
        """Check if execution should pause based on step mode."""
        try:
            if not self._step_mode or not current_frame:
                return False

            # print(f"Step mode: {self._step_mode}")
            # print(f"Current frame: {current_frame}")
            # print(f"Initial frame: {self._step_initial_frame}")

            if self._step_mode == "step_in":
                # Always pause on next instruction
                # print("Step in: pausing on next instruction")
                return True

            elif self._step_mode == "next":
                # For step over, we should pause when:
                # 1. We're in the same frame but on a different line
                # 2. We've returned to the caller frame

                if self._is_same_frame(current_frame, self._step_initial_frame):
                    # Check if we've moved to a different line
                    current_line = current_frame.get("line_number", 0)
                    initial_line = self._step_initial_frame.get("line_number", 0)

                    if current_line != initial_line:
                        # print(
                        #     f"Step over: same frame, different line ({initial_line} -> {current_line}), pausing"
                        # )
                        return True
                    else:
                        # print(
                        #     f"Step over: same frame, same line ({current_line}), continuing"
                        # )
                        return False

                # Also pause if we've returned to a shallower frame
                if self._is_caller_frame(current_frame, self._step_initial_frame):
                    # print("Step over: returned to caller, pausing")
                    return True

                # print("Step over: different frame, continuing")
                return False

            elif self._step_mode == "step_out":
                # Only pause when we've returned to the caller frame
                should_pause = self._is_caller_frame(
                    current_frame, self._step_initial_frame
                )
                # print(f"Step out: should pause = {should_pause}")
                return should_pause

            return False
        except Exception as e:
            self.logger.error(f"Error in should_pause_for_step: {e}")
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
        self.clients.append(writer)
        client_addr = writer.get_extra_info("peername")
        self.logger.info(f"Debug client connected from {client_addr}")

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                command_str = data.decode().strip()
                if command_str:
                    await self._handle_command(command_str, writer)

        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            print(e)
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
                # print(f"Error closing client connection: {e}")
                pass
            self.logger.info(f"Debug client {client_addr} disconnected")

    async def _handle_command(
        self, command_str: str, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming commands from debug clients."""
        try:
            command = json.loads(command_str)
            command_type = command.get("command")

            # print(f"Processing command: {command_type}")

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
            else:
                msg = f"Unknown command: {command_type}"
                await self._send_error(writer, msg)

        except (json.JSONDecodeError, KeyError) as e:
            error_msg = f"Invalid command format: {e}"
            self.logger.error(error_msg)
            await self._send_error(writer, error_msg)
        except Exception as e:
            error_msg = f"Error processing command '{command_str}': {e}"
            self.logger.error(error_msg)
            await self._send_error(writer, error_msg)

    async def _handle_set_breakpoints(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle set_breakpoints command."""
        file_path = command.get("file", "")
        lines = set(command.get("lines", []))
        self._breakpoints[file_path] = lines

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
        self.clear_step_mode()  # Only clear on continue
        self._continue_event.set()

        response = {"type": "response", "command": "continue", "success": True}
        await self._send_response(writer, response)

    async def _handle_next(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle next (step over) command."""
        try:
            self.logger.info("Handling 'next' command")
            # print("[DEBUG] DebugServer._handle_next - entering next command handler")

            # Diagnose frame structure
            diagnosis = self.diagnose_frame_structure()
            self.logger.info(f"Frame diagnosis: {diagnosis}")

            self._step_mode = "next"
            self._step_initial_frame = self._get_current_frame()

            self.logger.info(f"Initial frame captured: {self._step_initial_frame}")
            # print(
            #     f"[DEBUG] DebugServer._handle_next - set step_mode=next, initial_frame={self._step_initial_frame}"
            # )

            # Trigger the continue event to release any wait_for_continue()
            self._continue_event.set()
            # print("[DEBUG] DebugServer._handle_next - triggered continue event")

            response = {"type": "response", "command": "next", "success": True}
            await self._send_response(writer, response)
            self.logger.info("Successfully sent 'next' response")
            # print("[DEBUG] DebugServer._handle_next - sent response")

        except Exception as e:
            self.logger.error(f"Error in _handle_next: {e}")
            # print(f"[DEBUG] DebugServer._handle_next - error: {e}")
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
        # print("[DEBUG] DebugServer._handle_step_in - entering step_in command handler")
        self._step_mode = "step_in"
        self._step_initial_frame = self._get_current_frame()

        # Trigger the continue event to release any wait_for_continue()
        self._continue_event.set()
        # print("[DEBUG] DebugServer._handle_step_in - triggered continue event")

        response = {"type": "response", "command": "step_in", "success": True}
        await self._send_response(writer, response)

    async def _handle_step_out(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle step_out command."""
        # print(
        #     "[DEBUG] DebugServer._handle_step_out - entering step_out command handler"
        # )
        self._step_mode = "step_out"
        self._step_initial_frame = self._get_current_frame()

        # Trigger the continue event to release any wait_for_continue()
        self._continue_event.set()
        # print("[DEBUG] DebugServer._handle_step_out - triggered continue event")

        response = {"type": "response", "command": "step_out", "success": True}
        await self._send_response(writer, response)

    async def _handle_get_compiled_program(
        self, command: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        """Handle get_compiled_program command."""
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
        variables = self._get_current_variables()
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
        call_stack = self._get_current_call_stack()
        response = {
            "type": "call_stack_response",
            "success": True,
            "call_stack": list(reversed(call_stack)),
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
            # print(msg)
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

    def should_pause_at_line(self, source_line_number: int) -> bool:
        """Check if execution should pause at the given file and line."""
        return source_line_number in self._breakpoints

    def has_breakpoint(self, source_line_number: int) -> bool:
        """Check if there's a breakpoint for the given step or location."""
        return self.should_pause_at_line(source_line_number)

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
        # Convert event to JSON and broadcast to all clients
        try:
            event_data = self._event_to_dict(event)
            if event_data:
                asyncio.create_task(self._broadcast_event(event_data))
        except Exception as e:
            self.logger.error(f"Error handling event: {e}")

    def _event_to_dict(self, event: Any) -> Optional[Dict[str, Any]]:
        """Convert an event object to a dictionary for JSON serialization."""
        if hasattr(event, "__class__"):
            # Map specific event types to debug protocol events
            if isinstance(event, BreakpointHitEvent):
                return {
                    "type": "breakpoint_hit",
                    "file_path": getattr(event, "file_path", ""),
                    "line_number": getattr(event, "line_number", 0),
                }
            elif isinstance(event, StepCompleteEvent):
                return {
                    "type": "step_complete",
                }
            elif isinstance(event, ExecutionPausedEvent):
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

        return None

    async def _broadcast_event(self, event_data: Dict[str, Any]) -> None:
        """Broadcast an event to all connected clients."""
        if not self.clients:
            # print(f"[DEBUG] No clients connected, not broadcasting event: {event_data}")
            return

        # print(
        #     f"[DEBUG] Broadcasting event to {len(self.clients)} clients: {event_data}"
        # )
        message = json.dumps(event_data) + "\n"

        # Send to all clients
        disconnected_clients = []
        for client in self.clients:
            try:
                client.write(message.encode())
                await client.drain()
                # print(
                #     f"[DEBUG] Successfully sent event to client: {event_data['type']}"
                # )
            except (ConnectionResetError, BrokenPipeError, OSError):
                # msg = f"Client disconnected while sending event: {e}"
                # print(msg)
                # print(f"[DEBUG] Client disconnected while sending event: {e}")
                disconnected_clients.append(client)
            except Exception as e:
                self.logger.warning(f"Failed to send event to client: {e}")
                # print(f"[DEBUG] Failed to send event to client: {e}")
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

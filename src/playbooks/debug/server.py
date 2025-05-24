import asyncio
import json
from dataclasses import asdict
from typing import Any, Dict, List, Set

from ..event_bus import EventBus


class DebugServer:
    """Lightweight server that streams debug events to clients and handles debug commands."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7529) -> None:
        self.host = host
        self.port = port
        self.clients: List[asyncio.StreamWriter] = []
        self._server: asyncio.AbstractServer | None = None
        self._buses: Dict[str, EventBus] = {}  # Track buses by session ID
        self._client_connected_event = asyncio.Event()
        self._breakpoints: Dict[str, Set[int]] = {}  # file_path -> set of line numbers
        self._continue_event = (
            asyncio.Event()
        )  # Event to control execution continuation
        self._is_paused = False
        self._program = None  # Store reference to the program

    def set_program(self, program) -> None:
        """Store a reference to the program for debug operations.

        Args:
            program: The Program instance
        """
        self._program = program

    def register_bus(self, bus: EventBus) -> None:
        """Register an event bus to listen for its events.

        Args:
            bus: The event bus to subscribe to
        """
        if bus.session_id not in self._buses:
            self._buses[bus.session_id] = bus
            # Subscribe to all event types
            from ..events import (
                BreakpointHitEvent,
                CallStackPopEvent,
                CallStackPushEvent,
                CompiledProgramEvent,
                InstructionPointerEvent,
                LineExecutedEvent,
                PlaybookEndEvent,
                PlaybookStartEvent,
                VariableUpdateEvent,
            )

            for event_type in [
                BreakpointHitEvent,
                CallStackPushEvent,
                CallStackPopEvent,
                InstructionPointerEvent,
                VariableUpdateEvent,
                PlaybookStartEvent,
                PlaybookEndEvent,
                LineExecutedEvent,
                CompiledProgramEvent,
            ]:
                bus.subscribe(event_type, self._on_event)

    async def start(self) -> None:
        """Start the debug server."""
        if self._server:
            return
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        asyncio.create_task(self._server.serve_forever())

    async def wait_for_client(self) -> None:
        """Wait until at least one client is connected.

        This method blocks until a client connects to the debug server.
        If a client is already connected when this method is called, it returns immediately.
        """
        if not self.clients:
            # Reset the event if no clients are connected
            self._client_connected_event.clear()
            # Wait for the event to be set when a client connects
            await self._client_connected_event.wait()

    async def wait_for_continue(self) -> None:
        """Wait until execution should continue.

        This method pauses execution until a continue command is received from a debug client.
        """
        self._is_paused = True
        self._continue_event.clear()
        await self._continue_event.wait()
        self._is_paused = False

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.clients.append(writer)
        # Set the event to notify anyone waiting for a client connection
        self._client_connected_event.set()
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if line:
                    await self._handle_command(line.decode().strip(), writer)
        finally:
            self.clients.remove(writer)
            writer.close()
            await writer.wait_closed()
            # Clear the event if there are no more clients
            if not self.clients:
                self._client_connected_event.clear()

    async def _handle_command(
        self, command_str: str, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming commands from debug clients.

        Args:
            command_str: JSON-encoded command string
            writer: The client writer that sent the command
        """
        try:
            command = json.loads(command_str)
            command_type = command.get("command")

            if command_type == "set_breakpoints":
                file_path = command.get("file", "")
                lines = set(command.get("lines", []))
                self._breakpoints[file_path] = lines

                # Send acknowledgment back to client
                response = {
                    "type": "response",
                    "command": "set_breakpoints",
                    "success": True,
                    "file": file_path,
                    "lines": list(lines),
                }
                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()

            elif command_type == "continue":
                # Resume execution
                self._continue_event.set()

                # Send acknowledgment back to client
                response = {"type": "response", "command": "continue", "success": True}
                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()

            elif command_type == "get_compiled_program":
                # Send the compiled program content to the client
                if self._program:
                    compiled_file_path = self._program._get_compiled_file_name()
                    response = {
                        "type": "compiled_program_response",
                        "success": True,
                        "compiled_file": compiled_file_path,
                        "content": self._program.full_program,
                        "original_files": self._program.program_paths,
                    }
                else:
                    response = {
                        "type": "compiled_program_response",
                        "success": False,
                        "error": "No program available",
                    }

                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()

        except (json.JSONDecodeError, KeyError) as e:
            # Send error response
            error_response = {"type": "error", "message": f"Invalid command: {e}"}
            writer.write((json.dumps(error_response) + "\n").encode())
            await writer.drain()

    def should_pause_at_line(self, file_path: str, line_number: int) -> bool:
        """Check if execution should pause at the given file and line.

        Args:
            file_path: The file being executed
            line_number: The line number being executed

        Returns:
            True if there's a breakpoint at this location
        """
        file_breakpoints = self._breakpoints.get(file_path, set())
        return line_number in file_breakpoints

    def has_breakpoint(
        self, step: str = None, file_path: str = None, line_number: int = None
    ) -> bool:
        """Check if there's a breakpoint for the given step or location.

        Args:
            step: The step identifier (optional)
            file_path: The file path (optional)
            line_number: The line number (optional)

        Returns:
            True if there's a breakpoint at this location/step
        """
        if file_path and line_number:
            return self.should_pause_at_line(file_path, line_number)

        # For step-based breakpoints, we can check if any breakpoints exist
        # This is a simplified implementation - in a real system you might
        # want to map steps to specific file/line combinations
        if step:
            # For now, return True if there are any breakpoints set
            # This allows basic debugging functionality
            return any(
                len(breakpoints) > 0 for breakpoints in self._breakpoints.values()
            )

        return False

    def get_breakpoints(self, file_path: str = None) -> Dict[str, Set[int]]:
        """Get all breakpoints or breakpoints for a specific file.

        Args:
            file_path: Optional file path to get breakpoints for

        Returns:
            Dictionary of file paths to sets of line numbers
        """
        if file_path:
            return {file_path: self._breakpoints.get(file_path, set())}
        return self._breakpoints.copy()

    def _on_event(self, event: Any) -> None:
        """Handle an event by sending it to all connected clients.

        The event is converted to a dictionary and JSON-encoded before sending.

        Args:
            event: The event object from the EventBus
        """
        # Convert dataclass to dict
        event_dict = asdict(event)
        # Add the event type for debugging
        event_dict["__event_type__"] = event.__class__.__name__

        data = json.dumps(event_dict).encode() + b"\n"
        for writer in list(self.clients):
            try:
                writer.write(data)
            except Exception:
                pass

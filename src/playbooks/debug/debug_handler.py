"""Clean debug handler that integrates with the new architecture."""

import asyncio
import logging
from typing import TYPE_CHECKING, Dict, Optional

from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.state.call_stack import InstructionPointer

from .server import DebugServer

# Constants
POLLING_INTERVAL = 0.01  # Seconds for global continue polling

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DebugHandler:
    """Clean debug handler that works with the new multi-agent architecture."""

    def __init__(self, debug_server: DebugServer):
        self.debug_server = debug_server
        # Track continue events for each agent
        self._continue_events: Dict[str, asyncio.Event] = {}
        # Track step events for each agent
        self._step_events: Dict[str, asyncio.Event] = {}
        self._step_modes: Dict[str, str] = {}  # agent_id -> step_mode

    async def pause_if_needed(
        self,
        instruction_pointer: InstructionPointer,
        agent_id: Optional[str] = None,
    ) -> None:
        """Handle pause operations.

        Checks for breakpoints, stop-on-entry, pause requests, and step modes.
        Pauses execution and waits for continue command if needed.

        Args:
            instruction_pointer: Current execution position
            agent_id: ID of the agent executing (optional)
        """
        should_pause = False
        reason = None

        # Check for breakpoints first - breakpoints are set on compiled files
        file_path = self.debug_server.compiled_file_path
        line_number = instruction_pointer.source_line_number

        debug(f"Agent {agent_id} pause if needed on step {instruction_pointer}")

        if (
            self.debug_server.get_stop_on_entry()
            and not self.debug_server.has_agent_stopped_on_entry(agent_id)
        ):
            should_pause = True
            reason = "stop on entry"
            self.debug_server.set_agent_stopped_on_entry(agent_id)

        # Check if we should pause due to pause request
        elif self.debug_server and self.debug_server.is_pause_requested(agent_id):
            should_pause = True
            reason = "pause requested"
            self.debug_server.clear_pause_request(agent_id)

        elif self._step_modes and agent_id in self._step_modes:
            self._step_modes.pop(agent_id)
            reason = "step"
            should_pause = True
            # TODO: if in step mode, check if same level, and if so, pause

        # Check if there's a breakpoint at this location
        elif await self.debug_server.check_breakpoint(agent_id, file_path, line_number):
            # Breakpoint was hit - check_breakpoint already sent the stopped event
            # await self._wait_for_continue(agent_id)
            # return  # Return early since breakpoint handling is complete
            should_pause = True
            reason = "breakpoint"

        debug(f"Agent {agent_id} should pause: {should_pause}, reason: {reason}")
        if should_pause:
            logger.debug(f"Pausing execution for agent {agent_id}")
            self.debug_server.program.agents_by_id[agent_id].paused = {
                "reason": reason,
                "instruction_pointer": instruction_pointer,
            }
            self.debug_server.clear_pause_request(agent_id)
            # Set global state to stop all threads
            # self.debug_server.set_all_threads_stopped(True)
            await self.refresh_stopped_status(agent_id)

            await self._wait_for_continue(agent_id)
            await self.debug_server._send_message(
                {
                    "type": "event",
                    "event": "continued",
                    "body": {
                        "threadId": self.debug_server.agent_id_to_thread_id(agent_id),
                        "allThreadsContinued": False,
                    },
                }
            )
            self.debug_server.program.agents_by_id[agent_id].paused = None

    async def refresh_stopped_status(self, agent_id_to_focus: str):
        messages = []
        for agent in self.debug_server.program.agents:
            a_id = agent.id
            if agent.paused is not None:
                reason = agent.paused["reason"]
                instruction_pointer = agent.paused["instruction_pointer"]
                message = {
                    "type": "event",
                    "event": "stopped",
                    "body": {
                        "reason": reason,
                        "threadId": self.debug_server.agent_id_to_thread_id(a_id),
                        "allThreadsStopped": False,
                        "description": "Paused",
                        "lineNumber": instruction_pointer.line_number,
                        "playbook": instruction_pointer.playbook,
                        "sourceLineNumber": instruction_pointer.source_line_number,
                        "filePath": str(instruction_pointer.source_file_path),
                    },
                }

                # Keep the agent that paused at the end, so VSCode focuses back on it
                if a_id == agent_id_to_focus:
                    messages.append(message)
                else:
                    messages.insert(0, message)

        for message in messages:
            await self.debug_server._send_message(message)

    def reset_for_execution(self):
        """Reset state for new execution."""
        # self._is_first_iteration = True
        # Don't reset _has_stopped_on_entry - we only want to stop on entry once per debug session

    async def handle_execution_start(
        self,
        _instruction_pointer: InstructionPointer,
        _next_instruction_pointer: InstructionPointer,
        _event_bus,
        _agent_id: str = None,
    ):
        """Handle execution start operations."""
        pass

    async def handle_step(self, agent_id: str, step_mode: str, request_seq: int):
        # Acknowledgement that the step command has been received
        await self.debug_server._send_message(
            {
                "type": "response",
                "command": step_mode,
                "request_seq": request_seq,
                "success": True,
                "body": {
                    "threadId": agent_id,
                    "allThreadsStopped": False,
                },
            }
        )

        logger.debug(f"Signaling step for agent {agent_id}, mode: {step_mode}")

        # Store step mode for this agent
        self._step_modes[agent_id] = step_mode

        # Continue the agent. pause_if_needed will be called by the agent on the next step and execution will stop.
        self._continue_events[agent_id].set()

    async def handle_breakpoint(
        self,
        source_line_number: int,
        instruction_pointer: InstructionPointer,
        next_instruction_pointer: InstructionPointer,
        event_bus,
        agent_id: str = None,
    ):
        pass

    async def handle_execution_end(self):
        """Handle execution end cleanup."""
        # No specific cleanup needed for clean architecture
        pass

    def _should_stop_on_entry(self) -> bool:
        """Check if should stop on entry."""
        # Check if the debug server has stop-on-entry enabled
        return self.debug_server.stop_on_entry

    def signal_continue(self, agent_id: str):
        """Signal that an agent should continue execution."""
        if not agent_id:
            agent_id = "default"

        logger.debug(f"Signaling continue for agent {agent_id}")

        # Create an event for this agent if it doesn't exist
        if agent_id not in self._continue_events:
            self._continue_events[agent_id] = asyncio.Event()

        # Set the event for this agent
        self._continue_events[agent_id].set()

    async def _wait_for_continue(self, agent_id: str):
        """Wait for continue command from debugger."""
        if not agent_id:
            agent_id = "default"

        logger.debug(f"Waiting for continue signal for agent {agent_id}")

        # Create an event for this agent if it doesn't exist
        if agent_id not in self._continue_events:
            self._continue_events[agent_id] = asyncio.Event()

        # Clear the event and wait for it to be set
        self._continue_events[agent_id].clear()
        await self._continue_events[agent_id].wait()
        logger.debug(f"Continue signal received for agent {agent_id}")


class NoOpDebugHandler(DebugHandler):
    """No-op implementation for when debugging is disabled."""

    def __init__(self):
        super().__init__(None)

    async def handle_execution_start(
        self,
        instruction_pointer: InstructionPointer,
        next_instruction_pointer: InstructionPointer,
        event_bus,
        agent_id: str = None,
    ):
        pass

    async def handle_step(self, agent_id: str, step_mode: str, request_seq: int):
        pass

    async def handle_breakpoint(
        self,
        source_line_number: int,
        instruction_pointer: InstructionPointer,
        next_instruction_pointer: InstructionPointer,
        event_bus,
        agent_id: str = None,
    ):
        pass

    async def handle_execution_end(self):
        pass

    async def pause_if_needed(
        self,
        instruction_pointer: InstructionPointer,
        agent_id: str = None,
    ):
        pass

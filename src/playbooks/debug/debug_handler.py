from typing import TYPE_CHECKING

from playbooks.call_stack import InstructionPointer
from playbooks.events import BreakpointHitEvent, ExecutionPausedEvent, StepCompleteEvent

if TYPE_CHECKING:
    from playbooks.debug.server import DebugServer


class DebugHandler:
    """Handles all debug-related operations during playbook execution."""

    def __init__(self, debug_server: "DebugServer"):
        self.debug_server = debug_server
        self._is_first_iteration = True

    def reset_for_execution(self):
        """Reset state for a new execution."""
        # self._is_first_iteration = True
        pass

    async def handle_execution_start(
        self,
        instruction_pointer: InstructionPointer,
        next_instruction_pointer: InstructionPointer,
        event_bus,
        agent_id: str = None,
    ):
        # print(f"[DEBUG_HANDLER] handle_execution_start: {instruction_pointer}")

        # print(f"[DEBUG_HANDLER] is_first_iteration: {self._is_first_iteration}")
        """Handle debug operations at the start of execution loop iteration."""
        if self._is_first_iteration:
            # Handle stop-on-entry
            print(
                f"[DEBUG_HANDLER] should_stop_on_entry: {self.debug_server.should_stop_on_entry()}"
            )
            if self.debug_server.should_stop_on_entry():
                # Get thread_id for the agent if available
                thread_id = None
                if agent_id and self.debug_server:
                    thread_id = self.debug_server._agent_to_thread.get(agent_id, 1)

                # Only send the execution paused event if we're actually stopping
                event_bus.publish(
                    ExecutionPausedEvent(
                        reason="entry",
                        source_line_number=instruction_pointer.source_line_number,
                        step=str(instruction_pointer),
                        thread_id=thread_id,
                    )
                )

                self.debug_server._stop_on_entry = False
                # print("[DEBUG_HANDLER] waiting for continue")
                if agent_id:
                    await self.debug_server.wait_for_continue_agent(agent_id)
                else:
                    await self.debug_server.wait_for_continue()

            self._is_first_iteration = False
            await self.handle_step(
                instruction_pointer, next_instruction_pointer, event_bus, agent_id
            )

    async def handle_step(
        self,
        instruction_pointer: InstructionPointer,
        next_instruction_pointer: InstructionPointer,
        event_bus,
        agent_id: str = None,
    ):
        # Always check for stepping (not just when not first iteration)
        # This ensures we pause BEFORE the LLM call that will execute the next line
        debug_frame = self.debug_server._get_current_frame()

        # Use agent-aware stepping if agent_id is provided
        if agent_id:
            should_pause = self.debug_server.should_pause_for_step_agent(
                agent_id, debug_frame
            )
        else:
            should_pause = self.debug_server.should_pause_for_step(debug_frame)

        print(f"[DEBUG_HANDLER] agent_id: {agent_id}")
        print(f"[DEBUG_HANDLER] debug_frame: {debug_frame}")
        print(f"[DEBUG_HANDLER] should_pause_for_step: {should_pause}")

        if should_pause:
            source_line_number = instruction_pointer.source_line_number

            # Get thread_id for the agent if available
            thread_id = None
            if agent_id and self.debug_server:
                thread_id = self.debug_server._agent_to_thread.get(agent_id, 1)

            event_bus.publish(
                StepCompleteEvent(
                    source_line_number=source_line_number, thread_id=thread_id
                )
            )
            print("[DEBUG_HANDLER] waiting for step")

            event_bus.publish(
                ExecutionPausedEvent(
                    reason="entry",
                    source_line_number=next_instruction_pointer.source_line_number,
                    step=str(next_instruction_pointer),
                    thread_id=thread_id,
                )
            )

            # Use agent-aware continue if agent_id is provided
            if agent_id:
                await self.debug_server.wait_for_continue_agent(agent_id)
            else:
                await self.debug_server.wait_for_continue()
            print("[DEBUG_HANDLER] DONE waiting for step")

    async def handle_breakpoint(
        self,
        source_line_number,
        instruction_pointer: InstructionPointer,
        next_instruction_pointer: InstructionPointer,
        event_bus,
        agent_id: str = None,
    ):
        print(
            f"[DEBUG_HANDLER] handle_breakpoint: line {source_line_number} for agent {agent_id}"
        )

        # Get both original and compiled file paths from the debug server's program
        original_file_path = None
        compiled_file_path = None

        if self.debug_server._program:
            # Original file path
            if (
                hasattr(self.debug_server._program, "program_paths")
                and self.debug_server._program.program_paths
            ):
                original_file_path = self.debug_server._program.program_paths[0]

            # Compiled file path (get the full path that matches what VSCode sends)
            if hasattr(self.debug_server._program, "_get_compiled_file_name"):
                compiled_file_name = (
                    self.debug_server._program._get_compiled_file_name()
                )
                if original_file_path and compiled_file_name:
                    from pathlib import Path

                    original_path = Path(original_file_path)
                    compiled_file_path = str(
                        original_path.parent / ".pbasm_cache" / compiled_file_name
                    )

        print(
            f"[DEBUG_HANDLER] checking breakpoints for original: {original_file_path}"
        )
        print(
            f"[DEBUG_HANDLER] checking breakpoints for compiled: {compiled_file_path}"
        )

        # Check breakpoints for both file paths
        has_breakpoint = self.debug_server.has_breakpoint(
            source_line_number=source_line_number, file_path=original_file_path
        ) or self.debug_server.has_breakpoint(
            source_line_number=source_line_number, file_path=compiled_file_path
        )

        print(f"[DEBUG_HANDLER] has_breakpoint: {has_breakpoint}")

        """Check and handle breakpoint at the given line."""
        if has_breakpoint:
            # Get thread_id for the agent if available
            thread_id = None
            if agent_id and self.debug_server:
                thread_id = self.debug_server._agent_to_thread.get(agent_id, 1)

            event_bus.publish(
                BreakpointHitEvent(
                    source_line_number=source_line_number, thread_id=thread_id
                )
            )
            print("[DEBUG_HANDLER] waiting for continue")

            # Use agent-aware continue if agent_id is provided
            if agent_id:
                await self.debug_server.wait_for_continue_agent(agent_id)
            else:
                await self.debug_server.wait_for_continue()
        else:
            print(f"[DEBUG_HANDLER] no breakpoint at {source_line_number}")
            await self.handle_step(
                instruction_pointer, next_instruction_pointer, event_bus, agent_id
            )

    async def handle_execution_end(self):
        """Handle any cleanup needed at execution end."""
        # Note: This should NOT signal program termination!
        # Playbook execution ending is just like a function returning.
        # Program termination should only happen on ExecutionFinished event.
        pass


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

    async def handle_breakpoint(
        self,
        source_line_number,
        instruction_pointer: InstructionPointer,
        next_instruction_pointer: InstructionPointer,
        event_bus,
        agent_id: str = None,
    ):
        pass

    async def handle_execution_end(self):
        pass

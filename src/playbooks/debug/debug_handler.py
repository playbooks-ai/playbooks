import asyncio
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
    ):
        # print(f"[DEBUG_HANDLER] handle_execution_start: {instruction_pointer}")

        # print(f"[DEBUG_HANDLER] is_first_iteration: {self._is_first_iteration}")
        """Handle debug operations at the start of execution loop iteration."""
        if self._is_first_iteration:
            event_bus.publish(
                ExecutionPausedEvent(
                    reason="entry",
                    source_line_number=instruction_pointer.source_line_number,
                    step=str(instruction_pointer),
                )
            )

            # Handle stop-on-entry
            # print(
            #     f"[DEBUG_HANDLER] should_stop_on_entry: {self.debug_server.should_stop_on_entry()}"
            # )
            if self.debug_server.should_stop_on_entry():
                self.debug_server._stop_on_entry = False
                # print("[DEBUG_HANDLER] waiting for continue")
                await self.debug_server.wait_for_continue()

            self._is_first_iteration = False

        # Always check for stepping (not just when not first iteration)
        # This ensures we pause BEFORE the LLM call that will execute the next line
        debug_frame = self.debug_server._get_current_frame()
        # print(f"[DEBUG_HANDLER] debug_frame: {debug_frame}")
        # print(
        #     f"[DEBUG_HANDLER] should_pause_for_step: {self.debug_server.should_pause_for_step(debug_frame)}"
        # )
        if self.debug_server.should_pause_for_step(debug_frame):
            source_line_number = instruction_pointer.source_line_number
            event_bus.publish(StepCompleteEvent(source_line_number=source_line_number))
            # print("[DEBUG_HANDLER] waiting for step")

            event_bus.publish(
                ExecutionPausedEvent(
                    reason="entry",
                    source_line_number=next_instruction_pointer.source_line_number,
                    step=str(next_instruction_pointer),
                )
            )

            await self.debug_server.wait_for_continue()
            # print("[DEBUG_HANDLER] DONE waiting for step")

    async def handle_breakpoint(self, source_line_number, event_bus):
        # print(f"[DEBUG_HANDLER] handle_breakpoint: {source_line_number}")
        # print(
        #     f"[DEBUG_HANDLER] has_breakpoint: {self.debug_server.has_breakpoint(source_line_number=source_line_number)}"
        # )
        """Check and handle breakpoint at the given line."""
        if self.debug_server.has_breakpoint(source_line_number=source_line_number):
            event_bus.publish(BreakpointHitEvent(source_line_number=source_line_number))
            # print("[DEBUG_HANDLER] waiting for continue")
            await self.debug_server.wait_for_continue()

    async def handle_execution_end(self):
        """Handle any cleanup needed at execution end."""
        if self.debug_server:
            # Give a moment for events to be processed
            # print("[DEBUG_HANDLER] waiting for execution end")
            await asyncio.sleep(0.01)


class NoOpDebugHandler(DebugHandler):
    """No-op implementation for when debugging is disabled."""

    def __init__(self):
        super().__init__(None)

    async def handle_execution_start(
        self,
        instruction_pointer: InstructionPointer,
        next_instruction_pointer: InstructionPointer,
        event_bus,
    ):
        pass

    async def handle_breakpoint(self, source_line_number, event_bus):
        pass

    async def handle_execution_end(self):
        pass

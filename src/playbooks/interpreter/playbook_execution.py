"""Playbook execution module for the interpreter."""

import contextlib
import time
from typing import TYPE_CHECKING, Dict, Generator

from playbooks.trace_mixin import TraceMixin
from playbooks.types import AgentResponseChunk

if TYPE_CHECKING:
    from playbooks.playbook import Playbook

    from .interpreter import Interpreter


class PlaybookExecution(TraceMixin):
    """Represents the execution of a playbook."""

    def __init__(
        self,
        interpreter: "Interpreter",
        playbooks: Dict[str, "Playbook"],
        current_playbook: "Playbook",
        instruction: str,
        llm_config=None,
        stream=False,
    ):
        """Initialize a playbook execution.

        Args:
            interpreter: The interpreter executing the playbook.
            playbooks: The available playbooks.
            current_playbook: The current playbook being executed.
            instruction: The instruction to execute.
            llm_config: The LLM configuration.
            stream: Whether to stream the response.
        """
        super().__init__()
        self.interpreter: "Interpreter" = interpreter
        self.playbooks = playbooks
        self.current_playbook = current_playbook
        self.instruction = instruction
        self.llm_config = llm_config
        self.stream = stream

        # Execution state
        self.should_exit = False
        self.exit_reason = None
        self.wait_for_external_event = False

        # Configuration
        self.max_iterations = 100
        self.max_execution_time = 60  # seconds

    def _compute_state_hash(self) -> int:
        """Compute a hash of the current execution state to detect lack of progress."""
        state = {
            "call_stack": str(self.interpreter.call_stack.to_dict()),
            "variables": str(self.interpreter.local_variables.to_dict()),
            "current_playbook": self.current_playbook.klass,
            "line_number": self.interpreter.get_current_line_number(),
        }
        return hash(str(state))

    @contextlib.contextmanager
    def execution_loop(self):
        """Context manager for execution loops with safety limits and exit condition checks."""
        iteration_count = 0
        start_time = time.time()
        last_state_hash = None
        consecutive_no_progress = 0

        # Reset state at the beginning of the loop
        self.should_exit = False
        self.exit_reason = None
        self.wait_for_external_event = False

        def should_continue():
            nonlocal iteration_count, last_state_hash, consecutive_no_progress

            # Increment iteration count
            iteration_count += 1

            # Check if an exit condition was triggered
            if self.should_exit:
                return False

            # Check iteration limits
            if iteration_count >= self.max_iterations:
                self.should_exit = True
                self.exit_reason = f"Maximum iterations ({self.max_iterations}) reached"
                return False

            # Check time limits
            if (time.time() - start_time) >= self.max_execution_time:
                self.should_exit = True
                self.exit_reason = (
                    f"Maximum execution time ({self.max_execution_time}s) reached"
                )
                return False

            # Check for lack of progress
            current_state_hash = self._compute_state_hash()
            if current_state_hash == last_state_hash:
                consecutive_no_progress += 1
                if consecutive_no_progress >= 3:
                    self.should_exit = True
                    self.exit_reason = "No progress detected after multiple iterations"
                    self.wait_for_external_event = True  # Force waiting for user input
                    return False
            else:
                consecutive_no_progress = 0
                last_state_hash = current_state_hash

            return True

        try:
            # This is what's returned by the with statement
            yield should_continue

        finally:
            # Cleanup code - runs when exiting the with block
            execution_time = time.time() - start_time
            self.trace(
                f"Loop completed after {iteration_count-1} iterations in {execution_time:.2f}s",
                metadata={
                    "exit_reason": self.exit_reason,
                    "wait_for_external_event": self.wait_for_external_event,
                },
            )

    def execute(self) -> Generator[AgentResponseChunk, None, None]:
        """Execute the playbook.

        Returns:
            A generator of agent response chunks.
        """

        with self.execution_loop() as should_continue:
            while should_continue():
                # Check if call stack is empty
                should_exit, exit_reason = self.interpreter.handle_empty_call_stack(
                    {"playbook": self.current_playbook.klass}
                )
                if should_exit:
                    self.should_exit = should_exit
                    self.exit_reason = exit_reason
                    break

                # Get the current frame (we know it exists because handle_empty_call_stack didn't exit)
                current_frame = self.interpreter.call_stack.peek()

                self.trace(
                    "Start playbook session iteration",
                    metadata={
                        "playbook": self.current_playbook.klass,
                        "line_number": current_frame.instruction_pointer.line_number,
                        "instruction": self.instruction,
                    },
                )
                # Import here to avoid circular imports
                from .interpreter_execution import InterpreterExecution

                interpreter_execution = InterpreterExecution(
                    interpreter=self.interpreter,
                    playbooks=self.playbooks,
                    current_playbook=self.current_playbook,
                    instruction=self.instruction,
                    llm_config=self.llm_config,
                    stream=self.stream,
                )
                self.trace(interpreter_execution)
                yield from interpreter_execution.execute()

                # Check if interpreter execution is waiting for external event
                if interpreter_execution.wait_for_external_event:
                    self.wait_for_external_event = True
                    self.should_exit = True
                    self.exit_reason = "Waiting for external event"
                    self.trace("Waiting for external event, exiting loop")

                # Check if call stack is empty after interpreter execution
                should_exit, exit_reason = self.interpreter.handle_empty_call_stack(
                    {"playbook": self.current_playbook.klass}
                )
                if should_exit:
                    self.should_exit = should_exit
                    self.exit_reason = exit_reason
                    break

                # Get the current frame (we know it exists because handle_empty_call_stack didn't exit)
                current_frame = self.interpreter.call_stack.peek()

                # Check if we need to switch to a new playbook
                current_playbook_in_stack = self.interpreter.get_current_playbook_name()
                if current_playbook_in_stack != self.current_playbook.klass:
                    self.should_exit = True
                    self.exit_reason = (
                        f"Switching to new playbook {current_playbook_in_stack}"
                    )
                    self.trace(
                        f"Switching to new playbook {current_playbook_in_stack}, exiting loop"
                    )
                    # Make sure we don't lose the current frame when switching playbooks
                    if current_playbook_in_stack is not None:
                        self.trace(
                            f"Ensuring call stack contains {current_playbook_in_stack}"
                        )
                        # The call stack should already contain the frame for the playbook we're switching to
                        # This is just a safety check to make sure we don't lose it

    def __repr__(self):
        """Return a string representation of the playbook execution."""
        return f"{self.current_playbook.klass}()"

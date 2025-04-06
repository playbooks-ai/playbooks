"""Main interpreter module for executing playbooks."""

from typing import TYPE_CHECKING, Any, Dict, Generator, List, Tuple

from playbooks.call_stack import CallStackFrame, InstructionPointer
from playbooks.interpreter.execution_state import ExecutionState
from playbooks.interpreter.exit_conditions import (
    EmptyCallStackExitCondition,
    ExitCondition,
    MaxExecutionTimeExitCondition,
    MaxIterationsExitCondition,
    NoProgressExitCondition,
    WaitForExternalEventExitCondition,
)
from playbooks.trace_mixin import TraceMixin
from playbooks.types import AgentResponseChunk

if TYPE_CHECKING:
    from playbooks.config import LLMConfig
    from playbooks.playbook import Playbook


class InterpreterExitConditions(TraceMixin):
    """Class for managing interpreter exit conditions."""

    def __init__(self, state: ExecutionState):
        """Initialize the interpreter exit conditions.

        Args:
            state: The execution state.
        """
        super().__init__()
        self.state = state

        # Initialize exit conditions
        self.conditions: List[Tuple[ExitCondition, List[Any]]] = [
            (WaitForExternalEventExitCondition(), [self.state]),
            (
                MaxIterationsExitCondition(self.state.max_iterations),
                [],
            ),  # Pass count in check
            (MaxExecutionTimeExitCondition(self.state.max_execution_time), []),
            (EmptyCallStackExitCondition(), [self.state.call_stack]),
            (NoProgressExitCondition(state=self.state), [self.state]),
        ]

        # Initialize context
        self.iteration_count = 0
        self.exit_condition_reason: str | None = None

    def should_continue(self) -> bool:
        """Check if the interpreter should continue executing.

        Returns:
            True if execution should continue, False otherwise.
        """
        # Increment iteration count
        self.iteration_count += 1

        # Update arguments for conditions that depend on the current iteration
        # Find MaxIterationsExitCondition and update its args
        for i, (condition, _) in enumerate(self.conditions):
            if isinstance(condition, MaxIterationsExitCondition):
                self.conditions[i] = (condition, [self.iteration_count])
                break

        # Check exit conditions
        for condition, args in self.conditions:
            if condition.check(*args):
                self.trace(f"{condition.reason}, exiting interpreter loop")
                self.exit_condition_reason = condition.reason
                return False

        self.trace("No exit conditions met, continuing interpreter loop")
        return True


class Interpreter(TraceMixin):
    """Main interpreter class for executing playbooks."""

    def __init__(self, state: ExecutionState):
        """Initialize the interpreter.

        Args:
            state: The execution state shared across interpreter components.
        """
        super().__init__()
        self.state = state

    def execute(
        self,
        playbooks: Dict[str, "Playbook"],
        instruction: str,
        llm_config: "LLMConfig",
        stream: bool,
    ) -> Generator[AgentResponseChunk, None, None]:
        """Execute the interpreter loop until an exit condition is met.

        Args:
            playbooks: The available playbooks.
            instruction: The initial instruction or context.
            llm_config: The LLM configuration.
            stream: Whether to stream the response.

        Yields:
            AgentResponseChunk: Chunks of the agent's response as execution progresses.
        """
        done = False
        exit_conditions = InterpreterExitConditions(self.state)
        self.trace(exit_conditions)

        while not done:
            # Reset per-iteration state (like LLM calls, playbook calls)
            self.state.reset()

            # Get the current playbook based on the call stack
            current_playbook_name = self.get_current_playbook_name()
            current_playbook = (
                playbooks.get(current_playbook_name) if current_playbook_name else None
            )

            # Import here to avoid circular imports
            from playbooks.interpreter.playbook_execution import PlaybookExecution

            # Execute one step/iteration within the current playbook context
            playbook_execution = PlaybookExecution(
                state=self.state,
                current_playbook=current_playbook,
            )
            self.trace(playbook_execution)
            yield from playbook_execution.execute(
                playbooks=playbooks,
                instruction=instruction,  # Instruction might be needed for context/triggering
                llm_config=llm_config,
                stream=stream,
            )

            instruction = ""

            # If the execution resulted in a request to call another playbook, push it
            if len(self.state.playbook_calls) > 0:
                # Assuming only one call is queued per step for now
                new_playbook_klass = self.state.playbook_calls[0]
                self.state.call_stack.push(
                    CallStackFrame(
                        instruction_pointer=InstructionPointer(
                            playbook=new_playbook_klass,
                            line_number="01",  # Start at the beginning
                        )
                        # llm_chat_session_id might be needed here if calls inherit context
                    )
                )
                self.state.clear_playbook_calls()  # Clear the queue after pushing

            # Check if any exit condition is met after the step
            done = not exit_conditions.should_continue()

        self.trace(f"Interpreter finished: {exit_conditions.exit_condition_reason}")

    def get_current_playbook_name(self, default: str | None = None) -> str | None:
        """Get the current playbook name from the top of the call stack.

        Args:
            default: The value to return if the call stack is empty.

        Returns:
            The current playbook name, or the default value.
        """
        current_frame = self.state.call_stack.peek()
        return (
            default
            if current_frame is None
            else current_frame.instruction_pointer.playbook
        )

    def get_trace_metadata(self) -> Dict[str, Any]:
        """Return metadata for tracing."""
        # Currently no specific metadata for the interpreter itself,
        # but subclasses or future versions might add some.
        return {}

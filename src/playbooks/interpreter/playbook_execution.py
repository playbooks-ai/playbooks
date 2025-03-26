"""Playbook execution module for the interpreter."""

# Type hints for external imports
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional

from playbooks.config import LLMConfig
from playbooks.interpreter.execution_state import ExecutionState
from playbooks.interpreter.exit_conditions import (
    EmptyCallStackExitCondition,
    MaxExecutionTimeExitCondition,
    MaxIterationsExitCondition,
    NoProgressExitCondition,
    PlaybookSwitchExitCondition,
    WaitForExternalEventExitCondition,
)
from playbooks.trace_mixin import TraceMixin
from playbooks.types import AgentResponseChunk

if TYPE_CHECKING:
    from playbooks.playbook import Playbook


class PlaybookExitConditions(TraceMixin):
    """Manages exit conditions for playbook execution loops."""

    def __init__(self, state: ExecutionState, current_playbook_klass: Optional[str]):
        """Initialize playbook exit conditions.

        Args:
            state: The current execution state
            current_playbook_klass: The current playbook class name
        """
        super().__init__()
        self.state = state
        self.current_playbook_klass = current_playbook_klass
        self.exit_condition_reason = None
        self.iteration_count = 0

        # Initialize exit conditions
        self.wait_for_external_event_condition = WaitForExternalEventExitCondition()
        self.playbook_switch_condition = PlaybookSwitchExitCondition()
        self.max_iterations_condition = MaxIterationsExitCondition(
            self.state.max_iterations
        )
        self.max_execution_time_condition = MaxExecutionTimeExitCondition(
            self.state.max_execution_time
        )
        self.no_progress_condition = NoProgressExitCondition(state=self.state)
        self.empty_call_stack_condition = EmptyCallStackExitCondition()

    def should_continue(self) -> bool:
        """Check if the playbook execution should continue.

        Returns:
            bool: True if execution should continue, False otherwise
        """
        # Increment iteration count
        self.iteration_count += 1

        # List of conditions to check with their required arguments
        conditions = [
            (self.wait_for_external_event_condition, [self.state]),
            (self.playbook_switch_condition, [self.state, self.current_playbook_klass]),
            (self.max_iterations_condition, [self.iteration_count]),
            (self.max_execution_time_condition, []),
            (self.empty_call_stack_condition, [self.state.call_stack]),
            (self.no_progress_condition, [self.state]),
        ]

        # Check each condition
        for condition, args in conditions:
            if condition.check(*args):
                self.trace(f"{condition.reason}, exiting playbook loop")
                self.exit_condition_reason = condition.reason
                return False

        self.trace("No exit conditions met, continuing playbook loop")
        return True


class PlaybookExecution(TraceMixin):
    """Manages the execution of a playbook.

    This class executes a playbook by repeatedly running the interpreter
    until an exit condition is met.

    Attributes:
        state: The execution state
        current_playbook: The playbook being executed
        playbook_klass: The class name of the playbook
        playbook_content: The markdown content of the playbook
    """

    def __init__(
        self,
        state: ExecutionState,
        current_playbook: Optional["Playbook"] = None,
    ):
        """Initialize playbook execution.

        Args:
            state: The execution state
            current_playbook: The current playbook being executed
        """
        super().__init__()
        self.state = state
        self.current_playbook = current_playbook

        # Set playbook-specific attributes
        if current_playbook:
            self.playbook_klass = current_playbook.klass
            self.playbook_content = current_playbook.markdown
        else:
            self.playbook_klass = None
            self.playbook_content = None

    def execute(
        self,
        playbooks: Dict[str, "Playbook"],
        instruction: str,
        llm_config: LLMConfig,
        stream: bool,
    ) -> Generator[AgentResponseChunk, None, None]:
        """Execute the playbook until an exit condition is met.

        Args:
            playbooks: Dictionary of available playbooks
            instruction: Initial instruction or user query
            llm_config: LLM configuration
            stream: Whether to stream the response

        Yields:
            AgentResponseChunk: Response chunks from the execution
        """
        from .interpreter_execution import InterpreterExecution

        done = False

        while not done:
            # Create and execute the interpreter
            interpreter_execution = InterpreterExecution(
                state=self.state,
                current_playbook=self.current_playbook,
            )
            self.trace(interpreter_execution)

            # Execute the interpreter and yield response chunks
            yield from interpreter_execution.execute(
                playbooks=playbooks,
                instruction=instruction,
                llm_config=llm_config,
                stream=stream,
            )

            # Clear instruction after first iteration
            instruction = ""

            # Check exit conditions
            exit_conditions = PlaybookExitConditions(
                state=self.state,
                current_playbook_klass=(
                    self.current_playbook.klass if self.current_playbook else None
                ),
            )
            self.trace(exit_conditions)
            done = not exit_conditions.should_continue()

    def __repr__(self) -> str:
        """Return a string representation of the playbook execution."""
        return f"PlaybookExecution({self.playbook_klass})"

    def get_trace_metadata(self) -> Dict[str, Any]:
        """Return metadata for tracing."""
        return {
            "id": self._trace_id,
            "playbook_klass": self.playbook_klass,
        }

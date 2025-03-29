"""Exit conditions for the interpreter execution loops."""

import time
from abc import ABC, abstractmethod

from playbooks.call_stack import CallStack
from playbooks.interpreter.execution_state import ExecutionState


class ExitCondition(ABC):
    """Base class for exit conditions.

    Exit conditions determine when an execution loop should exit.
    """

    @abstractmethod
    def check(self, *args) -> bool:
        """Check if this exit condition is met.

        Returns:
            True if the condition is met, False otherwise
        """
        pass

    @property
    @abstractmethod
    def reason(self) -> str:
        """Get the reason for exiting."""
        pass

    @property
    @abstractmethod
    def wait_for_external_event(self) -> bool:
        """Determine if execution should pause waiting for an external event."""
        pass


class UserInputRequiredExitCondition(ExitCondition):
    """Exit condition for when user input is required."""

    def check(self, state: ExecutionState) -> bool:
        """Check if user input is required."""
        return state.user_input_required

    @property
    def reason(self) -> str:
        return "User input required"

    @property
    def wait_for_external_event(self) -> bool:
        return True


class PlaybookCallExitCondition(ExitCondition):
    """Exit condition for when a playbook call is encountered."""

    def check(self, state: ExecutionState) -> bool:
        """Check if a playbook call is encountered."""
        return len(state.playbook_calls) > 0

    @property
    def reason(self) -> str:
        return "Playbook call detected"

    @property
    def wait_for_external_event(self) -> bool:
        return False


class YieldStepExitCondition(ExitCondition):
    """Exit condition for when a YLD step is encountered."""

    def __init__(self):
        self.yielded_step = None

    def check(self, state: ExecutionState) -> bool:
        """Check if a YLD step is encountered and not previously yielded."""
        if not state or not state.last_executed_step:
            return False

        last_step = state.last_executed_step

        if last_step.endswith(":YLD") and not state.has_yielded_step(last_step):
            self.yielded_step = last_step
            state.add_yielded_step(last_step)
            return True
        return False

    @property
    def reason(self) -> str:
        return "Yield step detected"

    @property
    def wait_for_external_event(self) -> bool:
        return True


class EmptyCallStackExitCondition(ExitCondition):
    """Exit condition for when the call stack is empty."""

    def check(self, call_stack: CallStack) -> bool:
        """Check if the call stack is empty."""
        return call_stack.is_empty()

    @property
    def reason(self) -> str:
        return "Call stack is empty"

    @property
    def wait_for_external_event(self) -> bool:
        return False


class PlaybookSwitchExitCondition(ExitCondition):
    """Exit condition for when a playbook switch is needed."""

    def __init__(self):
        self.playbook_class = ""

    def check(self, state: ExecutionState, current_playbook_klass: str) -> bool:
        """Check if a playbook switch is needed.

        Args:
            state: The current execution state
            current_playbook_klass: The current playbook class name

        Returns:
            True if a playbook switch is needed, False otherwise
        """
        # Check for pending playbook calls first
        if len(state.playbook_calls) > 0:
            return True

        # Check if current frame refers to a different playbook
        frame = state.call_stack.peek()
        if frame:
            playbook_class = frame.instruction_pointer.playbook
        else:
            playbook_class = ""

        switching = playbook_class != current_playbook_klass
        if switching:
            self.playbook_class = playbook_class

        return switching

    @property
    def reason(self) -> str:
        return f"Switching to playbook {self.playbook_class}"

    @property
    def wait_for_external_event(self) -> bool:
        return False


class ReturnFromPlaybookExitCondition(ExitCondition):
    """Exit condition for when returning from a playbook call."""

    def check(self, state: ExecutionState) -> bool:
        """Check if returning from a playbook call."""
        if not state or not state.last_executed_step:
            return False

        return state.last_executed_step.endswith(":RET")

    @property
    def reason(self) -> str:
        return "Return from playbook"

    @property
    def wait_for_external_event(self) -> bool:
        return False


class SayOnlyExitCondition(ExitCondition):
    """Exit condition for when only Say calls are present."""

    def check(self, state: ExecutionState) -> bool:
        """Check if only Say calls are present (no tool calls)."""
        return state and state.response_chunks and not state.tool_calls

    @property
    def reason(self) -> str:
        return "Say-only response"

    @property
    def wait_for_external_event(self) -> bool:
        return True


class MaxIterationsExitCondition(ExitCondition):
    """Exit condition for when maximum iterations are reached."""

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.iteration_count = 0

    def check(self, iteration_count: int = None) -> bool:
        """Check if maximum iterations have been reached.

        Args:
            iteration_count: If provided, use this instead of incrementing internal counter

        Returns:
            True if max iterations reached, False otherwise
        """
        if iteration_count is not None:
            return iteration_count > self.max_iterations

        self.iteration_count += 1
        return self.iteration_count > self.max_iterations

    @property
    def reason(self) -> str:
        return f"Maximum iterations ({self.max_iterations}) reached"

    @property
    def wait_for_external_event(self) -> bool:
        return False


class MaxExecutionTimeExitCondition(ExitCondition):
    """Exit condition for when maximum execution time is reached."""

    def __init__(self, max_execution_time: int = 60):
        self.max_execution_time = max_execution_time
        self.start_time = time.time()

    def check(self, *args) -> bool:
        """Check if maximum execution time has been reached."""
        elapsed_time = time.time() - self.start_time
        return elapsed_time >= self.max_execution_time

    @property
    def reason(self) -> str:
        return f"Maximum execution time ({self.max_execution_time}s) reached"

    @property
    def wait_for_external_event(self) -> bool:
        return False


class NoProgressExitCondition(ExitCondition):
    """Exit condition for when no progress is detected."""

    def __init__(self, state: ExecutionState):
        self.max_no_progress = state.max_no_progress
        self.last_state_hash = state.progress_hash()
        self.consecutive_no_progress = 0

    def check(self, state: ExecutionState) -> bool:
        """Check if no progress is detected by comparing state hashes."""
        current_state_hash = state.progress_hash()

        if self.last_state_hash == current_state_hash:
            self.consecutive_no_progress += 1
            if self.consecutive_no_progress >= self.max_no_progress:
                return True
        else:
            self.consecutive_no_progress = 0
            self.last_state_hash = current_state_hash

        return False

    @property
    def reason(self) -> str:
        return f"No progress detected after {self.max_no_progress} iterations"

    @property
    def wait_for_external_event(self) -> bool:
        return True


class WaitForExternalEventExitCondition(ExitCondition):
    """Exit condition for when waiting for an external event."""

    def check(self, state: ExecutionState) -> bool:
        """Check if waiting for an external event."""
        return state.wait_for_external_event

    @property
    def reason(self) -> str:
        return "Waiting for external event"

    @property
    def wait_for_external_event(self) -> bool:
        return True

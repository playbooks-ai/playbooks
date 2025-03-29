"""Execution loop management for the interpreter.

This module provides the ExecutionLoop class, which encapsulates the logic for
running an execution loop with a given execution state. It handles loop iteration,
progress tracking, and yielding results from the execution.
"""

import traceback
from typing import Any, Callable, Dict, Generator, Optional, TypeVar

from playbooks.interpreter.execution_state import ExecutionState
from playbooks.trace_mixin import TraceMixin, TracingContext

T = TypeVar("T")


class ExecutionLoop:
    """Execution loop for the interpreter.

    This class manages the execution loop for the interpreter, handling
    iteration, error handling, and tracing. It monitors progress to prevent
    infinite loops and checks exit conditions during execution.

    Attributes:
        state: The execution state to use.
        tracer: The tracer to use for tracing execution.
        name: The name of the loop for tracing.
    """

    def __init__(
        self,
        state: ExecutionState,
        tracer: TraceMixin,
        name: str = "execution_loop",
    ):
        """Initialize the execution loop.

        Args:
            state: The execution state to use.
            tracer: The tracer to use for tracing execution.
            name: The name of the loop for tracing.
        """
        self.state = state
        self.tracer = tracer
        self.name = name

    def check_exit_conditions(self, context: Dict[str, Any]) -> bool:
        """Check if any exit conditions are met.

        Args:
            context: The context to check against.

        Returns:
            True if any exit condition is met, False otherwise.
        """
        return self.state.check_exit_conditions(context) is not None

    def execute_with_error_handling(
        self, func: Callable, *args, **kwargs
    ) -> Optional[Any]:
        """Execute a function with error handling.

        Args:
            func: The function to execute
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the function, or None if an error occurred
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.tracer.trace(
                f"Error executing {func.__name__}: {str(e)}",
                metadata={
                    "args": args,
                    "kwargs": kwargs,
                    "traceback": traceback.format_exc(),
                },
                level="ERROR",
            )
            return None

    def run(
        self, iteration_function: Callable[[Dict[str, Any]], Generator[T, None, None]]
    ) -> Generator[T, None, None]:
        """Run the execution loop and yield results.

        This method runs the execution loop, calling the iteration function
        on each iteration and yielding the results. It tracks progress to
        prevent infinite loops and checks exit conditions after each iteration.

        Args:
            iteration_function: The function to call on each iteration.

        Yields:
            The results of the iteration function.
        """
        with TracingContext(self.tracer, f"{self.name}_start", {}):
            # Reset exit state
            self.state.reset_exit_state()

            # Variables to track progress
            iteration_count = 0
            max_iterations_without_progress = self.state.max_no_progress
            previous_state_hash = None

            # Run the loop
            while not self.state.should_exit:
                with TracingContext(self.tracer, f"{self.name}_iteration", {}):
                    # Check for lack of progress to prevent infinite loops
                    iteration_count += 1
                    current_state_hash = self.state.progress_hash()

                    if previous_state_hash == current_state_hash:
                        if iteration_count > max_iterations_without_progress:
                            self.tracer.trace(
                                f"No progress detected after {iteration_count} iterations, breaking loop",
                                metadata={"current_state_hash": current_state_hash},
                                level="WARNING",
                            )
                            self.state.request_exit(
                                "No progress detected, breaking loop", False
                            )
                            break
                    else:
                        # Progress detected, reset counter
                        previous_state_hash = current_state_hash

                    # Run the iteration function
                    result_generator = iteration_function({})
                    if result_generator is not None:
                        yield from result_generator

                    # Check exit conditions
                    context = {
                        "iteration_count": iteration_count,
                        "state_hash": current_state_hash,
                    }
                    if self.check_exit_conditions(context):
                        break

            # Trace the exit
            self.tracer.trace(
                f"Exiting {self.name}",
                metadata={
                    "exit_reason": self.state.exit_reason,
                    "wait_for_input": self.state.wait_for_input,
                },
            )

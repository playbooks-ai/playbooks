"""Streaming Python code executor for incremental execution during LLM generation.

This module provides execution of LLM-generated Python code as it arrives in chunks,
allowing statements to execute progressively rather than waiting for complete code blocks.
"""

import ast
import asyncio
import logging
import traceback
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.core.exceptions import ExecutionFinished
from playbooks.execution.incremental_code_buffer import CodeBuffer
from playbooks.execution.python_executor import (
    ExecutionResult,
    PythonExecutor,
)
from playbooks.infrastructure.logging.debug_logger import debug

if TYPE_CHECKING:
    from playbooks.agents import LocalAIAgent

logger = logging.getLogger(__name__)


class StreamingExecutionError(Exception):
    """Exception raised when streaming execution encounters an error."""

    def __init__(self, message: str, original_error: Exception, executed_code: str):
        """Initialize streaming execution error.

        Args:
            message: Error message
            original_error: The original exception that occurred
            executed_code: The code that was successfully executed before the error
        """
        super().__init__(message)
        self.original_error = original_error
        self.executed_code = executed_code


class StreamingPythonExecutor:
    """Execute Python code incrementally as chunks arrive during streaming.

    This executor maintains a buffer of incoming code, attempts to parse and execute
    complete statements as they arrive, with proper globals/locals separation.

    Key features:
    - Uses CodeBuffer for indentation-aware executable prefix detection
    - Executes statements as soon as they're complete
    - Uses separate globals/locals dicts for proper variable scoping
    - Stops on errors and provides executed code for LLM retry
    """

    def __init__(
        self,
        agent: "LocalAIAgent",
        playbook_args: Optional[Dict[str, Any]] = None,
        execution_id: Optional[int] = None,
    ):
        """Initialize streaming Python executor.

        Args:
            agent: The AI agent executing the code
            playbook_args: Optional dict of playbook argument names to values
        """
        self.agent = agent
        self.playbook_args = playbook_args
        self.execution_id = execution_id

        # Create a PythonExecutor to reuse its namespace building and capture functions
        self.base_executor = PythonExecutor(agent)

        # Build namespace once at initialization (without playbook_args)
        self.namespace: Dict[str, Any] = self.base_executor.build_namespace()
        # Add self to namespace for LLM-generated code
        self.namespace["self"] = agent

        # Result tracking
        self.result = ExecutionResult()
        self.base_executor.result = self.result

        # Initialize frame locals with playbook arguments if provided
        if playbook_args:
            current_frame = self.agent.call_stack.peek()
            if current_frame:
                current_frame.locals.update(playbook_args)

        # Buffer management using CodeBuffer
        self.code_buffer = CodeBuffer()

        # Track executed code for error truncation
        self.executed_lines: List[str] = []  # Lines successfully executed
        self.statement_index: int = 0  # Track statement ordering for tracing

        # Error tracking
        self.has_error = False
        self.error: Optional[Exception] = None
        self.error_traceback: Optional[str] = None

        # Track if we've set executor on the call stack frame
        self._executor_set = False

    async def add_chunk(self, chunk: str) -> None:
        """Add a code chunk and attempt to execute complete statements.

        This method buffers incoming chunks and only attempts to parse/execute
        when complete lines (ending with \\n) are available. This prevents issues
        with variable names or tokens being split across chunks.

        Args:
            chunk: Code chunk to add to buffer

        Raises:
            StreamingExecutionError: If execution fails with error details
        """
        if self.has_error:
            # Don't process more chunks after an error
            return

        self.code_buffer.add_chunk(chunk)

        # Only try to execute when we have complete lines (ending with \n)
        # We only consider content up to the last newline - anything after
        # the last newline is incomplete and could be mid-token
        if "\n" in chunk:
            await self._try_execute()

    async def _try_execute(self) -> None:
        """Try to execute any complete statements in the buffer.

        This method:
        1. Gets the executable prefix from the buffer
        2. Preprocesses and parses it
        3. Executes each statement
        4. Removes executed code from buffer
        5. Captures errors if execution fails
        """
        executable = self.code_buffer.get_executable_prefix()

        if not executable:
            return

        # Set executor on current call stack frame for Log* methods (only once)
        if not self._executor_set:
            current_frame = self.agent.call_stack.peek()
            if current_frame:
                current_frame.executor = self.base_executor
                self._executor_set = True

        try:
            # Parse the code (no preprocessing needed - uses state.x syntax)
            parsed = ast.parse(executable)

            # Execute each statement
            for stmt in parsed.body:
                await self._execute_statement(stmt)
                await asyncio.sleep(0)  # Yield to event loop for other events

            # Success - remove executed code from buffer and track it
            self.code_buffer.consume_prefix(executable)
            self.executed_lines.append(executable)

        except ExecutionFinished:
            # Program execution finished - propagate without wrapping as error
            raise
        except Exception as e:
            # Execution error - capture and stop processing
            self.has_error = True
            self.error = e
            self.error_traceback = traceback.format_exc()

            # Update result with error info
            if isinstance(e, SyntaxError):
                self.result.syntax_error = e
                self.result.error_message = f"{type(e).__name__}: {e}"
            else:
                self.result.runtime_error = e
                self.result.error_message = f"{type(e).__name__}: {e}"
            self.result.error_traceback = self.error_traceback

            logger.error(f"Error executing statement: {type(e).__name__}: {e}")
            logger.error(f"Traceback: {self.error_traceback}")

            # Get the executed code up to and including the error
            executed_code = self.get_executed_code(include_error_line=True)

            raise StreamingExecutionError(
                f"Execution failed: {type(e).__name__}: {e}", e, executed_code
            )

    async def _execute_statement(self, stmt: ast.stmt) -> None:
        """Execute a single AST statement with tracing.

        Uses exec() with proper namespace handling. For async statements containing
        await, wraps them in a temporary async function.

        Args:
            stmt: AST statement to execute
        """
        if self.agent.program and getattr(
            self.agent.program, "execution_finished", False
        ):
            debug(
                f"Skipping execution of statement: {stmt} because program execution is finished"
            )
            raise ExecutionFinished("Program execution finished")

        # Get current frame and its locals
        current_frame = self.agent.call_stack.peek()
        if not current_frame:
            raise RuntimeError("No call stack frame available for execution")

        # Ensure executor is set on frame for Return/Yield calls
        if not hasattr(current_frame, "executor") or current_frame.executor is None:
            current_frame.executor = self.base_executor

        frame_locals = current_frame.locals

        # Convert the statement back to source code
        statement_code = ast.unparse(stmt)

        # Safety filters for streamed LLM output:
        # - Some models occasionally leak markdown/code-fence artifacts that parse as
        #   bare identifiers (e.g. a standalone `python` line). Those are no-ops and
        #   should not crash execution with NameError.
        # - Prevent LLM-generated code from mutating agent runtime internals that are
        #   not part of the playbook state API (e.g. joined_meetings).
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Name):
            debug(f"Skipping no-op bare identifier expression: {stmt.value.id}")
            return

        def _is_rooted_at_state(n: ast.AST) -> bool:
            """Return True if `n` is an Attribute chain whose base is `self.state`/`agent.state`."""
            if not isinstance(n, ast.Attribute):
                return False
            cur: ast.AST = n
            # Walk left through `.value` until we hit a non-Attribute node.
            while isinstance(cur, ast.Attribute):
                if (
                    cur.attr == "state"
                    and isinstance(cur.value, ast.Name)
                    and cur.value.id in {"self", "agent"}
                ):
                    return True
                cur = cur.value
            return False

        protected_self_attrs = {
            # Runtime wiring / infrastructure
            "program",
            "event_bus",
            "call_stack",
            "session_log",
            "namespace_manager",
            "meeting_manager",
            # Meeting runtime state (not playbook state)
            "owned_meetings",
            "joined_meetings",
        }

        def _is_protected_target(t: ast.AST) -> bool:
            # self.<protected>
            if (
                isinstance(t, ast.Attribute)
                and isinstance(t.value, ast.Name)
                and t.value.id in {"self", "agent"}
                and t.attr in protected_self_attrs
            ):
                return True
            # self.<protected>[...]
            if isinstance(t, ast.Subscript):
                base = t.value
                if (
                    isinstance(base, ast.Attribute)
                    and isinstance(base.value, ast.Name)
                    and base.value.id in {"self", "agent"}
                    and base.attr in protected_self_attrs
                ):
                    return True
            return False

        if isinstance(stmt, ast.Assign):
            if any(_is_protected_target(t) for t in stmt.targets):
                debug(
                    f"Skipping assignment to protected agent attribute: {statement_code}"
                )
                return
        elif isinstance(stmt, ast.AnnAssign):
            if _is_protected_target(stmt.target):
                debug(
                    f"Skipping annotated assignment to protected agent attribute: {statement_code}"
                )
                return
        elif isinstance(stmt, ast.AugAssign):
            if _is_protected_target(stmt.target):
                debug(
                    f"Skipping augmented assignment to protected agent attribute: {statement_code}"
                )
                return

        # Also block *reads* of protected attributes: LLM code occasionally introspects
        # runtime internals (e.g. iterating self.joined_meetings as if it were a list),
        # which is brittle and can crash streaming execution.
        for node in ast.walk(stmt):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in {"self", "agent"}
                and node.attr in protected_self_attrs
            ):
                debug(
                    f"Skipping statement that reads protected agent attribute {node.attr}: {statement_code}"
                )
                return

        debug(f"Executing: {statement_code}", agent=self.agent)

        # Check if this is a function/class definition
        # These don't need wrapping and should execute directly
        is_definition = isinstance(
            stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        )

        # Check if statement contains await
        has_await = any(isinstance(node, ast.Await) for node in ast.walk(stmt))

        try:
            if is_definition or not has_await:
                # Function/class definitions or synchronous statements - use frame locals
                exec(
                    compile(statement_code, "<llm>", "exec"),
                    self.namespace,
                    frame_locals,
                )
            else:
                # Async statement with await - create wrapper that updates frame locals
                # Merge globals and frame locals into a single dict for execution
                combined_ns = self.namespace.copy()
                combined_ns.update(frame_locals)

                fn_name = f"__stmt_{uuid.uuid4().hex[:8]}__"

                # Create wrapper that executes the statement and captures local variables
                # Use try-finally to ensure locals are captured even if statement throws
                wrapped_code = f"async def {fn_name}():\n"
                wrapped_code += "    try:\n"
                for line in statement_code.split("\n"):
                    wrapped_code += f"        {line}\n"
                wrapped_code += "    finally:\n"
                wrapped_code += (
                    "        # Update combined namespace with local variables\n"
                )
                wrapped_code += "        __combined_ns.update({k: v for k, v in locals().items() if not k.startswith('_')})\n"

                # Make combined_ns available in the wrapper's closure
                combined_ns["__combined_ns"] = combined_ns

                # Execute wrapper definition
                exec(compile(wrapped_code, "<llm>", "exec"), combined_ns)

                # Get and execute the async function
                fn = combined_ns[fn_name]

                try:
                    await fn()
                finally:
                    # Clean up
                    del combined_ns[fn_name]
                    if "__combined_ns" in combined_ns:
                        del combined_ns["__combined_ns"]

                    # Extract any NEW variables to frame locals
                    for key, value in combined_ns.items():
                        if (
                            key not in self.namespace
                            and not callable(value)
                            and not key.startswith("_")
                            and key not in ["asyncio", "self"]
                        ):
                            frame_locals[key] = value
        except Exception:
            # Mark statement as failed
            raise

    def get_executed_code(self, include_error_line: bool = False) -> str:
        """Get the code that has been successfully executed.

        Args:
            include_error_line: If True and there's an error, include the line that caused it

        Returns:
            String containing executed code lines
        """
        return "\n".join(self.executed_lines)

    async def finalize(self) -> ExecutionResult:
        """Finalize execution and return the result.

        This should be called after all chunks have been processed to ensure
        any remaining buffered code is executed.

        Returns:
            ExecutionResult containing all captured directives and any errors
        """
        remaining_buffer = self.code_buffer.get_buffer().strip()

        # Try to execute any remaining buffered code
        if not self.has_error and remaining_buffer:
            # Ensure the buffer ends with a newline so get_executable_prefix() will consider it
            if not self.code_buffer.get_buffer().endswith("\n"):
                self.code_buffer.add_chunk("\n")
            await self._try_execute()

        # No cleanup needed - executor is tied to call stack frame lifecycle
        # When the frame is popped, the previous frame's executor becomes current
        return self.result

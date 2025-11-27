"""Streaming Python code executor for incremental execution during LLM generation.

This module provides execution of LLM-generated Python code as it arrives in chunks,
allowing statements to execute progressively rather than waiting for complete code blocks.
"""

import ast
import logging
import traceback
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from playbooks.compilation.expression_engine import preprocess_program
from playbooks.execution.incremental_code_buffer import CodeBuffer
from playbooks.execution.python_executor import (
    ExecutionResult,
    LLMNamespace,
    PythonExecutor,
)
from playbooks.utils.langfuse_client import get_client, observe

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
    complete statements as they arrive, and tracks variable changes in real-time.

    Key features:
    - Uses CodeBuffer for indentation-aware executable prefix detection
    - Executes statements as soon as they're complete
    - Tracks variable changes via runtime namespace inspection
    - Stops on errors and provides executed code for LLM retry
    """

    def __init__(
        self, agent: "LocalAIAgent", playbook_args: Optional[Dict[str, Any]] = None
    ):
        """Initialize streaming Python executor.

        Args:
            agent: The AI agent executing the code
            playbook_args: Optional dict of playbook argument names to values
        """
        self.agent = agent
        self.playbook_args = playbook_args

        # Create a PythonExecutor to reuse its namespace building and capture functions
        self.base_executor = PythonExecutor(agent)

        # Build namespace once at initialization
        self.namespace: LLMNamespace = self.base_executor.build_namespace(playbook_args)

        # Result tracking
        self.result = ExecutionResult()
        self.base_executor.result = self.result

        # Buffer management using CodeBuffer
        self.code_buffer = CodeBuffer()

        # Track executed code for error truncation
        self.executed_lines: List[str] = []  # Lines successfully executed

        # Variable tracking for runtime detection
        self.last_namespace_vars: Dict[str, Any] = {}
        self._initialize_namespace_snapshot()

        # Error tracking
        self.has_error = False
        self.error: Optional[Exception] = None
        self.error_traceback: Optional[str] = None

    def _initialize_namespace_snapshot(self) -> None:
        """Initialize snapshot of namespace variables for change detection."""
        # Capture initial state of namespace (excluding functions and builtins)
        self.last_namespace_vars = {
            k: v
            for k, v in self.namespace.items()
            if not callable(v) and not k.startswith("_") and k not in ["asyncio"]
        }

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
        4. Tracks variable changes
        5. Removes executed code from buffer
        6. Captures errors if execution fails
        """
        executable = self.code_buffer.get_executable_prefix()

        if not executable:
            return

        try:
            # Preprocess to convert $variable syntax
            preprocessed = preprocess_program(executable)

            # Parse the code
            parsed = ast.parse(preprocessed)

            # Execute each statement
            for stmt in parsed.body:
                await self._execute_statement(stmt)

                # Track variable changes after each statement
                await self._track_variable_changes()

            # Success - remove executed code from buffer and track it
            self.code_buffer.consume_prefix(executable)
            self.executed_lines.append(executable)

        except Exception as e:
            # Execution error - capture and stop processing
            self.has_error = True
            self.error = e
            self.error_traceback = traceback.format_exc()

            # Update result with error info
            if isinstance(e, SyntaxError):
                self.result.syntax_error = e
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

    @observe(capture_input=False, capture_output=False)
    async def _execute_statement(self, stmt: ast.stmt) -> None:
        """Execute a single AST statement with tracing.

        Uses exec() with proper namespace handling. For async statements containing
        await, wraps them in a temporary async function.

        Args:
            stmt: AST statement to execute
        """
        # Convert the statement back to source code
        statement_code = ast.unparse(stmt)

        # Update current span with statement-specific information
        langfuse = get_client()
        display_code = (
            statement_code
            if len(statement_code) <= 100
            else statement_code[:97] + "..."
        )
        langfuse.update_current_span(
            name=f"exec: {display_code}",
            input={"code": statement_code},
            metadata={"statement_type": stmt.__class__.__name__},
        )

        # Check if this is a function/class definition
        # These don't need wrapping and should execute directly
        is_definition = isinstance(
            stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        )

        # Check if statement contains await
        has_await = any(isinstance(node, ast.Await) for node in ast.walk(stmt))

        try:
            if is_definition or not has_await:
                # Function/class definitions or synchronous statements - execute directly
                exec(compile(statement_code, "<llm>", "exec"), self.namespace)
            else:
                # Async statement with await - wrap in temporary function
                fn_name = f"__stmt_{uuid.uuid4().hex[:8]}__"

                wrapped_code = f"async def {fn_name}():\n"

                # Add global declarations for any assignments in the statement
                assignments = self._find_assignments(stmt)
                if assignments:
                    wrapped_code += f"    global {', '.join(assignments)}\n"

                for line in statement_code.split("\n"):
                    wrapped_code += f"    {line}\n"

                # Execute wrapper definition directly in namespace
                exec(compile(wrapped_code, "<llm>", "exec"), self.namespace)

                # Execute the async function from namespace
                fn = dict.__getitem__(self.namespace, fn_name)

                try:
                    await fn()
                finally:
                    # Clean up the temporary function
                    dict.__delitem__(self.namespace, fn_name)

                # Mark statement as successful
                langfuse.update_current_span(output={"success": True})
        except Exception as e:
            # Mark statement as failed - @observe will capture the exception
            langfuse.update_current_span(output={"success": False, "error": str(e)})
            raise

    def _find_assignments(self, stmt: ast.stmt) -> List[str]:
        """Find all variable names that are assigned in a statement.

        Excludes function and class definitions as they naturally persist in namespace.

        Args:
            stmt: AST statement to analyze

        Returns:
            List of variable names that are assigned
        """
        # Don't add global declarations for function/class definitions
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return []

        assignments = []

        for node in ast.walk(stmt):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments.append(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assignments.append(node.target.id)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                assignments.append(node.target.id)

        return assignments

    async def _track_variable_changes(self) -> None:
        """Track variable changes by comparing namespace before/after execution.

        For any new or changed variables, calls Var() to record them in the state.
        """
        # Get current namespace state (excluding functions and builtins)
        current_vars = {
            k: v
            for k, v in self.namespace.items()
            if not callable(v) and not k.startswith("_") and k not in ["asyncio"]
        }

        # Find new or changed variables
        changes = []
        for name, value in current_vars.items():
            # Skip if value is the same (using identity check first for efficiency)
            if name in self.last_namespace_vars:
                old_value = self.last_namespace_vars[name]
                if old_value is value:
                    continue
                # For non-identical values, do equality check
                try:
                    if old_value == value:
                        continue
                except Exception:
                    # Comparison failed - treat as changed
                    pass
                changes.append((name, "changed"))
            else:
                changes.append((name, "new"))

            # Variable is new or changed - call Var() to record it
            try:
                await self.base_executor._capture_var(name, value)
            except Exception as e:
                logger.warning(f"Failed to capture variable {name}: {e}")

        # Update snapshot for next comparison
        self.last_namespace_vars = current_vars.copy()

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

        return self.result

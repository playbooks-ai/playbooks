"""Incremental Python code executor for streaming LLM responses.

This module provides incremental execution of Python code as it's being generated
by LLMs, allowing for real-time feedback and faster perceived responsiveness.
"""

import ast
import asyncio
import logging
import traceback
import types
from typing import Any, Dict, List, Optional, Tuple

from playbooks.execution.python_executor import ExecutionResult, LLMNamespace, PythonExecutor
from playbooks.compilation.expression_engine import preprocess_program
from playbooks.compilation.inject_setvar import inject_setvar

logger = logging.getLogger(__name__)


class IncrementalStatementParser:
    """Parse Python code incrementally as chunks arrive.

    This parser buffers incoming code chunks and uses Python's AST parser
    to detect complete statements that can be executed.
    """

    def __init__(self):
        """Initialize the parser."""
        self.buffer = ""
        self.completed_statements: List[str] = []
        self.last_parsed_end = 0
        self.base_indent_level = 0  # Track base indentation of current statement
        self.parsed_lines: List[str] = []  # Accumulated lines being parsed

    def add_chunk(self, chunk: str) -> List[str]:
        """Add a chunk of code and return any complete statements.

        Args:
            chunk: Code chunk to add (can be partial statement)

        Returns:
            List of complete statements ready for execution
        """
        self.buffer += chunk
        return self._extract_complete_statements()

    def _extract_complete_statements(self) -> List[str]:
        """Extract complete statements from buffer.

        Uses Python's AST parser and indentation tracking to determine when
        we have complete statements. Waits for dedent before emitting indented blocks.

        Returns:
            List of complete statements
        """
        statements = []
        lines = self.buffer.split("\n")

        # Skip lines that are already in parsed_lines (from previous chunk)
        lines_to_skip = len(self.parsed_lines)

        i = lines_to_skip
        while i < len(lines):
            line = lines[i]

            # If we're already accumulating a statement
            if self.parsed_lines:
                # Check for dedent (lower indentation than base level)
                line_indent = self._get_indent_level(line)

                # Skip blank lines and comments - they don't signal dedent
                if line.strip() and not line.strip().startswith("#"):
                    # Check if this is a dedent
                    if line_indent < self.base_indent_level:
                        # Dedent detected! Emit the accumulated statement
                        # But only if not the last line
                        if i < len(lines) - 1:
                            statements.extend(self._finalize_parsed_lines(self.parsed_lines))
                            self.parsed_lines = []
                            self.base_indent_level = 0
                            # Don't increment i - reprocess this line as new statement
                            continue
                        else:
                            # Last line with dedent - keep everything in buffer
                            # parsed_lines already has the accumulated statement
                            # just add this new dedented line
                            self.parsed_lines.append(line)
                            i += 1
                            break

                # Not a dedent - add to accumulated lines
                self.parsed_lines.append(line)
                i += 1
                continue

            # Not accumulating yet - check what this line is
            # Blank line at top level is a complete statement (separator)
            if not line.strip():
                if i < len(lines) - 1:
                    statements.append("")
                i += 1
                continue

            # Comment line at top level is a complete statement
            if line.strip().startswith("#"):
                if i < len(lines) - 1:
                    statements.append(line)
                else:
                    # Last line - might be incomplete, keep in parsed_lines
                    self.parsed_lines.append(line)
                i += 1
                continue

            # Start accumulating a new statement
            self.base_indent_level = self._get_indent_level(line)
            self.parsed_lines.append(line)

            # Check if this single line is already complete (syntactically)
            # AND doesn't end with : (which needs a body)
            if self._is_complete_statement(line) and not line.rstrip().endswith(":"):
                # Single-line statement that's complete!
                # But only finalize if not the last line
                if i < len(lines) - 1:
                    statements.extend(self._finalize_parsed_lines(self.parsed_lines))
                    self.parsed_lines = []
                    self.base_indent_level = 0
                # else: Last line - keep in parsed_lines (already added above)
            # else: incomplete or has : - continue accumulating

            i += 1

        # Rebuild buffer from parsed_lines (incomplete statement being accumulated)
        self.buffer = "\n".join(self.parsed_lines)

        return statements

    def _get_indent_level(self, line: str) -> int:
        """Get the indentation level of a line (number of leading spaces).

        Args:
            line: Line to check

        Returns:
            Number of leading spaces
        """
        if not line:
            return 0
        return len(line) - len(line.lstrip())

    def _is_complete_statement(self, code: str) -> bool:
        """Check if code is a complete Python statement.

        Args:
            code: Code to check

        Returns:
            True if code is a complete statement
        """
        if not code.strip():
            return True

        # Check for unclosed multiline strings
        if self._has_unclosed_triple_quotes(code):
            return False

        # Check for unclosed brackets/parens/braces
        if self._has_unclosed_brackets(code):
            return False

        # Check if it ends with : (needs a body)
        if code.rstrip().endswith(":"):
            return False

        # Preprocess code (convert $var to var) before parsing
        # This allows us to validate LLM-generated code with $variable syntax
        preprocessed = preprocess_program(code)

        # Try to parse it
        try:
            ast.parse(preprocessed)
            return True
        except SyntaxError:
            return False

    def _has_unclosed_triple_quotes(self, code: str) -> bool:
        """Check if code has unclosed triple quotes.

        Args:
            code: Code to check

        Returns:
            True if there are unclosed triple quotes
        """
        # Count triple quotes (both """ and ''')
        double_count = code.count('"""')
        single_count = code.count("'''")

        # If odd number, there's an unclosed one
        return (double_count % 2 == 1) or (single_count % 2 == 1)

    def _has_unclosed_brackets(self, code: str) -> bool:
        """Check if code has unclosed brackets, parens, or braces.

        Args:
            code: Code to check

        Returns:
            True if there are unclosed brackets
        """
        # Simple bracket matching (doesn't handle strings properly, but good enough)
        stack = []
        pairs = {"(": ")", "[": "]", "{": "}"}
        in_string = False
        string_char = None
        i = 0

        while i < len(code):
            char = code[i]

            # Handle strings (skip bracket matching inside strings)
            if char in ['"', "'"]:
                # Check for triple quotes
                if i + 2 < len(code) and code[i : i + 3] in ['"""', "'''"]:
                    if not in_string:
                        in_string = True
                        string_char = code[i : i + 3]
                        i += 3
                        continue
                    elif string_char == code[i : i + 3]:
                        in_string = False
                        string_char = None
                        i += 3
                        continue
                # Single quote
                if not in_string:
                    in_string = True
                    string_char = char
                elif string_char == char and (i == 0 or code[i - 1] != "\\"):
                    in_string = False
                    string_char = None

            # Only match brackets outside strings
            if not in_string:
                if char in pairs:
                    stack.append(char)
                elif char in pairs.values():
                    if not stack:
                        return True  # Closing bracket without opening
                    opening = stack.pop()
                    if pairs[opening] != char:
                        return True  # Mismatched brackets

            i += 1

        return len(stack) > 0  # Unclosed brackets

    def _finalize_parsed_lines(self, lines: List[str]) -> List[str]:
        """Convert parsed lines into statement(s).

        Args:
            lines: List of lines that form complete Python code

        Returns:
            List of statements (usually just one, but could be multiple)
        """
        # Join lines back into code, preserving original formatting
        code = "\n".join(lines)

        # Try to parse and see if we have multiple statements
        try:
            tree = ast.parse(code)
            # If we have multiple top-level statements, we need to split them
            # But for now, let's just return the whole code block as one statement
            # This preserves formatting and is simpler
            return [code]
        except SyntaxError:
            # Shouldn't happen since we already validated, but just in case
            return [code]

    def has_buffered_content(self) -> bool:
        """Check if there's any buffered content waiting to be parsed.

        Returns:
            True if buffer is non-empty
        """
        return len(self.buffer.strip()) > 0

    def get_buffer(self) -> str:
        """Get current buffer content.

        Returns:
            Current buffer content
        """
        return self.buffer

    def clear_buffer(self) -> None:
        """Clear the buffer."""
        self.buffer = ""


class IncrementalExecutor:
    """Execute Python code incrementally as statements arrive.

    This executor processes statements one at a time as they're parsed,
    providing real-time feedback and allowing for early error detection.
    """

    def __init__(self, python_executor: PythonExecutor):
        """Initialize incremental executor.

        Args:
            python_executor: The underlying Python executor
        """
        self.python_executor = python_executor
        self.parser = IncrementalStatementParser()
        self.namespace: Optional[LLMNamespace] = None
        self.executed_statements: List[str] = []
        self.execution_result = ExecutionResult()

        # Track if we've had an error
        self.error_occurred = False
        self.error_statement: Optional[str] = None

    async def add_chunk(self, chunk: str) -> Tuple[List[str], Optional[Exception]]:
        """Add a chunk of code and execute any complete statements.

        Args:
            chunk: Code chunk to add

        Returns:
            Tuple of (executed statements, error if any)
        """
        if self.error_occurred:
            # Don't process more chunks after an error
            return [], None

        # Parse chunk into statements
        statements = self.parser.add_chunk(chunk)

        # Execute each statement
        executed = []
        for statement in statements:
            try:
                await self._execute_statement(statement)
                executed.append(statement)
                self.executed_statements.append(statement)
            except Exception as e:
                # Error occurred - stop processing
                self.error_occurred = True
                self.error_statement = statement
                self.executed_statements.append(statement)  # Include the failed statement
                logger.error(f"Error executing statement: {statement}")
                logger.error(f"Error: {type(e).__name__}: {e}")
                return executed, e

        return executed, None

    async def _execute_statement(self, statement: str) -> None:
        """Execute a single statement.

        Args:
            statement: Python statement to execute

        Raises:
            Exception: If execution fails
        """
        # Skip blank lines and pure comments (non-code)
        if not statement.strip() or statement.strip().startswith("#"):
            return

        # Initialize namespace on first execution
        if self.namespace is None:
            self.namespace = self.python_executor.build_namespace()

        # Preprocess the statement
        preprocessed = preprocess_program(statement)

        # For now, we'll inject Var() calls at the statement level
        # This is tricky because inject_setvar expects a full module/function
        # Let's wrap it temporarily for the transformation, then unwrap
        try:
            # Wrap in a dummy async function for inject_setvar
            wrapped = f"async def __temp__():\n"
            indented = "\n".join(f"    {line}" for line in preprocessed.split("\n"))
            wrapped += indented

            # Apply inject_setvar
            transformed = inject_setvar(wrapped)

            # Extract the body (remove function wrapper)
            tree = ast.parse(transformed)
            func_def = tree.body[0]  # The async def __temp__()
            body_statements = func_def.body

            # Unparse the body statements
            transformed_code = "\n".join(ast.unparse(stmt) for stmt in body_statements)

        except Exception as e:
            # If transformation fails, use original preprocessed code
            logger.warning(f"Failed to inject Var() calls: {e}")
            transformed_code = preprocessed

        # Compile with PyCF_ALLOW_TOP_LEVEL_AWAIT
        try:
            compiled_code = compile(
                transformed_code,
                "<llm-incremental>",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )
        except SyntaxError as e:
            logger.error(f"Syntax error compiling statement: {transformed_code}")
            raise

        # Execute in the namespace
        # We need to handle await at the top level
        # exec() with PyCF_ALLOW_TOP_LEVEL_AWAIT returns a coroutine if there are awaits
        result = eval(compiled_code, self.namespace)

        # If result is a coroutine, await it
        if asyncio.iscoroutine(result):
            await result

    async def finalize(self) -> ExecutionResult:
        """Finalize execution and return the result.

        Returns:
            ExecutionResult with all captured directives
        """
        # Get the execution result from the python executor
        return self.python_executor.result

    def get_executed_code(self) -> str:
        """Get all successfully executed code.

        Returns:
            String containing all executed statements
        """
        return "\n".join(self.executed_statements)

    def get_error_info(self) -> Optional[Tuple[str, Exception]]:
        """Get information about the error if one occurred.

        Returns:
            Tuple of (failed statement, exception) or None
        """
        if self.error_occurred and self.error_statement:
            return (self.error_statement, self.execution_result.runtime_error)
        return None

"""Incremental code buffer for streaming Python execution.

This module provides a buffer that accumulates code chunks and identifies
executable prefixes using an indentation-aware algorithm.
"""

import ast
import re
from typing import Optional


class CodeBuffer:
    """Buffers incoming code chunks and finds executable prefixes.

    The buffer accumulates code as it arrives in chunks and uses an
    indentation-aware algorithm to find the longest executable prefix:

    1. Split buffer into lines
    2. Find the last line that doesn't start with whitespace
    3. Try parsing from that line backwards until a valid prefix is found

    This approach correctly handles multiline constructs like loops and
    functions that are only complete when a line with lower indentation arrives.
    """

    def __init__(self):
        """Initialize an empty code buffer."""
        self._buffer = ""

    def add_chunk(self, chunk: str):
        """Add a code chunk to the buffer.

        Args:
            chunk: Code chunk to add (may be partial line, full line, or multiple lines)
        """
        self._buffer += chunk

    def get_executable_prefix(self) -> Optional[str]:
        """Find the longest executable prefix in the buffer.

        Uses the indentation-aware algorithm from the specification:
        1. Strip code block markers (```python, ```)
        2. Only consider complete lines (up to last newline)
        3. Split into lines (0 to N)
        4. Walk from bottom to find last non-whitespace-starting line (M)
        5. Try parsing lines[0:M], if not executable try [0:M-1], etc.
        6. Return first prefix that parses successfully

        Returns:
            The longest executable prefix (original code with $var), or None if
            no complete statements are available yet.
        """
        if not self._buffer.strip():
            return None

        # Only consider content up to the last newline
        # Everything after the last newline is incomplete (could be mid-token)
        last_newline_pos = self._buffer.rfind("\n")
        if last_newline_pos == -1:
            # No complete lines yet
            return None

        # Include the newline itself
        buffer_up_to_last_newline = self._buffer[: last_newline_pos + 1]

        # Strip code block markers
        code_to_parse = self._strip_code_block_markers(buffer_up_to_last_newline)

        if not code_to_parse.strip():
            return None

        # Split into lines
        lines = code_to_parse.split("\n")

        # Find the last non-whitespace-starting line (M)
        M = self._find_last_non_whitespace_line(lines)

        if M is None:
            # All lines start with whitespace (or are empty) - nothing executable
            return None

        # Try parsing from M backwards to find executable prefix
        # Special case: if M-1 has higher indentation than M, prefer M-1 (M closes a block)
        # Otherwise, prefer M (flat sequence of statements)
        should_prefer_m_minus_1 = False
        if M > 0:
            # Check if previous non-empty line has indentation
            for i in range(M - 1, -1, -1):
                if lines[i].strip():  # Found a non-empty line
                    if lines[i][0] in (" ", "\t"):
                        # Previous non-empty line is indented, M closes a block
                        should_prefer_m_minus_1 = True
                    break

        for end_idx in range(M, -1, -1):
            # Try M-1 first only if it closes an indented block
            if end_idx == M and M > 0 and should_prefer_m_minus_1:
                # First try without M (just up to M-1)
                prefix_lines = lines[0:M]
                prefix = "\n".join(prefix_lines)
                if prefix.strip() and self._can_parse(prefix):
                    return prefix.rstrip()

            # Now try including this line
            prefix_lines = lines[0 : end_idx + 1]
            prefix = "\n".join(prefix_lines)

            if not prefix.strip():
                continue

            if self._can_parse(prefix):
                # Found executable prefix - return original with proper line ending
                return prefix.rstrip()

        return None

    def consume_prefix(self, prefix: str):
        """Remove an executed prefix from the buffer.

        Args:
            prefix: The code prefix to remove (should match what get_executable_prefix returned)
        """
        if not prefix:
            return

        # Strip code block markers from buffer for comparison
        stripped_buffer = self._strip_code_block_markers(self._buffer)

        # Find where the prefix ends in the stripped buffer
        prefix_stripped = prefix.rstrip()

        if stripped_buffer.startswith(prefix_stripped):
            # Remove the prefix and any trailing newlines that were part of it
            remaining = stripped_buffer[len(prefix_stripped) :]

            # If there's a newline immediately after, consume it too
            if remaining.startswith("\n"):
                remaining = remaining[1:]

            self._buffer = remaining
        else:
            # Fallback: try to find and remove the prefix
            # This handles cases where code block markers might be involved
            if prefix_stripped in self._buffer:
                idx = self._buffer.index(prefix_stripped)
                self._buffer = self._buffer[idx + len(prefix_stripped) :]
                if self._buffer.startswith("\n"):
                    self._buffer = self._buffer[1:]

    def get_buffer(self) -> str:
        """Get the current buffer contents.

        Returns:
            The full buffer including any unexecuted code
        """
        return self._buffer

    def _strip_code_block_markers(self, code: str) -> str:
        """Strip markdown code block markers from code.

        Removes markers like ```python or ``` from the beginning and end.

        Args:
            code: Code potentially wrapped in markdown code block markers

        Returns:
            Code with markers removed
        """
        code = code.strip()

        # Remove opening marker: ``` or ```python or ```python3, etc.
        code = re.sub(r"^```(?:[a-z0-9_-]*)\n?", "", code)

        # Remove closing marker: ```
        code = re.sub(r"\n?```$", "", code)

        return code

    def _find_last_non_whitespace_line(self, lines: list) -> Optional[int]:
        """Find the index of the last line that doesn't start with whitespace.

        This is used to identify where a block might be complete. When an indented
        block is followed by a line with lower indentation, that indicates the
        block is complete.

        Args:
            lines: List of code lines

        Returns:
            Index of the last non-whitespace-starting line, or None if all lines
            start with whitespace (or are empty)
        """
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]
            # Skip empty lines
            if not line.strip():
                continue
            # Check if line starts with whitespace
            if line and line[0] not in (" ", "\t"):
                return i

        return None

    def _can_parse(self, code: str) -> bool:
        """Check if code can be parsed as valid Python and contains actual statements.

        Uses preprocess_program to handle $variable syntax before parsing.
        Only returns True if the code contains at least one executable statement
        (not just comments or empty lines).

        Args:
            code: Code to check

        Returns:
            True if code parses successfully and has statements, False otherwise
        """
        try:
            # Import here to avoid circular dependency
            from playbooks.compilation.expression_engine import preprocess_program

            # Preprocess to handle $variable syntax
            preprocessed = preprocess_program(code)

            # Try to parse
            parsed = ast.parse(preprocessed)

            # Only return True if there's at least one actual statement
            # (not just comments which result in an empty body)
            return len(parsed.body) > 0
        except SyntaxError:
            return False

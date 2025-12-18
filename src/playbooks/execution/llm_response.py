"""LLM response processing and execution.

This module handles the processing of LLM responses, including code execution,
artifact extraction, and integration with the playbook execution environment.
"""

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, Optional

from playbooks.compilation.expression_engine import preprocess_program
from playbooks.execution.python_executor import ExecutionResult, PythonExecutor
from playbooks.infrastructure.event_bus import EventBus
from playbooks.utils.async_init_mixin import AsyncInitMixin

if TYPE_CHECKING:
    from playbooks.agents import LocalAIAgent

logger = logging.getLogger(__name__)


def _strip_code_block_markers(code: str) -> str:
    """Strip markdown code block markers from code.

    Removes markers like ``` or ```python from the beginning and end of code.

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

    return code.strip()


class LLMResponse(AsyncInitMixin):
    """Processes and executes LLM-generated code responses.

    Handles code extraction, preprocessing, metadata parsing, and execution
    of LLM-generated Python code for playbook execution.
    """

    def __init__(
        self, response: str, event_bus: EventBus, agent: "LocalAIAgent"
    ) -> None:
        """Initialize LLM response processor.

        Args:
            response: Raw LLM response containing Python code
            event_bus: Event bus for publishing events
            agent: Agent executing this response
        """
        super().__init__()

        # Defensive: If response is accidentally a list of chunks, concatenate them
        if isinstance(response, list):
            import traceback

            logger.error(
                f"LLMResponse received a list instead of string! "
                f"List has {len(response)} items. First 3 items: {response[:3]}\n"
                f"Call stack:\n{''.join(traceback.format_stack())}"
            )
            response = "".join(response)

        self.response = response
        self.event_bus = event_bus
        self.agent = agent
        self.agent.last_llm_response = self.response
        self.preprocessed_code: Optional[str] = None
        self.execution_result: Optional[ExecutionResult] = None

        # Metadata parsed from comments
        self.execution_id: Optional[int] = None
        self.recap: Optional[str] = None
        self.plan: Optional[str] = None

    async def _async_init(self) -> None:
        """Initialize asynchronously - preprocess code and extract metadata."""
        # Strip code block markers if present
        self.preprocessed_code = _strip_code_block_markers(self.response)

        # Extract execution_id from first line
        self._extract_metadata_from_code(self.preprocessed_code)

        # Preprocess to convert $var syntax to valid Python
        self.preprocessed_code = preprocess_program(self.preprocessed_code)

    def _extract_metadata_from_code(self, code: str) -> None:
        """Extract execution_id, recap, and plan from code comments.

        Expected format:
            # execution_id: N
            # recap: ...
            # plan: ...

        Args:
            code: Code string with metadata comments

        Raises:
            ValueError: If expected comment format is not found
        """
        lines = code.strip().split("\n")

        prefix = "# execution_id:"
        first_line = lines[0].strip()
        if first_line.startswith(prefix):
            self.execution_id = int(first_line[len(prefix) :].strip())
        else:
            raise ValueError(f"First line is not a comment: {first_line}")

        prefix = "# recap:"
        second_line = lines[1].strip()
        if second_line.startswith(prefix):
            self.recap = second_line[len(prefix) :].strip()
        else:
            raise ValueError(f"Second line is not a comment: {second_line}")

        prefix = "# plan:"
        third_line = lines[2].strip()
        if third_line.startswith(prefix):
            self.plan = third_line[len(prefix) :].strip()
        else:
            raise ValueError(f"Third line is not a comment: {third_line}")

    async def execute_generated_code(
        self,
        playbook_args: Optional[Dict[str, Any]] = None,
        execution_result: Optional[ExecutionResult] = None,
    ) -> None:
        """Execute the generated code.

        If an execution_result is provided, uses that (from streaming execution).
        Otherwise, creates a PythonExecutor and executes the preprocessed code.
        The result is stored in self.execution_result. If execution fails,
        the error is captured in the result rather than raising an exception,
        allowing the LLM to see the error and retry with corrected code.

        Args:
            playbook_args: Optional dict of playbook argument names to values
            execution_result: Optional pre-computed ExecutionResult from streaming execution
        """
        if execution_result is not None:
            # Use pre-computed result from streaming execution
            self.execution_result = execution_result
        else:
            # Traditional batch execution (fallback)
            executor = PythonExecutor(self.agent)
            self.execution_result = await executor.execute(
                self.preprocessed_code, playbook_args=playbook_args
            )

    def has_execution_error(self) -> bool:
        """Check if the code execution resulted in an error.

        Returns:
            True if there was a syntax or runtime error during execution
        """
        return self.execution_result is not None and (
            self.execution_result.syntax_error is not None
            or self.execution_result.runtime_error is not None
        )

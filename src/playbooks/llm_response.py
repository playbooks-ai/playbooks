import logging
import re
from typing import TYPE_CHECKING, Optional

from playbooks.event_bus import EventBus
from playbooks.python_executor import ExecutionResult, PythonExecutor
from playbooks.utils.async_init_mixin import AsyncInitMixin
from playbooks.utils.expression_engine import preprocess_program

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
    def __init__(self, response: str, event_bus: EventBus, agent: "LocalAIAgent"):
        super().__init__()
        self.response = response
        self.event_bus = event_bus
        self.agent = agent
        self.agent.state.last_llm_response = self.response
        self.preprocessed_code = None
        self.execution_result: ExecutionResult = None

        # Metadata parsed from comments
        self.execution_id: Optional[int] = None
        self.recap = None
        self.plan = None

    async def _async_init(self):
        # Strip code block markers if present
        self.preprocessed_code = _strip_code_block_markers(self.response)

        # Extract execution_id from first line
        self._extract_metadata_from_code(self.preprocessed_code)

        # Preprocess to convert $var syntax to valid Python
        self.preprocessed_code = preprocess_program(self.preprocessed_code)

    def _extract_metadata_from_code(self, code: str) -> None:
        """Extract execution_id from first line comment in code.

        Expected format: # execution_id: N
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

    async def execute_generated_code(self):
        """Execute the generated code."""
        executor = PythonExecutor(self.agent)
        self.execution_result = await executor.execute(self.preprocessed_code)

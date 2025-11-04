"""Test that LLM can recover from Python execution errors."""

import pytest

from playbooks.python_executor import PythonExecutor
from playbooks.call_stack import CallStack, CallStackFrame, InstructionPointer
from playbooks.event_bus import EventBus
from playbooks.variables import Variables


class MockProgram:
    """Mock program for testing."""

    def __init__(self):
        self._debug_server = None


class MockState:
    """Mock execution state for testing."""

    def __init__(self):
        event_bus = EventBus("test-session")
        self.variables = Variables(event_bus, "test_agent")
        self.call_stack = CallStack(event_bus)
        # Push a dummy frame for testing so Step() calls work
        instruction_pointer = InstructionPointer(
            playbook="TestPlaybook",
            line_number="00",
            source_line_number=0,
        )
        frame = CallStackFrame(instruction_pointer=instruction_pointer)
        self.call_stack.push(frame)


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.id = "test_agent"
        self.klass = "MockAgent"
        self.state = MockState()
        self.playbooks = {}
        self.program = MockProgram()

    def parse_instruction_pointer(self, step: str):
        """Mock parse_instruction_pointer method."""
        parts = step.split(":")
        return InstructionPointer(
            playbook=parts[0] if len(parts) > 0 else "",
            line_number=parts[1] if len(parts) > 1 else "",
            source_line_number=0,
        )


@pytest.mark.asyncio
async def test_syntax_error_captured_not_raised():
    """Test that syntax errors are captured in result, not raised."""
    agent = MockAgent()

    # Create executor
    executor = PythonExecutor(agent)

    # Execute code with syntax error
    bad_code = """
if True
    print("missing colon")
"""

    result = await executor.execute(bad_code)

    # Check that error was captured, not raised
    assert result.syntax_error is not None
    assert result.error_message is not None
    assert "SyntaxError" in result.error_message
    assert result.error_traceback is not None


@pytest.mark.asyncio
async def test_runtime_error_captured_not_raised():
    """Test that runtime errors are captured in result, not raised."""
    agent = MockAgent()

    # Create executor
    executor = PythonExecutor(agent)

    # Execute code with runtime error (division by zero)
    bad_code = """
result = 10 / 0
"""

    result = await executor.execute(bad_code)

    # Check that error was captured, not raised
    assert result.runtime_error is not None
    assert result.error_message is not None
    assert "ZeroDivisionError" in result.error_message
    assert result.error_traceback is not None


@pytest.mark.asyncio
async def test_successful_execution_no_error():
    """Test that successful execution doesn't set error fields."""
    agent = MockAgent()

    # Create executor
    executor = PythonExecutor(agent)

    # Execute valid code
    good_code = """
result = 10 / 2
"""

    result = await executor.execute(good_code)

    # Check that no errors were set
    assert result.syntax_error is None
    assert result.runtime_error is None
    assert result.error_message is None
    assert result.error_traceback is None

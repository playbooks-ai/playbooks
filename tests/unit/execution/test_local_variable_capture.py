"""Tests for local variable capture in PythonExecutor.

These tests document that PythonExecutor does NOT currently capture local
variables to CallStackFrame.locals because it wraps code in a function.
StreamingPythonExecutor (used in actual playbook execution) DOES capture locals.

These tests serve as documentation of the current behavior and as regression tests.
"""

import pytest
from box import Box

from playbooks.execution.python_executor import PythonExecutor
from playbooks.execution.streaming_python_executor import StreamingPythonExecutor
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer


class MockProgram:
    """Mock program for testing."""

    def __init__(self):
        self._debug_server = None
        self.execution_finished = False


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.id = "test_agent"
        self.klass = "MockAgent"

        # Set up state matching the architecture
        event_bus = EventBus("test-session")
        self._variables_internal = Box()
        self.call_stack = CallStack(event_bus)
        # Push a dummy frame for testing
        instruction_pointer = InstructionPointer(
            playbook="TestPlaybook",
            line_number="00",
            source_line_number=0,
        )
        frame = CallStackFrame(instruction_pointer=instruction_pointer)
        self.call_stack.push(frame)

        self.playbooks = {}
        self.program = None

    def get_current_meeting(self):
        """Mock get_current_meeting method."""
        return None
        self.program = MockProgram()

    @property
    def state(self):
        """Return variables Box."""
        return self._variables_internal

    def parse_instruction_pointer(self, step: str):
        """Mock parse_instruction_pointer method."""
        parts = step.split(":")
        return InstructionPointer(
            playbook=parts[0] if len(parts) > 0 else "",
            line_number=parts[1] if len(parts) > 1 else "",
            source_line_number=0,
            step=parts[2] if len(parts) > 2 else None,
        )

    def resolve_target(self, target: str, allow_fallback: bool = True) -> str:
        """Mock resolve_target method."""
        return target

    async def WaitForMessage(self, target: str):
        """Mock WaitForMessage method."""
        pass

    async def Say(self, target: str, message: str):
        """Mock Say method."""
        pass

    @property
    def _current_executor(self):
        """Get the current executor from the top call stack frame."""
        current_frame = self.call_stack.peek()
        if (
            not current_frame
            or not hasattr(current_frame, "executor")
            or current_frame.executor is None
        ):
            raise RuntimeError("Called outside of code execution context")
        return current_frame.executor

    async def Step(self, location: str):
        """Mock Step method that delegates to executor."""
        await self._current_executor.capture_step(location)


@pytest.fixture
def mock_agent():
    """Fixture to create a mock agent."""
    return MockAgent()


@pytest.fixture
def executor(mock_agent):
    """Fixture to create a PythonExecutor instance."""
    return PythonExecutor(mock_agent)


class TestPythonExecutorDoesNotCaptureLocals:
    """Document that PythonExecutor does NOT capture locals (by design)."""

    @pytest.mark.asyncio
    async def test_python_executor_does_not_capture_simple_local(self, executor):
        """Document that PythonExecutor does NOT capture local variables to frame.locals.

        This is because PythonExecutor wraps code in a function where variables
        are local to that function scope. The actual playbook execution uses
        StreamingPythonExecutor which DOES capture locals.
        """
        code = "x = 5"
        result = await executor.execute(code)

        # Verify no errors
        assert result.error_message is None

        # Document that frame.locals is NOT updated (this is current behavior)
        frame = executor.agent.call_stack.peek()
        assert frame is not None
        assert "x" not in frame.locals  # NOT captured in PythonExecutor


class TestStreamingExecutorCapturesLocals:
    """Test that StreamingPythonExecutor DOES capture locals (actual playbook execution)."""

    @pytest.mark.asyncio
    async def test_streaming_simple_local_capture(self, mock_agent):
        """Test that StreamingPythonExecutor captures local variables."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("x = 5\n")
        result = await executor.finalize()

        assert result.error_message is None

        # StreamingPythonExecutor DOES capture locals
        frame = mock_agent.call_stack.peek()
        assert "x" in frame.locals
        assert frame.locals["x"] == 5

    @pytest.mark.asyncio
    async def test_streaming_multiple_variables(self, mock_agent):
        """Test that multiple variables are captured in streaming mode."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("x = 5\n")
        await executor.add_chunk("y = 10\n")
        await executor.add_chunk("name = 'Alice'\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["x"] == 5
        assert frame.locals["y"] == 10
        assert frame.locals["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_streaming_variable_arithmetic(self, mock_agent):
        """Test arithmetic operations between local variables."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("a = 10\n")
        await executor.add_chunk("b = 20\n")
        await executor.add_chunk("c = a + b\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["a"] == 10
        assert frame.locals["b"] == 20
        assert frame.locals["c"] == 30

    @pytest.mark.asyncio
    async def test_streaming_locals_and_state(self, mock_agent):
        """Test that local and state variables can coexist."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("x = 5\n")
        await executor.add_chunk("self.state.y = 10\n")
        await executor.add_chunk("z = x + self.state.y\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["x"] == 5
        assert frame.locals["z"] == 15
        assert mock_agent.state.y == 10

    @pytest.mark.asyncio
    async def test_streaming_playbook_args(self, mock_agent):
        """Test playbook arguments with streaming executor."""
        playbook_args = {"order_id": "12345"}
        executor = StreamingPythonExecutor(mock_agent, playbook_args=playbook_args)

        await executor.add_chunk("total = 99.99\n")
        await executor.add_chunk("message = f'Order {order_id}'\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["order_id"] == "12345"
        assert frame.locals["total"] == 99.99
        assert "Order 12345" in frame.locals["message"]

    @pytest.mark.asyncio
    async def test_streaming_loops(self, mock_agent):
        """Test simple list comprehension (works better than loops with exec)."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("numbers = [x for x in range(5)]\n")
        await executor.add_chunk("total = sum(numbers)\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["numbers"] == [0, 1, 2, 3, 4]
        assert frame.locals["total"] == 10

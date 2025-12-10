"""Tests for local variable persistence across multiple LLM calls.

These tests verify that local variables stored in CallStackFrame.locals persist
across multiple code executions within the same playbook execution context.
This simulates the behavior when a playbook yields (e.g., for user input) and
then resumes execution.

Note: Uses StreamingPythonExecutor which is used in actual playbook execution
and properly captures locals.
"""

import pytest

from playbooks.execution.streaming_python_executor import StreamingPythonExecutor
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer
from playbooks.state.variables import PlaybookDotMap


class MockProgram:
    """Mock program for testing."""

    def __init__(self):
        self._debug_server = None


class MockAgent:
    """Mock agent for testing."""

    def __init__(self):
        self.id = "test_agent"
        self.klass = "MockAgent"

        # Set up state matching the architecture
        event_bus = EventBus("test-session")
        self._variables_internal = PlaybookDotMap()
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
        self.program = MockProgram()

    @property
    def state(self):
        """Return variables DotMap."""
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


class TestLocalVariablePersistence:
    """Test that local variables persist in the call stack frame."""

    @pytest.mark.asyncio
    async def test_local_variable_persists_in_frame(self, mock_agent):
        """Test that local variables remain in frame.locals after execution."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("x = 42\n")
        await executor.add_chunk('name = "Test"\n')
        result = await executor.finalize()

        assert result.error_message is None

        # Verify variables persist in frame after execution completes
        frame = mock_agent.call_stack.peek()
        assert frame is not None
        assert "x" in frame.locals
        assert frame.locals["x"] == 42
        assert "name" in frame.locals
        assert frame.locals["name"] == "Test"

    @pytest.mark.asyncio
    async def test_frame_locals_survive_yield_simulation(self, mock_agent):
        """Test that frame locals survive when frame stays on stack (simulating yield)."""
        # First execution - define variables
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("counter = 5\n")
        await executor1.add_chunk('status = "active"\n')
        await executor1.finalize()

        # Verify frame is still on stack
        frame = mock_agent.call_stack.peek()
        assert frame is not None

        # Verify locals are still there (simulating time between yield and resume)
        assert "counter" in frame.locals
        assert frame.locals["counter"] == 5
        assert "status" in frame.locals
        assert frame.locals["status"] == "active"


class TestVariableAvailabilityAcrossCalls:
    """Test that variables from previous executions are available in subsequent ones."""

    @pytest.mark.asyncio
    async def test_local_variable_available_after_frame_persistence(self, mock_agent):
        """Test that local variables defined in one execution are available in the next."""
        # First execution - define variable
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("x = 10\n")
        await executor1.finalize()

        # Second execution - use the variable from first execution
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("y = x + 5\n")
        await executor2.add_chunk("result = x * y\n")
        result = await executor2.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["x"] == 10
        assert frame.locals["y"] == 15
        assert frame.locals["result"] == 150

    @pytest.mark.asyncio
    async def test_multiple_llm_calls_accumulate_locals(self, mock_agent):
        """Test that multiple executions accumulate local variables."""
        # First call
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("a = 1\n")
        await executor1.finalize()

        # Second call
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("b = 2\n")
        await executor2.finalize()

        # Third call
        executor3 = StreamingPythonExecutor(mock_agent)
        await executor3.add_chunk("c = 3\n")
        await executor3.finalize()

        # Fourth call - use all previous variables
        executor4 = StreamingPythonExecutor(mock_agent)
        await executor4.add_chunk("total = a + b + c\n")
        result = await executor4.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["a"] == 1
        assert frame.locals["b"] == 2
        assert frame.locals["c"] == 3
        assert frame.locals["total"] == 6

    @pytest.mark.asyncio
    async def test_playbook_args_persist_with_other_locals(self, mock_agent):
        """Test that playbook arguments and subsequent locals all persist."""
        playbook_args = {"user_id": "user123", "session_id": "abc"}

        # First call with playbook args
        executor1 = StreamingPythonExecutor(mock_agent, playbook_args=playbook_args)
        await executor1.add_chunk("count = 0\n")
        await executor1.add_chunk('status = "initialized"\n')
        await executor1.finalize()

        # Second call - all should be available
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("count = count + 1\n")
        await executor2.add_chunk(
            'message = f"User {user_id} in session {session_id}: {status}"\n'
        )
        result = await executor2.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        # Original args
        assert frame.locals["user_id"] == "user123"
        assert frame.locals["session_id"] == "abc"
        # Variables from first call
        assert frame.locals["status"] == "initialized"
        # Modified in second call
        assert frame.locals["count"] == 1
        assert "User user123" in frame.locals["message"]


class TestVariableModification:
    """Test modification of local variables across multiple calls."""

    @pytest.mark.asyncio
    async def test_local_variable_modification_across_calls(self, mock_agent):
        """Test that local variables can be modified across multiple executions."""
        # First call - initialize
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("counter = 0\n")
        await executor1.finalize()

        # Second call - increment
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("counter = counter + 1\n")
        await executor2.finalize()

        # Third call - increment again
        executor3 = StreamingPythonExecutor(mock_agent)
        await executor3.add_chunk("counter = counter + 1\n")
        await executor3.finalize()

        # Fourth call - double it
        executor4 = StreamingPythonExecutor(mock_agent)
        await executor4.add_chunk("counter = counter * 2\n")
        result = await executor4.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["counter"] == 4  # (0 + 1 + 1) * 2

    @pytest.mark.asyncio
    async def test_local_variable_type_change_across_calls(self, mock_agent):
        """Test that local variables can change type across calls."""
        # First call - string
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("value = 'hello'\n")
        await executor1.finalize()

        frame = mock_agent.call_stack.peek()
        assert frame.locals["value"] == "hello"

        # Second call - change to number
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("value = 42\n")
        await executor2.finalize()

        frame = mock_agent.call_stack.peek()
        assert frame.locals["value"] == 42

        # Third call - change to list
        executor3 = StreamingPythonExecutor(mock_agent)
        await executor3.add_chunk("value = [1, 2, 3]\n")
        result = await executor3.finalize()

        assert result.error_message is None
        frame = mock_agent.call_stack.peek()
        assert frame.locals["value"] == [1, 2, 3]


class TestStateAndLocalPersistence:
    """Test that both state and local variables persist correctly."""

    @pytest.mark.asyncio
    async def test_state_and_local_variables_both_persist(self, mock_agent):
        """Test that state variables and local variables both persist independently."""
        # First call - set both types
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("local_count = 5\n")
        await executor1.add_chunk("self.state.state_count = 10\n")
        await executor1.finalize()

        # Second call - use and modify both
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("local_count = local_count + 1\n")
        await executor2.add_chunk(
            "self.state.state_count = self.state.state_count + 1\n"
        )
        await executor2.add_chunk("total = local_count + self.state.state_count\n")
        result = await executor2.finalize()

        assert result.error_message is None

        # Check local variables
        frame = mock_agent.call_stack.peek()
        assert frame.locals["local_count"] == 6
        assert frame.locals["total"] == 17

        # Check state variables
        assert mock_agent.state.state_count == 11

    @pytest.mark.asyncio
    async def test_locals_dont_affect_state_and_vice_versa(self, mock_agent):
        """Test that local and state variables with different names don't interfere."""
        # First call
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("x = 100\n")
        await executor1.add_chunk("self.state.y = 200\n")
        await executor1.finalize()

        # Second call - modify one of each
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("x = x * 2\n")
        await executor2.add_chunk("self.state.z = 300\n")
        await executor2.finalize()

        # Third call - verify all are still accessible
        executor3 = StreamingPythonExecutor(mock_agent)
        await executor3.add_chunk("result = x + self.state.y + self.state.z\n")
        result = await executor3.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["x"] == 200
        assert frame.locals["result"] == 700
        assert mock_agent.state.y == 200
        assert mock_agent.state.z == 300


class TestComplexPersistenceScenarios:
    """Test complex scenarios involving variable persistence."""

    @pytest.mark.asyncio
    async def test_accumulating_list_across_calls(self, mock_agent):
        """Test that a list can be built up across multiple calls."""
        # Initialize empty list
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("items = []\n")
        await executor1.finalize()

        # Add items in subsequent calls
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("items.append('first')\n")
        await executor2.finalize()

        executor3 = StreamingPythonExecutor(mock_agent)
        await executor3.add_chunk("items.append('second')\n")
        await executor3.finalize()

        executor4 = StreamingPythonExecutor(mock_agent)
        await executor4.add_chunk("items.append('third')\n")
        result = await executor4.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["items"] == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_building_dict_across_calls(self, mock_agent):
        """Test that a dictionary can be built across multiple calls."""
        # Initialize
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("config = {}\n")
        await executor1.finalize()

        # Add entries
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("config['host'] = 'localhost'\n")
        await executor2.finalize()

        executor3 = StreamingPythonExecutor(mock_agent)
        await executor3.add_chunk("config['port'] = 8080\n")
        await executor3.finalize()

        executor4 = StreamingPythonExecutor(mock_agent)
        await executor4.add_chunk("config['debug'] = True\n")
        result = await executor4.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["config"] == {
            "host": "localhost",
            "port": 8080,
            "debug": True,
        }

    @pytest.mark.asyncio
    async def test_complex_computation_across_calls(self, mock_agent):
        """Test a multi-step computation split across calls."""
        # Step 1: Initialize
        executor1 = StreamingPythonExecutor(mock_agent)
        await executor1.add_chunk("numbers = [1, 2, 3, 4, 5]\n")
        await executor1.finalize()

        # Step 2: Compute sum
        executor2 = StreamingPythonExecutor(mock_agent)
        await executor2.add_chunk("total = sum(numbers)\n")
        await executor2.finalize()

        # Step 3: Calculate average
        executor3 = StreamingPythonExecutor(mock_agent)
        await executor3.add_chunk("average = total / len(numbers)\n")
        await executor3.finalize()

        # Step 4: Simple computation
        executor4 = StreamingPythonExecutor(mock_agent)
        await executor4.add_chunk("doubled = average * 2\n")
        result = await executor4.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["total"] == 15
        assert frame.locals["average"] == 3.0
        assert frame.locals["doubled"] == 6.0

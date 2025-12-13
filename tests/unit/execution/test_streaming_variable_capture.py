"""Tests for local variable capture in StreamingPythonExecutor.

These tests verify that local variables are properly captured and stored in
CallStackFrame.locals during incremental code execution as chunks arrive.
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
        self.execution_finished = False


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
        self.namespace_manager = None

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


class TestStreamingSimpleCapture:
    """Test basic variable capture in streaming mode."""

    @pytest.mark.asyncio
    async def test_streaming_simple_local_capture(self, mock_agent):
        """Test that a simple local variable is captured in streaming mode."""
        executor = StreamingPythonExecutor(mock_agent)

        # Add code as a single chunk with newline
        await executor.add_chunk("x = 5\n")
        result = await executor.finalize()

        assert result.error_message is None

        # Verify variable is captured
        frame = mock_agent.call_stack.peek()
        assert "x" in frame.locals
        assert frame.locals["x"] == 5

    @pytest.mark.asyncio
    async def test_streaming_multiple_statements_capture(self, mock_agent):
        """Test that multiple statements each create captured variables."""
        executor = StreamingPythonExecutor(mock_agent)

        # Add statements as separate chunks
        await executor.add_chunk("x = 10\n")
        await executor.add_chunk("y = 20\n")
        await executor.add_chunk("z = x + y\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["x"] == 10
        assert frame.locals["y"] == 20
        assert frame.locals["z"] == 30


class TestStreamingAsyncCapture:
    """Test variable capture from async statements in streaming mode."""

    @pytest.mark.asyncio
    async def test_streaming_async_await_variable_capture(self, mock_agent):
        """Test that variables from statements with await are captured."""
        executor = StreamingPythonExecutor(mock_agent)

        # Add async statements
        await executor.add_chunk("await self.Step('Test:01:QUE')\n")
        await executor.add_chunk("x = 42\n")
        await executor.add_chunk("await self.Step('Test:02:QUE')\n")
        await executor.add_chunk("y = x + 1\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["x"] == 42
        assert frame.locals["y"] == 43

    @pytest.mark.asyncio
    async def test_streaming_sync_and_async_mixed(self, mock_agent):
        """Test that both sync and async statements capture variables correctly."""
        executor = StreamingPythonExecutor(mock_agent)

        # Mix of sync and async
        await executor.add_chunk("count = 0\n")
        await executor.add_chunk("await self.Step('Test:01:QUE')\n")
        await executor.add_chunk("count = count + 1\n")
        await executor.add_chunk("name = 'Alice'\n")
        await executor.add_chunk("await self.Step('Test:02:QUE')\n")
        await executor.add_chunk("message = f'{name}: {count}'\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["count"] == 1
        assert frame.locals["name"] == "Alice"
        assert frame.locals["message"] == "Alice: 1"


class TestStreamingChunkBehavior:
    """Test how variables are captured as chunks arrive."""

    @pytest.mark.asyncio
    async def test_streaming_local_available_in_later_chunk(self, mock_agent):
        """Test that variables defined in early chunks are available in later ones."""
        executor = StreamingPythonExecutor(mock_agent)

        # First chunk defines variable
        await executor.add_chunk("base = 100\n")

        # Verify it's already in frame.locals
        frame = mock_agent.call_stack.peek()
        assert "base" in frame.locals
        assert frame.locals["base"] == 100

        # Second chunk uses it
        await executor.add_chunk("multiplier = 2\n")
        await executor.add_chunk("result = base * multiplier\n")
        result = await executor.finalize()

        assert result.error_message is None
        assert frame.locals["result"] == 200

    @pytest.mark.asyncio
    async def test_streaming_frame_locals_updated_incrementally(self, mock_agent):
        """Test that frame.locals grows incrementally as statements execute."""
        executor = StreamingPythonExecutor(mock_agent)
        frame = mock_agent.call_stack.peek()

        # Initially empty (except any setup)
        initial_count = len(frame.locals)

        # Add first variable
        await executor.add_chunk("a = 1\n")
        assert len(frame.locals) == initial_count + 1
        assert "a" in frame.locals

        # Add second variable
        await executor.add_chunk("b = 2\n")
        assert len(frame.locals) == initial_count + 2
        assert "b" in frame.locals

        # Add third variable
        await executor.add_chunk("c = 3\n")
        assert len(frame.locals) == initial_count + 3
        assert "c" in frame.locals

        result = await executor.finalize()
        assert result.error_message is None


class TestStreamingWithPlaybookArgs:
    """Test interaction between playbook arguments and streaming locals."""

    @pytest.mark.asyncio
    async def test_streaming_playbook_args_with_locals(self, mock_agent):
        """Test that playbook args and streaming-defined locals both exist."""
        playbook_args = {
            "user_id": "123",
            "config": {"debug": True},
        }

        executor = StreamingPythonExecutor(mock_agent, playbook_args=playbook_args)

        # Add code that uses args and creates new locals
        await executor.add_chunk("counter = 0\n")
        await executor.add_chunk("message = f'User {user_id} initialized'\n")
        await executor.add_chunk("is_debug = config['debug']\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()

        # Check playbook args are in locals
        assert frame.locals["user_id"] == "123"
        assert frame.locals["config"] == {"debug": True}

        # Check new locals
        assert frame.locals["counter"] == 0
        assert "User 123" in frame.locals["message"]
        assert frame.locals["is_debug"] is True

    @pytest.mark.asyncio
    async def test_streaming_modify_playbook_args(self, mock_agent):
        """Test that playbook arguments can be modified in streaming execution."""
        playbook_args = {"count": 5}

        executor = StreamingPythonExecutor(mock_agent, playbook_args=playbook_args)

        await executor.add_chunk("count = count + 10\n")
        await executor.add_chunk("doubled = count * 2\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["count"] == 15
        assert frame.locals["doubled"] == 30


class TestStreamingComplexScenarios:
    """Test complex streaming scenarios."""

    @pytest.mark.asyncio
    async def test_streaming_with_loops(self, mock_agent):
        """Test list comprehensions and built-in functions (work better than loops)."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("numbers = list(range(5))\n")
        await executor.add_chunk("doubled = [x * 2 for x in numbers]\n")
        await executor.add_chunk("total = sum(doubled)\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["numbers"] == [0, 1, 2, 3, 4]
        assert frame.locals["doubled"] == [0, 2, 4, 6, 8]
        assert frame.locals["total"] == 20

    @pytest.mark.asyncio
    async def test_streaming_with_conditionals(self, mock_agent):
        """Test variable capture with conditional statements."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("x = 15\n")
        await executor.add_chunk("if x > 10:\n")
        await executor.add_chunk("    status = 'high'\n")
        await executor.add_chunk("else:\n")
        await executor.add_chunk("    status = 'low'\n")
        await executor.add_chunk("\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["x"] == 15
        assert frame.locals["status"] == "high"

    @pytest.mark.asyncio
    async def test_streaming_with_function_definitions(self, mock_agent):
        """Test that function definitions and their use are captured."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("def multiply(a, b):\n")
        await executor.add_chunk("    return a * b\n")
        await executor.add_chunk("\n")
        await executor.add_chunk("result = multiply(6, 7)\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert "multiply" in frame.locals
        assert callable(frame.locals["multiply"])
        assert frame.locals["result"] == 42

    @pytest.mark.asyncio
    async def test_streaming_with_collections(self, mock_agent):
        """Test streaming capture of collection types."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("my_list = []\n")
        await executor.add_chunk("my_list.append(1)\n")
        await executor.add_chunk("my_list.append(2)\n")
        await executor.add_chunk("my_dict = {'key': 'value'}\n")
        await executor.add_chunk("my_dict['count'] = len(my_list)\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["my_list"] == [1, 2]
        assert frame.locals["my_dict"] == {"key": "value", "count": 2}


class TestStreamingPartialChunks:
    """Test handling of partial chunks (code split mid-token)."""

    @pytest.mark.asyncio
    async def test_streaming_variable_name_split_across_chunks(self, mock_agent):
        """Test that variable names split across chunks still work."""
        executor = StreamingPythonExecutor(mock_agent)

        # Simulate streaming where variable name is split
        await executor.add_chunk("long")
        await executor.add_chunk("_variable")
        await executor.add_chunk("_name = ")
        await executor.add_chunk("42\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert "long_variable_name" in frame.locals
        assert frame.locals["long_variable_name"] == 42

    @pytest.mark.asyncio
    async def test_streaming_multiline_string_across_chunks(self, mock_agent):
        """Test that multiline strings split across chunks work correctly."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk('text = """This is\n')
        await executor.add_chunk("a multiline\n")
        await executor.add_chunk('string"""\n')
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert "text" in frame.locals
        assert "multiline" in frame.locals["text"]

    @pytest.mark.asyncio
    async def test_streaming_expression_across_chunks(self, mock_agent):
        """Test that expressions split across chunks execute correctly."""
        executor = StreamingPythonExecutor(mock_agent)

        await executor.add_chunk("x = 10\n")
        await executor.add_chunk("y = 20\n")
        await executor.add_chunk("result = x")
        await executor.add_chunk(" + ")
        await executor.add_chunk("y")
        await executor.add_chunk(" * 2\n")
        result = await executor.finalize()

        assert result.error_message is None

        frame = mock_agent.call_stack.peek()
        assert frame.locals["result"] == 50  # 10 + (20 * 2)

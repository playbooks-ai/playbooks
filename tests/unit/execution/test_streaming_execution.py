"""Integration tests for streaming code execution.

Tests the full flow of streaming execution in playbook contexts.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from playbooks.execution.streaming_python_executor import StreamingPythonExecutor


class TestStreamingExecutionIntegration:
    """Integration tests for streaming execution in playbook context."""

    @pytest.fixture
    def mock_agent(self):
        """Create a comprehensive mock agent."""
        agent = Mock()
        agent.id = "test_agent"
        agent.klass = "TestAgent"
        agent.state = Mock()

        # Create a dict-like mock for variables that supports 'in' operator
        variables_dict = {}
        agent.state.variables = Mock()
        agent.state.variables.to_dict = Mock(return_value=variables_dict)
        agent.state.variables.__setitem__ = Mock(
            side_effect=lambda name, value, **kwargs: variables_dict.__setitem__(
                name, value
            )
        )
        agent.state.variables.__contains__ = Mock(
            side_effect=lambda k: k in variables_dict
        )
        agent.state.variables.__getitem__ = Mock(
            side_effect=lambda k: variables_dict[k]
        )

        agent.state.call_stack = Mock()
        agent.state.call_stack.peek = Mock(
            return_value=Mock(langfuse_span=None, instruction_pointer=Mock())
        )
        agent.state.call_stack.advance_instruction_pointer = Mock()
        agent.state.call_stack.add_llm_message = Mock()
        agent.state.event_bus = Mock()
        agent.program = Mock()
        agent.program._debug_server = None
        agent.program.agents = []
        agent.program.agent_klasses = []  # Fix for agent_proxy iteration
        agent.playbooks = {}
        agent.parse_instruction_pointer = Mock(return_value=Mock(step="EXE"))
        agent.resolve_target = Mock(return_value="test_target")
        return agent

    @pytest.mark.asyncio
    async def test_streaming_execution_correctness(self, mock_agent):
        """Test that streaming execution produces correct results."""
        code = """x = 10
y = 20
result = x + y
"""

        # Execute with streaming executor
        streaming_executor = StreamingPythonExecutor(mock_agent)
        for line in code.split("\n"):
            if line.strip():
                await streaming_executor.add_chunk(line + "\n")
        _streaming_result = await streaming_executor.finalize()

        # Verify results are correct
        assert streaming_executor.namespace["x"] == 10
        assert streaming_executor.namespace["y"] == 20
        assert streaming_executor.namespace["result"] == 30

    @pytest.mark.asyncio
    async def test_streaming_with_step_calls(self, mock_agent):
        """Test streaming execution with Step() calls."""
        streaming_executor = StreamingPythonExecutor(mock_agent)

        code = """await Step("TEST:01:EXE")
x = 10
await Step("TEST:02:EXE")
y = 20
"""

        for line in code.split("\n"):
            if line.strip():
                await streaming_executor.add_chunk(line + "\n")

        result = await streaming_executor.finalize()

        # Verify Step calls were made
        assert len(result.steps) == 2
        assert result.vars["x"] == 10
        assert result.vars["y"] == 20

    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, mock_agent):
        """Test that errors are properly propagated for LLM retry."""
        streaming_executor = StreamingPythonExecutor(mock_agent)

        # Execute code that will fail
        await streaming_executor.add_chunk("x = 10\n")

        try:
            await streaming_executor.add_chunk("y = undefined_var\n")
            await streaming_executor.add_chunk("z = 30\n")
        except Exception:
            pass

        result = await streaming_executor.finalize()

        # Should have error information
        assert result.runtime_error is not None
        assert result.error_message is not None

        # Should have executed code up to error
        assert "x" in result.vars
        assert "z" not in result.vars

        # Executed code should be truncated
        executed_code = streaming_executor.get_executed_code()
        assert "x = 10" in executed_code
        assert "z = 30" not in executed_code

    @pytest.mark.asyncio
    async def test_variable_state_updates(self, mock_agent):
        """Test that variables are properly stored in agent state."""
        streaming_executor = StreamingPythonExecutor(mock_agent)

        await streaming_executor.add_chunk("user_name = 'Alice'\n")
        await streaming_executor.add_chunk("user_age = 30\n")

        result = await streaming_executor.finalize()

        # Verify variables were captured
        assert result.vars["user_name"] == "Alice"
        assert result.vars["user_age"] == 30

        # Verify state was updated (via mock)
        assert mock_agent.state.variables.__setitem__.called

    @pytest.mark.asyncio
    async def test_complex_code_streaming(self, mock_agent):
        """Test streaming execution with complex Python constructs."""
        streaming_executor = StreamingPythonExecutor(mock_agent)

        code = """# Simple function
def double(x):
    return x * 2

def add_ten(x):
    return x + 10

# Use the functions
a = double(5)
b = add_ten(15)
result = a + b
"""

        for line in code.split("\n"):
            await streaming_executor.add_chunk(line + "\n")

        _result = await streaming_executor.finalize()

        # Verify functions were defined and executed correctly
        assert streaming_executor.namespace["a"] == 10
        assert streaming_executor.namespace["b"] == 25
        assert streaming_executor.namespace["result"] == 35

    @pytest.mark.asyncio
    async def test_incremental_chunk_sizes(self, mock_agent):
        """Test that different chunk sizes produce same results."""
        code = "x = 10; y = 20; z = x + y"

        # Test with character-by-character chunks (will only parse when \n is seen)
        executor1 = StreamingPythonExecutor(mock_agent)
        for char in code:
            await executor1.add_chunk(char)
        await executor1.add_chunk("\n")
        _result1 = await executor1.finalize()

        # Test with line-at-once
        # Create a fresh mock agent for isolation
        variables_dict2 = {}
        mock_agent2 = Mock()
        mock_agent2.id = "test_agent2"
        mock_agent2.klass = "TestAgent"
        mock_agent2.state = Mock()
        mock_agent2.state.variables = Mock()
        mock_agent2.state.variables.to_dict = Mock(return_value=variables_dict2)
        mock_agent2.state.variables.__setitem__ = Mock(
            side_effect=lambda name, value, **kwargs: variables_dict2.__setitem__(
                name, value
            )
        )
        mock_agent2.state.variables.__contains__ = Mock(
            side_effect=lambda k: k in variables_dict2
        )
        mock_agent2.state.variables.__getitem__ = Mock(
            side_effect=lambda k: variables_dict2[k]
        )
        mock_agent2.state.call_stack = mock_agent.state.call_stack
        mock_agent2.state.event_bus = mock_agent.state.event_bus
        mock_agent2.program = mock_agent.program
        mock_agent2.playbooks = {}
        mock_agent2.parse_instruction_pointer = mock_agent.parse_instruction_pointer

        executor2 = StreamingPythonExecutor(mock_agent2)
        await executor2.add_chunk(code + "\n")
        _result2 = await executor2.finalize()

        # Results should be equivalent (check namespace directly)
        assert executor1.namespace["z"] == 30
        assert executor2.namespace["z"] == 30

    @pytest.mark.asyncio
    async def test_streaming_with_playbook_args(self, mock_agent):
        """Test that playbook arguments work correctly in streaming execution."""
        playbook_args = {"input_value": 100, "multiplier": 3}

        streaming_executor = StreamingPythonExecutor(
            mock_agent, playbook_args=playbook_args
        )

        await streaming_executor.add_chunk("result = input_value * multiplier\n")

        result = await streaming_executor.finalize()

        assert result.vars["result"] == 300

    @pytest.mark.asyncio
    async def test_namespace_continuity(self, mock_agent):
        """Test that namespace is preserved across statement executions."""
        streaming_executor = StreamingPythonExecutor(mock_agent)

        # Define a function in one chunk
        await streaming_executor.add_chunk("def square(x):\n")
        await streaming_executor.add_chunk("    return x * x\n")
        await streaming_executor.add_chunk("\n")

        # Use it in another chunk
        await streaming_executor.add_chunk("result = square(7)\n")

        result = await streaming_executor.finalize()

        assert result.vars["result"] == 49

    @pytest.mark.asyncio
    async def test_mixed_sync_async_statements(self, mock_agent):
        """Test execution of mixed sync and async statements."""
        streaming_executor = StreamingPythonExecutor(mock_agent)

        # Add async mock
        mock_step = AsyncMock()
        streaming_executor.namespace["Step"] = mock_step

        await streaming_executor.add_chunk("x = 10\n")
        await streaming_executor.add_chunk('await Step("TEST:01:EXE")\n')
        await streaming_executor.add_chunk("y = x + 5\n")
        await streaming_executor.add_chunk('await Step("TEST:02:EXE")\n')
        await streaming_executor.add_chunk("z = y * 2\n")

        result = await streaming_executor.finalize()

        assert result.vars["x"] == 10
        assert result.vars["y"] == 15
        assert result.vars["z"] == 30
        assert mock_step.call_count == 2

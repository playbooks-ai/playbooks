"""Test error handling when a non-existent playbook is called mid-execution.

This test covers the scenario where:
1. Multiple steps execute successfully
2. A playbook call to a non-existent playbook fails
3. Execution is aborted at the correct point
4. Call stack is at the correct Step
5. LLM message history is set up correctly for retry
"""

from unittest.mock import AsyncMock, Mock

import pytest

from playbooks.execution.streaming_python_executor import (
    StreamingExecutionError,
    StreamingPythonExecutor,
)
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer


class TestPlaybookNotFoundError:
    """Test suite for playbook not found errors during execution."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        agent = Mock()
        agent.id = "test_agent"
        agent.klass = "TestAgent"
        agent.state = Mock()

        # Create a dict-like mock for variables
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

        # Create call stack
        event_bus = EventBus("test_session")
        agent.state.call_stack = CallStack(event_bus)
        agent.state.event_bus = event_bus
        agent.program = Mock()
        agent.program._debug_server = None
        agent.program.agents = []
        agent.program.agent_klasses = []
        agent.playbooks = {}
        agent.parse_instruction_pointer = Mock(return_value=Mock(step="EXE"))

        # Track playbook calls for verification
        agent.playbook_calls = []

        # Mock execute_playbook to handle both success and failure
        async def mock_execute_playbook(playbook_name, args, kwargs):
            # Track all calls
            agent.playbook_calls.append(
                {"name": playbook_name, "args": args, "kwargs": kwargs}
            )

            if "GoodPlaybook" in playbook_name:
                return (True, "success")
            elif "PlaybookDoesNotExist" in playbook_name:
                return (
                    False,
                    f"Playbook '{playbook_name}' not found in agent 'TestAgent' or any registered agents",
                )
            else:
                return (True, None)

        agent.execute_playbook = mock_execute_playbook

        return agent

    @pytest.fixture
    def executor(self, mock_agent):
        """Create a StreamingPythonExecutor instance for testing."""
        return StreamingPythonExecutor(mock_agent, playbook_args=None)

    @pytest.mark.asyncio
    async def test_playbook_not_found_returns_error_string(self, executor, mock_agent):
        """Test that calling a non-existent playbook returns an error string.

        This test documents the CURRENT behavior: failed playbook calls
        return "ERROR: ..." strings rather than raising exceptions, so
        execution continues past the error.

        Scenario:
        - PB:02:EXE was executed
        - LLM generates code with multiple steps
        - await GoodPlaybook(x) executes successfully
        - await PlaybookDoesNotExist() returns "ERROR: ..." string

        Current behavior:
        - Execution continues (no exception raised)
        - The error string is the return value
        - Subsequent code still executes
        """
        # Mock Step function
        step_mock = AsyncMock()
        executor.namespace["Step"] = step_mock

        # Mock Yld function to avoid the parse error
        yld_mock = AsyncMock()
        executor.namespace["Yld"] = yld_mock

        # Create playbook wrappers in namespace
        from playbooks.agent_proxy import create_playbook_wrapper

        executor.namespace["GoodPlaybook"] = create_playbook_wrapper(
            "GoodPlaybook", mock_agent, executor.namespace
        )
        executor.namespace["PlaybookDoesNotExist"] = create_playbook_wrapper(
            "PlaybookDoesNotExist", mock_agent, executor.namespace
        )

        # Add initial call stack frame for PB:02:EXE
        initial_ip = InstructionPointer(
            playbook="PB", line_number="02", source_line_number=2
        )
        initial_frame = CallStackFrame(instruction_pointer=initial_ip)
        mock_agent.state.call_stack.push(initial_frame)

        # Execute code that includes successful and failing playbook calls
        await executor.add_chunk('await Step("PB:03:EXE")\n')
        await executor.add_chunk("x = 10\n")
        await executor.add_chunk('await Step("PB:04:QUE")\n')

        # GoodPlaybook should execute successfully
        await executor.add_chunk("await GoodPlaybook(x)\n")
        # Verify GoodPlaybook was actually executed with correct arguments
        good_playbook_calls = [
            call for call in mock_agent.playbook_calls if "GoodPlaybook" in call["name"]
        ]
        assert (
            len(good_playbook_calls) == 1
        ), "GoodPlaybook should have been called once"
        assert good_playbook_calls[0]["args"] == (
            10,
        ), "GoodPlaybook should have been called with x=10"

        await executor.add_chunk('await Step("PB:05:QUE")\n')

        # PlaybookDoesNotExist returns an error string (not raise exception)
        await executor.add_chunk("result = await PlaybookDoesNotExist()\n")
        # Verify PlaybookDoesNotExist was called but failed
        bad_playbook_calls = [
            call
            for call in mock_agent.playbook_calls
            if "PlaybookDoesNotExist" in call["name"]
        ]
        assert (
            len(bad_playbook_calls) == 1
        ), "PlaybookDoesNotExist should have been called once"

        # Execution continues - these lines WILL execute
        await executor.add_chunk('await Step("PB:06:YLD")\n')
        await executor.add_chunk('await Yld("call")\n')

        result = await executor.finalize()

        # Verify executed code includes all lines (no exception was raised)
        executed_code = executor.get_executed_code()
        assert "await GoodPlaybook(x)" in executed_code
        assert "await PlaybookDoesNotExist()" in executed_code
        assert 'await Step("PB:06:YLD")' in executed_code

        # Verify the error string was returned
        assert "result" in result.vars
        result_value = str(result.vars["result"])
        assert result_value.startswith("ERROR:")
        assert "not found" in result_value

        # Verify variables were set correctly
        assert result.vars["x"] == 10

        # No error captured because no exception was raised
        assert result.runtime_error is None
        assert result.syntax_error is None

    @pytest.mark.asyncio
    async def test_playbook_call_exception_aborts_execution(self, executor, mock_agent):
        """Test that an exception during playbook call aborts execution.

        This tests what SHOULD happen if playbook calls raised exceptions
        on failure instead of returning error strings.
        """
        # Mock Step function
        step_mock = AsyncMock()
        executor.namespace["Step"] = step_mock

        # Create a playbook wrapper that raises an exception
        async def failing_playbook(*args, **kwargs):
            raise RuntimeError("Playbook 'PlaybookDoesNotExist' not found")

        executor.namespace["FailingPlaybook"] = failing_playbook

        # Execute code up to the failing playbook
        await executor.add_chunk('await Step("PB:03:EXE")\n')
        await executor.add_chunk("x = 10\n")
        await executor.add_chunk('await Step("PB:04:QUE")\n')
        await executor.add_chunk('await Step("PB:05:QUE")\n')

        # This should raise an exception and abort execution
        with pytest.raises(StreamingExecutionError):
            await executor.add_chunk("await FailingPlaybook()\n")

        # Verify error was captured
        assert executor.has_error
        assert isinstance(executor.error, RuntimeError)
        assert "not found" in str(executor.error)

        # Code after the error should not execute
        await executor.add_chunk('await Step("PB:06:YLD")\n')

        result = await executor.finalize()

        # Verify executed code does NOT include the error line
        # (current behavior - only successfully executed code is tracked)
        executed_code = executor.get_executed_code()
        assert "await FailingPlaybook()" not in executed_code
        assert 'await Step("PB:05:QUE")' in executed_code
        assert 'await Step("PB:06:YLD")' not in executed_code

        # Verify variables were set correctly up to the error
        assert result.vars["x"] == 10

        # Verify error information is available for LLM retry
        assert result.runtime_error is not None
        assert result.error_message is not None
        assert "not found" in result.error_message

    @pytest.mark.asyncio
    async def test_call_stack_state_after_playbook_error(self, executor, mock_agent):
        """Test that call stack is at correct position after playbook error.

        This test verifies that when a playbook call fails:
        1. The call stack is at the Step where the error occurred
        2. The error message includes context about the failure
        3. The next LLM call can continue from the correct position
        """

        # Mock Step function that updates call stack
        async def step_impl(step_id):
            # Parse step and update call stack
            parts = step_id.split(":")
            if len(parts) >= 2:
                playbook = parts[0]
                line_number = parts[1]
                ip = InstructionPointer(
                    playbook=playbook,
                    line_number=line_number,
                    source_line_number=int(line_number),
                )
                # Update the top frame's instruction pointer
                frame = mock_agent.state.call_stack.peek()
                if frame:
                    frame.instruction_pointer = ip

        step_mock = AsyncMock(side_effect=step_impl)
        executor.namespace["Step"] = step_mock

        # Create a playbook wrapper that raises an exception
        async def failing_playbook(*args, **kwargs):
            raise RuntimeError("Playbook 'PlaybookDoesNotExist' not found")

        executor.namespace["FailingPlaybook"] = failing_playbook

        # Add initial call stack frame
        initial_ip = InstructionPointer(
            playbook="PB", line_number="02", source_line_number=2
        )
        initial_frame = CallStackFrame(instruction_pointer=initial_ip)
        mock_agent.state.call_stack.push(initial_frame)

        # Execute steps leading up to error
        await executor.add_chunk('await Step("PB:03:EXE")\n')
        await executor.add_chunk("x = 10\n")
        await executor.add_chunk('await Step("PB:04:QUE")\n')
        await executor.add_chunk('await Step("PB:05:QUE")\n')

        # Call the failing playbook (this should raise an exception)
        with pytest.raises(StreamingExecutionError):
            await executor.add_chunk("await FailingPlaybook()\n")

        # Verify call stack is at PB:05:QUE (the last successfully executed Step)
        current_frame = mock_agent.state.call_stack.peek()
        assert current_frame is not None
        assert current_frame.instruction_pointer.playbook == "PB"
        assert current_frame.instruction_pointer.line_number == "05"

        # Verify error information is captured
        result = await executor.finalize()
        assert result.runtime_error is not None
        assert "not found" in result.error_message

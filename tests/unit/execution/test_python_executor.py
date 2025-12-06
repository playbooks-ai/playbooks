"""Tests for PythonExecutor class."""

import pytest
from dotmap import DotMap

from playbooks.execution.python_executor import PythonExecutor
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer


class MockProgram:
    """Mock program for testing."""

    def __init__(self):
        self._debug_server = None


class MockState:
    """Mock execution state for testing."""

    def __init__(self):
        event_bus = EventBus("test-session")
        self.variables = DotMap()
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
            step=parts[2] if len(parts) > 2 else None,
        )

    def resolve_target(self, target: str, allow_fallback: bool = True) -> str:
        """Mock resolve_target method."""
        return target

    async def WaitForMessage(self, target: str):
        """Mock WaitForMessage method."""
        pass


@pytest.fixture
def mock_agent():
    """Fixture to create a mock agent."""
    return MockAgent()


@pytest.fixture
def executor(mock_agent):
    """Fixture to create a PythonExecutor instance."""
    return PythonExecutor(mock_agent)


class TestPythonExecutor:
    """Test suite for PythonExecutor."""

    @pytest.mark.asyncio
    async def test_execute_simple_code(self, executor):
        """Test executing simple Python code."""
        code = "x = 5"
        result = await executor.execute(code)
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_capture_step(self, executor):
        """Test capturing Step() calls."""
        code = 'await Step("Welcome:01:QUE")'
        result = await executor.execute(code)
        assert len(result.steps) == 1
        assert result.steps[0].playbook == "Welcome"
        assert result.steps[0].line_number == "01"

    @pytest.mark.asyncio
    async def test_capture_step_thinking(self, executor):
        """Test capturing thinking step (TNK)."""
        code = 'await Step("Analysis:02:TNK")'
        result = await executor.execute(code)
        assert result.is_thinking is True

    @pytest.mark.asyncio
    async def test_capture_say(self, executor):
        """Test capturing Say() calls."""
        code = 'await Say("user", "Hello, how are you?")'
        result = await executor.execute(code)
        assert len(result.messages) == 1
        assert result.messages[0] == ("user", "Hello, how are you?")

    @pytest.mark.asyncio
    async def test_capture_var(self, executor):
        """Test capturing Var() calls."""
        code = "state.count = 42"
        await executor.execute(code)
        assert executor.agent.state.variables.count == 42

    @pytest.mark.asyncio
    async def test_capture_var_string(self, executor):
        """Test capturing Var() with string values."""
        code = 'state.message = "test message"'
        await executor.execute(code)
        assert executor.agent.state.variables.message == "test message"

    @pytest.mark.asyncio
    async def test_capture_artifact(self, executor):
        """Test capturing Artifact() calls."""
        code = 'await Artifact("report", "Summary", "Long content here")'
        result = await executor.execute(code)
        assert len(result.artifacts) == 1
        assert result.artifacts["report"].name == "report"
        assert result.artifacts["report"].summary == "Summary"

    @pytest.mark.asyncio
    async def test_capture_trigger(self, executor):
        """Test capturing Trigger() calls."""
        code = 'await Trigger("UserAuth:01:CND")'
        result = await executor.execute(code)
        assert len(result.triggers) == 1
        assert result.triggers[0] == "UserAuth:01:CND"

    @pytest.mark.asyncio
    async def test_capture_return(self, executor):
        """Test capturing Return() calls."""
        code = 'await Return("success")'
        result = await executor.execute(code)
        assert result.return_value == "success"
        assert result.playbook_finished is True

    @pytest.mark.asyncio
    async def test_capture_yld_user(self, executor):
        """Test capturing Yld() for user."""
        code = 'await Yld("user")'
        result = await executor.execute(code)
        assert result.wait_for_user_input is True

    @pytest.mark.asyncio
    async def test_capture_yld_exit(self, executor):
        """Test capturing Yld() for exit."""

        code = 'await Yld("exit")'
        result = await executor.execute(code)
        assert result.exit_program is True

    @pytest.mark.asyncio
    async def test_capture_yld_agent(self, executor):
        """Test capturing Yld() for specific agent."""
        code = 'await Yld("agent_123")'
        result = await executor.execute(code)
        assert result.wait_for_agent_input is True
        assert result.wait_for_agent_target == "agent_123"

    @pytest.mark.asyncio
    async def test_multiple_statements(self, executor):
        """Test executing multiple statements."""
        code = """
await Step("Welcome:01:QUE")
await Say("user", "Hello!")
state.name = "Alice"
"""
        result = await executor.execute(code)
        assert len(result.steps) == 1
        assert len(result.messages) == 1
        assert executor.agent.state.variables.name == "Alice"

    @pytest.mark.asyncio
    async def test_syntax_error(self, executor):
        """Test handling syntax errors."""
        code = 'Step("step"'  # Missing closing paren
        result = await executor.execute(code)
        assert result.syntax_error is not None
        assert isinstance(result.syntax_error, SyntaxError)

    @pytest.mark.asyncio
    async def test_name_error(self, executor):
        """Test handling name errors (undefined variable)."""
        code = "x = undefined_variable"
        result = await executor.execute(code)
        assert result.runtime_error is not None
        assert isinstance(result.runtime_error, NameError)

    @pytest.mark.asyncio
    async def test_multiline_say(self, executor):
        """Test Say() with multiline strings."""
        code = '''await Say("user", """This is
a multiline
message""")'''
        result = await executor.execute(code)
        assert len(result.messages) == 1
        assert "multiline" in result.messages[0][1]

    @pytest.mark.asyncio
    async def test_variable_access(self, executor):
        """Test accessing variables in code."""
        # First set a variable
        executor.agent.state.variables.count = 5

        # Then use it
        code = 'await Step("Test:01:QUE")\nstate.result = state.count * 2'
        await executor.execute(code)
        assert executor.agent.state.variables.result == 10

    @pytest.mark.asyncio
    async def test_builtin_namespace(self, executor):
        """Test that builtins are available (like len, str, etc.)."""
        code = 'state.length = len("hello")'
        await executor.execute(code)
        assert executor.agent.state.variables.length == 5

    @pytest.mark.asyncio
    async def test_execution_result_structure(self, executor):
        """Test ExecutionResult structure."""
        code = """
await Step("Step1:01:QUE")
await Say("user", "hello")
state.x = 1
await Trigger("T1")
await Return(True)
"""
        result = await executor.execute(code)

        # Verify all result attributes are properly initialized
        assert isinstance(result.steps, list)
        assert isinstance(result.messages, list)
        assert isinstance(result.vars, dict)
        assert isinstance(result.artifacts, dict)
        assert isinstance(result.triggers, list)
        assert isinstance(result.playbook_calls, list)
        assert result.return_value is not None
        assert result.playbook_finished is True

    @pytest.mark.asyncio
    async def test_playbook_arguments_in_namespace(self, executor):
        """Test that playbook arguments are available in generated code."""
        # Simulate playbook arguments
        playbook_args = {
            "order_id": "12345",
            "customer_name": "John Doe",
            "total": 99.99,
        }

        # Code that uses the playbook arguments
        code = """
state.order_info = f"Order {order_id} for {customer_name}"
state.total_plus_ten = total + 10
"""
        result = await executor.execute(code, playbook_args=playbook_args)

        # Verify arguments were accessible
        assert result.error_message is None
        assert executor.agent.state.variables.order_info == "Order 12345 for John Doe"
        assert executor.agent.state.variables.total_plus_ten == 109.99

    @pytest.mark.asyncio
    async def test_playbook_arguments_none(self, executor):
        """Test that code works when no playbook_args are provided."""
        code = "state.x = 5"
        result = await executor.execute(code, playbook_args=None)
        assert result.error_message is None
        assert executor.agent.state.variables.x == 5

    @pytest.mark.asyncio
    async def test_playbook_arguments_empty_dict(self, executor):
        """Test that code works with empty playbook_args dict."""
        code = "state.y = 10"
        result = await executor.execute(code, playbook_args={})
        assert result.error_message is None
        assert executor.agent.state.variables.y == 10

    @pytest.mark.asyncio
    async def test_playbook_arguments_with_say(self, executor):
        """Test using playbook arguments in Say() calls."""
        playbook_args = {"user_name": "Alice", "greeting": "Welcome"}

        code = 'await Say("user", f"{greeting}, {user_name}!")'
        result = await executor.execute(code, playbook_args=playbook_args)

        assert result.error_message is None
        assert len(result.messages) == 1

    @pytest.mark.asyncio
    async def test_variable_read_before_write_no_unbound_error(self, executor):
        """Test that reading a variable via state.x before writing works correctly.

        With state.x syntax, variables are accessed through the DotMap directly,
        so there's no UnboundLocalError issue.
        """
        # Set up initial state
        executor.agent.state.variables.current_symbol = "X"
        executor.agent.state.variables.game_state = ["1", "2", "3"]
        executor.agent.state.variables.move = 2

        code = """
state.game_state[state.move - 1] = state.current_symbol
state.current_symbol = 'X' if state.current_symbol == 'O' else 'O'
"""
        result = await executor.execute(code)

        # Should not have any errors
        assert result.error_message is None
        assert result.runtime_error is None
        assert result.syntax_error is None

        # Should have updated current_symbol value
        assert (
            executor.agent.state.variables.current_symbol == "O"
        )  # Flipped from X to O

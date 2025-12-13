"""Tests for PythonExecutor class."""

import pytest
from dotmap import DotMap

from playbooks.execution.python_executor import PythonExecutor
from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.call_stack import CallStack, CallStackFrame, InstructionPointer
from playbooks.state.variables import PlaybookDotMap


class MockProgram:
    """Mock program for testing."""

    def __init__(self):
        self._debug_server = None
        self.execution_finished = False


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

        # Set up state matching the new flattened architecture
        event_bus = EventBus("test-session")
        self._variables_internal = PlaybookDotMap()
        self.call_stack = CallStack(event_bus)
        # Push a dummy frame for testing so Step() calls work
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
        """Return variables DotMap for new architecture compatibility."""
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
        """Mock Say method that captures messages."""
        # Get current executor and manually add to messages
        current_frame = self.call_stack.peek()
        if (
            current_frame
            and hasattr(current_frame, "executor")
            and current_frame.executor
        ):
            current_frame.executor.result.messages.append((target, message))

    @property
    def _current_executor(self):
        """Get the current executor from the top call stack frame.

        Returns:
            The executor associated with the current call stack frame.

        Raises:
            RuntimeError: If called outside of code execution context.
        """
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

    async def Yield(self, target: str = "user"):
        """Mock Yield method that delegates to executor."""
        await self._current_executor.capture_yld(target)

    async def Return(self, value):
        """Mock Return method that delegates to executor."""
        await self._current_executor.capture_return(value)

    async def SaveArtifact(self, name: str, summary: str, content: str):
        """Mock SaveArtifact method that delegates to executor."""
        await self._current_executor.capture_artifact(name, summary, content)

    async def LogTrigger(self, code: str):
        """Mock LogTrigger method that delegates to executor."""
        await self._current_executor.capture_trigger(code)


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
        code = 'await self.Step("Welcome:01:QUE")'
        result = await executor.execute(code)
        assert len(result.steps) == 1
        assert result.steps[0].playbook == "Welcome"
        assert result.steps[0].line_number == "01"

    @pytest.mark.asyncio
    async def test_capture_step_thinking(self, executor):
        """Test capturing thinking step (TNK)."""
        code = 'await self.Step("Analysis:02:TNK")'
        result = await executor.execute(code)
        assert result.is_thinking is True

    @pytest.mark.asyncio
    async def test_capture_say(self, executor):
        """Test capturing Say() calls."""
        code = 'await self.Say("user", "Hello, how are you?")'
        result = await executor.execute(code)
        assert len(result.messages) == 1
        assert result.messages[0] == ("user", "Hello, how are you?")

    @pytest.mark.asyncio
    async def test_state_assignment(self, executor):
        """Test state variable assignment."""
        code = "self.state.count = 42"
        await executor.execute(code)
        assert executor.agent.state.count == 42

    @pytest.mark.asyncio
    async def test_state_assignment_string(self, executor):
        """Test state variable assignment with string values."""
        code = 'self.state.message = "test message"'
        await executor.execute(code)
        assert executor.agent.state.message == "test message"

    @pytest.mark.asyncio
    async def test_capture_artifact(self, executor):
        """Test capturing Artifact() calls."""
        code = 'await self.SaveArtifact("report", "Summary", "Long content here")'
        result = await executor.execute(code)
        assert len(result.artifacts) == 1
        assert result.artifacts["report"].name == "report"
        assert result.artifacts["report"].summary == "Summary"

    @pytest.mark.asyncio
    async def test_capture_trigger(self, executor):
        """Test capturing Trigger() calls."""
        code = 'await self.LogTrigger("UserAuth:01:CND")'
        result = await executor.execute(code)
        assert len(result.triggers) == 1
        assert result.triggers[0] == "UserAuth:01:CND"

    @pytest.mark.asyncio
    async def test_capture_return(self, executor):
        """Test capturing Return() calls."""
        code = 'await self.Return("success")'
        result = await executor.execute(code)
        assert result.return_value == "success"
        assert result.playbook_finished is True

    @pytest.mark.asyncio
    async def test_capture_yld_user(self, executor):
        """Test capturing Yld() for user."""
        code = 'await self.Yield("user")'
        result = await executor.execute(code)
        assert result.wait_for_user_input is True

    @pytest.mark.asyncio
    async def test_capture_yld_exit(self, executor):
        """Test capturing Yld() for exit."""

        code = 'await self.Yield("exit")'
        result = await executor.execute(code)
        assert result.exit_program is True

    @pytest.mark.asyncio
    async def test_capture_yld_agent(self, executor):
        """Test capturing Yld() for specific agent."""
        code = 'await self.Yield("agent_123")'
        result = await executor.execute(code)
        assert result.wait_for_agent_input is True
        assert result.wait_for_agent_target == "agent_123"

    @pytest.mark.asyncio
    async def test_multiple_statements(self, executor):
        """Test executing multiple statements."""
        code = """
await self.Step("Welcome:01:QUE")
await self.Say("user", "Hello!")
self.state.name = "Alice"
"""
        result = await executor.execute(code)
        assert len(result.steps) == 1
        assert len(result.messages) == 1
        assert executor.agent.state.name == "Alice"

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
        code = '''await self.Say("user", """This is
a multiline
message""")'''
        result = await executor.execute(code)
        assert len(result.messages) == 1
        assert "multiline" in result.messages[0][1]

    @pytest.mark.asyncio
    async def test_variable_access(self, executor):
        """Test accessing variables in code."""
        # First set a variable
        executor.agent.state.count = 5

        # Then use it
        code = (
            'await self.Step("Test:01:QUE")\nself.state.result = self.state.count * 2'
        )
        await executor.execute(code)
        assert executor.agent.state.result == 10

    @pytest.mark.asyncio
    async def test_builtin_namespace(self, executor):
        """Test that builtins are available (like len, str, etc.)."""
        code = 'self.state.length = len("hello")'
        await executor.execute(code)
        assert executor.agent.state.length == 5

    @pytest.mark.asyncio
    async def test_execution_result_structure(self, executor):
        """Test ExecutionResult structure."""
        code = """
await self.Step("Step1:01:QUE")
await self.Say("user", "hello")
self.state.x = 1
await self.LogTrigger("T1")
await self.Return(True)
"""
        result = await executor.execute(code)

        # Verify all result attributes are properly initialized
        assert isinstance(result.steps, list)
        assert isinstance(result.messages, list)
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
self.state.order_info = f"Order {order_id} for {customer_name}"
self.state.total_plus_ten = total + 10
"""
        result = await executor.execute(code, playbook_args=playbook_args)

        # Verify arguments were accessible
        assert result.error_message is None
        assert executor.agent.state.order_info == "Order 12345 for John Doe"
        assert executor.agent.state.total_plus_ten == 109.99

    @pytest.mark.asyncio
    async def test_playbook_arguments_none(self, executor):
        """Test that code works when no playbook_args are provided."""
        code = "self.state.x = 5"
        result = await executor.execute(code, playbook_args=None)
        assert result.error_message is None
        assert executor.agent.state.x == 5

    @pytest.mark.asyncio
    async def test_playbook_arguments_empty_dict(self, executor):
        """Test that code works with empty playbook_args dict."""
        code = "self.state.y = 10"
        result = await executor.execute(code, playbook_args={})
        assert result.error_message is None
        assert executor.agent.state.y == 10

    @pytest.mark.asyncio
    async def test_playbook_arguments_with_say(self, executor):
        """Test using playbook arguments in Say() calls."""
        playbook_args = {"user_name": "Alice", "greeting": "Welcome"}

        code = 'await self.Say("user", f"{greeting}, {user_name}!")'
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
        executor.agent.state.current_symbol = "X"
        executor.agent.state.game_state = ["1", "2", "3"]
        executor.agent.state.move = 2

        code = """
self.state.game_state[self.state.move - 1] = self.state.current_symbol
self.state.current_symbol = 'X' if self.state.current_symbol == 'O' else 'O'
"""
        result = await executor.execute(code)

        # Should not have any errors
        assert result.error_message is None
        assert result.runtime_error is None
        assert result.syntax_error is None

        # Should have updated current_symbol value
        assert executor.agent.state.current_symbol == "O"  # Flipped from X to O

    @pytest.mark.asyncio
    async def test_format_specifier_with_nested_dict_in_execution(self, executor):
        """Test format specifier with nested dict in executed code (regression test).

        This tests the exact failure case reported:
        - FormatSummary called with report_data={'sales': 1000, 'region': 'North', 'trend': 'positive'}
        - Code tries to format: f"${self.state.report_data['sales']:,}"
        - Previously failed with: "unsupported format string passed to DotMap.__format__"
        """
        # Set up the state as it would be in the actual scenario
        executor.agent.state.report_data = {
            "sales": 1000,
            "region": "North",
            "trend": "positive",
        }

        # This is the exact code pattern that was failing
        code = """
await self.Step("FormatSummary:01:EXE")
self.state.summary = f'📊 **North Region Report**: Sales reached **${self.state.report_data["sales"]:,}** with a **{self.state.report_data["trend"]}** trend—excellent momentum!'
"""

        result = await executor.execute(code)

        # Should not have any errors
        assert result.error_message is None
        assert result.runtime_error is None
        assert result.syntax_error is None

        # Should have created the summary
        assert hasattr(executor.agent.state, "summary")
        summary = executor.agent.state.summary

        # Verify the formatted values are correct
        assert "**$1,000**" in summary  # Formatted with comma separator
        assert "**positive**" in summary
        assert "North Region Report" in summary

    @pytest.mark.asyncio
    async def test_format_specifier_with_multiple_values(self, executor):
        """Test format specifiers with multiple numeric values in execution."""
        executor.agent.state.metrics = {
            "revenue": 1234567,
            "profit": 98765.43,
            "growth": 15.5,
        }

        code = """
self.state.report = f"Revenue: ${self.state.metrics['revenue']:,} | Profit: ${self.state.metrics['profit']:,.2f} | Growth: {self.state.metrics['growth']:.1f}%"
"""

        result = await executor.execute(code)

        assert result.error_message is None
        assert result.runtime_error is None

        report = executor.agent.state.report
        assert "Revenue: $1,234,567" in report
        assert "Profit: $98,765.43" in report
        assert "Growth: 15.5%" in report

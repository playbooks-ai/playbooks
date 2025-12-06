"""Tests for variable assignment handling in PythonExecutor.

Tests cover:
- Variable capture via state.x attribute access
- Namespace updates for subsequent code access
- Integration with existing capture functions
"""

from unittest.mock import MagicMock

import pytest
from dotmap import DotMap

from playbooks.execution.python_executor import PythonExecutor


@pytest.mark.asyncio
class TestVariableCapture:
    """Tests for variable capture through execution."""

    async def test_execute_simple_variable_assignment(self):
        """Test executing code with simple variable assignment using state.x syntax."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "state.x = 10"
        await executor.execute(code)

        assert agent.state.variables.x == 10

    async def test_execute_variable_assignment_with_expression(self):
        """Test executing variable assignment with expressions."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "state.result = 5 + 3"
        await executor.execute(code)

        assert agent.state.variables.result == 8

    async def test_execute_multiple_variables(self):
        """Test executing multiple variable assignments."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = """state.x = 10
state.y = 20
state.z = state.x + state.y"""
        await executor.execute(code)

        assert agent.state.variables.x == 10
        assert agent.state.variables.y == 20
        assert agent.state.variables.z == 30

    async def test_execute_variables_available_in_subsequent_code(self):
        """Test that variables are available for use in subsequent code."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = """state.x = 10
state.y = state.x * 2
state.z = state.x + state.y"""
        await executor.execute(code)

        assert agent.state.variables.x == 10
        assert agent.state.variables.y == 20
        assert agent.state.variables.z == 30

    async def test_execute_variable_with_string_value(self):
        """Test executing variable assignment with string value."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = 'state.message = "Hello, World!"'
        await executor.execute(code)

        assert agent.state.variables.message == "Hello, World!"

    async def test_execute_variable_with_list_value(self):
        """Test executing variable assignment with list value."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "state.mylist = [1, 2, 3, 4, 5]"
        await executor.execute(code)

        assert agent.state.variables.mylist == [1, 2, 3, 4, 5]

    async def test_execute_variable_with_dict_value(self):
        """Test executing variable assignment with dict value."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = 'state.data = {"key": "value", "number": 42}'
        await executor.execute(code)

        assert agent.state.variables.data["key"] == "value"
        assert agent.state.variables.data["number"] == 42

    async def test_execute_variable_with_conditional(self):
        """Test executing variable assignment within conditional."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = """state.x = 10
if state.x > 5:
    state.result = "greater"
else:
    state.result = "less"
"""
        await executor.execute(code)

        assert agent.state.variables.result == "greater"

    async def test_execute_preserves_error_handling(self):
        """Test that execution errors are captured in the result."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "state.x = undefined_variable"

        result = await executor.execute(code)
        assert result.runtime_error is not None
        assert isinstance(result.runtime_error, NameError)
        assert "undefined_variable" in str(result.runtime_error)

    async def test_execute_syntax_error_still_captured(self):
        """Test that syntax errors are captured in the result."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = DotMap()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "state.x = ("  # Invalid syntax

        result = await executor.execute(code)
        assert result.syntax_error is not None
        assert isinstance(result.syntax_error, SyntaxError)

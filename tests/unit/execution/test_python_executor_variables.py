"""Tests for variable assignment handling in PythonExecutor.

Tests cover:
- Variable capture via AST transformation (inject_setvar)
- Namespace updates for subsequent code access
- Integration with existing capture functions
- Backward compatibility with explicit Var() calls
"""

from unittest.mock import MagicMock

import pytest

from playbooks.execution.python_executor import LLMNamespace, PythonExecutor
from playbooks.state.variables import Variable


@pytest.mark.asyncio
class TestLLMNamespace:
    """Tests for LLMNamespace that tracks variable assignments."""

    async def test_namespace_creation(self):
        """Test creating an LLMNamespace instance."""
        executor = MagicMock()
        namespace = LLMNamespace(executor, {"key": "value"})

        assert namespace["key"] == "value"
        assert namespace.executor is executor

    async def test_namespace_setitem_basic(self):
        """Test basic __setitem__ behavior."""
        executor = MagicMock()
        namespace = LLMNamespace(executor)

        namespace["x"] = 42
        assert namespace["x"] == 42

    async def test_namespace_behaves_as_dict(self):
        """Test that LLMNamespace behaves like a normal dict."""
        executor = MagicMock()
        namespace = LLMNamespace(executor)

        namespace.update({"a": 1, "b": 2})
        assert "a" in namespace
        assert namespace.get("c", "default") == "default"
        assert len(namespace) >= 2

    async def test_namespace_getitem_from_local_namespace(self):
        """Test __getitem__ returns values from local namespace."""
        executor = MagicMock()
        namespace = LLMNamespace(executor)

        namespace["x"] = 42
        assert namespace["x"] == 42

    async def test_namespace_getitem_proxies_state_variable(self):
        """Test __getitem__ proxies variables from execution state."""
        executor = MagicMock()
        executor.agent = MagicMock()
        executor.agent.state = MagicMock()
        executor.agent.state.variables = {"$x": Variable(name="$x", value=100)}

        namespace = LLMNamespace(executor)

        # Access x should proxy to $x in state
        assert namespace["x"] == 100

    async def test_namespace_getitem_prefers_local_over_state(self):
        """Test __getitem__ prefers local namespace over state."""
        executor = MagicMock()
        executor.state = MagicMock()
        executor.state.variables = {"$x": 100}

        namespace = LLMNamespace(executor)
        namespace["x"] = 42

        # Should return local value, not state value
        assert namespace["x"] == 42

    async def test_namespace_getitem_raises_keyerror(self):
        """Test __getitem__ raises KeyError for missing variables."""
        executor = MagicMock()
        executor.state = MagicMock()
        executor.state.variables = {}

        namespace = LLMNamespace(executor)

        with pytest.raises(KeyError):
            _ = namespace["nonexistent"]

    async def test_namespace_getitem_skips_dunder_proxying(self):
        """Test __getitem__ doesn't proxy dunder variables from state."""
        executor = MagicMock()
        executor.state = MagicMock()
        executor.state.variables = {"$__name__": "test"}

        namespace = LLMNamespace(executor)

        with pytest.raises(KeyError):
            _ = namespace["__name__"]

    async def test_namespace_getitem_no_state(self):
        """Test __getitem__ works when state is None."""
        executor = MagicMock()
        executor.state = None

        namespace = LLMNamespace(executor)
        namespace["x"] = 42

        assert namespace["x"] == 42

        with pytest.raises(KeyError):
            _ = namespace["y"]


@pytest.mark.asyncio
class TestVariableCapture:
    """Tests for variable capture through execution."""

    async def test_execute_simple_variable_assignment(self):
        """Test executing code with simple variable assignment.

        inject_setvar automatically transforms 'x = 10' into:
            x = 10
            Var('x', x)
        """
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "x = 10"
        result = await executor.execute(code)

        assert result.vars["x"] == 10
        # Verify state was updated via _capture_var
        agent.state.variables.__setitem__.assert_called()

    async def test_execute_variable_assignment_with_expression(self):
        """Test executing variable assignment with expressions."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "result = 5 + 3"
        result = await executor.execute(code)

        assert result.vars["result"] == 8

    async def test_execute_multiple_variables(self):
        """Test executing multiple variable assignments."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = """x = 10
y = 20
z = x + y"""
        result = await executor.execute(code)

        assert result.vars["x"] == 10
        assert result.vars["y"] == 20
        assert result.vars["z"] == 30

    async def test_execute_variables_available_in_subsequent_code(self):
        """Test that variables are available for use in subsequent code."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = """x = 10
y = x * 2
z = x + y"""
        result = await executor.execute(code)

        assert result.vars["x"] == 10
        assert result.vars["y"] == 20
        assert result.vars["z"] == 30

    async def test_execute_variable_with_string_value(self):
        """Test executing variable assignment with string value."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = 'message = "Hello, World!"'
        result = await executor.execute(code)

        assert result.vars["message"] == "Hello, World!"

    async def test_execute_variable_with_list_value(self):
        """Test executing variable assignment with list value."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "items = [1, 2, 3, 4, 5]"
        result = await executor.execute(code)

        assert result.vars["items"] == [1, 2, 3, 4, 5]

    async def test_execute_variable_with_dict_value(self):
        """Test executing variable assignment with dict value."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = 'data = {"key": "value", "number": 42}'
        result = await executor.execute(code)

        assert result.vars["data"]["key"] == "value"
        assert result.vars["data"]["number"] == 42

    async def test_execute_variable_with_conditional(self):
        """Test executing variable assignment within conditional."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = """x = 10
if x > 5:
    result = "greater"
else:
    result = "less"
"""
        result = await executor.execute(code)

        assert result.vars["result"] == "greater"

    async def test_execute_preserves_error_handling(self):
        """Test that execution errors are captured in the result."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "x = undefined_variable"

        result = await executor.execute(code)
        assert result.runtime_error is not None
        assert isinstance(result.runtime_error, NameError)
        assert "undefined_variable" in str(result.runtime_error)

    async def test_execute_syntax_error_still_captured(self):
        """Test that syntax errors are captured in the result."""
        agent = MagicMock()
        agent.playbooks = {}
        agent.state = MagicMock()
        agent.state.variables = MagicMock()
        agent.state.call_stack = MagicMock()
        agent.state.call_stack.peek = MagicMock(return_value=None)
        agent.program = MagicMock()
        agent.program._debug_server = None

        executor = PythonExecutor(agent)
        code = "x = ("  # Invalid syntax

        result = await executor.execute(code)
        assert result.syntax_error is not None
        assert isinstance(result.syntax_error, SyntaxError)

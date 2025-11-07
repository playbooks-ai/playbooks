"""Integration tests for Artifact string operations in expressions."""

import pytest

from playbooks.infrastructure.event_bus import EventBus
from playbooks.state.execution_state import ExecutionState
from playbooks.execution.call import PlaybookCall
from playbooks.compilation.expression_engine import ExpressionContext
from playbooks.state.variables import Artifact


@pytest.fixture
def expression_context():
    """Create an expression context with an artifact."""
    event_bus = EventBus(session_id="test-session")
    state = ExecutionState(event_bus, "TestAgent", "test-agent-123")

    # Create an artifact and add to state
    artifact = Artifact(name="report", summary="Test Report", value="Hello World")
    state.variables["$report"] = artifact

    # Create a mock call
    call = PlaybookCall("TestPlaybook", [], {})

    return ExpressionContext(agent=None, state=state, call=call)


def test_len_in_expression(expression_context):
    """Test that len(artifact) works in expressions."""
    result = expression_context.evaluate_expression("len($report)")
    assert result == 11  # len("Hello World")


def test_concatenation_in_expression(expression_context):
    """Test that artifact concatenation works in expressions."""
    result = expression_context.evaluate_expression("$report + ' everyone'")
    assert result == "Hello World everyone"


def test_reverse_concatenation_in_expression(expression_context):
    """Test that reverse concatenation works in expressions."""
    result = expression_context.evaluate_expression("'Say: ' + $report")
    assert result == "Say: Hello World"


def test_indexing_in_expression(expression_context):
    """Test that artifact indexing works in expressions."""
    result = expression_context.evaluate_expression("$report[0]")
    assert result == "H"


def test_slicing_in_expression(expression_context):
    """Test that artifact slicing works in expressions."""
    result = expression_context.evaluate_expression("$report[0:5]")
    assert result == "Hello"


def test_contains_in_expression(expression_context):
    """Test that 'in' operator works with artifacts in expressions."""
    result = expression_context.evaluate_expression("'World' in $report")
    assert result is True

    result = expression_context.evaluate_expression("'xyz' in $report")
    assert result is False


def test_comparison_in_expression(expression_context):
    """Test that comparisons work with artifacts in expressions."""
    result = expression_context.evaluate_expression("$report == 'Hello World'")
    assert result is True

    result = expression_context.evaluate_expression("$report != 'Goodbye'")
    assert result is True


def test_multiplication_in_expression(expression_context):
    """Test that artifact multiplication works in expressions."""
    expression_context.state.variables["$short"] = Artifact(
        name="short", summary="Short", value="Ha"
    )
    result = expression_context.evaluate_expression("$short * 3")
    assert result == "HaHaHa"


def test_str_function_in_expression(expression_context):
    """Test that str() function works with artifacts in expressions."""
    result = expression_context.evaluate_expression("str($report)")
    assert result == "Hello World"


def test_artifact_with_dict_content_in_expression(expression_context):
    """Test that artifacts with dict content work in expressions."""
    expression_context.state.variables["$data"] = Artifact(
        name="data", summary="Data", value={"key": "value"}
    )

    # len should work on string representation
    result = expression_context.evaluate_expression("len($data)")
    assert result > 0

    # Contains should work on string representation
    result = expression_context.evaluate_expression("'key' in $data")
    assert result is True


def test_chained_operations_in_expression(expression_context):
    """Test that chained operations work with artifacts."""
    result = expression_context.evaluate_expression("($report + '!!!')[0:16]")
    assert result == "Hello World!!!"


def test_artifact_in_complex_expression(expression_context):
    """Test artifacts in more complex expressions."""
    expression_context.state.variables["$count"] = 3
    result = expression_context.evaluate_expression("len($report) > $count")
    assert result is True  # len("Hello World") = 11 > 3

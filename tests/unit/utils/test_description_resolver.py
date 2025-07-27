"""Tests for description placeholder resolution."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from playbooks.utils.description_resolver import (
    LazyContextDict,
    evaluate_with_context,
    extract_and_validate_expressions,
    format_value,
    preprocess_dollar_variables,
    update_description_in_markdown,
)


class TestLazyContextDict:
    """Test the LazyContextDict class."""

    def test_basic_variable_access(self):
        """Test basic variable access from state."""
        # Mock objects
        agent = Mock()
        state = Mock()
        call = Mock()
        call.playbook_klass = "TestPlaybook"

        # Mock state variables
        mock_var = Mock()
        mock_var.value = "test_value"
        state.variables.variables = {"$test_var": mock_var}

        context = LazyContextDict(agent, state, call)

        # Test variable access with and without $
        assert context["test_var"] == "test_value"
        assert context["$test_var"] == "test_value"

    def test_special_variables(self):
        """Test pre-populated special variables."""
        agent = Mock()
        state = Mock()
        call = Mock()

        context = LazyContextDict(agent, state, call)

        assert context["agent"] == agent
        assert context["call"] == call
        assert isinstance(context["timestamp"], datetime)

    def test_circular_reference_detection(self):
        """Test circular reference detection."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock namespace manager with circular reference
        namespace = {}
        agent.namespace_manager.namespace = namespace
        state.variables.variables = {}

        context = LazyContextDict(agent, state, call)

        # Simulate circular reference by accessing during resolution
        context._resolving.add("test_key")

        with pytest.raises(RecursionError, match="Circular reference detected"):
            context["test_key"]

    def test_llm_playbook_access(self):
        """Test access to LLM playbooks from namespace manager."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock LLM playbook function
        def mock_llm_playbook(*args, **kwargs):
            return f"LLM result with args: {args}, kwargs: {kwargs}"

        # Mock namespace manager with LLM playbook
        agent.namespace_manager.namespace = {"SummarizeReport": mock_llm_playbook}
        state.variables.variables = {}

        context = LazyContextDict(agent, state, call)

        # Test LLM playbook access
        playbook_func = context["SummarizeReport"]
        result = playbook_func("test_report", format="summary")
        assert "LLM result with args: ('test_report',)" in result
        assert "kwargs: {'format': 'summary'}" in result

    def test_python_playbook_access(self):
        """Test access to Python playbooks from namespace manager."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock Python playbook function
        def mock_python_playbook(data, process_type="default"):
            return f"Processed {data} with type {process_type}"

        # Mock namespace manager with Python playbook
        agent.namespace_manager.namespace = {"ProcessData": mock_python_playbook}
        state.variables.variables = {}

        context = LazyContextDict(agent, state, call)

        # Test Python playbook access
        playbook_func = context["ProcessData"]
        result = playbook_func("test_data", process_type="advanced")
        assert result == "Processed test_data with type advanced"

    def test_python_builtins_access(self):
        """Test access to Python built-in functions."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock namespace manager with Python builtins
        agent.namespace_manager.namespace = {
            "len": len,
            "str": str,
            "max": max,
            "round": round,
        }
        state.variables.variables = {}

        context = LazyContextDict(agent, state, call)

        # Test Python builtin access
        assert context["len"]([1, 2, 3]) == 3
        assert context["str"](42) == "42"
        assert context["max"]([1, 5, 3]) == 5
        assert context["round"](3.14159, 2) == 3.14

    def test_imported_modules_access(self):
        """Test access to imported modules like math, json, etc."""
        import datetime
        import json
        import math

        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock namespace manager with imported modules
        agent.namespace_manager.namespace = {
            "math": math,
            "json": json,
            "datetime": datetime,
        }
        state.variables.variables = {}

        context = LazyContextDict(agent, state, call)

        # Test module access
        assert context["math"].pi == math.pi
        assert context["math"].sqrt(16) == 4.0

        test_dict = {"key": "value", "number": 42}
        json_str = context["json"].dumps(test_dict)
        assert "key" in json_str and "value" in json_str

        assert hasattr(context["datetime"], "datetime")
        assert hasattr(context["datetime"], "timedelta")

    def test_agent_methods_access(self):
        """Test access to agent methods and properties."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock agent methods
        agent.klass = "TestAgent"
        agent.id = "agent_123"
        agent.get_compact_information.return_value = "Agent compact info"
        agent.other_agent_klasses_information.return_value = ["Agent1", "Agent2"]

        state.variables.variables = {}

        context = LazyContextDict(agent, state, call)

        # Test agent property access
        agent_obj = context["agent"]
        assert agent_obj.klass == "TestAgent"
        assert agent_obj.id == "agent_123"
        assert agent_obj.get_compact_information() == "Agent compact info"
        assert agent_obj.other_agent_klasses_information() == ["Agent1", "Agent2"]

    def test_complex_state_variables(self):
        """Test access to complex state variables like dicts and lists."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock complex state variables
        report_var = Mock()
        report_var.value = {
            "title": "Test Report",
            "content": "Report content here",
            "metadata": {"author": "test_user", "date": "2025-01-27"},
        }

        items_var = Mock()
        items_var.value = [
            {"name": "item1", "active": True},
            {"name": "item2", "active": False},
            {"name": "item3", "active": True},
        ]

        state.variables.variables = {"$report": report_var, "$items": items_var}

        context = LazyContextDict(agent, state, call)

        # Test complex variable access
        report = context["report"]
        assert report["title"] == "Test Report"
        assert report["metadata"]["author"] == "test_user"

        items = context["items"]
        assert len(items) == 3
        assert items[0]["name"] == "item1"
        assert not items[1]["active"]

    def test_variable_caching(self):
        """Test that variables are cached after first access."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock state variable
        mock_var = Mock()
        mock_var.value = "cached_value"
        state.variables.variables = {"$cached_var": mock_var}

        context = LazyContextDict(agent, state, call)

        # First access should fetch from state
        value1 = context["cached_var"]
        assert value1 == "cached_value"

        # Modify the mock to return different value
        mock_var.value = "new_value"

        # Second access should return cached value
        value2 = context["cached_var"]
        assert value2 == "cached_value"  # Should still be cached value

        # Verify the variable is in the cache
        assert "cached_var" in context

    def test_missing_variable_error(self):
        """Test proper error handling for missing variables."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Empty state and namespace
        state.variables.variables = {}
        agent.namespace_manager.namespace = {}

        context = LazyContextDict(agent, state, call)

        # Test missing variable access
        with pytest.raises(KeyError, match="Variable 'nonexistent' not found"):
            context["nonexistent"]

    def test_async_function_detection_and_wrapping(self):
        """Test that async functions are properly detected and wrapped."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Create actual async function
        async def async_playbook(data):
            return f"async processed: {data}"

        # Create sync function for comparison
        def sync_playbook(data):
            return f"sync processed: {data}"

        # Mock namespace with both async and sync functions
        agent.namespace_manager.namespace = {
            "AsyncPlaybook": async_playbook,
            "SyncPlaybook": sync_playbook,
        }
        state.variables.variables = {}

        context = LazyContextDict(agent, state, call)

        # Test that async function is wrapped (name changes)
        wrapped_async = context["AsyncPlaybook"]
        assert wrapped_async.__name__ == "sync_async_playbook"

        # Test that sync function is not wrapped
        sync_func = context["SyncPlaybook"]
        assert sync_func.__name__ == "sync_playbook"  # Original name preserved

        # Test that wrapped function can be called synchronously
        result = wrapped_async("test_data")
        assert result == "async processed: test_data"


class TestDollarVariablePreprocessing:
    """Test dollar variable preprocessing."""

    def test_simple_dollar_variables(self):
        """Test preprocessing simple $variable patterns."""
        assert preprocess_dollar_variables("$order") == "order"
        assert preprocess_dollar_variables("$user_name") == "user_name"
        assert preprocess_dollar_variables("$item123") == "item123"

    def test_dollar_variables_with_access(self):
        """Test preprocessing $variable with property/index access."""
        assert preprocess_dollar_variables("$order['id']") == "order['id']"
        assert preprocess_dollar_variables("$order.customer") == "order.customer"
        assert preprocess_dollar_variables("$data[0]['name']") == "data[0]['name']"

    def test_multiple_dollar_variables(self):
        """Test preprocessing expressions with multiple $variables."""
        assert preprocess_dollar_variables("$var1 + $var2") == "var1 + var2"
        assert (
            preprocess_dollar_variables("func($param1, $param2)")
            == "func(param1, param2)"
        )
        assert (
            preprocess_dollar_variables("$order['id'] if $order else None")
            == "order['id'] if order else None"
        )

    def test_mixed_expressions(self):
        """Test expressions mixing $variables with regular code."""
        assert preprocess_dollar_variables("len($items)") == "len(items)"
        assert (
            preprocess_dollar_variables("round($order['amount'], 2)")
            == "round(order['amount'], 2)"
        )
        assert (
            preprocess_dollar_variables("$user if active else 'anonymous'")
            == "user if active else 'anonymous'"
        )

    def test_no_dollar_variables(self):
        """Test expressions without $variables remain unchanged."""
        assert preprocess_dollar_variables("len(items)") == "len(items)"
        assert preprocess_dollar_variables("agent.klass") == "agent.klass"
        assert preprocess_dollar_variables("'hello world'") == "'hello world'"

    def test_edge_cases(self):
        """Test edge cases in dollar variable preprocessing."""
        # Dollar not followed by valid identifier should be preserved
        assert preprocess_dollar_variables("'cost: $5.99'") == "'cost: $5.99'"
        assert preprocess_dollar_variables("$") == "$"
        assert (
            preprocess_dollar_variables("$$var") == "$var"
        )  # Only first $ is stripped


class TestExpressionValidation:
    """Test expression extraction and validation."""

    def test_extract_valid_expressions(self):
        """Test extraction of valid Python expressions."""
        description = "Hello {name}, today is {datetime.now().strftime('%Y-%m-%d')}"
        valid, invalid = extract_and_validate_expressions(description)

        assert "name" in valid
        assert "datetime.now().strftime('%Y-%m-%d')" in valid
        assert len(invalid) == 0

    def test_extract_invalid_expressions(self):
        """Test extraction of invalid Python expressions."""
        description = "Hello {user name}, {Summarize the report}"
        valid, invalid = extract_and_validate_expressions(description)

        assert "user name" in invalid
        assert "Summarize the report" in invalid
        assert len(valid) == 0

    def test_no_expressions(self):
        """Test descriptions with no expressions."""
        description = "Simple description with no placeholders"
        valid, invalid = extract_and_validate_expressions(description)

        assert len(valid) == 0
        assert len(invalid) == 0

    def test_nested_braces(self):
        """Test handling of nested braces."""
        description = 'Status: {"Good" if score > 0.8 else "Bad"}'
        valid, invalid = extract_and_validate_expressions(description)

        assert '"Good" if score > 0.8 else "Bad"' in valid
        assert len(invalid) == 0


class TestValueFormatting:
    """Test value formatting functions."""

    def test_format_none(self):
        """Test formatting None values."""
        assert format_value(None) == ""

    def test_format_simple_values(self):
        """Test formatting simple values."""
        assert format_value("test") == "test"
        assert format_value(42) == "42"
        assert format_value(3.14) == "3.14"

    def test_format_small_dict(self):
        """Test formatting small dictionaries."""
        small_dict = {"key": "value"}
        result = format_value(small_dict)
        assert result == '{"key": "value"}'

    def test_format_large_dict(self):
        """Test formatting large dictionaries with indentation."""
        # Create a dict that's definitely over 100 chars when serialized
        large_dict = {
            "key1": "value1_long_enough_to_exceed_100_chars",
            "key2": "value2_also_long_enough_to_exceed_100_chars",
            "key3": {"nested": "value_that_makes_this_really_long"},
        }
        result = format_value(large_dict)
        assert result.startswith("\n")
        assert result.endswith("\n")
        assert '"key1"' in result


class TestMarkdownUpdate:
    """Test markdown description replacement."""

    def test_update_description_with_sections(self):
        """Test updating description when sections exist."""
        markdown = """## TestPlaybook
Original description here
### Triggers
- Some trigger
### Steps
- Some step"""

        resolved = "New resolved description"
        result = update_description_in_markdown(markdown, resolved)

        assert "New resolved description" in result
        assert "Original description here" not in result
        assert "### Triggers" in result
        assert "### Steps" in result

    def test_update_description_no_sections(self):
        """Test updating description when no sections exist."""
        markdown = """## TestPlaybook
Original description here"""

        resolved = "New resolved description"
        result = update_description_in_markdown(markdown, resolved)

        assert "New resolved description" in result
        assert "Original description here" not in result


class TestAsyncIntegration:
    """Test async function integration."""

    def test_async_function_wrapper(self):
        """Test that async functions are properly wrapped."""

        # Create a mock async function
        async def mock_async_func():
            return "async_result"

        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock namespace with async function
        agent.namespace_manager.namespace = {"async_func": mock_async_func}
        state.variables.variables = {}

        context = LazyContextDict(agent, state, call)

        # Access the async function - should be wrapped
        wrapped_func = context["async_func"]

        # Should be able to call it synchronously
        result = wrapped_func()
        assert result == "async_result"


class TestRealisticUsageScenarios:
    """Test realistic usage scenarios with actual expression evaluation."""

    def test_evaluate_simple_expressions(self):
        """Test evaluating simple expressions in realistic contexts."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Setup realistic context
        agent.klass = "OrderAgent"
        agent.id = "agent_001"

        order_var = Mock()
        order_var.value = {"id": "ORD-123", "customer": "John Doe", "amount": 99.99}

        state.variables.variables = {"$order": order_var}
        agent.namespace_manager.namespace = {"len": len, "round": round}

        context = LazyContextDict(agent, state, call)

        # Test realistic expressions using natural $variable syntax
        description = "Processing order {$order['id']} for {$order['customer']} (${round($order['amount'], 2)})"
        result = evaluate_with_context(description, context)

        assert result == "Processing order ORD-123 for John Doe ($99.99)"

    def test_evaluate_complex_expressions(self):
        """Test evaluating complex expressions with function calls."""
        import json

        agent = Mock()
        state = Mock()
        call = Mock()

        # Setup complex context
        agent.klass = "DataAgent"
        agent.get_compact_information.return_value = (
            "DataAgent v1.0 - Processing active"
        )

        items_var = Mock()
        items_var.value = [
            {"name": "item1", "active": True, "value": 100},
            {"name": "item2", "active": False, "value": 200},
            {"name": "item3", "active": True, "value": 150},
        ]

        state.variables.variables = {"$items": items_var}
        agent.namespace_manager.namespace = {"len": len, "sum": sum, "json": json}

        context = LazyContextDict(agent, state, call)

        # Test complex expressions
        description = """Data Analysis Report:
Total items: {len(items)}
Active items: {len([x for x in items if x['active']])}
Total value: ${sum(x['value'] for x in items if x['active'])}
Agent status: {agent.get_compact_information()}"""

        result = evaluate_with_context(description, context)

        assert "Total items: 3" in result
        assert "Active items: 2" in result
        assert "Total value: $250" in result
        assert "DataAgent v1.0 - Processing active" in result

    def test_evaluate_with_timestamp_and_agent_info(self):
        """Test expressions using timestamp and agent information."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Setup agent context
        agent.klass = "SchedulerAgent"
        agent.id = "scheduler_001"

        user_var = Mock()
        user_var.value = "alice@example.com"

        state.variables.variables = {"$user": user_var}
        agent.namespace_manager.namespace = {}

        context = LazyContextDict(agent, state, call)

        # Test timestamp and agent expressions
        description = """Scheduled Task:
User: {user}
Agent: {agent.klass} ({agent.id})
Scheduled at: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Current call: {call}"""

        result = evaluate_with_context(description, context)

        assert "User: alice@example.com" in result
        assert "Agent: SchedulerAgent (scheduler_001)" in result
        assert "Scheduled at: 2025-" in result  # Should contain current year
        assert "Current call:" in result

    def test_evaluate_with_playbook_calls(self):
        """Test expressions that include playbook function calls."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock playbook functions
        def summarize_report(content):
            return f"Summary: {content[:50]}..."

        def count_items(items_list):
            return len(items_list)

        # Setup context with playbooks
        report_var = Mock()
        report_var.value = "This is a very long report content that needs to be summarized for display purposes."

        tasks_var = Mock()
        tasks_var.value = ["task1", "task2", "task3", "task4", "task5"]

        state.variables.variables = {"$report": report_var, "$tasks": tasks_var}
        agent.namespace_manager.namespace = {
            "SummarizeReport": summarize_report,
            "CountItems": count_items,
        }

        context = LazyContextDict(agent, state, call)

        # Test playbook call expressions
        description = """Daily Report:
{SummarizeReport(report)}
Total tasks: {CountItems(tasks)}
Status: {"Complete" if CountItems(tasks) > 3 else "In Progress"}"""

        result = evaluate_with_context(description, context)

        assert "Summary: This is a very long report content that needs to" in result
        assert "Total tasks: 5" in result
        assert "Status: Complete" in result

    def test_error_scenarios_with_location(self):
        """Test error scenarios with proper location reporting."""
        agent = Mock()
        state = Mock()
        call = Mock()

        state.variables.variables = {}
        agent.namespace_manager.namespace = {}

        context = LazyContextDict(agent, state, call)

        # Test error with location information
        description = """First line
Second line with error {nonexistent_variable}
Third line"""

        try:
            evaluate_with_context(description, context)
            assert False, "Should have raised an error"
        except ValueError as e:
            error_msg = str(e)
            assert "nonexistent_variable" in error_msg
            assert "line 2" in error_msg  # Should indicate line number
            assert "column" in error_msg  # Should indicate column number

    def test_developer_friendly_dollar_syntax(self):
        """Test that developers can use natural $variable syntax as they see in playbooks."""
        agent = Mock()
        state = Mock()
        call = Mock()

        # Mock state variables as developers see them (with $ prefix)
        user_var = Mock()
        user_var.value = {"name": "Alice", "email": "alice@example.com", "id": 123}

        status_var = Mock()
        status_var.value = "active"

        items_var = Mock()
        items_var.value = [
            {"name": "item1", "price": 10.99},
            {"name": "item2", "price": 25.50},
        ]

        state.variables.variables = {
            "$user": user_var,
            "$status": status_var,
            "$items": items_var,
        }
        agent.namespace_manager.namespace = {"len": len, "sum": sum, "round": round}

        context = LazyContextDict(agent, state, call)

        # Test that developers can use the natural $variable syntax they see
        description = """User Report:
Name: {$user['name']} (ID: {$user['id']})
Email: {$user['email']}
Status: {$status}
Items: {len($items)}
Total: ${round(sum(item['price'] for item in $items), 2)}
Active: {$status == 'active'}"""

        result = evaluate_with_context(description, context)

        expected_lines = [
            "User Report:",
            "Name: Alice (ID: 123)",
            "Email: alice@example.com",
            "Status: active",
            "Items: 2",
            "Total: $36.49",
            "Active: True",
        ]

        for expected_line in expected_lines:
            assert expected_line in result


if __name__ == "__main__":
    pytest.main([__file__])

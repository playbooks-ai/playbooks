"""Comprehensive tests for the expression engine."""

import ast
from datetime import datetime
from unittest.mock import Mock

import pytest

from playbooks.compilation.expression_engine import (
    ExpressionContext,
    ExpressionError,
    bind_call_parameters,
    extract_parameter_defaults_from_signature,
    extract_parameter_names_from_signature,
    extract_playbook_calls,
    extract_variables,
    format_value,
    parse_playbook_call,
    parse_to_ast,
    preprocess_expression,
    resolve_description_placeholders,
    validate_expression,
)
from playbooks.core.argument_types import LiteralValue, VariableReference


class TestPreprocessExpression:
    """Test the preprocess_expression function."""

    def test_simple_variable_replacement(self):
        """Test basic $variable replacement."""
        assert preprocess_expression("$name") == "name"
        assert preprocess_expression("$user_id") == "user_id"
        assert preprocess_expression("$_private") == "_private"

    def test_complex_expressions(self):
        """Test complex expressions with $variables."""
        assert preprocess_expression("$user.name") == "user.name"
        assert preprocess_expression("$order['id']") == "order['id']"
        assert preprocess_expression("$data[0].value") == "data[0].value"
        assert preprocess_expression("$config.db.host") == "config.db.host"

    def test_multiple_variables(self):
        """Test expressions with multiple variables."""
        assert preprocess_expression("$user + $order") == "user + order"
        assert preprocess_expression("$a.b + $c['d']") == "a.b + c['d']"

    def test_string_literals_preserved(self):
        """Test that string literals with $ are preserved."""
        assert preprocess_expression("'cost: $5.99'") == "'cost: $5.99'"
        assert preprocess_expression('"price $100"') == '"price $100"'

    def test_invalid_identifiers_preserved(self):
        """Test that invalid identifiers are not replaced."""
        assert preprocess_expression("$123") == "$123"  # Invalid identifier
        assert preprocess_expression("$$") == "$$"  # Invalid format

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        assert preprocess_expression("") == ""
        assert preprocess_expression("$") == "$"
        assert preprocess_expression("no_variables") == "no_variables"
        assert preprocess_expression(123) == "123"  # Non-string input


class TestParseToAst:
    """Test the parse_to_ast function."""

    def test_valid_expressions(self):
        """Test parsing valid expressions."""
        ast_node, error = parse_to_ast("user.name")
        assert ast_node is not None
        assert error is None
        assert isinstance(ast_node.body, ast.Attribute)

        ast_node, error = parse_to_ast("order['id']")
        assert ast_node is not None
        assert error is None
        assert isinstance(ast_node.body, ast.Subscript)

    def test_invalid_syntax(self):
        """Test parsing invalid syntax."""
        ast_node, error = parse_to_ast("user.")
        assert ast_node is None
        assert "Syntax error" in error

        ast_node, error = parse_to_ast("order[")
        assert ast_node is None
        assert error is not None

    def test_caching(self):
        """Test that parsing results are cached."""
        # Same expression should return identical results
        expr = "user.name"
        result1 = parse_to_ast(expr)
        result2 = parse_to_ast(expr)
        assert result1 == result2


class TestExtractVariables:
    """Test the extract_variables function."""

    def test_simple_variables(self):
        """Test extracting simple variables."""
        assert extract_variables("$user") == {"user"}
        assert extract_variables("$order_id") == {"order_id"}

    def test_complex_expressions(self):
        """Test extracting variables from complex expressions."""
        assert extract_variables("$user.name") == {"user"}
        assert extract_variables("$order['id']") == {"order"}
        assert extract_variables("$user + $order") == {"user", "order"}

    def test_no_variables(self):
        """Test expressions with no variables."""
        assert extract_variables("'no variables'") == set()
        assert extract_variables("123 + 456") == set()

    def test_edge_cases(self):
        """Test edge cases."""
        assert extract_variables("") == set()
        assert extract_variables(123) == set()


class TestValidateExpression:
    """Test the validate_expression function."""

    def test_valid_expressions(self):
        """Test validation of valid expressions."""
        is_valid, error = validate_expression("$user.name")
        assert is_valid is True
        assert error is None

        is_valid, error = validate_expression("$order['id'] + 1")
        assert is_valid is True
        assert error is None

    def test_invalid_syntax(self):
        """Test validation of invalid syntax."""
        is_valid, error = validate_expression("$user.")
        assert is_valid is False
        assert "Syntax error" in error

    def test_security_violations(self):
        """Test detection of security violations."""
        dangerous_exprs = [
            "__import__('os')",
            "eval('malicious_code')",
            "subprocess.call(['rm', '-rf', '/'])",
            "__builtins__.__dict__",
        ]

        for expr in dangerous_exprs:
            is_valid, error = validate_expression(expr)
            assert is_valid is False
            assert "Security violation" in error

    def test_non_string_input(self):
        """Test validation of non-string input."""
        is_valid, error = validate_expression(123)
        assert is_valid is False
        assert "must be a string" in error


class TestExpressionContext:
    """Test the ExpressionContext class."""

    def setup_method(self):
        """Set up test fixtures."""
        from dotmap import DotMap

        self.agent = Mock()
        self.state = Mock()
        self.call = Mock()
        self.call.playbook_klass = "TestPlaybook"

        # Use real DotMap for variables (no $ prefix, no .value wrapper)
        self.agent.state = DotMap()
        self.agent.state.test_var = "test_value"

        # Mock namespace manager
        namespace_dict = {"namespace_var": "namespace_value"}
        self.agent.namespace_manager = Mock(namespace=namespace_dict)

        self.context = ExpressionContext(agent=self.agent, call=self.call)

    def test_built_in_variables(self):
        """Test access to built-in variables."""
        assert self.context.resolve_variable("agent") == self.agent
        assert self.context.resolve_variable("call") == self.call
        assert isinstance(self.context.resolve_variable("timestamp"), datetime)

    def test_state_variable_resolution(self):
        """Test resolution of state variables."""
        assert self.context.resolve_variable("test_var") == "test_value"

    def test_namespace_variable_resolution(self):
        """Test resolution of namespace variables."""
        assert self.context.resolve_variable("namespace_var") == "namespace_value"

    def test_variable_not_found(self):
        """Test handling of undefined variables."""
        with pytest.raises(KeyError) as exc_info:
            self.context.resolve_variable("nonexistent")

        assert "Variable 'nonexistent' not found" in str(exc_info.value)

    def test_circular_reference_detection(self):
        """Test detection of circular references."""
        # Add the context to its own resolving set to simulate circular reference
        self.context._resolving.add("circular")

        with pytest.raises(RecursionError) as exc_info:
            self.context.resolve_variable("circular")

        assert "Circular reference detected" in str(exc_info.value)

    def test_variable_caching(self):
        """Test that variables are cached after first resolution."""
        # First access
        value1 = self.context.resolve_variable("test_var")

        # Modify the underlying state
        self.agent.state.test_var = "modified_value"

        # Second access should return cached value
        value2 = self.context.resolve_variable("test_var")
        assert value1 == value2 == "test_value"

    def test_evaluate_expression(self):
        """Test expression evaluation."""
        result = self.context.evaluate_expression("$test_var")
        assert result == "test_value"

        # Test with literal
        result = self.context.evaluate_expression("'literal_string'")
        assert result == "literal_string"

    def test_evaluate_expression_with_error(self):
        """Test expression evaluation with errors."""
        with pytest.raises(ExpressionError) as exc_info:
            self.context.evaluate_expression("$nonexistent")

        assert "name 'nonexistent' is not defined" in str(exc_info.value)

    def test_dict_like_access(self):
        """Test dict-like access for eval compatibility."""
        assert self.context["test_var"] == "test_value"
        assert self.context["agent"] == self.agent


class TestParsePlaybookCall:
    """Test the parse_playbook_call function."""

    def test_simple_call(self):
        """Test parsing simple playbook calls."""
        call = parse_playbook_call("GetOrder()")
        assert call.playbook_klass == "GetOrder"
        assert call.args == []
        assert call.kwargs == {}

    def test_call_with_args(self):
        """Test parsing calls with positional arguments."""
        call = parse_playbook_call("GetOrder($order_id)")
        assert call.playbook_klass == "GetOrder"
        assert isinstance(call.args[0], VariableReference)
        assert call.args[0].reference == "$order_id"

        call = parse_playbook_call("ProcessOrder($order, $user)")
        assert call.playbook_klass == "ProcessOrder"
        assert isinstance(call.args[0], VariableReference)
        assert call.args[0].reference == "$order"
        assert isinstance(call.args[1], VariableReference)
        assert call.args[1].reference == "$user"

    def test_call_with_kwargs(self):
        """Test parsing calls with keyword arguments."""
        call = parse_playbook_call("GetOrder(order_id=$id)")
        assert call.playbook_klass == "GetOrder"
        assert call.args == []
        assert isinstance(call.kwargs["order_id"], VariableReference)
        assert call.kwargs["order_id"].reference == "$id"

    def test_call_with_mixed_args(self):
        """Test parsing calls with both positional and keyword arguments."""
        call = parse_playbook_call("ProcessOrder($order, status='pending')")
        assert call.playbook_klass == "ProcessOrder"
        assert isinstance(call.args[0], VariableReference)
        assert call.args[0].reference == "$order"
        assert isinstance(call.kwargs["status"], LiteralValue)
        assert call.kwargs["status"].value == "pending"

    def test_call_with_boolean_literals(self):
        """Test parsing calls with boolean literals (true, false)."""
        # Test true literal
        call = parse_playbook_call(
            "FileSystem.list_directory(path=$folder, recursive=true)"
        )
        assert call.playbook_klass == "FileSystem.list_directory"
        assert isinstance(call.kwargs["path"], VariableReference)
        assert call.kwargs["path"].reference == "$folder"
        assert isinstance(call.kwargs["recursive"], LiteralValue)
        assert isinstance(call.kwargs["recursive"].value, bool)
        assert call.kwargs["recursive"].value is True

        # Test false literal
        call = parse_playbook_call(
            "FileSystem.list_directory(path=$folder, recursive=false)"
        )
        assert isinstance(call.kwargs["recursive"], LiteralValue)
        assert call.kwargs["recursive"].value is False
        assert isinstance(call.kwargs["recursive"].value, bool)

        # Test with null literal
        call = parse_playbook_call("ProcessData(data=$data, default=null)")
        assert isinstance(call.kwargs["default"], LiteralValue)
        assert call.kwargs["default"].value is None

    def test_complex_variable_expressions(self):
        """Test parsing calls with complex variable expressions."""
        call = parse_playbook_call("GetOrder($order['id'])")
        # Accept both single and double quotes (Python AST may normalize)
        assert isinstance(call.args[0], VariableReference)
        assert call.args[0].reference in ["$order['id']", '$order["id"]']

        call = parse_playbook_call("ProcessUser($user.profile)")
        assert isinstance(call.args[0], VariableReference)
        assert call.args[0].reference == "$user.profile"

    def test_module_qualified_calls(self):
        """Test parsing module-qualified playbook calls."""
        call = parse_playbook_call("orders.GetOrder($id)")
        assert call.playbook_klass == "orders.GetOrder"

    def test_invalid_call_syntax(self):
        """Test handling of invalid call syntax."""
        with pytest.raises(ExpressionError):
            parse_playbook_call("not_a_call")

        with pytest.raises(ExpressionError):
            parse_playbook_call("invalid_syntax(")


class TestExtractPlaybookCalls:
    """Test the extract_playbook_calls function."""

    def test_single_call(self):
        """Test extracting single playbook call."""
        text = "`GetOrder($order_id)`"
        calls = extract_playbook_calls(text)
        assert calls == ["GetOrder($order_id)"]

    def test_multiple_calls(self):
        """Test extracting multiple playbook calls."""
        text = "First `GetOrder($id)` then `ProcessOrder($order)`"
        calls = extract_playbook_calls(text)
        assert calls == ["GetOrder($id)", "ProcessOrder($order)"]

    def test_calls_with_assignment(self):
        """Test extracting calls with variable assignment."""
        text = "`$result = GetOrder($id)`"
        calls = extract_playbook_calls(text)
        assert calls == ["GetOrder($id)"]

    def test_no_calls(self):
        """Test text with no playbook calls."""
        text = "Just regular text with no calls"
        calls = extract_playbook_calls(text)
        assert calls == []

    def test_malformed_calls(self):
        """Test handling of malformed calls."""
        text = "`NotACall` and `AlsoNotACall()`"
        calls = extract_playbook_calls(text)
        assert calls == ["AlsoNotACall()"]  # Only valid call format


class TestResolveDescriptionPlaceholders:
    """Test the resolve_description_placeholders function."""

    def setup_method(self):
        """Set up test fixtures."""
        from dotmap import DotMap

        self.agent = Mock()
        self.state = Mock()
        self.call = Mock()

        # Use real DotMap for variables (no $ prefix, no .value wrapper)
        self.agent.state = DotMap()
        self.agent.state.order_id = "12345"

        # Mock namespace manager
        namespace_dict = {}
        self.agent.namespace_manager = Mock(namespace=namespace_dict)

        self.context = ExpressionContext(agent=self.agent, call=self.call)

    @pytest.mark.asyncio
    async def test_simple_placeholder(self):
        """Test resolving simple placeholders."""
        description = "Order ID: {$order_id}"
        result = await resolve_description_placeholders(description, self.context)
        assert result == "Order ID: 12345"

    @pytest.mark.asyncio
    async def test_multiple_placeholders(self):
        """Test resolving multiple placeholders."""
        # Add another variable (no $ prefix, no wrapper)
        self.agent.state.status = "pending"

        description = "Order {$order_id} has status {$status}"
        result = await resolve_description_placeholders(description, self.context)
        assert result == "Order 12345 has status pending"

    @pytest.mark.asyncio
    async def test_no_placeholders(self):
        """Test description with no placeholders."""
        description = "Simple description without placeholders"
        result = await resolve_description_placeholders(description, self.context)
        assert result == description

    @pytest.mark.asyncio
    async def test_complex_expressions(self):
        """Test placeholders with complex expressions."""
        description = "Order: {'order' + '_id'}"  # This would eval to 'order_id'
        # Since this isn't a variable reference, it should work as a literal expression
        result = await resolve_description_placeholders(description, self.context)
        assert result == "Order: order_id"

    @pytest.mark.asyncio
    async def test_nested_braces(self):
        """Test handling of nested braces."""
        # This is a complex case - for now just test that it doesn't crash
        description = "Data: {{'key': 'value'}}"
        try:
            result = await resolve_description_placeholders(description, self.context)
            # Should resolve to the dict representation
            assert "key" in result and "value" in result
        except ExpressionError:
            # This is acceptable for malformed expressions
            pass

    @pytest.mark.asyncio
    async def test_invalid_expression_error(self):
        """Test error handling for invalid expressions."""
        description = "Invalid: {$nonexistent}"
        with pytest.raises(ExpressionError) as exc_info:
            await resolve_description_placeholders(description, self.context)

        assert "'nonexistent' is not defined" in str(exc_info.value)


class TestFormatValue:
    """Test the format_value function."""

    def test_none_value(self):
        """Test formatting None values."""
        assert format_value(None) == ""

    def test_simple_values(self):
        """Test formatting simple values."""
        assert format_value("string") == "string"
        assert format_value(123) == "123"
        assert format_value(True) == "True"

    def test_small_collections(self):
        """Test formatting small collections."""
        assert format_value([1, 2, 3]) == "[1, 2, 3]"
        assert format_value({"key": "value"}) == '{"key": "value"}'

    def test_large_collections(self):
        """Test formatting large collections with pretty printing."""
        large_dict = {f"key{i}": f"value{i}" for i in range(10)}
        result = format_value(large_dict)
        # Should use pretty printing (multiline)
        assert "\n" in result
        assert "  " in result  # Indentation

    def test_nested_collections(self):
        """Test formatting nested collections."""
        nested = {"user": {"name": "John", "orders": [1, 2, 3]}}
        result = format_value(nested)
        assert "user" in result
        assert "name" in result
        assert "John" in result


class TestExpressionError:
    """Test the ExpressionError class."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = ExpressionError("$invalid", "Test error message")
        assert error.expr == "$invalid"
        assert error.message == "Test error message"
        assert "Error evaluating '$invalid'" in str(error)

    def test_error_with_position(self):
        """Test error with line and column information."""
        error = ExpressionError("$invalid", "Test error", line=2, column=5)
        assert error.line == 2
        assert error.column == 5
        assert "at line 2, column 5" in str(error)

    def test_error_with_line_only(self):
        """Test error with line information only."""
        error = ExpressionError("$invalid", "Test error", line=3)
        assert error.line == 3
        assert error.column is None
        assert "at line 3" in str(error)
        assert "column" not in str(error)


class TestIntegration:
    """Integration tests for the expression engine."""

    def setup_method(self):
        """Set up integration test fixtures."""
        from dotmap import DotMap

        self.agent = Mock()
        self.state = Mock()
        self.call = Mock()
        self.call.playbook_klass = "TestPlaybook"

        # Use real DotMap for variables with raw values (no $ prefix, no wrappers)
        self.agent.state = DotMap()
        self.agent.state.order = {
            "id": "12345",
            "status": "pending",
            "items": [{"name": "item1", "price": 99.99}],
        }
        self.agent.state.user = {"name": "John Doe", "email": "john@example.com"}

        # Mock namespace manager
        namespace_dict = {"current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.agent.namespace_manager = Mock(namespace=namespace_dict)

        self.context = ExpressionContext(agent=self.agent, call=self.call)

    @pytest.mark.asyncio
    async def test_complex_description_resolution(self):
        """Test resolving complex description with multiple variable types."""
        description = """
        Order Details:
        - Order ID: {$order['id']}
        - Customer: {$user['name']} ({$user['email']})
        - Status: {$order['status']}
        - Total Items: {len($order['items'])}
        - First Item: {$order['items'][0]['name']} - ${$order['items'][0]['price']}
        - Current Time: {current_time}
        """

        result = await resolve_description_placeholders(description, self.context)

        # Verify all placeholders were resolved
        assert "12345" in result  # order id
        assert "John Doe" in result  # user name
        assert "john@example.com" in result  # user email
        assert "pending" in result  # order status
        assert "1" in result  # len(items)
        assert "item1" in result  # first item name
        assert "99.99" in result  # first item price
        assert ":" in result  # current_time format

    def test_playbook_call_with_complex_args(self):
        """Test parsing playbook calls with complex arguments."""
        call_str = "ProcessOrder($order, customer=$user, notify_email=$user['email'], total=len($order['items']))"

        call = parse_playbook_call(call_str, self.context)

        assert call.playbook_klass == "ProcessOrder"
        assert isinstance(call.args[0], VariableReference)
        assert call.args[0].reference == "$order"
        assert isinstance(call.kwargs["customer"], VariableReference)
        assert call.kwargs["customer"].reference == "$user"
        # Accept both quote formats due to AST normalization
        assert isinstance(call.kwargs["notify_email"], VariableReference)
        assert call.kwargs["notify_email"].reference in [
            "$user['email']",
            '$user["email"]',
        ]
        # Function call should preserve variable references
        assert isinstance(call.kwargs["total"], VariableReference)
        assert call.kwargs["total"].reference.startswith("len($order")
        assert "items" in call.kwargs["total"].reference

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test a complete end-to-end workflow."""
        # 1. Extract calls from text
        text = "Process the order: `ProcessOrder($order, status='confirmed')` and notify user: `NotifyUser($user['email'])`"
        calls = extract_playbook_calls(text)
        assert len(calls) == 2

        # 2. Parse each call
        call1 = parse_playbook_call(calls[0], self.context)
        call2 = parse_playbook_call(calls[1], self.context)

        assert call1.playbook_klass == "ProcessOrder"
        assert call2.playbook_klass == "NotifyUser"

        # 3. Resolve description with context
        description = "Processing order {$order['id']} for {$user['name']}"
        resolved = await resolve_description_placeholders(description, self.context)

        assert "12345" in resolved
        assert "John Doe" in resolved

    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """Test integrated error handling across components."""
        # Test invalid variable in description
        with pytest.raises(ExpressionError) as exc_info:
            await resolve_description_placeholders(
                "Invalid: {$nonexistent}", self.context
            )

        assert "name 'nonexistent' is not defined" in str(exc_info.value)
        assert "Error evaluating '$nonexistent'" in str(exc_info.value)

        # Test invalid playbook call
        with pytest.raises(ExpressionError) as exc_info:
            parse_playbook_call("InvalidCall(unclosed_paren")

        assert "Failed to parse playbook call" in str(exc_info.value)

    def test_performance_with_caching(self):
        """Test that caching improves performance for repeated operations."""
        expr = "$order['id']"

        # First evaluation should populate cache
        result1 = self.context.evaluate_expression(expr)

        # Subsequent evaluations should use cache
        result2 = self.context.evaluate_expression(expr)
        result3 = self.context.evaluate_expression(expr)

        # $order['id'] should return the 'id' value from the order dict
        assert result1 == result2 == result3 == "12345"


class TestExtractParameterNamesFromSignature:
    """Test the extract_parameter_names_from_signature function."""

    def test_simple_parameters(self):
        """Test extracting simple parameter names."""
        sig = "MyPlaybook($arg1:str, $arg2:int)"
        params = extract_parameter_names_from_signature(sig)
        assert params == ["arg1", "arg2"]

    def test_parameters_without_types(self):
        """Test extracting parameters without type annotations."""
        sig = "MyPlaybook($name, $value)"
        params = extract_parameter_names_from_signature(sig)
        assert params == ["name", "value"]

    def test_parameters_without_dollar_prefix(self):
        """Test extracting parameters without $ prefix."""
        sig = "MyPlaybook(arg1:str, arg2:int)"
        params = extract_parameter_names_from_signature(sig)
        assert params == ["arg1", "arg2"]

    def test_no_parameters(self):
        """Test extracting from signature with no parameters."""
        sig = "MyPlaybook()"
        params = extract_parameter_names_from_signature(sig)
        assert params == []

    def test_empty_signature(self):
        """Test handling of empty signature."""
        params = extract_parameter_names_from_signature("")
        assert params == []

    def test_complex_signature(self):
        """Test extracting from complex signature with return type."""
        sig = "LoadRelevantContext($question:str, $current_reasoning:str) -> dict"
        params = extract_parameter_names_from_signature(sig)
        assert params == ["question", "current_reasoning"]

    def test_invalid_signature_graceful_failure(self):
        """Test that invalid signatures fail gracefully."""
        sig = "InvalidSignature(unclosed"
        params = extract_parameter_names_from_signature(sig)
        assert params == []  # Should return empty list instead of crashing


class TestExtractParameterDefaultsFromSignature:
    """Test the extract_parameter_defaults_from_signature function."""

    def test_simple_defaults(self):
        """Test extracting simple default values."""
        sig = "Func($a:str, $b:int=10)"
        defaults = extract_parameter_defaults_from_signature(sig)
        assert defaults == {"b": 10}

    def test_multiple_defaults(self):
        """Test extracting multiple default values."""
        sig = "Func($a:str, $b:int=10, $c:bool=True)"
        defaults = extract_parameter_defaults_from_signature(sig)
        assert defaults == {"b": 10, "c": True}

    def test_string_defaults(self):
        """Test extracting string default values."""
        sig = "Func($a:str, $b:str='hello')"
        defaults = extract_parameter_defaults_from_signature(sig)
        assert defaults == {"b": "hello"}

    def test_no_defaults(self):
        """Test signature with no defaults."""
        sig = "Func($a:str, $b:int)"
        defaults = extract_parameter_defaults_from_signature(sig)
        assert defaults == {}

    def test_mixed_defaults(self):
        """Test signature with some params having defaults."""
        sig = "PB1($a:str, $b:int=10) -> None"
        defaults = extract_parameter_defaults_from_signature(sig)
        assert defaults == {"b": 10}

    def test_none_default(self):
        """Test None as default value."""
        sig = "Func($a:str, $b:int=None)"
        defaults = extract_parameter_defaults_from_signature(sig)
        assert defaults == {"b": None}


class TestBindCallParameters:
    """Test the bind_call_parameters function."""

    def test_positional_args_only(self):
        """Test binding with only positional arguments."""
        sig = "Func($a:str, $b:int)"
        args = ["hello", 42]
        kwargs = {}
        result = bind_call_parameters(sig, args, kwargs)
        assert result == {"a": "hello", "b": 42}

    def test_keyword_args_only(self):
        """Test binding with only keyword arguments."""
        sig = "Func($a:str, $b:int)"
        args = []
        kwargs = {"a": "hello", "b": 42}
        result = bind_call_parameters(sig, args, kwargs)
        assert result == {"a": "hello", "b": 42}

    def test_mixed_args(self):
        """Test binding with mixed positional and keyword arguments."""
        sig = "Func($a:str, $b:int, $c:bool)"
        args = ["hello"]
        kwargs = {"b": 42, "c": True}
        result = bind_call_parameters(sig, args, kwargs)
        assert result == {"a": "hello", "b": 42, "c": True}

    def test_kwargs_override_positional(self):
        """Test that keyword arguments override positional arguments."""
        sig = "Func($a:str, $b:int)"
        args = ["hello", 42]
        kwargs = {"b": 99}
        result = bind_call_parameters(sig, args, kwargs)
        assert result == {"a": "hello", "b": 99}

    def test_partial_arguments(self):
        """Test binding with only some arguments provided (for optional params)."""
        sig = "Func($a:str, $b:int, $c:bool)"
        args = ["hello"]
        kwargs = {}
        result = bind_call_parameters(sig, args, kwargs)
        # Should only return what was provided
        assert result == {"a": "hello"}

    def test_default_values_filled(self):
        """Test that default values are filled in when not provided."""
        sig = "Func($a:str, $b:int=10)"
        args = ["hello"]
        kwargs = {}
        result = bind_call_parameters(sig, args, kwargs)
        assert result == {"a": "hello", "b": 10}

    def test_default_values_overridden(self):
        """Test that provided values override defaults."""
        sig = "Func($a:str, $b:int=10)"
        args = ["hello", 99]
        kwargs = {}
        result = bind_call_parameters(sig, args, kwargs)
        assert result == {"a": "hello", "b": 99}

    def test_multiple_defaults_partial_override(self):
        """Test multiple defaults with partial override."""
        sig = "Func($a:str, $b:int=10, $c:bool=True)"
        args = ["hello"]
        kwargs = {"b": 99}
        result = bind_call_parameters(sig, args, kwargs)
        assert result == {"a": "hello", "b": 99, "c": True}


class TestParameterResolution:
    """Test parameter resolution in ExpressionContext."""

    def setup_method(self):
        """Set up test fixtures."""
        from dotmap import DotMap

        self.agent = Mock()
        self.state = Mock()
        self.call = Mock()

        # Mock a playbook with signature
        self.playbook = Mock()
        self.playbook.signature = (
            "LoadRelevantContext($question:str, $current_reasoning:str)"
        )

        # Set up call with arguments
        self.call.playbook_klass = "LoadRelevantContext"
        self.call.args = [LiteralValue("How are you?"), LiteralValue("Starting")]
        self.call.kwargs = {}

        # Mock agent playbooks
        self.agent.playbooks = {"LoadRelevantContext": self.playbook}

        # Use real DotMap for variables
        self.agent.state = DotMap()

        # Mock namespace manager
        self.agent.namespace_manager = Mock(namespace={})

        self.context = ExpressionContext(agent=self.agent, call=self.call)

    def test_resolve_positional_parameters(self):
        """Test resolving positional parameters."""
        # First parameter
        result = self.context.resolve_variable("question")
        assert result == "How are you?"

        # Second parameter
        result = self.context.resolve_variable("current_reasoning")
        assert result == "Starting"

    def test_resolve_keyword_parameters(self):
        """Test resolving keyword parameters."""
        # Set up with keyword arguments
        self.call.args = []
        self.call.kwargs = {
            "question": LiteralValue("What is AI?"),
            "current_reasoning": LiteralValue("Exploring"),
        }

        # Reset context
        self.context = ExpressionContext(agent=self.agent, call=self.call)

        result = self.context.resolve_variable("question")
        assert result == "What is AI?"

        result = self.context.resolve_variable("current_reasoning")
        assert result == "Exploring"

    def test_parameters_shadow_state_variables(self):
        """Test that parameters shadow state variables with the same name."""
        # Add a state variable with the same name as a parameter (no $ prefix, no wrapper)
        self.agent.state.question = "global_question"

        # Reset context to pick up the new state
        self.context = ExpressionContext(agent=self.agent, call=self.call)

        # Parameter should take precedence over state variable
        result = self.context.resolve_variable("question")
        assert result == "How are you?"  # From parameter, not "global_question"

    def test_state_variables_accessible_when_no_parameter_match(self):
        """Test that state variables are accessible when there's no matching parameter."""
        # Add a state variable that doesn't match any parameter (no $ prefix, no wrapper)
        self.agent.state.other_var = "some_global_value"

        # Reset context
        self.context = ExpressionContext(agent=self.agent, call=self.call)

        # Should resolve from state since no parameter named "other_var"
        result = self.context.resolve_variable("other_var")
        assert result == "some_global_value"

    def test_parameter_caching(self):
        """Test that parameter binding is cached."""
        # First access
        result1 = self.context.resolve_variable("question")

        # Change the underlying call args (simulating mutation)
        self.call.args[0] = LiteralValue("Changed question")

        # Second access should return cached parameter binding
        result2 = self.context.resolve_variable("question")

        # Both should be the original value due to caching
        assert result1 == result2 == "How are you?"

    def test_variable_reference_parameters_resolved(self):
        """Test that VariableReference parameters are resolved to actual values."""
        # Add a state variable (no $ prefix, no wrapper)
        self.agent.state.source_var = "resolved_value"

        # Set up call with VariableReference
        self.call.args = [VariableReference("$source_var"), LiteralValue("Starting")]

        # Reset context
        self.context = ExpressionContext(agent=self.agent, call=self.call)

        # Parameter should be resolved to the value from state
        result = self.context.resolve_variable("question")
        assert result == "resolved_value"

    def test_no_playbook_signature_graceful(self):
        """Test graceful handling when playbook has no signature."""
        # Remove signature
        self.playbook.signature = None

        # Reset context
        self.context = ExpressionContext(agent=self.agent, call=self.call)

        # Should not crash, just not find the parameter
        with pytest.raises(KeyError):
            self.context.resolve_variable("question")

    @pytest.mark.asyncio
    async def test_parameters_in_description_placeholders(self):
        """Test that parameters work in description placeholder resolution."""
        description = (
            "Find context for: {$question}\nCurrent reasoning: {$current_reasoning}"
        )
        result = await resolve_description_placeholders(description, self.context)
        assert result == "Find context for: How are you?\nCurrent reasoning: Starting"

    def test_default_parameter_values(self):
        """Test that default parameter values work correctly."""
        # Set up playbook with default parameter
        self.playbook.signature = "PB1($a:str, $b:int=10) -> None"

        # Call with only first argument
        self.call.args = [LiteralValue("World")]
        self.call.kwargs = {}

        # Add a state variable (no $ prefix, no wrapper)
        self.agent.state.var1 = "hello"

        # Reset context
        self.context = ExpressionContext(agent=self.agent, call=self.call)

        # Test parameter with default
        result_b = self.context.resolve_variable("b")
        assert result_b == 10

        # Test provided parameter
        result_a = self.context.resolve_variable("a")
        assert result_a == "World"

        # Test state variable
        result_var1 = self.context.resolve_variable("var1")
        assert result_var1 == "hello"

    @pytest.mark.asyncio
    async def test_default_parameters_in_description(self):
        """Test the full user scenario with defaults in description placeholders."""
        # Create a new playbook with default parameter
        playbook_with_defaults = Mock()
        playbook_with_defaults.signature = "PB1($a:str, $b:int=10) -> None"

        # Update agent playbooks
        self.agent.playbooks["PB1"] = playbook_with_defaults

        # Call with only first argument
        self.call.playbook_klass = "PB1"
        self.call.args = [LiteralValue("World")]
        self.call.kwargs = {}

        # Add a state variable (no $ prefix, no wrapper)
        self.agent.state.var1 = "hello"

        # Create fresh context with new configuration
        context = ExpressionContext(agent=self.agent, call=self.call)

        # Test description with mixed variables (state, parameter, default parameter)
        description = "This playbook says {$var1}, {$a} {$b} times"
        result = await resolve_description_placeholders(description, context)
        assert result == "This playbook says hello, World 10 times"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

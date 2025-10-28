"""Tests for preprocess_program function."""

from playbooks.utils.expression_engine import preprocess_program


class TestPreprocessProgram:
    """Test suite for preprocess_program function."""

    def test_simple_variable(self):
        """Test simple $variable conversion."""
        code = 'Say("user", $message)'
        result = preprocess_program(code)
        assert result == 'Say("user", message)'

    def test_multiple_variables(self):
        """Test multiple variable conversions."""
        code = "$result = $x + $y"
        result = preprocess_program(code)
        assert result == "result = x + y"

    def test_variable_in_string_literal_preserved(self):
        """Test that $var in string literals is preserved."""
        code = 'Say("user", "cost: $5.99")'
        result = preprocess_program(code)
        # String literal $5.99 should be preserved
        assert "$5.99" in result

    def test_fstring_with_variable(self):
        """Test f-string with $variable."""
        code = 'Say("user", f"Hello {$name}")'
        result = preprocess_program(code)
        assert result == 'Say("user", f"Hello {name}")'

    def test_nested_expression(self):
        """Test nested expressions with $variables."""
        code = '$result = $data["key"] + $offset'
        result = preprocess_program(code)
        assert result == 'result = data["key"] + offset'

    def test_attribute_access(self):
        """Test attribute access with $."""
        code = "$value = $obj.attribute"
        result = preprocess_program(code)
        assert result == "value = obj.attribute"

    def test_method_call(self):
        """Test method calls with $."""
        code = "$result = $obj.method()"
        result = preprocess_program(code)
        assert result == "result = obj.method()"

    def test_complex_expression(self):
        """Test complex expression with multiple $vars."""
        code = "$x = ($a + $b) * $c - $d.value"
        result = preprocess_program(code)
        assert result == "x = (a + b) * c - d.value"

    def test_dollar_in_quoted_string_not_converted(self):
        """Test that $ in quoted strings is not converted."""
        code = 'x = "price is $50"'
        result = preprocess_program(code)
        assert result == 'x = "price is $50"'

    def test_single_dollar_not_converted(self):
        """Test that $ alone (not identifier) is not converted."""
        code = 'x = "$ is dollar"'
        result = preprocess_program(code)
        assert result == 'x = "$ is dollar"'

    def test_double_dollar_not_converted(self):
        """Test that $$ is not converted."""
        code = 'x = "$$"'
        result = preprocess_program(code)
        assert result == 'x = "$$"'

    def test_dollar_number_not_converted(self):
        """Test that $123 is not converted (invalid identifier)."""
        code = 'x = "$123"'
        result = preprocess_program(code)
        assert result == 'x = "$123"'

    def test_empty_code(self):
        """Test preprocessing empty code."""
        result = preprocess_program("")
        assert result == ""

    def test_code_without_variables(self):
        """Test code without any $variables."""
        code = 'x = 5\ny = "hello"'
        result = preprocess_program(code)
        assert result == code

    def test_multiline_code(self):
        """Test multiline code with variables."""
        code = """Step("Step1:01:QUE")
Say("user", $message)
$x = $count + 1"""
        result = preprocess_program(code)
        assert "message" in result
        assert "count" in result
        assert "$" not in result.split("\n")[1].split(",")[1]  # No $ in message part

    def test_artifact_with_variable(self):
        """Test Artifact with $variable."""
        code = 'Artifact("name", "summary", $content)'
        result = preprocess_program(code)
        assert result == 'Artifact("name", "summary", content)'

    def test_complex_real_world_code(self):
        """Test complex real-world playbook code."""
        code = """
# execution_id: 1
# recap: welcoming user
# plan: greet user and trigger event
Step("Welcome:01:QUE")
Say("user", f"Hello {$user_name}!")
$greeting = $user_name + " says hello"
Trigger("UserGreeted")
Yld("user")
"""
        result = preprocess_program(code)
        # Verify $variables are converted
        assert "user_name" in result
        assert "${" not in result  # No {$ syntax
        # Verify code structure is preserved
        assert "execution_id" in result
        assert "recap" in result
        assert "plan" in result
        assert "Step(" in result
        assert "Say(" in result

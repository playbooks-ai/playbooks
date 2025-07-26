"""Tests for the variable resolution functionality."""

import pytest
from playbooks.utils.variable_resolution import resolve_variable_ast


class TestVariableResolution:
    """Test cases for resolve_variable_ast function."""

    def test_simple_variable_access(self):
        """Test simple variable access."""
        assert resolve_variable_ast("$name", {"$name": "Steve"}) == "Steve"
        assert resolve_variable_ast("$age", {"$age": 25}) == 25
        assert resolve_variable_ast("$active", {"$active": True}) is True
        assert resolve_variable_ast("$balance", {"$balance": 100.50}) == 100.50
        assert resolve_variable_ast("$data", {"$data": None}) is None

    def test_dictionary_dot_notation(self):
        """Test dictionary access with dot notation."""
        variables = {"$user": {"name": "Alice", "age": 30}}
        assert resolve_variable_ast("$user.name", variables) == "Alice"
        assert resolve_variable_ast("$user.age", variables) == 30

    def test_dictionary_bracket_notation(self):
        """Test dictionary access with bracket notation."""
        variables = {"$user": {"name": "Bob", "age": 25}}
        assert resolve_variable_ast('$user["name"]', variables) == "Bob"
        assert resolve_variable_ast("$user['name']", variables) == "Bob"
        
        # Test with spaces in key
        variables = {"$user": {"full name": "Bob Smith"}}
        assert resolve_variable_ast('$user["full name"]', variables) == "Bob Smith"

    def test_nested_dictionary_access(self):
        """Test nested dictionary access."""
        variables = {"$config": {"db": {"host": "localhost", "port": 5432}}}
        assert resolve_variable_ast("$config.db.host", variables) == "localhost"
        assert resolve_variable_ast("$config.db.port", variables) == 5432
        assert resolve_variable_ast('$config["db"]["host"]', variables) == "localhost"
        assert resolve_variable_ast("$config['db']['host']", variables) == "localhost"

    def test_list_array_access(self):
        """Test list/array access."""
        variables = {"$items": [1, 2, 3, 4, 5]}
        assert resolve_variable_ast("$items[0]", variables) == 1
        assert resolve_variable_ast("$items[2]", variables) == 3
        assert resolve_variable_ast("$items[-1]", variables) == 5
        
        variables = {"$items": ["a", "b", "c"]}
        assert resolve_variable_ast("$items[1]", variables) == "b"

    def test_mixed_notation(self):
        """Test mixed notation."""
        variables = {"$users": [{"name": "Alice"}, {"name": "Bob"}]}
        assert resolve_variable_ast("$users[0].name", variables) == "Alice"
        assert resolve_variable_ast("$users[1].name", variables) == "Bob"
        assert resolve_variable_ast('$users[0]["name"]', variables) == "Alice"
        
        variables = {"$data": {"users": [{"id": 1}, {"id": 2}]}}
        assert resolve_variable_ast("$data.users[0].id", variables) == 1
        assert resolve_variable_ast('$data["users"][1]["id"]', variables) == 2

    def test_complex_nested_structures(self):
        """Test complex nested structures."""
        variables = {
            "$company": {
                "departments": {
                    "engineering": {
                        "employees": [{"name": "Alice", "role": "dev"}]
                    }
                }
            }
        }
        assert resolve_variable_ast(
            "$company.departments.engineering.employees[0].name", variables
        ) == "Alice"
        assert resolve_variable_ast(
            '$company["departments"]["engineering"]["employees"][0]["role"]', variables
        ) == "dev"

    def test_special_cases(self):
        """Test special cases."""
        assert resolve_variable_ast("$empty_list", {"$empty_list": []}) == []
        assert resolve_variable_ast("$empty_dict", {"$empty_dict": {}}) == {}
        assert resolve_variable_ast("$zero", {"$zero": 0}) == 0
        assert resolve_variable_ast("$false", {"$false": False}) is False
        assert resolve_variable_ast("$empty_string", {"$empty_string": ""}) == ""

    def test_numeric_indices(self):
        """Test numeric indices."""
        variables = {"$matrix": [[1, 2], [3, 4]]}
        assert resolve_variable_ast("$matrix[0][0]", variables) == 1
        assert resolve_variable_ast("$matrix[1][1]", variables) == 4

    def test_invalid_syntax_returns_original(self):
        """Test that invalid syntax returns original expression."""
        variables = {"$name": "Steve"}
        assert resolve_variable_ast("$name.", variables) == "$name."
        assert resolve_variable_ast("$name[", variables) == "$name["
        assert resolve_variable_ast("$name]", variables) == "$name]"

    def test_non_string_expressions(self):
        """Test non-string expressions return as-is."""
        variables = {"$num": 42}
        assert resolve_variable_ast(123, variables) == 123
        assert resolve_variable_ast(None, variables) is None
        assert resolve_variable_ast(True, variables) is True

    def test_expressions_without_dollar_prefix(self):
        """Test expressions without $ prefix return as-is."""
        variables = {"$name": "Steve"}
        assert resolve_variable_ast("name", variables) == "name"
        assert resolve_variable_ast("regular string", variables) == "regular string"

    def test_unicode_and_special_characters(self):
        """Test unicode and special characters."""
        variables = {"$data": {"😀": "emoji_key"}}
        assert resolve_variable_ast('$data["😀"]', variables) == "emoji_key"
        
        variables = {"$user": {"name": "José"}}
        assert resolve_variable_ast("$user.name", variables) == "José"

    def test_mixed_types_in_collections(self):
        """Test mixed types in collections."""
        variables = {"$mixed": [1, "two", {"three": 3}, [4, 5]]}
        assert resolve_variable_ast("$mixed[0]", variables) == 1
        assert resolve_variable_ast("$mixed[1]", variables) == "two"
        assert resolve_variable_ast("$mixed[2].three", variables) == 3
        assert resolve_variable_ast("$mixed[3][0]", variables) == 4

    def test_variable_not_found_error(self):
        """Test KeyError when variable is not found."""
        with pytest.raises(KeyError, match="Variable \\$nonexistent not found"):
            resolve_variable_ast("$nonexistent", {})
        
        with pytest.raises(KeyError, match="Variable \\$unknown_var not found"):
            resolve_variable_ast("$unknown_var", {"$user": {"name": "Alice"}})

    def test_attribute_not_found_error(self):
        """Test AttributeError when attribute is not found."""
        variables = {"$user": {"name": "Alice"}}
        
        with pytest.raises(AttributeError):
            resolve_variable_ast("$user.nonexistent", variables)
        
        with pytest.raises(AttributeError):
            resolve_variable_ast("$user.age", variables)
        
        variables = {"$config": {"db": {"host": "localhost"}}}
        with pytest.raises(AttributeError):
            resolve_variable_ast("$config.db.port", variables)
        
        variables = {"$obj": {"x": 1}}
        with pytest.raises(AttributeError):
            resolve_variable_ast("$obj.y.z", variables)

    def test_index_out_of_bounds_error(self):
        """Test IndexError when list index is out of bounds."""
        variables = {"$items": [1, 2, 3]}
        
        with pytest.raises(IndexError):
            resolve_variable_ast("$items[10]", variables)
        
        with pytest.raises(IndexError):
            resolve_variable_ast("$items[5]", variables)
        
        with pytest.raises(IndexError):
            resolve_variable_ast("$items[-10]", variables)
        
        variables = {"$items": []}
        with pytest.raises(IndexError):
            resolve_variable_ast("$items[0]", variables)

    def test_mixed_errors(self):
        """Test mixed error conditions."""
        variables = {"$data": {"users": [{"name": "Alice"}]}}
        
        with pytest.raises(IndexError):
            resolve_variable_ast("$data.users[5].name", variables)
        
        with pytest.raises(AttributeError):
            resolve_variable_ast("$data.users[0].age", variables)
        
        variables = {"$data": {"users": []}}
        with pytest.raises(IndexError):
            resolve_variable_ast("$data.users[0].name", variables)
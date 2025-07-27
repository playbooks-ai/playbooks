import re
from typing import Any, Dict


def resolve_variable_ast(expression: str, variables: Dict[str, Any]) -> Any:
    """
    Resolve variable references using Python's AST parser.

    Supports:
    - Simple variables: $name
    - Dot notation: $user.name, $config.db.host
    - Bracket notation: $user["name"], $data['key']
    - Mixed notation: $user.addresses[0], $config["servers"]["prod"]
    - Nested access: $users[0].name, $data["users"][0]["name"]

    Args:
        expression: The expression to resolve (e.g., "$user.name")
        variables: Dictionary of available variables

    Returns:
        The resolved value

    Raises:
        KeyError: If a variable is not found
        AttributeError: If an attribute is not found
        IndexError: If a list index is out of bounds
    """
    if not isinstance(expression, str):
        return expression

    # If it doesn't start with $, return as-is
    if not expression.startswith("$"):
        return expression

    class DotDict(dict):
        """A dictionary that supports dot notation access."""

        def __getattr__(self, key):
            try:
                value = self[key]
                if isinstance(value, dict):
                    return DotDict(value)
                elif isinstance(value, list):
                    return [
                        DotDict(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                return value
            except KeyError:
                raise AttributeError(
                    f"'{type(self).__name__}' object has no attribute '{key}'"
                )

    def convert_to_dotdict(obj):
        """Recursively convert dictionaries to DotDict."""
        if isinstance(obj, dict):
            return DotDict({k: convert_to_dotdict(v) for k, v in obj.items()})
        elif isinstance(obj, list):
            return [convert_to_dotdict(item) for item in obj]
        else:
            return obj

    try:
        # Convert all dict values in variables to DotDict
        namespace = {}
        for key, value in variables.items():
            if key.startswith("$"):
                # Remove the $ prefix for the namespace
                clean_key = key[1:]
                namespace[clean_key] = convert_to_dotdict(value)

        # Also add the variables with $ prefix for direct access
        for key, value in variables.items():
            if key.startswith("$"):
                namespace[key] = convert_to_dotdict(value)

        # Parse and evaluate the expression
        # First, replace $var with var in the expression (only at word boundaries)
        clean_expr = re.sub(r"\$(\w+)(?=\W|$)", r"\1", expression)

        # Check if the base variable exists
        # Extract the base variable name
        match = re.match(r"(\w+)", clean_expr)
        if match:
            base_var = match.group(1)
            if base_var not in namespace and "$" + base_var not in namespace:
                raise KeyError(f"Variable ${base_var} not found")

        # Evaluate the expression with restricted builtins
        result = eval(clean_expr, {"__builtins__": {}}, namespace)
        return result

    except (KeyError, AttributeError, IndexError):
        # Re-raise these specific exceptions
        raise
    except Exception:
        # For any other exception during parsing/evaluation,
        # return the original expression
        return expression

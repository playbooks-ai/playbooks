"""
Unified expression processing for all contexts.
Zero dependencies on other expression modules.
"""

import ast
import inspect
import json
import re
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from ..llm_messages.types import ArtifactLLMMessage
from ..variables import Artifact

if TYPE_CHECKING:
    from ..agents.base_agent import Agent
    from ..execution_state import ExecutionState
    from ..playbook_call import PlaybookCall

# ============================================================================
# Core Processing Functions (Pure, Stateless)
# ============================================================================


@lru_cache(maxsize=512)
def preprocess_expression(expr: str) -> str:
    """Convert $variable syntax to valid Python.

    Single-pass transformation that preserves:
    - String literals: 'cost: $5.99'
    - Invalid identifiers: '$123', '$$'
    - Complex expressions: $obj.attr, $dict['key']

    Args:
        expr: Expression to preprocess

    Returns:
        Preprocessed expression with $variable → variable

    Examples:
        >>> preprocess_expression("$order['id']")
        "order['id']"
        >>> preprocess_expression("$user.name")
        "user.name"
        >>> preprocess_expression("'cost: $5.99'")  # String literal preserved
        "'cost: $5.99'"
    """
    if not isinstance(expr, str):
        return str(expr)

    # Pattern matches $ followed by valid Python identifier
    # Uses word boundaries to avoid matching inside strings
    pattern = r"\$([a-zA-Z_][a-zA-Z0-9_]*)"

    def replace_dollar(match):
        var_name = match.group(1)
        return var_name

    return re.sub(pattern, replace_dollar, expr)


@lru_cache(maxsize=512)
def parse_to_ast(expr: str) -> Tuple[Optional[ast.AST], Optional[str]]:
    """Parse preprocessed expression to AST with error context.

    Args:
        expr: Preprocessed expression to parse

    Returns:
        Tuple of (AST node, error message). One will be None.

    Examples:
        >>> ast_node, error = parse_to_ast("user.name")
        >>> ast_node is not None
        True
        >>> error is None
        True
    """
    try:
        return ast.parse(expr, mode="eval"), None
    except SyntaxError as e:
        error_msg = f"Syntax error in expression '{expr}': {e}"
        if hasattr(e, "lineno") and hasattr(e, "offset"):
            error_msg += f" at line {e.lineno}, column {e.offset}"
        return None, error_msg
    except Exception as e:
        return None, f"Parse error in expression '{expr}': {type(e).__name__}: {e}"


def extract_variables(expr: str) -> Set[str]:
    """Extract all $variable references from expression.

    Args:
        expr: Expression to analyze

    Returns:
        Set of variable names (without $ prefix)

    Examples:
        >>> extract_variables("$user.name + $order['id']")
        {'user', 'order'}
    """
    if not isinstance(expr, str):
        return set()

    pattern = r"\$([a-zA-Z_][a-zA-Z0-9_]*)"
    matches = re.findall(pattern, expr)
    return set(matches)


def validate_expression(expr: str) -> Tuple[bool, Optional[str]]:
    """Validate expression syntax without full parsing.

    Args:
        expr: Expression to validate

    Returns:
        Tuple of (is_valid, error_message)

    Examples:
        >>> is_valid, error = validate_expression("$user.name")
        >>> is_valid
        True
    """
    if not isinstance(expr, str):
        return False, "Expression must be a string"

    # Preprocess and attempt to parse
    preprocessed = preprocess_expression(expr)
    ast_node, error = parse_to_ast(preprocessed)

    if ast_node is None:
        return False, error

    # Security validation - check for dangerous operations
    dangerous_patterns = [
        "subprocess",
        "eval",
        "exec",
        "__import__",
        "open",
        "__builtins__",
        "__globals__",
        "__locals__",
    ]

    for pattern in dangerous_patterns:
        if pattern in preprocessed.lower():
            return False, f"Security violation: '{pattern}' not allowed in expressions"

    return True, None


# ============================================================================
# Context Resolution (Stateful, Per-Execution)
# ============================================================================


class ExpressionContext:
    """Minimal context for variable and function resolution."""

    def __init__(self, agent: "Agent", state: "ExecutionState", call: "PlaybookCall"):
        """Initialize expression context.

        Args:
            agent: Agent instance for namespace resolution
            state: Execution state for variable lookup
            call: Current playbook call for context
        """
        self.agent = agent
        self.state = state
        self.call = call
        self._cache: Dict[str, Any] = {}
        self._resolving: Set[str] = set()  # Circular reference detection

        # Pre-populate built-in context
        self._cache.update({"agent": agent, "call": call, "timestamp": datetime.now()})

    def resolve_variable(self, name: str) -> Any:
        """Resolve single variable with caching.

        Resolution order:
        1. Built-in context (agent, call, timestamp)
        2. State variables (state.variables["$" + name])
        3. Namespace manager (agent.namespace_manager.namespace[name])
        4. KeyError with suggestions

        Args:
            name: Variable name (without $ prefix)

        Returns:
            Resolved variable value

        Raises:
            KeyError: If variable not found
            RecursionError: If circular reference detected
        """
        # Circular reference detection
        if name in self._resolving:
            raise RecursionError(f"Circular reference detected: ${name}")

        # Check cache first
        if name in self._cache:
            return self._cache[name]

        self._resolving.add(name)
        try:
            # Try state variables (with or without $)
            var_key = f"${name}" if not name.startswith("$") else name
            if hasattr(self.state, "variables") and hasattr(
                self.state.variables, "variables"
            ):
                if var_key in self.state.variables.variables:
                    variable = self.state.variables.variables[var_key]
                    # If the variable itself is an Artifact, return it directly
                    # Otherwise, return its value
                    if isinstance(variable, Artifact):
                        value = variable
                        # Auto-load artifact if not already loaded in any frame
                        if hasattr(
                            self.state, "call_stack"
                        ) and not self.state.call_stack.is_artifact_loaded(var_key):

                            artifact_msg = ArtifactLLMMessage(variable)
                            self.state.call_stack.add_llm_message(artifact_msg)
                    else:
                        value = variable.value
                    self._cache[name] = value
                    return value

            # Try namespace manager
            if (
                hasattr(self.agent, "namespace_manager")
                and hasattr(self.agent.namespace_manager, "namespace")
                and name in self.agent.namespace_manager.namespace
            ):
                value = self.agent.namespace_manager.namespace[name]
                self._cache[name] = value
                return value

            # Variable not found - generate suggestions
            available_vars = self._get_available_variables()
            suggestions = self._get_variable_suggestions(name, available_vars)

            error_msg = f"Variable '{name}' not found"
            if suggestions:
                error_msg += f". Did you mean: {', '.join(suggestions)}?"

            raise KeyError(error_msg)

        finally:
            self._resolving.discard(name)

    def _get_available_variables(self) -> List[str]:
        """Get list of available variable names for suggestions."""
        variables = []

        # Built-in variables
        variables.extend(["agent", "call", "timestamp"])

        # State variables
        if hasattr(self.state, "variables") and hasattr(
            self.state.variables, "variables"
        ):
            for key in self.state.variables.variables.keys():
                if key.startswith("$"):
                    variables.append(key[1:])  # Remove $ prefix

        # Namespace variables
        if hasattr(self.agent, "namespace_manager") and hasattr(
            self.agent.namespace_manager, "namespace"
        ):
            variables.extend(self.agent.namespace_manager.namespace.keys())

        return variables

    def _get_variable_suggestions(
        self, name: str, available_vars: List[str]
    ) -> List[str]:
        """Get variable name suggestions using simple similarity."""
        if not available_vars:
            return []

        # Simple similarity: starts with same letter or contains substring
        suggestions = []
        name_lower = name.lower()

        for var in available_vars:
            var_lower = var.lower()
            if (
                var_lower.startswith(name_lower[0])
                or name_lower in var_lower
                or var_lower in name_lower
            ):
                suggestions.append(var)

        return suggestions[:3]  # Limit to 3 suggestions

    def evaluate_expression(self, expr: str) -> Any:
        """Evaluate expression in this context.

        Pipeline: preprocess → parse → eval(ast, {}, self)

        Args:
            expr: Expression to evaluate

        Returns:
            Evaluated result

        Raises:
            ExpressionError: If evaluation fails
        """
        try:
            # Validate expression first
            is_valid, error = validate_expression(expr)
            if not is_valid:
                raise ExpressionError(expr, error)

            # Preprocess $variable syntax
            preprocessed = preprocess_expression(expr)

            # Parse to AST
            ast_node, parse_error = parse_to_ast(preprocessed)
            if ast_node is None:
                raise ExpressionError(expr, parse_error)

            # Create evaluation namespace
            namespace = self._create_namespace()

            # Evaluate with safe builtins
            safe_builtins = {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "max": max,
                "min": min,
                "sum": sum,
                "abs": abs,
                "round": round,
            }

            # Merge namespace into globals with safe builtins
            # This is needed so that imported modules (like date) work correctly
            eval_globals = {"__builtins__": safe_builtins}
            eval_globals.update(namespace)

            result = eval(
                compile(ast_node, "<expression>", "eval"),
                eval_globals,
                {},  # Empty locals, everything is in globals
            )

            # Handle coroutines by awaiting them if possible, otherwise return the coroutine
            if inspect.iscoroutine(result):
                # For now, just return the coroutine - caller needs to handle it
                # This is safer than trying to run it synchronously
                return result

            return result

        except ExpressionError:
            raise
        except Exception as e:
            # Format as simple error without redundant "Expression error" prefix
            raise ExpressionError(expr, f"{type(e).__name__}: {e}") from None

    def _create_namespace(self) -> Dict[str, Any]:
        """Create namespace for expression evaluation."""
        namespace = {}

        # Start with agent's namespace manager (includes imports and functions)
        if hasattr(self.agent, "namespace_manager") and hasattr(
            self.agent.namespace_manager, "namespace"
        ):
            namespace.update(self.agent.namespace_manager.namespace)

        # Add all resolvable variables (may override namespace items)
        available_vars = self._get_available_variables()
        for var_name in available_vars:
            try:
                namespace[var_name] = self.resolve_variable(var_name)
            except (KeyError, RecursionError):
                # Skip variables that can't be resolved
                continue

        return namespace

    def __getitem__(self, key: str) -> Any:
        """Dict-like access for eval() namespace compatibility."""
        return self.resolve_variable(key)


# ============================================================================
# Specialized Parsers (Built on Core Functions)
# ============================================================================


def parse_playbook_call(
    call_str: str,
    context: Optional[ExpressionContext] = None,
    variable_to_assign: str = None,
    type_annotation: str = None,
) -> "PlaybookCall":
    """Parse playbook call with optional argument resolution.

    Args:
        call_str: Playbook call string (e.g., "MyPlaybook($arg1, kwarg=$arg2)")
        context: Optional context for variable resolution
        variable_to_assign: Optional variable name to assign result to (e.g., "$result")
        type_annotation: Optional type annotation for the variable (e.g., "bool")

    Returns:
        PlaybookCall object with parsed arguments

    Raises:
        ExpressionError: If parsing fails

    Examples:
        >>> call = parse_playbook_call("GetOrder($order_id)")
        >>> call.playbook_name
        'GetOrder'
        >>> call.args
        ['$order_id']
    """
    from ..playbook_call import PlaybookCall

    try:
        # Preprocess the call string
        preprocessed = preprocess_expression(call_str)

        # Parse to AST
        ast_node, error = parse_to_ast(preprocessed)
        if ast_node is None:
            raise ExpressionError(call_str, f"Failed to parse playbook call: {error}")

        # Verify it's a function call
        if not isinstance(ast_node.body, ast.Call):
            raise ExpressionError(call_str, "Expected a function call")

        call_node = ast_node.body

        # Extract playbook name
        playbook_name = _extract_playbook_name(call_node)

        # Extract arguments
        args = []
        for arg in call_node.args:
            arg_value = _node_to_value(arg, call_str, context)
            args.append(arg_value)

        # Extract keyword arguments
        kwargs = {}
        for keyword in call_node.keywords:
            kwarg_value = _node_to_value(keyword.value, call_str, context)
            kwargs[keyword.arg] = kwarg_value

        return PlaybookCall(
            playbook_name, args, kwargs, variable_to_assign, type_annotation
        )

    except ExpressionError:
        raise
    except Exception as e:
        raise ExpressionError(
            call_str, f"Failed to parse playbook call: {type(e).__name__}: {e}"
        )


def extract_playbook_calls(text: str) -> List[str]:
    """Extract call strings from text using regex patterns.

    Args:
        text: Text to search for playbook calls

    Returns:
        List of playbook call strings

    Examples:
        >>> calls = extract_playbook_calls("`GetOrder($order_id)`")
        >>> calls
        ['GetOrder($order_id)']
    """
    # Pattern matches backtick-wrapped calls, optionally with assignment
    # re.DOTALL allows matching multi-line strings with triple quotes
    pattern = r"`(?:.*\W*=\W*)?([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*\(.*?\))`"
    matches = re.findall(pattern, text, re.DOTALL)
    return matches


async def resolve_description_placeholders(
    description: str, context: ExpressionContext
) -> str:
    """Resolve {expression} patterns in descriptions.

    Args:
        description: Description text with {expression} placeholders
        context: Expression context for variable resolution

    Returns:
        Description with placeholders resolved to string values

    Examples:
        >>> resolved = resolve_description_placeholders("Order {$order_id} status", context)
        >>> # Returns "Order 12345 status" if $order_id = 12345
    """
    if not isinstance(description, str) or "{" not in description:
        return description

    # Pattern to handle nested braces
    pattern = r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"

    # Find all matches and replace them manually since re.sub doesn't work with async
    matches = list(re.finditer(pattern, description))
    if not matches:
        return description

    # Process matches in reverse order to avoid index shifting
    result_desc = description
    for match in reversed(matches):
        expr = match.group(1)
        try:
            # Evaluate expression
            result = context.evaluate_expression(expr)
            # If result is a coroutine, await it
            if inspect.iscoroutine(result):
                result = await result
            replacement = format_value(result)
            # Replace the match in the string
            result_desc = (
                result_desc[: match.start()] + replacement + result_desc[match.end() :]
            )
        except Exception as e:
            # Extract the root error message, avoiding nested ExpressionError wrapping
            if isinstance(e, ExpressionError):
                # Just re-raise as-is to avoid double-wrapping
                raise
            else:
                error_detail = f"{type(e).__name__}: {e}"

            # Calculate position for error context
            pos = match.start()
            line_num = description[:pos].count("\n") + 1
            col_num = pos - description.rfind("\n", 0, pos)

            raise ExpressionError(
                expr,
                f"{error_detail} (at line {line_num}, column {col_num})",
            ) from None

    return result_desc


def update_description_in_markdown(markdown: str, resolved_description: str) -> str:
    """Replace the description portion in playbook markdown.

    Args:
        markdown: Original markdown content
        resolved_description: Resolved description to replace with

    Returns:
        Updated markdown with replaced description
    """
    lines = markdown.split("\n")
    new_lines = []
    in_description = False
    description_added = False

    for line in lines:
        if line.startswith("## "):
            new_lines.append(line)
            in_description = True
        elif line.startswith("### "):
            # End of description section
            if in_description and not description_added:
                if resolved_description.strip():
                    new_lines.append(resolved_description)
                description_added = True
            in_description = False
            new_lines.append(line)
        elif not in_description:
            new_lines.append(line)
        # Skip original description lines when in_description=True

    # If we never hit a ### section, add description at the end
    if in_description and not description_added and resolved_description.strip():
        new_lines.append(resolved_description)

    return "\n".join(new_lines)


def format_value(value: Any) -> str:
    """Format values for string conversion with smart JSON handling.

    Args:
        value: Value to format

    Returns:
        String representation of value

    Examples:
        >>> format_value({"key": "value"})
        '{"key": "value"}'
        >>> format_value(None)
        ''
    """
    # Handle Artifact objects by using their content

    if isinstance(value, Artifact):
        return str(value.value)
    elif value is None:
        return ""
    elif isinstance(value, (list, dict)):
        json_str = json.dumps(value, default=str, ensure_ascii=False)
        if len(json_str) > 100:
            return f"\n{json.dumps(value, indent=2, default=str, ensure_ascii=False)}\n"
        return json_str
    else:
        return str(value)


# ============================================================================
# Helper Functions
# ============================================================================


def _extract_playbook_name(call_node: ast.Call) -> str:
    """Extract playbook name from AST call node."""
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    elif isinstance(call_node.func, ast.Attribute):
        # Handle module.PlaybookName calls
        parts = []
        node = call_node.func
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))
    else:
        raise ValueError(
            f"Unsupported playbook call format: {ast.unparse(call_node.func)}"
        )


def _node_to_value(
    node: ast.AST, original_expr: str, context: Optional[ExpressionContext]
) -> Any:
    """Convert AST node to typed value (LiteralValue or VariableReference)."""
    from playbooks.argument_types import LiteralValue, VariableReference

    if isinstance(node, ast.Constant):
        # Literal value
        return LiteralValue(node.value)
    elif isinstance(node, ast.Name):
        # Check if it's a known literal (true, false, null, None)
        # These should not be treated as variables
        literal_map = {
            "true": True,
            "false": False,
            "null": None,
            "None": None,
        }
        if node.id in literal_map:
            return LiteralValue(literal_map[node.id])
        # Variable reference - return with $ prefix for later resolution
        return VariableReference(f"${node.id}")
    elif isinstance(node, ast.Attribute):
        # Attribute access like $user.name
        expr_str = _build_attribute_expr(node)
        return VariableReference(expr_str)
    elif isinstance(node, ast.Subscript):
        # Subscript access like $user['name'] or $items[0]
        expr_str = _build_subscript_expr(node)
        return VariableReference(expr_str)
    elif isinstance(node, ast.Call):
        # Function call like len($items) - return as expression with $ restoration
        expr_str = ast.unparse(node)
        # Restore $ prefix for variables in the expression, but not function names
        expr_str = _restore_variable_prefixes(expr_str, node)
        return VariableReference(expr_str)
    else:
        # Try to evaluate as literal
        try:
            literal_value = ast.literal_eval(node)
            return LiteralValue(literal_value)
        except (ValueError, TypeError):
            # If not a literal, return as variable reference (expression)
            expr_str = ast.unparse(node)
            return VariableReference(expr_str)


def _build_attribute_expr(node: ast.Attribute) -> str:
    """Build attribute expression string like $user.name."""

    def build_parts(n):
        if isinstance(n, ast.Name):
            return f"${n.id}"
        elif isinstance(n, ast.Attribute):
            return f"{build_parts(n.value)}.{n.attr}"
        else:
            return ast.unparse(n)

    return build_parts(node)


def _restore_variable_prefixes(expr_str: str, call_node: ast.Call) -> str:
    """Restore $ prefixes for variables in function call expressions."""
    # This is a simple approach - collect all Name nodes that are variables
    var_names = set()

    def collect_var_names(node):
        if isinstance(node, ast.Name):
            var_names.add(node.id)
        elif hasattr(node, "_fields"):
            for field_name in node._fields:
                field_value = getattr(node, field_name, None)
                if isinstance(field_value, list):
                    for item in field_value:
                        if isinstance(item, ast.AST):
                            collect_var_names(item)
                elif isinstance(field_value, ast.AST):
                    collect_var_names(field_value)

    # Collect variable names from arguments only (not function name)
    for arg in call_node.args:
        collect_var_names(arg)

    # Restore $ prefixes for collected variable names
    for var_name in var_names:
        # Use word boundaries to avoid partial matches
        expr_str = re.sub(rf"\b{re.escape(var_name)}\b", f"${var_name}", expr_str)

    return expr_str


def _build_subscript_expr(node: ast.Subscript) -> str:
    """Build subscript expression string like $user['name'] or $items[0]."""
    if isinstance(node.value, ast.Attribute):
        value_expr = _build_attribute_expr(node.value)
    elif isinstance(node.value, ast.Name):
        value_expr = f"${node.value.id}"
    else:
        value_expr = ast.unparse(node.value)

    if isinstance(node.slice, ast.Constant):
        if isinstance(node.slice.value, str):
            return f'{value_expr}["{node.slice.value}"]'
        else:
            return f"{value_expr}[{node.slice.value}]"
    else:
        slice_str = ast.unparse(node.slice)
        return f"{value_expr}[{slice_str}]"


# ============================================================================
# Error Handling (Centralized)
# ============================================================================


class ExpressionError(Exception):
    """Unified exception for all expression errors."""

    def __init__(
        self,
        expr: str,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
    ):
        """Initialize expression error.

        Args:
            expr: Expression that caused the error
            message: Error message
            line: Optional line number
            column: Optional column number
        """
        self.expr = expr
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context."""
        # Don't include "Expression error in" if message already has it
        if self.message.startswith("Expression error in"):
            return self.message

        msg = f"Error evaluating '{self.expr}': {self.message}"
        if self.line is not None:
            msg += f" at line {self.line}"
            if self.column is not None:
                msg += f", column {self.column}"
        return msg


# ============================================================================
# Program Preprocessing (For Python Execution)
# ============================================================================


def preprocess_program(code: str) -> str:
    """Convert $variable syntax to valid Python in LLM-generated code.

    This function preprocesses Python code generated by LLMs to convert
    the $variable syntax to standard Python identifiers.

    Handles:
    - Simple variables: $var → var
    - Expressions: $obj.attr → obj.attr, $dict['key'] → dict['key']
    - F-strings: f"{$var}" → f"{var}"
    - Function calls: Say("user", $message) → Say("user", message)
    - Preserves string literals: "cost: $5.99" → "cost: $5.99"

    Args:
        code: Python code potentially containing $variable references

    Returns:
        Preprocessed code with $variable → variable conversion

    Examples:
        >>> preprocess_program('Say("user", $message)')
        'Say("user", message)'
        >>> preprocess_program('$count = $existing_count + 1')
        '$count = existing_count + 1'
        >>> preprocess_program('x = "cost: $5.99"')  # String literal preserved
        'x = "cost: $5.99"'
    """
    if not isinstance(code, str):
        return str(code)

    # Use the existing preprocess_expression on the entire code
    # This is safe because preprocess_expression preserves string literals
    return preprocess_expression(code)

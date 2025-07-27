"""Description placeholder resolution for LLM playbooks.

This module provides functionality to resolve {expression} placeholders in playbook descriptions
using Python f-string evaluation with lazy context resolution and automatic async function wrapping.
"""

import ast
import asyncio
import inspect
import json
import logging
import re
import signal
import threading
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from typing import Any, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.base_agent import Agent
    from ..execution_state import ExecutionState
    from ..playbook_call import PlaybookCall

logger = logging.getLogger(__name__)


@contextmanager
def timeout(duration: int):
    """Context manager for timing out operations."""

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Expression evaluation timed out after {duration} seconds")

    # Store the old handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(duration)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class LazyContextDict(dict):
    """Dict-like object that provides sync wrappers for async functions and lazy variable resolution."""

    def __init__(self, agent: "Agent", state: "ExecutionState", call: "PlaybookCall"):
        super().__init__()
        self.agent = agent
        self.state = state
        self.call = call
        self._resolving = set()  # Circular reference detection

        # Pre-populate special variables
        self["agent"] = agent
        self["call"] = call
        self["timestamp"] = datetime.now()

    def __getitem__(self, key: str) -> Any:
        """Get item with lazy resolution and async function wrapping."""
        # Circular reference detection
        if key in self._resolving:
            raise RecursionError(f"Circular reference detected: {key}")

        if key in self:
            value = super().__getitem__(key)
            return self._wrap_if_async(value)

        self._resolving.add(key)
        try:
            # Try state variables (with or without $)
            var_key = f"${key}" if not key.startswith("$") else key
            if var_key in self.state.variables.variables:
                value = self.state.variables.variables[var_key].value
                self[key] = value
                return value

            # Try namespace manager
            if (
                hasattr(self.agent, "namespace_manager")
                and key in self.agent.namespace_manager.namespace
            ):
                value = self.agent.namespace_manager.namespace[key]
                value = self._wrap_if_async(value)
                self[key] = value
                return value

            raise KeyError(f"Variable '{key}' not found")
        finally:
            self._resolving.discard(key)

    def _wrap_if_async(self, value: Any) -> Any:
        """Wrap async functions with sync wrapper."""
        if inspect.iscoroutinefunction(value):
            return self._make_sync_wrapper(value)
        return value

    def _make_sync_wrapper(self, async_func):
        """Create a sync wrapper for async functions with deadlock protection."""

        def sync_wrapper(*args, **kwargs):
            try:
                loop = asyncio.get_running_loop()
                # Check if we're in the loop's thread to avoid deadlock
                if (
                    hasattr(loop, "_thread")
                    and threading.current_thread() == loop._thread
                ):
                    raise RuntimeError(
                        f"Cannot call async function '{async_func.__name__}' from same event loop thread. "
                        "This would cause a deadlock. Consider using a sync alternative."
                    )
                else:
                    # Different thread - safe to use run_coroutine_threadsafe
                    future = asyncio.run_coroutine_threadsafe(
                        async_func(*args, **kwargs), loop
                    )
                    return future.result()
            except RuntimeError:
                # No running loop, create one
                return asyncio.run(async_func(*args, **kwargs))

        sync_wrapper.__name__ = f"sync_{async_func.__name__}"
        sync_wrapper.__doc__ = async_func.__doc__
        return sync_wrapper


@lru_cache(maxsize=128)
def parse_expression(expr: str) -> Tuple[Any, str]:
    """Parse and cache AST for expressions."""
    try:
        return ast.parse(expr, mode="eval"), None
    except SyntaxError as e:
        return None, str(e)


def extract_and_validate_expressions(description: str) -> Tuple[List[str], List[str]]:
    """Extract {expression} patterns and validate Python syntax."""
    # Skip if no placeholders
    if "{" not in description:
        return [], []

    # Regex to handle nested braces
    pattern = r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"
    expressions = re.findall(pattern, description)

    valid = []
    invalid = []

    for expr in expressions:
        ast_tree, error = parse_expression(expr)
        if ast_tree:
            valid.append(expr)
        else:
            invalid.append(expr)

    return valid, invalid


def preprocess_dollar_variables(expr: str) -> str:
    """Preprocess expression to convert $variable syntax to valid Python.

    Examples:
        $order['id'] -> order['id']
        $order.customer -> order.customer
        func($param) -> func(param)
        $var + $other -> var + other
    """
    # Use regex to find $variable patterns and replace them
    # Pattern matches $ followed by identifier, then stops at non-alphanumeric/underscore
    pattern = r"\$([a-zA-Z_][a-zA-Z0-9_]*)"

    def replace_dollar(match):
        var_name = match.group(1)
        return var_name

    return re.sub(pattern, replace_dollar, expr)


def format_value(value: Any) -> str:
    """Format values for string conversion with smart JSON handling."""
    if value is None:
        return ""
    elif isinstance(value, (list, dict)):
        json_str = json.dumps(value, default=str, ensure_ascii=False)
        if len(json_str) > 100:
            return f"\n{json.dumps(value, indent=2, default=str, ensure_ascii=False)}\n"
        return json_str
    else:
        return str(value)


def evaluate_with_context(description: str, context: LazyContextDict) -> str:
    """Evaluate description with individual expression error handling."""
    pattern = r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"

    def replace_expr(match):
        expr = match.group(1)
        try:
            # Preprocess expression to handle $variable syntax
            processed_expr = preprocess_dollar_variables(expr)
            result = eval(processed_expr, {"__builtins__": __builtins__}, context)
            return format_value(result)
        except Exception as e:
            pos = match.start()
            line_num = description[:pos].count("\n") + 1
            col_num = pos - description.rfind("\n", 0, pos)
            raise ValueError(
                f"Error in expression '{expr}' at line {line_num}, column {col_num}: {type(e).__name__}: {e}"
            )

    return re.sub(pattern, replace_expr, description)


async def resolve_description(
    description: str, agent: "Agent", state: "ExecutionState", call: "PlaybookCall"
) -> str:
    """Main resolution function with logging and natural language fallback."""
    logger.info(
        f"Resolving placeholders for {call.playbook_klass}: {description[:50]}..."
    )

    # Security logging for potentially dangerous expressions
    if any(
        dangerous in description
        for dangerous in ["subprocess", "eval", "exec", "__import__", "open(", "file("]
    ):
        logger.warning(
            f"Potentially dangerous expression in {call.playbook_klass}: {description}"
        )

    if "{" not in description:
        return description  # No placeholders

    # Extract and validate expressions
    valid_exprs, invalid_exprs = extract_and_validate_expressions(description)

    # Handle natural language expressions if needed
    if invalid_exprs:
        logger.info(
            f"Found natural language expressions, resolving via LLM: {invalid_exprs}"
        )

        # Call built-in ResolveDescriptionPlaceholders playbook
        try:
            resolved = await agent.execute_playbook(
                "ResolveDescriptionPlaceholders", [str(call), description]
            )
        except Exception as e:
            logger.error(f"Failed to resolve natural language expressions via LLM: {e}")
            # Fallback to original description
            resolved = description

        # Re-validate after LLM resolution
        valid_exprs, invalid_exprs = extract_and_validate_expressions(resolved)

        if invalid_exprs:
            raise ValueError(
                f"Failed to resolve expressions after LLM processing: {invalid_exprs}"
            )

        description = resolved

    # Create context and evaluate with timeout protection
    context = LazyContextDict(agent, state, call)

    try:
        with timeout(30):  # 30 second timeout
            return evaluate_with_context(description, context)
    except TimeoutError as e:
        logger.error(f"Description resolution timed out for {call.playbook_klass}: {e}")
        raise ValueError(f"Description resolution timed out: {e}")
    except Exception as e:
        logger.error(f"Failed to resolve description for {call.playbook_klass}: {e}")
        raise


def update_description_in_markdown(markdown: str, resolved_description: str) -> str:
    """Replace the description portion in playbook markdown."""
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

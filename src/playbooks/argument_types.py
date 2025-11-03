"""Typed argument wrappers for preserving variable references vs literals."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ArgumentValue:
    """Base class for typed argument values.

    Used to distinguish between literal values and variable references
    in playbook argument handling.
    """


@dataclass
class LiteralValue(ArgumentValue):
    """A literal value (string, number, bool, etc).

    These values have already been resolved and should be used as-is.
    Examples:
        - LiteralValue("hello") - a string literal
        - LiteralValue(42) - a number literal
        - LiteralValue(True) - a boolean literal
    """

    value: Any


@dataclass
class VariableReference(ArgumentValue):
    """A variable reference ($varname) - resolved at execution time.

    These are references to variables that should be resolved based on
    the playbook type (external/Python/LLM).
    Examples:
        - VariableReference("$order_id") - simple variable
        - VariableReference("$user.name") - attribute access
        - VariableReference("$items[0]") - subscript access
        - VariableReference("len($items)") - expression
    """

    reference: str  # e.g., "$order_id" or "$user.name"

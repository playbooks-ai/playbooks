"""Miscellaneous utility functions.

This module contains various utility functions used throughout the playbooks
framework for common operations like function copying and code manipulation.
"""

import functools
import types
from typing import Any, Dict, Optional


def copy_func(
    f: types.FunctionType, globals: Optional[Dict[str, Any]] = None
) -> types.FunctionType:
    """Create a copy of a function with optional globals override.

    Based on http://stackoverflow.com/a/6528148/190597 (Glenn Maynard)

    Args:
        f: The function to copy
        globals: Optional globals dictionary to use in the copy

    Returns:
        A new function object that is a copy of the original
    """
    g = types.FunctionType(
        f.__code__,
        globals or f.__globals__,
        name=f.__name__,
        argdefs=f.__defaults__,
        closure=f.__closure__,
    )
    g = functools.update_wrapper(g, f)
    g.__kwdefaults__ = f.__kwdefaults__
    return g

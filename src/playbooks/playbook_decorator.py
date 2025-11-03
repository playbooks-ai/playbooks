"""Playbook decorator for marking functions as executable playbooks.

This module provides the @playbook decorator that marks Python functions
as playbooks, enabling them to be discovered and executed by the playbook
runtime system.
"""

from typing import Any, Callable, List, Optional, Union


def playbook_decorator(
    func_or_triggers: Optional[Union[Callable, List[str]]] = None,
    **kwargs,
) -> Union[Callable, Any]:
    """
    A decorator that marks a function as a playbook. It sets the ``__is_playbook__``
    flag to ``True`` and populates ``__triggers__`` and ``__metadata__`` attributes
    based on the provided arguments. No wrapper function is created; the original
    function is returned unchanged after validation.

    Both synchronous and asynchronous functions are supported. The PythonPlaybook
    execution layer will handle the appropriate calling convention.

    Args:
        func_or_triggers: Either the function to decorate or a list of trigger strings
        triggers: A list of trigger strings when used in the form @playbook(triggers=[...])
        **kwargs: Additional metadata options to store in __metadata__

    Returns:
        The decorated function with __is_playbook__ attribute set to True

    Raises:
        TypeError: If the decorated object is not a callable function
    """
    # Case 1: @playbook used directly (no arguments)
    if callable(func_or_triggers):
        func = func_or_triggers
        # Validate function signature
        if not callable(func):
            raise TypeError("Playbook decorator can only be applied to functions")

        # Store playbook metadata on the function
        func.__is_playbook__ = True
        func.__triggers__ = []
        func.__metadata__ = {}
        return func

    # Case 2: @playbook(triggers=[...]) or @playbook([...]) or @playbook(public=True, etc.)
    else:
        # If triggers is None, assume func_or_triggers is the triggers list
        def decorator(func: Callable) -> Callable:
            # Validate function signature
            if not callable(func):
                raise TypeError("Playbook decorator can only be applied to functions")

            # Store playbook metadata on the function
            func.__is_playbook__ = True
            func.__triggers__ = kwargs.get("triggers", [])

            # Store all kwargs except 'triggers' as metadata
            func.__metadata__ = {k: v for k, v in kwargs.items() if k != "triggers"}

            return func

        return decorator

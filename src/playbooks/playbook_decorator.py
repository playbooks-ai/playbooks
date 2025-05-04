import inspect
from typing import Any, Callable, List, Optional, Union


def playbook_decorator(
    func_or_triggers: Optional[Union[Callable, List[str]]] = None,
    **kwargs,
) -> Union[Callable, Any]:
    """
    A decorator that marks a function as a playbook by setting __is_playbook__ to True.
    Can be used with or without arguments. Wraps the function in an async wrapper.

    Args:
        func_or_triggers: Either the function to decorate or a list of trigger strings
        triggers: A list of trigger strings when used in the form @playbook(triggers=[...])

    Returns:
        The decorated function with __is_playbook__ attribute set to True

    Raises:
        TypeError: If the decorated function is not async
    """
    # Case 1: @playbook used directly (no arguments)
    if callable(func_or_triggers):
        func = func_or_triggers
        if not inspect.iscoroutinefunction(func):
            raise TypeError(f"Playbook function '{func.__name__}' must be async")
        func.__is_playbook__ = True
        func.__triggers__ = []
        func.__export__ = False
        return func

    # Case 2: @playbook(triggers=[...]) or @playbook([...]) or @playbook(export=True)
    else:
        # If triggers is None, assume func_or_triggers is the triggers list
        def decorator(func: Callable) -> Callable:
            if not inspect.iscoroutinefunction(func):
                raise TypeError(f"Playbook function '{func.__name__}' must be async")
            func.__is_playbook__ = True
            func.__triggers__ = kwargs.get("triggers", [])
            func.__export__ = kwargs.get("export", False)
            return func

    return decorator

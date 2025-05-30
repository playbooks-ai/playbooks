import inspect
from typing import Any, Callable, List, Optional, Union


def playbook_decorator(
    func_or_triggers: Optional[Union[Callable, List[str]]] = None,
    **kwargs,
) -> Union[Callable, Any]:
    """
    A decorator that marks a coroutine as a playbook. It sets the ``__is_playbook__``
    flag to ``True`` and populates ``__triggers__`` and ``__public__`` attributes
    based on the provided arguments. No wrapper function is created; the original
    coroutine is returned unchanged after validation.

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
        func.__public__ = False
        return func

    # Case 2: @playbook(triggers=[...]) or @playbook([...]) or @playbook(public=True)
    else:
        # If triggers is None, assume func_or_triggers is the triggers list
        def decorator(func: Callable) -> Callable:
            if not inspect.iscoroutinefunction(func):
                raise TypeError(f"Playbook function '{func.__name__}' must be async")
            func.__is_playbook__ = True
            func.__triggers__ = kwargs.get("triggers", [])
            func.__public__ = kwargs.get("public", False)
            return func

        return decorator

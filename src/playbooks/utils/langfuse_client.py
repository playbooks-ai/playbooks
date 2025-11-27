"""Shim around Langfuse's Langfuse client helpers that respect configuration."""

from __future__ import annotations

from functools import wraps

from langfuse import get_client as langfuse_get_client
from langfuse import observe as langfuse_observe

from playbooks.utils.langfuse_helper import LangfuseHelper, PlaybooksLangfuseInstance


def get_client():
    """Return Langfuse client or a no-op instance when telemetry is disabled."""

    helper_client = LangfuseHelper.instance()
    if isinstance(helper_client, PlaybooksLangfuseInstance):
        return helper_client
    return langfuse_get_client()


def observe(*decorator_args, **decorator_kwargs):
    """Langfuse @observe shim that becomes a no-op when telemetry is disabled."""

    helper_client = LangfuseHelper.instance()
    if isinstance(helper_client, PlaybooksLangfuseInstance):
        # Support both @observe and @observe(...)
        if (
            len(decorator_args) == 1
            and callable(decorator_args[0])
            and not decorator_kwargs
        ):
            func = decorator_args[0]

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    return langfuse_observe(*decorator_args, **decorator_kwargs)

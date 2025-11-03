"""Mixin for classes that require asynchronous initialization.

This mixin prevents direct instantiation of classes and requires using
an async create() class method for proper initialization.
"""

from typing import Any, TypeVar

T = TypeVar("T", bound="AsyncInitMixin")


class AsyncInitMixin:
    """Mixin that enforces asynchronous initialization pattern."""

    _ALLOW_INIT: bool = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize instance - should only be called through create()."""
        if not self.__class__._ALLOW_INIT:
            raise RuntimeError(
                f"{self.__class__.__name__} cannot be instantiated directly. "
                f"Use 'await {self.__class__.__name__}.create()' instead."
            )
        super().__init__(*args, **kwargs)

    @classmethod
    async def create(cls: type[T], *args: Any, **kwargs: Any) -> T:
        """Create and asynchronously initialize an instance.

        Args:
            *args: Positional arguments for __init__
            **kwargs: Keyword arguments for __init__

        Returns:
            Fully initialized instance
        """
        cls._ALLOW_INIT = True
        try:
            instance = cls(*args, **kwargs)
        finally:
            cls._ALLOW_INIT = False
        await instance._async_init()
        return instance

    async def _async_init(self) -> None:
        """Override this method in subclasses for async initialization."""
        pass

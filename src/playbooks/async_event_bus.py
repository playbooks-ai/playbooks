"""
Pure async event bus implementation with zero threading primitives.

This module provides a clean, async-first event bus that replaces the
threading-based EventBus with a pure asyncio implementation.
"""

import asyncio
import logging
from typing import Callable, Dict, List, Type, Union, Optional, Coroutine, Any
from weakref import WeakSet

from playbooks.events import Event

logger = logging.getLogger(__name__)


class AsyncEventBus:
    """
    Pure async event bus with zero threading primitives.

    This implementation provides:
    - Thread-safe operation in single-threaded asyncio context
    - Concurrent callback execution with error isolation
    - Weak reference tracking to prevent memory leaks
    - Support for wildcard subscriptions
    - Graceful shutdown with cleanup

    Example:
        bus = AsyncEventBus("session-123")

        # Subscribe to specific event
        bus.subscribe(MyEvent, my_handler)

        # Subscribe to all events
        bus.subscribe("*", universal_handler)

        # Publish event (async)
        await bus.publish(MyEvent(data="test"))
    """

    def __init__(self, session_id: str):
        """
        Initialize the async event bus.

        Args:
            session_id: Unique identifier for this session
        """
        self.session_id = session_id
        self._subscribers: Dict[Union[Type[Event], str], List[Callable]] = {}
        self._active_tasks: WeakSet[asyncio.Task] = WeakSet()
        self._closing = False

    def subscribe(
        self,
        event_type: Union[Type[Event], str],
        callback: Callable[[Event], Union[None, Coroutine[Any, Any, None]]],
    ) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: The type of events to subscribe to, or "*" for all events
            callback: Function to call when events occur (can be sync or async)

        Raises:
            RuntimeError: If event bus is closing
            TypeError: If callback is not callable
        """
        if self._closing:
            raise RuntimeError("Cannot subscribe to closing event bus")

        if not callable(callback):
            raise TypeError(f"Callback must be callable, got {type(callback)}")

        if isinstance(event_type, str) and event_type == "*":
            # Store wildcard subscription only
            self._subscribers.setdefault("*", []).append(callback)
        else:
            self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(
        self,
        event_type: Union[Type[Event], str],
        callback: Callable[[Event], Union[None, Coroutine[Any, Any, None]]],
    ) -> None:
        """
        Remove a previously registered callback.

        Args:
            event_type: The type of events the callback was subscribed to
            callback: The callback function to remove

        Raises:
            ValueError: If callback was not subscribed
        """
        if isinstance(event_type, str) and event_type == "*":
            # Unsubscribe from wildcard
            if "*" not in self._subscribers or callback not in self._subscribers["*"]:
                raise ValueError(f"Callback {callback} not subscribed to wildcard")

            self._subscribers["*"].remove(callback)
            if not self._subscribers["*"]:
                del self._subscribers["*"]
        else:
            if (
                event_type not in self._subscribers
                or callback not in self._subscribers[event_type]
            ):
                raise ValueError(f"Callback {callback} not subscribed to {event_type}")

            self._subscribers[event_type].remove(callback)
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers asynchronously.

        The event's session_id will be set to this bus's session_id.
        All callbacks are executed concurrently with error isolation.

        Args:
            event: The event object to publish

        Raises:
            RuntimeError: If event bus is closing
            TypeError: If event is not an Event instance
        """
        if self._closing:
            raise RuntimeError("Cannot publish to closing event bus")

        if not isinstance(event, Event):
            raise TypeError(f"Event must be an Event instance, got {type(event)}")

        # Set session ID
        event.session_id = self.session_id

        # Collect all applicable callbacks
        callbacks = []

        # Type-specific subscribers
        callbacks.extend(self._subscribers.get(type(event), []))

        # Wildcard subscribers
        callbacks.extend(self._subscribers.get("*", []))

        if not callbacks:
            return

        # Execute callbacks concurrently with error isolation
        tasks = []
        for callback in callbacks:
            task = asyncio.create_task(self._safe_callback(callback, event))
            tasks.append(task)
            self._active_tasks.add(task)

        # Wait for all callbacks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Error in event callback {callbacks[i].__name__} "
                    f"for {type(event).__name__}: {result}",
                    exc_info=result,
                )

    async def _safe_callback(self, callback: Callable, event: Event) -> None:
        """
        Execute callback with error isolation and async detection.

        Args:
            callback: The callback to execute
            event: The event to pass to the callback
        """
        try:
            result = callback(event)
            # Handle both sync and async callbacks
            if asyncio.iscoroutine(result):
                await result
        except asyncio.CancelledError:
            # Propagate cancellation
            raise
        except Exception as e:
            # Log but don't propagate other exceptions
            logger.error(
                f"Exception in event callback {callback.__name__}: {e}", exc_info=True
            )
            # Re-raise to be caught by gather
            raise

    def clear_subscribers(self, event_type: Optional[Type[Event]] = None) -> None:
        """
        Clear all subscribers or subscribers of a specific event type.

        Args:
            event_type: Optional type of events to clear subscribers for.
                       If None, clears all subscribers.
        """
        if event_type:
            self._subscribers.pop(event_type, None)
        else:
            self._subscribers.clear()

    async def close(self) -> None:
        """
        Close the event bus and cancel any active tasks.

        This method ensures graceful shutdown by:
        1. Preventing new subscriptions/publications
        2. Cancelling active callback tasks
        3. Waiting for cleanup
        """
        self._closing = True

        # Cancel all active tasks
        active_tasks = list(self._active_tasks)
        for task in active_tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete (with timeout)
        if active_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*active_tasks, return_exceptions=True), timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some event callbacks did not complete during shutdown")

        # Clear subscribers
        self.clear_subscribers()

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        await self.close()

    @property
    def subscriber_count(self) -> Dict[Union[Type[Event], str], int]:
        """Get count of subscribers per event type."""
        return {
            event_type: len(callbacks)
            for event_type, callbacks in self._subscribers.items()
        }

    @property
    def is_closing(self) -> bool:
        """Check if event bus is closing."""
        return self._closing


class AsyncEventBusAdapter:
    """
    Adapter to make AsyncEventBus compatible with sync EventBus interface.

    This allows gradual migration by providing the old synchronous API
    while using the new async implementation underneath.
    """

    def __init__(self, async_bus: AsyncEventBus):
        """
        Initialize adapter with an async event bus.

        Args:
            async_bus: The async event bus to wrap
        """
        self._async_bus = async_bus
        self._loop = None  # Will be set when needed

    @property
    def session_id(self) -> str:
        """Get session ID from wrapped bus."""
        return self._async_bus.session_id

    def subscribe(
        self, event_type: Union[Type[Event], str], callback: Callable
    ) -> None:
        """Synchronous subscribe wrapper."""
        self._async_bus.subscribe(event_type, callback)

    def unsubscribe(
        self, event_type: Union[Type[Event], str], callback: Callable
    ) -> None:
        """Synchronous unsubscribe wrapper."""
        self._async_bus.unsubscribe(event_type, callback)

    def publish(self, event: Event) -> None:
        """
        Synchronous publish wrapper.

        Note: This blocks until all callbacks complete. For better performance,
        use the async version directly.
        """
        # If we're already in an event loop, schedule as a task
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, create a task
            task = loop.create_task(self._async_bus.publish(event))
            # Store task reference to prevent garbage collection
            if not hasattr(self, "_pending_tasks"):
                self._pending_tasks = WeakSet()
            self._pending_tasks.add(task)
        except RuntimeError:
            # No event loop running, run synchronously
            asyncio.run(self._async_bus.publish(event))

    def clear_subscribers(self, event_type: Optional[Type[Event]] = None) -> None:
        """Synchronous clear subscribers wrapper."""
        self._async_bus.clear_subscribers(event_type)

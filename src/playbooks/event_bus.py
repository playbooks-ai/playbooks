import asyncio
import logging
from collections import defaultdict
from typing import Awaitable, Callable, Dict, List, Type, TypeVar, Union
from weakref import WeakSet

from .events import Event

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Event)


class EventBus:
    """Event bus for typed events with sync and async support."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._handlers: Dict[Type[Event], List[Callable]] = defaultdict(list)
        self._global_handlers: List[Callable] = []
        self._active_tasks: WeakSet[asyncio.Task] = WeakSet()
        self._closing = False

    def subscribe(
        self,
        event_type: Union[Type[T], str],
        callback: Callable[[T], Union[None, Awaitable[None]]],
    ) -> None:
        """Subscribe to events of a specific type."""
        if self._closing:
            raise RuntimeError("Cannot subscribe to closing event bus")

        if isinstance(event_type, str) and event_type == "*":
            self._global_handlers.append(callback)
        else:
            self._handlers[event_type].append(callback)

    def unsubscribe(
        self,
        event_type: Union[Type[T], str],
        callback: Callable[[T], Union[None, Awaitable[None]]],
    ) -> None:
        """Remove a previously registered callback."""
        try:
            if isinstance(event_type, str) and event_type == "*":
                self._global_handlers.remove(callback)
            else:
                self._handlers[event_type].remove(callback)
                if not self._handlers[event_type]:
                    del self._handlers[event_type]
        except ValueError:
            pass

    def publish(self, event: Event) -> None:
        """Publish an event synchronously."""
        # Events are frozen, so session_id should be set during construction

        # Get handlers
        callbacks = list(self._handlers.get(type(event), []))
        callbacks.extend(self._global_handlers)

        # Execute callbacks
        for callback in callbacks:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    # Schedule async callback
                    try:
                        loop = asyncio.get_running_loop()
                        task = loop.create_task(result)
                        self._active_tasks.add(task)
                    except RuntimeError:
                        # No event loop running
                        asyncio.run(result)
            except Exception as e:
                logger.error(
                    f"Error in subscriber for {type(event).__name__}: {e}",
                    exc_info=True,
                )

    async def publish_async(self, event: Event) -> None:
        """Publish an event asynchronously."""
        if self._closing:
            raise RuntimeError("Cannot publish to closing event bus")

        # Events are frozen, so session_id should be set during construction

        event_type = type(event)

        # Get handlers
        handlers = list(self._handlers.get(event_type, []))
        handlers.extend(self._global_handlers)

        if not handlers:
            return

        # Execute handlers concurrently
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(self._safe_handler(handler, event))
            tasks.append(task)
            self._active_tasks.add(task)

        # Wait for completion with error isolation
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Handler {i} failed for {event_type.__name__}: {result}",
                    exc_info=True,
                )

    async def _safe_handler(self, handler: Callable, event: Event) -> None:
        """Execute handler with error isolation."""
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Exception in handler {handler.__name__}: {e}", exc_info=True)
            raise

    def clear_subscribers(self, event_type: Type[Event] = None) -> None:
        """Clear all subscribers or subscribers of a specific event type."""
        if event_type:
            self._handlers.pop(event_type, None)
        else:
            self._handlers.clear()
            self._global_handlers.clear()

    async def close(self) -> None:
        """Close the event bus gracefully."""
        self._closing = True

        # Cancel active tasks
        active_tasks = list(self._active_tasks)
        for task in active_tasks:
            if not task.done():
                task.cancel()

        # Wait for cleanup
        if active_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*active_tasks, return_exceptions=True), timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some handlers did not complete during shutdown")

        self.clear_subscribers()

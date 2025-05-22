import threading
from typing import Callable, Dict, Type, Union

from playbooks.events import Event


class EventBus:
    """An event bus for typed events."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._subscribers: Dict[Event, list[Callable[[Event], None]]] = {}
        self._lock = threading.RLock()  # Reentrant lock for thread safety

    def subscribe(
        self, event_type: Union[Type[Event], str], callback: Callable[[Event], None]
    ) -> None:
        """Subscribe to events of a specific type.

        Args:
            event_type: The type of events to subscribe to
            callback: Function to call when events of this type occur
        """
        with self._lock:
            if isinstance(event_type, str) and event_type == "*":
                # subscribe to all events
                event_subclasses = Event.__subclasses__()
                for event_type in event_subclasses:
                    self._subscribers.setdefault(event_type, []).append(callback)

            else:
                self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(
        self, event_type: Union[Type[Event], str], callback: Callable[[Event], None]
    ) -> None:
        """Remove a previously registered callback.

        Args:
            event_type: The type of events the callback was subscribed to
            callback: The callback function to remove
        """
        with self._lock:
            if isinstance(event_type, str) and event_type == "*":
                # unsubscribe from all events
                event_subclasses = Event.__subclasses__()
                for event_type in event_subclasses:
                    self._subscribers[event_type].remove(callback)
                    if not self._subscribers[event_type]:
                        del self._subscribers[event_type]
            else:
                self._subscribers[event_type].remove(callback)
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers of its type.

        The event's session_id attribute (if it exists) will be set to this bus's session_id.

        Args:
            event: The event object to publish
        """
        with self._lock:
            event.session_id = self.session_id

            # Make a copy of the subscriber list to avoid issues if callbacks modify subscribers
            callbacks = list(self._subscribers.get(type(event), []))

            # Add global subscribers (those subscribed to all events)
            global_subscribers = self._subscribers.get("*", [])
            callbacks.extend(global_subscribers)

        # Call callbacks outside the lock to prevent deadlocks
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Error in subscriber for {type(event).__name__}: {e}")

    def clear_subscribers(self, event_type: Type[Event] = None) -> None:
        """Clear all subscribers or subscribers of a specific event type.

        Args:
            event_type: Optional type of events to clear subscribers for.
                       If None, clears all subscribers.
        """
        with self._lock:
            if event_type:
                self._subscribers.pop(event_type, None)
            else:
                self._subscribers.clear()

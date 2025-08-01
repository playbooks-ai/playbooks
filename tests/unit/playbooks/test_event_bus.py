import threading
import time
import pytest
from unittest.mock import Mock, patch
from dataclasses import dataclass

from playbooks.event_bus import EventBus
from playbooks.events import Event, CallStackPushEvent, VariableUpdateEvent


@dataclass
class TestEventForTesting(Event):
    """Test event for unit testing."""

    message: str
    session_id: str = ""


@dataclass
class AnotherTestEventForTesting(Event):
    """Another test event for unit testing."""

    value: int
    session_id: str = ""


class TestEventForTestingBus:
    """Comprehensive test suite for EventBus class."""

    def test_init(self):
        """Test EventBus initialization."""
        session_id = "test-session-123"
        event_bus = EventBus(session_id)

        assert event_bus.session_id == session_id
        assert event_bus._subscribers == {}
        assert hasattr(event_bus._lock, "acquire") and hasattr(
            event_bus._lock, "release"
        )

    def test_subscribe_single_event_type(self):
        """Test subscribing to a single event type."""
        event_bus = EventBus("test-session")
        callback = Mock()

        event_bus.subscribe(TestEventForTesting, callback)

        assert TestEventForTesting in event_bus._subscribers
        assert callback in event_bus._subscribers[TestEventForTesting]
        assert len(event_bus._subscribers[TestEventForTesting]) == 1

    def test_subscribe_multiple_callbacks_same_event(self):
        """Test subscribing multiple callbacks to the same event type."""
        event_bus = EventBus("test-session")
        callback1 = Mock()
        callback2 = Mock()
        callback3 = Mock()

        event_bus.subscribe(TestEventForTesting, callback1)
        event_bus.subscribe(TestEventForTesting, callback2)
        event_bus.subscribe(TestEventForTesting, callback3)

        assert len(event_bus._subscribers[TestEventForTesting]) == 3
        assert callback1 in event_bus._subscribers[TestEventForTesting]
        assert callback2 in event_bus._subscribers[TestEventForTesting]
        assert callback3 in event_bus._subscribers[TestEventForTesting]

    def test_subscribe_different_event_types(self):
        """Test subscribing to different event types."""
        event_bus = EventBus("test-session")
        callback1 = Mock()
        callback2 = Mock()

        event_bus.subscribe(TestEventForTesting, callback1)
        event_bus.subscribe(AnotherTestEventForTesting, callback2)

        assert TestEventForTesting in event_bus._subscribers
        assert AnotherTestEventForTesting in event_bus._subscribers
        assert callback1 in event_bus._subscribers[TestEventForTesting]
        assert callback2 in event_bus._subscribers[AnotherTestEventForTesting]

    def test_subscribe_wildcard_all_events(self):
        """Test subscribing to all events using wildcard '*'."""
        event_bus = EventBus("test-session")
        callback = Mock()

        # Mock Event.__subclasses__ to return known test events
        with patch.object(Event, "__subclasses__") as mock_subclasses:
            mock_subclasses.return_value = [
                TestEventForTesting,
                AnotherTestEventForTesting,
                CallStackPushEvent,
            ]

            event_bus.subscribe("*", callback)

            # Should subscribe to all Event subclasses
            assert TestEventForTesting in event_bus._subscribers
            assert AnotherTestEventForTesting in event_bus._subscribers
            assert CallStackPushEvent in event_bus._subscribers
            assert callback in event_bus._subscribers[TestEventForTesting]
            assert callback in event_bus._subscribers[AnotherTestEventForTesting]
            assert callback in event_bus._subscribers[CallStackPushEvent]

    def test_unsubscribe_single_callback(self):
        """Test unsubscribing a single callback."""
        event_bus = EventBus("test-session")
        callback = Mock()

        event_bus.subscribe(TestEventForTesting, callback)
        assert callback in event_bus._subscribers[TestEventForTesting]

        event_bus.unsubscribe(TestEventForTesting, callback)
        assert TestEventForTesting not in event_bus._subscribers

    def test_unsubscribe_multiple_callbacks_same_event(self):
        """Test unsubscribing one of multiple callbacks for the same event."""
        event_bus = EventBus("test-session")
        callback1 = Mock()
        callback2 = Mock()

        event_bus.subscribe(TestEventForTesting, callback1)
        event_bus.subscribe(TestEventForTesting, callback2)

        event_bus.unsubscribe(TestEventForTesting, callback1)

        assert TestEventForTesting in event_bus._subscribers
        assert callback1 not in event_bus._subscribers[TestEventForTesting]
        assert callback2 in event_bus._subscribers[TestEventForTesting]
        assert len(event_bus._subscribers[TestEventForTesting]) == 1

    def test_unsubscribe_last_callback_removes_event_type(self):
        """Test that unsubscribing the last callback removes the event type."""
        event_bus = EventBus("test-session")
        callback = Mock()

        event_bus.subscribe(TestEventForTesting, callback)
        event_bus.unsubscribe(TestEventForTesting, callback)

        assert TestEventForTesting not in event_bus._subscribers

    def test_unsubscribe_wildcard_all_events(self):
        """Test unsubscribing from all events using wildcard '*'."""
        event_bus = EventBus("test-session")
        callback = Mock()

        # First subscribe to all events
        with patch.object(Event, "__subclasses__") as mock_subclasses:
            mock_subclasses.return_value = [
                TestEventForTesting,
                AnotherTestEventForTesting,
            ]
            event_bus.subscribe("*", callback)

            # Verify subscription
            assert callback in event_bus._subscribers[TestEventForTesting]
            assert callback in event_bus._subscribers[AnotherTestEventForTesting]

            # Now unsubscribe from all
            event_bus.unsubscribe("*", callback)

            # Should remove callback from all event types and clean up empty lists
            assert TestEventForTesting not in event_bus._subscribers
            assert AnotherTestEventForTesting not in event_bus._subscribers

    def test_unsubscribe_wildcard_with_other_callbacks(self):
        """Test unsubscribing wildcard when other callbacks exist for same events."""
        event_bus = EventBus("test-session")
        wildcard_callback = Mock()
        specific_callback = Mock()

        # Subscribe specific callback to TestEventForTesting
        event_bus.subscribe(TestEventForTesting, specific_callback)

        # Subscribe wildcard callback to all events
        with patch.object(Event, "__subclasses__") as mock_subclasses:
            mock_subclasses.return_value = [
                TestEventForTesting,
                AnotherTestEventForTesting,
            ]
            event_bus.subscribe("*", wildcard_callback)

            # Both callbacks should be subscribed to TestEventForTesting
            assert wildcard_callback in event_bus._subscribers[TestEventForTesting]
            assert specific_callback in event_bus._subscribers[TestEventForTesting]

            # Unsubscribe wildcard
            event_bus.unsubscribe("*", wildcard_callback)

            # Specific callback should remain, wildcard callback should be removed
            assert specific_callback in event_bus._subscribers[TestEventForTesting]
            assert wildcard_callback not in event_bus._subscribers[TestEventForTesting]
            assert (
                AnotherTestEventForTesting not in event_bus._subscribers
            )  # Should be cleaned up

    def test_unsubscribe_nonexistent_callback_raises_error(self):
        """Test that unsubscribing a non-existent callback raises KeyError."""
        event_bus = EventBus("test-session")
        callback = Mock()

        with pytest.raises(KeyError):
            event_bus.unsubscribe(TestEventForTesting, callback)

    def test_publish_single_subscriber(self):
        """Test publishing an event to a single subscriber."""
        event_bus = EventBus("test-session")
        callback = Mock()
        event = TestEventForTesting(message="Hello World")

        event_bus.subscribe(TestEventForTesting, callback)
        event_bus.publish(event)

        callback.assert_called_once_with(event)
        assert event.session_id == "test-session"

    def test_publish_multiple_subscribers(self):
        """Test publishing an event to multiple subscribers."""
        event_bus = EventBus("test-session")
        callback1 = Mock()
        callback2 = Mock()
        callback3 = Mock()
        event = TestEventForTesting(message="Hello World")

        event_bus.subscribe(TestEventForTesting, callback1)
        event_bus.subscribe(TestEventForTesting, callback2)
        event_bus.subscribe(TestEventForTesting, callback3)

        event_bus.publish(event)

        callback1.assert_called_once_with(event)
        callback2.assert_called_once_with(event)
        callback3.assert_called_once_with(event)

    def test_publish_no_subscribers(self):
        """Test publishing an event with no subscribers."""
        event_bus = EventBus("test-session")
        event = TestEventForTesting(message="Hello World")

        # Should not raise any errors
        event_bus.publish(event)
        assert event.session_id == "test-session"

    def test_publish_sets_session_id(self):
        """Test that publish sets the event's session_id."""
        session_id = "custom-session-456"
        event_bus = EventBus(session_id)
        event = TestEventForTesting(message="Test")
        callback = Mock()

        event_bus.subscribe(TestEventForTesting, callback)
        event_bus.publish(event)

        assert event.session_id == session_id
        callback.assert_called_once_with(event)

    def test_publish_overwrites_existing_session_id(self):
        """Test that publish overwrites existing session_id on event."""
        event_bus = EventBus("new-session")
        event = TestEventForTesting(message="Test", session_id="old-session")
        callback = Mock()

        event_bus.subscribe(TestEventForTesting, callback)
        event_bus.publish(event)

        assert event.session_id == "new-session"

    def test_publish_with_wildcard_subscribers(self):
        """Test publishing events with wildcard subscribers."""
        event_bus = EventBus("test-session")
        wildcard_callback = Mock()
        specific_callback = Mock()
        event = TestEventForTesting(message="Test")

        # Subscribe specific callback
        event_bus.subscribe(TestEventForTesting, specific_callback)

        # Subscribe wildcard callback
        with patch.object(Event, "__subclasses__") as mock_subclasses:
            mock_subclasses.return_value = [
                TestEventForTesting,
                AnotherTestEventForTesting,
            ]
            event_bus.subscribe("*", wildcard_callback)

        event_bus.publish(event)

        # Both callbacks should be called
        specific_callback.assert_called_once_with(event)
        wildcard_callback.assert_called_once_with(event)

    def test_publish_callback_exception_handling(self):
        """Test that exceptions in callbacks don't break event publishing."""
        event_bus = EventBus("test-session")
        failing_callback = Mock(side_effect=Exception("Callback error"))
        working_callback = Mock()
        event = TestEventForTesting(message="Test")

        event_bus.subscribe(TestEventForTesting, failing_callback)
        event_bus.subscribe(TestEventForTesting, working_callback)

        # Should not raise exception, but should print error
        with patch("builtins.print") as mock_print:
            event_bus.publish(event)

            # Both callbacks should be attempted
            failing_callback.assert_called_once_with(event)
            working_callback.assert_called_once_with(event)

            # Error should be printed
            mock_print.assert_called_once_with(
                "Error in subscriber for TestEventForTesting: Callback error"
            )

    def test_clear_subscribers_all(self):
        """Test clearing all subscribers."""
        event_bus = EventBus("test-session")
        callback1 = Mock()
        callback2 = Mock()

        event_bus.subscribe(TestEventForTesting, callback1)
        event_bus.subscribe(AnotherTestEventForTesting, callback2)

        assert len(event_bus._subscribers) == 2

        event_bus.clear_subscribers()

        assert len(event_bus._subscribers) == 0

    def test_clear_subscribers_specific_event_type(self):
        """Test clearing subscribers for a specific event type."""
        event_bus = EventBus("test-session")
        callback1 = Mock()
        callback2 = Mock()

        event_bus.subscribe(TestEventForTesting, callback1)
        event_bus.subscribe(AnotherTestEventForTesting, callback2)

        event_bus.clear_subscribers(TestEventForTesting)

        assert TestEventForTesting not in event_bus._subscribers
        assert AnotherTestEventForTesting in event_bus._subscribers
        assert callback2 in event_bus._subscribers[AnotherTestEventForTesting]

    def test_clear_subscribers_nonexistent_event_type(self):
        """Test clearing subscribers for a non-existent event type."""
        event_bus = EventBus("test-session")
        callback = Mock()

        event_bus.subscribe(TestEventForTesting, callback)

        # Should not raise error
        event_bus.clear_subscribers(AnotherTestEventForTesting)

        # Original subscription should remain
        assert TestEventForTesting in event_bus._subscribers
        assert callback in event_bus._subscribers[TestEventForTesting]

    def test_thread_safety_concurrent_subscribe_unsubscribe(self):
        """Test thread safety with concurrent subscribe/unsubscribe operations."""
        event_bus = EventBus("test-session")
        callbacks = [Mock() for _ in range(10)]
        results = []
        errors = []

        def subscribe_unsubscribe_worker(callback_idx):
            try:
                callback = callbacks[callback_idx]
                # Subscribe
                event_bus.subscribe(TestEventForTesting, callback)
                time.sleep(0.001)  # Small delay to increase chance of race conditions
                # Unsubscribe
                event_bus.unsubscribe(TestEventForTesting, callback)
                results.append(f"worker_{callback_idx}_success")
            except Exception as e:
                errors.append(f"worker_{callback_idx}_error: {e}")

        # Start multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=subscribe_unsubscribe_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should complete without errors
        assert len(errors) == 0
        assert len(results) == 10
        assert TestEventForTesting not in event_bus._subscribers

    def test_thread_safety_concurrent_publish(self):
        """Test thread safety with concurrent publish operations."""
        event_bus = EventBus("test-session")
        callback = Mock()
        event_bus.subscribe(TestEventForTesting, callback)

        call_counts = []

        def publish_worker(worker_id):
            event = TestEventForTesting(message=f"Message from worker {worker_id}")
            event_bus.publish(event)
            call_counts.append(worker_id)

        # Start multiple threads publishing events
        threads = []
        for i in range(20):
            thread = threading.Thread(target=publish_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All events should have been published
        assert len(call_counts) == 20
        assert callback.call_count == 20

    def test_thread_safety_subscribe_during_publish(self):
        """Test thread safety when subscribing during event publishing."""
        event_bus = EventBus("test-session")
        initial_callback = Mock()
        event_bus.subscribe(TestEventForTesting, initial_callback)

        new_callbacks = []
        publish_complete = threading.Event()

        def slow_callback(event):
            """Callback that takes time, allowing subscription during execution."""
            time.sleep(0.01)
            # Try to subscribe a new callback during publish
            new_callback = Mock()
            new_callbacks.append(new_callback)
            event_bus.subscribe(AnotherTestEventForTesting, new_callback)
            initial_callback(event)

        # Replace initial callback with slow callback
        event_bus.unsubscribe(TestEventForTesting, initial_callback)
        event_bus.subscribe(TestEventForTesting, slow_callback)

        def publish_worker():
            event = TestEventForTesting(message="Test message")
            event_bus.publish(event)
            publish_complete.set()

        # Start publish in separate thread
        publish_thread = threading.Thread(target=publish_worker)
        publish_thread.start()
        publish_thread.join()

        # Should complete without deadlocks
        assert publish_complete.is_set()
        assert len(new_callbacks) == 1
        assert AnotherTestEventForTesting in event_bus._subscribers

    def test_publish_copies_subscriber_list(self):
        """Test that publish makes a copy of subscribers to avoid modification issues."""
        event_bus = EventBus("test-session")
        callback1 = Mock()
        callback2 = Mock()

        def modifying_callback(event):
            """Callback that modifies subscribers during publish."""
            # This should not affect the current publish cycle
            event_bus.subscribe(AnotherTestEventForTesting, Mock())
            callback1(event)

        event_bus.subscribe(TestEventForTesting, modifying_callback)
        event_bus.subscribe(TestEventForTesting, callback2)

        event = TestEventForTesting(message="Test")
        event_bus.publish(event)

        # Both callbacks should have been called despite modification
        callback1.assert_called_once_with(event)
        callback2.assert_called_once_with(event)

        # New subscription should exist
        assert AnotherTestEventForTesting in event_bus._subscribers

    def test_integration_real_event_types(self):
        """Integration test with real event types from the system."""
        event_bus = EventBus("integration-test-session")
        callback = Mock()

        # Test with CallStackPushEvent
        event_bus.subscribe(CallStackPushEvent, callback)
        push_event = CallStackPushEvent(frame="test_frame", stack=["frame1", "frame2"])
        event_bus.publish(push_event)

        callback.assert_called_once_with(push_event)
        assert push_event.session_id == "integration-test-session"

        # Test with VariableUpdateEvent
        callback.reset_mock()
        event_bus.subscribe(VariableUpdateEvent, callback)
        var_event = VariableUpdateEvent(name="test_var", value=42)
        event_bus.publish(var_event)

        assert callback.call_count == 1  # Called for VariableUpdateEvent
        assert var_event.session_id == "integration-test-session"

    def test_memory_cleanup_after_unsubscribe(self):
        """Test that memory is properly cleaned up after unsubscribing."""
        event_bus = EventBus("test-session")
        callbacks = [Mock() for _ in range(100)]

        # Subscribe many callbacks
        for callback in callbacks:
            event_bus.subscribe(TestEventForTesting, callback)

        assert len(event_bus._subscribers[TestEventForTesting]) == 100

        # Unsubscribe all but one
        for callback in callbacks[:-1]:
            event_bus.unsubscribe(TestEventForTesting, callback)

        assert len(event_bus._subscribers[TestEventForTesting]) == 1
        assert callbacks[-1] in event_bus._subscribers[TestEventForTesting]

        # Unsubscribe the last one
        event_bus.unsubscribe(TestEventForTesting, callbacks[-1])

        # Event type should be completely removed
        assert TestEventForTesting not in event_bus._subscribers
        assert len(event_bus._subscribers) == 0

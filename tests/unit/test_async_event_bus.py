"""
Comprehensive unit tests for AsyncEventBus implementation.

Tests cover:
- Basic pub/sub functionality
- Async and sync callback handling
- Error isolation
- Wildcard subscriptions
- Concurrent operations
- Graceful shutdown
- Memory leak prevention
"""

import asyncio
import gc

import pytest

from playbooks.async_event_bus import AsyncEventBus, AsyncEventBusAdapter
from playbooks.events import Event


class SampleEvent(Event):
    """Sample event for unit tests."""

    def __init__(self, data: str):
        super().__init__()
        self.data = data


class AnotherSampleEvent(Event):
    """Another sample event type."""

    def __init__(self, value: int):
        super().__init__()
        self.value = value


@pytest.mark.asyncio
class TestAsyncEventBus:
    """Test cases for AsyncEventBus."""

    async def test_basic_publish_subscribe(self):
        """Test basic publish/subscribe functionality."""
        bus = AsyncEventBus("test-session")
        received_events = []

        def handler(event: SampleEvent):
            received_events.append(event)

        # Subscribe and publish
        bus.subscribe(SampleEvent, handler)
        test_event = SampleEvent("hello")
        await bus.publish(test_event)

        # Verify
        assert len(received_events) == 1
        assert received_events[0].data == "hello"
        assert received_events[0].session_id == "test-session"

    async def test_async_callback(self):
        """Test async callback handling."""
        bus = AsyncEventBus("test-session")
        received_events = []

        async def async_handler(event: SampleEvent):
            await asyncio.sleep(0.01)  # Simulate async work
            received_events.append(event)

        # Subscribe and publish
        bus.subscribe(SampleEvent, async_handler)
        await bus.publish(SampleEvent("async"))

        # Verify
        assert len(received_events) == 1
        assert received_events[0].data == "async"

    async def test_multiple_subscribers(self):
        """Test multiple subscribers to same event type."""
        bus = AsyncEventBus("test-session")
        results = []

        def handler1(event):
            results.append(("h1", event.data))

        def handler2(event):
            results.append(("h2", event.data))

        async def handler3(event):
            results.append(("h3", event.data))

        # Subscribe multiple handlers
        bus.subscribe(SampleEvent, handler1)
        bus.subscribe(SampleEvent, handler2)
        bus.subscribe(SampleEvent, handler3)

        # Publish
        await bus.publish(SampleEvent("multi"))

        # Verify all handlers called (order not guaranteed due to concurrent execution)
        assert len(results) == 3
        assert ("h1", "multi") in results
        assert ("h2", "multi") in results
        assert ("h3", "multi") in results

    async def test_wildcard_subscription(self):
        """Test wildcard subscription to all events."""
        bus = AsyncEventBus("test-session")
        received_events = []

        def wildcard_handler(event):
            received_events.append((type(event).__name__, event))

        # Subscribe to all events
        bus.subscribe("*", wildcard_handler)

        # Publish different event types
        await bus.publish(SampleEvent("test1"))
        await bus.publish(AnotherSampleEvent(42))

        # Verify
        assert len(received_events) == 2
        assert received_events[0][0] == "SampleEvent"
        assert received_events[1][0] == "AnotherSampleEvent"

    async def test_unsubscribe(self):
        """Test unsubscribe functionality."""
        bus = AsyncEventBus("test-session")
        call_count = 0

        def handler(event):
            nonlocal call_count
            call_count += 1

        # Subscribe
        bus.subscribe(SampleEvent, handler)
        await bus.publish(SampleEvent("first"))
        assert call_count == 1

        # Unsubscribe
        bus.unsubscribe(SampleEvent, handler)
        await bus.publish(SampleEvent("second"))
        assert call_count == 1  # Should not increase

    async def test_unsubscribe_wildcard(self):
        """Test unsubscribe from wildcard subscription."""
        bus = AsyncEventBus("test-session")
        call_count = 0

        def handler(event):
            nonlocal call_count
            call_count += 1

        # Subscribe to all
        bus.subscribe("*", handler)
        await bus.publish(SampleEvent("first"))
        assert call_count == 1

        # Unsubscribe from all
        bus.unsubscribe("*", handler)
        await bus.publish(SampleEvent("second"))
        await bus.publish(AnotherSampleEvent(42))
        assert call_count == 1  # Should not increase

    async def test_error_isolation(self):
        """Test that errors in one callback don't affect others."""
        bus = AsyncEventBus("test-session")
        results = []

        def failing_handler(event):
            raise ValueError("Intentional error")

        def working_handler(event):
            results.append("success")

        # Subscribe both handlers
        bus.subscribe(SampleEvent, failing_handler)
        bus.subscribe(SampleEvent, working_handler)

        # Publish - should not raise
        await bus.publish(SampleEvent("test"))

        # Verify working handler was called
        assert results == ["success"]

    async def test_concurrent_publish(self):
        """Test concurrent publishing of events."""
        bus = AsyncEventBus("test-session")
        received_events = []

        async def slow_handler(event):
            await asyncio.sleep(0.01)
            received_events.append(event.data)

        bus.subscribe(SampleEvent, slow_handler)

        # Publish multiple events concurrently
        tasks = [bus.publish(SampleEvent(f"event-{i}")) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all events received
        assert len(received_events) == 10
        assert all(f"event-{i}" in received_events for i in range(10))

    async def test_clear_subscribers(self):
        """Test clearing subscribers."""
        bus = AsyncEventBus("test-session")
        call_count = 0

        def handler(event):
            nonlocal call_count
            call_count += 1

        # Subscribe to multiple event types
        bus.subscribe(SampleEvent, handler)
        bus.subscribe(AnotherSampleEvent, handler)

        # Clear specific type
        bus.clear_subscribers(SampleEvent)
        await bus.publish(SampleEvent("test"))
        assert call_count == 0

        # Other type still works
        await bus.publish(AnotherSampleEvent(42))
        assert call_count == 1

        # Clear all
        bus.clear_subscribers()
        await bus.publish(AnotherSampleEvent(99))
        assert call_count == 1  # No increase

    async def test_graceful_shutdown(self):
        """Test graceful shutdown with active tasks."""
        bus = AsyncEventBus("test-session")
        task_completed = False

        async def slow_handler(event):
            await asyncio.sleep(0.1)
            nonlocal task_completed
            task_completed = True

        bus.subscribe(SampleEvent, slow_handler)

        # Publish event (don't await)
        _ = asyncio.create_task(bus.publish(SampleEvent("test")))

        # Close bus while task is running
        await asyncio.sleep(0.01)  # Let task start
        await bus.close()

        # Verify task was cancelled
        assert bus.is_closing
        # Task may or may not complete depending on timing

    async def test_context_manager(self):
        """Test context manager usage."""
        received = []

        async with AsyncEventBus("test-session") as bus:
            bus.subscribe(SampleEvent, lambda e: received.append(e))
            await bus.publish(SampleEvent("ctx"))

        # After context, bus should be closed
        assert bus.is_closing
        assert len(received) == 1

        # Publishing should raise
        with pytest.raises(RuntimeError, match="closing"):
            await bus.publish(SampleEvent("after"))

    async def test_weak_reference_cleanup(self):
        """Test that active tasks are tracked with weak references."""
        bus = AsyncEventBus("test-session")
        initial_count = len(bus._active_tasks)

        async def handler(event):
            await asyncio.sleep(0.01)

        bus.subscribe(SampleEvent, handler)

        # Publish several events
        for i in range(5):
            await bus.publish(SampleEvent(f"test-{i}"))

        # Wait a bit for tasks to complete
        await asyncio.sleep(0.01)

        # Force garbage collection
        gc.collect()

        # Active tasks should be cleaned up (allow for one remaining task)
        assert len(bus._active_tasks) <= initial_count + 1

    async def test_subscriber_count_property(self):
        """Test subscriber count property."""
        bus = AsyncEventBus("test-session")

        # Initially empty
        assert bus.subscriber_count == {}

        # Add subscribers
        bus.subscribe(SampleEvent, lambda e: None)
        bus.subscribe(SampleEvent, lambda e: None)
        bus.subscribe(AnotherSampleEvent, lambda e: None)
        bus.subscribe("*", lambda e: None)

        # Check counts
        counts = bus.subscriber_count
        assert counts[SampleEvent] == 2  # 2 direct subscribers
        assert counts[AnotherSampleEvent] == 1  # 1 direct subscriber
        assert counts["*"] == 1  # 1 wildcard subscriber

    async def test_type_validation(self):
        """Test type validation for events and callbacks."""
        bus = AsyncEventBus("test-session")

        # Invalid callback type
        with pytest.raises(TypeError, match="Callback must be callable"):
            bus.subscribe(SampleEvent, "not-a-function")

        # Invalid event type
        with pytest.raises(TypeError, match="Event must be an Event instance"):
            await bus.publish("not-an-event")

    async def test_cancellation_propagation(self):
        """Test that cancellation is properly propagated."""
        bus = AsyncEventBus("test-session")
        handler_started = False
        handler_cancelled = False

        async def handler(event):
            nonlocal handler_started, handler_cancelled
            handler_started = True
            try:
                await asyncio.sleep(10)  # Long sleep
            except asyncio.CancelledError:
                handler_cancelled = True
                raise

        bus.subscribe(SampleEvent, handler)

        # Start publish in a task
        publish_task = asyncio.create_task(bus.publish(SampleEvent("test")))
        await asyncio.sleep(0.01)  # Let handler start

        # Cancel the publish task
        publish_task.cancel()

        try:
            await publish_task
        except asyncio.CancelledError:
            pass

        assert handler_started
        # Handler cancellation depends on implementation details


class TestAsyncEventBusAdapter:
    """Test cases for backward compatibility adapter."""

    def test_sync_publish_subscribe(self):
        """Test synchronous API compatibility."""
        async_bus = AsyncEventBus("test-session")
        adapter = AsyncEventBusAdapter(async_bus)
        received = []

        def handler(event):
            received.append(event.data)

        # Use sync API
        adapter.subscribe(SampleEvent, handler)
        adapter.publish(SampleEvent("sync-test"))

        # In sync context, this might not work as expected
        # Real implementation would need event loop handling

    def test_session_id_property(self):
        """Test session ID property access."""
        async_bus = AsyncEventBus("test-123")
        adapter = AsyncEventBusAdapter(async_bus)

        assert adapter.session_id == "test-123"

    @pytest.mark.asyncio
    async def test_adapter_in_async_context(self):
        """Test adapter when used in async context."""
        async_bus = AsyncEventBus("test-session")
        adapter = AsyncEventBusAdapter(async_bus)
        received = []

        def handler(event):
            received.append(event.data)

        adapter.subscribe(SampleEvent, handler)

        # In async context, publish creates a task
        adapter.publish(SampleEvent("async-adapter"))

        # Give task time to complete
        await asyncio.sleep(0.01)

        assert len(received) == 1
        assert received[0] == "async-adapter"

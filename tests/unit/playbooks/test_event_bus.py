"""
Comprehensive tests for the unified EventBus.

Tests both synchronous and asynchronous event handling, subscription management,
error handling, and integration with the unified event system.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.playbooks.event_bus import EventBus
from src.playbooks.events import (
    AgentStartedEvent,
    CallStackPushEvent,
    VariableUpdateEvent,
)


class TestEventBusBasics:
    """Test basic EventBus functionality."""

    def test_eventbus_creation(self):
        """Test EventBus creation with session_id."""
        bus = EventBus("test-session")
        assert bus.session_id == "test-session"
        assert not bus._closing

    def test_eventbus_subscription_specific_event(self):
        """Test subscribing to a specific event type."""
        bus = EventBus("test-session")
        handler = Mock()

        bus.subscribe(CallStackPushEvent, handler)

        # Check that handler was added
        assert CallStackPushEvent in bus._handlers
        assert handler in bus._handlers[CallStackPushEvent]

    def test_eventbus_subscription_all_events(self):
        """Test subscribing to all events with wildcard."""
        bus = EventBus("test-session")
        handler = Mock()

        bus.subscribe("*", handler)

        # Check that handler was added to global handlers
        assert handler in bus._global_handlers

    def test_eventbus_unsubscribe_specific(self):
        """Test unsubscribing from specific event type."""
        bus = EventBus("test-session")
        handler = Mock()

        bus.subscribe(CallStackPushEvent, handler)
        bus.unsubscribe(CallStackPushEvent, handler)

        # Handler should be removed
        assert (
            CallStackPushEvent not in bus._handlers
            or handler not in bus._handlers[CallStackPushEvent]
        )

    def test_eventbus_unsubscribe_all(self):
        """Test unsubscribing from all events."""
        bus = EventBus("test-session")
        handler = Mock()

        bus.subscribe("*", handler)
        bus.unsubscribe("*", handler)

        # Handler should be removed from global handlers
        assert handler not in bus._global_handlers

    def test_eventbus_unsubscribe_nonexistent(self):
        """Test unsubscribing handler that wasn't subscribed (should not raise)."""
        bus = EventBus("test-session")
        handler = Mock()

        # Should not raise exception
        bus.unsubscribe(CallStackPushEvent, handler)
        bus.unsubscribe("*", handler)

    def test_eventbus_clear_subscribers_specific(self):
        """Test clearing subscribers for specific event type."""
        bus = EventBus("test-session")
        handler1 = Mock()
        handler2 = Mock()

        bus.subscribe(CallStackPushEvent, handler1)
        bus.subscribe(AgentStartedEvent, handler2)

        bus.clear_subscribers(CallStackPushEvent)

        # Only CallStackPushEvent handlers should be cleared
        assert CallStackPushEvent not in bus._handlers
        assert AgentStartedEvent in bus._handlers

    def test_eventbus_clear_subscribers_all(self):
        """Test clearing all subscribers."""
        bus = EventBus("test-session")
        handler1 = Mock()
        handler2 = Mock()

        bus.subscribe(CallStackPushEvent, handler1)
        bus.subscribe("*", handler2)

        bus.clear_subscribers()

        # All handlers should be cleared
        assert len(bus._handlers) == 0
        assert len(bus._global_handlers) == 0


class TestEventBusSyncPublishing:
    """Test synchronous event publishing."""

    def test_sync_publish_to_specific_handler(self):
        """Test publishing event to specific handler."""
        bus = EventBus("test-session")
        handler = Mock()

        bus.subscribe(CallStackPushEvent, handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        bus.publish(event)

        # Handler should be called once with the event
        handler.assert_called_once_with(event)

    def test_sync_publish_to_wildcard_handler(self):
        """Test publishing event to wildcard handler."""
        bus = EventBus("test-session")
        handler = Mock()

        bus.subscribe("*", handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        bus.publish(event)

        # Handler should be called once with the event
        handler.assert_called_once_with(event)

    def test_sync_publish_to_multiple_handlers(self):
        """Test publishing event to multiple handlers."""
        bus = EventBus("test-session")
        specific_handler = Mock()
        wildcard_handler = Mock()

        bus.subscribe(CallStackPushEvent, specific_handler)
        bus.subscribe("*", wildcard_handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        bus.publish(event)

        # Both handlers should be called
        specific_handler.assert_called_once_with(event)
        wildcard_handler.assert_called_once_with(event)

    def test_sync_publish_no_handlers(self):
        """Test publishing event with no handlers (should not raise)."""
        bus = EventBus("test-session")

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        # Should not raise exception
        bus.publish(event)

    def test_sync_publish_handler_exception(self):
        """Test that handler exceptions are caught and logged."""
        bus = EventBus("test-session")
        failing_handler = Mock(side_effect=Exception("Handler failed"))
        working_handler = Mock()

        bus.subscribe(CallStackPushEvent, failing_handler)
        bus.subscribe(CallStackPushEvent, working_handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        # Should not raise exception, both handlers should be called
        bus.publish(event)

        failing_handler.assert_called_once_with(event)
        working_handler.assert_called_once_with(event)


class TestEventBusAsyncPublishing:
    """Test asynchronous event publishing."""

    @pytest.mark.asyncio
    async def test_async_publish_to_async_handler(self):
        """Test publishing event to async handler."""
        bus = EventBus("test-session")
        handler = AsyncMock()

        bus.subscribe(CallStackPushEvent, handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        await bus.publish_async(event)

        # Handler should be called once with the event
        handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_async_publish_to_sync_handler(self):
        """Test publishing event to sync handler via async method."""
        bus = EventBus("test-session")
        handler = Mock()

        bus.subscribe(CallStackPushEvent, handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        await bus.publish_async(event)

        # Handler should be called once with the event
        handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_async_publish_mixed_handlers(self):
        """Test publishing to both sync and async handlers."""
        bus = EventBus("test-session")
        sync_handler = Mock()
        async_handler = AsyncMock()

        bus.subscribe(CallStackPushEvent, sync_handler)
        bus.subscribe(CallStackPushEvent, async_handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        await bus.publish_async(event)

        # Both handlers should be called
        sync_handler.assert_called_once_with(event)
        async_handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_async_publish_handler_exception(self):
        """Test that async handler exceptions are caught and logged."""
        bus = EventBus("test-session")
        failing_handler = AsyncMock(side_effect=Exception("Async handler failed"))
        working_handler = AsyncMock()

        bus.subscribe(CallStackPushEvent, failing_handler)
        bus.subscribe(CallStackPushEvent, working_handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        # Should not raise exception, both handlers should be called
        await bus.publish_async(event)

        failing_handler.assert_called_once_with(event)
        working_handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_async_publish_concurrent_execution(self):
        """Test that async handlers execute concurrently."""
        bus = EventBus("test-session")

        # Create handlers that track execution order
        execution_order = []

        async def slow_handler(event):
            execution_order.append("slow_start")
            await asyncio.sleep(0.1)
            execution_order.append("slow_end")

        async def fast_handler(event):
            execution_order.append("fast_start")
            await asyncio.sleep(0.05)
            execution_order.append("fast_end")

        bus.subscribe(CallStackPushEvent, slow_handler)
        bus.subscribe(CallStackPushEvent, fast_handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=["main"])

        await bus.publish_async(event)

        # Both handlers should have started before either finished (concurrent execution)
        assert "slow_start" in execution_order
        assert "fast_start" in execution_order
        assert "slow_end" in execution_order
        assert "fast_end" in execution_order

        # Fast handler should finish before slow handler
        fast_end_idx = execution_order.index("fast_end")
        slow_end_idx = execution_order.index("slow_end")
        assert fast_end_idx < slow_end_idx


class TestEventBusIntegration:
    """Test EventBus integration with different event types."""

    def test_different_event_types(self):
        """Test handling different event types correctly."""
        bus = EventBus("test-session")

        # Handlers for different event types
        callstack_handler = Mock()
        agent_handler = Mock()
        variable_handler = Mock()

        bus.subscribe(CallStackPushEvent, callstack_handler)
        bus.subscribe(AgentStartedEvent, agent_handler)
        bus.subscribe(VariableUpdateEvent, variable_handler)

        # Publish different event types
        callstack_event = CallStackPushEvent(session_id="test", frame="main", stack=[])
        agent_event = AgentStartedEvent(session_id="test", agent_name="TestAgent")
        variable_event = VariableUpdateEvent(
            session_id="test", variable_name="x", variable_value=42
        )

        bus.publish(callstack_event)
        bus.publish(agent_event)
        bus.publish(variable_event)

        # Each handler should only be called for its event type
        callstack_handler.assert_called_once_with(callstack_event)
        agent_handler.assert_called_once_with(agent_event)
        variable_handler.assert_called_once_with(variable_event)

    def test_wildcard_receives_all_events(self):
        """Test that wildcard handler receives all event types."""
        bus = EventBus("test-session")
        wildcard_handler = Mock()

        bus.subscribe("*", wildcard_handler)

        # Publish different event types
        callstack_event = CallStackPushEvent(session_id="test", frame="main", stack=[])
        agent_event = AgentStartedEvent(session_id="test", agent_name="TestAgent")
        variable_event = VariableUpdateEvent(
            session_id="test", variable_name="x", variable_value=42
        )

        bus.publish(callstack_event)
        bus.publish(agent_event)
        bus.publish(variable_event)

        # Wildcard handler should be called for all events
        assert wildcard_handler.call_count == 3
        wildcard_handler.assert_any_call(callstack_event)
        wildcard_handler.assert_any_call(agent_event)
        wildcard_handler.assert_any_call(variable_event)


class TestEventBusLifecycle:
    """Test EventBus lifecycle management."""

    def test_subscription_after_closing_raises_error(self):
        """Test that subscription after closing raises error."""
        bus = EventBus("test-session")
        bus._closing = True

        with pytest.raises(RuntimeError, match="Cannot subscribe to closing event bus"):
            bus.subscribe(CallStackPushEvent, Mock())

    @pytest.mark.asyncio
    async def test_async_publish_after_closing_raises_error(self):
        """Test that async publish after closing raises error."""
        bus = EventBus("test-session")
        bus._closing = True

        event = CallStackPushEvent(session_id="test", frame="main", stack=[])

        with pytest.raises(RuntimeError, match="Cannot publish to closing event bus"):
            await bus.publish_async(event)

    @pytest.mark.asyncio
    async def test_close_cancels_active_tasks(self):
        """Test that close() cancels active tasks."""
        bus = EventBus("test-session")

        # Create a long-running handler
        async def long_handler(event):
            await asyncio.sleep(1.0)  # Long delay

        bus.subscribe(CallStackPushEvent, long_handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=[])

        # Start async publish (don't await)
        publish_task = asyncio.create_task(bus.publish_async(event))

        # Give it a moment to start
        await asyncio.sleep(0.01)

        # Close the bus
        close_task = asyncio.create_task(bus.close())

        # Both should complete quickly (close cancels the handler)
        await asyncio.wait_for(
            asyncio.gather(publish_task, close_task, return_exceptions=True),
            timeout=0.5,
        )

        assert bus._closing is True

    @pytest.mark.asyncio
    async def test_close_clears_subscribers(self):
        """Test that close() clears all subscribers."""
        bus = EventBus("test-session")
        handler = Mock()

        bus.subscribe(CallStackPushEvent, handler)
        bus.subscribe("*", handler)

        await bus.close()

        assert len(bus._handlers) == 0
        assert len(bus._global_handlers) == 0


class TestEventBusErrorHandling:
    """Test EventBus error handling and edge cases."""

    def test_sync_publish_with_coroutine_handler(self):
        """Test sync publish with async handler (should schedule it)."""
        bus = EventBus("test-session")

        async def async_handler(event):
            return "async result"

        bus.subscribe(CallStackPushEvent, async_handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=[])

        # Should not raise exception (async handler gets scheduled)
        bus.publish(event)

    def test_multiple_subscriptions_same_handler(self):
        """Test that same handler can be subscribed multiple times."""
        bus = EventBus("test-session")
        handler = Mock()

        bus.subscribe(CallStackPushEvent, handler)
        bus.subscribe(CallStackPushEvent, handler)  # Subscribe again

        event = CallStackPushEvent(session_id="test", frame="main", stack=[])
        bus.publish(event)

        # Handler should be called twice
        assert handler.call_count == 2

    def test_handler_modification_during_publish(self):
        """Test that handlers can be modified during event publishing."""
        bus = EventBus("test-session")
        call_order = []

        def first_handler(event):
            call_order.append("first")
            # Unsubscribe self during handling
            bus.unsubscribe(CallStackPushEvent, first_handler)

        def second_handler(event):
            call_order.append("second")

        bus.subscribe(CallStackPushEvent, first_handler)
        bus.subscribe(CallStackPushEvent, second_handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=[])
        bus.publish(event)

        # Both handlers should still be called for this event
        assert "first" in call_order
        assert "second" in call_order

        # But first_handler should be unsubscribed for future events
        call_order.clear()
        bus.publish(event)
        assert call_order == ["second"]


class TestEventBusPerformance:
    """Test EventBus performance characteristics."""

    def test_many_handlers_performance(self):
        """Test performance with many handlers."""
        bus = EventBus("test-session")
        handlers = [Mock() for _ in range(100)]

        # Subscribe all handlers
        for handler in handlers:
            bus.subscribe(CallStackPushEvent, handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=[])

        # Should handle many handlers efficiently
        bus.publish(event)

        # All handlers should be called
        for handler in handlers:
            handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_many_async_handlers_performance(self):
        """Test performance with many async handlers."""
        bus = EventBus("test-session")
        handlers = [AsyncMock() for _ in range(50)]

        # Subscribe all handlers
        for handler in handlers:
            bus.subscribe(CallStackPushEvent, handler)

        event = CallStackPushEvent(session_id="test", frame="main", stack=[])

        # Should handle many async handlers efficiently
        await bus.publish_async(event)

        # All handlers should be called
        for handler in handlers:
            handler.assert_called_once_with(event)

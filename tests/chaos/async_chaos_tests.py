"""
Chaos engineering tests for async components.

These tests simulate various failure conditions and edge cases to ensure
the async architecture handles unexpected situations gracefully.
"""

import asyncio
import gc
import logging
import random
import time
from contextlib import asynccontextmanager

import pytest

from playbooks.agents.async_queue import AsyncMessageQueue
from playbooks.infrastructure.event_bus import EventBus
from playbooks.core.events import Event
from playbooks.core.message import Message, MessageType

logger = logging.getLogger(__name__)


class ChaosEvent(Event):
    """Event for chaos testing."""

    def __init__(self, data: str, delay: float = 0):
        super().__init__()
        self.data = data
        self.delay = delay


def create_chaos_message(content: str, sender_id: str = "chaos") -> Message:
    """Create a message for chaos testing."""
    return Message(
        sender_id=sender_id,
        sender_klass="ChaosAgent",
        content=content,
        recipient_id="target",
        recipient_klass="TargetAgent",
        message_type=MessageType.DIRECT,
        meeting_id=None,
    )


class ChaosMonkey:
    """Chaos engineering helper for async testing."""

    def __init__(self, failure_rate: float = 0.1):
        """
        Initialize chaos monkey.

        Args:
            failure_rate: Probability of introducing failures (0.0 to 1.0)
        """
        self.failure_rate = failure_rate
        self.failures_injected = 0
        self.operations_count = 0

    async def maybe_fail(self, operation_name: str = "operation"):
        """Randomly inject failures."""
        self.operations_count += 1

        if random.random() < self.failure_rate:
            self.failures_injected += 1
            failure_type = random.choice(["timeout", "cancel", "exception", "delay"])

            logger.info(f"Chaos: Injecting {failure_type} in {operation_name}")

            if failure_type == "timeout":
                # Simulate timeout by sleeping longer than expected
                await asyncio.sleep(random.uniform(1.0, 2.0))
            elif failure_type == "cancel":
                # Simulate cancellation
                raise asyncio.CancelledError(f"Chaos cancellation in {operation_name}")
            elif failure_type == "exception":
                # Simulate random exception
                raise RuntimeError(f"Chaos exception in {operation_name}")
            elif failure_type == "delay":
                # Simulate network delay
                await asyncio.sleep(random.uniform(0.1, 0.5))

    @property
    def failure_stats(self) -> dict:
        """Get failure statistics."""
        return {
            "operations": self.operations_count,
            "failures": self.failures_injected,
            "failure_rate": self.failures_injected / max(1, self.operations_count),
        }


@asynccontextmanager
async def chaos_test_context(chaos_monkey: ChaosMonkey, duration: float = 5.0):
    """Context manager for chaos testing with time limits."""
    start_time = time.time()
    try:
        yield chaos_monkey
    finally:
        elapsed = time.time() - start_time
        stats = chaos_monkey.failure_stats
        logger.info(f"Chaos test completed in {elapsed:.2f}s: {stats}")


@pytest.mark.asyncio
class TestEventBusChaos:
    """Chaos tests for EventBus (async)."""

    async def test_high_volume_with_failures(self):
        """Test event bus under high load with random failures."""
        bus = EventBus("chaos-session")
        chaos = ChaosMonkey(failure_rate=0.2)

        received_events = []
        failed_callbacks = 0

        async def chaotic_handler(event: ChaosEvent):
            nonlocal failed_callbacks
            try:
                await chaos.maybe_fail("event_handler")
                await asyncio.sleep(event.delay)
                received_events.append(event.data)
            except Exception:
                failed_callbacks += 1
                raise  # Let event bus handle the error

        # Subscribe handler
        bus.subscribe(ChaosEvent, chaotic_handler)

        async with chaos_test_context(chaos, duration=3.0):
            # Publish many events with random delays
            tasks = []
            for i in range(100):
                event = ChaosEvent(f"event-{i}", delay=random.uniform(0, 0.1))
                task = asyncio.create_task(bus.publish(event))
                tasks.append(task)

                # Random publishing delays
                if random.random() < 0.3:
                    await asyncio.sleep(random.uniform(0, 0.05))

            # Wait for all publishes
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for publish failures
            publish_failures = sum(1 for r in results if isinstance(r, Exception))

        await bus.close()

        # Verify system survived chaos
        assert len(received_events) > 50  # Should handle most events
        assert failed_callbacks > 0  # Should have some failures
        assert publish_failures == 0  # Publishes should not fail

        logger.info(
            f"Handled {len(received_events)}/100 events, "
            f"{failed_callbacks} callback failures, "
            f"{publish_failures} publish failures"
        )

    async def test_rapid_subscribe_unsubscribe(self):
        """Test rapid subscription changes."""
        bus = EventBus("chaos-session")
        chaos = ChaosMonkey(failure_rate=0.1)

        handlers = []
        active_handlers = set()

        def create_handler(handler_id: int):
            async def handler(event):
                await chaos.maybe_fail(f"handler-{handler_id}")

            return handler

        async with chaos_test_context(chaos):
            # Rapidly add and remove handlers
            for i in range(50):
                handler = create_handler(i)
                handlers.append(handler)

                # Subscribe
                bus.subscribe(ChaosEvent, handler)
                active_handlers.add(handler)

                # Randomly unsubscribe some handlers
                if len(active_handlers) > 10 and random.random() < 0.3:
                    old_handler = random.choice(list(active_handlers))
                    try:
                        bus.unsubscribe(ChaosEvent, old_handler)
                        active_handlers.remove(old_handler)
                    except ValueError:
                        pass  # Handler might have been removed already

                # Publish event occasionally
                if i % 10 == 0:
                    await bus.publish(ChaosEvent(f"test-{i}"))

        await bus.close()

        # System should survive rapid changes
        assert len(active_handlers) > 0

    async def test_concurrent_close_operations(self):
        """Test closing event bus while operations are active."""
        bus = EventBus("chaos-session")
        chaos = ChaosMonkey(failure_rate=0.1)

        results = []

        async def slow_handler(event):
            await chaos.maybe_fail("slow_handler")
            await asyncio.sleep(random.uniform(0.1, 0.5))
            results.append(event.data)

        bus.subscribe(ChaosEvent, slow_handler)

        # Start many slow operations
        publish_tasks = []
        for i in range(20):
            task = asyncio.create_task(bus.publish(ChaosEvent(f"slow-{i}")))
            publish_tasks.append(task)

        # Let some operations start
        await asyncio.sleep(0.1)

        # Close bus while operations are running
        close_task = asyncio.create_task(bus.close())

        # Wait for everything
        all_results = await asyncio.gather(
            *publish_tasks, close_task, return_exceptions=True
        )

        # Verify graceful shutdown
        assert bus.is_closing

        # Some operations may have completed, some may have been cancelled
        completed_publishes = sum(
            1 for r in all_results[:-1] if not isinstance(r, Exception)
        )

        logger.info(f"Completed {completed_publishes}/20 publishes during shutdown")


@pytest.mark.asyncio
class TestAsyncMessageQueueChaos:
    """Chaos tests for AsyncMessageQueue."""

    async def test_producer_consumer_chaos(self):
        """Test producer-consumer pattern with chaos."""
        queue = AsyncMessageQueue(max_size=50)
        chaos = ChaosMonkey(failure_rate=0.15)

        produced_messages = []
        consumed_messages = []

        async def chaotic_producer(producer_id: int):
            for i in range(20):
                try:
                    await chaos.maybe_fail(f"producer-{producer_id}")
                    message = create_chaos_message(f"p{producer_id}-m{i}")
                    await queue.put(message)
                    produced_messages.append(message.content)

                    # Random delays
                    await asyncio.sleep(random.uniform(0, 0.05))
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Producer {producer_id} failed: {e}")

        async def chaotic_consumer(consumer_id: int):
            while not queue.is_closed or queue.size > 0:
                try:
                    await chaos.maybe_fail(f"consumer-{consumer_id}")
                    message = await queue.get(timeout=0.5)
                    consumed_messages.append(message.content)

                    # Random processing delays
                    await asyncio.sleep(random.uniform(0, 0.02))
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Consumer {consumer_id} failed: {e}")

        async with chaos_test_context(chaos, duration=5.0):
            # Start producers and consumers
            tasks = []

            # Multiple producers
            for i in range(3):
                tasks.append(asyncio.create_task(chaotic_producer(i)))

            # Multiple consumers
            for i in range(2):
                tasks.append(asyncio.create_task(chaotic_consumer(i)))

            # Let them run for a while
            await asyncio.sleep(2.0)

            # Close queue
            await queue.close()

            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

        # Verify reasonable throughput despite chaos
        assert len(consumed_messages) > 15  # Should process messages despite chaos
        assert (
            len(produced_messages) > len(consumed_messages) * 0.5
        )  # Chaos causes some loss

        logger.info(
            f"Produced: {len(produced_messages)}, "
            f"Consumed: {len(consumed_messages)}"
        )

    async def test_memory_pressure_chaos(self):
        """Test queue behavior under memory pressure."""
        queue = AsyncMessageQueue(max_size=100)
        chaos = ChaosMonkey(failure_rate=0.1)

        # Track memory allocations
        allocations = []

        async def memory_intensive_handler():
            # Simulate memory-heavy operations
            data = bytearray(random.randint(1024, 10240))  # 1-10KB allocations
            allocations.append(data)

            await chaos.maybe_fail("memory_operation")

            # Randomly free some memory
            if len(allocations) > 50 and random.random() < 0.3:
                allocations.pop(0)

        async with chaos_test_context(chaos):
            # Fill queue with messages
            for i in range(200):
                try:
                    message = create_chaos_message(f"mem-test-{i}")
                    await queue.put(message)

                    # Trigger memory operations
                    if i % 10 == 0:
                        try:
                            await memory_intensive_handler()
                        except asyncio.CancelledError:
                            # Chaos injection - continue with next iteration
                            continue

                    # Force garbage collection occasionally
                    if i % 50 == 0:
                        gc.collect()

                except asyncio.CancelledError:
                    # Chaos injection - continue
                    continue
                except Exception as e:
                    logger.warning(f"Memory test iteration {i} failed: {e}")

            # Drain queue
            processed = 0
            while queue.size > 0:
                try:
                    await queue.get(timeout=0.1)
                    processed += 1
                except asyncio.TimeoutError:
                    break

        await queue.close()

        # Verify system remained stable
        assert processed >= 100  # Should process messages despite chaos
        assert len(allocations) < 100  # Memory should be manageable

    async def test_cancellation_storm(self):
        """Test behavior under heavy cancellation."""
        queue = AsyncMessageQueue()
        chaos = ChaosMonkey(failure_rate=0.3)

        completed_operations = 0
        cancelled_operations = 0

        async def cancellable_operation(op_id: int):
            nonlocal completed_operations, cancelled_operations

            try:
                await chaos.maybe_fail(f"operation-{op_id}")

                # Simulate work
                for i in range(5):
                    await asyncio.sleep(0.05)

                    # Put and get message
                    message = create_chaos_message(f"op-{op_id}-{i}")
                    await queue.put(message)
                    retrieved = await queue.get()
                    assert retrieved.content == message.content

                completed_operations += 1

            except asyncio.CancelledError:
                cancelled_operations += 1
                raise

        # Start many operations
        tasks = []
        for i in range(50):
            task = asyncio.create_task(cancellable_operation(i))
            tasks.append(task)

        # Let them start
        await asyncio.sleep(0.1)

        # Cancel random tasks
        for _ in range(20):
            if tasks:
                task_to_cancel = random.choice(tasks)
                if not task_to_cancel.done():
                    task_to_cancel.cancel()
                    tasks.remove(task_to_cancel)

        # Wait for remaining tasks
        await asyncio.gather(*tasks, return_exceptions=True)
        await queue.close()

        # Verify system handled cancellations gracefully
        assert completed_operations > 20  # Some operations should complete
        assert cancelled_operations > 10  # Some should be cancelled
        assert queue.size == 0  # Queue should be empty

        logger.info(
            f"Completed: {completed_operations}, " f"Cancelled: {cancelled_operations}"
        )


@pytest.mark.asyncio
class TestIntegratedChaos:
    """Integrated chaos tests for multiple components."""

    async def test_event_bus_message_queue_integration(self):
        """Test event bus and message queue working together under chaos."""
        event_bus = EventBus("integrated-chaos")
        message_queue = AsyncMessageQueue()
        chaos = ChaosMonkey(failure_rate=0.2)

        processed_events = []
        processed_messages = []

        async def event_to_message_bridge(event: ChaosEvent):
            """Convert events to messages."""
            try:
                await chaos.maybe_fail("bridge")
                message = create_chaos_message(f"event-{event.data}")
                await message_queue.put(message)
            except Exception as e:
                logger.warning(f"Bridge failed: {e}")

        async def message_processor():
            """Process messages from queue."""
            while not message_queue.is_closed or message_queue.size > 0:
                try:
                    await chaos.maybe_fail("processor")
                    message = await message_queue.get(timeout=0.5)
                    processed_messages.append(message.content)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    logger.info("Message processor cancelled by chaos")
                    break
                except Exception as e:
                    logger.warning(f"Processor failed: {e}")
                    break

        # Setup
        event_bus.subscribe(ChaosEvent, event_to_message_bridge)
        processor_task = asyncio.create_task(message_processor())

        async with chaos_test_context(chaos, duration=3.0):
            # Generate events
            for i in range(100):
                try:
                    event = ChaosEvent(f"integrated-{i}")
                    await event_bus.publish(event)

                    # Track published events
                    processed_events.append(event.data)

                    # Random delays
                    if random.random() < 0.1:
                        await asyncio.sleep(random.uniform(0, 0.05))

                except Exception as e:
                    logger.warning(f"Event publish {i} failed: {e}")

            # Let processing finish
            await asyncio.sleep(1.0)

        # Cleanup
        await message_queue.close()
        try:
            await processor_task
        except asyncio.CancelledError:
            # Processor may be cancelled by chaos - this is expected
            pass
        await event_bus.close()

        # Verify integration worked despite chaos
        assert (
            len(processed_messages) >= 1
        )  # Should process at least one message despite chaos
        assert len(processed_events) > 80  # Should publish most events

        logger.info(
            f"Events: {len(processed_events)}, " f"Messages: {len(processed_messages)}"
        )


def run_chaos_tests():
    """Run all chaos tests."""
    import subprocess
    import sys

    # Run chaos tests with proper async support
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--tb=short", __file__],
        capture_output=True,
        text=True,
    )

    print("CHAOS TEST RESULTS:")
    print("=" * 50)
    print(result.stdout)

    if result.stderr:
        print("ERRORS:")
        print(result.stderr)

    return result.returncode == 0


if __name__ == "__main__":
    run_chaos_tests()

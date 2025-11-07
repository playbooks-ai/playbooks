"""
Comprehensive unit tests for AsyncMessageQueue implementation.

Tests cover:
- Basic put/get operations
- Predicate-based filtering
- Batch operations
- Priority queue functionality
- Timeout handling
- Cancellation safety
- Memory management
- Smart buffering
"""

import asyncio
import time

import pytest

from playbooks.agents.async_queue import AsyncMessageQueue
from playbooks.core.identifiers import AgentID, MeetingID
from playbooks.core.message import Message, MessageType


def create_test_message(
    content: str,
    sender_id: str = "test-sender",
    recipient_id: str = "test-recipient",
    meeting_id: str = None,
) -> Message:
    """Create a test message."""
    return Message(
        sender_id=AgentID.parse(sender_id),
        sender_klass="TestAgent",
        content=content,
        recipient_id=AgentID.parse(recipient_id),
        recipient_klass="TestAgent",
        message_type=MessageType.DIRECT,
        meeting_id=MeetingID.parse(meeting_id) if meeting_id else None,
    )


@pytest.mark.asyncio
class TestAsyncMessageQueue:
    """Test cases for AsyncMessageQueue."""

    async def test_basic_put_get(self):
        """Test basic put and get operations."""
        queue = AsyncMessageQueue()
        message = create_test_message("hello")

        # Put message
        await queue.put(message)
        assert queue.size == 1

        # Get message
        retrieved = await queue.get()
        assert retrieved.content == "hello"
        assert queue.size == 0

    async def test_predicate_filtering(self):
        """Test predicate-based message filtering."""
        queue = AsyncMessageQueue()

        # Add messages
        await queue.put(create_test_message("msg1", sender_id="agent1"))
        await queue.put(create_test_message("msg2", sender_id="agent2"))
        await queue.put(create_test_message("msg3", sender_id="agent1"))

        # Get message from specific agent (compare with AgentID)
        msg = await queue.get(lambda m: m.sender_id.id == "agent2")
        assert msg.content == "msg2"
        assert queue.size == 2

        # Get any remaining message
        msg = await queue.get()
        assert msg.content == "msg1"  # FIFO order

    async def test_get_with_timeout(self):
        """Test get operation with timeout."""
        queue = AsyncMessageQueue()

        start_time = time.time()
        with pytest.raises(asyncio.TimeoutError):
            await queue.get(timeout=0.1)

        elapsed = time.time() - start_time
        assert 0.09 <= elapsed <= 0.2  # Allow some tolerance

    async def test_get_batch(self):
        """Test batch message retrieval."""
        queue = AsyncMessageQueue()

        # Add multiple messages
        for i in range(5):
            await queue.put(create_test_message(f"msg{i}"))

        # Get batch of 3 messages
        batch = await queue.get_batch(max_messages=3, timeout=0.1)
        assert len(batch) == 3
        assert [m.content for m in batch] == ["msg0", "msg1", "msg2"]
        assert queue.size == 2

    async def test_get_batch_with_predicate(self):
        """Test batch retrieval with filtering."""
        queue = AsyncMessageQueue()

        # Add mixed messages
        await queue.put(create_test_message("keep1", sender_id="target"))
        await queue.put(create_test_message("skip1", sender_id="other"))
        await queue.put(create_test_message("keep2", sender_id="target"))
        await queue.put(create_test_message("skip2", sender_id="other"))

        # Get batch with predicate
        batch = await queue.get_batch(
            predicate=lambda m: m.sender_id.id == "target", max_messages=10, timeout=0.1
        )

        assert len(batch) == 2
        assert [m.content for m in batch] == ["keep1", "keep2"]
        assert queue.size == 2  # Other messages remain

    async def test_get_batch_timeout_behavior(self):
        """Test batch timeout with minimum messages."""
        queue = AsyncMessageQueue()

        # Add one message
        await queue.put(create_test_message("msg1"))

        # Try to get batch of 3 with timeout
        start_time = time.time()
        batch = await queue.get_batch(max_messages=3, min_messages=1, timeout=0.1)
        elapsed = time.time() - start_time

        # Should return immediately with 1 message
        assert len(batch) == 1
        assert elapsed < 0.05  # Should be very fast

    async def test_priority_message(self):
        """Test priority message handling."""
        queue = AsyncMessageQueue()

        # Add normal message
        await queue.put(create_test_message("normal"))

        # Add priority message
        await queue.put(create_test_message("urgent"), priority=True)

        # Priority message should come first
        msg = await queue.get()
        assert msg.content == "urgent"

        msg = await queue.get()
        assert msg.content == "normal"

    async def test_peek_operation(self):
        """Test peek without removing message."""
        queue = AsyncMessageQueue()
        await queue.put(create_test_message("peek-test"))

        # Peek should return message without removing
        peeked = await queue.peek()
        assert peeked.content == "peek-test"
        assert queue.size == 1

        # Get should return same message
        msg = await queue.get()
        assert msg.content == "peek-test"
        assert queue.size == 0

    async def test_remove_operation(self):
        """Test selective message removal."""
        queue = AsyncMessageQueue()

        # Add messages
        await queue.put(create_test_message("keep1"))
        await queue.put(create_test_message("remove1"))
        await queue.put(create_test_message("keep2"))
        await queue.put(create_test_message("remove2"))

        # Remove messages containing "remove"
        removed_count = await queue.remove(lambda m: "remove" in m.content)
        assert removed_count == 2
        assert queue.size == 2

        # Verify remaining messages
        msg1 = await queue.get()
        msg2 = await queue.get()
        assert {msg1.content, msg2.content} == {"keep1", "keep2"}

    async def test_clear_operation(self):
        """Test clearing all messages."""
        queue = AsyncMessageQueue()

        # Add messages
        for i in range(5):
            await queue.put(create_test_message(f"msg{i}"))

        assert queue.size == 5

        # Clear all
        cleared_count = await queue.clear()
        assert cleared_count == 5
        assert queue.size == 0

    async def test_concurrent_put_get(self):
        """Test concurrent put and get operations."""
        queue = AsyncMessageQueue()
        results = []

        async def producer():
            for i in range(10):
                await queue.put(create_test_message(f"msg{i}"))
                await asyncio.sleep(0.01)

        async def consumer():
            for _ in range(10):
                msg = await queue.get()
                results.append(msg.content)

        # Run concurrently
        await asyncio.gather(producer(), consumer())

        # Verify all messages received
        assert len(results) == 10
        assert all(f"msg{i}" in results for i in range(10))

    async def test_multiple_waiters(self):
        """Test multiple consumers waiting for messages."""
        queue = AsyncMessageQueue()
        results = []

        async def consumer(consumer_id: str):
            msg = await queue.get()
            results.append((consumer_id, msg.content))

        # Start multiple consumers
        consumers = [asyncio.create_task(consumer(f"c{i}")) for i in range(3)]

        # Give consumers time to start waiting
        await asyncio.sleep(0.01)

        # Send messages
        for i in range(3):
            await queue.put(create_test_message(f"msg{i}"))

        # Wait for all consumers
        await asyncio.gather(*consumers)

        # Verify all consumers got messages
        assert len(results) == 3
        consumer_ids = {r[0] for r in results}
        assert consumer_ids == {"c0", "c1", "c2"}

    async def test_queue_closing(self):
        """Test queue closing behavior."""
        queue = AsyncMessageQueue()

        # Add message before closing
        await queue.put(create_test_message("before-close"))

        # Close queue
        await queue.close()
        assert queue.is_closed

        # Should still be able to get existing messages
        msg = await queue.get()
        assert msg.content == "before-close"

        # Should raise when trying to get from empty closed queue
        with pytest.raises(RuntimeError, match="closed and empty"):
            await queue.get()

        # Should raise when trying to put to closed queue
        with pytest.raises(RuntimeError, match="closed queue"):
            await queue.put(create_test_message("after-close"))

    async def test_context_manager(self):
        """Test context manager usage."""
        messages_retrieved = []

        async with AsyncMessageQueue() as queue:
            await queue.put(create_test_message("ctx-test"))
            msg = await queue.get()
            messages_retrieved.append(msg.content)

        # Queue should be closed after context
        assert queue.is_closed
        assert messages_retrieved == ["ctx-test"]

    async def test_size_limits(self):
        """Test queue size limits."""
        queue = AsyncMessageQueue(max_size=2)

        # Add up to limit
        await queue.put(create_test_message("msg1"))
        await queue.put(create_test_message("msg2"))
        assert queue.size == 2
        assert queue.is_full

        # Adding more should work (deque handles overflow)
        await queue.put(create_test_message("msg3"))
        assert queue.size == 2  # Oldest message dropped

    async def test_cancellation_safety(self):
        """Test cancellation during get operations."""
        queue = AsyncMessageQueue()
        cancelled = False

        async def cancellable_get():
            nonlocal cancelled
            try:
                await queue.get(timeout=10)  # Long timeout
            except asyncio.CancelledError:
                cancelled = True
                raise

        # Start get operation
        task = asyncio.create_task(cancellable_get())
        await asyncio.sleep(0.01)  # Let it start waiting

        # Cancel the task
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert cancelled

        # Queue should still work after cancellation
        await queue.put(create_test_message("after-cancel"))
        msg = await queue.get()
        assert msg.content == "after-cancel"

    async def test_statistics(self):
        """Test queue statistics."""
        queue = AsyncMessageQueue()

        # Initial stats
        stats = queue.stats
        assert stats["size"] == 0
        assert stats["total_messages"] == 0
        assert stats["total_gets"] == 0

        # Add and retrieve messages
        await queue.put(create_test_message("msg1"))
        await queue.put(create_test_message("msg2"))
        _ = await queue.get()

        # Check updated stats
        stats = queue.stats
        assert stats["size"] == 1
        assert stats["total_messages"] == 2
        assert stats["total_gets"] == 1
        assert stats["uptime_seconds"] > 0

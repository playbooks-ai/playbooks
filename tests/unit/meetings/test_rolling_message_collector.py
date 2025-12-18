"""Tests for RollingMessageCollector message batching."""

import asyncio

import pytest

from playbooks.core.identifiers import AgentID, MeetingID
from playbooks.core.message import Message, MessageType
from playbooks.meetings.meeting_manager import RollingMessageCollector


class TestRollingMessageCollector:
    """Test the rolling message collector for batching meeting messages."""

    @pytest.mark.asyncio
    async def test_single_message_delivery_after_timeout(self):
        """Test that a single message is delivered after timeout expires."""
        delivered_messages = []

        async def delivery_callback(messages):
            delivered_messages.extend(messages)

        collector = RollingMessageCollector(timeout_seconds=0.1)
        collector.set_delivery_callback(delivery_callback)

        # Add a single message
        msg = Message(
            sender_id=AgentID("1000"),
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Test message",
            meeting_id=MeetingID("meeting-123"),
        )
        await collector.add_message(msg)

        # Wait for timeout to expire
        await asyncio.sleep(0.15)

        # Message should have been delivered
        assert len(delivered_messages) == 1
        assert delivered_messages[0].content == "Test message"

    @pytest.mark.asyncio
    async def test_multiple_messages_batched(self):
        """Test that multiple messages are batched together."""
        delivered_batches = []

        async def delivery_callback(messages):
            delivered_batches.append(messages.copy())

        collector = RollingMessageCollector(timeout_seconds=0.2)
        collector.set_delivery_callback(delivery_callback)

        # Add multiple messages rapidly
        for i in range(5):
            msg = Message(
                sender_id=AgentID("1000"),
                sender_klass="TestAgent",
                recipient_id=None,
                recipient_klass=None,
                message_type=MessageType.MEETING_BROADCAST,
                content=f"Message {i}",
                meeting_id=MeetingID("meeting-123"),
            )
            await collector.add_message(msg)
            await asyncio.sleep(0.05)  # Less than timeout

        # Wait for timeout to expire
        await asyncio.sleep(0.25)

        # All messages should be in a single batch
        assert len(delivered_batches) == 1
        assert len(delivered_batches[0]) == 5
        for i in range(5):
            assert delivered_batches[0][i].content == f"Message {i}"

    @pytest.mark.asyncio
    async def test_rolling_timeout_resets(self):
        """Test that timeout resets when new messages arrive."""
        delivered_batches = []

        async def delivery_callback(messages):
            delivered_batches.append(messages.copy())

        collector = RollingMessageCollector(timeout_seconds=0.15)
        collector.set_delivery_callback(delivery_callback)

        # Add first message
        msg1 = Message(
            sender_id=AgentID("1000"),
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Message 1",
            meeting_id=MeetingID("meeting-123"),
        )
        await collector.add_message(msg1)
        await asyncio.sleep(0.1)

        # Add second message (should reset timer)
        msg2 = Message(
            sender_id=AgentID("1000"),
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Message 2",
            meeting_id=MeetingID("meeting-123"),
        )
        await collector.add_message(msg2)
        await asyncio.sleep(0.1)

        # Add third message (should reset timer again)
        msg3 = Message(
            sender_id=AgentID("1000"),
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Message 3",
            meeting_id=MeetingID("meeting-123"),
        )
        await collector.add_message(msg3)

        # At this point, no messages should have been delivered yet
        assert len(delivered_batches) == 0

        # Wait for timeout to expire
        await asyncio.sleep(0.2)

        # All messages should be in a single batch
        assert len(delivered_batches) == 1
        assert len(delivered_batches[0]) == 3

    @pytest.mark.asyncio
    async def test_separate_batches_after_delivery(self):
        """Test that messages after delivery start a new batch."""
        delivered_batches = []

        async def delivery_callback(messages):
            delivered_batches.append(messages.copy())

        collector = RollingMessageCollector(timeout_seconds=0.1)
        collector.set_delivery_callback(delivery_callback)

        # First batch
        msg1 = Message(
            sender_id=AgentID("1000"),
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Batch 1 Message 1",
            meeting_id=MeetingID("meeting-123"),
        )
        await collector.add_message(msg1)

        # Wait for first batch to be delivered
        await asyncio.sleep(0.15)
        assert len(delivered_batches) == 1

        # Second batch
        msg2 = Message(
            sender_id=AgentID("1000"),
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Batch 2 Message 1",
            meeting_id=MeetingID("meeting-123"),
        )
        await collector.add_message(msg2)

        # Wait for second batch to be delivered
        await asyncio.sleep(0.15)

        # Should have two separate batches
        assert len(delivered_batches) == 2
        assert len(delivered_batches[0]) == 1
        assert delivered_batches[0][0].content == "Batch 1 Message 1"
        assert len(delivered_batches[1]) == 1
        assert delivered_batches[1][0].content == "Batch 2 Message 1"

    @pytest.mark.asyncio
    async def test_configurable_timeout(self):
        """Test that the timeout duration is configurable."""
        delivered_messages = []

        async def delivery_callback(messages):
            delivered_messages.extend(messages)

        # Use a longer timeout
        collector = RollingMessageCollector(timeout_seconds=0.3)
        collector.set_delivery_callback(delivery_callback)

        msg = Message(
            sender_id=AgentID("1000"),
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Test message",
            meeting_id=MeetingID("meeting-123"),
        )
        await collector.add_message(msg)

        # Check that message is NOT delivered before timeout
        await asyncio.sleep(0.2)
        assert len(delivered_messages) == 0

        # Wait for timeout to expire
        await asyncio.sleep(0.15)
        assert len(delivered_messages) == 1

    @pytest.mark.asyncio
    async def test_absolute_max_wait_prevents_starvation(self):
        """Test that absolute max wait prevents starvation when messages keep arriving."""
        delivered_batches = []

        async def delivery_callback(messages):
            delivered_batches.append(messages.copy())

        # Short rolling timeout but also short absolute max for testing
        collector = RollingMessageCollector(timeout_seconds=0.1, max_batch_wait=0.3)
        collector.set_delivery_callback(delivery_callback)

        # Continuously add messages every 0.08s (less than rolling timeout)
        # This would normally prevent delivery indefinitely
        for i in range(6):
            msg = Message(
                sender_id=AgentID("1000"),
                sender_klass="TestAgent",
                recipient_id=None,
                recipient_klass=None,
                message_type=MessageType.MEETING_BROADCAST,
                content=f"Message {i}",
                meeting_id=MeetingID("meeting-123"),
            )
            await collector.add_message(msg)
            await asyncio.sleep(0.08)  # Keep resetting timer

        # Even though we kept adding messages, the absolute max should have triggered
        # We expect at least one delivery by now (after ~0.48s total)
        assert len(delivered_batches) >= 1

        # First batch should have been forced out around the 0.3s mark
        # (around message 3 or 4, given 0.08s intervals)
        assert len(delivered_batches[0]) >= 3
        assert len(delivered_batches[0]) <= 5

    @pytest.mark.asyncio
    async def test_absolute_max_wait_resets_after_delivery(self):
        """Test that max wait timer resets after delivery, allowing new batches."""
        delivered_batches = []

        async def delivery_callback(messages):
            delivered_batches.append(messages.copy())

        collector = RollingMessageCollector(timeout_seconds=0.1, max_batch_wait=0.25)
        collector.set_delivery_callback(delivery_callback)

        # First burst: continuously add messages until max wait forces delivery
        for i in range(4):
            msg = Message(
                sender_id=AgentID("1000"),
                sender_klass="TestAgent",
                recipient_id=None,
                recipient_klass=None,
                message_type=MessageType.MEETING_BROADCAST,
                content=f"Batch 1 Message {i}",
                meeting_id=MeetingID("meeting-123"),
            )
            await collector.add_message(msg)
            await asyncio.sleep(0.08)

        # Wait to confirm batches were delivered
        await asyncio.sleep(0.15)
        # With timeout_seconds=0.1 and messages every 0.08s, expect 2 batches
        assert len(delivered_batches) == 2

        # Second burst: add more messages - should start a fresh batch
        for i in range(4):
            msg = Message(
                sender_id=AgentID("1000"),
                sender_klass="TestAgent",
                recipient_id=None,
                recipient_klass=None,
                message_type=MessageType.MEETING_BROADCAST,
                content=f"Batch 2 Message {i}",
                meeting_id=MeetingID("meeting-123"),
            )
            await collector.add_message(msg)
            await asyncio.sleep(0.08)

        # Second batch should also be delivered (may be split due to timing)
        await asyncio.sleep(0.15)
        assert len(delivered_batches) == 4  # Both bursts split due to timing

        # Verify messages went to correct batches
        # Batches may be split due to rolling timeout
        batch_1_messages = [
            m for batch in delivered_batches for m in batch if "Batch 1" in m.content
        ]
        batch_2_messages = [
            m for batch in delivered_batches for m in batch if "Batch 2" in m.content
        ]
        assert len(batch_1_messages) == 4
        assert len(batch_2_messages) == 4

    @pytest.mark.asyncio
    async def test_rolling_timeout_still_works_under_max_wait(self):
        """Test that rolling timeout still delivers quickly when under max wait."""
        delivered_batches = []

        async def delivery_callback(messages):
            delivered_batches.append(messages.copy())

        # Longer max wait, shorter rolling timeout
        collector = RollingMessageCollector(timeout_seconds=0.1, max_batch_wait=5.0)
        collector.set_delivery_callback(delivery_callback)

        # Add a couple messages with short intervals
        msg1 = Message(
            sender_id=AgentID("1000"),
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Message 1",
            meeting_id=MeetingID("meeting-123"),
        )
        await collector.add_message(msg1)
        await asyncio.sleep(0.05)

        msg2 = Message(
            sender_id=AgentID("1000"),
            sender_klass="TestAgent",
            recipient_id=None,
            recipient_klass=None,
            message_type=MessageType.MEETING_BROADCAST,
            content="Message 2",
            meeting_id=MeetingID("meeting-123"),
        )
        await collector.add_message(msg2)

        # Now stop sending messages - rolling timeout should trigger
        await asyncio.sleep(0.15)

        # Should deliver via rolling timeout (not max wait)
        assert len(delivered_batches) == 1
        assert len(delivered_batches[0]) == 2

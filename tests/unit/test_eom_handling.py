"""Test EOM (End of Message) handling in AsyncMessageQueue."""

import pytest
from playbooks.async_message_queue import AsyncMessageQueue
from playbooks.core.constants import EOM
from playbooks.core.message import Message, MessageType


@pytest.mark.asyncio
async def test_eom_stops_batch_collection():
    """Verify that EOM acts as a delimiter and stops message collection."""
    queue = AsyncMessageQueue()

    # Queue multiple messages with EOM markers
    await queue.put(
        Message(
            sender_id="human",
            sender_klass="human",
            content="Message 1",
            recipient_id="agent-1",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
    )
    await queue.put(
        Message(
            sender_id="human",
            sender_klass="human",
            content=EOM,
            recipient_id="agent-1",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
    )
    await queue.put(
        Message(
            sender_id="human",
            sender_klass="human",
            content="Message 2",
            recipient_id="agent-1",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
    )
    await queue.put(
        Message(
            sender_id="human",
            sender_klass="human",
            content=EOM,
            recipient_id="agent-1",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
    )
    await queue.put(
        Message(
            sender_id="human",
            sender_klass="human",
            content="Message 3",
            recipient_id="agent-1",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
    )
    await queue.put(
        Message(
            sender_id="human",
            sender_klass="human",
            content=EOM,
            recipient_id="agent-1",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
    )

    # Predicate that matches any message from human (including EOM)
    def predicate(msg):
        return msg.sender_id == "human"

    # First batch - should get only "Message 1" (stops at first EOM)
    batch1 = await queue.get_batch(
        predicate=predicate, timeout=0.1, min_messages=1, max_messages=100
    )

    assert len(batch1) == 1, f"Expected 1 message in batch 1, got {len(batch1)}"
    assert (
        batch1[0].content == "Message 1"
    ), f"Expected 'Message 1', got '{batch1[0].content}'"

    # Second batch - should get only "Message 2" (stops at second EOM)
    batch2 = await queue.get_batch(
        predicate=predicate, timeout=0.1, min_messages=1, max_messages=100
    )

    assert len(batch2) == 1, f"Expected 1 message in batch 2, got {len(batch2)}"
    assert (
        batch2[0].content == "Message 2"
    ), f"Expected 'Message 2', got '{batch2[0].content}'"

    # Third batch - should get only "Message 3" (stops at third EOM)
    batch3 = await queue.get_batch(
        predicate=predicate, timeout=0.1, min_messages=1, max_messages=100
    )

    assert len(batch3) == 1, f"Expected 1 message in batch 3, got {len(batch3)}"
    assert (
        batch3[0].content == "Message 3"
    ), f"Expected 'Message 3', got '{batch3[0].content}'"

    # Queue should be empty now
    assert queue.size == 0, f"Expected queue to be empty, but has {queue.size} messages"


@pytest.mark.asyncio
async def test_eom_consumed_from_queue():
    """Verify that EOM messages are consumed and not returned in batches."""
    queue = AsyncMessageQueue()

    # Queue message + EOM
    await queue.put(
        Message(
            sender_id="human",
            sender_klass="human",
            content="Test message",
            recipient_id="agent-1",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
    )
    await queue.put(
        Message(
            sender_id="human",
            sender_klass="human",
            content=EOM,
            recipient_id="agent-1",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
    )

    def predicate(msg):
        return msg.sender_id == "human"

    # Get batch
    batch = await queue.get_batch(
        predicate=predicate, timeout=0.1, min_messages=1, max_messages=100
    )

    # Should only have the actual message, not EOM
    assert len(batch) == 1
    assert batch[0].content == "Test message"

    # EOM should have been consumed
    assert queue.size == 0


@pytest.mark.asyncio
async def test_multiple_messages_before_eom():
    """Verify that multiple messages before EOM are all collected."""
    queue = AsyncMessageQueue()

    # Queue multiple messages before EOM
    for i in range(1, 4):
        await queue.put(
            Message(
                sender_id="human",
                sender_klass="human",
                content=f"Message {i}",
                recipient_id="agent-1",
                recipient_klass="TestAgent",
                message_type=MessageType.DIRECT,
                meeting_id=None,
            )
        )

    await queue.put(
        Message(
            sender_id="human",
            sender_klass="human",
            content=EOM,
            recipient_id="agent-1",
            recipient_klass="TestAgent",
            message_type=MessageType.DIRECT,
            meeting_id=None,
        )
    )

    def predicate(msg):
        return msg.sender_id == "human"

    # Get batch - should get all 3 messages
    batch = await queue.get_batch(
        predicate=predicate, timeout=0.1, min_messages=1, max_messages=100
    )

    assert len(batch) == 3, f"Expected 3 messages, got {len(batch)}"
    assert batch[0].content == "Message 1"
    assert batch[1].content == "Message 2"
    assert batch[2].content == "Message 3"
    assert queue.size == 0

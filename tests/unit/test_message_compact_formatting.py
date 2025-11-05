"""Test compact message formatting in LLM context."""

from playbooks.message import Message, MessageType
from playbooks.playbook_call import PlaybookCall


def test_message_compact_str():
    """Test that Message.to_compact_str() produces compact format."""
    msg = Message(
        sender_id="1000",
        sender_klass="StoryTeller",
        recipient_id="1001",
        recipient_klass="CharacterCreator",
        message_type=MessageType.DIRECT,
        content="Hi! Could you please create a new character for a story I'm crafting?",
        meeting_id=None,
    )

    compact = msg.to_compact_str()

    # Check format: "SenderKlass(sender_id) → RecipientKlass(recipient_id): content"
    assert "StoryTeller(1000)" in compact
    assert "CharacterCreator(1001)" in compact
    assert "Hi! Could you please create" in compact
    assert " → " in compact


def test_message_compact_str_human():
    """Test compact formatting for messages to/from human."""
    msg = Message(
        sender_id="1000",
        sender_klass="StoryTeller",
        recipient_id="human",
        recipient_klass="User",
        message_type=MessageType.DIRECT,
        content="Hello!",
        meeting_id=None,
    )

    compact = msg.to_compact_str()

    assert "StoryTeller(1000)" in compact
    assert "StoryTeller(1000) → User:" in compact
    assert "Hello!" in compact


def test_message_compact_str_from_human():
    """Test compact formatting for messages from human to agent."""
    msg = Message(
        sender_id="human",
        sender_klass="User",
        recipient_id="1000",
        recipient_klass="Assistant",
        message_type=MessageType.DIRECT,
        content="Help me with this task",
        meeting_id=None,
    )

    compact = msg.to_compact_str()

    assert "User → Assistant(1000):" in compact
    assert "Help me with this task" in compact


def test_message_compact_str_truncation():
    """Test that very long messages are truncated."""
    long_content = "a" * 200
    msg = Message(
        sender_id="1000",
        sender_klass="StoryTeller",
        recipient_id="1001",
        recipient_klass="CharacterCreator",
        message_type=MessageType.DIRECT,
        content=long_content,
        meeting_id=None,
    )

    compact = msg.to_compact_str()

    # Should be truncated to 100 chars
    assert len(compact) < len(long_content) + 100  # Account for metadata
    assert "..." in compact


def test_playbook_call_with_messages():
    """Test that PlaybookCall formats messages compactly."""
    messages = [
        Message(
            sender_id="1000",
            sender_klass="StoryTeller",
            recipient_id="1001",
            recipient_klass="CharacterCreator",
            message_type=MessageType.DIRECT,
            content="Hi! Could you please create a new character?",
            meeting_id=None,
        )
    ]

    call = PlaybookCall("ProcessMessages", args=[messages], kwargs={})
    call_str = str(call)

    # Should use compact format, not verbose Python repr
    assert "ProcessMessages([" in call_str
    assert "StoryTeller(1000) → CharacterCreator(1001)" in call_str
    assert "Hi! Could you please create" in call_str

    # Should NOT contain verbose repr elements
    assert "MessageType.DIRECT" not in call_str
    assert "sender_klass=" not in call_str
    assert "uuid.UUID" not in call_str
    assert "datetime.datetime" not in call_str


def test_playbook_call_with_multiple_messages():
    """Test that PlaybookCall formats multiple messages compactly."""
    messages = [
        Message(
            sender_id="1000",
            sender_klass="StoryTeller",
            recipient_id="1001",
            recipient_klass="CharacterCreator",
            message_type=MessageType.DIRECT,
            content="Message 1",
            meeting_id=None,
        ),
        Message(
            sender_id="1002",
            sender_klass="WorldBuilder",
            recipient_id="human",
            recipient_klass="User",
            message_type=MessageType.DIRECT,
            content="Message 2",
            meeting_id=None,
        ),
    ]

    call = PlaybookCall("ProcessMessages", args=[messages], kwargs={})
    call_str = str(call)

    # Both messages should be formatted compactly
    assert "StoryTeller(1000) → CharacterCreator(1001): Message 1" in call_str
    assert "WorldBuilder(1002) → User: Message 2" in call_str

    # Should NOT contain verbose repr elements
    assert "MessageType" not in call_str
    assert "sender_id=" not in call_str

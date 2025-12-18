"""Tests for the semantic LLMMessage subclasses."""

import time

from playbooks.core.enums import LLMMessageRole, LLMMessageType
from playbooks.llm.messages import (
    AgentCommunicationLLMMessage,
    AgentInfoLLMMessage,
    AssistantResponseLLMMessage,
    ExecutionResultLLMMessage,
    FileLoadLLMMessage,
    LLMMessage,
    MeetingLLMMessage,
    OtherAgentInfoLLMMessage,
    PlaybookImplementationLLMMessage,
    SessionLogLLMMessage,
    SystemPromptLLMMessage,
    TriggerInstructionsLLMMessage,
    UserInputLLMMessage,
)
from playbooks.llm.messages.timestamp import get_timestamp, reset_timestamp_manager


class TestLLMMessageBase:
    """Test the updated base LLMMessage class."""

    def test_base_message_creation(self):
        """Test creating a base message."""
        msg = LLMMessage("Hello", LLMMessageRole.USER)
        assert msg.content == "Hello"
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.USER_INPUT

    def test_to_full_message_with_cache(self):
        """Test converting message to dictionary with caching enabled."""
        msg = LLMMessage("Test", LLMMessageRole.ASSISTANT)
        result = msg.to_full_message(is_cached=True)

        assert result["role"] == LLMMessageRole.ASSISTANT
        assert result["type"] == LLMMessageType.USER_INPUT
        assert result["content"] == "Test"
        assert result["cache_control"] == {"type": "ephemeral"}

    def test_to_full_message_without_cache(self):
        """Test converting message to dictionary without caching."""
        msg = LLMMessage("Test", LLMMessageRole.USER)
        result = msg.to_full_message(is_cached=False)

        assert result["role"] == LLMMessageRole.USER
        assert result["type"] == LLMMessageType.USER_INPUT
        assert result["content"] == "Test"
        assert "cache_control" not in result

    def test_repr(self):
        """Test string representation."""
        msg = LLMMessage("Test content", LLMMessageRole.SYSTEM)
        repr_str = repr(msg)

        assert "LLMMessage" in repr_str
        assert "role=LLMMessageRole.SYSTEM" in repr_str
        assert "content_length=12" in repr_str
        assert "timestamp=" in repr_str
        assert "cached" not in repr_str.lower()

    def test_equality(self):
        """Test equality comparison."""
        msg1 = LLMMessage("Hello", LLMMessageRole.USER)
        msg2 = LLMMessage("Hello", LLMMessageRole.USER)
        msg3 = LLMMessage("Goodbye", LLMMessageRole.USER)

        assert msg1 == msg2
        assert msg1 != msg3

    def test_timestamp_field(self):
        """Test that timestamp is set automatically and can be provided."""
        # Reset timestamp manager for consistent testing
        reset_timestamp_manager()
        time.sleep(0.01)  # Small delay to ensure timestamp advances

        # Test automatic timestamp
        before_ts = get_timestamp()
        msg1 = LLMMessage("Test", LLMMessageRole.USER)
        after_ts = get_timestamp()

        assert hasattr(msg1, "timestamp")
        assert isinstance(msg1.timestamp, int)
        assert before_ts <= msg1.timestamp <= after_ts

        # Test custom timestamp
        custom_timestamp = 12345
        msg2 = LLMMessage("Test", LLMMessageRole.USER, timestamp=custom_timestamp)
        assert msg2.timestamp == custom_timestamp
        assert isinstance(msg2.timestamp, int)


class TestPlaybookImplementationLLMMessage:
    """Test the PlaybookImplementationLLMMessage class."""

    def test_creation(self):
        """Test creating a playbook implementation message."""
        content = "# Test Playbook\n\nSome markdown content"
        msg = PlaybookImplementationLLMMessage(content, "test_playbook")

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.PLAYBOOK_IMPLEMENTATION
        assert msg.playbook_name == "test_playbook"

    def test_to_full_message(self):
        """Test converting to dictionary."""
        msg = PlaybookImplementationLLMMessage("# Playbook", "test")
        result = msg.to_full_message()

        assert result["role"] == LLMMessageRole.USER
        assert result["content"] == "# Playbook"
        # Note: caching is now applied at call stack frame level, not message type level


class TestAssistantResponseLLMMessage:
    """Test the AssistantResponseLLMMessage class."""

    def test_creation(self):
        """Test creating an LLM response message."""
        content = "I understand your request."
        msg = AssistantResponseLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.ASSISTANT
        assert msg.type == LLMMessageType.ASSISTANT_RESPONSE


class TestMeetingLLMMessage:
    """Test the MeetingLLMMessage class."""

    def test_creation_with_meeting_id(self):
        """Test creating a meeting message with meeting ID."""
        content = "Meeting invitation sent"
        msg = MeetingLLMMessage(content, meeting_id="meeting-123")

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.MEETING_MESSAGE
        assert msg.meeting_id == "meeting-123"

    def test_creation_without_meeting_id(self):
        """Test that creating a meeting message without meeting ID raises TypeError."""
        content = "General meeting update"
        try:
            MeetingLLMMessage(content)
            assert False, "Should have raised TypeError"
        except TypeError:
            pass  # Expected - missing required argument


class TestAgentCommunicationLLMMessage:
    """Test the AgentCommunicationLLMMessage class."""

    def test_creation_with_agents(self):
        """Test creating an agent communication message with agent IDs."""
        content = "Message sent to agent"
        msg = AgentCommunicationLLMMessage(
            content, sender_agent="agent-1", target_agent="agent-2"
        )

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.AGENT_COMMUNICATION
        assert msg.sender_agent == "agent-1"
        assert msg.target_agent == "agent-2"

    def test_creation_without_agents(self):
        """Test that creating agent communication without agents raises ValueError."""
        content = "General communication"
        try:
            AgentCommunicationLLMMessage(content)
            assert False, "Should have raised ValueError"
        except TypeError:
            pass  # Expected - missing required arguments


class TestFileLoadLLMMessage:
    """Test the FileLoadLLMMessage class."""

    def test_creation_with_file_path(self):
        """Test creating a file load message with file path."""
        content = "File contents here"
        msg = FileLoadLLMMessage(content, file_path="/path/to/file.txt")

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.FILE_LOAD
        assert msg.file_path == "/path/to/file.txt"

    def test_creation_without_file_path(self):
        """Test that creating file load message without file path raises TypeError."""
        content = "File operation result"
        try:
            FileLoadLLMMessage(content)
            assert False, "Should have raised TypeError"
        except TypeError:
            pass  # Expected - missing required argument


class TestExecutionResultLLMMessage:
    """Test the ExecutionResultLLMMessage class."""

    def test_creation_success(self):
        """Test creating a successful execution result message."""
        content = "Playbook executed successfully"
        msg = ExecutionResultLLMMessage(
            content, playbook_name="test_playbook", success=True
        )

        assert msg.content == content
        assert (
            msg.role == LLMMessageRole.USER
        )  # Fixed: execution results come from assistant
        assert msg.type == LLMMessageType.EXECUTION_RESULT
        assert msg.playbook_name == "test_playbook"
        assert msg.success is True

    def test_creation_failure(self):
        """Test creating a failed execution result message."""
        content = "Playbook execution failed"
        msg = ExecutionResultLLMMessage(
            content, playbook_name="test_playbook", success=False
        )

        assert msg.success is False

    def test_creation_minimal(self):
        """Test that creating execution result without playbook name raises TypeError."""
        content = "Result"
        try:
            ExecutionResultLLMMessage(content)
            assert False, "Should have raised TypeError"
        except TypeError:
            pass  # Expected - missing required argument


class TestSessionLogLLMMessage:
    """Test the SessionLogLLMMessage class."""

    def test_creation_with_log_level(self):
        """Test creating a session log message with log level."""
        content = "Debug information"
        msg = SessionLogLLMMessage(content, log_level="DEBUG")

        assert msg.content == content
        assert (
            msg.role == LLMMessageRole.SYSTEM
        )  # Fixed: logs are system-level information
        assert msg.type == LLMMessageType.SESSION_LOG
        assert msg.log_level == "DEBUG"

    def test_creation_default_log_level(self):
        """Test creating a session log message with default log level."""
        content = "Information"
        msg = SessionLogLLMMessage(content)

        assert msg.content == content
        assert msg.log_level == "INFO"  # Default


class TestSystemPromptLLMMessage:
    """Test the SystemPromptLLMMessage class."""

    def test_creation(self):
        """Test creating a system prompt message."""
        msg = SystemPromptLLMMessage()

        assert msg.content is not None  # Content is loaded from file
        assert msg.role == LLMMessageRole.SYSTEM
        assert msg.type == LLMMessageType.SYSTEM_PROMPT


class TestUserInputLLMMessage:
    """Test the UserInputLLMMessage class."""

    def test_creation(self):
        """Test creating a user input message."""
        content = "Please execute this task"
        msg = UserInputLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.USER_INPUT


class TestTriggerInstructionsLLMMessage:
    """Test the TriggerInstructionsLLMMessage class."""

    def test_creation(self):
        """Test creating a trigger instructions message."""
        content = "Available triggers: trigger1, trigger2"
        msg = TriggerInstructionsLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.TRIGGER_INSTRUCTIONS


class TestAgentInfoLLMMessage:
    """Test the AgentInfoLLMMessage class."""

    def test_creation(self):
        """Test creating an agent info message."""
        content = "Current agent: TestAgent"
        msg = AgentInfoLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.AGENT_INFO


class TestOtherAgentInfoLLMMessage:
    """Test the OtherAgentInfoLLMMessage class."""

    def test_creation(self):
        """Test creating an other agent info message."""
        content = "Other agents: Agent1, Agent2"
        msg = OtherAgentInfoLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.OTHER_AGENT_INFO

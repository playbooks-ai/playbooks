"""Tests for the semantic LLMMessage subclasses."""

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


class TestLLMMessageBase:
    """Test the updated base LLMMessage class."""

    def test_base_message_with_caching(self):
        """Test creating a base message with caching."""
        msg = LLMMessage("Hello", LLMMessageRole.USER, cached=True)
        assert msg.content == "Hello"
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.USER_INPUT
        assert msg.cached is True

    def test_base_message_without_caching(self):
        """Test creating a base message without caching."""
        msg = LLMMessage("Hello", LLMMessageRole.USER, cached=False)
        assert msg.content == "Hello"
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.USER_INPUT
        assert msg.cached is False

    def test_to_full_message_with_cache(self):
        """Test converting cached message to dictionary."""
        msg = LLMMessage("Test", LLMMessageRole.ASSISTANT, cached=True)
        result = msg.to_full_message()

        assert result == {
            "role": LLMMessageRole.ASSISTANT,
            "type": LLMMessageType.USER_INPUT,
            "content": "Test",
            "cache_control": {"type": "ephemeral"},
        }

    def test_to_full_message_without_cache(self):
        """Test converting uncached message to dictionary."""
        msg = LLMMessage("Test", LLMMessageRole.USER, cached=False)
        result = msg.to_full_message()

        assert result == {
            "role": LLMMessageRole.USER,
            "type": LLMMessageType.USER_INPUT,
            "content": "Test",
        }
        assert "cache_control" not in result

    def test_repr_with_cache(self):
        """Test string representation with caching."""
        msg = LLMMessage("Test content", LLMMessageRole.SYSTEM, cached=True)
        repr_str = repr(msg)

        assert "LLMMessage" in repr_str
        assert "role=LLMMessageRole.SYSTEM" in repr_str
        assert "content_length=12" in repr_str
        assert "cached=True" in repr_str

    def test_repr_without_cache(self):
        """Test string representation without caching."""
        msg = LLMMessage("Test", LLMMessageRole.USER, cached=False)
        repr_str = repr(msg)

        assert "LLMMessage" in repr_str
        assert "cached=True" not in repr_str

    def test_equality_with_cache(self):
        """Test equality comparison including cache attribute."""
        msg1 = LLMMessage("Hello", LLMMessageRole.USER, cached=True)
        msg2 = LLMMessage("Hello", LLMMessageRole.USER, cached=True)
        msg3 = LLMMessage("Hello", LLMMessageRole.USER, cached=False)

        assert msg1 == msg2
        assert msg1 != msg3  # Different cache values


class TestPlaybookImplementationLLMMessage:
    """Test the PlaybookImplementationLLMMessage class."""

    def test_creation(self):
        """Test creating a playbook implementation message."""
        content = "# Test Playbook\n\nSome markdown content"
        msg = PlaybookImplementationLLMMessage(content, "test_playbook")

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.PLAYBOOK_IMPLEMENTATION
        assert msg.cached is True  # Should be cached by default
        assert msg.playbook_name == "test_playbook"

    def test_to_full_message(self):
        """Test converting to dictionary."""
        msg = PlaybookImplementationLLMMessage("# Playbook", "test")
        result = msg.to_full_message()

        assert result["role"] == LLMMessageRole.USER
        assert result["content"] == "# Playbook"
        assert "cache_control" in result  # Should be cached


class TestAssistantResponseLLMMessage:
    """Test the AssistantResponseLLMMessage class."""

    def test_creation(self):
        """Test creating an LLM response message."""
        content = "I understand your request."
        msg = AssistantResponseLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.ASSISTANT
        assert msg.type == LLMMessageType.ASSISTANT_RESPONSE
        assert msg.cached is True  # Should be cached by default


class TestMeetingLLMMessage:
    """Test the MeetingLLMMessage class."""

    def test_creation_with_meeting_id(self):
        """Test creating a meeting message with meeting ID."""
        content = "Meeting invitation sent"
        msg = MeetingLLMMessage(content, meeting_id="meeting-123")

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.MEETING_MESSAGE
        assert msg.cached is False  # Should not be cached by default
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
        assert msg.cached is False  # Should not be cached by default
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
        assert msg.cached is False  # Should not be cached by default
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
        assert msg.cached is False  # Should not be cached by default
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
        assert msg.cached is False  # Should not be cached by default
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
        content = "You are a helpful assistant."
        msg = SystemPromptLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.SYSTEM
        assert msg.type == LLMMessageType.SYSTEM_PROMPT
        assert msg.cached is True  # Should be cached by default


class TestUserInputLLMMessage:
    """Test the UserInputLLMMessage class."""

    def test_creation_cached(self):
        """Test creating a cached user instruction message."""
        content = "Please execute this task"
        msg = UserInputLLMMessage(content, cached=True)

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.USER_INPUT
        assert msg.cached is True

    def test_creation_uncached(self):
        """Test creating an uncached user instruction message."""
        content = "Quick query"
        msg = UserInputLLMMessage(content, cached=False)

        assert msg.content == content
        assert msg.cached is False

    def test_creation_default(self):
        """Test creating a user instruction with default caching."""
        content = "Default instruction"
        msg = UserInputLLMMessage(content)

        assert msg.content == content
        assert msg.cached is False  # Default


class TestTriggerInstructionsLLMMessage:
    """Test the TriggerInstructionsLLMMessage class."""

    def test_creation(self):
        """Test creating a trigger instructions message."""
        content = "Available triggers: trigger1, trigger2"
        msg = TriggerInstructionsLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.TRIGGER_INSTRUCTIONS
        assert msg.cached is True  # Should be cached by default


class TestAgentInfoLLMMessage:
    """Test the AgentInfoLLMMessage class."""

    def test_creation(self):
        """Test creating an agent info message."""
        content = "Current agent: TestAgent"
        msg = AgentInfoLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.AGENT_INFO
        assert msg.cached is True  # Should be cached by default


class TestOtherAgentInfoLLMMessage:
    """Test the OtherAgentInfoLLMMessage class."""

    def test_creation(self):
        """Test creating an other agent info message."""
        content = "Other agents: Agent1, Agent2"
        msg = OtherAgentInfoLLMMessage(content)

        assert msg.content == content
        assert msg.role == LLMMessageRole.USER
        assert msg.type == LLMMessageType.OTHER_AGENT_INFO
        assert msg.cached is True  # Should be cached by default

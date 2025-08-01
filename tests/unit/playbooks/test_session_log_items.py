"""Comprehensive test suite for session_log_items.py"""

from datetime import datetime

from playbooks.session_log_items import (
    SessionLogItemBase,
    SessionLogItemPlaybookStart,
    SessionLogItemPlaybookEnd,
    SessionLogItemLLMRequest,
    SessionLogItemLLMResponse,
    SessionLogItemStepExecution,
    SessionLogItemVariableUpdate,
    SessionLogItemAgentMessage,
    SessionLogItemError,
    SessionLogItemDebug,
)


class TestSessionLogItemBase:
    """Test the base SessionLogItem class."""

    def test_item_type_property(self):
        """Test that item_type property correctly extracts class name."""

        # Create a concrete implementation for testing
        class SessionLogItemTestType(SessionLogItemBase):
            def to_log_full(self) -> str:
                return "test"

            def to_log_compact(self) -> str:
                return "test"

            def to_log_minimal(self) -> str:
                return "test"

        timestamp = datetime.now()
        item = SessionLogItemTestType(
            timestamp=timestamp, agent_id="test-agent", agent_klass="TestAgent"
        )

        assert item.item_type == "testtype"

    def test_to_metadata_base_fields(self):
        """Test that base metadata contains required fields."""

        class SessionLogItemTestType(SessionLogItemBase):
            def to_log_full(self) -> str:
                return "test"

            def to_log_compact(self) -> str:
                return "test"

            def to_log_minimal(self) -> str:
                return "test"

        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        item = SessionLogItemTestType(
            timestamp=timestamp, agent_id="agent-123", agent_klass="AIAgent"
        )

        metadata = item.to_metadata()

        assert metadata["type"] == "testtype"
        assert metadata["timestamp"] == "2024-01-15T10:30:45"
        assert metadata["agent_id"] == "agent-123"
        assert metadata["agent_klass"] == "AIAgent"

    def test_timestamp_formatting(self):
        """Test timestamp formatting in metadata."""

        class SessionLogItemTestType(SessionLogItemBase):
            def to_log_full(self) -> str:
                return "test"

            def to_log_compact(self) -> str:
                return "test"

            def to_log_minimal(self) -> str:
                return "test"

        # Test with microseconds
        timestamp = datetime(2024, 1, 15, 10, 30, 45, 123456)
        item = SessionLogItemTestType(
            timestamp=timestamp, agent_id="test-agent", agent_klass="TestAgent"
        )

        metadata = item.to_metadata()
        assert metadata["timestamp"] == "2024-01-15T10:30:45.123456"


class TestSessionLogItemPlaybookStart:
    """Test SessionLogItemPlaybookStart class."""

    def test_creation_minimal(self):
        """Test creating PlaybookStart with minimal fields."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookStart(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
        )

        assert item.playbook_name == "test_playbook"
        assert item.playbook_id is None
        assert item.parent_playbook is None

    def test_creation_full(self):
        """Test creating PlaybookStart with all fields."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookStart(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
            playbook_id="pb-123",
            parent_playbook="parent_pb",
        )

        assert item.playbook_name == "test_playbook"
        assert item.playbook_id == "pb-123"
        assert item.parent_playbook == "parent_pb"

    def test_to_log_full(self):
        """Test full log format."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookStart(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="my_awesome_playbook",
        )

        assert item.to_log_full() == "▶ Starting playbook: my_awesome_playbook"

    def test_to_log_compact(self):
        """Test compact log format."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookStart(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="my_playbook",
        )

        assert item.to_log_compact() == "▶ my_playbook"

    def test_to_log_minimal(self):
        """Test minimal log format."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookStart(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test",
        )

        assert item.to_log_minimal() == "▶"

    def test_to_metadata(self):
        """Test metadata conversion."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        item = SessionLogItemPlaybookStart(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
            playbook_id="pb-123",
            parent_playbook="parent_pb",
        )

        metadata = item.to_metadata()

        # Check base fields
        assert metadata["type"] == "playbookstart"
        assert metadata["timestamp"] == "2024-01-15T10:30:45"
        assert metadata["agent_id"] == "agent-1"
        assert metadata["agent_klass"] == "AIAgent"

        # Check specific fields
        assert metadata["playbook_name"] == "test_playbook"
        assert metadata["playbook_id"] == "pb-123"
        assert metadata["parent_playbook"] == "parent_pb"

    def test_to_metadata_with_none_values(self):
        """Test metadata conversion with None values."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookStart(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
        )

        metadata = item.to_metadata()

        assert metadata["playbook_name"] == "test_playbook"
        assert metadata["playbook_id"] is None
        assert metadata["parent_playbook"] is None


class TestSessionLogItemPlaybookEnd:
    """Test SessionLogItemPlaybookEnd class."""

    def test_creation_minimal(self):
        """Test creating PlaybookEnd with minimal fields."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
        )

        assert item.playbook_name == "test_playbook"
        assert item.playbook_id is None
        assert item.return_value is None
        assert item.execution_time_ms is None
        assert item.success is True
        assert item.error is None

    def test_creation_with_success_and_return_value(self):
        """Test creating PlaybookEnd with success and return value."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
            return_value="success_result",
            execution_time_ms=1500,
            success=True,
        )

        assert item.return_value == "success_result"
        assert item.execution_time_ms == 1500
        assert item.success is True

    def test_creation_with_error(self):
        """Test creating PlaybookEnd with error."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
            success=False,
            error="Something went wrong",
        )

        assert item.success is False
        assert item.error == "Something went wrong"

    def test_to_log_full_success_with_return_value(self):
        """Test full log format for successful execution with return value."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
            return_value="result_value",
            execution_time_ms=1000,
            success=True,
        )

        expected = "✓ Finished playbook: test_playbook (1000ms) → result_value"
        assert item.to_log_full() == expected

    def test_to_log_full_success_without_return_value(self):
        """Test full log format for successful execution without return value."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
            execution_time_ms=500,
            success=True,
        )

        expected = "✓ Finished playbook: test_playbook (500ms)"
        assert item.to_log_full() == expected

    def test_to_log_full_error(self):
        """Test full log format for failed execution."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
            success=False,
            error="Runtime error occurred",
        )

        expected = "✗ Finished playbook: test_playbook - Error: Runtime error occurred"
        assert item.to_log_full() == expected

    def test_to_log_compact_success(self):
        """Test compact log format for success."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="my_playbook",
            success=True,
        )

        assert item.to_log_compact() == "✓ my_playbook"

    def test_to_log_compact_failure(self):
        """Test compact log format for failure."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="my_playbook",
            success=False,
        )

        assert item.to_log_compact() == "✗ my_playbook"

    def test_to_log_minimal_success(self):
        """Test minimal log format for success."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test",
            success=True,
        )

        assert item.to_log_minimal() == "✓"

    def test_to_log_minimal_failure(self):
        """Test minimal log format for failure."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test",
            success=False,
        )

        assert item.to_log_minimal() == "✗"

    def test_to_metadata(self):
        """Test metadata conversion."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
            playbook_id="pb-123",
            return_value={"result": "success"},
            execution_time_ms=2000,
            success=True,
        )

        metadata = item.to_metadata()

        assert metadata["type"] == "playbookend"
        assert metadata["playbook_name"] == "test_playbook"
        assert metadata["playbook_id"] == "pb-123"
        assert metadata["return_value"] == "{'result': 'success'}"
        assert metadata["execution_time_ms"] == 2000
        assert metadata["success"] is True
        assert metadata["error"] is None

    def test_to_metadata_with_none_return_value(self):
        """Test metadata conversion with None return value."""
        timestamp = datetime.now()
        item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="test_playbook",
        )

        metadata = item.to_metadata()
        assert metadata["return_value"] is None


class TestSessionLogItemLLMRequest:
    """Test SessionLogItemLLMRequest class."""

    def test_creation_minimal(self):
        """Test creating LLMRequest with minimal fields."""
        timestamp = datetime.now()
        messages = [{"role": "user", "content": "Hello"}]

        item = SessionLogItemLLMRequest(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            messages=messages,
        )

        assert item.model == "gpt-4"
        assert item.messages == messages
        assert item.temperature is None
        assert item.max_tokens is None

    def test_creation_full(self):
        """Test creating LLMRequest with all fields."""
        timestamp = datetime.now()
        messages = [{"role": "user", "content": "Hello"}]

        item = SessionLogItemLLMRequest(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        assert item.temperature == 0.7
        assert item.max_tokens == 1000

    def test_to_log_full(self):
        """Test full log format."""
        timestamp = datetime.now()
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        item = SessionLogItemLLMRequest(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4-turbo",
            messages=messages,
        )

        expected = "🤖 LLM Request to gpt-4-turbo (3 messages)"
        assert item.to_log_full() == expected

    def test_to_log_compact(self):
        """Test compact log format."""
        timestamp = datetime.now()
        messages = [{"role": "user", "content": "Hello"}]

        item = SessionLogItemLLMRequest(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-3.5-turbo",
            messages=messages,
        )

        assert item.to_log_compact() == "🤖 gpt-3.5-turbo"

    def test_to_log_minimal(self):
        """Test minimal log format."""
        timestamp = datetime.now()
        item = SessionLogItemLLMRequest(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            messages=[],
        )

        assert item.to_log_minimal() == "🤖"

    def test_to_metadata(self):
        """Test metadata conversion."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        messages = [{"role": "user", "content": "Test message"}]

        item = SessionLogItemLLMRequest(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            messages=messages,
            temperature=0.5,
            max_tokens=2000,
        )

        metadata = item.to_metadata()

        assert metadata["type"] == "llmrequest"
        assert metadata["model"] == "gpt-4"
        assert metadata["messages"] == messages
        assert metadata["temperature"] == 0.5
        assert metadata["max_tokens"] == 2000


class TestSessionLogItemLLMResponse:
    """Test SessionLogItemLLMResponse class."""

    def test_creation_minimal(self):
        """Test creating LLMResponse with minimal fields."""
        timestamp = datetime.now()

        item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content="Hello! How can I help you?",
        )

        assert item.model == "gpt-4"
        assert item.content == "Hello! How can I help you?"
        assert item.usage is None
        assert item.response_time_ms is None

    def test_creation_full(self):
        """Test creating LLMResponse with all fields."""
        timestamp = datetime.now()
        usage = {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75}

        item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content="Response content",
            usage=usage,
            response_time_ms=1500,
        )

        assert item.usage == usage
        assert item.response_time_ms == 1500

    def test_to_log_full_short_content(self):
        """Test full log format with short content."""
        timestamp = datetime.now()
        usage = {"total_tokens": 100}

        item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content="Short response",
            usage=usage,
            response_time_ms=800,
        )

        expected = "💬 LLM Response from gpt-4 (800ms) - Tokens: 100\nShort response"
        assert item.to_log_full() == expected

    def test_to_log_full_long_content(self):
        """Test full log format with long content (truncated)."""
        timestamp = datetime.now()
        long_content = "A" * 250  # 250 characters

        item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content=long_content,
        )

        result = item.to_log_full()
        assert result.startswith("💬 LLM Response from gpt-4")
        assert result.endswith("...")
        assert "A" * 200 in result  # Should contain first 200 characters

    def test_to_log_full_without_usage_and_time(self):
        """Test full log format without usage and response time."""
        timestamp = datetime.now()

        item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content="Response without usage",
        )

        expected = "💬 LLM Response from gpt-4\nResponse without usage"
        assert item.to_log_full() == expected

    def test_to_log_compact(self):
        """Test compact log format."""
        timestamp = datetime.now()
        content = "This is a response that should be truncated after 50 characters"

        item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content=content,
        )

        result = item.to_log_compact()
        assert result.startswith("💬 ")
        assert result.endswith("...")
        assert len(result) <= 60  # "💬 " + 50 chars + "..."

    def test_to_log_compact_with_newlines(self):
        """Test compact log format with newlines (should be replaced with spaces)."""
        timestamp = datetime.now()
        content = "Line 1\nLine 2\nLine 3"

        item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content=content,
        )

        result = item.to_log_compact()
        assert "\n" not in result
        assert "Line 1 Line 2 Line 3" in result

    def test_to_log_minimal(self):
        """Test minimal log format."""
        timestamp = datetime.now()
        item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content="Any content",
        )

        assert item.to_log_minimal() == "💬"

    def test_to_metadata(self):
        """Test metadata conversion."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        usage = {"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50}

        item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content="Test response",
            usage=usage,
            response_time_ms=1200,
        )

        metadata = item.to_metadata()

        assert metadata["type"] == "llmresponse"
        assert metadata["model"] == "gpt-4"
        assert metadata["content"] == "Test response"
        assert metadata["usage"] == usage
        assert metadata["response_time_ms"] == 1200


class TestSessionLogItemStepExecution:
    """Test SessionLogItemStepExecution class."""

    def test_creation(self):
        """Test creating StepExecution."""
        timestamp = datetime.now()

        item = SessionLogItemStepExecution(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            step_name="Initialize Variables",
            step_type="step",
            step_content="Set counter = 0",
            playbook_name="main_playbook",
        )

        assert item.step_name == "Initialize Variables"
        assert item.step_type == "step"
        assert item.step_content == "Set counter = 0"
        assert item.playbook_name == "main_playbook"

    def test_to_log_full(self):
        """Test full log format."""
        timestamp = datetime.now()

        item = SessionLogItemStepExecution(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            step_name="Process Data",
            step_type="trigger",
            step_content="When data is received, process it",
            playbook_name="data_processor",
        )

        expected = "→ Trigger: Process Data - When data is received, process it"
        assert item.to_log_full() == expected

    def test_to_log_compact(self):
        """Test compact log format."""
        timestamp = datetime.now()

        item = SessionLogItemStepExecution(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            step_name="Validate Input",
            step_type="condition",
            step_content="Check if input is valid",
            playbook_name="validator",
        )

        assert item.to_log_compact() == "→ Validate Input"

    def test_to_log_minimal(self):
        """Test minimal log format."""
        timestamp = datetime.now()

        item = SessionLogItemStepExecution(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            step_name="Test Step",
            step_type="step",
            step_content="Do something",
            playbook_name="test",
        )

        assert item.to_log_minimal() == "→"

    def test_to_metadata(self):
        """Test metadata conversion."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)

        item = SessionLogItemStepExecution(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            step_name="Execute Command",
            step_type="action",
            step_content="Run the specified command",
            playbook_name="command_runner",
        )

        metadata = item.to_metadata()

        assert metadata["type"] == "stepexecution"
        assert metadata["step_name"] == "Execute Command"
        assert metadata["step_type"] == "action"
        assert metadata["step_content"] == "Run the specified command"
        assert metadata["playbook_name"] == "command_runner"


class TestSessionLogItemVariableUpdate:
    """Test SessionLogItemVariableUpdate class."""

    def test_creation(self):
        """Test creating VariableUpdate."""
        timestamp = datetime.now()

        item = SessionLogItemVariableUpdate(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            variable_name="counter",
            old_value=5,
            new_value=6,
            scope="local",
        )

        assert item.variable_name == "counter"
        assert item.old_value == 5
        assert item.new_value == 6
        assert item.scope == "local"

    def test_creation_with_complex_values(self):
        """Test creating VariableUpdate with complex data types."""
        timestamp = datetime.now()
        old_dict = {"key": "old_value"}
        new_dict = {"key": "new_value", "extra": "data"}

        item = SessionLogItemVariableUpdate(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            variable_name="config",
            old_value=old_dict,
            new_value=new_dict,
            scope="global",
        )

        assert item.old_value == old_dict
        assert item.new_value == new_dict
        assert item.scope == "global"

    def test_to_log_full(self):
        """Test full log format."""
        timestamp = datetime.now()

        item = SessionLogItemVariableUpdate(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            variable_name="status",
            old_value="pending",
            new_value="completed",
            scope="local",
        )

        expected = "📝 status = completed (was: pending)"
        assert item.to_log_full() == expected

    def test_to_log_compact(self):
        """Test compact log format."""
        timestamp = datetime.now()
        long_value = "A" * 50  # Exactly 50 characters

        item = SessionLogItemVariableUpdate(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            variable_name="data",
            old_value="old",
            new_value=long_value,
            scope="local",
        )

        result = item.to_log_compact()
        assert result.startswith("📝 data = ")
        assert result.endswith("...")
        assert len(result) <= 35  # Should be truncated with "..."

    def test_to_log_compact_short_value(self):
        """Test compact log format with short value."""
        timestamp = datetime.now()

        item = SessionLogItemVariableUpdate(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            variable_name="flag",
            old_value=False,
            new_value=True,
            scope="local",
        )

        result = item.to_log_compact()
        assert result == "📝 flag = True..."

    def test_to_log_minimal(self):
        """Test minimal log format."""
        timestamp = datetime.now()

        item = SessionLogItemVariableUpdate(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            variable_name="test",
            old_value=1,
            new_value=2,
            scope="local",
        )

        assert item.to_log_minimal() == "📝"

    def test_to_metadata(self):
        """Test metadata conversion."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)

        item = SessionLogItemVariableUpdate(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            variable_name="result",
            old_value=None,
            new_value={"success": True, "data": [1, 2, 3]},
            scope="global",
        )

        metadata = item.to_metadata()

        assert metadata["type"] == "variableupdate"
        assert metadata["variable_name"] == "result"
        assert metadata["old_value"] == "None"
        assert metadata["new_value"] == "{'success': True, 'data': [1, 2, 3]}"
        assert metadata["scope"] == "global"


class TestSessionLogItemAgentMessage:
    """Test SessionLogItemAgentMessage class."""

    def test_creation(self):
        """Test creating AgentMessage."""
        timestamp = datetime.now()

        item = SessionLogItemAgentMessage(
            timestamp=timestamp,
            agent_id="receiver-1",
            agent_klass="AIAgent",
            sender_id="sender-1",
            sender_klass="HumanAgent",
            recipient_id="receiver-1",
            recipient_klass="AIAgent",
            message="Hello, how are you?",
            message_type="greeting",
        )

        assert item.sender_id == "sender-1"
        assert item.sender_klass == "HumanAgent"
        assert item.recipient_id == "receiver-1"
        assert item.recipient_klass == "AIAgent"
        assert item.message == "Hello, how are you?"
        assert item.message_type == "greeting"

    def test_to_log_full(self):
        """Test full log format."""
        timestamp = datetime.now()

        item = SessionLogItemAgentMessage(
            timestamp=timestamp,
            agent_id="receiver-1",
            agent_klass="AIAgent",
            sender_id="user-123",
            sender_klass="HumanAgent",
            recipient_id="ai-456",
            recipient_klass="AIAgent",
            message="Please process this data",
            message_type="request",
        )

        expected = "📨 HumanAgent(user-123) → AIAgent(ai-456): Please process this data"
        assert item.to_log_full() == expected

    def test_to_log_compact(self):
        """Test compact log format."""
        timestamp = datetime.now()
        long_message = "This is a very long message that should be truncated after 50 characters to fit compact format"

        item = SessionLogItemAgentMessage(
            timestamp=timestamp,
            agent_id="receiver-1",
            agent_klass="AIAgent",
            sender_id="sender-1",
            sender_klass="HumanAgent",
            recipient_id="receiver-1",
            recipient_klass="AIAgent",
            message=long_message,
            message_type="info",
        )

        result = item.to_log_compact()
        assert result.startswith("📨 HumanAgent → AIAgent: ")
        assert result.endswith("...")
        assert len(result) <= 80  # Reasonable limit for compact format

    def test_to_log_compact_with_newlines(self):
        """Test compact log format with newlines."""
        timestamp = datetime.now()
        message_with_newlines = "Line 1\nLine 2\nLine 3"

        item = SessionLogItemAgentMessage(
            timestamp=timestamp,
            agent_id="receiver-1",
            agent_klass="AIAgent",
            sender_id="sender-1",
            sender_klass="TestAgent",
            recipient_id="receiver-1",
            recipient_klass="AIAgent",
            message=message_with_newlines,
            message_type="multiline",
        )

        result = item.to_log_compact()
        assert "\n" not in result
        assert "Line 1 Line 2 Line 3" in result

    def test_to_log_minimal(self):
        """Test minimal log format."""
        timestamp = datetime.now()

        item = SessionLogItemAgentMessage(
            timestamp=timestamp,
            agent_id="receiver-1",
            agent_klass="AIAgent",
            sender_id="sender-1",
            sender_klass="HumanAgent",
            recipient_id="receiver-1",
            recipient_klass="AIAgent",
            message="Test message",
            message_type="test",
        )

        assert item.to_log_minimal() == "📨"

    def test_to_metadata(self):
        """Test metadata conversion."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)

        item = SessionLogItemAgentMessage(
            timestamp=timestamp,
            agent_id="receiver-1",
            agent_klass="AIAgent",
            sender_id="sender-123",
            sender_klass="HumanAgent",
            recipient_id="receiver-456",
            recipient_klass="AIAgent",
            message="Transfer complete",
            message_type="notification",
        )

        metadata = item.to_metadata()

        assert metadata["type"] == "agentmessage"
        assert metadata["sender_id"] == "sender-123"
        assert metadata["sender_klass"] == "HumanAgent"
        assert metadata["recipient_id"] == "receiver-456"
        assert metadata["recipient_klass"] == "AIAgent"
        assert metadata["message"] == "Transfer complete"
        assert metadata["message_type"] == "notification"


class TestSessionLogItemError:
    """Test SessionLogItemError class."""

    def test_creation_minimal(self):
        """Test creating Error with minimal fields."""
        timestamp = datetime.now()

        item = SessionLogItemError(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            error_type="ValueError",
            error_message="Invalid input provided",
        )

        assert item.error_type == "ValueError"
        assert item.error_message == "Invalid input provided"
        assert item.stack_trace is None
        assert item.context is None

    def test_creation_full(self):
        """Test creating Error with all fields."""
        timestamp = datetime.now()
        stack_trace = "Traceback (most recent call last):\n  File test.py, line 10\n    raise ValueError()"
        context = {"function": "process_data", "line": 42, "file": "processor.py"}

        item = SessionLogItemError(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            error_type="RuntimeError",
            error_message="Process failed unexpectedly",
            stack_trace=stack_trace,
            context=context,
        )

        assert item.stack_trace == stack_trace
        assert item.context == context

    def test_to_log_full_without_stack_trace(self):
        """Test full log format without stack trace."""
        timestamp = datetime.now()

        item = SessionLogItemError(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            error_type="ConnectionError",
            error_message="Failed to connect to service",
        )

        expected = "❌ ConnectionError: Failed to connect to service"
        assert item.to_log_full() == expected

    def test_to_log_full_with_stack_trace(self):
        """Test full log format with stack trace."""
        timestamp = datetime.now()
        stack_trace = "Traceback:\n  File test.py, line 5\n    x = 1/0"

        item = SessionLogItemError(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            error_type="ZeroDivisionError",
            error_message="division by zero",
            stack_trace=stack_trace,
        )

        expected = f"❌ ZeroDivisionError: division by zero\n{stack_trace}"
        assert item.to_log_full() == expected

    def test_to_log_compact(self):
        """Test compact log format."""
        timestamp = datetime.now()
        long_message = "This is a very long error message that should be truncated after 50 characters"

        item = SessionLogItemError(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            error_type="CustomError",
            error_message=long_message,
        )

        result = item.to_log_compact()
        assert result.startswith("❌ CustomError: ")
        assert result.endswith("...")
        assert len(result) <= 70  # Should be truncated

    def test_to_log_minimal(self):
        """Test minimal log format."""
        timestamp = datetime.now()

        item = SessionLogItemError(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            error_type="Error",
            error_message="Something went wrong",
        )

        assert item.to_log_minimal() == "❌"

    def test_to_metadata(self):
        """Test metadata conversion."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        stack_trace = "Traceback: Error occurred"
        context = {"module": "auth", "function": "login"}

        item = SessionLogItemError(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            error_type="AuthenticationError",
            error_message="Invalid credentials",
            stack_trace=stack_trace,
            context=context,
        )

        metadata = item.to_metadata()

        assert metadata["type"] == "error"
        assert metadata["error_type"] == "AuthenticationError"
        assert metadata["error_message"] == "Invalid credentials"
        assert metadata["stack_trace"] == stack_trace
        assert metadata["context"] == context


class TestSessionLogItemDebug:
    """Test SessionLogItemDebug class."""

    def test_creation_minimal(self):
        """Test creating Debug with minimal fields."""
        timestamp = datetime.now()

        item = SessionLogItemDebug(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            message="Debug checkpoint reached",
        )

        assert item.message == "Debug checkpoint reached"
        assert item.data is None

    def test_creation_with_data(self):
        """Test creating Debug with data."""
        timestamp = datetime.now()
        debug_data = {"variable": "value", "state": "processing", "count": 42}

        item = SessionLogItemDebug(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            message="Variable state check",
            data=debug_data,
        )

        assert item.data == debug_data

    def test_to_log_full_without_data(self):
        """Test full log format without data."""
        timestamp = datetime.now()

        item = SessionLogItemDebug(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            message="Processing step 3",
        )

        expected = "🐛 Processing step 3"
        assert item.to_log_full() == expected

    def test_to_log_full_with_data(self):
        """Test full log format with data."""
        timestamp = datetime.now()
        debug_data = {"counter": 5, "status": "active"}

        item = SessionLogItemDebug(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            message="State check",
            data=debug_data,
        )

        expected = "🐛 State check - {'counter': 5, 'status': 'active'}"
        assert item.to_log_full() == expected

    def test_to_log_compact(self):
        """Test compact log format."""
        timestamp = datetime.now()
        long_message = "This is a very long debug message that should be truncated after 50 characters"

        item = SessionLogItemDebug(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            message=long_message,
        )

        result = item.to_log_compact()
        assert result.startswith("🐛 ")
        assert result.endswith("...")
        assert len(result) <= 60  # Should be truncated

    def test_to_log_minimal(self):
        """Test minimal log format."""
        timestamp = datetime.now()

        item = SessionLogItemDebug(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            message="Debug info",
        )

        assert item.to_log_minimal() == "🐛"

    def test_to_metadata(self):
        """Test metadata conversion."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        debug_data = {"thread": "main", "memory": "12MB", "cpu": "15%"}

        item = SessionLogItemDebug(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            message="Performance metrics",
            data=debug_data,
        )

        metadata = item.to_metadata()

        assert metadata["type"] == "debug"
        assert metadata["message"] == "Performance metrics"
        assert metadata["data"] == debug_data

    def test_to_metadata_without_data(self):
        """Test metadata conversion without data."""
        timestamp = datetime.now()

        item = SessionLogItemDebug(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            message="Simple debug message",
        )

        metadata = item.to_metadata()
        assert metadata["data"] is None


class TestIntegrationScenarios:
    """Integration tests for various session log item scenarios."""

    def test_complete_playbook_execution_flow(self):
        """Test a complete playbook execution flow with multiple log items."""
        timestamp = datetime(2024, 1, 15, 10, 30, 45)

        # Start playbook
        start_item = SessionLogItemPlaybookStart(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="data_processor",
            playbook_id="pb-123",
        )

        # Execute step
        step_item = SessionLogItemStepExecution(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            step_name="Load Data",
            step_type="step",
            step_content="Load data from database",
            playbook_name="data_processor",
        )

        # Update variable
        var_item = SessionLogItemVariableUpdate(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            variable_name="records_loaded",
            old_value=0,
            new_value=1000,
            scope="local",
        )

        # End playbook
        end_item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="data_processor",
            playbook_id="pb-123",
            return_value="success",
            execution_time_ms=5000,
            success=True,
        )

        # Verify the flow makes sense
        assert start_item.playbook_name == end_item.playbook_name
        assert start_item.playbook_id == end_item.playbook_id
        assert step_item.playbook_name == start_item.playbook_name
        assert var_item.new_value == 1000
        assert end_item.success is True

    def test_error_handling_flow(self):
        """Test error handling flow in a playbook."""
        timestamp = datetime.now()

        # Start playbook
        start_item = SessionLogItemPlaybookStart(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="error_prone_task",
        )

        # Debug message
        debug_item = SessionLogItemDebug(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            message="Attempting risky operation",
            data={"risk_level": "high"},
        )

        # Error occurs
        error_item = SessionLogItemError(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            error_type="NetworkError",
            error_message="Connection timeout",
            context={"endpoint": "api.example.com", "timeout": 30},
        )

        # End playbook with failure
        end_item = SessionLogItemPlaybookEnd(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            playbook_name="error_prone_task",
            success=False,
            error="Connection timeout",
        )

        # Verify error handling flow
        assert start_item.playbook_name == end_item.playbook_name
        assert debug_item.data["risk_level"] == "high"
        assert error_item.error_type == "NetworkError"
        assert end_item.success is False
        assert end_item.error == "Connection timeout"

    def test_llm_interaction_flow(self):
        """Test LLM request/response flow."""
        timestamp = datetime.now()

        # LLM Request
        request_item = SessionLogItemLLMRequest(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Explain quantum computing"},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        # LLM Response
        response_item = SessionLogItemLLMResponse(
            timestamp=timestamp,
            agent_id="agent-1",
            agent_klass="AIAgent",
            model="gpt-4",
            content="Quantum computing is a revolutionary technology...",
            usage={"prompt_tokens": 25, "completion_tokens": 150, "total_tokens": 175},
            response_time_ms=2500,
        )

        # Verify LLM interaction
        assert request_item.model == response_item.model
        assert len(request_item.messages) == 2
        assert response_item.usage["total_tokens"] == 175
        assert "quantum computing" in response_item.content.lower()

    def test_agent_communication_flow(self):
        """Test inter-agent communication flow."""
        timestamp = datetime.now()

        # Agent A sends message to Agent B
        message_item = SessionLogItemAgentMessage(
            timestamp=timestamp,
            agent_id="agent-b",  # Receiver's perspective
            agent_klass="ProcessorAgent",
            sender_id="agent-a",
            sender_klass="CoordinatorAgent",
            recipient_id="agent-b",
            recipient_klass="ProcessorAgent",
            message="Process this data batch",
            message_type="task_assignment",
        )

        # Agent B responds
        response_message = SessionLogItemAgentMessage(
            timestamp=timestamp,
            agent_id="agent-a",  # Now from Agent A's perspective
            agent_klass="CoordinatorAgent",
            sender_id="agent-b",
            sender_klass="ProcessorAgent",
            recipient_id="agent-a",
            recipient_klass="CoordinatorAgent",
            message="Task completed successfully",
            message_type="task_response",
        )

        # Verify communication flow
        assert message_item.sender_id == response_message.recipient_id
        assert message_item.recipient_id == response_message.sender_id
        assert message_item.message_type == "task_assignment"
        assert response_message.message_type == "task_response"

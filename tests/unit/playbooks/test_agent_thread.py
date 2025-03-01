from unittest.mock import MagicMock, patch

import pytest

from playbooks.agent_thread import AgentThread, MessageReceived
from playbooks.types import AgentResponseChunk, ToolCall, ToolResponse


class TestMessageReceived:
    def test_initialization(self):
        # Test with agent
        mock_agent = MagicMock()
        mock_agent.klass = "TestAgent"
        message = MessageReceived("Hello", mock_agent)

        assert message.message == "Hello"
        assert message.from_agent == mock_agent

    def test_initialization_without_agent(self):
        # Test without agent (should default to "System")
        message = MessageReceived("Hello", None)

        assert message.message == "Hello"
        assert message.from_agent == "System"

    def test_repr(self):
        # Test with agent - use a real object instead of a MagicMock
        class MockAgent:
            def __str__(self):
                return "TestAgent"

        mock_agent = MockAgent()
        message = MessageReceived("Hello", mock_agent)
        assert repr(message) == "TestAgent: Hello"

        # Test without agent
        message_no_agent = MessageReceived("Hello", None)
        assert repr(message_no_agent) == "System: Hello"


class TestAgentThread:
    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent.klass = "TestAgent"
        agent.playbooks = ["playbook1", "playbook2"]
        return agent

    @pytest.fixture
    def agent_thread(self, mock_agent):
        return AgentThread(mock_agent)

    def test_initialization(self, mock_agent, agent_thread):
        assert agent_thread.agent == mock_agent
        assert hasattr(agent_thread, "interpreter")

    @patch("playbooks.agent_thread.Interpreter")
    def test_process_message_basic(self, mock_interpreter_class, mock_agent):
        # Setup mocks
        mock_interpreter = MagicMock()
        mock_interpreter_class.return_value = mock_interpreter
        mock_interpreter.execute.return_value = []

        # Create thread with mocked interpreter
        thread = AgentThread(mock_agent)

        # Test processing a message
        from_agent = MagicMock()
        from_agent.klass = "SenderAgent"

        list(thread.process_message("Hello", from_agent, "direct"))

        # Verify interpreter was called correctly
        mock_interpreter.trace.assert_called_once()
        mock_interpreter.execute.assert_called_once_with(
            playbooks=mock_agent.playbooks,
            instruction="Received direct message from SenderAgent: Hello",
            llm_config=None,
            stream=False,
        )

    @patch("playbooks.agent_thread.Interpreter")
    def test_process_message_with_say_tool(self, mock_interpreter_class, mock_agent):
        # Setup mocks
        mock_interpreter = MagicMock()
        mock_interpreter_class.return_value = mock_interpreter

        # Create a Say tool call
        say_tool_call = ToolCall(fn="Say", args=["Hello there!"], kwargs={})
        say_chunk = AgentResponseChunk(tool_call=say_tool_call)

        # Make interpreter return the chunk
        mock_interpreter.execute.return_value = [say_chunk]

        # Create thread with mocked interpreter
        thread = AgentThread(mock_agent)

        # Process a message
        from_agent = MagicMock()
        from_agent.klass = "SenderAgent"

        # Collect the response chunks
        response_chunks = list(thread.process_message("Hello", from_agent, "direct"))

        # Verify the response contains both the original chunk and a new chunk with the Say response
        assert len(response_chunks) == 2
        assert response_chunks[0] == say_chunk
        assert isinstance(response_chunks[1], AgentResponseChunk)
        assert response_chunks[1].agent_response == "Hello there!\n"

    @patch("playbooks.agent_thread.Interpreter")
    def test_process_message_with_other_tool(self, mock_interpreter_class, mock_agent):
        # Setup mocks
        mock_interpreter = MagicMock()
        mock_interpreter_class.return_value = mock_interpreter

        # Create a non-Say tool call with a return value
        other_tool_call = ToolCall(fn="OtherTool", args=[], kwargs={})
        other_tool_call.retval = "Tool result"
        other_chunk = AgentResponseChunk(tool_call=other_tool_call)

        # Make interpreter return the chunk
        mock_interpreter.execute.return_value = [other_chunk]

        # Create thread with mocked interpreter
        thread = AgentThread(mock_agent)

        # Process a message
        from_agent = MagicMock()
        from_agent.klass = "SenderAgent"

        # Collect the response chunks
        response_chunks = list(thread.process_message("Hello", from_agent, "direct"))

        # Verify the response contains both the original chunk and a new chunk with the tool response
        assert len(response_chunks) == 2
        assert response_chunks[0] == other_chunk
        assert isinstance(response_chunks[1], AgentResponseChunk)
        assert isinstance(response_chunks[1].tool_response, ToolResponse)
        assert response_chunks[1].tool_response.code == "OtherTool"
        assert response_chunks[1].tool_response.output == "Tool result"

    @patch("playbooks.agent_thread.Interpreter")
    def test_process_message_with_streaming(self, mock_interpreter_class, mock_agent):
        # Setup mocks
        mock_interpreter = MagicMock()
        mock_interpreter_class.return_value = mock_interpreter

        # Create a chunk
        chunk = AgentResponseChunk(raw="Streaming response")

        # Make interpreter return the chunk
        mock_interpreter.execute.return_value = [chunk]

        # Create thread with mocked interpreter
        thread = AgentThread(mock_agent)

        # Process a message with streaming enabled
        from_agent = MagicMock()
        from_agent.klass = "SenderAgent"

        # Collect the response chunks
        response_chunks = list(
            thread.process_message("Hello", from_agent, "direct", stream=True)
        )

        # Verify the response contains the chunk
        assert len(response_chunks) == 1
        assert response_chunks[0] == chunk

        # Verify interpreter was called with stream=True
        mock_interpreter.execute.assert_called_once_with(
            playbooks=mock_agent.playbooks,
            instruction="Received direct message from SenderAgent: Hello",
            llm_config=None,
            stream=True,
        )

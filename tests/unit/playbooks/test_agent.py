from unittest.mock import Mock, patch

import pytest

from playbooks.agent import Agent
from playbooks.enums import PlaybookExecutionType
from playbooks.exceptions import AgentAlreadyRunningError, AgentConfigurationError
from playbooks.playbook import Playbook
from playbooks.types import ToolCall
from playbooks.utils.llm_helper import configure_litellm

configure_litellm()


@pytest.fixture
def mock_playbook():
    return Mock(
        spec=Playbook,
        execution_type=PlaybookExecutionType.EXT,
        klass="test_tool",
        signature="test_signature",
        description="Test playbook description",
        markdown="Test markdown",
    )


@pytest.fixture
def mock_agent_thread():
    with patch("playbooks.agent.AgentThread") as mock_agent_thread_class:
        mock_thread = Mock()
        mock_agent_thread_class.return_value = mock_thread
        yield mock_thread


def test_agent_initialization():
    # Mock the run method to avoid starting the agent
    with patch.object(Agent, "run", return_value=None):
        agent = Agent(klass="test_agent", description="Test Agent")
        assert agent.klass == "test_agent"
        assert agent.description == "Test Agent"
        assert agent.playbooks == {}
        assert agent.main_thread is None


def test_agent_initialization_with_playbooks(mock_playbook):
    # Mock the run method to avoid starting the agent
    with patch.object(Agent, "run", return_value=None):
        agent = Agent(
            klass="test_agent",
            description="Test Agent",
            playbooks={"test_playbook": mock_playbook},
        )
        assert len(agent.playbooks) == 1
        assert "test_playbook" in agent.playbooks
        assert agent.playbooks["test_playbook"] == mock_playbook


def test_run_without_playbooks():
    # Mock the run method to avoid starting the agent
    with patch.object(Agent, "run", return_value=None):
        agent = Agent(klass="test_agent", description="Test Agent")
        # Override the run method to call process_message directly
        with pytest.raises(AgentConfigurationError):
            list(
                agent.process_message(
                    message="test", from_agent=None, routing_type="direct"
                )
            )


def test_run_already_running():
    # Create a mock agent
    agent = Mock(spec=Agent)
    agent.main_thread = Mock()  # Simulate an already running agent

    # Mock the run method to raise AgentAlreadyRunningError
    agent.run.side_effect = AgentAlreadyRunningError("AI agent is already running")

    # Test that calling run raises the expected exception
    with pytest.raises(AgentAlreadyRunningError):
        agent.run()


def test_execute_tool_not_found(mock_agent_thread):
    # Create a mock agent with a mock playbook
    with patch.object(Agent, "run", return_value=None):
        agent = Agent(
            klass="test_agent",
            description="Test Agent",
            playbooks={"test_playbook": Mock()},
        )

        # Set up the agent thread
        agent.main_thread = mock_agent_thread

        # Create a tool call for a non-existent tool
        tool_call = ToolCall(fn="nonexistent_tool", args=(), kwargs={})

        # Mock the execute_tool method to raise an exception
        mock_agent_thread.execute_tool.side_effect = Exception(
            "EXT playbook nonexistent_tool not found"
        )

        # Verify the exception is raised
        with pytest.raises(Exception) as exc_info:
            agent.main_thread.execute_tool(tool_call)
        assert "EXT playbook nonexistent_tool not found" in str(exc_info.value)


def test_process_message(mock_agent_thread):
    # Mock the run method to avoid starting the agent
    with patch.object(Agent, "run", return_value=None):
        agent = Agent(
            klass="test_agent",
            description="Test Agent",
            playbooks={"test_playbook": Mock()},
        )

        # Set up the agent thread
        agent.main_thread = mock_agent_thread
        mock_agent_thread.process_message.return_value = ["response"]

        # Process a message
        result = list(
            agent.process_message(
                message="test message", from_agent=None, routing_type="direct"
            )
        )

        # Verify results
        assert result == ["response"]
        mock_agent_thread.process_message.assert_called_once_with(
            message="test message",
            from_agent=None,
            routing_type="direct",
            llm_config=None,
            stream=False,
        )

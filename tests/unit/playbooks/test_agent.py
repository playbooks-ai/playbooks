from unittest.mock import Mock, patch

import pytest

from playbooks.agent import Agent
from playbooks.agent_factory import AgentFactory
from playbooks.enums import PlaybookExecutionType
from playbooks.exceptions import AgentAlreadyRunningError, AgentConfigurationError
from playbooks.playbook import Playbook
from playbooks.types import ToolCall
from playbooks.utils.llm_helper import LLMConfig, configure_litellm

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
def basic_agent(test_data_dir):
    agents = AgentFactory.from_playbooks_paths(
        [test_data_dir / "example.md"], LLMConfig()
    )

    agent_class = agents["HelloWorld Agent"]
    agent = agent_class()

    return agent


def test_agent_initialization():
    agent = Agent(klass="test_agent", description="Test Agent")
    assert agent.klass == "test_agent"
    assert agent.description == "Test Agent"
    assert agent.playbooks == []
    assert agent.main_thread is None


def test_agent_initialization_with_playbooks(mock_playbook):
    agent = Agent(
        klass="test_agent",
        description="Test Agent",
        playbooks=[mock_playbook],
    )
    assert len(agent.playbooks) == 1
    assert agent.playbooks[0] == mock_playbook


def test_run_without_playbooks():
    agent = Agent(klass="test_agent", description="Test Agent")
    with pytest.raises(AgentConfigurationError):
        list(agent.run())


def test_run_already_running(basic_agent: Agent):
    # Mock llm_config
    llm_config = LLMConfig()

    # First run should succeed
    list(basic_agent.run(llm_config=llm_config, stream=True))

    # Second run should fail
    with pytest.raises(AgentAlreadyRunningError):
        list(basic_agent.run(llm_config=llm_config))


def test_execute_tool_not_found(basic_agent):
    tool_call = ToolCall(fn="nonexistent_tool", args=(), kwargs={})
    with pytest.raises(Exception) as exc_info:
        basic_agent.execute_tool(tool_call)
    assert "EXT playbook nonexistent_tool not found" in str(exc_info.value)


@patch("playbooks.agent.AgentThread")
def test_process_message(mock_agent_thread_class, basic_agent):
    # Setup mock
    mock_agent_thread = Mock()
    mock_agent_thread.process_message.return_value = iter(["response"])
    mock_agent_thread_class.return_value = mock_agent_thread

    # Process a message
    result = list(
        basic_agent.process_message(
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

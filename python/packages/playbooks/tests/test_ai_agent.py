import os
from unittest.mock import Mock

import pytest

from playbooks.core.agents.ai_agent import AIAgent, AIAgentThread
from playbooks.core.exceptions import (
    AgentAlreadyRunningError,
    AgentConfigurationError,
    AgentError,
)
from playbooks.core.playbook import Playbook
from playbooks.enums import AgentType


@pytest.fixture
def sample_h1_node():
    return {
        "type": "h1",
        "text": "TestAgent",
        "description": "A test agent",
        "markdown": "# TestAgent\nA test agent",
        "children": [
            {
                "type": "h2",
                "text": "TestPlaybook",
                "description": "A test playbook",
                "markdown": "## TestPlaybook\nA test playbook",
                "children": [],
            }
        ],
    }


@pytest.fixture
def sample_h1_node_no_children():
    return {
        "type": "h1",
        "text": "TestAgent",
        "description": "A test agent",
        "markdown": "# TestAgent\nA test agent",
        "children": [],
    }


@pytest.fixture
def mock_runtime(hello_world_response):
    runtime = Mock()
    runtime.get_llm_completion.return_value = iter([hello_world_response])
    return runtime


@pytest.fixture
def hello_world_response():
    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "hello_world_response.txt"
    )
    with open(fixture_path) as f:
        return f.read()


def test_ai_agent_init():
    agent = AIAgent(klass="TestAgent", description="Test description")
    assert agent.klass == "TestAgent"
    assert agent.description == "Test description"
    assert agent.type == AgentType.AI
    assert len(agent.playbooks) == 0
    assert agent.main_thread is None


def test_ai_agent_from_h1(sample_h1_node):
    agent = AIAgent.from_h1(sample_h1_node)
    assert agent.klass == "TestAgent"
    assert agent.description == "A test agent"
    assert len(agent.playbooks) == 1
    assert isinstance(agent.playbooks[0], Playbook)
    assert agent.playbooks[0].klass == "TestPlaybook"


def test_ai_agent_from_h1_no_children(sample_h1_node_no_children):
    agent = AIAgent.from_h1(sample_h1_node_no_children)
    assert len(agent.playbooks) == 0


def test_run_no_playbooks():
    agent = AIAgent(klass="TestAgent", description="Test description")
    with pytest.raises(AgentConfigurationError):
        next(agent.run(Mock()))


def test_run_already_running(sample_h1_node, mock_runtime):
    agent = AIAgent.from_h1(sample_h1_node)
    agent.main_thread = Mock()
    with pytest.raises(AgentAlreadyRunningError):
        next(agent.run(mock_runtime))


def test_run_no_runtime(sample_h1_node):
    agent = AIAgent.from_h1(sample_h1_node)
    with pytest.raises(AgentError):
        next(agent.run(None))


def test_run_success(sample_h1_node, mock_runtime, hello_world_response):
    agent = AIAgent.from_h1(sample_h1_node)
    response = list(agent.run(mock_runtime))
    assert response == [hello_world_response]
    assert isinstance(agent.main_thread, AIAgentThread)


def test_process_message(sample_h1_node, mock_runtime, hello_world_response):
    agent = AIAgent.from_h1(sample_h1_node)
    from_agent = AIAgent(klass="SenderAgent", description="Test sender")

    # First run to initialize main_thread
    list(agent.run(mock_runtime))

    # Reset the mock to ensure we get a fresh response
    mock_runtime.get_llm_completion.reset_mock()
    mock_runtime.get_llm_completion.return_value = iter([hello_world_response])

    response = list(
        agent.process_message(
            message="Test message",
            from_agent=from_agent,
            routing_type="direct",
            runtime=mock_runtime,
        )
    )
    assert response == [hello_world_response]

    # Verify the message format
    messages = mock_runtime.get_llm_completion.call_args[1]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert (
        "Received the following message from SenderAgent: Test message"
        in messages[1]["content"]
    )


def test_ai_agent_thread_get_system_prompt():
    agent = AIAgent(klass="TestAgent", description="Test description")
    thread = AIAgentThread(agent)

    mock_playbook = Mock()
    mock_playbook.markdown = "# Test Playbook\n## Test Step"

    prompt = thread.get_system_prompt([mock_playbook])
    assert "You are a pseudocode interpreter" in prompt
    assert "# Test Playbook\n## Test Step" in prompt


def test_ai_agent_thread_run(mock_runtime, hello_world_response):
    agent = AIAgent(klass="TestAgent", description="Test description")
    thread = AIAgentThread(agent)

    mock_playbook = Mock()
    mock_playbook.markdown = "# Test Playbook\n## Test Step"

    response = list(
        thread.run(
            runtime=mock_runtime,
            included_playbooks=[mock_playbook],
            instruction=hello_world_response,
        )
    )
    assert response == [hello_world_response]

    # Verify the messages passed to get_llm_completion
    messages = mock_runtime.get_llm_completion.call_args[1]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == hello_world_response

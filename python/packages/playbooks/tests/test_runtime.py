import os

import pytest

from playbooks.config import DEFAULT_MODEL, RuntimeConfig
from playbooks.core.agents import AIAgent
from playbooks.core.runtime import SingleThreadedPlaybooksRuntime
from playbooks.enums import AgentType


def get_fixture_path(filename: str) -> str:
    """Get the absolute path to a fixture file."""
    return os.path.join(os.path.dirname(__file__), "fixtures", filename)


@pytest.fixture
def runtime():
    config = RuntimeConfig()
    return SingleThreadedPlaybooksRuntime(config)


async def test_runtime_init():
    # Test default initialization
    config = RuntimeConfig()
    runtime = SingleThreadedPlaybooksRuntime(config)
    assert runtime.config.llm_config.model == DEFAULT_MODEL

    # Test custom initialization
    config = RuntimeConfig(model="custom-model", api_key="test-key")
    runtime = SingleThreadedPlaybooksRuntime(config)
    assert runtime.config.llm_config.model == "custom-model"
    assert runtime.config.llm_config.api_key == "test-key"


def test_load_playbook():
    runtime = SingleThreadedPlaybooksRuntime()
    runtime.load_from_path("examples/playbooks/hello.md")
    assert runtime.playbooks_content is not None
    assert runtime.ast is not None

    assert runtime.agents is not None
    assert len(runtime.agents) == 1, runtime.agents

    agent = runtime.agents[0]
    assert agent.klass == "HelloWorld Agent"
    assert agent.type == AgentType.AI

    assert agent.playbooks is not None
    assert len(agent.playbooks) == 1

    playbook = agent.playbooks[0]
    assert playbook.klass == "HelloWorld"

    # Check if runtime session is created and persisted to DB
    assert runtime._session is not None
    assert runtime._session.id is not None
    assert runtime._session.created_at is not None
    assert runtime._session.updated_at is not None


def test_run_playbook(runtime):
    runtime.load_from_path("examples/playbooks/hello.md")
    agent = runtime.agents[0]
    assert isinstance(agent, AIAgent)

    # Load sample response from fixture file
    with open(get_fixture_path("hello_world_response.txt")) as f:
        sample_response = f.read()

    # Mock the LLM response to return our sample
    runtime.get_llm_completion = lambda messages: [sample_response]

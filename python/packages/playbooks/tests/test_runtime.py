import pytest

from playbooks.config import DEFAULT_MODEL
from playbooks.constants import INTERPRETER_TRACE_HEADER
from playbooks.core.db import Database
from playbooks.core.runtime import (
    RuntimeConfig,
    SingleThreadedPlaybooksRuntime,
)
from playbooks.enums import AgentType

db = Database()
pytestmark = pytest.mark.asyncio


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


# async def test_runtime_session_persistance():
#     runtime = SingleThreadedPlaybooksRuntime()
#     runtime.load_from_path("examples/playbooks/hello.md")
#     assert runtime._session is not None

#     # Check if runtime session is persisted to DB
#     runtime_session = db.get(RuntimeSession, runtime._session.id)
#     assert runtime_session is not None
#     assert runtime_session.id == runtime._session.id
#     assert runtime_session.runtime.id == runtime.id


def test_run_playbook():
    runtime = SingleThreadedPlaybooksRuntime()
    runtime.load_from_path("examples/playbooks/hello.md")
    response = "".join(list(runtime.agents[0].run(runtime=runtime)))

    assert INTERPRETER_TRACE_HEADER in response

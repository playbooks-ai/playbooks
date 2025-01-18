import pytest

from playbooks.config import DEFAULT_MODEL
from playbooks.core.db import Database
from playbooks.core.db.runtime_session import RuntimeSession
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


async def test_load_playbook():
    runtime = SingleThreadedPlaybooksRuntime()
    runtime.load_from_path("examples/playbooks/hello.md")
    assert runtime.playbooks_content is not None
    assert runtime.ast is not None

    assert runtime.agents is not None
    assert len(runtime.agents) == 1, runtime.agents

    assert runtime.agents[0].klass == "HelloWorld Agent"
    assert runtime.agents[0].type == AgentType.AI

    # Check if runtime session is created and persisted to DB
    assert runtime._session is not None
    assert runtime._session.id is not None
    assert runtime._session.created_at is not None
    assert runtime._session.updated_at is not None


async def test_runtime_session_persistance():
    runtime = SingleThreadedPlaybooksRuntime()
    runtime.load_from_path("examples/playbooks/hello.md")
    assert runtime._session is not None

    # Check if runtime session is persisted to DB
    runtime_session = db.get(RuntimeSession, runtime._session.id)
    assert runtime_session is not None
    assert runtime_session.id == runtime._session.id
    assert runtime_session.runtime.id == runtime.id


# async def test_run_playbook():
#     test_response = "test response"
#     runtime = SingleThreadedPlaybooksRuntime()
#     runtime.load_from_path(
#         "examples/playbooks/hello.md", mock_llm_response=test_response
#     )
#     response = await runtime.run("test playbook")
#     assert str(response) == test_response


# async def test_stream_playbook():
#     runtime = SingleThreadedPlaybooksRuntime()
#     test_response = "Hello World !"
#     runtime.load_from_path(
#         "examples/playbooks/hello.md", mock_llm_response=test_response
#     )

#     chunks = []
#     async for chunk in runtime.stream("test playbook"):
#         chunks.append(chunk)
#     assert chunks == ["Hello", "World", "!"]


# async def test_run_with_kwargs():
#     runtime = SingleThreadedPlaybooksRuntime(RuntimeConfig())
#     test_response = "Test response"

#     mock_response = {"choices": [{"message": {"content": test_response}}]}

#     with patch("playbooks.core.runtime.acompletion") as mock_completion:
#         mock_completion.return_value = mock_response
#         await runtime.run("test playbook", temperature=0.7)
#         mock_completion.assert_called_once()
#         call_kwargs = mock_completion.call_args.kwargs
#         assert call_kwargs["temperature"] == 0.7


# async def test_convenience_run():
#     test_response = "Test response"

#     mock_response = {"choices": [{"message": {"content": test_response}}]}

#     with patch("playbooks.core.runtime.acompletion") as mock_completion:
#         mock_completion.return_value = mock_response
#         await run(
#             "test playbook", model="custom-model", api_key="test-key", temperature=0.7
#         )
#         mock_completion.assert_called_once()
#         call_kwargs = mock_completion.call_args.kwargs
#         assert call_kwargs["model"] == "custom-model"
#         assert call_kwargs["api_key"] == "test-key"
#         assert call_kwargs["temperature"] == 0.7

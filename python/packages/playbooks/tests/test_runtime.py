from unittest.mock import AsyncMock, patch

import pytest

from playbooks.core.runtime import (
    RuntimeConfig,
    SingleThreadedPlaybooksRuntime,
    run,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def runtime():
    config = RuntimeConfig()
    return SingleThreadedPlaybooksRuntime(config)


async def test_runtime_init():
    # Test default initialization
    config = RuntimeConfig()
    runtime = SingleThreadedPlaybooksRuntime(config)
    assert runtime.config.model == "test_model"
    assert runtime.config.api_key == "test_key"

    # Test custom initialization
    config = RuntimeConfig(model="custom-model", api_key="test-key")
    runtime = SingleThreadedPlaybooksRuntime(config)
    assert runtime.config.model == "custom-model"
    assert runtime.config.api_key == "test-key"


async def test_run_playbook():
    runtime = SingleThreadedPlaybooksRuntime()
    test_response = "Test response"

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = test_response

    with patch(
        "playbooks.core.runtime.acompletion", AsyncMock(return_value=mock_response)
    ):
        response = await runtime.run("test playbook")
        assert response == test_response


async def test_stream_playbook():
    runtime = SingleThreadedPlaybooksRuntime(RuntimeConfig())
    test_chunks = ["Hello", " World", "!"]

    async def mock_stream():
        for chunk in test_chunks:
            mock_chunk = AsyncMock()
            mock_chunk.choices = [AsyncMock()]
            mock_chunk.choices[0].delta.content = chunk
            yield mock_chunk

    with patch(
        "playbooks.core.runtime.acompletion", AsyncMock(return_value=mock_stream())
    ):
        chunks = []
        async for chunk in runtime.stream("test playbook"):
            chunks.append(chunk)
        assert chunks == test_chunks


async def test_run_with_kwargs():
    runtime = SingleThreadedPlaybooksRuntime(RuntimeConfig())
    test_response = "Test response"

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = test_response

    with patch("playbooks.core.runtime.acompletion") as mock_completion:
        await runtime.run("test playbook", temperature=0.7)
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs["temperature"] == 0.7


async def test_convenience_run():
    test_response = "Test response"

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = test_response

    with patch("playbooks.core.runtime.acompletion") as mock_completion:
        await run(
            "test playbook", model="custom-model", api_key="test-key", temperature=0.7
        )
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs["model"] == "custom-model"
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["temperature"] == 0.7

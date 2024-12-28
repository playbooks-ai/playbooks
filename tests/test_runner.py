import pytest
import pytest_asyncio
from playbooks.core.runner import PlaybooksRunner, DEFAULT_MODEL
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.asyncio

@pytest.fixture
def runner():
    return PlaybooksRunner()

async def test_runner_init():
    # Test default initialization
    runner = PlaybooksRunner()
    assert runner.model == DEFAULT_MODEL
    assert runner.api_key is None
    assert runner.kwargs == {}

    # Test custom initialization
    runner = PlaybooksRunner(model="custom-model", api_key="test-key", temperature=0.7)
    assert runner.model == "custom-model"
    assert runner.api_key == "test-key"
    assert runner.kwargs == {"temperature": 0.7}

async def test_run_playbook():
    runner = PlaybooksRunner()
    test_response = "Test response"
    
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = test_response

    with patch("playbooks.core.runner.acompletion", AsyncMock(return_value=mock_response)):
        response = await runner.run("test playbook")
        assert response == test_response

async def test_stream_playbook():
    runner = PlaybooksRunner()
    test_chunks = ["Hello", " World", "!"]
    
    async def mock_stream():
        for chunk in test_chunks:
            mock_chunk = AsyncMock()
            mock_chunk.choices = [AsyncMock()]
            mock_chunk.choices[0].delta.content = chunk
            yield mock_chunk

    with patch("playbooks.core.runner.acompletion", AsyncMock(return_value=mock_stream())):
        chunks = []
        async for chunk in runner.stream("test playbook"):
            chunks.append(chunk)
        assert chunks == test_chunks

async def test_run_with_custom_kwargs():
    runner = PlaybooksRunner(temperature=0.7)
    test_response = "Test response"
    
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = test_response

    with patch("playbooks.core.runner.acompletion") as mock_completion:
        mock_completion.return_value = mock_response
        await runner.run("test playbook", max_tokens=100)
        
        # Verify both init kwargs and run kwargs are passed
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 100

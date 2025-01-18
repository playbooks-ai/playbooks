import os

import pytest
from dotenv import load_dotenv

from playbooks.core.llm_helper import (
    LLMConfig,
    configure_litellm,
    custom_get_cache_key,
    get_completion,
)

# Load .env.test configuration
load_dotenv(".env.test")


@pytest.fixture
def mock_litellm(mocker):
    return mocker.patch("playbooks.core.llm_helper.litellm")


@pytest.fixture
def default_model():
    return os.environ["DEFAULT_MODEL"]


@pytest.fixture
def api_key():
    return os.environ["ANTHROPIC_API_KEY"]


def test_custom_get_cache_key():
    key = custom_get_cache_key(model="gpt-3", messages="Hello", temperature=0.5)
    assert len(key) == 32
    assert isinstance(key, str)


def test_configure_litellm_production(mock_litellm, mocker):
    mock_cache = mocker.patch("playbooks.core.llm_helper.Cache")
    mocker.patch.dict(
        os.environ,
        {
            "LITELLM_CACHE_ENABLED": "true",
            "ENVIRONMENT": "production",
            "REDIS_URL": "redis://localhost:6379/0",
        },
    )
    configure_litellm()
    mock_cache.assert_called_with(type="redis", url="redis://localhost:6379/0")


def test_configure_litellm_development(mock_litellm, mocker):
    mock_cache = mocker.patch("playbooks.core.llm_helper.Cache")
    mocker.patch.dict(
        os.environ,
        {
            "LITELLM_CACHE_ENABLED": "true",
            "ENVIRONMENT": "development",
            "LITELLM_CACHE_PATH": "/tmp/cache",
        },
    )
    configure_litellm()
    mock_cache.assert_called()


def test_get_completion(default_model, api_key):
    configure_litellm()
    config = LLMConfig(model=default_model, api_key=api_key)
    messages = [{"role": "user", "content": "Say hello"}]

    # First call should hit the API and cache the result
    response = list(get_completion(config, messages=messages))
    assert len(response) > 0
    assert isinstance(response[0], tuple)
    # Verify response structure
    assert len(response) == 7  # Check total number of tuples
    assert response[0][0] == "id"
    assert response[0][1].startswith("chatcmpl-")

    assert response[2][0] == "model"
    assert response[2][1] == "claude-3-5-sonnet-20241022"

    assert response[3][0] == "object"
    assert response[3][1] == "chat.completion"

    # Second call should use cached result
    cached_response = list(get_completion(config, messages=messages))
    assert cached_response == response


def test_get_completion_streaming(default_model, api_key):
    configure_litellm()
    config = LLMConfig(model=default_model, api_key=api_key)
    messages = [{"role": "user", "content": "Count to 3"}]

    # Test streaming response
    stream_response = list(get_completion(config, stream=True, messages=messages))

    # Verify response structure
    assert len(stream_response) == 2  # Two chunks - content and completion

    # First chunk contains the content
    assert stream_response[0].id.startswith("chatcmpl-")
    assert isinstance(stream_response[0].created, int)
    assert stream_response[0].model == "claude-3-5-sonnet-20241022"
    assert stream_response[0].object == "chat.completion.chunk"
    assert stream_response[0].system_fingerprint is None
    assert len(stream_response[0].choices) == 1
    assert stream_response[0].choices[0].finish_reason is None
    assert stream_response[0].choices[0].index == 0
    assert stream_response[0].choices[0].delta.content == "1\n2\n3"
    assert stream_response[0].choices[0].delta.role == "assistant"

    # Second chunk indicates completion
    assert stream_response[1].id == stream_response[0].id  # Same ID for the stream
    assert stream_response[1].choices[0].finish_reason == "stop"
    assert stream_response[1].choices[0].delta.content is None


def test_get_completion_different_params(default_model, api_key):
    configure_litellm()
    config = LLMConfig(model=default_model, api_key=api_key)
    messages = [{"role": "user", "content": "Say hello"}]

    # Different temperature should result in different cache key
    response1 = list(get_completion(config, messages=messages, temperature=0.5))
    response2 = list(get_completion(config, messages=messages, temperature=0.7))
    assert (
        response1 != response2
    )  # Different temperature should give different responses

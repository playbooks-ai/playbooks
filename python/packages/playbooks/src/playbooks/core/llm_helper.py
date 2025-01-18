import os
from typing import Iterator

import litellm
from litellm import completion
from litellm.caching.caching import Cache

from playbooks.config import LLMConfig


def custom_get_cache_key(*args, **kwargs):
    # return key to use for your cache:
    key = (
        kwargs.get("model", "")
        + str(kwargs.get("messages", ""))
        + str(kwargs.get("temperature", ""))
        + str(kwargs.get("logit_bias", ""))
    )
    # print("key for cache", key)
    return key


def configure_litellm():
    if os.getenv("LITELLM_CACHE_ENABLED", "False").lower() == "true":
        if os.getenv("ENVIRONMENT") == "production":
            litellm.cache = Cache(
                type="redis", url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
            )
        else:
            cache_path = os.getenv(
                "LITELLM_CACHE_PATH",
                os.path.join(os.path.dirname(__file__), "litellm_cache"),
            )

            litellm.cache = Cache(
                type="disk",
                disk_cache_dir=cache_path,
            )

        litellm.cache.get_cache_key = custom_get_cache_key
        litellm.enable_cache()

    litellm.set_verbose = os.getenv("LITELLM_SET_VERBOSE", "False").lower() == "true"


configure_litellm()


def get_completion(
    config: LLMConfig, mock_response: str = None, stream: bool = False, **kwargs
) -> Iterator[str]:
    """Get completion from LLM with optional streaming support."""
    if mock_response is not None:
        if stream:

            def mock_stream():
                for chunk in mock_response.split():
                    yield {"choices": [{"delta": {"content": chunk}}]}

            return mock_stream()
        return {"choices": [{"message": {"content": mock_response}}]}

    return completion(
        model=config.model,
        api_key=config.api_key,
        stream=stream,
        **kwargs,
    )

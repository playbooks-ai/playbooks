import hashlib
import os
import tempfile
from typing import Iterator, List, Union

import litellm
from litellm import completion

from playbooks.config import LLMConfig

llm_cache_enabled = os.getenv("LLM_CACHE_ENABLED", "False").lower() == "true"
if llm_cache_enabled:
    llm_cache_type = os.getenv("LLM_CACHE_TYPE", "disk").lower()
    print(f"Using LLM cache type: {llm_cache_type}")

    if llm_cache_type == "disk":
        from diskcache import Cache

        cache_dir = (
            os.getenv("LLM_CACHE_PATH")
            or tempfile.TemporaryDirectory(prefix="llm_cache_").name
        )
        cache = Cache(directory=cache_dir)
        print(f"Using LLM cache directory: {cache_dir}")

    elif llm_cache_type == "redis":
        from redis import Redis

        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        cache = Redis.from_url(redis_url)
        print(f"Using LLM cache Redis URL: {redis_url}")

    else:
        raise ValueError(f"Invalid LLM cache type: {llm_cache_type}")


def custom_get_cache_key(*args, **kwargs):
    # Create a string combining all relevant parameters
    key_str = (
        kwargs.get("model", "")
        + str(kwargs.get("messages", ""))
        + str(kwargs.get("temperature", ""))
        + str(kwargs.get("logit_bias", ""))
    )
    # print("Custom cache key:", key_str)

    # Create SHA-256 hash and return first 32 characters (128 bits) of the hex digest
    key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:32]
    # print("Custom cache key hash:", key_hash)
    return key_hash


def configure_litellm():
    litellm.set_verbose = os.getenv("LLM_SET_VERBOSE", "False").lower() == "true"


configure_litellm()


def get_completion(
    llm_config: LLMConfig,
    messages: List[dict],
    stream: bool = False,
    use_cache: bool = True,
    **kwargs,
) -> Union[dict, Iterator[dict]]:
    """Get completion from LLM with optional streaming and caching support.

    Args:
        llm_config: LLM configuration containing model and API key
        stream: If True, returns an iterator of response chunks
        use_cache: If True and caching is enabled, will try to use cached responses
        **kwargs: Additional arguments passed to litellm.completion

    Returns:
        If stream=True, returns an iterator of response chunks
        If stream=False, returns the complete response
    """
    completion_kwargs = {
        "model": llm_config.model,
        "api_key": llm_config.api_key,
        "messages": messages,
        "stream": stream,
        **kwargs,
    }

    if llm_cache_enabled and use_cache:
        cache_key = custom_get_cache_key(**completion_kwargs)
        cache_value = cache.get(cache_key)
        # print("Looking for cache key:", cache_key)
        if cache_value is not None:
            # print("Cache hit:", cache_value)
            if stream:
                for chunk in cache_value:
                    yield chunk
            else:
                yield cache_value
        else:
            # print("Cache miss")
            # Get response from LLM
            full_response = []
            try:
                response = completion(**completion_kwargs)
                if stream:
                    for chunk in response.completion_stream:
                        full_response.append(chunk["text"])
                        yield chunk["text"]
                else:
                    full_response = [response["choices"][0]["message"]["content"]]
                    yield full_response
            finally:
                if use_cache:
                    cache.set(cache_key, "".join(full_response))
                    cache.close()

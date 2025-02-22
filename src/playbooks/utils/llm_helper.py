import hashlib
import os
import tempfile
import time
from functools import wraps
from typing import Any, Callable, Iterator, List, TypeVar, Union

import litellm
from litellm import BadRequestError, completion

from playbooks.config import LLMConfig

llm_cache_enabled = os.getenv("LLM_CACHE_ENABLED", "False").lower() == "true"
if llm_cache_enabled:
    llm_cache_type = os.getenv("LLM_CACHE_TYPE", "disk").lower()
    # print(f"Using LLM cache type: {llm_cache_type}")

    if llm_cache_type == "disk":
        from diskcache import Cache

        cache_dir = (
            os.getenv("LLM_CACHE_PATH")
            or tempfile.TemporaryDirectory(prefix="llm_cache_").name
        )
        cache = Cache(directory=cache_dir)
        # print(f"Using LLM cache directory: {cache_dir}")

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


T = TypeVar("T")


def retry_on_overload(
    max_retries: int = 3, base_delay: float = 1.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that retries a function on Anthropic overload errors with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except BadRequestError as e:
                    if "Overloaded" in str(e) and attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        time.sleep(delay)
                        continue
                    raise
            return func(*args, **kwargs)  # Final attempt

        return wrapper

    return decorator


@retry_on_overload()
def _make_completion_request(completion_kwargs: dict) -> Union[str, Iterator[str]]:
    """Make a non-streaming completion request to the LLM with automatic retries on overload.

    Args:
        completion_kwargs: Arguments to pass to the completion function

    Returns:
        Either the complete response or an iterator of response chunks
    """
    response = completion(**completion_kwargs)
    return response["choices"][0]["message"]["content"]


@retry_on_overload()
def _make_completion_request_stream(
    completion_kwargs: dict,
) -> Union[str, Iterator[str]]:
    """Make a streaming completion request to the LLM with automatic retries on overload.

    Args:
        completion_kwargs: Arguments to pass to the completion function

    Returns:
        Either the complete response or an iterator of response chunks
    """
    response = completion(**completion_kwargs)
    for chunk in response.completion_stream:
        yield chunk["text"]


def get_completion(
    llm_config: LLMConfig,
    messages: List[dict],
    stream: bool = False,
    use_cache: bool = True,
    **kwargs,
) -> Iterator[str]:
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
        "max_completion_tokens": 2000,
        "stream": stream,
        **kwargs,
    }

    print()
    print("=" * 20 + f" LLM CALL: {llm_config.model} " + "=" * 20)
    print(messages[0]["content"])
    print(messages[1]["content"] if len(messages) > 1 else "")
    print("=" * 40)
    print()

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

            # cache.close()
            return

    # print("Cache miss for key:", cache_key)
    # print("     Existing keys:", list(cache.iterkeys()))
    # Get response from LLM
    full_response = []
    try:
        if stream:
            for chunk in _make_completion_request_stream(completion_kwargs):
                full_response.append(chunk)
                yield chunk
            full_response = "".join(full_response)
        else:
            full_response = _make_completion_request(completion_kwargs)
            yield full_response
    finally:
        if llm_cache_enabled and use_cache:
            cache.set(cache_key, full_response)
            # cache.close()

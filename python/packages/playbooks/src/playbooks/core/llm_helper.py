import hashlib
import os
from typing import Iterator, Union
import litellm
from litellm import completion
from litellm.caching.caching import Cache

from playbooks.config import LLMConfig


def custom_get_cache_key(*args, **kwargs):
    # Create a string combining all relevant parameters
    key_str = (
        kwargs.get("model", "")
        + str(kwargs.get("messages", ""))
        + str(kwargs.get("temperature", ""))
        + str(kwargs.get("logit_bias", ""))
    )
    # Create SHA-256 hash and return first 32 characters (128 bits) of the hex digest
    return hashlib.sha256(key_str.encode()).hexdigest()[:32]


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
    config: LLMConfig, stream: bool = False, use_cache: bool = True, **kwargs
) -> Union[dict, Iterator[dict]]:
    """Get completion from LLM with optional streaming and caching support.

    Args:
        config: LLM configuration containing model and API key
        stream: If True, returns an iterator of response chunks
        use_cache: If True and caching is enabled, will try to use cached responses
        **kwargs: Additional arguments passed to litellm.completion

    Returns:
        If stream=True, returns an iterator of response chunks
        If stream=False, returns the complete response
    """
    if not use_cache:
        litellm.disable_cache()

    try:
        return completion(
            model=config.model,
            api_key=config.api_key,
            stream=stream,
            **kwargs,
        )
    finally:
        if not use_cache:
            litellm.enable_cache()

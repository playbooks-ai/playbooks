"""LLM helper utilities for making completion requests with caching and tracing.

This module provides a unified interface for LLM interactions, including:
- Streaming and non-streaming completion requests
- Automatic retry logic for rate limits and overloads
- LLM response caching (disk or Redis)
- Langfuse integration for observability
- Message preprocessing and consolidation
"""

import hashlib
import logging
import os
import tempfile
import time
from functools import wraps
from typing import Any, Callable, Iterator, List, Optional, TypeVar, Union

import litellm
from litellm import completion, get_supported_openai_params

from playbooks.enums import LLMMessageRole
from playbooks.llm_messages import SystemPromptLLMMessage, UserInputLLMMessage

from ..config import config
from ..constants import SYSTEM_PROMPT_DELIMITER
from ..debug_logger import debug
from ..exceptions import VendorAPIOverloadedError, VendorAPIRateLimitError
from .langfuse_helper import LangfuseHelper
from .llm_config import LLMConfig
from .playbooks_lm_handler import PlaybooksLMHandler

# https://github.com/BerriAI/litellm/issues/2256#issuecomment-2041374430
loggers = ["LiteLLM Proxy", "LiteLLM Router", "LiteLLM"]

for logger_name in loggers:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL + 1)

litellm.suppress_debug_info = True
# Handle different litellm versions
litellm.drop_params = True
# Note: LLM_API_BASE is now applied per-model basis, not globally
# litellm._turn_on_debug()

# Initialize the Playbooks-LM handler
playbooks_handler = PlaybooksLMHandler()

# Store the original completion function
_original_completion = completion


def completion_with_preprocessing(*args: Any, **kwargs: Any) -> Any:
    """Wrapper for litellm.completion that applies preprocessing for playbooks-lm models.

    This wrapper is injected into litellm to intercept completion calls.
    Currently handles debugging/logging when verbose mode is enabled.

    Args:
        *args: Positional arguments passed to litellm.completion
        **kwargs: Keyword arguments passed to litellm.completion

    Returns:
        Response from litellm.completion
    """
    model = kwargs.get("model", "")

    # Note: Playbooks-LM preprocessing is now handled in get_completion() before Langfuse logging

    # Debug: log the call to help diagnose auth issues when verbose mode is enabled
    if os.getenv("LLM_SET_VERBOSE", "False").lower() == "true":
        api_key_preview = kwargs.get("api_key", "MISSING")
        if api_key_preview and api_key_preview != "MISSING":
            api_key_preview = (
                api_key_preview[:8] + "..." if len(api_key_preview) > 8 else "short"
            )
        debug(
            "LLM Call",
            model=model,
            api_base=kwargs.get("api_base", "default"),
            api_key_preview=api_key_preview,
        )

    # Call the original completion function
    return _original_completion(*args, **kwargs)


# Replace litellm's completion function with our wrapper
litellm.completion = completion_with_preprocessing
completion = completion_with_preprocessing

# Initialize cache if enabled
cache = None

# Load cache configuration from config system with environment fallback
llm_cache_enabled = config.llm_cache.enabled
llm_cache_type = config.llm_cache.type.lower()
llm_cache_path = config.llm_cache.path

if llm_cache_enabled:
    if llm_cache_type == "disk":
        from diskcache import Cache

        cache_dir = (
            llm_cache_path or tempfile.TemporaryDirectory(prefix="llm_cache_").name
        )
        cache = Cache(directory=cache_dir)

    elif llm_cache_type == "redis":
        from redis import Redis

        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        cache = Redis.from_url(redis_url)
        debug("Using LLM cache", redis_url=redis_url)

    else:
        raise ValueError(f"Invalid LLM cache type: {llm_cache_type}")


def custom_get_cache_key(**kwargs) -> str:
    """Generate a deterministic cache key based on request parameters.

    Args:
        **kwargs: The completion request parameters

    Returns:
        A unique hash string to use as cache key
    """
    import json

    # Create a deterministic representation of the cache key components
    cache_components = {
        "model": kwargs.get("model", ""),
        "messages": kwargs.get("messages", []),
        "temperature": kwargs.get("temperature", 0.2),
        "logit_bias": kwargs.get("logit_bias", {}),
    }

    # Use json.dumps with sort_keys=True for deterministic serialization
    key_str = json.dumps(cache_components, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:32]


T = TypeVar("T")


def retry_on_overload(
    max_retries: int = 3, base_delay: float = 1.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that retries a function on API overload or rate limit errors with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds

    Returns:
        A decorator function that adds retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (
                    VendorAPIOverloadedError,
                    VendorAPIRateLimitError,
                    litellm.RateLimitError,
                    litellm.InternalServerError,
                    litellm.ServiceUnavailableError,
                    litellm.APIConnectionError,
                    litellm.Timeout,
                ):
                    if attempt == max_retries - 1:
                        # Last attempt, re-raise the exception
                        raise

                    delay = base_delay * (2**attempt)
                    time.sleep(delay)
                    continue
            return func(*args, **kwargs)  # This line should never be reached

        return wrapper

    return decorator


@retry_on_overload()
def _make_completion_request(completion_kwargs: dict) -> str:
    """Make a non-streaming completion request to the LLM with automatic retries on overload.

    Args:
        completion_kwargs: Dictionary of arguments for litellm.completion

    Returns:
        Full response text from the LLM

    Raises:
        VendorAPIOverloadedError: If API is overloaded after retries
        VendorAPIRateLimitError: If rate limit exceeded after retries
        litellm exceptions: Various litellm exceptions if request fails
    """
    response = completion(**completion_kwargs)
    return response["choices"][0]["message"]["content"]


def _make_completion_request_stream(completion_kwargs: dict) -> Iterator[str]:
    """Make a streaming completion request to the LLM with automatic retries on overload.

    Since exceptions occur on the first token (during initial call), we can retry
    the entire stream creation and maintain true streaming.

    Args:
        completion_kwargs: Dictionary of arguments for litellm.completion

    Yields:
        Response text chunks as they arrive from the LLM

    Raises:
        VendorAPIOverloadedError: If API is overloaded after retries
        VendorAPIRateLimitError: If rate limit exceeded after retries
        litellm exceptions: Various litellm exceptions if request fails
    """
    max_retries = 5
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            response = completion(**completion_kwargs)

            # Try to get the first chunk to trigger any immediate exceptions
            first_chunk = None
            response_iter = iter(response)
            try:
                first_chunk = next(response_iter)
            except StopIteration:
                # Empty response
                return

            # Yield the first chunk
            content = first_chunk.choices[0].delta.content
            if content is not None:
                yield content

            # Now stream the rest normally
            for chunk in response_iter:
                content = chunk.choices[0].delta.content
                if content is not None:
                    yield content

            return  # Success, exit retry loop

        except (
            VendorAPIOverloadedError,
            VendorAPIRateLimitError,
            litellm.RateLimitError,
            litellm.InternalServerError,
            litellm.ServiceUnavailableError,
            litellm.APIConnectionError,
            litellm.Timeout,
        ):
            if attempt == max_retries - 1:
                # Last attempt, re-raise the exception
                raise

            delay = base_delay * (2**attempt)
            time.sleep(delay)
            continue


def get_completion(
    llm_config: LLMConfig,
    messages: List[dict],
    stream: bool = False,
    use_cache: bool = True,
    json_mode: bool = False,
    session_id: Optional[str] = None,
    langfuse_span: Optional[Any] = None,
    **kwargs,
) -> Iterator[str]:
    """Get completion from LLM with optional streaming and caching support.

    Args:
        llm_config: LLM configuration containing model and API key
        messages: List of message dictionaries to send to the LLM
        stream: If True, returns an iterator of response chunks
        use_cache: If True and caching is enabled, will try to use cached responses
        json_mode: If True, instructs the model to return a JSON response
        session_id: Optional session ID to associate with the generation
        langfuse_span: Optional parent span for Langfuse tracing
        **kwargs: Additional arguments passed to litellm.completion

    Returns:
        An iterator of response text (single item for non-streaming)
    """

    messages = remove_empty_messages(messages)
    # messages = consolidate_messages(messages)
    messages = ensure_upto_N_cached_messages(messages)

    # Apply playbooks-lm preprocessing if needed (before Langfuse logging)
    if "playbooks-lm" in llm_config.model.lower():
        messages = playbooks_handler.preprocess_messages(messages.copy())

    completion_kwargs = {
        "model": llm_config.model,
        "api_key": llm_config.api_key,
        "messages": messages.copy(),
        "max_completion_tokens": llm_config.max_completion_tokens,
        "stream": stream,
        "temperature": llm_config.temperature,
        **kwargs,
    }

    # Add response_format for JSON mode if supported by the model
    if json_mode:
        params = get_supported_openai_params(model=llm_config.model)
        if "response_format" in params:
            completion_kwargs["response_format"] = {"type": "json_object"}

    # Initialize Langfuse tracing if available
    langfuse_span_obj = None
    if langfuse_span is None:
        langfuse_helper = LangfuseHelper.instance()
        if langfuse_helper is not None:
            langfuse_span_obj = langfuse_helper.trace(
                name="llm_call",
                metadata={"model": llm_config.model, "session_id": session_id},
            )
    else:
        langfuse_span_obj = langfuse_span

    langfuse_generation = None
    if langfuse_span_obj is not None:
        langfuse_generation = langfuse_span_obj.generation(
            model=llm_config.model,
            model_parameters={
                "maxTokens": completion_kwargs["max_completion_tokens"],
                "temperature": completion_kwargs["temperature"],
            },
            input=messages,
            session_id=session_id,
            metadata={"stream": stream},
        )

    # Try to get response from cache if enabled
    if llm_cache_enabled and use_cache and cache is not None:
        cache_key = custom_get_cache_key(**completion_kwargs)
        cache_value = cache.get(cache_key)

        if cache_value is not None:
            if langfuse_generation:
                langfuse_generation.update(metadata={"cache_hit": True})
                langfuse_generation.end(output=str(cache_value))
                langfuse_generation.update(cost_details={"input": 0, "output": 0})
                LangfuseHelper.flush()

            if stream:
                for chunk in cache_value:
                    yield chunk
            else:
                yield cache_value

            return

    # Get response from LLM
    full_response: Union[str, List[str]] = [] if stream else ""
    error_occurred = False
    try:
        if langfuse_generation:
            langfuse_generation.update(metadata={"cache_hit": False})

        if stream:
            for chunk in _make_completion_request_stream(completion_kwargs):
                full_response.append(chunk)  # type: ignore
                yield chunk
            full_response = "".join(full_response)  # type: ignore
        else:
            full_response = _make_completion_request(completion_kwargs)
            yield full_response
    except Exception as e:
        error_occurred = True
        if langfuse_generation:
            langfuse_generation.end(error=str(e))
            LangfuseHelper.flush()
        raise e  # Re-raise the exception to be caught by the decorator if applicable
    finally:
        # Update cache and Langfuse
        if (
            not error_occurred
            and llm_cache_enabled
            and use_cache
            and cache is not None
            and full_response is not None
            and len(full_response) > 0
        ):
            full_response = str(full_response)
            cache.set(cache_key, full_response)

        if langfuse_generation and not error_occurred:
            # Only update if no exception occurred
            langfuse_generation.end(output=full_response)
            LangfuseHelper.flush()


def remove_empty_messages(messages: List[dict]) -> List[dict]:
    """Remove empty messages from the list.

    Filters out messages with empty or whitespace-only content.

    Args:
        messages: List of message dictionaries

    Returns:
        Filtered list with empty messages removed
    """
    return [message for message in messages if message["content"].strip()]


def get_messages_for_prompt(prompt: str) -> List[dict]:
    """Convert a raw prompt into a properly formatted message list.

    If the prompt contains a system prompt delimiter, it will be split into
    separate system and user messages. Otherwise, treated as a system message.

    Args:
        prompt: The raw prompt text, potentially containing a system/user split

    Returns:
        A list of message dictionaries formatted for LLM API calls
    """
    if SYSTEM_PROMPT_DELIMITER in prompt:
        system, user = prompt.split(SYSTEM_PROMPT_DELIMITER)

        return [
            SystemPromptLLMMessage(system.strip()).to_full_message(),
            UserInputLLMMessage(user.strip()).to_full_message(),
        ]
    return [UserInputLLMMessage(prompt.strip()).to_full_message()]


def consolidate_messages(messages: List[dict]) -> List[dict]:
    """Consolidate consecutive messages where possible.

    Groups consecutive messages with the same role and combines them into single
    messages. Handles cache control markers and preserves up to 1 cached message
    per role group.

    Args:
        messages: List of message dictionaries to consolidate

    Returns:
        Consolidated list of messages with consecutive same-role messages merged
    """

    # First, group messages that can be combined into a single message
    message_groups = []
    current_group = []
    current_role = messages[0]["role"]

    for message in messages:
        if "cache_control" in message and message["role"] == current_role:
            # Include the cached message in the current group
            current_group.append(message)
            message_groups.append(current_group)

            # Start a new group
            current_group = []
        elif message["role"] == current_role:
            current_group.append(message)
        else:
            # New role, so start a new group with this message in it
            message_groups.append(current_group)
            current_group = [message]
            current_role = message["role"]

    if current_group:
        message_groups.append(current_group)

    # Now, consolidate each group into a single message
    messages = []
    for group in message_groups:
        if not group:
            continue
        contents = []
        cache_control = False

        # Collect all contents and track if there is a cached message
        for message in group:
            contents.append(message["content"])
            if "cache_control" in message:
                cache_control = True

        # Join all contents into a single string
        contents = "\n\n".join(contents)

        # Add the consolidated message to the list
        from playbooks.llm_messages import LLMMessage

        if cache_control:
            llm_msg = LLMMessage(
                contents, LLMMessageRole(group[0]["role"]), cached=True
            )
        else:
            llm_msg = LLMMessage(
                contents, LLMMessageRole(group[0]["role"]), cached=False
            )
        messages.append(llm_msg.to_full_message())

    return messages


def ensure_upto_N_cached_messages(messages: List[dict]) -> List[dict]:
    """Ensure that there are at most N cached messages in the list.

    Scans messages in reverse order and removes cache_control markers from
    messages beyond the limit. System messages are always preserved regardless
    of cache status.

    Args:
        messages: List of message dictionaries (modified in-place)

    Returns:
        Modified message list with cache_control markers removed from excess messages
    """

    max_cached_messages = 4 - 1  # Keep one for the System message
    count_cached_messages = 0

    # Cached messages are those with a cache_control field set
    # Scan in reverse order to keep the last N cached messages
    for message in reversed(messages):
        # If we've already found N cached messages, remove cache_control from all earlier messages
        if count_cached_messages >= max_cached_messages:
            # Don't remove cache_control from the System message
            if message["role"] == LLMMessageRole.SYSTEM:
                continue

            # Remove cache_control from all other messages
            if "cache_control" in message:
                del message["cache_control"]

            continue

        # If we haven't found N cached messages yet, check if this message is cached
        if "cache_control" in message:
            count_cached_messages += 1

    return messages

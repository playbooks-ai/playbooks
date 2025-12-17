"""LLM helper utilities for making completion requests with caching and tracing.

This module provides a unified interface for LLM interactions, including:
- Streaming and non-streaming completion requests
- Automatic retry logic for rate limits and overloads
- LLM response caching (disk or Redis)
- Event-based telemetry integration
- Message preprocessing and consolidation
"""

import asyncio
import hashlib
import json
import logging
import os
import queue
import tempfile
import threading
import time
from functools import wraps
from typing import Any, Callable, Iterator, List, Optional, TypeVar, Union

import litellm
from litellm import completion, get_supported_openai_params

try:
    from diskcache import Cache
except ImportError:
    Cache = None

try:
    from redis import Redis
except ImportError:
    Redis = None

from playbooks.config import config
from playbooks.core.constants import SYSTEM_PROMPT_DELIMITER
from playbooks.core.enums import LLMMessageRole
from playbooks.core.events import LLMCallEndedEvent, LLMCallStartedEvent
from playbooks.core.exceptions import (
    CompilationError,
    VendorAPIOverloadedError,
    VendorAPIRateLimitError,
)
from playbooks.infrastructure.logging.debug_logger import debug
from playbooks.llm.messages import (
    LLMMessage,
    UserInputLLMMessage,
)

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
# litellm._turn_on_debug()

# Initialize the Playbooks-LM handler
playbooks_handler = PlaybooksLMHandler()

# Store the original completion function
_original_completion = completion


def ensure_async_iterable(obj: Any):
    """Coerce an iterable into an async iterable.

    This keeps call sites compatible with tests that monkeypatch `get_completion`
    to return a plain (sync) iterator while production code returns an async
    generator.
    """
    if hasattr(obj, "__aiter__"):
        return obj

    if hasattr(obj, "__iter__"):

        async def _gen():
            for item in obj:
                yield item

        return _gen()

    raise TypeError(f"Expected async iterable or iterable, got {type(obj).__name__}")


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
        cache_dir = (
            llm_cache_path or tempfile.TemporaryDirectory(prefix="llm_cache_").name
        )
        cache = Cache(directory=cache_dir)

    elif llm_cache_type == "redis":
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
        CompilationError: If response is truncated due to token limit or content is empty
        VendorAPIOverloadedError: If API is overloaded after retries
        VendorAPIRateLimitError: If rate limit exceeded after retries
        litellm exceptions: Various litellm exceptions if request fails
    """
    response = completion(**completion_kwargs)
    choice = response["choices"][0]
    finish_reason = choice.get("finish_reason")
    content = choice["message"]["content"]

    # Check for token limit truncation
    if finish_reason == "length":
        raise CompilationError(
            "LLM response was truncated due to token limit.\n"
            "Increase max_completion_tokens in playbooks.toml:\n\n"
            "[model]\n"
            "max_completion_tokens = 15000  # Increase this value"
        )

    # Validate content is not empty
    if not content or not content.strip():
        raise CompilationError(
            f"LLM returned empty content (finish_reason: {finish_reason}).\n"
            "This may indicate the model couldn't generate a valid response."
        )

    return content


def _make_completion_request_stream_sync(completion_kwargs: dict) -> Iterator[str]:
    """Synchronous helper that performs the actual streaming.

    This runs in a thread pool to avoid blocking the event loop.
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

            # Stream the rest
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


async def _make_completion_request_stream(completion_kwargs: dict):
    """Make a streaming completion request to the LLM without blocking the event loop.

    Runs the synchronous streaming in a thread pool to keep the event loop responsive.

    Args:
        completion_kwargs: Dictionary of arguments for litellm.completion

    Yields:
        Response text chunks as they arrive from the LLM

    Raises:
        VendorAPIOverloadedError: If API is overloaded after retries
        VendorAPIRateLimitError: If rate limit exceeded after retries
        litellm exceptions: Various litellm exceptions if request fails
    """
    # Create a queue to transfer chunks from thread to async code
    chunk_queue = queue.Queue()
    exception_holder = []

    def _stream_in_thread():
        """Run the synchronous streaming in a background thread."""
        try:
            for chunk in _make_completion_request_stream_sync(completion_kwargs):
                chunk_queue.put(("chunk", chunk))
            chunk_queue.put(("done", None))
        except Exception as e:
            exception_holder.append(e)
            chunk_queue.put(("error", e))

    # Start streaming in background thread
    stream_thread = threading.Thread(target=_stream_in_thread, daemon=True)
    stream_thread.start()

    # Yield chunks as they arrive, without blocking the event loop
    while True:
        # Check queue in thread pool to avoid blocking
        try:
            item_type, item_value = await asyncio.to_thread(
                chunk_queue.get, timeout=0.1
            )
        except queue.Empty:
            # No chunk yet, yield control and try again
            await asyncio.sleep(0.01)
            continue

        if item_type == "chunk":
            yield item_value
            # Yield control after each chunk
            await asyncio.sleep(0)
        elif item_type == "error":
            raise item_value
        elif item_type == "done":
            break


def _check_llm_calls_allowed() -> bool:
    """Check if LLM calls are allowed in the current context.

    This is controlled by the _ALLOW_LLM_CALLS environment variable,
    which is set by the test infrastructure based on test type:
    - Unit tests: _ALLOW_LLM_CALLS=false (LLM calls blocked)
    - Integration tests: _ALLOW_LLM_CALLS=true (LLM calls allowed)
    - Production/default: Not set (LLM calls allowed)

    Note: Using _ALLOW_LLM_CALLS (not PLAYBOOKS_*) to avoid being picked up
    by the Playbooks config loader.

    Returns:
        True if LLM calls are allowed, False if they should be blocked
    """
    allow_llm = os.environ.get("_ALLOW_LLM_CALLS", "true").lower()
    return allow_llm == "true"


async def get_completion(
    llm_config: LLMConfig,
    messages: List[dict],
    stream: bool = False,
    use_cache: bool = True,
    json_mode: bool = False,
    session_id: Optional[str] = None,
    execution_id: Optional[int] = None,
    event_bus: Optional[Any] = None,
    agent_id: Optional[str] = None,
    response_validator: Optional[Callable[[str], bool]] = None,
    **kwargs,
):
    """Get completion from LLM with optional streaming and caching support.

    Args:
        llm_config: LLM configuration containing model and API key
        messages: List of message dictionaries to send to the LLM
        stream: If True, returns an iterator of response chunks
        use_cache: If True and caching is enabled, will try to use cached responses
        json_mode: If True, instructs the model to return a JSON response
        session_id: Optional session ID to associate with the generation
        execution_id: Optional counter identifying this LLM call for tracing
        event_bus: Optional event bus for telemetry events
        response_validator: Optional function to validate responses before caching.
                          Should return True if response is valid, False otherwise.
        **kwargs: Additional arguments passed to litellm.completion

    Returns:
        An iterator of response text (single item for non-streaming)
    """
    cache_key = None

    # Check if LLM calls are allowed in the current context
    if not _check_llm_calls_allowed():
        raise RuntimeError(
            "LLM calls are not allowed in this context (likely a unit test).\n"
            "This test should be moved to tests/integration/ or the LLM call should be mocked.\n"
            "Use @patch('playbooks.utils.llm_helper.get_completion') to mock LLM calls in unit tests."
        )

    # Estimate input token count
    input_token_count = (
        sum(len(str(msg.get("content", ""))) for msg in messages) // 4
    )  # Rough estimate

    # Publish LLM call started event
    if event_bus and agent_id and session_id:
        event_bus.publish(
            LLMCallStartedEvent(
                session_id=session_id,
                agent_id=agent_id,
                model=llm_config.model,
                input_tokens=input_token_count,
                input=messages,
                stream=stream,
                metadata={"execution_id": execution_id, "json_mode": json_mode},
            )
        )

    messages = remove_empty_messages(messages)
    # messages = consolidate_messages(messages)
    messages = ensure_upto_N_cached_messages(messages)

    # Apply playbooks-lm preprocessing if needed (before telemetry events)
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
        if "reasoning_effort" in params:
            completion_kwargs["reasoning_effort"] = "low"

    # Try to get response from cache if enabled
    if llm_cache_enabled and use_cache and cache is not None:
        cache_key = custom_get_cache_key(**completion_kwargs)
        cache_value = cache.get(cache_key)

        if cache_value is not None:
            debug(f"cache_hit: {True}", cache_key=cache_key)

            if stream:
                for chunk in cache_value:
                    yield chunk
            else:
                yield cache_value

            # Publish LLM call ended event for cache hit
            if event_bus and agent_id and session_id:
                output_value = str(cache_value)
                output_token_count = len(output_value) // 4  # Rough estimate

                event_bus.publish(
                    LLMCallEndedEvent(
                        session_id=session_id,
                        agent_id=agent_id,
                        model=llm_config.model,
                        output_tokens=output_token_count,
                        output=output_value,
                        error=None,
                        cache_hit=True,
                    )
                )

            return

    # Get response from LLM
    full_response: Union[str, List[str]] = [] if stream else ""
    error_occurred = False
    error_msg = None
    try:
        debug(f"cache_hit: {False}", cache_key=cache_key)

        if stream:
            async for chunk in _make_completion_request_stream(completion_kwargs):
                full_response.append(chunk)  # type: ignore
                yield chunk
            full_response = "".join(full_response)  # type: ignore
        else:
            full_response = _make_completion_request(completion_kwargs)
            yield full_response
    except Exception as e:
        error_occurred = True
        error_msg = str(e)
        raise e  # Re-raise the exception to be caught by the decorator if applicable
    finally:
        # Update cache - only store valid responses
        if (
            not error_occurred
            and llm_cache_enabled
            and use_cache
            and cache is not None
            and full_response is not None
            and len(full_response) > 0
        ):
            if isinstance(full_response, list):
                full_response = "".join(full_response)
            full_response = str(full_response)

            # Validate response before caching if validator provided
            if response_validator is None or response_validator(full_response):
                cache.set(cache_key, full_response)
            else:
                debug(
                    "Response validation failed - not caching invalid response",
                    cache_key=cache_key,
                )

        # Publish LLM call ended event
        if event_bus and agent_id and session_id:
            output_token_count = (
                len(str(full_response)) // 4 if full_response else 0
            )  # Rough estimate
            output_value = full_response if not error_occurred else None

            event_bus.publish(
                LLMCallEndedEvent(
                    session_id=session_id,
                    agent_id=agent_id,
                    model=llm_config.model,
                    output_tokens=output_token_count,
                    output=output_value,
                    error=error_msg,
                    cache_hit=(
                        cache_key is not None and cache_value is not None
                        if "cache_value" in locals()
                        else False
                    ),
                )
            )


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

        messages = [
            {"role": LLMMessageRole.SYSTEM, "content": system.strip()},
            UserInputLLMMessage(instruction=user.strip()).to_full_message(),
        ]
        # System message should always be cached
        messages[0]["cache_control"] = {"type": "ephemeral"}
        return messages
    return [UserInputLLMMessage(instruction=prompt.strip()).to_full_message()]


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
        llm_msg = LLMMessage(contents, LLMMessageRole(group[0]["role"]))
        msg_dict = llm_msg.to_full_message()
        if cache_control:
            msg_dict["cache_control"] = {"type": "ephemeral"}
        messages.append(msg_dict)

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

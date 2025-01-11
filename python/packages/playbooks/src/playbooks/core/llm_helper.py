from typing import AsyncIterator

from litellm import acompletion

from playbooks.config import LLMConfig


async def get_completion(
    config: LLMConfig, mock_response: str = None, stream: bool = False, **kwargs
) -> AsyncIterator[str]:
    """Get completion from LLM with optional streaming support."""
    if mock_response is not None:
        if stream:

            async def mock_stream():
                for chunk in mock_response.split():
                    yield {"choices": [{"delta": {"content": chunk}}]}

            return mock_stream()
        return {"choices": [{"message": {"content": mock_response}}]}

    # Remove conversation from kwargs if present since Anthropic doesn't accept it
    kwargs.pop("conversation", None)
    return await acompletion(
        model=config.model, api_key=config.api_key, stream=stream, **kwargs
    )

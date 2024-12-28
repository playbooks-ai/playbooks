from typing import Optional, Union, Iterator, AsyncIterator
from litellm import acompletion
from playbooks.config import DEFAULT_MODEL

class PlaybooksRunner:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None, **kwargs):
        """
        Initialize runner with a model
        
        Args:
            model: Model identifier (e.g. 'gpt-4', 'claude-3', etc)
            api_key: Optional API key (can also be set via env vars)
            **kwargs: Additional arguments passed to completion
        """
        self.model = model
        self.api_key = api_key
        self.kwargs = kwargs
        
    async def run(self, playbooks: str, stream: bool = False, **kwargs) -> str:
        """Run playbooks using the configured model"""
        if stream:
            return self.stream(playbooks, **kwargs)
            
        response = await acompletion(
            model=self.model,
            messages=[{"role": "user", "content": playbooks}],
            api_key=self.api_key,
            **{**self.kwargs, **kwargs}
        )
        return response.choices[0].message.content

    async def stream(self, playbooks: str, **kwargs) -> AsyncIterator[str]:
        """Run playbooks using the configured model with streaming enabled"""
        response = await acompletion(
            model=self.model,
            messages=[{"role": "user", "content": playbooks}],
            api_key=self.api_key,
            stream=True,
            **{**self.kwargs, **kwargs}
        )
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

async def run(playbooks: str, **kwargs) -> str:
    """Convenience function to run playbooks"""
    runner = PlaybooksRunner(**kwargs)
    return await runner.run(playbooks)
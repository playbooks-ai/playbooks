from typing import Optional, Union, Iterator, AsyncIterator
from playbooks.llms.base import BaseLLM
from playbooks.llms.openai import OpenAILLM
from playbooks.llms.anthropic import AnthropicLLM
from playbooks.llms.vertexai import VertexAILLM

class PlaybookRunner:
    def __init__(self, llm: Optional[Union[BaseLLM, str]] = None, **kwargs):
        """
        Initialize runner with an LLM client
        
        Args:
            llm: LLM client instance or string identifier ('openai', 'anthropic', etc)
            **kwargs: Additional arguments passed to LLM client
        """
        if isinstance(llm, str):
            llm = self._get_llm_client(llm, **kwargs)
            
        self.llm = llm
        
    def _get_llm_client(self, provider: str, **kwargs) -> BaseLLM:
        providers = {
            'openai': OpenAILLM,
            'anthropic': AnthropicLLM,
            'vertexai': VertexAILLM
        }
        if provider not in providers:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        return providers[provider](**kwargs)
        
    def run(self, playbooks: str, stream: bool = False, **kwargs) -> Union[str, Iterator[str]]:
        """Run playbooks using the configured LLM"""
        if not self.llm:
            return "No LLM configured"
            
        if stream:
            return self.stream(playbooks, **kwargs)
        return self.llm.generate(playbooks, **kwargs)

    async def stream(self, playbooks: str, **kwargs) -> AsyncIterator[str]:
        """
        Run playbooks using the configured LLM with streaming enabled
        """
        for chunk in self.llm.generate_stream(playbooks, **kwargs):
            yield chunk

def run(playbooks: str, **kwargs) -> str:
    """Convenience function to run playbooks"""
    runner = PlaybookRunner(**kwargs)
    return runner.run(playbooks) 
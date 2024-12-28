from typing import Optional, Union
from ..llms import BaseLLM, OpenAILLM, AnthropicLLM, VertexAILLM

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
        
    def run(self, playbooks: str, **kwargs) -> str:
        """Run playbooks using the configured LLM"""
        if self.llm:
            return self.llm.generate(playbooks, **kwargs)
        else:
            return "No LLM configured"

def run(playbooks: str, **kwargs) -> str:
    """Convenience function to run playbooks"""
    runner = PlaybookRunner(**kwargs)
    return runner.run(playbooks) 
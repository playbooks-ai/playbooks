from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Iterator

class BaseLLM(ABC):
    """Base class for LLM implementations"""
    
    @abstractmethod
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize the LLM client"""
        pass
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response from the LLM"""
        pass

    @abstractmethod
    def generate_stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Generate streaming response from the LLM"""
        pass
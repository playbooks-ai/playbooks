from typing import Optional
import anthropic
from .base import BaseLLM

class AnthropicLLM(BaseLLM):
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize Anthropic client"""
        if not api_key:
            raise ValueError("API key is required for Anthropic")
            
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = kwargs.get("model", "claude-3-opus-20240229")
        
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response using Anthropic's Claude"""
        response = self.client.messages.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI agent that executes playbooks."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return response.content[0].text 
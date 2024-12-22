from typing import Optional, Iterator
import anthropic
from .base import BaseLLM
import os

class AnthropicLLM(BaseLLM):
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize Anthropic client"""
        api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("API key is required for Anthropic")
            
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = kwargs.get("model") or "claude-3-5-sonnet-20241022"
        
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response using Anthropic's Claude"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0,
            system="You are an AI agent that executes playbooks.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return response.content[0].text 

    def generate_stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Generate streaming response using Anthropic's Claude"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0,
            system="You are an AI agent that executes playbooks.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            stream=True
        )
        for message in response:
            if message.type == "content_block_delta" and message.delta.text:
                yield message.delta.text
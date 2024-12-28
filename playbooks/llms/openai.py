from typing import Optional
import openai
from .base import BaseLLM

class OpenAILLM(BaseLLM):
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        if api_key:
            openai.api_key = api_key
        self.client = openai.OpenAI()
        self.model = kwargs.get("model", "gpt-4")
        
    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an AI agent that executes playbooks."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content 
from typing import Optional
import vertexai.generative_models as gm
from .base import BaseLLM

class VertexAILLM(BaseLLM):
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize Vertex AI client"""
        # Note: Vertex AI typically uses application default credentials or explicit project settings
        # api_key is kept in signature for consistency with BaseLLM
        
        self.model = kwargs.get("model", "gemini-pro")
        self.client = gm.GenerativeModel(self.model)
        
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response using Vertex AI's Gemini"""
        response = self.client.generate_content(
            contents=[
                gm.Content(
                    role="system",
                    parts=[gm.Part.from_text("You are an AI agent that executes playbooks.")]
                ),
                gm.Content(
                    role="user",
                    parts=[gm.Part.from_text(prompt)]
                )
            ]
        )
        return response.text 
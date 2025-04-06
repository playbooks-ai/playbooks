import os
from dataclasses import dataclass
from typing import Optional

from playbooks.utils.env_loader import load_environment

from .constants import DEFAULT_MODEL

# Load environment variables from .env files
load_environment()


@dataclass
class LLMConfig:
    """
    Configuration class for language model settings.

    This class manages model selection and API key configuration for different
    LLM providers (OpenAI, Anthropic, Google). It automatically retrieves
    appropriate API keys from environment variables based on the selected model.

    Attributes:
        model: The language model to use. If None, uses MODEL env var or DEFAULT_MODEL.
        api_key: API key for the model provider. If None, determined by model type.
    """

    model: Optional[str] = None
    api_key: Optional[str] = None

    def __post_init__(self):
        """Initialize with default values from environment variables if needed."""
        # Set model from environment or default
        self.model = self.model or os.environ.get("MODEL") or DEFAULT_MODEL

        # Set appropriate API key based on model provider if none was provided
        if self.api_key is None:
            if "claude" in self.model:
                self.api_key = os.environ.get("ANTHROPIC_API_KEY")
            elif "gemini" in self.model:
                self.api_key = os.environ.get("GEMINI_API_KEY")
            elif "groq" in self.model:
                self.api_key = os.environ.get("GROQ_API_KEY")
            else:
                # Default to OpenAI for other models
                self.api_key = os.environ.get("OPENAI_API_KEY")

    def to_dict(self) -> dict:
        """Convert configuration to a dictionary."""
        return {"model": self.model, "api_key": self.api_key}

import os
from dataclasses import dataclass
from typing import Optional

from ..config import config
from .env_loader import load_environment

# Load environment variables from .env files
load_environment()


@dataclass
class LLMConfig:
    """
    Configuration class for language model settings.

    This class manages model selection and API key configuration for different
    LLM providers (OpenAI, Anthropic, Google). Model configuration comes from
    the TOML config system, with environment variable override support.
    API keys are always loaded from environment variables for security.

    Attributes:
        model: The language model to use. If None, loaded from config system.
        provider: The model provider. If None, loaded from config system.
        temperature: The model temperature. If None, loaded from config system.
        api_key: API key for the model provider. If None, determined by model type.
    """

    model: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    api_key: Optional[str] = None

    def __post_init__(self):
        """Initialize with default values from config system and environment variables."""
        # Load model configuration from config system (which handles env overrides)
        try:
            # Set model name if not explicitly provided
            if self.model is None:
                self.model = config.model.default.name

            # Set provider if not explicitly provided
            if self.provider is None:
                self.provider = config.model.default.provider

            # Set temperature if not explicitly provided
            if self.temperature is None:
                self.temperature = config.model.default.temperature

        except Exception:
            # Fallback to constants/defaults if config loading fails
            if self.model is None:
                from ..constants import DEFAULT_MODEL

                self.model = DEFAULT_MODEL
            if self.provider is None:
                self.provider = "openai"  # Default provider
            if self.temperature is None:
                self.temperature = 0.2  # Default temperature

        # Set appropriate API key based on model provider if none was provided
        if not self.api_key:
            # Use provider field to determine API key, fallback to model name detection
            provider = self.provider.lower() if self.provider else ""
            model = self.model.lower() if self.model else ""

            api_key_env_var = None
            if provider == "anthropic" or "claude" in model:
                api_key_env_var = "ANTHROPIC_API_KEY"
            elif provider == "google" or "gemini" in model:
                api_key_env_var = "GEMINI_API_KEY"
            elif "groq" in provider or "groq" in model:
                api_key_env_var = "GROQ_API_KEY"
            elif "openrouter" in provider or "openrouter" in model:
                api_key_env_var = "OPENROUTER_API_KEY"
            else:
                # Default to OpenAI for other models
                api_key_env_var = "OPENAI_API_KEY"

            self.api_key = os.environ.get(api_key_env_var)

        if not self.api_key:
            raise ValueError(
                f"Set {api_key_env_var} environment variable to use model {self.model}"
            )

    def to_dict(self) -> dict:
        """Convert configuration to a dictionary."""
        return {
            "model": self.model,
            "provider": self.provider,
            "temperature": self.temperature,
            "api_key": self.api_key,
        }

    def copy(self) -> "LLMConfig":
        """Create a copy of the configuration."""
        return LLMConfig(
            model=self.model,
            provider=self.provider,
            temperature=self.temperature,
            api_key=self.api_key,
        )

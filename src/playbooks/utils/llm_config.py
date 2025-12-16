import os
from dataclasses import dataclass
from typing import Optional

from litellm import common_cloud_provider_auth_params, get_llm_provider

from playbooks.config import config

from .env_loader import load_environment

# Load environment variables from .env files
load_environment()


def _uses_credential_auth(model: str, provider: str) -> bool:
    """Check if the model/provider uses credential-based authentication.

    Some providers (Vertex AI, AWS Bedrock, etc.) use environment-based
    credentials (gcloud ADC, AWS IAM roles) instead of API keys. For these,
    we should not require an api_key and let LiteLLM handle authentication.

    Uses LiteLLM's common_cloud_provider_auth_params to determine which
    providers use cloud-based authentication, plus additional providers
    that use IAM-based auth (like sagemaker).

    Args:
        model: The model name/identifier (e.g., "vertex_ai/gemini-1.5-flash")
        provider: The provider name (e.g., "vertex_ai")

    Returns:
        True if the provider uses credential-based auth, False otherwise
    """
    # Get the list of cloud providers from LiteLLM, plus sagemaker which also
    # uses AWS IAM credentials but isn't in the common_cloud_provider_auth_params list
    cloud_providers = set(common_cloud_provider_auth_params.get("providers", []))
    cloud_providers.add("sagemaker")

    # Check explicit provider first - if user specified a provider, trust it
    if provider:
        return provider.lower() in cloud_providers

    # Only use model-based detection if no explicit provider was given
    # Use lowercase model to handle case-insensitivity
    if model:
        try:
            _, custom_provider, *_ = get_llm_provider(model.lower())
            if custom_provider and custom_provider.lower() in cloud_providers:
                return True
        except Exception:
            # If LiteLLM can't determine the provider, fall through
            pass

    return False


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
        max_completion_tokens: Maximum completion tokens. If None, loaded from config system.
        api_key: API key for the model provider. If None, determined by model type.
    """

    model: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_completion_tokens: Optional[int] = None
    api_key: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize with default values from config system and environment variables.

        Loads model configuration from config system (which handles env overrides)
        and determines API key based on provider/model type. Falls back to defaults
        if config loading fails.

        Raises:
            ValueError: If required API key environment variable is not set
        """
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

            # Set max_completion_tokens if not explicitly provided
            if self.max_completion_tokens is None:
                self.max_completion_tokens = config.model.default.max_completion_tokens

        except Exception:
            # Fallback to constants/defaults if config loading fails
            if self.model is None:
                from playbooks.core.constants import DEFAULT_MODEL

                self.model = DEFAULT_MODEL
            if self.provider is None:
                self.provider = "openai"  # Default provider
            if self.temperature is None:
                self.temperature = 0.2  # Default temperature
            if self.max_completion_tokens is None:
                self.max_completion_tokens = 7500  # Default max completion tokens

        # Set appropriate API key based on model provider if none was provided
        if not self.api_key:
            # Check if this provider uses credential-based auth (Vertex AI, Bedrock, etc.)
            # These providers don't need an api_key - LiteLLM handles auth via environment
            if _uses_credential_auth(self.model, self.provider):
                # Let LiteLLM handle authentication via gcloud ADC, AWS credentials, etc.
                return

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
            elif "xai" in provider or "xai" in model:
                api_key_env_var = "XAI_API_KEY"
            else:
                # Default to OpenAI for other models
                api_key_env_var = "OPENAI_API_KEY"

            self.api_key = os.environ.get(api_key_env_var)

            if not self.api_key:
                raise ValueError(
                    f"Set {api_key_env_var} environment variable to use model {self.model}"
                )

    def to_dict(self) -> dict:
        """Convert configuration to a dictionary.

        Returns:
            Dictionary containing all configuration fields
        """
        return {
            "model": self.model,
            "provider": self.provider,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_completion_tokens,
            "api_key": self.api_key,
        }

    def copy(self) -> "LLMConfig":
        """Create a copy of this LLM configuration.

        Returns:
            New LLMConfig instance with same values
        """
        return LLMConfig(
            model=self.model,
            provider=self.provider,
            temperature=self.temperature,
            max_completion_tokens=self.max_completion_tokens,
            api_key=self.api_key,
        )

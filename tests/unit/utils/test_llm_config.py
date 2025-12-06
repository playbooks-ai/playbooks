"""Tests for LLMConfig and credential-based authentication handling.

This module tests that credential-based providers (Vertex AI, Bedrock, Sagemaker)
can be used without API keys, letting LiteLLM handle authentication via
environment credentials (gcloud ADC, AWS IAM, etc.).
"""

import os
from unittest.mock import patch

import pytest

from playbooks.utils.llm_config import (
    LLMConfig,
    _uses_credential_auth,
)


class TestUsesCredentialAuth:
    """Test the _uses_credential_auth helper function."""

    def test_vertex_ai_model_prefix(self):
        """Test that vertex_ai/ model prefix is detected."""
        assert _uses_credential_auth("vertex_ai/gemini-1.5-flash", "") is True
        assert _uses_credential_auth("vertex_ai/gemini-pro", "") is True
        assert _uses_credential_auth("vertex_ai/claude-sonnet-4", "") is True

    def test_bedrock_model_prefix(self):
        """Test that bedrock/ model prefix is detected."""
        assert _uses_credential_auth("bedrock/anthropic.claude-v2", "") is True
        assert _uses_credential_auth("bedrock/amazon.titan-text-lite-v1", "") is True

    def test_sagemaker_model_prefix(self):
        """Test that sagemaker/ model prefix is detected."""
        assert _uses_credential_auth("sagemaker/my-endpoint", "") is True

    def test_vertex_ai_provider(self):
        """Test that vertex_ai provider is detected."""
        assert _uses_credential_auth("gemini-1.5-flash", "vertex_ai") is True
        assert _uses_credential_auth("claude-sonnet-4", "vertex_ai") is True

    def test_bedrock_provider(self):
        """Test that bedrock provider is detected."""
        assert _uses_credential_auth("anthropic.claude-v2", "bedrock") is True

    def test_sagemaker_provider(self):
        """Test that sagemaker provider is detected."""
        assert _uses_credential_auth("my-model", "sagemaker") is True

    def test_api_key_providers_not_detected(self):
        """Test that API key providers are not detected as credential-based."""
        assert _uses_credential_auth("claude-3-opus", "anthropic") is False
        assert _uses_credential_auth("gpt-4", "openai") is False
        assert _uses_credential_auth("gemini-pro", "google") is False
        assert _uses_credential_auth("groq/llama-2", "groq") is False

    def test_case_insensitive(self):
        """Test that detection is case-insensitive."""
        assert _uses_credential_auth("VERTEX_AI/gemini-pro", "") is True
        assert _uses_credential_auth("Bedrock/claude-v2", "") is True
        assert _uses_credential_auth("gemini-pro", "VERTEX_AI") is True

    def test_empty_values(self):
        """Test handling of empty model and provider."""
        assert _uses_credential_auth("", "") is False
        assert _uses_credential_auth(None, None) is False

    def test_uses_litellm_cloud_providers(self):
        """Test that detection uses LiteLLM's cloud provider list."""
        # These are the providers from LiteLLM's common_cloud_provider_auth_params
        # plus sagemaker which uses AWS IAM credentials
        from litellm import common_cloud_provider_auth_params

        cloud_providers = common_cloud_provider_auth_params.get("providers", [])
        assert "vertex_ai" in cloud_providers
        assert "bedrock" in cloud_providers
        # sagemaker is added manually since it also uses IAM auth


class TestLLMConfigCredentialAuth:
    """Test LLMConfig initialization with credential-based providers."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("playbooks.utils.llm_config.config")
    def test_vertex_ai_no_api_key_required(self, mock_config):
        """Test that Vertex AI models don't require an API key."""
        mock_config.model.default.name = "vertex_ai/gemini-1.5-flash"
        mock_config.model.default.provider = "vertex_ai"
        mock_config.model.default.temperature = 0.2
        mock_config.model.default.max_completion_tokens = 7500

        # Should not raise ValueError even without any API keys set
        config = LLMConfig()

        assert config.model == "vertex_ai/gemini-1.5-flash"
        assert config.provider == "vertex_ai"
        assert config.api_key is None  # No API key needed

    @patch.dict(os.environ, {}, clear=True)
    @patch("playbooks.utils.llm_config.config")
    def test_bedrock_no_api_key_required(self, mock_config):
        """Test that Bedrock models don't require an API key."""
        mock_config.model.default.name = "bedrock/anthropic.claude-v2"
        mock_config.model.default.provider = "bedrock"
        mock_config.model.default.temperature = 0.2
        mock_config.model.default.max_completion_tokens = 7500

        # Should not raise ValueError even without any API keys set
        config = LLMConfig()

        assert config.model == "bedrock/anthropic.claude-v2"
        assert config.provider == "bedrock"
        assert config.api_key is None

    @patch.dict(os.environ, {}, clear=True)
    @patch("playbooks.utils.llm_config.config")
    def test_vertex_ai_by_provider_only(self, mock_config):
        """Test that provider=vertex_ai is detected even without model prefix."""
        mock_config.model.default.name = "gemini-1.5-flash"  # No vertex_ai/ prefix
        mock_config.model.default.provider = "vertex_ai"
        mock_config.model.default.temperature = 0.2
        mock_config.model.default.max_completion_tokens = 7500

        # Should not raise ValueError
        config = LLMConfig()

        assert config.model == "gemini-1.5-flash"
        assert config.provider == "vertex_ai"
        assert config.api_key is None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True)
    @patch("playbooks.utils.llm_config.config")
    def test_anthropic_still_requires_api_key(self, mock_config):
        """Test that Anthropic models still require an API key."""
        mock_config.model.default.name = "claude-3-opus"
        mock_config.model.default.provider = "anthropic"
        mock_config.model.default.temperature = 0.2
        mock_config.model.default.max_completion_tokens = 7500

        config = LLMConfig()

        assert config.api_key == "test-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("playbooks.utils.llm_config.config")
    def test_anthropic_raises_without_api_key(self, mock_config):
        """Test that Anthropic models raise ValueError without API key."""
        mock_config.model.default.name = "claude-3-opus"
        mock_config.model.default.provider = "anthropic"
        mock_config.model.default.temperature = 0.2
        mock_config.model.default.max_completion_tokens = 7500

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            LLMConfig()

    @patch.dict(os.environ, {}, clear=True)
    @patch("playbooks.utils.llm_config.config")
    def test_explicit_api_key_preserved(self, mock_config):
        """Test that explicitly provided API key is preserved."""
        mock_config.model.default.name = "vertex_ai/gemini-1.5-flash"
        mock_config.model.default.provider = "vertex_ai"
        mock_config.model.default.temperature = 0.2
        mock_config.model.default.max_completion_tokens = 7500

        # Even for Vertex AI, if user provides an API key, keep it
        config = LLMConfig(api_key="explicit-key")

        assert config.api_key == "explicit-key"

"""Tests for the LLM client factory dispatch.

``create_llm_client`` lazily imports the provider-specific client and
constructs it. Native providers (anthropic/google/azure/bedrock) are matched
before the OpenAI-compatible fallthrough so their string check never imports
the OpenAI client. Azure/bedrock are skipped here (their SDKs are optional);
anthropic, google, and the openai-compatible path plus the unsupported-provider
error are covered.
"""

from unittest.mock import MagicMock

import pytest

from tradingagents.llm_clients import (
    anthropic_client,
    factory,
    google_client,
    openai_client,
)


@pytest.mark.unit
class TestCreateLlmClientDispatch:
    def test_unsupported_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            factory.create_llm_client("not-a-real-provider", "m")

    def test_anthropic_dispatches_to_anthropic_client(self, monkeypatch):
        mock = MagicMock()
        monkeypatch.setattr(anthropic_client, "AnthropicClient", mock)
        factory.create_llm_client("anthropic", "claude-3", base_url="http://x", extra="kw")
        mock.assert_called_once_with("claude-3", "http://x", extra="kw")

    def test_google_dispatches_to_google_client(self, monkeypatch):
        mock = MagicMock()
        monkeypatch.setattr(google_client, "GoogleClient", mock)
        factory.create_llm_client("google", "gemini-pro")
        mock.assert_called_once_with("gemini-pro", None)

    def test_provider_is_case_insensitive(self, monkeypatch):
        mock = MagicMock()
        monkeypatch.setattr(anthropic_client, "AnthropicClient", mock)
        factory.create_llm_client("AnThRoPiC", "claude-3")
        mock.assert_called_once_with("claude-3", None)

    def test_passes_base_url_and_kwargs_through(self, monkeypatch):
        mock = MagicMock()
        monkeypatch.setattr(anthropic_client, "AnthropicClient", mock)
        factory.create_llm_client(
            "anthropic", "claude-3", base_url="https://api.example.com",
            thinking_level="high", max_retries=4,
        )
        mock.assert_called_once_with(
            "claude-3", "https://api.example.com",
            thinking_level="high", max_retries=4,
        )

    def test_openai_compatible_dispatches_with_provider_kwarg(self, monkeypatch):
        mock = MagicMock()
        monkeypatch.setattr(openai_client, "OpenAIClient", mock)
        monkeypatch.setattr(openai_client, "is_openai_compatible", lambda p: True)
        factory.create_llm_client("deepseek", "deepseek-chat", base_url="http://x")
        mock.assert_called_once_with(
            "deepseek-chat", "http://x", provider="deepseek",
        )

    def test_native_provider_skips_openai_compatible_check(self, monkeypatch):
        # Anthropic must short-circuit before is_openai_compatible is touched.
        mock = MagicMock()
        compat = MagicMock(return_value=True)
        monkeypatch.setattr(anthropic_client, "AnthropicClient", mock)
        monkeypatch.setattr(openai_client, "is_openai_compatible", compat)
        factory.create_llm_client("anthropic", "claude-3")
        mock.assert_called_once()
        compat.assert_not_called()

    def test_non_compatible_unknown_falls_through_to_error(self, monkeypatch):
        monkeypatch.setattr(openai_client, "is_openai_compatible", lambda p: False)
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            factory.create_llm_client("mystery-provider", "m")

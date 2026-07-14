"""Tests for the OpenAI-compatible client registry and helpers.

Covers the pure functions ``_is_native_openai_base_url``,
``is_openai_compatible``, ``_supports_reasoning_effort``, and the
``OPENAI_COMPATIBLE_PROVIDERS`` registry / ``ProviderSpec`` defaults. These
were partially uncovered (openai_client.py 92%); no ChatOpenAI instance is
created.
"""

import pytest

from tradingagents.llm_clients.openai_client import (
    OPENAI_COMPATIBLE_PROVIDERS,
    ProviderSpec,
    DeepSeekChatOpenAI,
    MinimaxChatOpenAI,
    LocalCompatibleChatOpenAI,
    _is_native_openai_base_url,
    _supports_reasoning_effort,
    is_openai_compatible,
)


@pytest.mark.unit
class TestIsNativeOpenaiBaseUrl:
    def test_none_is_native(self):
        assert _is_native_openai_base_url(None) is True

    def test_api_openai_com_is_native(self):
        assert _is_native_openai_base_url("https://api.openai.com/v1") is True

    def test_subdomain_of_openai_com_is_native(self):
        assert _is_native_openai_base_url("https://us.api.openai.com/v1") is True

    def test_xai_is_not_native(self):
        assert _is_native_openai_base_url("https://api.x.ai/v1") is False

    def test_localhost_is_not_native(self):
        assert _is_native_openai_base_url("http://localhost:1234/v1") is False

    def test_no_scheme_assumes_https(self):
        # A bare host without "://" is prefixed with https://.
        assert _is_native_openai_base_url("api.openai.com") is True

    def test_custom_proxy_is_not_native(self):
        assert _is_native_openai_base_url("https://proxy.example.com/v1") is False


@pytest.mark.unit
class TestIsOpenaiCompatible:
    @pytest.mark.parametrize("provider", [
        "openai", "xai", "deepseek", "qwen", "glm", "minimax", "openrouter",
        "mistral", "kimi", "groq", "nvidia", "ollama", "openai_compatible",
    ])
    def test_known_providers_are_compatible(self, provider):
        assert is_openai_compatible(provider) is True

    def test_case_insensitive(self):
        assert is_openai_compatible("OLLAMA") is True
        assert is_openai_compatible("DeepSeek") is True

    def test_native_providers_not_in_registry(self):
        assert is_openai_compatible("anthropic") is False
        assert is_openai_compatible("google") is False
        assert is_openai_compatible("azure") is False

    def test_unknown_provider(self):
        assert is_openai_compatible("not-a-provider") is False


@pytest.mark.unit
class TestSupportsReasoningEffort:
    @pytest.mark.parametrize("model", ["gpt-5", "gpt-5-mini", "o1", "o3", "o3-mini", "o4"])
    def test_reasoning_models_supported(self, model):
        assert _supports_reasoning_effort(model) is True

    @pytest.mark.parametrize("model", ["gpt-4.1", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"])
    def test_non_reasoning_models_unsupported(self, model):
        assert _supports_reasoning_effort(model) is False

    def test_case_insensitive(self):
        assert _supports_reasoning_effort("GPT-5") is True
        assert _supports_reasoning_effort("O1") is True


@pytest.mark.unit
class TestProviderRegistry:
    def test_ollama_is_keyless_with_placeholder(self):
        spec = OPENAI_COMPATIBLE_PROVIDERS["ollama"]
        assert spec.key_optional is True
        assert spec.placeholder_key == "ollama"
        assert spec.base_url_env == "OLLAMA_BASE_URL"

    def test_openai_compatible_requires_base_url_and_keyless(self):
        spec = OPENAI_COMPATIBLE_PROVIDERS["openai_compatible"]
        assert spec.require_base_url is True
        assert spec.key_optional is True
        assert spec.chat_class is LocalCompatibleChatOpenAI

    def test_openai_uses_responses_api(self):
        assert OPENAI_COMPATIBLE_PROVIDERS["openai"].use_responses_api is True

    def test_third_party_providers_do_not_use_responses_api(self):
        assert OPENAI_COMPATIBLE_PROVIDERS["xai"].use_responses_api is False
        assert OPENAI_COMPATIBLE_PROVIDERS["deepseek"].use_responses_api is False

    def test_deepseek_and_minimax_use_their_subclasses(self):
        assert OPENAI_COMPATIBLE_PROVIDERS["deepseek"].chat_class is DeepSeekChatOpenAI
        assert OPENAI_COMPATIBLE_PROVIDERS["minimax"].chat_class is MinimaxChatOpenAI

    def test_provider_spec_defaults(self):
        spec = ProviderSpec()
        assert spec.chat_class.__name__ == "NormalizedChatOpenAI"
        assert spec.base_url is None
        assert spec.key_optional is False
        assert spec.require_base_url is False
        assert spec.use_responses_api is False

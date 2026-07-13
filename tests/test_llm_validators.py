"""Tests for the per-provider model-name validator.

``validate_model`` accepts any model for user-defined providers (ollama,
openrouter, openai_compatible, ...) and for providers absent from the catalog;
for catalogued providers it checks membership. The unknown-provider accept
branch and the VALID_MODELS exclusion were uncovered (validators.py 90%).
"""

import pytest

from tradingagents.llm_clients.validators import (
    VALID_MODELS,
    _ANY_MODEL_PROVIDERS,
    validate_model,
)


@pytest.mark.unit
class TestValidateModel:
    @pytest.mark.parametrize("provider", list(_ANY_MODEL_PROVIDERS))
    def test_any_model_providers_accept_anything(self, provider):
        assert validate_model(provider, "literally-anything-123") is True

    def test_unknown_provider_accepts_anything(self):
        # Covers `if provider_lower not in VALID_MODELS: return True`.
        assert validate_model("completely-unknown-provider", "whatever") is True

    def test_case_insensitive(self):
        assert validate_model("OLLAMA", "x") is True
        assert validate_model("Ollama", "x") is True
        assert validate_model("ollama", "x") is True

    def test_valid_models_excludes_any_model_providers(self):
        for provider in _ANY_MODEL_PROVIDERS:
            assert provider not in VALID_MODELS

    def test_known_provider_accepts_listed_model(self):
        provider = next(iter(VALID_MODELS))
        valid_model = VALID_MODELS[provider][0]
        assert validate_model(provider, valid_model) is True

    def test_known_provider_rejects_unlisted_model(self):
        provider = next(iter(VALID_MODELS))
        assert validate_model(provider, "definitely-not-a-real-model-name") is False

    def test_known_provider_case_insensitive(self):
        provider = next(iter(VALID_MODELS))
        valid_model = VALID_MODELS[provider][0]
        assert validate_model(provider.upper(), valid_model) is True

"""Tests for the Anthropic client's effort-parameter support heuristic.

``_supports_effort`` decides whether a model accepts the ``effort`` parameter
based on family (opus/sonnet/fable) and version, plus an exact-match set for
non-standard names. This is the testable pure logic; the invoke/get_llm paths
need a live ChatAnthropic and are not covered here
(anthropic_client.py was 95% covered).
"""

import pytest

from tradingagents.llm_clients.anthropic_client import _supports_effort


@pytest.mark.unit
class TestSupportsEffort:
    @pytest.mark.parametrize("model", [
        "claude-opus-4-5", "claude-opus-4-8", "claude-opus-5", "claude-opus-5-0",
        "claude-sonnet-4-6", "claude-sonnet-5", "claude-sonnet-5-0",
        "claude-fable-5", "claude-fable-5-0",
        "claude-mythos-preview", "claude-mythos-5",
    ])
    def test_effort_capable_models(self, model):
        assert _supports_effort(model) is True

    @pytest.mark.parametrize("model", [
        "claude-opus-4-4", "claude-opus-4",
        "claude-sonnet-4-5", "claude-sonnet-4",
        "claude-fable-4",
        "claude-haiku-4-5",  # haiku is not in the effort families
        "gpt-4", "claude-opus", "",
    ])
    def test_effort_incapable_models(self, model):
        assert _supports_effort(model) is False

    def test_case_insensitive(self):
        assert _supports_effort("CLAUDE-OPUS-4-5") is True
        assert _supports_effort("Claude-Sonnet-5") is True
        assert _supports_effort("CLAUDE-HAIKU-4-5") is False

    def test_single_number_version_minor_defaults_to_zero(self):
        # "claude-sonnet-5" (no minor) -> (5, 0) >= (4, 6) -> True
        assert _supports_effort("claude-sonnet-5") is True
        # "claude-sonnet-4" (no minor) -> (4, 0) >= (4, 6) -> False
        assert _supports_effort("claude-sonnet-4") is False

    def test_opus_boundary_4_5(self):
        # The minimum for opus is (4, 5).
        assert _supports_effort("claude-opus-4-5") is True
        assert _supports_effort("claude-opus-4-4") is False

    def test_sonnet_boundary_4_6(self):
        assert _supports_effort("claude-sonnet-4-6") is True
        assert _supports_effort("claude-sonnet-4-5") is False

    def test_fable_boundary_5_0(self):
        assert _supports_effort("claude-fable-5") is True
        assert _supports_effort("claude-fable-4") is False

    def test_mythos_exact_match(self):
        assert _supports_effort("claude-mythos-preview") is True
        assert _supports_effort("claude-mythos-5") is True
        # A mythos version not in the exact set and not matching the family regex.
        assert _supports_effort("claude-mythos-3") is False

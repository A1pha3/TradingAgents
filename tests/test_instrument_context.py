"""Tests for the instrument-context helpers in agent_utils.

``build_instrument_context`` produces the identity-anchoring preamble injected
into every agent prompt so the pipeline does not hallucinate a different
company from the price chart (#814). ``get_instrument_context_from_state`` is
the state-aware accessor used inside the graph. Several branches were
uncovered: sector-only and industry-only identity, the crypto label swap, and
the state fallback when no context was pre-resolved.
"""

import pytest

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_instrument_context_from_state,
)


@pytest.mark.unit
class TestBuildInstrumentContext:
    def test_stock_basic_includes_ticker_and_preserves_suffix(self):
        ctx = build_instrument_context("7203.T")
        assert "7203.T" in ctx
        assert "instrument" in ctx
        # Suffix preservation is the whole point (#814); do not mangle it.
        assert "exact ticker" in ctx

    def test_crypto_uses_asset_label(self):
        ctx = build_instrument_context("BTC-USD", asset_type="crypto")
        assert "asset" in ctx
        assert "BTC-USD" in ctx
        assert "crypto asset" in ctx
        assert "fundamentals" in ctx  # crypto disclaimer

    def test_full_identity_uses_business_classification(self):
        ctx = build_instrument_context(
            "AAPL",
            identity={
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "exchange": "NASDAQ",
            },
        )
        assert "Company: Apple Inc." in ctx
        assert "Business classification: Technology / Consumer Electronics" in ctx
        assert "Exchange: NASDAQ" in ctx

    def test_sector_only_omits_industry(self):
        # Covers the elif sector branch (line 151) — no "Business
        # classification" line, just "Sector".
        ctx = build_instrument_context(
            "X", identity={"company_name": "Co", "sector": "Energy"}
        )
        assert "Sector: Energy" in ctx
        assert "Business classification:" not in ctx
        assert "Industry:" not in ctx

    def test_industry_only_omits_sector(self):
        # Covers the elif industry branch (line 153).
        ctx = build_instrument_context(
            "X", identity={"company_name": "Co", "industry": "Software"}
        )
        assert "Industry: Software" in ctx
        assert "Business classification:" not in ctx
        assert "Sector:" not in ctx

    def test_crypto_identity_uses_name_label_not_company(self):
        ctx = build_instrument_context(
            "ETH-USD",
            asset_type="crypto",
            identity={"company_name": "Ethereum"},
        )
        assert "Name: Ethereum" in ctx
        assert "Company:" not in ctx

    def test_identity_without_name_skips_name_line(self):
        ctx = build_instrument_context(
            "X", identity={"sector": "Energy", "industry": "Oil"}
        )
        assert "Business classification: Energy / Oil" in ctx
        # No name was resolved, so neither "Company:" nor "Name:" appears.
        assert "Company:" not in ctx
        assert "Name:" not in ctx

    def test_exchange_alone_is_listed(self):
        ctx = build_instrument_context("X", identity={"exchange": "LSE"})
        assert "Exchange: LSE" in ctx

    def test_resolved_identity_instructs_no_substitution(self):
        ctx = build_instrument_context("X", identity={"company_name": "Co"})
        assert "Do not substitute a different company" in ctx

    def test_empty_identity_has_no_resolved_block(self):
        ctx = build_instrument_context("X", identity={})
        assert "Resolved identity:" not in ctx

    def test_none_identity_treated_as_empty(self):
        # resolve_instrument_identity can return {} on failure; build must not
        # crash when identity is None.
        ctx = build_instrument_context("X", identity=None)
        assert "X" in ctx
        assert "Resolved identity:" not in ctx


@pytest.mark.unit
class TestGetInstrumentContextFromState:
    def test_returns_pre_resolved_context_when_present(self):
        state = {
            "company_of_interest": "AAPL",
            "asset_type": "stock",
            "instrument_context": "The instrument to analyze is `AAPL`. ...",
        }
        assert (
            get_instrument_context_from_state(state)
            == "The instrument to analyze is `AAPL`. ..."
        )

    def test_falls_back_when_context_missing(self):
        state = {"company_of_interest": "MSFT", "asset_type": "stock"}
        ctx = get_instrument_context_from_state(state)
        assert "MSFT" in ctx
        assert "instrument" in ctx

    def test_falls_back_when_context_blank(self):
        # A whitespace-only context must not be used verbatim.
        state = {
            "company_of_interest": "NVDA",
            "asset_type": "stock",
            "instrument_context": "   ",
        }
        ctx = get_instrument_context_from_state(state)
        assert "NVDA" in ctx
        assert ctx != "   "

    def test_fallback_defaults_asset_type_to_stock(self):
        # Bare programmatic states (tests) may omit asset_type entirely.
        state = {"company_of_interest": "GOOG"}
        ctx = get_instrument_context_from_state(state)
        assert "GOOG" in ctx
        assert "instrument" in ctx  # stock label, not crypto "asset"

    def test_fallback_honours_crypto_asset_type(self):
        state = {"company_of_interest": "BTC-USD", "asset_type": "crypto"}
        ctx = get_instrument_context_from_state(state)
        assert "BTC-USD" in ctx
        assert "asset" in ctx

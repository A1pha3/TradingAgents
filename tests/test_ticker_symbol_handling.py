import unittest

import pytest

from cli.utils import normalize_ticker_symbol, expand_a_share_ticker
from tradingagents.agents.utils.agent_utils import build_instrument_context, build_market_context
from tradingagents.market.instrument_profile import resolve_instrument_profile


@pytest.mark.unit
class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" cnc.to "), "CNC.TO")
        self.assertEqual(normalize_ticker_symbol(" 600519.sh "), "600519.SH")
        self.assertEqual(normalize_ticker_symbol("000001.sz"), "000001.SZ")

    def test_expand_a_share_ticker_raises_on_bare_6_digit(self):
        with self.assertRaises(ValueError) as cm:
            expand_a_share_ticker("600519")
        self.assertIn("requires exchange parameter", str(cm.exception))
        self.assertIn("600519", str(cm.exception))

    def test_expand_a_share_ticker_with_exchange(self):
        self.assertEqual(expand_a_share_ticker("600519", "SH"), "600519.SH")
        self.assertEqual(expand_a_share_ticker("000001", "SZ"), "000001.SZ")
        self.assertEqual(expand_a_share_ticker("430047", "BJ"), "430047.BJ")

    def test_expand_a_share_ticker_preserves_existing_suffix(self):
        self.assertEqual(expand_a_share_ticker("600519.SH"), "600519.SH")
        self.assertEqual(expand_a_share_ticker("000001.sz"), "000001.SZ")

    def test_expand_a_share_ticker_passes_through_non_china_tickers(self):
        self.assertEqual(expand_a_share_ticker("SPY"), "SPY")
        self.assertEqual(expand_a_share_ticker("AAPL"), "AAPL")
        self.assertEqual(expand_a_share_ticker("CNC.TO"), "CNC.TO")

    def test_build_market_context_for_cn_a(self):
        profile = resolve_instrument_profile("600519.SH")
        context = build_market_context(profile)
        self.assertIn("China A-share", context)
        self.assertIn("CNY", context)
        self.assertIn("price limit", context.lower())
        self.assertIn("insider", context.lower())

    def test_build_market_context_for_global(self):
        profile = resolve_instrument_profile("SPY")
        context = build_market_context(profile)
        self.assertEqual(context, "")

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context("7203.T")
        self.assertIn("7203.T", context)
        self.assertIn("exchange suffix", context)

    def test_build_instrument_context_includes_a_share_market_context(self):
        context = build_instrument_context("600519.SH")
        self.assertIn("600519.SH", context)
        self.assertIn("China A-share", context)
        self.assertIn("price limit", context.lower())

    def test_build_instrument_context_crypto_behavior(self):
        context = build_instrument_context("BTC-USD", asset_type="crypto")
        self.assertIn("BTC-USD", context)
        self.assertIn("crypto asset", context)
        self.assertIn("fundamentals", context.lower())
        # Should not include market context for crypto
        self.assertNotIn("China A-share", context)

    def test_build_instrument_context_non_a_share_stock(self):
        context = build_instrument_context("AAPL")
        self.assertIn("AAPL", context)
        # Should not include A-share specific context
        self.assertNotIn("China A-share", context)
        self.assertNotIn("price limit", context.lower())


if __name__ == "__main__":
    unittest.main()

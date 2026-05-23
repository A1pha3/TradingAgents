"""Tests for the market-layer return resolver."""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import pandas as pd

from tradingagents.market.return_resolver import (
    resolve_benchmark_ticker,
    fetch_close_series,
    fetch_returns,
)
from tradingagents.market.instrument_profile import resolve_instrument_profile


class TestResolveBenchmarkTicker(unittest.TestCase):
    """Test benchmark ticker resolution logic."""

    def test_cn_a_default_benchmark(self):
        """CN_A profile returns 000300.SS when no explicit benchmark is provided."""
        profile = resolve_instrument_profile("600519.SH")
        result = resolve_benchmark_ticker(profile, explicit_benchmark=None)
        self.assertEqual(result, "000300.SS")

    def test_global_default_benchmark(self):
        """GLOBAL profile returns SPY when no explicit benchmark is provided."""
        profile = resolve_instrument_profile("AAPL")
        result = resolve_benchmark_ticker(profile, explicit_benchmark=None)
        self.assertEqual(result, "SPY")

    def test_explicit_benchmark_overrides_profile(self):
        """Explicit benchmark overrides profile default."""
        profile = resolve_instrument_profile("600519.SH")
        result = resolve_benchmark_ticker(profile, explicit_benchmark="^GSPC")
        self.assertEqual(result, "^GSPC")

    def test_explicit_benchmark_overrides_global_profile(self):
        """Explicit benchmark overrides global profile default."""
        profile = resolve_instrument_profile("AAPL")
        result = resolve_benchmark_ticker(profile, explicit_benchmark="QQQ")
        self.assertEqual(result, "QQQ")


class TestFetchCloseSeries(unittest.TestCase):
    """Test close series fetching with vendor routing."""

    @patch("tradingagents.market.return_resolver.yf.Ticker")
    def test_non_a_share_uses_yfinance(self, mock_yf_ticker):
        """Non-A-share ticker uses yfinance."""
        mock_hist = pd.DataFrame({
            "Close": [100.0, 101.0, 102.0],
        }, index=pd.date_range("2024-01-01", periods=3))
        mock_yf_ticker.return_value.history.return_value = mock_hist

        result = fetch_close_series("AAPL", "2024-01-01", "2024-01-03")

        mock_yf_ticker.assert_called_once_with("AAPL")
        mock_yf_ticker.return_value.history.assert_called_once_with(
            start="2024-01-01", end="2024-01-03"
        )
        pd.testing.assert_series_equal(result, mock_hist["Close"])

    @patch("tradingagents.market.return_resolver._load_hist")
    def test_a_share_uses_akshare(self, mock_load_hist):
        """A-share ticker uses AkShare via _load_hist."""
        mock_hist = pd.DataFrame({
            "Date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "Close": [50.0, 51.0, 52.0],
        })
        mock_load_hist.return_value = mock_hist

        result = fetch_close_series("600519.SH", "2024-01-01", "2024-01-05")

        mock_load_hist.assert_called_once_with("600519.SH", "2024-01-01", "2024-01-05")
        expected = pd.Series(
            [50.0, 51.0, 52.0],
            index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            name="Close",
        )
        expected.index.name = "Date"
        pd.testing.assert_series_equal(result, expected)

    @patch("tradingagents.market.return_resolver.yf.Ticker")
    def test_empty_series_returns_empty_series(self, mock_yf_ticker):
        """Empty history returns empty series."""
        mock_yf_ticker.return_value.history.return_value = pd.DataFrame()

        result = fetch_close_series("XYZ", "2024-01-01", "2024-01-03")

        self.assertTrue(result.empty)

    @patch("tradingagents.market.return_resolver.yf.Ticker")
    def test_exception_returns_empty_series(self, mock_yf_ticker):
        """Exception during fetch returns empty series."""
        mock_yf_ticker.return_value.history.side_effect = Exception("Network error")

        result = fetch_close_series("AAPL", "2024-01-01", "2024-01-03")

        self.assertTrue(result.empty)


class TestFetchReturns(unittest.TestCase):
    """Test integrated return calculation with mocked close series."""

    @patch("tradingagents.market.return_resolver.fetch_close_series")
    def test_cn_a_returns_calculation(self, mock_fetch_close):
        """CN_A ticker calculates raw and alpha returns correctly."""
        # Mock stock series: 100 -> 105 (5% raw return)
        stock_series = pd.Series(
            [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
            index=pd.date_range("2024-01-02", periods=6, freq="D"),
        )
        # Mock benchmark series: 1000 -> 1020 (2% benchmark return, so 3% alpha)
        benchmark_series = pd.Series(
            [1000.0, 1005.0, 1010.0, 1012.0, 1015.0, 1020.0],
            index=pd.date_range("2024-01-02", periods=6, freq="D"),
        )

        def side_effect(ticker, start, end):
            if ticker == "600519.SH":
                return stock_series
            elif ticker == "000300.SS":
                return benchmark_series
            return pd.Series()

        mock_fetch_close.side_effect = side_effect

        profile = resolve_instrument_profile("600519.SH")
        raw, alpha, days = fetch_returns(
            profile=profile,
            trade_date="2024-01-02",
            holding_days=5,
            explicit_benchmark=None,
        )

        self.assertAlmostEqual(raw, 0.05, places=5)
        self.assertAlmostEqual(alpha, 0.03, places=5)
        self.assertEqual(days, 5)

    @patch("tradingagents.market.return_resolver.fetch_close_series")
    def test_explicit_benchmark_override(self, mock_fetch_close):
        """Explicit benchmark overrides profile default."""
        stock_series = pd.Series(
            [200.0, 210.0],
            index=pd.date_range("2024-01-02", periods=2, freq="D"),
        )
        spy_series = pd.Series(
            [400.0, 404.0],
            index=pd.date_range("2024-01-02", periods=2, freq="D"),
        )

        def side_effect(ticker, start, end):
            if ticker == "AAPL":
                return stock_series
            elif ticker == "SPY":
                return spy_series
            return pd.Series()

        mock_fetch_close.side_effect = side_effect

        profile = resolve_instrument_profile("AAPL")
        raw, alpha, days = fetch_returns(
            profile=profile,
            trade_date="2024-01-02",
            holding_days=1,
            explicit_benchmark="SPY",
        )

        # Raw: (210 - 200) / 200 = 0.05
        # Benchmark: (404 - 400) / 400 = 0.01
        # Alpha: 0.05 - 0.01 = 0.04
        self.assertAlmostEqual(raw, 0.05, places=5)
        self.assertAlmostEqual(alpha, 0.04, places=5)
        self.assertEqual(days, 1)

    @patch("tradingagents.market.return_resolver.fetch_close_series")
    def test_missing_stock_series_returns_none(self, mock_fetch_close):
        """Missing stock series returns (None, None, None)."""
        mock_fetch_close.return_value = pd.Series()

        profile = resolve_instrument_profile("600519.SH")
        result = fetch_returns(
            profile=profile,
            trade_date="2024-01-02",
            holding_days=5,
            explicit_benchmark=None,
        )

        self.assertEqual(result, (None, None, None))

    @patch("tradingagents.market.return_resolver.fetch_close_series")
    def test_missing_benchmark_series_returns_none(self, mock_fetch_close):
        """Missing benchmark series returns (None, None, None)."""
        stock_series = pd.Series(
            [100.0, 105.0],
            index=pd.date_range("2024-01-02", periods=2, freq="D"),
        )

        def side_effect(ticker, start, end):
            if ticker == "600519.SH":
                return stock_series
            return pd.Series()

        mock_fetch_close.side_effect = side_effect

        profile = resolve_instrument_profile("600519.SH")
        result = fetch_returns(
            profile=profile,
            trade_date="2024-01-02",
            holding_days=5,
            explicit_benchmark=None,
        )

        self.assertEqual(result, (None, None, None))

    @patch("tradingagents.market.return_resolver.fetch_close_series")
    def test_insufficient_stock_data_returns_none(self, mock_fetch_close):
        """Fewer than 2 data points returns (None, None, None)."""
        stock_series = pd.Series([100.0], index=pd.date_range("2024-01-02", periods=1))
        benchmark_series = pd.Series(
            [1000.0, 1010.0],
            index=pd.date_range("2024-01-02", periods=2, freq="D"),
        )

        def side_effect(ticker, start, end):
            if ticker == "600519.SH":
                return stock_series
            elif ticker == "000300.SS":
                return benchmark_series
            return pd.Series()

        mock_fetch_close.side_effect = side_effect

        profile = resolve_instrument_profile("600519.SH")
        result = fetch_returns(
            profile=profile,
            trade_date="2024-01-02",
            holding_days=5,
            explicit_benchmark=None,
        )

        self.assertEqual(result, (None, None, None))

    @patch("tradingagents.market.return_resolver.fetch_close_series")
    def test_actual_holding_days_capped(self, mock_fetch_close):
        """Actual holding days is capped by available data."""
        # Stock has only 3 data points, benchmark has 5
        stock_series = pd.Series(
            [100.0, 102.0, 104.0],
            index=pd.date_range("2024-01-02", periods=3, freq="D"),
        )
        benchmark_series = pd.Series(
            [1000.0, 1005.0, 1010.0, 1015.0, 1020.0],
            index=pd.date_range("2024-01-02", periods=5, freq="D"),
        )

        def side_effect(ticker, start, end):
            if ticker == "AAPL":
                return stock_series
            elif ticker == "SPY":
                return benchmark_series
            return pd.Series()

        mock_fetch_close.side_effect = side_effect

        profile = resolve_instrument_profile("AAPL")
        raw, alpha, days = fetch_returns(
            profile=profile,
            trade_date="2024-01-02",
            holding_days=5,
            explicit_benchmark=None,
        )

        # Actual holding days should be 2 (stock has 3 points, so 3-1=2)
        self.assertEqual(days, 2)
        self.assertAlmostEqual(raw, 0.04, places=5)


if __name__ == "__main__":
    unittest.main()

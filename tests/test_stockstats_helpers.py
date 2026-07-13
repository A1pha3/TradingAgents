"""Tests for stockstats_utils pure helpers.

Covers the date/normalization helpers that don't require a yfinance call:
``_ensure_date_column``, ``_clean_dataframe``, ``filter_financials_by_date``,
and ``_assert_ohlcv_not_stale``. These were partially uncovered
(stockstats_utils.py 71%); all inputs are in-memory DataFrames.
"""

import pandas as pd
import pytest

from tradingagents.dataflows.stockstats_utils import (
    _assert_ohlcv_not_stale,
    _clean_dataframe,
    _ensure_date_column,
    filter_financials_by_date,
)
from tradingagents.dataflows.symbol_utils import NoMarketDataError


@pytest.mark.unit
class TestEnsureDateColumn:
    def test_keeps_existing_date_column(self):
        df = pd.DataFrame({"Date": ["2024-01-01"], "Close": [100]})
        assert _ensure_date_column(df).columns.tolist() == ["Date", "Close"]

    def test_renames_index_column(self):
        df = pd.DataFrame({"index": ["2024-01-01"], "Close": [100]})
        assert "Date" in _ensure_date_column(df).columns
        assert "index" not in _ensure_date_column(df).columns

    def test_renames_datetime_column(self):
        df = pd.DataFrame({"Datetime": ["2024-01-01"], "Close": [100]})
        assert "Date" in _ensure_date_column(df).columns

    def test_no_date_like_column_unchanged(self):
        df = pd.DataFrame({"Close": [100], "Volume": [1]})
        out = _ensure_date_column(df)
        assert out.columns.tolist() == ["Close", "Volume"]


@pytest.mark.unit
class TestCleanDataframe:
    def test_parses_dates_and_drops_invalid(self):
        df = pd.DataFrame({"Date": ["2024-01-01", "not-a-date"], "Close": [100, 101]})
        out = _clean_dataframe(df)
        assert len(out) == 1
        assert out["Close"].iloc[0] == 100

    def test_drops_rows_with_nan_close(self):
        df = pd.DataFrame({"Date": ["2024-01-01", "2024-01-02"], "Close": [100, None]})
        out = _clean_dataframe(df)
        assert len(out) == 1
        assert out["Close"].iloc[0] == 100

    def test_ffills_non_close_price_gaps(self):
        # Close is present on both rows (so neither is dropped); the Open gap
        # is forward-filled from the prior row.
        df = pd.DataFrame({
            "Date": ["2024-01-01", "2024-01-02"],
            "Open": [100.0, None], "Close": [100.0, 110.0],
        })
        out = _clean_dataframe(df)
        assert len(out) == 2
        assert out["Open"].iloc[1] == 100.0  # forward-filled
        assert out["Close"].iloc[1] == 110.0


@pytest.mark.unit
class TestFilterFinancialsByDate:
    def test_drops_future_columns(self):
        # Financial statements use fiscal-period end dates as columns.
        df = pd.DataFrame({
            "metric": ["revenue"],
            "2023-12-31": [100],
            "2024-06-30": [110],
            "2025-01-01": [120],  # future relative to 2024-12-31
        }).set_index("metric")
        out = filter_financials_by_date(df, "2024-12-31")
        assert "2023-12-31" in out.columns
        assert "2024-06-30" in out.columns
        assert "2025-01-01" not in out.columns

    def test_empty_curr_date_returns_unchanged(self):
        df = pd.DataFrame({"2024-01-01": [1]})
        assert filter_financials_by_date(df, "").equals(df)

    def test_empty_frame_returned_unchanged(self):
        df = pd.DataFrame()
        assert filter_financials_by_date(df, "2024-01-01").empty


@pytest.mark.unit
class TestAssertOhlcvNotStale:
    def _frame(self, last_date):
        return pd.DataFrame({
            "Date": pd.to_datetime(["2024-01-01", last_date]),
            "Close": [100.0, 110.0],
        })

    def test_recent_data_no_raise(self):
        # Latest row is 3 days before the requested date -> within the 10-day window.
        df = self._frame("2024-01-12")
        _assert_ohlcv_not_stale(df, "2024-01-15", "AAPL")  # no exception

    def test_stale_data_raises(self):
        # Latest row is far older than the requested date -> stale -> NoMarketDataError.
        df = self._frame("2024-01-01")
        with pytest.raises(NoMarketDataError):
            _assert_ohlcv_not_stale(df, "2024-06-01", "AAPL")

    def test_empty_frame_no_raise(self):
        _assert_ohlcv_not_stale(pd.DataFrame(), "2024-01-01", "AAPL")

    def test_none_frame_no_raise(self):
        _assert_ohlcv_not_stale(None, "2024-01-01", "AAPL")

    def test_unparseable_curr_date_no_raise(self):
        df = self._frame("2024-01-01")
        _assert_ohlcv_not_stale(df, "not-a-date", "AAPL")

    def test_stale_error_carries_symbol_and_detail(self):
        df = self._frame("2024-01-01")
        with pytest.raises(NoMarketDataError) as exc_info:
            _assert_ohlcv_not_stale(df, "2024-06-01", "AAPL")
        assert exc_info.value.symbol == "AAPL"

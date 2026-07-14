"""Tests for the Alpha Vantage stock OHLCV fetcher.

Covers ``get_stock``: the compact-vs-full ``outputsize`` choice (based on
whether the start date is within 100 days of today), parameter forwarding,
and that the returned CSV is filtered to the requested window.
``_make_api_request`` is mocked (alpha_vantage_stock.py was 30% covered).
"""

from datetime import datetime, timedelta

import pytest

from tradingagents.dataflows import alpha_vantage_stock as avs


def _capture(monkeypatch):
    captured = {}

    def fake(fn, params):
        captured["function"] = fn
        captured["params"] = params
        return "timestamp,close\n2024-01-01,100\n"

    monkeypatch.setattr(avs, "_make_api_request", fake)
    return captured


@pytest.mark.unit
class TestGetStockOutputsize:
    def test_recent_start_uses_compact(self, monkeypatch):
        captured = _capture(monkeypatch)
        start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        avs.get_stock("AAPL", start, end)
        assert captured["params"]["outputsize"] == "compact"

    def test_99_days_uses_compact(self, monkeypatch):
        captured = _capture(monkeypatch)
        start = (datetime.now() - timedelta(days=99)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        avs.get_stock("AAPL", start, end)
        assert captured["params"]["outputsize"] == "compact"

    def test_exactly_100_days_uses_full(self, monkeypatch):
        # The boundary is strict (< 100 -> compact); 100 days -> full.
        captured = _capture(monkeypatch)
        start = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        avs.get_stock("AAPL", start, end)
        assert captured["params"]["outputsize"] == "full"

    def test_old_start_uses_full(self, monkeypatch):
        captured = _capture(monkeypatch)
        avs.get_stock("AAPL", "2020-01-01", "2020-06-01")
        assert captured["params"]["outputsize"] == "full"


@pytest.mark.unit
class TestGetStockParams:
    def test_forwards_symbol_datatype_and_function(self, monkeypatch):
        captured = _capture(monkeypatch)
        avs.get_stock("MSFT", "2020-01-01", "2020-06-01")
        assert captured["function"] == "TIME_SERIES_DAILY_ADJUSTED"
        assert captured["params"]["symbol"] == "MSFT"
        assert captured["params"]["datatype"] == "csv"


@pytest.mark.unit
class TestGetStockFiltering:
    def test_returns_csv_filtered_to_window(self, monkeypatch):
        csv = "timestamp,close\n2024-01-01,100\n2024-02-01,110\n2024-03-01,120\n"
        monkeypatch.setattr(avs, "_make_api_request", lambda *a, **k: csv)
        result = avs.get_stock("AAPL", "2024-01-15", "2024-02-15")
        assert "110" in result   # 2024-02-01 in window
        assert "100" not in result  # 2024-01-01 before window
        assert "120" not in result  # 2024-03-01 after window

    def test_empty_window_yields_empty_or_header(self, monkeypatch):
        csv = "timestamp,close\n2024-01-01,100\n"
        monkeypatch.setattr(avs, "_make_api_request", lambda *a, **k: csv)
        result = avs.get_stock("AAPL", "2024-06-01", "2024-07-01")
        # No rows in window -> header-only CSV (no data row).
        assert "100" not in result

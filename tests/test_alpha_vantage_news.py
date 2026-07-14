"""Tests for the Alpha Vantage news + insider-transactions fetchers.

Covers ``get_news``, ``get_global_news``, ``get_insider_transactions``:
parameter forwarding, date formatting via ``format_datetime_for_api``, and the
``get_global_news`` look-back-window calculation. ``_make_api_request`` is
mocked (alpha_vantage_news.py was 29% covered).
"""

import pytest

from tradingagents.dataflows import alpha_vantage_news as avn


def _recorder(monkeypatch):
    captured = {}

    def fake(function_name, params):
        captured["function"] = function_name
        captured["params"] = params
        return {"ok": True}

    monkeypatch.setattr(avn, "_make_api_request", fake)
    return captured


@pytest.mark.unit
class TestGetNews:
    def test_passes_ticker_and_formatted_dates(self, monkeypatch):
        captured = _recorder(monkeypatch)
        result = avn.get_news("AAPL", "2024-01-01", "2024-01-31")
        assert captured["function"] == "NEWS_SENTIMENT"
        assert captured["params"]["tickers"] == "AAPL"
        assert captured["params"]["time_from"] == "20240101T0000"
        assert captured["params"]["time_to"] == "20240131T0000"
        assert result == {"ok": True}

    def test_returns_raw_api_response(self, monkeypatch):
        monkeypatch.setattr(avn, "_make_api_request", lambda *a, **k: "raw-csv-or-json")
        assert avn.get_news("MSFT", "2024-01-01", "2024-01-02") == "raw-csv-or-json"


@pytest.mark.unit
class TestGetGlobalNews:
    def test_calculates_lookback_window_and_topics(self, monkeypatch):
        captured = _recorder(monkeypatch)
        avn.get_global_news("2024-01-31", look_back_days=7, limit=20)
        assert captured["params"]["topics"] == "financial_markets,economy_macro,economy_monetary"
        assert captured["params"]["time_from"] == "20240124T0000"  # 2024-01-31 - 7d
        assert captured["params"]["time_to"] == "20240131T0000"
        assert captured["params"]["limit"] == "20"

    def test_defaults_look_back_and_limit(self, monkeypatch):
        captured = _recorder(monkeypatch)
        avn.get_global_news("2024-01-31")
        assert captured["params"]["limit"] == "50"  # default limit
        # default look_back_days=7 -> start = 2024-01-24
        assert captured["params"]["time_from"] == "20240124T0000"

    def test_zero_lookback_uses_same_day(self, monkeypatch):
        captured = _recorder(monkeypatch)
        avn.get_global_news("2024-01-15", look_back_days=0)
        assert captured["params"]["time_from"] == "20240115T0000"
        assert captured["params"]["time_to"] == "20240115T0000"


@pytest.mark.unit
class TestGetInsiderTransactions:
    def test_passes_symbol(self, monkeypatch):
        captured = _recorder(monkeypatch)
        result = avn.get_insider_transactions("IBM")
        assert captured["function"] == "INSIDER_TRANSACTIONS"
        assert captured["params"]["symbol"] == "IBM"
        assert result == {"ok": True}

    def test_returns_raw_response(self, monkeypatch):
        monkeypatch.setattr(avn, "_make_api_request", lambda *a, **k: {"transactions": []})
        assert avn.get_insider_transactions("AAPL") == {"transactions": []}

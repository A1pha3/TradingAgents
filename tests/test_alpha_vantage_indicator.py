"""Tests for the Alpha Vantage indicator fetcher.

Covers ``get_indicator``: unsupported-indicator rejection, the VWMA
no-API-call special case, CSV parsing + date-window filtering, missing-column
errors, the not-configured propagation, and per-indicator function dispatch.
``_make_api_request`` is mocked so no network call is made
(alpha_vantage_indicator.py was 3% covered).
"""

import pytest

from tradingagents.dataflows import alpha_vantage_indicator as avi
from tradingagents.dataflows.alpha_vantage_common import (
    AlphaVantageNotConfiguredError,
)


@pytest.mark.unit
class TestGetIndicatorDispatch:
    def test_unsupported_indicator_raises_value_error(self):
        with pytest.raises(ValueError, match="not supported"):
            avi.get_indicator("AAPL", "not_a_real_indicator", "2024-01-15", 30)

    def test_vwma_returns_informational_without_api_call(self, monkeypatch):
        called = []
        monkeypatch.setattr(avi, "_make_api_request",
                            lambda *a, **k: called.append(a) or "")
        result = avi.get_indicator("AAPL", "vwma", "2024-01-15", 30)
        assert "VWMA" in result
        assert called == []  # no API call made

    @pytest.mark.parametrize("indicator,function", [
        ("close_50_sma", "SMA"),
        ("close_200_sma", "SMA"),
        ("close_10_ema", "EMA"),
        ("macd", "MACD"),
        ("macds", "MACD"),
        ("macdh", "MACD"),
        ("rsi", "RSI"),
        ("atr", "ATR"),
        ("boll", "BBANDS"),
        ("boll_ub", "BBANDS"),
    ])
    def test_indicator_calls_correct_av_function(self, monkeypatch, indicator, function):
        col = {"rsi": "RSI", "macd": "MACD", "macds": "MACD_Signal",
               "macdh": "MACD_Hist", "atr": "ATR", "boll": "Real Middle Band",
               "boll_ub": "Real Upper Band", "close_50_sma": "SMA",
               "close_200_sma": "SMA", "close_10_ema": "EMA"}[indicator]
        captured = {}

        def fake(fn, params):
            captured["function"] = fn
            captured["params"] = params
            return f"time,{col}\n2024-01-10,1.0\n"

        monkeypatch.setattr(avi, "_make_api_request", fake)
        avi.get_indicator("AAPL", indicator, "2024-01-15", 10)
        assert captured["function"] == function
        assert captured["params"]["symbol"] == "AAPL"
        assert captured["params"]["datatype"] == "csv"


@pytest.mark.unit
class TestGetIndicatorParsing:
    def test_rsi_parses_and_filters_by_date_window(self, monkeypatch):
        # Window is [curr_date - look_back_days, curr_date] = 2024-01-05..2024-01-15.
        csv = "time,RSI\n2024-01-10,55.0\n2024-01-15,60.0\n2024-02-01,65.0\n"
        monkeypatch.setattr(avi, "_make_api_request", lambda *a, **k: csv)
        result = avi.get_indicator("AAPL", "rsi", "2024-01-15", 10)
        assert "2024-01-10" in result
        assert "2024-01-15" in result
        assert "2024-02-01" not in result  # outside window
        assert "55.0" in result

    def test_no_data_in_window_returns_no_data(self, monkeypatch):
        csv = "time,RSI\n2024-03-01,55.0\n"  # outside the window
        monkeypatch.setattr(avi, "_make_api_request", lambda *a, **k: csv)
        result = avi.get_indicator("AAPL", "rsi", "2024-01-15", 10)
        assert "No data available" in result

    def test_missing_time_column_returns_error(self, monkeypatch):
        csv = "date,RSI\n2024-01-10,55.0\n"
        monkeypatch.setattr(avi, "_make_api_request", lambda *a, **k: csv)
        result = avi.get_indicator("AAPL", "rsi", "2024-01-15", 10)
        assert "'time' column not found" in result

    def test_missing_value_column_returns_error(self, monkeypatch):
        csv = "time,Other\n2024-01-10,55.0\n"
        monkeypatch.setattr(avi, "_make_api_request", lambda *a, **k: csv)
        result = avi.get_indicator("AAPL", "rsi", "2024-01-15", 10)
        assert "not found" in result

    def test_empty_response_returns_no_data_error(self, monkeypatch):
        monkeypatch.setattr(avi, "_make_api_request", lambda *a, **k: "")
        result = avi.get_indicator("AAPL", "rsi", "2024-01-15", 10)
        assert "No data returned" in result

    def test_header_only_yields_no_data_error(self, monkeypatch):
        # "time,RSI\n".strip() -> "time,RSI" -> 1 line -> "No data returned".
        monkeypatch.setattr(avi, "_make_api_request", lambda *a, **k: "time,RSI\n")
        result = avi.get_indicator("AAPL", "rsi", "2024-01-15", 10)
        assert "No data returned" in result

    def test_output_includes_indicator_description(self, monkeypatch):
        csv = "time,RSI\n2024-01-10,55.0\n"
        monkeypatch.setattr(avi, "_make_api_request", lambda *a, **k: csv)
        result = avi.get_indicator("AAPL", "rsi", "2024-01-15", 10)
        assert "RSI" in result  # description mentions RSI

    def test_not_configured_propagates(self, monkeypatch):
        def raise_it(*a, **k):
            raise AlphaVantageNotConfiguredError("no key")
        monkeypatch.setattr(avi, "_make_api_request", raise_it)
        with pytest.raises(AlphaVantageNotConfiguredError):
            avi.get_indicator("AAPL", "rsi", "2024-01-15", 10)

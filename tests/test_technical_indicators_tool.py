"""Tests for the get_indicators tool wrapper.

The ``@tool``-decorated ``get_indicators`` splits a comma-separated indicator
string, lowercases each name, routes each to the configured vendor, and
stringifies ``ValueError`` so one bad indicator does not sink the call. The
body was 38% covered (only the decorator/import path ran). These tests mock
``route_to_vendor`` and drive the tool via its public ``invoke`` surface.
"""

import pytest

from tradingagents.agents.utils import technical_indicators_tools as tit
from tradingagents.agents.utils.technical_indicators_tools import get_indicators


def _route_recorder(monkeypatch, responses=None, errors=None):
    responses = responses or {}
    errors = errors or set()
    seen = []

    def fake(method, symbol, ind, curr_date, look_back_days):
        seen.append({
            "method": method, "symbol": symbol, "indicator": ind,
            "curr_date": curr_date, "look_back_days": look_back_days,
        })
        if ind in errors:
            raise ValueError(f"unknown indicator {ind}")
        return responses.get(ind, f"value_{ind}")

    monkeypatch.setattr(tit, "route_to_vendor", fake)
    return seen


@pytest.mark.unit
class TestGetIndicatorsTool:
    def test_single_indicator_returned(self, monkeypatch):
        seen = _route_recorder(monkeypatch, responses={"rsi": "14.5"})
        result = get_indicators.invoke(
            {"symbol": "AAPL", "indicator": "rsi", "curr_date": "2024-01-01"}
        )
        assert "14.5" in result
        assert seen[0]["method"] == "get_indicators"
        assert seen[0]["symbol"] == "AAPL"

    def test_multiple_comma_separated_joined_by_blank_line(self, monkeypatch):
        _route_recorder(monkeypatch, responses={"rsi": "r1", "macd": "m1", "boll": "b1"})
        result = get_indicators.invoke(
            {"symbol": "AAPL", "indicator": "rsi,macd,boll", "curr_date": "2024-01-01"}
        )
        assert "r1" in result and "m1" in result and "b1" in result
        assert result.count("\n\n") == 2  # three results -> two separators

    def test_indicators_lowercased_before_routing(self, monkeypatch):
        seen = _route_recorder(monkeypatch)
        get_indicators.invoke(
            {"symbol": "AAPL", "indicator": "RSI,MACD", "curr_date": "2024-01-01"}
        )
        assert [c["indicator"] for c in seen] == ["rsi", "macd"]

    def test_whitespace_trimmed(self, monkeypatch):
        seen = _route_recorder(monkeypatch)
        get_indicators.invoke(
            {"symbol": "AAPL", "indicator": "  rsi ,  macd  ", "curr_date": "2024-01-01"}
        )
        assert [c["indicator"] for c in seen] == ["rsi", "macd"]

    def test_empty_segments_dropped(self, monkeypatch):
        seen = _route_recorder(monkeypatch)
        get_indicators.invoke(
            {"symbol": "AAPL", "indicator": "rsi,, ,macd,", "curr_date": "2024-01-01"}
        )
        assert [c["indicator"] for c in seen] == ["rsi", "macd"]

    def test_value_error_stringified_not_raised(self, monkeypatch):
        _route_recorder(monkeypatch, responses={"rsi": "r1"}, errors={"bad"})
        result = get_indicators.invoke(
            {"symbol": "AAPL", "indicator": "rsi,bad", "curr_date": "2024-01-01"}
        )
        assert "r1" in result
        assert "unknown indicator bad" in result

    def test_threads_look_back_days(self, monkeypatch):
        seen = _route_recorder(monkeypatch)
        get_indicators.invoke(
            {"symbol": "AAPL", "indicator": "rsi", "curr_date": "2024-05-10",
             "look_back_days": 60}
        )
        assert seen[0]["look_back_days"] == 60
        assert seen[0]["curr_date"] == "2024-05-10"

    def test_default_look_back_days_is_30(self, monkeypatch):
        seen = _route_recorder(monkeypatch)
        get_indicators.invoke(
            {"symbol": "AAPL", "indicator": "rsi", "curr_date": "2024-05-10"}
        )
        assert seen[0]["look_back_days"] == 30

"""Tests for the Polymarket prediction-market vendor.

Covers the pure helpers ``_parse_json_list`` and ``_is_forward_looking``
(closed/past filtering, missing-prices rejection, bad-endDate tolerance) and
``get_prediction_markets`` (formatting, volume sort, no-match, network-error
degradation). ``requests.get`` is mocked so no network call is made
(polymarket.py was 83% covered).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tradingagents.dataflows import polymarket
from tradingagents.dataflows.polymarket import (
    _is_forward_looking,
    _parse_json_list,
    get_prediction_markets,
)


@pytest.mark.unit
class TestParseJsonList:
    def test_list_returned_as_is(self):
        assert _parse_json_list(["a", "b"]) == ["a", "b"]

    def test_json_string_parsed(self):
        assert _parse_json_list('["yes", "no"]') == ["yes", "no"]

    def test_invalid_string_returns_empty(self):
        assert _parse_json_list("not json") == []

    def test_none_returns_empty(self):
        assert _parse_json_list(None) == []

    def test_int_returns_empty(self):
        assert _parse_json_list(42) == []


def _market(closed=False, end_date=None, prices=None, outcomes=None):
    m = {"question": "q?", "volumeNum": 100}
    if closed:
        m["closed"] = True
    if end_date is not None:
        m["endDate"] = end_date
    if prices is not None:
        m["outcomePrices"] = prices
    if outcomes is not None:
        m["outcomes"] = outcomes
    return m


NOW = datetime(2024, 6, 15, tzinfo=timezone.utc)


@pytest.mark.unit
class TestIsForwardLooking:
    def test_closed_market_excluded(self):
        assert _is_forward_looking(
            _market(closed=True, end_date="2025-01-01T00:00:00Z",
                    prices='["0.7"]', outcomes='["Yes"]'), NOW) is False

    def test_past_end_date_excluded(self):
        assert _is_forward_looking(
            _market(end_date="2024-01-01T00:00:00Z", prices='["0.7"]', outcomes='["Yes"]'), NOW) is False

    def test_open_future_market_with_prices_included(self):
        assert _is_forward_looking(
            _market(end_date="2025-01-01T00:00:00Z", prices='["0.7"]', outcomes='["Yes"]'), NOW) is True

    def test_open_market_without_prices_excluded(self):
        assert _is_forward_looking(
            _market(end_date="2025-01-01T00:00:00Z", outcomes='["Yes"]'), NOW) is False

    def test_open_market_without_outcomes_excluded(self):
        assert _is_forward_looking(
            _market(end_date="2025-01-01T00:00:00Z", prices='["0.7"]'), NOW) is False

    def test_bad_end_date_tolerated(self):
        # Unparseable endDate is ignored; the prices/outcomes check still runs.
        assert _is_forward_looking(
            _market(end_date="not-a-date", prices='["0.7"]', outcomes='["Yes"]'), NOW) is True

    def test_no_end_date_with_prices_included(self):
        assert _is_forward_looking(
            _market(prices='["0.7"]', outcomes='["Yes"]'), NOW) is True

    def test_list_prices_accepted_directly(self):
        # outcomePrices may already be a list (not a JSON string).
        assert _is_forward_looking(
            _market(end_date="2025-01-01T00:00:00Z", prices=["0.7"], outcomes=["Yes"]), NOW) is True


def _mock_response(json_data):
    r = MagicMock()
    r.json = MagicMock(return_value=json_data)
    r.raise_for_status = MagicMock()
    return r


@pytest.mark.unit
class TestGetPredictionMarkets:
    def _events(self, markets):
        return {"events": [{"markets": markets}]}

    def test_no_matches_returns_no_open_message(self):
        with patch.object(polymarket, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(self._events([]))
            mock_req.RequestException = Exception
            result = get_prediction_markets("obscure topic")
        assert "No open prediction markets" in result

    def test_formats_matching_markets_with_probability(self):
        markets = [
            _market(end_date="2030-01-01T00:00:00Z", prices='["0.76"]', outcomes='["Yes"]'),
        ]
        markets[0]["question"] = "Will Fed cut in 2024?"
        markets[0]["volumeNum"] = 50000
        with patch.object(polymarket, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(self._events(markets))
            mock_req.RequestException = Exception
            result = get_prediction_markets("Fed rate cut")
        assert "Will Fed cut in 2024?" in result
        assert "76%" in result
        assert "$50,000" in result

    def test_sorts_by_volume_descending(self):
        markets = [
            _market(end_date="2030-01-01T00:00:00Z", prices='["0.5"]', outcomes='["Yes"]'),
            _market(end_date="2030-01-01T00:00:00Z", prices='["0.6"]', outcomes='["Yes"]'),
        ]
        markets[0]["question"] = "low-volume"
        markets[0]["volumeNum"] = 100
        markets[1]["question"] = "high-volume"
        markets[1]["volumeNum"] = 9999
        with patch.object(polymarket, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(self._events(markets))
            mock_req.RequestException = Exception
            result = get_prediction_markets("topic")
        assert result.index("high-volume") < result.index("low-volume")

    def test_network_error_returns_unavailable_message(self):
        with patch.object(polymarket, "requests") as mock_req:
            mock_req.get.side_effect = Exception("timeout")
            mock_req.RequestException = Exception
            result = get_prediction_markets("Fed rate cut")
        assert "unavailable" in result
        assert "timeout" in result

    def test_limit_caps_number_of_markets(self):
        markets = [
            _market(end_date="2030-01-01T00:00:00Z", prices='["0.5"]', outcomes='["Yes"]')
            for _ in range(5)
        ]
        for i, m in enumerate(markets):
            m["question"] = f"q{i}"
            m["volumeNum"] = 100 - i
        with patch.object(polymarket, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(self._events(markets))
            mock_req.RequestException = Exception
            result = get_prediction_markets("topic", limit=2)
        assert "q0" in result and "q1" in result
        assert "q2" not in result  # beyond limit

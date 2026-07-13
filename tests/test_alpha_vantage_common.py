"""Tests for Alpha Vantage common helpers.

Covers ``get_api_key`` env handling, ``format_datetime_for_api`` format
conversion, ``_make_api_request`` response classification (rate-limit vs
bad-key vs CSV data vs entitlement), and ``_filter_csv_by_date_range``.
These were uncovered (alpha_vantage_common.py 56%); ``requests.get`` and the
API key are mocked so no network call is made.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from tradingagents.dataflows import alpha_vantage_common as av
from tradingagents.dataflows.alpha_vantage_common import (
    AlphaVantageNotConfiguredError,
    AlphaVantageRateLimitError,
    _filter_csv_by_date_range,
    _make_api_request,
    format_datetime_for_api,
    get_api_key,
)


@pytest.mark.unit
class TestGetApiKey:
    def test_raises_when_unset(self, monkeypatch):
        monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
        with pytest.raises(AlphaVantageNotConfiguredError, match="environment variable"):
            get_api_key()

    def test_returns_when_set(self, monkeypatch):
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key-123")
        assert get_api_key() == "test-key-123"


@pytest.mark.unit
class TestFormatDatetimeForApi:
    def test_date_string_yields_midnight(self):
        assert format_datetime_for_api("2024-01-15") == "20240115T0000"

    def test_datetime_string_preserves_time(self):
        assert format_datetime_for_api("2024-01-15 14:30") == "20240115T1430"

    def test_already_formatted_passthrough(self):
        assert format_datetime_for_api("20240115T0000") == "20240115T0000"

    def test_datetime_object(self):
        dt = datetime(2024, 1, 15, 9, 5)
        assert format_datetime_for_api(dt) == "20240115T0905"

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="Unsupported date format"):
            format_datetime_for_api("not-a-date")

    def test_wrong_type_raises(self):
        with pytest.raises(ValueError, match="string or datetime"):
            format_datetime_for_api(12345)


def _mock_response(text):
    r = MagicMock()
    r.text = text
    r.raise_for_status = MagicMock()
    return r


@pytest.mark.unit
class TestMakeApiRequest:
    def test_csv_response_returned_verbatim(self, monkeypatch):
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "k")
        csv = "timestamp,close\n2024-01-01,100\n"
        with patch.object(av, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(csv)
            result = _make_api_request("TIME_SERIES_DAILY", {"symbol": "AAPL"})
        assert result == csv

    def test_rate_limit_notice_raises_rate_limit_error(self, monkeypatch):
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "k")
        with patch.object(av, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(
                '{"Information": "Thank you for using Alpha Vantage. Our standard API rate limit is 25 requests per day."}'
            )
            with pytest.raises(AlphaVantageRateLimitError):
                _make_api_request("F", {})

    def test_premium_notice_raises_rate_limit_error(self, monkeypatch):
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "k")
        with patch.object(av, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(
                '{"Information": "This is a premium endpoint."}'
            )
            with pytest.raises(AlphaVantageRateLimitError):
                _make_api_request("F", {})

    def test_bad_key_notice_raises_not_configured(self, monkeypatch):
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "k")
        with patch.object(av, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(
                '{"Note": "Invalid API key. Please claim a free key."}'
            )
            with pytest.raises(AlphaVantageNotConfiguredError):
                _make_api_request("F", {})

    def test_entitlement_included_when_present(self, monkeypatch):
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "k")
        csv = "timestamp,close\n2024-01-01,100\n"
        with patch.object(av, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(csv)
            _make_api_request("F", {"entitlement": "real-time"})
            sent_params = mock_req.get.call_args.kwargs["params"]
            assert sent_params["entitlement"] == "real-time"

    def test_entitlement_dropped_when_empty(self, monkeypatch):
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "k")
        csv = "timestamp,close\n2024-01-01,100\n"
        with patch.object(av, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(csv)
            _make_api_request("F", {"entitlement": None})
            sent_params = mock_req.get.call_args.kwargs["params"]
            assert "entitlement" not in sent_params


@pytest.mark.unit
class TestFilterCsvByDateRange:
    def test_filters_rows_outside_range(self):
        csv = "timestamp,close\n2024-01-01,100\n2024-01-15,110\n2024-02-01,120\n"
        out = _filter_csv_by_date_range(csv, "2024-01-10", "2024-01-20")
        assert "2024-01-01,100" not in out
        assert "2024-01-15,110" in out
        assert "2024-02-01,120" not in out

    def test_empty_input_returned_unchanged(self):
        assert _filter_csv_by_date_range("", "2024-01-01", "2024-02-01") == ""
        assert _filter_csv_by_date_range("   ", "2024-01-01", "2024-02-01") == "   "

    def test_all_rows_in_range_kept(self):
        csv = "timestamp,close\n2024-01-01,100\n2024-01-02,101\n"
        out = _filter_csv_by_date_range(csv, "2024-01-01", "2024-01-31")
        assert "100" in out and "101" in out

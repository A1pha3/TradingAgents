"""Tests for FRED macro-data helpers.

Covers ``_resolve_series_id`` (alias mapping, normalization, raw-ID passthrough,
descriptive-phrase rejection), ``get_api_key`` (env handling), and ``_request``
(400 error surfacing). These were partially uncovered (fred.py 82%);
``requests.get`` is mocked so no network call is made.
"""

from unittest.mock import MagicMock, patch

import pytest

from tradingagents.dataflows import fred
from tradingagents.dataflows.fred import (
    FredNotConfiguredError,
    _request,
    _resolve_series_id,
    get_api_key,
)


@pytest.mark.unit
class TestResolveSeriesId:
    @pytest.mark.parametrize("alias,series_id", [
        ("cpi", "CPIAUCSL"),
        ("unemployment", "UNRATE"),
        ("fed_funds_rate", "FEDFUNDS"),
        ("10y_treasury", "DGS10"),
        ("10y_2y_spread", "T10Y2Y"),
        ("vix", "VIXCLS"),
        ("gdp", "GDP"),
    ])
    def test_known_alias_maps_to_series_id(self, alias, series_id):
        assert _resolve_series_id(alias) == series_id

    def test_alias_case_insensitive(self):
        assert _resolve_series_id("CPI") == "CPIAUCSL"
        assert _resolve_series_id("Unemployment") == "UNRATE"

    def test_alias_normalizes_spaces_and_hyphens(self):
        assert _resolve_series_id("10y treasury") == "DGS10"
        assert _resolve_series_id("fed-funds-rate") == "FEDFUNDS"

    def test_raw_series_id_passthrough(self):
        assert _resolve_series_id("DGS10") == "DGS10"
        assert _resolve_series_id("CPIAUCSL") == "CPIAUCSL"

    def test_descriptive_phrase_rejected(self):
        with pytest.raises(ValueError, match="not a known macro alias"):
            _resolve_series_id("bank of japan rate")

    def test_empty_rejected(self):
        with pytest.raises(ValueError, match="not a known macro alias"):
            _resolve_series_id("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValueError, match="not a known macro alias"):
            _resolve_series_id("   ")

    def test_overlong_rejected(self):
        with pytest.raises(ValueError, match="not a known macro alias"):
            _resolve_series_id("A" * 31)


@pytest.mark.unit
class TestGetApiKey:
    def test_raises_when_unset(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with pytest.raises(FredNotConfiguredError, match="environment variable"):
            get_api_key()

    def test_returns_when_set(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "fred-key-42")
        assert get_api_key() == "fred-key-42"


def _mock_response(status_code=200, json_data=None, text=""):
    r = MagicMock()
    r.status_code = status_code
    r.text = text or (str(json_data) if json_data else "")
    r.json = MagicMock(return_value=json_data if json_data is not None else {})
    return r


@pytest.mark.unit
class TestRequest:
    def test_ok_returns_json(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "k")
        with patch.object(fred, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(200, {"seriess": [{"title": "x"}]})
            result = _request("series", {"series_id": "CPIAUCSL"})
        assert result == {"seriess": [{"title": "x"}]}

    def test_400_with_json_error_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "k")
        with patch.object(fred, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(
                400, {"error_message": "Bad series id"}, text='{"error_message": "Bad series id"}'
            )
            with pytest.raises(ValueError, match="FRED request failed: Bad series id"):
                _request("series", {"series_id": "X"})

    def test_400_with_non_json_body_raises_value_error_with_text(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "k")
        response = _mock_response(400, text="plain text error")
        response.json.side_effect = ValueError("not json")
        with patch.object(fred, "requests") as mock_req:
            mock_req.get.return_value = response
            with pytest.raises(ValueError, match="plain text error"):
                _request("series", {"series_id": "X"})

    def test_api_key_and_file_type_included_in_params(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "my-key")
        with patch.object(fred, "requests") as mock_req:
            mock_req.get.return_value = _mock_response(200, {"ok": True})
            _request("series", {"series_id": "CPIAUCSL"})
            sent = mock_req.get.call_args.kwargs["params"]
            assert sent["api_key"] == "my-key"
            assert sent["file_type"] == "json"
            assert sent["series_id"] == "CPIAUCSL"

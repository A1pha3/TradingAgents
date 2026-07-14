"""Tests for yfinance_news pure helpers.

Covers ``_extract_article_data`` (nested 'content' + flat fallback, date
parsing) and ``_in_news_window`` (dated-article windowing + undated-article
look-ahead safety). These helpers were partially uncovered (yfinance_news.py
84%); no yfinance call is made — only the pure functions are exercised.
"""

from datetime import datetime

import pytest

from tradingagents.dataflows.yfinance_news import (
    _extract_article_data,
    _in_news_window,
)


@pytest.mark.unit
class TestExtractArticleData:
    def test_nested_content_structure(self):
        article = {
            "content": {
                "title": "AAPL up",
                "summary": "Apple gained on earnings.",
                "provider": {"displayName": "Reuters"},
                "canonicalUrl": {"url": "https://example.com/a"},
                "pubDate": "2024-05-10T13:00:00Z",
            }
        }
        data = _extract_article_data(article)
        assert data["title"] == "AAPL up"
        assert data["summary"] == "Apple gained on earnings."
        assert data["publisher"] == "Reuters"
        assert data["link"] == "https://example.com/a"
        assert data["pub_date"] == datetime.fromisoformat("2024-05-10T13:00:00+00:00")

    def test_nested_uses_click_through_url_when_no_canonical(self):
        article = {
            "content": {
                "title": "t",
                "summary": "",
                "provider": {},
                "clickThroughUrl": {"url": "https://example.com/b"},
            }
        }
        assert _extract_article_data(article)["link"] == "https://example.com/b"

    def test_nested_missing_publisher_defaults_unknown(self):
        article = {"content": {"title": "t"}}
        assert _extract_article_data(article)["publisher"] == "Unknown"

    def test_nested_missing_title_defaults_no_title(self):
        article = {"content": {}}
        assert _extract_article_data(article)["title"] == "No title"

    def test_nested_bad_pub_date_yields_none(self):
        article = {"content": {"title": "t", "pubDate": "not-a-date"}}
        assert _extract_article_data(article)["pub_date"] is None

    def test_flat_structure_with_epoch_time(self):
        article = {
            "title": "flat",
            "summary": "s",
            "publisher": "Bloomberg",
            "link": "https://example.com/c",
            "providerPublishTime": 1715336400,  # 2024-05-10T13:00:00Z
        }
        data = _extract_article_data(article)
        assert data["title"] == "flat"
        assert data["publisher"] == "Bloomberg"
        assert data["pub_date"] is not None
        assert data["pub_date"].year == 2024

    def test_flat_structure_without_time(self):
        article = {"title": "flat"}
        data = _extract_article_data(article)
        assert data["pub_date"] is None
        assert data["title"] == "flat"

    def test_flat_bad_epoch_yields_none(self):
        article = {"title": "t", "providerPublishTime": "not-an-int"}
        assert _extract_article_data(article)["pub_date"] is None


@pytest.mark.unit
class TestInNewsWindow:
    def test_dated_article_inside_window_kept(self):
        pub = datetime(2024, 5, 10, 12, 0)
        start = datetime(2024, 5, 9)
        end = datetime(2024, 5, 10)
        assert _in_news_window(pub, start, end) is True

    def test_dated_article_before_window_excluded(self):
        pub = datetime(2024, 5, 8)
        assert _in_news_window(pub, datetime(2024, 5, 9), datetime(2024, 5, 10)) is False

    def test_dated_article_after_window_excluded(self):
        # Window is [start, end+1day]; an article 2 days after end is excluded.
        pub = datetime(2024, 5, 13, 0, 0)
        assert _in_news_window(pub, datetime(2024, 5, 9), datetime(2024, 5, 10)) is False

    def test_dated_article_at_end_plus_one_kept(self):
        # end+1day boundary is inclusive (catches same-day timezone drift).
        pub = datetime(2024, 5, 11, 0, 0)
        assert _in_news_window(pub, datetime(2024, 5, 9), datetime(2024, 5, 10)) is True

    def test_undated_article_kept_only_in_live_window(self):
        # An undated article is kept only when the window reaches "now"
        # (live run). A recent end date -> kept; an old end date -> excluded.
        from datetime import datetime as dt
        recent_end = dt.now()
        assert _in_news_window(None, dt(2024, 1, 1), recent_end) is True
        old_end = dt(2020, 1, 1)
        assert _in_news_window(None, dt(2020, 1, 1), old_end) is False

"""Tests for write_report_tree section branching.

``write_report_tree`` renders a run's per-section markdown plus a consolidated
``complete_report.md``. Each section is written only when its source state key
is non-empty, so a partial run produces a partial tree without empty files.
The sentiment/fundamentals/bear/neutral/portfolio branches were uncovered by
the existing reporting tests.
"""

import pytest

from tradingagents.reporting import write_report_tree


def _full_state():
    return {
        "market_report": "market analysis text",
        "sentiment_report": "sentiment analysis text",
        "news_report": "news analysis text",
        "fundamentals_report": "fundamentals analysis text",
        "investment_debate_state": {
            "bull_history": "bull case",
            "bear_history": "bear case",
            "judge_decision": "manager synthesis",
        },
        "trader_investment_plan": "trader plan text",
        "risk_debate_state": {
            "aggressive_history": "aggressive risk",
            "conservative_history": "conservative risk",
            "neutral_history": "neutral risk",
            "judge_decision": "portfolio decision",
        },
    }


@pytest.mark.unit
class TestWriteReportTree:
    def test_full_state_writes_all_sections(self, tmp_path):
        report = write_report_tree(_full_state(), "AAPL", tmp_path / "out")
        assert report.name == "complete_report.md"
        text = report.read_text(encoding="utf-8")
        assert "## I. Analyst Team Reports" in text
        assert "## II. Research Team Decision" in text
        assert "## III. Trading Team Plan" in text
        assert "## IV. Risk Management Team Decision" in text
        assert "## V. Portfolio Manager Decision" in text
        # Per-section files exist.
        assert (tmp_path / "out" / "1_analysts" / "market.md").exists()
        assert (tmp_path / "out" / "1_analysts" / "sentiment.md").exists()
        assert (tmp_path / "out" / "1_analysts" / "news.md").exists()
        assert (tmp_path / "out" / "1_analysts" / "fundamentals.md").exists()
        assert (tmp_path / "out" / "2_research" / "bull.md").exists()
        assert (tmp_path / "out" / "2_research" / "bear.md").exists()
        assert (tmp_path / "out" / "2_research" / "manager.md").exists()
        assert (tmp_path / "out" / "3_trading" / "trader.md").exists()
        assert (tmp_path / "out" / "4_risk" / "aggressive.md").exists()
        assert (tmp_path / "out" / "4_risk" / "conservative.md").exists()
        assert (tmp_path / "out" / "4_risk" / "neutral.md").exists()
        assert (tmp_path / "out" / "5_portfolio" / "decision.md").exists()

    def test_empty_state_writes_only_consolidated_report(self, tmp_path):
        report = write_report_tree({}, "AAPL", tmp_path / "out")
        text = report.read_text(encoding="utf-8")
        assert "Trading Analysis Report: AAPL" in text
        assert "## " not in text  # no section headers
        # No section directories created for an empty run.
        assert not (tmp_path / "out" / "1_analysts").exists()
        assert not (tmp_path / "out" / "4_risk").exists()

    def test_sentiment_only_creates_sentiment_file(self, tmp_path):
        state = {"sentiment_report": "sentiment only"}
        write_report_tree(state, "X", tmp_path / "out")
        assert (tmp_path / "out" / "1_analysts" / "sentiment.md").exists()
        assert not (tmp_path / "out" / "1_analysts" / "market.md").exists()
        text = (tmp_path / "out" / "complete_report.md").read_text(encoding="utf-8")
        assert "Sentiment Analyst" in text
        assert "Market Analyst" not in text

    def test_fundamentals_only_creates_fundamentals_file(self, tmp_path):
        state = {"fundamentals_report": "fundamentals only"}
        write_report_tree(state, "X", tmp_path / "out")
        assert (tmp_path / "out" / "1_analysts" / "fundamentals.md").exists()
        text = (tmp_path / "out" / "complete_report.md").read_text(encoding="utf-8")
        assert "Fundamentals Analyst" in text

    def test_research_bear_only(self, tmp_path):
        state = {"investment_debate_state": {"bear_history": "bear only"}}
        write_report_tree(state, "X", tmp_path / "out")
        assert (tmp_path / "out" / "2_research" / "bear.md").exists()
        assert not (tmp_path / "out" / "2_research" / "bull.md").exists()
        assert not (tmp_path / "out" / "2_research" / "manager.md").exists()

    def test_research_judge_decision_creates_manager_file(self, tmp_path):
        state = {"investment_debate_state": {"judge_decision": "manager only"}}
        write_report_tree(state, "X", tmp_path / "out")
        assert (tmp_path / "out" / "2_research" / "manager.md").exists()

    def test_risk_neutral_and_conservative_only(self, tmp_path):
        state = {
            "risk_debate_state": {
                "conservative_history": "cons only",
                "neutral_history": "neut only",
            }
        }
        write_report_tree(state, "X", tmp_path / "out")
        assert (tmp_path / "out" / "4_risk" / "conservative.md").exists()
        assert (tmp_path / "out" / "4_risk" / "neutral.md").exists()
        assert not (tmp_path / "out" / "4_risk" / "aggressive.md").exists()
        # No judge_decision -> no portfolio section.
        assert not (tmp_path / "out" / "5_portfolio").exists()

    def test_risk_judge_decision_creates_portfolio_section(self, tmp_path):
        state = {"risk_debate_state": {"judge_decision": "final call"}}
        write_report_tree(state, "X", tmp_path / "out")
        assert (tmp_path / "out" / "5_portfolio" / "decision.md").exists()
        text = (tmp_path / "out" / "complete_report.md").read_text(encoding="utf-8")
        assert "## V. Portfolio Manager Decision" in text
        assert "final call" in text

    def test_trader_plan_creates_trading_section(self, tmp_path):
        state = {"trader_investment_plan": "go long"}
        write_report_tree(state, "X", tmp_path / "out")
        assert (tmp_path / "out" / "3_trading" / "trader.md").exists()
        text = (tmp_path / "out" / "complete_report.md").read_text(encoding="utf-8")
        assert "## III. Trading Team Plan" in text

    def test_creates_save_path_if_missing(self, tmp_path):
        target = tmp_path / "nested" / "deep" / "out"
        report = write_report_tree({}, "X", target)
        assert report.exists()

    def test_header_contains_ticker(self, tmp_path):
        report = write_report_tree({}, "NVDA", tmp_path / "out")
        assert "NVDA" in report.read_text(encoding="utf-8")

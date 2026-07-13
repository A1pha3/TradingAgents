"""Tests for TradingMemoryLog edge cases not covered by test_memory_log.

Covers: get_past_context break/empty branches, _parse_entry malformed tags,
_format_reflection_only truncation, update_with_outcome no-match, and
batch_update_with_outcomes early-return / no-match paths.
"""

import pytest

from tradingagents.agents.utils.memory import TradingMemoryLog

_SEPARATOR = "\n\n<!-- ENTRY_END -->\n\n"


def _write_resolved(path, entries):
    """Write resolved log entries directly (date, ticker, rating, decision, reflection)."""
    for e in entries:
        tag = f"[{e['date']} | {e['ticker']} | {e.get('rating', 'Buy')} | +1.0% | +0.5% | 5d]"
        body = f"DECISION:\n{e.get('decision', 'd')}"
        if e.get("reflection"):
            body += f"\n\nREFLECTION:\n{e['reflection']}"
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{tag}\n\n{body}{_SEPARATOR}")


@pytest.mark.unit
class TestGetPastContextEdges:
    def test_returns_empty_when_no_resolved_entries(self, tmp_path):
        p = tmp_path / "log.md"
        log = TradingMemoryLog({"memory_log_path": str(p)})
        assert log.get_past_context("AAPL") == ""

    def test_returns_empty_when_both_quotas_zero(self, tmp_path):
        # Covers the `if not same and not cross: return ""` branch.
        p = tmp_path / "log.md"
        _write_resolved(p, [{"date": "2024-01-01", "ticker": "AAPL"}])
        log = TradingMemoryLog({"memory_log_path": str(p)})
        assert log.get_past_context("AAPL", n_same=0, n_cross=0) == ""

    def test_breaks_once_both_quotas_filled(self, tmp_path):
        # Covers the break branch: stop scanning once same + cross quotas fill.
        p = tmp_path / "log.md"
        entries = [
            {"date": f"2024-01-{i:02d}", "ticker": "AAPL" if i % 2 else "MSFT"}
            for i in range(1, 13)
        ]
        _write_resolved(p, entries)
        log = TradingMemoryLog({"memory_log_path": str(p)})
        ctx = log.get_past_context("AAPL", n_same=2, n_cross=2)
        assert "Past analyses of AAPL" in ctx
        assert "Recent cross-ticker lessons" in ctx

    def test_cross_ticker_only(self, tmp_path):
        p = tmp_path / "log.md"
        _write_resolved(p, [{"date": "2024-01-01", "ticker": "MSFT"}])
        log = TradingMemoryLog({"memory_log_path": str(p)})
        ctx = log.get_past_context("AAPL")
        assert "Recent cross-ticker lessons" in ctx
        assert "Past analyses of AAPL" not in ctx


@pytest.mark.unit
class TestParseEntryMalformed:
    def test_empty_raw_returns_none(self, tmp_path):
        log = TradingMemoryLog({"memory_log_path": str(tmp_path / "log.md")})
        assert log._parse_entry("   ") is None

    def test_tag_without_brackets_returns_none(self, tmp_path):
        log = TradingMemoryLog({"memory_log_path": str(tmp_path / "log.md")})
        assert log._parse_entry("not a tag\nDECISION:\nx") is None

    def test_tag_with_too_few_fields_returns_none(self, tmp_path):
        log = TradingMemoryLog({"memory_log_path": str(tmp_path / "log.md")})
        assert log._parse_entry("[2024-01-01 | AAPL]") is None

    def test_pending_entry_parsed(self, tmp_path):
        log = TradingMemoryLog({"memory_log_path": str(tmp_path / "log.md")})
        e = log._parse_entry(
            "[2024-01-01 | AAPL | Buy | pending]\n\nDECISION:\ngo long"
        )
        assert e is not None
        assert e["pending"] is True
        assert e["raw"] is None
        assert e["decision"] == "go long"

    def test_resolved_entry_parsed(self, tmp_path):
        log = TradingMemoryLog({"memory_log_path": str(tmp_path / "log.md")})
        e = log._parse_entry(
            "[2024-01-01 | AAPL | Buy | +1.0% | +0.5% | 5d]\n\nDECISION:\ngo long\n\nREFLECTION:\nlearned"
        )
        assert e is not None
        assert e["pending"] is False
        assert e["raw"] == "+1.0%"
        assert e["alpha"] == "+0.5%"
        assert e["holding"] == "5d"
        assert e["reflection"] == "learned"


@pytest.mark.unit
class TestFormatReflectionOnly:
    def test_truncates_long_decision_when_no_reflection(self, tmp_path):
        log = TradingMemoryLog({"memory_log_path": str(tmp_path / "log.md")})
        e = {
            "date": "2024-01-01", "ticker": "AAPL", "rating": "Buy",
            "raw": "+1.0%", "alpha": None, "holding": None,
            "decision": "X" * 500, "reflection": "",
        }
        out = log._format_reflection_only(e)
        assert "..." in out
        assert out.count("X") == 300

    def test_uses_reflection_when_present(self, tmp_path):
        log = TradingMemoryLog({"memory_log_path": str(tmp_path / "log.md")})
        e = {
            "date": "2024-01-01", "ticker": "AAPL", "rating": "Buy",
            "raw": "+1.0%", "alpha": None, "holding": None,
            "decision": "d", "reflection": "lesson learned",
        }
        out = log._format_reflection_only(e)
        assert "lesson learned" in out
        assert "..." not in out


@pytest.mark.unit
class TestUpdateWithOutcomeNoMatch:
    def test_no_op_when_no_pending_entry_matches(self, tmp_path):
        # Covers `if not updated: return`.
        p = tmp_path / "log.md"
        _write_resolved(p, [{"date": "2024-01-01", "ticker": "AAPL"}])
        log = TradingMemoryLog({"memory_log_path": str(p)})
        before = p.read_text(encoding="utf-8")
        log.update_with_outcome("MSFT", "2024-02-01", 0.1, 0.05, 5, "refl")
        assert before == p.read_text(encoding="utf-8")

    def test_no_op_when_log_missing(self, tmp_path):
        log = TradingMemoryLog({"memory_log_path": str(tmp_path / "log.md")})
        # File does not exist -> no-op, no crash.
        log.update_with_outcome("AAPL", "2024-01-01", 0.1, 0.05, 5, "refl")


@pytest.mark.unit
class TestBatchUpdate:
    def test_no_op_when_no_updates(self, tmp_path):
        # Covers the early return for empty updates.
        p = tmp_path / "log.md"
        _write_resolved(p, [{"date": "2024-01-01", "ticker": "AAPL"}])
        log = TradingMemoryLog({"memory_log_path": str(p)})
        before = p.read_text(encoding="utf-8")
        log.batch_update_with_outcomes([])
        assert before == p.read_text(encoding="utf-8")

    def test_no_op_when_no_matching_pending(self, tmp_path):
        # Covers the `if not matched` path.
        p = tmp_path / "log.md"
        _write_resolved(p, [{"date": "2024-01-01", "ticker": "AAPL"}])
        log = TradingMemoryLog({"memory_log_path": str(p)})
        log.batch_update_with_outcomes([{
            "ticker": "MSFT", "trade_date": "2024-02-01",
            "raw_return": 0.1, "alpha_return": 0.05, "holding_days": 5,
            "reflection": "r",
        }])
        assert "REFLECTION" not in p.read_text(encoding="utf-8")

    def test_resolves_pending_entry(self, tmp_path):
        p = tmp_path / "log.md"
        log = TradingMemoryLog({"memory_log_path": str(p)})
        log.store_decision("AAPL", "2024-01-01", "Rating: Buy\nDo it.")
        log.batch_update_with_outcomes([{
            "ticker": "AAPL", "trade_date": "2024-01-01",
            "raw_return": 0.12, "alpha_return": 0.04, "holding_days": 5,
            "reflection": "good call",
        }])
        text = p.read_text(encoding="utf-8")
        assert "REFLECTION:\ngood call" in text
        assert "pending" not in text
        assert "+12.0%" in text

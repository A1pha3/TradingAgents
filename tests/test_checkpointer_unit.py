"""Tests for the checkpointer helpers.

Covers thread_id determinism/signature folding, _db_path ticker hardening,
checkpoint_step/clear_checkpoint/has_checkpoint no-DB paths, and
clear_all_checkpoints file counting — the branches that were uncovered
(checkpointer.py 82%).
"""

import pytest

from tradingagents.graph import checkpointer


@pytest.mark.unit
class TestThreadId:
    def test_deterministic_for_same_inputs(self):
        assert checkpointer.thread_id("AAPL", "2024-01-01") == checkpointer.thread_id("AAPL", "2024-01-01")

    def test_different_ticker_yields_different_id(self):
        assert checkpointer.thread_id("AAPL", "2024-01-01") != checkpointer.thread_id("MSFT", "2024-01-01")

    def test_different_date_yields_different_id(self):
        assert checkpointer.thread_id("AAPL", "2024-01-01") != checkpointer.thread_id("AAPL", "2024-01-02")

    def test_signature_folds_into_id(self):
        base = checkpointer.thread_id("AAPL", "2024-01-01")
        signed = checkpointer.thread_id("AAPL", "2024-01-01", "analysts=market")
        assert base != signed

    def test_empty_signature_matches_omitted(self):
        assert checkpointer.thread_id("AAPL", "2024-01-01", "") == checkpointer.thread_id("AAPL", "2024-01-01")

    def test_id_is_16_hex_chars(self):
        tid = checkpointer.thread_id("AAPL", "2024-01-01", "sig")
        assert len(tid) == 16
        int(tid, 16)  # parses as hex


@pytest.mark.unit
class TestDbPath:
    def test_uppercases_ticker_and_creates_dir(self, tmp_path):
        p = checkpointer._db_path(tmp_path, "aapl")
        assert p == tmp_path / "checkpoints" / "AAPL.db"
        assert (tmp_path / "checkpoints").is_dir()

    def test_rejects_path_traversal_ticker(self, tmp_path):
        with pytest.raises(ValueError):
            checkpointer._db_path(tmp_path, "../../etc/passwd")


@pytest.mark.unit
class TestNoDbPaths:
    def test_checkpoint_step_returns_none_when_no_db(self, tmp_path):
        # Covers the `if not db.exists(): return None` branch.
        assert checkpointer.checkpoint_step(tmp_path, "AAPL", "2024-01-01") is None

    def test_has_checkpoint_false_when_no_db(self, tmp_path):
        assert checkpointer.has_checkpoint(tmp_path, "AAPL", "2024-01-01") is False

    def test_clear_checkpoint_no_op_when_no_db(self, tmp_path):
        # Covers the `if not db.exists(): return` branch — must not crash.
        checkpointer.clear_checkpoint(tmp_path, "AAPL", "2024-01-01")

    def test_clear_all_checkpoints_returns_zero_when_no_dir(self, tmp_path):
        assert checkpointer.clear_all_checkpoints(tmp_path) == 0


@pytest.mark.unit
class TestClearAllCheckpoints:
    def test_deletes_all_db_files_and_returns_count(self, tmp_path):
        cp_dir = tmp_path / "checkpoints"
        cp_dir.mkdir()
        (cp_dir / "AAPL.db").write_bytes(b"x")
        (cp_dir / "MSFT.db").write_bytes(b"x")
        (cp_dir / "not_a_db.txt").write_text("ignore me")  # not a .db -> kept

        count = checkpointer.clear_all_checkpoints(tmp_path)
        assert count == 2
        assert not (cp_dir / "AAPL.db").exists()
        assert not (cp_dir / "MSFT.db").exists()
        assert (cp_dir / "not_a_db.txt").exists()  # non-db files untouched

    def test_idempotent_when_dir_empty(self, tmp_path):
        (tmp_path / "checkpoints").mkdir()
        assert checkpointer.clear_all_checkpoints(tmp_path) == 0

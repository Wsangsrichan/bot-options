import os
import tempfile

import pytest

from src.storage import OptionsStore


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = OptionsStore(db_path=path)
    yield s
    s.close()
    os.unlink(path)


def test_init_creates_tables(store):
    tables = store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='snapshots'"
    ).fetchall()
    assert len(tables) == 1


def test_save_and_load_snapshot(store):
    opts = [{"strike": 520, "option_type": "C", "open_interest": 100}]
    store.save_snapshot("SPY", 522.5, "2026-05-13T10:00:00Z", 1, opts)
    rows = store.get_snapshots("SPY")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "SPY"
    assert rows[0]["underlying_price"] == 522.5
    assert rows[0]["options"] == opts


def test_get_latest(store):
    opts_a = [{"strike": 520}]
    opts_b = [{"strike": 525}]
    store.save_snapshot("SPY", 522.0, "2026-05-13T09:00:00Z", 1, opts_a)
    store.save_snapshot("SPY", 523.0, "2026-05-13T10:00:00Z", 1, opts_b)
    latest = store.get_latest("SPY")
    assert latest is not None
    assert latest["underlying_price"] == 523.0


def test_filter_by_ticker(store):
    store.save_snapshot("SPY", 522.0, "2026-05-13T10:00:00Z", 0, [])
    store.save_snapshot("QQQ", 430.0, "2026-05-13T10:00:00Z", 0, [])
    store.save_snapshot("QQQ", 431.0, "2026-05-13T11:00:00Z", 0, [])
    assert len(store.get_snapshots("SPY")) == 1
    assert len(store.get_snapshots("QQQ")) == 2


def test_save_and_get_open_positions(store):
    pid = store.save_position("SPY", "C", 525.0, "2026-06-20", 5.28, 520.50, 0.42, 0.185, 1)
    open_pos = store.get_open_positions()
    assert len(open_pos) == 1
    assert open_pos[0]["ticker"] == "SPY"
    assert open_pos[0]["id"] == pid


def test_close_position(store):
    pid = store.save_position("SPY", "C", 525.0, "2026-06-20", 5.28, 520.50)
    store.close_position(pid, 8.50, "2026-05-14T10:00:00Z", 322.0)
    assert len(store.get_open_positions()) == 0
    history = store.get_position_history()
    assert len(history) == 1
    assert history[0]["pnl"] == 322.0


def test_get_account_summary(store):
    store.save_position("SPY", "C", 525.0, "2026-06-20", 5.28, 520.50)
    pid2 = store.save_position("QQQ", "P", 430.0, "2026-07-18", 3.15, 432.0)
    store.close_position(pid2, 6.30, "2026-05-15T10:00:00Z", 315.0)
    summary = store.get_account_summary()
    assert summary["open_count"] == 1
    assert summary["closed_count"] == 1
    assert summary["total_pnl"] == 315.0
    assert summary["total_invested"] == 528.0

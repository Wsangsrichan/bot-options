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

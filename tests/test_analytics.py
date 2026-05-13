import os
import tempfile

import pytest

from src.storage import OptionsStore
from src.analytics import Analytics


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = OptionsStore(db_path=path)
    yield s
    s.close()
    os.unlink(path)


@pytest.fixture
def analytics(store):
    return Analytics(store)


def _close(store, pnl, exit_time="2026-05-14T10:00:00Z"):
    pid = store.save_position("SPY", "C", 525.0, "2026-06-20", 5.0, 520.0)
    store.close_position(pid, 5.0 + pnl / 100, exit_time, pnl)
    return pid


def test_empty_positions_returns_zeros(analytics):
    m = analytics.calculate()
    assert m["total_trades"] == 0
    assert m["win_rate"] == 0
    assert m["sharpe_ratio"] == 0


def test_single_trade(analytics, store):
    _close(store, 150)
    m = analytics.calculate()
    assert m["total_trades"] == 1
    assert m["winning_trades"] == 1
    assert m["win_rate"] == 100.0
    assert m["total_pnl"] == 150


def test_mixed_wins_losses(analytics, store):
    _close(store, 200, "2026-05-14T10:00:00Z")
    _close(store, -100, "2026-05-15T10:00:00Z")
    _close(store, 300, "2026-05-16T10:00:00Z")
    m = analytics.calculate()
    assert m["total_trades"] == 3
    assert m["winning_trades"] == 2
    assert m["losing_trades"] == 1
    assert m["win_rate"] == pytest.approx(66.7, abs=0.1)
    assert m["total_pnl"] == 400
    assert m["profit_factor"] == pytest.approx(5.0)


def test_max_drawdown_and_sharpe(analytics, store):
    _close(store, 100, "2026-05-14T10:00:00Z")
    _close(store, 200, "2026-05-15T10:00:00Z")
    _close(store, -300, "2026-05-16T10:00:00Z")
    _close(store, 50, "2026-05-17T10:00:00Z")
    m = analytics.calculate()
    # Equity curve: 0→100→300→0→50, peak=300, max DD=300
    assert m["max_drawdown_pct"] == pytest.approx(100.0, abs=0.1)
    assert m["sharpe_ratio"] != 0  # has variance

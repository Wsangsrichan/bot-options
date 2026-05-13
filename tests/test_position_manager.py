import os
import tempfile

import pytest

from src.storage import OptionsStore
from src.position_manager import PositionManager


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = OptionsStore(db_path=path)
    yield s
    s.close()
    os.unlink(path)


@pytest.fixture
def pm(store):
    return PositionManager(store, initial_balance=10000)


def _sample_alert(**overrides):
    alert = {
        "ticker": "SPY",
        "option_type": "C",
        "strike": 525.0,
        "expiration": "2026-06-20",
        "bid": 5.20,
        "ask": 5.35,
        "delta": 0.42,
        "iv": 0.185,
    }
    alert.update(overrides)
    return alert


def test_open_position(pm):
    pos_id = pm.open_position(_sample_alert(), spot_price=520.50)
    assert pos_id is not None
    assert isinstance(pos_id, int)


def test_open_position_no_bid_ask(pm):
    pos_id = pm.open_position(_sample_alert(bid=0, ask=0), spot_price=520.50)
    assert pos_id is None


def test_close_position(pm):
    pos_id = pm.open_position(_sample_alert(), spot_price=520.50)
    pnl = pm.close_position(pos_id, exit_price=8.50, reason="take_profit")
    assert pnl > 0
    assert len(pm.store.get_open_positions()) == 0


def test_portfolio_summary(pm):
    portfolio = pm.get_portfolio()
    assert portfolio["initial_balance"] == 10000
    assert portfolio["cash"] == 10000.0
    assert portfolio["total_pnl"] == 0
    assert portfolio["open_positions"] == 0


def test_portfolio_after_trade(pm):
    pm.open_position(_sample_alert(), spot_price=520.50)
    portfolio = pm.get_portfolio()
    assert portfolio["open_positions"] == 1
    assert portfolio["cash"] < 10000


def test_insufficient_cash(pm):
    cheap = PositionManager(pm.store, initial_balance=10)
    pos_id = cheap.open_position(_sample_alert(bid=5.0, ask=5.0), spot_price=520.50)
    assert pos_id is None

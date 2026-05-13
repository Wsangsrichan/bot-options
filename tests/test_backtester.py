import os
import pytest
from datetime import datetime, timedelta
from src.storage import OptionsStore
from src.backtester import Backtester


@pytest.fixture
def store_with_data():
    db_path = "/tmp/test_bt.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    store = OptionsStore(db_path)

    base = datetime(2026, 1, 1, 10, 0, 0)
    for i, (spot, days_offset) in enumerate([(520.0, 0), (525.0, 3), (530.0, 7)]):
        ts = (base + timedelta(days=days_offset)).isoformat()
        options = [{
            "strike": 520.0, "option_type": "C",
            "bid": 5.0, "ask": 5.5, "last": 5.25,
            "volume": 100, "open_interest": 200,
            "delta": 0.55, "gamma": 0.02, "theta": -0.5,
            "vega": 0.3, "rho": 0.1, "iv": 0.18,
            "expiration": "2026-01-15"
        }]
        store.save_snapshot("SPY", spot, ts, 1, options)

    yield db_path
    store.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_backtest_basic(store_with_data):
    bt = Backtester(store_path=store_with_data)
    result = bt.run(ticker="SPY", forward_days=5)
    assert "hit_rate" in result
    assert result["total_signals"] > 0
    bt.close()


def test_backtest_no_data():
    bt = Backtester(store_path="/tmp/nonexistent_bt.db")
    result = bt.run(ticker="SPY")
    assert "error" in result
    bt.close()

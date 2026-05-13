import json
import os
import tempfile

import pytest

from src.config import Config
from src.storage import OptionsStore
from src.paper_backtest import PaperBacktest


def _make_config(**overrides):
    cfg = Config.__new__(Config)
    cfg.database_path = ""
    cfg.telegram_bot_token = "fake"
    cfg.telegram_chat_id = "fake"
    cfg.scan_tickers = "SPY,QQQ".split(",")
    cfg.paper_initial_balance = 10000
    cfg.paper_ai_confidence_threshold = 60
    cfg.stop_loss_pct = -0.50
    cfg.take_profit_pct = 1.00
    cfg.min_dte_days = 5
    cfg.trailing_stop_activation = 0.30
    cfg.trailing_stop_distance = 0.15
    cfg.vol_oi_ratio_threshold = 0.8
    cfg.min_contracts = 50
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = OptionsStore(db_path=path)
    yield s
    s.close()
    os.unlink(path)


def _save_snapshots(store):
    """Populate store with sample snapshots."""
    options = json.dumps([
        {
            "strike": 525.0, "expiration": "2026-07-17", "option_type": "C",
            "bid": 5.20, "ask": 5.35, "last": 5.25,
            "volume": 50000, "open_interest": 45000,
            "delta": 0.42, "gamma": 0.08, "theta": -0.15, "vega": 0.22, "iv": 0.185,
        },
        {
            "strike": 515.0, "expiration": "2026-07-17", "option_type": "P",
            "bid": 3.10, "ask": 3.25, "last": 3.15,
            "volume": 30000, "open_interest": 32000,
            "delta": -0.38, "gamma": 0.07, "theta": -0.12, "vega": 0.20, "iv": 0.190,
        },
    ])
    store.save_snapshot("SPY", 520.50, "2026-05-13T10:00:00", 2, json.loads(options))

    # Second option with low volume (should be filtered)
    low_vol_options = json.dumps([
        {
            "strike": 530.0, "expiration": "2026-07-17", "option_type": "C",
            "bid": 2.10, "ask": 2.20, "last": 2.15,
            "volume": 10, "open_interest": 5000,
            "delta": 0.30, "gamma": 0.05, "theta": -0.10, "vega": 0.15, "iv": 0.18,
        },
    ])
    store.save_snapshot("SPY", 521.0, "2026-05-13T11:00:00", 1, json.loads(low_vol_options))


def test_backtest_empty_store():
    cfg = _make_config()
    bt = PaperBacktest(cfg, store=None)
    result = bt.run()
    assert result["total_trades"] == 0
    assert result["equity_curve"] == []


def test_backtest_with_data(store):
    _save_snapshots(store)
    cfg = _make_config(paper_ai_confidence_threshold=50)
    bt = PaperBacktest(cfg, store=store, seed=42)
    result = bt.run()
    assert result["total_alerts"] > 0
    assert result["total_trades"] > 0
    assert "equity_curve" in result
    assert len(result["equity_curve"]) == result["total_trades"]
    assert result["total_pnl"] != 0 or result["total_trades"] > 0


def test_backtest_date_filter(store):
    _save_snapshots(store)
    cfg = _make_config()
    bt = PaperBacktest(cfg, store=store, seed=42)
    # Filter to a date with no data
    result = bt.run(start_date="2099-01-01", end_date="2099-12-31")
    assert result["total_trades"] == 0


def test_backtest_ticker_filter(store):
    _save_snapshots(store)
    cfg = _make_config()
    bt = PaperBacktest(cfg, store=store, seed=42)
    # Filter to ticker not in data
    result = bt.run(tickers=["AAPL"])
    assert result["total_trades"] == 0

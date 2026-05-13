import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.storage import OptionsStore
from src.position_manager import PositionManager
from src.exit_rules import ExitRules
from src.paper_trader import PaperTrader


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


@pytest.fixture
def trader(pm):
    rules = ExitRules()
    return PaperTrader(pm, rules, ai_confidence_threshold=60)


def _alert(**overrides):
    alert = {
        "ticker": "SPY",
        "option_type": "C",
        "strike": 525.0,
        "expiration": "2026-06-20",
        "bid": 5.20,
        "ask": 5.35,
        "delta": 0.42,
        "iv": 0.185,
        "ai_confidence": 0,
        "ai_direction": "neutral",
    }
    alert.update(overrides)
    return alert


def _mock_chain():
    chain = MagicMock()
    chain.ticker = "SPY"
    chain.underlying_price = 520.50
    return chain


@pytest.mark.asyncio
async def test_evaluate_below_threshold(trader):
    result = await trader.evaluate_alert(_alert(ai_confidence=30, ai_direction="bullish"), _mock_chain())
    assert result is None


@pytest.mark.asyncio
async def test_evaluate_neutral_direction(trader):
    result = await trader.evaluate_alert(_alert(ai_confidence=80, ai_direction="neutral"), _mock_chain())
    assert result is None


@pytest.mark.asyncio
async def test_evaluate_opens_position(trader):
    result = await trader.evaluate_alert(
        _alert(ai_confidence=75, ai_direction="bullish"), _mock_chain()
    )
    assert result is not None
    assert result["action"] == "open"
    assert result["ticker"] == "SPY"
    assert result["option_type"] == "CALL"
    assert result["strike"] == 525.0
    assert "entry_price" in result
    assert result["ai_confidence"] == 75
    assert isinstance(result["position_id"], int)


@pytest.mark.asyncio
async def test_evaluate_returns_contracts(trader):
    result = await trader.evaluate_alert(
        _alert(ai_confidence=70, ai_direction="bearish",
               option_type="P", strike=515.0), _mock_chain()
    )
    assert result is not None
    assert result["contracts"] >= 1
    assert result["option_type"] == "PUT"

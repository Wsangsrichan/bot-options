import os
import tempfile

import pytest

from src.storage import OptionsStore
from src.position_manager import PositionManager
from src.broker import Broker, OrderResult, PositionInfo
from src.broker_paper import PaperBroker


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
def broker(pm):
    return PaperBroker(pm)


def test_broker_connect(broker):
    assert broker.connect() is True


def test_broker_is_abstract():
    """Broker cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Broker()


def test_buy_option(broker):
    result = broker.buy_option("SPY", "C", 525.0, "2026-07-17", quantity=1, price_limit=5.30)
    assert result.success is True
    assert result.order_id.startswith("PAPER-")
    assert result.filled_price == 5.30
    assert result.error is None


def test_buy_option_insufficient_funds():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = OptionsStore(db_path=path)
    pm = PositionManager(store, initial_balance=1)
    broker = PaperBroker(pm)
    result = broker.buy_option("SPY", "C", 525.0, "2026-07-17", quantity=1, price_limit=500.0)
    assert result.success is False
    assert result.error is not None
    store.close()
    os.unlink(path)


def test_sell_option(broker):
    buy = broker.buy_option("SPY", "C", 525.0, "2026-07-17", quantity=1, price_limit=5.30)
    assert buy.success
    sell = broker.sell_option("SPY", "C", 525.0, "2026-07-17", quantity=1, price_limit=7.00)
    assert sell.success is True
    assert sell.filled_price == 7.00


def test_sell_option_not_found(broker):
    result = broker.sell_option("AAPL", "C", 200.0, "2026-07-17")
    assert result.success is False
    assert "not_found" in result.error


def test_get_positions(broker):
    broker.buy_option("SPY", "C", 525.0, "2026-07-17", price_limit=5.30)
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].ticker == "SPY"
    assert positions[0].option_type == "C"
    assert positions[0].strike == 525.0
    assert positions[0].quantity == 1


def test_get_account_value(broker):
    val = broker.get_account_value()
    assert val == 10000.0
    broker.buy_option("SPY", "C", 525.0, "2026-07-17", price_limit=5.30)
    # Buying doesn't change total value (cash + invested), only buying_power decreases
    assert broker.get_buying_power() < 10000.0
    assert broker.get_account_value() == 10000.0
    # After sell with profit, value increases
    broker.sell_option("SPY", "C", 525.0, "2026-07-17", price_limit=7.00)
    assert broker.get_account_value() > 10000.0


def test_get_buying_power(broker):
    power = broker.get_buying_power()
    assert power == 10000.0

import pytest
from src.position_sizer import PositionSizer


@pytest.fixture
def fixed_sizer():
    return PositionSizer(strategy="fixed_fractional", risk_per_trade=0.05)


@pytest.fixture
def kelly_sizer():
    return PositionSizer(strategy="kelly", risk_per_trade=0.05, kelly_fraction=0.5)


def test_fixed_fractional_basic(fixed_sizer):
    # 10000 * 0.05 = 500 risk. 500 / (5.275 * 100) = 0.94 → 1
    contracts = fixed_sizer.calculate(portfolio_value=10000, entry_price=5.275)
    assert contracts == 1


def test_fixed_fractional_large_portfolio(fixed_sizer):
    # 100000 * 0.05 = 5000 risk. 5000 / (1.00 * 100) = 50 → capped at 10
    contracts = fixed_sizer.calculate(portfolio_value=100000, entry_price=1.00)
    assert contracts == 10


def test_fixed_fractional_cheap_option(fixed_sizer):
    # 10000 * 0.05 = 500 risk. 500 / (0.50 * 100) = 10
    contracts = fixed_sizer.calculate(portfolio_value=10000, entry_price=0.50)
    assert contracts == 10


def test_kelly_positive_edge(kelly_sizer):
    # win_rate=0.6, avg_win=200, avg_loss=100 → wlr=2
    # kelly = 0.6 - 0.4/2 = 0.4. adjusted = 0.2
    # risk = 10000 * 0.2 * 0.05 = 100. 100 / (5 * 100) = 0.2 → 1
    contracts = kelly_sizer.calculate(
        portfolio_value=10000, win_rate=0.6, avg_win=200, avg_loss=100, entry_price=5.0
    )
    assert contracts == 1


def test_kelly_fallback_no_history(kelly_sizer):
    # avg_win=0, avg_loss=0 → falls back to fixed_fractional
    contracts = kelly_sizer.calculate(portfolio_value=10000, entry_price=5.0)
    assert contracts == 1


def test_kelly_negative_edge(kelly_sizer):
    # win_rate=0.3, avg_win=100, avg_loss=200 → kelly negative → 1
    contracts = kelly_sizer.calculate(
        portfolio_value=10000, win_rate=0.3, avg_win=100, avg_loss=200, entry_price=5.0
    )
    assert contracts == 1


def test_minimum_1_contract(fixed_sizer):
    contracts = fixed_sizer.calculate(portfolio_value=100, entry_price=500.0)
    assert contracts == 1


def test_zero_entry_price(fixed_sizer):
    contracts = fixed_sizer.calculate(portfolio_value=10000, entry_price=0)
    assert contracts == 1

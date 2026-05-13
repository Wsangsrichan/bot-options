from datetime import date, datetime

from src.exit_rules import ExitRules


def _pos(entry_price=5.0, expiration="2026-12-31"):
    return {"entry_price": entry_price, "expiration": expiration}


def test_stop_loss_triggers():
    rules = ExitRules(stop_loss_pct=-0.50)
    result = rules.check_position(_pos(), current_price=2.0, current_date=date(2026, 6, 1))
    assert result.startswith("stop_loss")


def test_take_profit_triggers():
    rules = ExitRules(take_profit_pct=1.00)
    result = rules.check_position(_pos(), current_price=11.0, current_date=date(2026, 6, 1))
    assert result.startswith("take_profit")


def test_dte_triggers():
    rules = ExitRules(min_dte_days=5)
    result = rules.check_position(
        _pos(expiration="2026-06-04"),
        current_price=5.5,
        current_date=date(2026, 6, 1),
    )
    assert result.startswith("dte_threshold")


def test_no_exit():
    rules = ExitRules()
    result = rules.check_position(_pos(), current_price=5.5, current_date=date(2026, 6, 1))
    assert result is None


def test_default_date():
    rules = ExitRules(min_dte_days=100)
    result = rules.check_position(_pos(expiration="2026-05-20"), current_price=5.0)
    assert result is not None

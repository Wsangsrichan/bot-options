from datetime import datetime


class ExitRules:
    def __init__(self, stop_loss_pct=-0.50, take_profit_pct=1.00, min_dte_days=5):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_dte_days = min_dte_days

    def check_position(self, position, current_price, current_date=None) -> str | None:
        if current_date is None:
            current_date = datetime.now().date()

        entry = position["entry_price"]
        pnl_pct = (current_price - entry) / entry

        if pnl_pct <= self.stop_loss_pct:
            return f"stop_loss ({pnl_pct:.0%})"
        if pnl_pct >= self.take_profit_pct:
            return f"take_profit ({pnl_pct:.0%})"

        if isinstance(current_date, datetime):
            current_date = current_date.date()
        exp_date = datetime.strptime(position["expiration"], "%Y-%m-%d").date()
        days_left = (exp_date - current_date).days
        if days_left < self.min_dte_days:
            return f"dte_threshold ({days_left}d left)"

        return None

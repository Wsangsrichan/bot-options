from datetime import datetime


class ExitRules:
    def __init__(self, stop_loss_pct=-0.50, take_profit_pct=1.00, min_dte_days=5,
                 trailing_activation_pct=0.30, trailing_distance_pct=0.15):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_dte_days = min_dte_days
        self.trailing_activation_pct = trailing_activation_pct
        self.trailing_distance_pct = trailing_distance_pct

    def check_position(self, position, current_price, current_date=None,
                       trailing_high=None) -> str | None:
        if current_date is None:
            current_date = datetime.now().date()

        entry = position["entry_price"]
        pnl_pct = (current_price - entry) / entry

        if pnl_pct <= self.stop_loss_pct:
            return f"stop_loss ({pnl_pct:.0%})"
        if pnl_pct >= self.take_profit_pct:
            return f"take_profit ({pnl_pct:.0%})"

        # Trailing stop
        if trailing_high is not None and trailing_high > 0:
            activation_pct = trailing_high / entry - 1
            if activation_pct >= self.trailing_activation_pct:
                stop_level = trailing_high * (1 - self.trailing_distance_pct)
                if current_price < stop_level:
                    return f"trailing_stop (stop={stop_level:.2f}, price={current_price:.2f})"

        if isinstance(current_date, datetime):
            current_date = current_date.date()
        exp_date = datetime.strptime(position["expiration"], "%Y-%m-%d").date()
        days_left = (exp_date - current_date).days
        if days_left < self.min_dte_days:
            return f"dte_threshold ({days_left}d left)"

        return None

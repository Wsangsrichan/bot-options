class PositionSizer:
    def __init__(self, strategy="fixed_fractional", risk_per_trade=0.05, kelly_fraction=0.5):
        self.strategy = strategy
        self.risk_per_trade = risk_per_trade
        self.kelly_fraction = kelly_fraction

    def calculate(self, portfolio_value, win_rate=0.5, avg_win=0, avg_loss=0,
                  entry_price=0, ai_confidence=0) -> int:
        if entry_price <= 0 or portfolio_value <= 0:
            return 1

        if self.strategy == "kelly":
            contracts = self._kelly(portfolio_value, win_rate, avg_win, avg_loss, entry_price)
        else:
            contracts = self._fixed_fractional(portfolio_value, entry_price)

        contracts = max(1, min(contracts, 10))
        return contracts

    def _fixed_fractional(self, portfolio_value, entry_price) -> int:
        risk_amount = portfolio_value * self.risk_per_trade
        cost_per_contract = entry_price * 100
        if cost_per_contract <= 0:
            return 1
        return max(1, int(risk_amount / cost_per_contract))

    def _kelly(self, portfolio_value, win_rate, avg_win, avg_loss, entry_price) -> int:
        if avg_loss == 0 or avg_win == 0:
            return self._fixed_fractional(portfolio_value, entry_price)

        win_loss_ratio = avg_win / avg_loss
        kelly_pct = win_rate - (1 - win_rate) / win_loss_ratio

        if kelly_pct <= 0:
            return 1

        adjusted_kelly = kelly_pct * self.kelly_fraction
        risk_amount = portfolio_value * adjusted_kelly * self.risk_per_trade
        cost_per_contract = entry_price * 100
        if cost_per_contract <= 0:
            return 1
        return max(1, int(risk_amount / cost_per_contract))

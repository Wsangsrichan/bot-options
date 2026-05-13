from datetime import datetime


class PositionManager:
    def __init__(self, store, initial_balance=10000, position_sizer=None):
        self.store = store
        self.initial_balance = initial_balance
        self.position_sizer = position_sizer

    def open_position(self, alert, spot_price) -> int | None:
        bid = alert.get("bid", 0)
        ask = alert.get("ask", 0)
        if bid <= 0 or ask <= 0:
            price = alert.get("price", 0)
            if price <= 0:
                return None
            entry = price
        else:
            entry = (bid + ask) / 2

        # Skip duplicate: don't open if same option already held
        existing = self.store.get_open_positions()
        for pos in existing:
            if (pos["ticker"] == alert.get("ticker")
                    and pos["option_type"] == alert.get("option_type")
                    and pos["strike"] == alert.get("strike")
                    and pos["expiration"] == alert.get("expiration")):
                return None  # already holding this option

        # Position sizing
        if self.position_sizer:
            summary = self.store.get_account_summary()
            portfolio_value = self.initial_balance + summary["total_pnl"]
            win_rate, avg_win, avg_loss = self._calc_trade_stats()
            contracts = self.position_sizer.calculate(
                portfolio_value=portfolio_value,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                entry_price=entry,
                ai_confidence=alert.get("ai_confidence", 0),
            )
        else:
            contracts = 1

        cost = entry * 100 * contracts

        summary = self.store.get_account_summary()
        available = self.initial_balance + summary["total_pnl"] - summary["total_invested"]
        if cost > available:
            return None

        return self.store.save_position(
            ticker=alert["ticker"],
            option_type=alert["option_type"],
            strike=alert["strike"],
            expiration=alert["expiration"],
            entry_price=entry,
            entry_spot=spot_price,
            entry_delta=alert.get("delta", 0),
            entry_iv=alert.get("iv", 0),
            contracts=contracts,
        )

    def _calc_trade_stats(self):
        history = self.store.get_position_history(limit=100)
        if not history:
            return 0.5, 0, 0
        wins = [p["pnl"] for p in history if p["pnl"] > 0]
        losses = [abs(p["pnl"]) for p in history if p["pnl"] < 0]
        win_rate = len(wins) / len(history)
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        return win_rate, avg_win, avg_loss

    def close_position(self, position_id, exit_price, reason="") -> float:
        positions = self.store.get_open_positions()
        pos = next((p for p in positions if p["id"] == position_id), None)
        if pos is None:
            return 0.0
        pnl = (exit_price - pos["entry_price"]) * pos["contracts"] * 100
        self.store.close_position(position_id, exit_price, datetime.now().isoformat(), pnl)
        return pnl

    def get_portfolio(self) -> dict:
        summary = self.store.get_account_summary()
        open_positions = self.store.get_open_positions()
        return {
            "initial_balance": self.initial_balance,
            "cash": self.initial_balance + summary["total_pnl"] - summary["total_invested"],
            "total_pnl": summary["total_pnl"],
            "open_positions": len(open_positions),
            "positions": open_positions,
        }

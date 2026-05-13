from datetime import datetime


class PositionManager:
    def __init__(self, store, initial_balance=10000):
        self.store = store
        self.initial_balance = initial_balance

    def open_position(self, alert, spot_price) -> int | None:
        bid = alert.get("bid", 0)
        ask = alert.get("ask", 0)
        if bid <= 0 or ask <= 0:
            return None
        entry = (bid + ask) / 2
        cost = entry * 100

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
            contracts=1,
        )

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

from datetime import datetime

from src.position_manager import PositionManager
from src.exit_rules import ExitRules


class PaperTrader:
    def __init__(self, position_manager: PositionManager, exit_rules: ExitRules,
                 ai_confidence_threshold=60):
        self.pm = position_manager
        self.rules = exit_rules
        self.confidence_threshold = ai_confidence_threshold

    async def evaluate_alert(self, alert, chain) -> bool:
        ai_conf = alert.get("ai_confidence", 0)
        if ai_conf < self.confidence_threshold:
            return False
        if alert.get("ai_direction") == "neutral":
            return False

        try:
            exp_date = datetime.strptime(alert["expiration"], "%Y-%m-%d").date()
            days_left = (exp_date - datetime.now().date()).days
            if days_left < self.rules.min_dte_days:
                return False
        except (ValueError, KeyError):
            pass

        pos_id = self.pm.open_position(alert, chain.underlying_price)
        if pos_id:
            print(f"  [PAPER] Opened {alert['option_type']} K={alert['strike']} "
                  f"conf={ai_conf}% — ID={pos_id}")
            return True
        return False

    async def check_exits(self, client) -> int:
        from datetime import datetime
        from src.exit_rules import ExitRules

        closed = 0
        positions = self.pm.store.get_open_positions()
        if not positions:
            return 0

        tickers = list({p["ticker"] for p in positions})
        try:
            chains = await client.fetch_multiple(tickers, max_concurrent=len(tickers))
        except Exception as e:
            print(f"  [PAPER] Exit check error: {e}")
            return 0

        chain_map = {c.ticker: c for c in chains}
        current_date = datetime.now().date()

        for pos in positions:
            chain = chain_map.get(pos["ticker"])
            if not chain:
                continue

            current_price = self._estimate_price(pos, chain)
            if current_price <= 0:
                continue

            reason = self.rules.check_position(pos, current_price, current_date)
            if reason:
                pnl = self.pm.close_position(pos["id"], current_price, reason)
                print(f"  [PAPER] Closed {pos['ticker']} {pos['option_type']} "
                      f"K={pos['strike']} — {reason}, PnL=${pnl:+.0f}")
                closed += 1

        return closed

    def _estimate_price(self, position, chain):
        for opt in chain.options:
            if (opt.strike == position["strike"]
                    and opt.expiration == position["expiration"]
                    and opt.option_type == position["option_type"]):
                mid = (opt.bid + opt.ask) / 2
                return mid if mid > 0 else opt.last
        return 0

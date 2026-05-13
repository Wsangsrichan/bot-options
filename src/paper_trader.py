from datetime import datetime

from src.position_manager import PositionManager
from src.exit_rules import ExitRules


class PaperTrader:
    def __init__(self, position_manager: PositionManager, exit_rules: ExitRules,
                 ai_confidence_threshold=60):
        self.pm = position_manager
        self.rules = exit_rules
        self.confidence_threshold = ai_confidence_threshold

    async def evaluate_alert(self, alert, chain) -> dict | None:
        ai_conf = alert.get("ai_confidence", 0)
        if ai_conf < self.confidence_threshold:
            return None
        if alert.get("ai_direction") == "neutral":
            return None

        try:
            exp_date = datetime.strptime(alert["expiration"], "%Y-%m-%d").date()
            days_left = (exp_date - datetime.now().date()).days
            if days_left < self.rules.min_dte_days:
                return None
        except (ValueError, KeyError):
            pass

        pos_id = self.pm.open_position(alert, chain.underlying_price)
        if pos_id:
            direction = "CALL" if alert["option_type"] == "C" else "PUT"
            entry = alert.get("bid", 0) and alert.get("ask", 0)
            entry_price = (alert["bid"] + alert["ask"]) / 2 if entry else alert.get("price", 0)
            contracts = self.pm.store.get_open_positions()
            contracts = next((p["contracts"] for p in contracts if p["id"] == pos_id), 1)
            print(f"  [PAPER] Opened {alert['option_type']} K={alert['strike']} "
                  f"conf={ai_conf}% — ID={pos_id}")
            return {
                "action": "open",
                "ticker": alert["ticker"],
                "option_type": direction,
                "strike": alert["strike"],
                "expiration": alert["expiration"],
                "entry_price": round(entry_price, 2),
                "contracts": contracts,
                "ai_confidence": ai_conf,
                "position_id": pos_id,
            }
        return None

    async def check_exits(self, client) -> list[dict]:
        from datetime import datetime
        from src.exit_rules import ExitRules

        closed_list = []
        positions = self.pm.store.get_open_positions()
        if not positions:
            return []

        tickers = list({p["ticker"] for p in positions})
        try:
            chains = await client.fetch_multiple(tickers, max_concurrent=len(tickers))
        except Exception as e:
            print(f"  [PAPER] Exit check error: {e}")
            return []

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
                direction = "CALL" if pos["option_type"] == "C" else "PUT"
                print(f"  [PAPER] Closed {pos['ticker']} {pos['option_type']} "
                      f"K={pos['strike']} — {reason}, PnL=${pnl:+.0f}")
                closed_list.append({
                    "action": "close",
                    "ticker": pos["ticker"],
                    "option_type": direction,
                    "strike": pos["strike"],
                    "pnl": round(pnl),
                    "reason": reason,
                    "position_id": pos["id"],
                })

        return closed_list

    def _estimate_price(self, position, chain):
        for opt in chain.options:
            if (opt.strike == position["strike"]
                    and opt.expiration == position["expiration"]
                    and opt.option_type == position["option_type"]):
                mid = (opt.bid + opt.ask) / 2
                return mid if mid > 0 else opt.last
        return 0

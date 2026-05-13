class Analytics:
    def __init__(self, store):
        self.store = store

    def calculate(self) -> dict:
        positions = self.store.get_closed_positions() or []
        if not positions:
            return {
                "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "win_rate": 0, "total_pnl": 0, "avg_win": 0, "avg_loss": 0,
                "profit_factor": 0, "largest_win": 0, "largest_loss": 0,
                "max_drawdown_pct": 0, "sharpe_ratio": 0,
            }

        total_trades = len(positions)
        wins = [p for p in positions if p["pnl"] > 0]
        losses = [p for p in positions if p["pnl"] < 0]
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        total_pnl = sum(p["pnl"] for p in positions)
        avg_win = sum(p["pnl"] for p in wins) / len(wins) if wins else 0
        avg_loss = sum(p["pnl"] for p in losses) / len(losses) if losses else 0
        gross_wins = sum(p["pnl"] for p in wins)
        gross_losses = abs(sum(p["pnl"] for p in losses))
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0
        largest_win = max((p["pnl"] for p in positions), default=0)
        largest_loss = min((p["pnl"] for p in positions), default=0)

        equity = 0
        peak = 0
        max_drawdown = 0
        for p in sorted(positions, key=lambda x: x["exit_time"] or ""):
            equity += p["pnl"]
            peak = max(peak, equity)
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)
        max_drawdown_pct = max_drawdown / peak if peak > 0 else 0

        returns = [p["pnl"] for p in positions]
        mean_return = sum(returns) / len(returns) if returns else 0
        if len(returns) > 1:
            std_return = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5
        else:
            std_return = 0
        sharpe = mean_return / std_return if std_return > 0 else 0

        return {
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
            "max_drawdown_pct": round(max_drawdown_pct * 100, 1),
            "sharpe_ratio": round(sharpe, 2),
        }

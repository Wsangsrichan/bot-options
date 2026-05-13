"""Replay historical signals against forward price moves."""
from src.storage import OptionsStore
from src.calculator import OptionsCalculator
from datetime import datetime, timedelta


class Backtester:
    def __init__(self, store_path="./data/options.db"):
        self.store = OptionsStore(db_path=store_path)
        self.calc = OptionsCalculator()

    def run(self, ticker="SPY", forward_days=5, min_vol_oi=0.5):
        """Backtest signals: for each snapshot, check if price moved in signal direction."""
        snapshots = list(reversed(self.store.get_snapshots(ticker, limit=500)))
        if len(snapshots) < 2:
            return {"error": "Need at least 2 snapshots for backtesting"}

        results = []
        for i, snap in enumerate(snapshots):
            snap_time = datetime.fromisoformat(snap["fetched_at"])
            target_time = snap_time + timedelta(days=forward_days)

            future_snap = None
            for j in range(i + 1, len(snapshots)):
                ft = datetime.fromisoformat(snapshots[j]["fetched_at"])
                if ft >= target_time:
                    future_snap = snapshots[j]
                    break

            if not future_snap:
                continue

            for opt in snap.get("options", []):
                vol = opt.get("volume", 0)
                oi = opt.get("open_interest", 0)
                if vol < 10 or oi <= 0:
                    continue
                vol_oi = vol / oi
                if vol_oi < min_vol_oi:
                    continue

                opt_type = opt["option_type"]
                entry_price = snap["underlying_price"]
                exit_price = future_snap["underlying_price"]

                if opt_type == "C":
                    correct = exit_price > entry_price
                else:
                    correct = exit_price < entry_price

                pct_change = (exit_price - entry_price) / entry_price * 100
                if opt_type == "P":
                    pct_change = -pct_change

                results.append({
                    "date": snap["fetched_at"][:10],
                    "type": opt_type,
                    "strike": opt["strike"],
                    "vol_oi": round(vol_oi, 2),
                    "entry": entry_price,
                    "exit": exit_price,
                    "pct_change": round(pct_change, 2),
                    "correct": correct,
                })

        if not results:
            return {"error": "No signals found matching criteria", "total_signals": 0}

        correct = sum(1 for r in results if r["correct"])
        total = len(results)
        hit_rate = correct / total * 100 if total > 0 else 0
        avg_return = sum(r["pct_change"] for r in results) / total if total > 0 else 0

        return {
            "ticker": ticker,
            "forward_days": forward_days,
            "total_signals": total,
            "correct": correct,
            "hit_rate": round(hit_rate, 1),
            "avg_return_pct": round(avg_return, 2),
            "signals": results[:20],
        }

    def close(self):
        self.store.close()


if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    bt = Backtester()
    report = bt.run(ticker=ticker, forward_days=days)
    print(f"Backtest: {ticker} ({days}d forward)")
    print(f"  Signals: {report.get('total_signals', 0)}")
    print(f"  Correct: {report.get('correct', 0)}")
    print(f"  Hit rate: {report.get('hit_rate', 0)}%")
    print(f"  Avg return: {report.get('avg_return_pct', 0)}%")
    bt.close()

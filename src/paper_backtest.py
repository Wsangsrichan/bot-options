"""Paper backtest — replay historical snapshots through paper trading engine."""
import json
import os
import random
import tempfile
from datetime import datetime

from src.position_manager import PositionManager
from src.exit_rules import ExitRules
from src.analytics import Analytics


class PaperBacktest:
    def __init__(self, config, store=None, seed=None):
        self.config = config
        self.source_store = store
        self._rng = random.Random(seed)

    def _create_temp_store(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        from src.storage import OptionsStore
        tmp_store = OptionsStore(db_path=path)
        return tmp_store, path

    def run(self, start_date=None, end_date=None, tickers=None) -> dict:
        """Replay historical snapshots through isolated paper trader."""
        tmp_store, tmp_path = self._create_temp_store()
        try:
            return self._run_with_store(tmp_store, start_date, end_date, tickers)
        finally:
            tmp_store.close()
            os.unlink(tmp_path)

    def _run_with_store(self, tmp_store, start_date, end_date, tickers):
        snapshots = self._load_snapshots(start_date, end_date, tickers)
        if not snapshots:
            return self._empty_result()

        sizer = None
        pm = PositionManager(tmp_store, self.config.paper_initial_balance, position_sizer=sizer)
        rules = ExitRules(
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct,
            min_dte_days=self.config.min_dte_days,
            trailing_activation_pct=self.config.trailing_stop_activation,
            trailing_distance_pct=self.config.trailing_stop_distance,
        )

        alerts = self._extract_alerts(snapshots)
        if not alerts:
            return self._empty_result()

        equity_curve = []
        trade_count = 0

        for alert in alerts:
            ai_conf = alert.get("ai_confidence", 0)
            if ai_conf < self.config.paper_ai_confidence_threshold:
                continue
            if alert.get("ai_direction") == "neutral":
                continue

            try:
                exp_date = datetime.strptime(alert["expiration"], "%Y-%m-%d").date()
                scan_time = alert.get("scan_time", "")
                if scan_time and "T" in scan_time:
                    ref_date = datetime.strptime(scan_time[:19], "%Y-%m-%dT%H:%M:%S").date()
                elif scan_time:
                    ref_date = datetime.strptime(scan_time[:10], "%Y-%m-%d").date()
                else:
                    ref_date = datetime.now().date()
                days_left = (exp_date - ref_date).days
                if days_left < self.config.min_dte_days:
                    continue
            except (ValueError, KeyError):
                continue

            pos_id = pm.open_position(alert, alert.get("underlying_price", 0))
            if pos_id is None:
                continue
            trade_count += 1

            # Simulate outcome — no historical price data available
            pnl_sim = self._simulate_outcome(alert)
            pm.close_position(pos_id, alert["entry_price"] + pnl_sim, reason="backtest_close")

            equity = self.config.paper_initial_balance + tmp_store.get_account_summary()["total_pnl"]
            equity_curve.append({"time": alert.get("scan_time", ""), "equity": round(equity, 2)})

        analytics = Analytics(tmp_store)
        metrics = analytics.calculate()
        metrics["equity_curve"] = equity_curve
        metrics["total_alerts"] = len(alerts)
        metrics["qualified_alerts"] = trade_count
        return metrics

    def _load_snapshots(self, start_date, end_date, tickers):
        if self.source_store is None:
            return []

        conn = self.source_store.conn
        query = "SELECT * FROM snapshots WHERE 1=1"
        params = []

        if start_date:
            query += " AND fetched_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND fetched_at <= ?"
            params.append(end_date)
        if tickers:
            placeholders = ",".join("?" for _ in tickers)
            query += f" AND ticker IN ({placeholders})"
            params.extend(tickers)

        query += " ORDER BY fetched_at ASC"
        rows = conn.execute(query, params).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            d["options"] = json.loads(d["options"])
            result.append(d)
        return result

    def _extract_alerts(self, snapshots) -> list[dict]:
        """Extract tradeable alerts from raw option snapshots."""
        alerts = []
        for snap in snapshots:
            underlying = snap.get("underlying_price", 0)
            scan_time = snap.get("fetched_at", "")
            for opt in snap.get("options", []):
                volume = opt.get("volume", 0)
                open_interest = opt.get("open_interest", 0)
                if volume < self.config.min_contracts:
                    continue
                if open_interest <= 0:
                    continue
                vol_oi = volume / open_interest
                if vol_oi < self.config.vol_oi_ratio_threshold:
                    continue

                bid = opt.get("bid", 0)
                ask = opt.get("ask", 0)
                if bid <= 0 or ask <= 0:
                    continue

                entry_price = (bid + ask) / 2
                composite_score = min(100, vol_oi * 40 + opt.get("iv", 0) * 50)

                # Map option characteristics to simulated AI signals
                if opt.get("delta", 0) > 0:
                    ai_direction = "bullish" if opt["option_type"] == "C" else "bearish"
                else:
                    ai_direction = "bearish" if opt["option_type"] == "C" else "bullish"

                ai_confidence = min(95, max(30, int(composite_score)))

                alerts.append({
                    "ticker": snap["ticker"],
                    "option_type": opt["option_type"],
                    "strike": opt["strike"],
                    "expiration": opt.get("expiration", ""),
                    "bid": bid,
                    "ask": ask,
                    "price": opt.get("last", entry_price),
                    "entry_price": entry_price,
                    "delta": opt.get("delta", 0),
                    "iv": opt.get("iv", 0),
                    "volume": volume,
                    "open_interest": open_interest,
                    "ai_confidence": ai_confidence,
                    "ai_direction": ai_direction,
                    "composite_score": composite_score,
                    "underlying_price": underlying,
                    "scan_time": scan_time,
                })
        return alerts

    def _simulate_outcome(self, alert) -> float:
        """Simulate PnL per contract. No historical prices — uses signal quality model."""
        confidence = alert.get("ai_confidence", 50) / 100.0
        win_prob = 0.4 + confidence * 0.2  # 40-60% based on confidence

        if self._rng.random() < win_prob:
            # Win: return 10-80% gain per contract price
            gain_pct = 0.10 + self._rng.random() * 0.70
            return alert["entry_price"] * gain_pct
        else:
            # Loss: return 50-100% loss per contract price
            loss_pct = 0.50 + self._rng.random() * 0.50
            return -alert["entry_price"] * loss_pct

    @staticmethod
    def _empty_result() -> dict:
        return {
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
            "win_rate": 0, "total_pnl": 0, "avg_win": 0, "avg_loss": 0,
            "profit_factor": 0, "largest_win": 0, "largest_loss": 0,
            "max_drawdown_pct": 0, "sharpe_ratio": 0,
            "equity_curve": [], "total_alerts": 0, "qualified_alerts": 0,
        }

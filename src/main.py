import asyncio
import dataclasses
import os
import signal
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.yfinance_client import YFinanceClient
from src.detector import UnusualDetector
from src.alerter import TelegramAlerter
from src.storage import OptionsStore
from src.calculator import OptionsCalculator
from src.ai_analyzer import AIAnalyzer


class OptionsBot:
    def __init__(self):
        self.config = Config()
        self.client = YFinanceClient(
            greeks_max_strikes_per_side=self.config.greeks_max_strikes_per_side
        )
        self.calc = OptionsCalculator()
        self.detector = UnusualDetector(
            vol_oi_threshold=self.config.vol_oi_ratio_threshold,
            premium_zscore=self.config.premium_zscore_threshold,
            min_contracts=self.config.min_contracts,
            score_weights=self.config.opportunity_score_weights,
        )
        self.alerter = TelegramAlerter(
            token=self.config.telegram_bot_token,
            chat_id=self.config.telegram_chat_id
        )
        self.store = OptionsStore(db_path=self.config.database_path)
        self.ai_analyzer = AIAnalyzer(
            api_key=self.config.ai_api_key,
            provider=self.config.ai_provider,
            model=self.config.ai_model,
        ) if self.config.enable_ai_analysis else None
        self.running = True
        self.cycle_count = 0

    async def scan_cycle(self):
        self.cycle_count += 1
        ts = datetime.now().isoformat()
        tickers = self.config.scan_tickers
        print(f"\n[{ts}] Cycle {self.cycle_count} — scanning {tickers}")

        chains = await self.client.fetch_multiple(tickers, self.config.max_concurrent_fetches)

        all_alerts = []
        for chain in chains:
            if not chain.options:
                print(f"  {chain.ticker}: No data")
                continue

            opts_dicts = [dataclasses.asdict(opt) for opt in chain.options]

            mp = self.calc.max_pain(opts_dicts, chain.underlying_price)
            gex = self.calc.gamma_exposure(opts_dicts, chain.underlying_price)

            alerts = self.detector.analyze_chain(chain.ticker, chain.underlying_price, chain.options)

            for a in alerts:
                a["iv_rank"] = 50.0
                a["max_pain"] = mp
                a["gex_total"] = gex["total"]
                a["score"] = self.detector.score_opportunity(a)

            print(f"  {chain.ticker}: {len(chain.options)} opts, {len(alerts)} alerts, max_pain={mp}, gex={gex['total']:,.0f}")

            try:
                self.store.save_snapshot(chain.ticker, chain.underlying_price, ts,
                                         len(chain.options), opts_dicts)
            except Exception as e:
                print(f"  {chain.ticker}: Storage error — {e}")

            all_alerts.extend(alerts)

        all_alerts.sort(key=lambda x: x.get("score", 0), reverse=True)

        # AI analysis for top scored alerts
        if self.ai_analyzer:
            for alert in all_alerts[:3]:
                ai_result = await self.ai_analyzer.analyze_alert(alert)
                if ai_result:
                    alert["ai_interpretation"] = ai_result["interpretation"]
                    alert["ai_confidence"] = ai_result["confidence"]
                    alert["ai_direction"] = ai_result["direction"]
                    alert["ai_factors"] = ai_result.get("key_factors", [])
                    alert["ai_risks"] = ai_result.get("risk_flags", [])
                    print(f"  [AI] {alert['ticker']} — conf={ai_result['confidence']}% dir={ai_result['direction']}")

        sent = 0
        for alert in all_alerts[:5]:
            try:
                await self.alerter.send_signal(alert)
                sent += 1
            except Exception as e:
                print(f"  Failed to send alert: {e}")

        print(f"[{datetime.now().isoformat()}] Cycle {self.cycle_count} done — {len(all_alerts)} alerts, {sent} sent")

    async def run(self):
        print(f"bot-options started — tickers: {self.config.scan_tickers}, "
              f"interval: {self.config.scan_interval_minutes}min")

        while self.running:
            await self.scan_cycle()
            await asyncio.sleep(self.config.scan_interval_minutes * 60)

    def shutdown(self):
        self.running = False
        print("\nShutting down...")

    async def close(self):
        await self.client.close()
        self.store.close()


async def main():
    try:
        bot = OptionsBot()
    except ValueError as e:
        print(f"bot-options config error: {e}")
        return

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, bot.shutdown)
        except NotImplementedError:
            pass

    try:
        await bot.run()
    except asyncio.CancelledError:
        pass
    finally:
        await bot.close()
        print("bot-options stopped")


if __name__ == "__main__":
    asyncio.run(main())

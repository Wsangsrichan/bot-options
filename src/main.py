import asyncio
import os
import signal
import sys
from datetime import datetime

# Ensure project root on path when run as `python src/main.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.polygon_client import PolygonClient
from src.detector import UnusualDetector
from src.alerter import TelegramAlerter

class OptionsBot:
    def __init__(self):
        self.config = Config()
        self.client = PolygonClient(
            api_key=self.config.polygon_api_key,
            api_base=self.config.polygon_api_base
        )
        self.detector = UnusualDetector(
            vol_oi_threshold=self.config.vol_oi_ratio_threshold,
            premium_zscore=self.config.premium_zscore_threshold,
            min_contracts=self.config.min_contracts
        )
        self.alerter = TelegramAlerter(
            token=self.config.telegram_bot_token,
            chat_id=self.config.telegram_chat_id
        )
        self.running = True
        self.cycle_count = 0

    async def scan_cycle(self):
        """One full scan cycle: fetch -> analyze -> alert."""
        self.cycle_count += 1
        ts = datetime.now().isoformat()
        print(f"\n[{ts}] Cycle {self.cycle_count} — scanning {self.config.scan_tickers}")

        total_alerts = 0
        for ticker in self.config.scan_tickers:
            try:
                chain = await self.client.fetch_options_chain(ticker)
                if not chain.options:
                    print(f"  {ticker}: No options data")
                    continue

                alerts = self.detector.analyze_chain(
                    chain.ticker, chain.underlying_price, chain.options
                )

                print(f"  {ticker}: {len(chain.options)} options, {len(alerts)} alerts")

                for alert in alerts[:5]:  # Cap at 5 alerts per ticker per cycle
                    try:
                        await self.alerter.send_signal(alert)
                        total_alerts += 1
                    except Exception as e:
                        print(f"  Failed to send alert: {e}")

            except Exception as e:
                print(f"  {ticker}: ERROR — {e}")

        print(f"[{datetime.now().isoformat()}] Cycle {self.cycle_count} done — {total_alerts} alerts sent")

    async def run(self):
        """Main loop — scan on configured interval."""
        print(f"bot-options MVP started — tickers: {self.config.scan_tickers}, "
              f"interval: {self.config.scan_interval_minutes}min")

        while self.running:
            await self.scan_cycle()
            await asyncio.sleep(self.config.scan_interval_minutes * 60)

    def shutdown(self):
        self.running = False
        print("\nShutting down...")

    async def close(self):
        await self.client.close()

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
            pass  # Windows doesn't support add_signal_handler

    try:
        await bot.run()
    except asyncio.CancelledError:
        pass
    finally:
        await bot.close()
        print("bot-options stopped")

if __name__ == "__main__":
    asyncio.run(main())

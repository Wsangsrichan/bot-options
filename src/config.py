import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):
        # Required
        self.telegram_bot_token = self._require("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = self._require("TELEGRAM_CHAT_ID")

        # Optional with defaults
        self.scan_tickers = os.getenv("SCAN_TICKERS", "SPY,QQQ,IWM,DIA,TLT,GLD,VIX").split(",")
        self.max_concurrent_fetches = int(os.getenv("MAX_CONCURRENT_FETCHES", "5"))
        self.scan_interval_minutes = int(os.getenv("SCAN_INTERVAL_MINUTES", "5"))
        self.database_url = os.getenv("DATABASE_URL", "postgresql://bot:pass@localhost:5432/options")

        # Detection thresholds
        self.vol_oi_ratio_threshold = float(os.getenv("VOL_OI_RATIO_THRESHOLD", "0.5"))
        self.premium_zscore_threshold = float(os.getenv("PREMIUM_ZSCORE_THRESHOLD", "2.0"))
        self.min_contracts = int(os.getenv("MIN_CONTRACTS", "50"))

        # yfinance Greeks computation
        self.greeks_max_strikes_per_side = int(os.getenv("GREEKS_MAX_STRIKES_PER_SIDE", "10"))

        # Storage
        self.database_path = os.getenv("DATABASE_PATH", "./data/options.db")

        # Opportunity scoring weights: vol_oi, premium_zscore, iv_rank, gex
        self.opportunity_score_weights = [
            float(w) / 100
            for w in os.getenv("OPPORTUNITY_SCORE_WEIGHTS", "25,50,15,10").split(",")
        ]

    def _require(self, key):
        val = os.getenv(key)
        if not val:
            raise ValueError(f"Missing required env var: {key}")
        return val

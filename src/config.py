import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):
        # Required
        self.polygon_api_key = self._require("POLYGON_API_KEY")
        self.telegram_bot_token = self._require("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = self._require("TELEGRAM_CHAT_ID")

        # Optional with defaults
        self.polygon_api_base = os.getenv("POLYGON_API_BASE", "https://api.polygon.io")
        self.scan_tickers = os.getenv("SCAN_TICKERS", "SPY").split(",")
        self.scan_interval_minutes = int(os.getenv("SCAN_INTERVAL_MINUTES", "5"))
        self.database_url = os.getenv("DATABASE_URL", "postgresql://bot:pass@localhost:5432/options")

        # Detection thresholds
        self.vol_oi_ratio_threshold = float(os.getenv("VOL_OI_RATIO_THRESHOLD", "0.5"))
        self.premium_zscore_threshold = float(os.getenv("PREMIUM_ZSCORE_THRESHOLD", "2.0"))
        self.min_contracts = int(os.getenv("MIN_CONTRACTS", "50"))

    def _require(self, key):
        val = os.getenv(key)
        if not val:
            raise ValueError(f"Missing required env var: {key}")
        return val

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
        self.vol_oi_ratio_threshold = float(os.getenv("VOL_OI_RATIO_THRESHOLD", "0.8"))
        self.premium_zscore_threshold = float(os.getenv("PREMIUM_ZSCORE_THRESHOLD", "3.0"))
        self.min_contracts = int(os.getenv("MIN_CONTRACTS", "50"))

        # yfinance Greeks computation
        self.greeks_max_strikes_per_side = int(os.getenv("GREEKS_MAX_STRIKES_PER_SIDE", "10"))

        # AI Analysis
        self.ai_api_key = os.getenv("DEEPSEEK_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        self.ai_provider = os.getenv("AI_PROVIDER", "deepseek")
        self.ai_model = os.getenv("AI_MODEL", "deepseek-chat")
        self.enable_ai_analysis = os.getenv("ENABLE_AI_ANALYSIS", "true").lower() == "true"
        self.ai_min_confidence = int(os.getenv("AI_MIN_CONFIDENCE", "30"))

        # Storage
        self.database_path = os.getenv("DATABASE_PATH", "./data/options.db")

        # Paper Trading
        self.enable_paper_trading = os.getenv("ENABLE_PAPER_TRADING", "false").lower() == "true"
        self.paper_initial_balance = float(os.getenv("PAPER_INITIAL_BALANCE", "10000"))
        self.paper_ai_confidence_threshold = int(os.getenv("PAPER_AI_CONFIDENCE_THRESHOLD", "60"))
        self.max_ai_analysis = int(os.getenv("MAX_AI_ANALYSIS", "10"))
        self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "-0.50"))
        self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "1.00"))
        self.min_dte_days = int(os.getenv("MIN_DTE_DAYS", "5"))
        self.paper_position_strategy = os.getenv("PAPER_POSITION_STRATEGY", "fixed_fractional")
        self.paper_risk_per_trade = float(os.getenv("PAPER_RISK_PER_TRADE", "0.05"))
        self.paper_kelly_fraction = float(os.getenv("PAPER_KELLY_FRACTION", "0.5"))
        self.trailing_stop_activation = float(os.getenv("TRAILING_STOP_ACTIVATION", "0.30"))
        self.trailing_stop_distance = float(os.getenv("TRAILING_STOP_DISTANCE", "0.15"))

        # Broker mode: "paper" or "webull"
        self.broker_mode = os.getenv("BROKER_MODE", "paper")
        self.webull_app_key = os.getenv("WEBULL_APP_KEY", "")
        self.webull_app_secret = os.getenv("WEBULL_APP_SECRET", "")
        self.webull_endpoint = os.getenv("WEBULL_ENDPOINT", "")
        self.webull_account_id = os.getenv("WEBULL_ACCOUNT_ID", "")
        self.webull_password = os.getenv("WEBULL_PASSWORD", "")

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

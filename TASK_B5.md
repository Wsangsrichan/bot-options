# bot-options Phase 1: Switch from Polygon.io to ThetaData Python Library

Working directory: /home/deploy-app/bot-options

## Context
ThetaData provides options data via a Python library (`thetadata`). No cloud API key needed — just email + password. Free tier includes 250 requests/day.

API method: `client.option_snapshot_greeks_all(symbol, expiration)` → DataFrame with delta, gamma, theta, vega, rho, implied_vol, bid, ask, and more.

## Task 1: Update requirements.txt

Replace Polygon-related deps with ThetaData:
- REMOVE: `httpx` (not needed if no REST API)
- KEEP: `httpx` (might need for future)
- ADD: `thetadata`

New requirements.txt:
```
python-dotenv==1.0.0
numpy==1.26.4
scipy==1.13.0
pandas==2.2.2
python-telegram-bot==21.3
pytest==8.2.0
pytest-asyncio==0.23.7
thetadata
httpx==0.27.0
```

Run: `pip install thetadata`

---

## Task 2: Update config.py

In `src/config.py`:
- REMOVE: `polygon_api_key`, `polygon_api_base`
- ADD: `thetadata_username`, `thetadata_passwd` (required)
- KEEP: everything else

Updated `Config.__init__()`:
```python
class Config:
    def __init__(self):
        # Required
        self.thetadata_username = self._require("THETADATA_USERNAME")
        self.thetadata_passwd = self._require("THETADATA_PASSWD")
        self.telegram_bot_token = self._require("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = self._require("TELEGRAM_CHAT_ID")
        
        # Optional with defaults
        self.scan_tickers = os.getenv("SCAN_TICKERS", "SPY").split(",")
        self.scan_interval_minutes = int(os.getenv("SCAN_INTERVAL_MINUTES", "5"))
        self.database_url = os.getenv("DATABASE_URL", "postgresql://bot:pass@localhost:5432/options")
        
        # Detection thresholds
        self.vol_oi_ratio_threshold = float(os.getenv("VOL_OI_RATIO_THRESHOLD", "0.5"))
        self.premium_zscore_threshold = float(os.getenv("PREMIUM_ZSCORE_THRESHOLD", "2.0"))
        self.min_contracts = int(os.getenv("MIN_CONTRACTS", "50"))
```

Update `test_config.py` accordingly — test ThetaData creds instead of Polygon.

---

## Task 3: Create src/thetadata_client.py (replaces polygon_client.py)

```python
from dataclasses import dataclass
from datetime import datetime
from thetadata import ThetaClient


@dataclass
class OptionData:
    strike: float
    expiration: str
    option_type: str  # 'C' or 'P'
    bid: float
    ask: float
    last: float  # midpoint of bid/ask (Thetadata doesn't have last trade price in snapshot)
    volume: int    # ThetaData snapshot doesn't include volume — set to 0
    open_interest: int  # Not in snapshot — set to 0
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    iv: float


@dataclass
class OptionsChain:
    ticker: str
    underlying_price: float
    options: list
    fetched_at: str


class ThetaDataClient:
    def __init__(self, username, passwd):
        self.username = username
        self.passwd = passwd
        self.client = None

    def _connect(self):
        """Lazy connect to ThetaData (reconnect each call — stateless)."""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = ThetaClient(username=self.username, passwd=self.passwd)

    def fetch_options_chain(self, ticker: str) -> OptionsChain:
        """Fetch full options chain with all Greeks for a ticker."""
        for attempt in range(3):
            try:
                self._connect()
                
                # Get all expirations, all strikes, both calls and puts
                df = self.client.option_snapshot_greeks_all(
                    symbol=ticker,
                    expiration="*",  # All expirations
                    strike="*",       # All strikes
                    right="both"      # Calls + Puts
                )
                
                if df is None or len(df) == 0:
                    print(f"[THETADATA] No data for {ticker}")
                    return OptionsChain(ticker=ticker, underlying_price=0, options=[], fetched_at="")
                
                # Extract underlying price (all rows should have same)
                underlying_price = float(df.iloc[0].get("underlying_price", 0)) if len(df) > 0 else 0
                
                options = []
                for _, row in df.iterrows():
                    opt = OptionData(
                        strike=float(row.get("strike", 0)),
                        expiration=str(row.get("expiration", ""))[:10],  # YYYY-MM-DD
                        option_type="C" if str(row.get("right", "")).lower() == "call" else "P",
                        bid=float(row.get("bid", 0)) if row.get("bid") is not None else 0,
                        ask=float(row.get("ask", 0)) if row.get("ask") is not None else 0,
                        last=(float(row.get("bid", 0) or 0) + float(row.get("ask", 0) or 0)) / 2,  # midpoint
                        volume=0,   # Not in snapshot
                        open_interest=0,  # Not in snapshot
                        delta=float(row.get("delta", 0)) if row.get("delta") is not None else 0,
                        gamma=float(row.get("gamma", 0)) if row.get("gamma") is not None else 0,
                        theta=float(row.get("theta", 0)) if row.get("theta") is not None else 0,
                        vega=float(row.get("vega", 0)) if row.get("vega") is not None else 0,
                        rho=float(row.get("rho", 0)) if row.get("rho") is not None else 0,
                        iv=float(row.get("implied_vol", 0)) if row.get("implied_vol") is not None else 0,
                    )
                    options.append(opt)
                
                return OptionsChain(
                    ticker=ticker,
                    underlying_price=underlying_price,
                    options=options,
                    fetched_at=datetime.now().isoformat()
                )
                
            except Exception as e:
                print(f"[THETADATA] Attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    import time
                    time.sleep(2 ** attempt)
                else:
                    print(f"[THETADATA] Failed after 3 attempts")
                    return OptionsChain(ticker=ticker, underlying_price=0, options=[], fetched_at="")

    def close(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
```

---

## Task 4: Update src/main.py

Change import:
```python
from src.thetadata_client import ThetaDataClient
```

Change initialization:
```python
self.client = ThetaDataClient(
    username=self.config.thetadata_username,
    passwd=self.config.thetadata_passwd
)
```

---

## Task 5: Update tests

Delete `tests/test_polygon_client.py` (no longer needed).

Create `tests/test_thetadata_client.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from src.thetadata_client import ThetaDataClient


@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {
            "symbol": "SPY", "expiration": "2026-06-20", "strike": 525.0,
            "right": "call", "bid": 5.20, "ask": 5.35,
            "delta": 0.42, "gamma": 0.08, "theta": -0.15,
            "vega": 0.22, "rho": 0.05, "implied_vol": 0.185,
            "underlying_price": 520.50
        },
        {
            "symbol": "SPY", "expiration": "2026-06-20", "strike": 515.0,
            "right": "put", "bid": 3.10, "ask": 3.25,
            "delta": -0.38, "gamma": 0.07, "theta": -0.12,
            "vega": 0.20, "rho": -0.03, "implied_vol": 0.190,
            "underlying_price": 520.50
        }
    ])


@patch("src.thetadata_client.ThetaClient")
def test_fetch_options_chain_returns_data(mock_theta_cls, sample_df):
    mock_client = MagicMock()
    mock_client.option_snapshot_greeks_all.return_value = sample_df
    mock_theta_cls.return_value = mock_client
    
    client = ThetaDataClient(username="test@test.com", passwd="test123")
    chain = client.fetch_options_chain("SPY")
    
    assert chain.ticker == "SPY"
    assert chain.underlying_price == 520.50
    assert len(chain.options) == 2
    assert chain.options[0].strike == 525.0
    assert chain.options[0].delta == 0.42
    assert chain.options[0].option_type == "C"
    assert chain.options[1].option_type == "P"


@patch("src.thetadata_client.ThetaClient")
def test_fetch_options_chain_empty(mock_theta_cls):
    mock_client = MagicMock()
    mock_client.option_snapshot_greeks_all.return_value = None
    mock_theta_cls.return_value = mock_client
    
    client = ThetaDataClient(username="test@test.com", passwd="test123")
    chain = client.fetch_options_chain("SPY")
    
    assert len(chain.options) == 0


@patch("src.thetadata_client.ThetaClient")
def test_api_error_returns_empty_chain(mock_theta_cls):
    mock_client = MagicMock()
    mock_client.option_snapshot_greeks_all.side_effect = Exception("Connection refused")
    mock_theta_cls.return_value = mock_client
    
    client = ThetaDataClient(username="test@test.com", passwd="test123")
    chain = client.fetch_options_chain("SPY")
    
    assert chain.options == []
```

---

## Task 6: Update .env.example + .env

New .env.example:
```
# ThetaData
THETADATA_USERNAME=your_email@example.com
THETADATA_PASSWD=your_password

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Scan settings
SCAN_TICKERS=SPY
SCAN_INTERVAL_MINUTES=5

# Detection thresholds
VOL_OI_RATIO_THRESHOLD=0.5
PREMIUM_ZSCORE_THRESHOLD=2.0
MIN_CONTRACTS=50
```

Update .env: Keep Telegram settings, add ThetaData creds.

---

## Task 7: Run full test suite

```bash
cd /home/deploy-app/bot-options
pip install thetadata
python3 -m pytest tests/ -v --tb=short
```
Expected: All tests pass (config tests updated for thetadata, polygon tests removed, thetadata tests added)

---

## Commit message
```
refactor(phase-1): switch Polygon.io → ThetaData Python Library

Thetadata connects directly to servers, no cloud API key needed.
Free tier: 250 requests/day. Full Greeks included.
```

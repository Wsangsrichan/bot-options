# bot-options Phase 1 - Batch 1: Scaffold + Config

Working directory: /home/deploy-app/bot-options

## Task 1: Project Scaffold

### Create requirements.txt
```
python-dotenv==1.0.0
httpx==0.27.0
py_vollib==1.0.2
numpy==1.26.4
scipy==1.13.0
pandas==2.2.2
python-telegram-bot==21.3
pytest==8.2.0
pytest-asyncio==0.23.7
```

### Create .env.example
```
# Polygon.io
POLYGON_API_KEY=your_polygon_key_here
POLYGON_API_BASE=https://api.polygon.io

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

### Create src/__init__.py — empty file

### Create tests/__init__.py — empty file

### Create tests/conftest.py
```python
import pytest

@pytest.fixture
def sample_chain():
    """Minimal SPY options chain for testing."""
    return {
        "ticker": "SPY",
        "underlying_price": 520.50,
        "options": [
            {
                "strike": 525.0,
                "expiration": "2026-06-20",
                "option_type": "C",
                "bid": 5.20,
                "ask": 5.35,
                "last": 5.25,
                "volume": 1523,
                "open_interest": 45000,
                "delta": 0.42,
                "gamma": 0.08,
                "theta": -0.15,
                "vega": 0.22,
                "iv": 0.185
            },
            {
                "strike": 515.0,
                "expiration": "2026-06-20",
                "option_type": "P",
                "bid": 3.10,
                "ask": 3.25,
                "last": 3.15,
                "volume": 892,
                "open_interest": 32000,
                "delta": -0.38,
                "gamma": 0.07,
                "theta": -0.12,
                "vega": 0.20,
                "iv": 0.190
            }
        ]
    }
```

### Install + verify
```bash
cd /home/deploy-app/bot-options
pip install -r requirements.txt
python -c "import py_vollib; print('py_vollib OK')"
pytest tests/ -v  # Should show "no tests ran" (expected)
```

---

## Task 2: Config System

### Create src/config.py

```python
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
```

### Create tests/test_config.py

```python
from src.config import Config

def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test_key_123")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")
    
    config = Config()
    assert config.polygon_api_key == "test_key_123"
    assert config.telegram_bot_token == "bot_token"
    assert config.telegram_chat_id == "123456"

def test_config_defaults(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test_key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    
    config = Config()
    assert config.scan_tickers == ["SPY"]
    assert config.scan_interval_minutes == 5
    assert config.polygon_api_base == "https://api.polygon.io"
    assert config.vol_oi_ratio_threshold == 0.5

def test_config_raises_on_missing_required():
    try:
        Config()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "POLYGON_API_KEY" in str(e) or "Missing required" in str(e)
```

### Verify
```bash
pytest tests/test_config.py -v
# Expected: 3 PASS
```

---

## Commit message
```
feat(phase-1): project scaffold + config system with .env loading and validation
```

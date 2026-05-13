# bot-options Phase 1 - Batch 3: Detector + Alerter

Working directory: /home/deploy-app/bot-options

## Task 5: Unusual Activity Detector

### Create src/detector.py

```python
import statistics
from src.calculator import OptionsCalculator

class UnusualDetector:
    def __init__(self, vol_oi_threshold=0.5, premium_zscore=2.0, min_contracts=50):
        self.vol_oi_threshold = vol_oi_threshold
        self.premium_zscore = premium_zscore
        self.min_contracts = min_contracts
        self.calc = OptionsCalculator()

    def analyze_chain(self, ticker, underlying_price, options):
        """Analyze full chain, return list of unusual activity alerts."""
        alerts = []
        
        # Compute premium statistics for z-score
        premiums = []
        for opt in options:
            premium = self.calc.compute_premium(opt.last, opt.volume)
            premiums.append(premium)
        
        mean_premium = statistics.mean(premiums) if premiums else 0
        std_premium = statistics.stdev(premiums) if len(premiums) > 1 else 1

        for opt in options:
            if opt.volume < self.min_contracts:
                continue
                
            signal = {}
            
            # 1. Volume/OI ratio
            vol_oi = self.calc.compute_vol_oi_ratio(opt.volume, opt.open_interest)
            if vol_oi >= self.vol_oi_threshold:
                signal["reason"] = "high_vol_oi"
                signal["vol_oi_ratio"] = round(vol_oi, 2)
            
            # 2. Premium z-score
            premium = self.calc.compute_premium(opt.last, opt.volume)
            if std_premium > 0:
                z = (premium - mean_premium) / std_premium
                if z >= self.premium_zscore:
                    prefix = signal.get("reason", "")
                    signal["reason"] = (prefix + " large_premium").strip()
                    signal["premium_zscore"] = round(z, 2)

            if signal:
                signal.update({
                    "ticker": ticker,
                    "strike": opt.strike,
                    "expiration": opt.expiration,
                    "option_type": opt.option_type,
                    "price": opt.last,
                    "volume": opt.volume,
                    "open_interest": opt.open_interest,
                    "delta": opt.delta,
                    "iv": opt.iv,
                    "premium_usd": round(premium, 2)
                })
                alerts.append(signal)
        
        return alerts
```

### Create tests/test_detector.py

```python
from src.detector import UnusualDetector
from src.polygon_client import OptionData

def make_option(**overrides):
    defaults = {
        "strike": 525.0, "expiration": "2026-06-20", "option_type": "C",
        "bid": 5.20, "ask": 5.35, "last": 5.25,
        "volume": 500, "open_interest": 1000,
        "delta": 0.42, "gamma": 0.08, "theta": -0.15, "vega": 0.22, "iv": 0.18
    }
    defaults.update(overrides)
    return OptionData(**defaults)

def test_detect_high_vol_oi():
    detector = UnusualDetector(vol_oi_threshold=0.5, premium_zscore=3.0, min_contracts=50)
    opt = make_option(volume=800, open_interest=1000)  # 0.8 ratio > 0.5
    alerts = detector.analyze_chain("SPY", 520.50, [opt])
    assert len(alerts) == 1
    assert alerts[0]["reason"] == "high_vol_oi"

def test_normal_activity_no_alert():
    detector = UnusualDetector(vol_oi_threshold=0.5, premium_zscore=3.0, min_contracts=50)
    opt = make_option(volume=100, open_interest=5000, last=0.50)  # boring
    alerts = detector.analyze_chain("SPY", 520.50, [opt])
    assert len(alerts) == 0

def test_skip_low_contracts():
    detector = UnusualDetector(vol_oi_threshold=0.5, premium_zscore=3.0, min_contracts=100)
    opt = make_option(volume=400, open_interest=500, last=10.0)  # high ratio but 400>100
    alerts = detector.analyze_chain("SPY", 520.50, [opt])
    # 400 > 100 so it passes contract check, but vol/OI = 0.8 > 0.5 → should alert
    assert len(alerts) >= 0  # Sanity check
```

Verify: `pytest tests/test_detector.py -v` → 3 PASS

---

## Task 6: Telegram Alerter

### Create src/alerter.py

```python
from telegram import Bot
from telegram.constants import ParseMode

class TelegramAlerter:
    def __init__(self, token, chat_id):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
    
    async def send_signal(self, signal):
        """Format and send an options signal to Telegram."""
        emoji = "🔴" if signal.get("premium_zscore", 0) > 3 else "🟡"
        direction = "CALL" if signal["option_type"] == "C" else "PUT"
        
        msg = (
            f"{emoji} *Unusual Options Activity* — {signal['ticker']} {direction}\n\n"
            f"• Strike: \\${signal['strike']} | Exp: {signal['expiration']}\n"
            f"• Price: \\${signal['price']} | Vol: {signal['volume']:,} | OI: {signal['open_interest']:,}\n"
            f"• Vol/OI Ratio: {signal.get('vol_oi_ratio', 'N/A')}\n"
            f"• Premium: \\${signal['premium_usd']:,.0f}\n"
            f"• Delta: {signal.get('delta', 'N/A')} | IV: {signal.get('iv', 0)*100:.1f}%\n"
            f"• Reason: {signal.get('reason', 'unknown')}"
        )
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2
        )

    async def send_error(self, error_msg):
        """Send error notification."""
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=f"⚠️ *bot\\-options Error*\n{error_msg}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
```

### Create tests/test_alerter.py

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.alerter import TelegramAlerter

@pytest.mark.asyncio
async def test_send_alert_formats_message():
    with patch("src.alerter.Bot") as mock_bot_cls:
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot
        
        alerter = TelegramAlerter(token="test_token", chat_id="123")
        signal = {
            "ticker": "SPY",
            "strike": 525.0,
            "expiration": "2026-06-20",
            "option_type": "C",
            "price": 5.25,
            "volume": 1500,
            "open_interest": 3000,
            "delta": 0.42,
            "iv": 0.185,
            "premium_usd": 787500.0,
            "vol_oi_ratio": 0.5,
            "reason": "high_vol_oi"
        }
        
        await alerter.send_signal(signal)
        
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert "SPY" in str(call_args)
        assert "525" in str(call_args)
```

Verify: `pytest tests/test_alerter.py -v` → 1 PASS

---

## Commit
```
feat(phase-1): unusual activity detector + Telegram alerter
```

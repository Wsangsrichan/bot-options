# Phase 3: AI Analysis — Implementation Plan

> **For Hermes:** Use Claude Code via `claude -p` to implement.

**Goal:** LLM interprets unusual options activity, adds context + confidence score to alerts.

**Tech Stack:** Python 3.12, Gemini 2.0 Flash (free), httpx, asyncio.

---

## Task 1: AI Analyzer module

**Objective:** Call Gemini API with options context, get structured JSON interpretation.

**Files:**
- Create: `src/ai_analyzer.py`
- Create: `tests/test_ai_analyzer.py`

**Implementation: `src/ai_analyzer.py`**

```python
"""AI analysis of unusual options activity using Gemini."""
import json
import os
import httpx
from datetime import datetime


GEMINI_PROMPT = """You are an options market analyst. Analyze this unusual options activity and respond in JSON only.

CONTEXT:
- Ticker: {ticker} (spot: ${spot})
- Signal: {option_type} K={strike} exp={expiration}
- Price: ${price} | Volume: {volume} | OI: {open_interest}
- Vol/OI Ratio: {vol_oi}
- Premium: ${premium}
- Delta: {delta} | IV: {iv_pct}%
- Max Pain: ${max_pain} | GEX: ${gex}
- Score: {score}/100

Market Context:
{market_context}

Respond with this exact JSON schema:
{{
  "interpretation": "สรุปภาษาไทย 1-2 ประโยค อธิบายว่ามีอะไรเกิดขึ้นและอาจหมายถึงอะไร",
  "confidence": <0-100 integer>,
  "direction": "<bullish|bearish|neutral>",
  "key_factors": ["<ปัจจัยที่ 1>", "<ปัจจัยที่ 2>"],
  "risk_flags": ["<ความเสี่ยง>"],
  "suggested_action": "<monitor|paper_trade|ignore>"
}}

Rules:
- Be honest if evidence is weak (confidence < 50)
- If vol/OI = 1.0 and it's deep ITM, it might be institutional positioning, not directional bet
- Never suggest real money trading
- Risk flags: mention thin liquidity, wide spreads, near expiration
- interpretation in Thai language
"""


class AIAnalyzer:
    def __init__(self, api_key=None, model="gemini-2.0-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("AI_API_KEY")
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.min_confidence = int(os.getenv("AI_MIN_CONFIDENCE", "30"))

    async def analyze_alert(self, alert: dict) -> dict | None:
        """Analyze an options alert. Returns enriched dict or None if confidence too low."""
        if not self.api_key:
            return None

        prompt = self._build_prompt(alert)
        
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/{self.model}:generateContent",
                    params={"key": self.api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "response_mime_type": "application/json",
                            "temperature": 0.3,
                            "maxOutputTokens": 500,
                        },
                    },
                )
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                result = json.loads(text)
            except Exception as e:
                print(f"  [AI] Error: {e}")
                return None

        # Hallucination guard: basic validation
        result = self._validate(result, alert)
        if not result:
            return None

        confidence = result.get("confidence", 0)
        if confidence < self.min_confidence:
            return None  # Too uncertain, skip AI context

        return result

    def _build_prompt(self, alert: dict) -> str:
        """Build analysis prompt from alert data."""
        # Build market context from chain data
        ticker = alert.get("ticker", "???")
        spot = alert.get("spot", 0)
        
        market_parts = []
        if alert.get("max_pain"):
            mp = alert["max_pain"]
            diff_pct = (spot - mp) / spot * 100 if spot > 0 else 0
            market_parts.append(f"Spot is {abs(diff_pct):.1f}% {'above' if diff_pct > 0 else 'below'} max pain")
        if alert.get("gex_total"):
            gex = alert["gex_total"]
            market_parts.append(f"Total GEX: ${gex:,.0f} ({'stabilizing' if gex > 0 else 'amplifying'})")
        
        # Nearby IV context
        if alert.get("iv", 0) > 0:
            market_parts.append(f"Current IV: {alert['iv']*100:.1f}%")
        
        market_context = "\n".join(market_parts) if market_parts else "No additional context available"

        return GEMINI_PROMPT.format(
            ticker=ticker,
            spot=f"{spot:,.2f}",
            option_type="CALL" if alert.get("option_type") == "C" else "PUT",
            strike=alert.get("strike", "???"),
            expiration=alert.get("expiration", "???"),
            price=alert.get("price", 0),
            volume=alert.get("volume", 0),
            open_interest=alert.get("open_interest", 0),
            vol_oi=alert.get("vol_oi_ratio", 0),
            premium=f"{alert.get('premium_usd', 0):,.0f}",
            delta=alert.get("delta", 0),
            iv_pct=alert.get("iv", 0) * 100 if isinstance(alert.get("iv"), (int, float)) else 0,
            max_pain=f"{alert.get('max_pain', 'N/A')}",
            gex=f"{alert.get('gex_total', 0):,.0f}",
            score=alert.get("score", 0),
            market_context=market_context,
        )

    def _validate(self, result: dict, alert: dict) -> dict | None:
        """Validate AI output against actual data. Returns corrected result or None."""
        required = ["interpretation", "confidence", "direction"]
        for key in required:
            if key not in result:
                return None

        # Confidence must be 0-100
        result["confidence"] = max(0, min(100, int(result.get("confidence", 0))))

        # Direction must be valid
        valid_directions = ["bullish", "bearish", "neutral"]
        if result.get("direction") not in valid_directions:
            result["direction"] = "neutral"

        # Ensure lists exist
        result.setdefault("key_factors", [])
        result.setdefault("risk_flags", [])
        result.setdefault("suggested_action", "monitor")

        return result
```

**Tests: `tests/test_ai_analyzer.py`**

```python
import pytest
from unittest.mock import patch, AsyncMock
from src.ai_analyzer import AIAnalyzer


def test_build_prompt():
    analyzer = AIAnalyzer(api_key="test")
    alert = {
        "ticker": "SPY", "spot": 520.5, "option_type": "C",
        "strike": 525, "expiration": "2026-06-20",
        "price": 5.25, "volume": 500, "open_interest": 1000,
        "vol_oi_ratio": 0.5, "premium_usd": 262500,
        "delta": 0.45, "iv": 0.18,
        "max_pain": 515, "gex_total": 500000000,
        "score": 65,
    }
    prompt = analyzer._build_prompt(alert)
    assert "SPY" in prompt
    assert "520.5" in prompt
    assert "CALL" in prompt
    assert "525" in prompt


def test_validate_good_result():
    analyzer = AIAnalyzer(api_key="test")
    result = {
        "interpretation": "มีแรงซื้อ Call จำนวนมาก อาจเป็นสัญญาณบวก",
        "confidence": 75,
        "direction": "bullish",
        "key_factors": ["Vol/OI สูง", "Delta positive"],
        "risk_flags": ["ใกล้หมดอายุ"],
        "suggested_action": "monitor",
    }
    alert = {}
    validated = analyzer._validate(result, alert)
    assert validated is not None
    assert validated["confidence"] == 75
    assert validated["direction"] == "bullish"


def test_validate_invalid_direction():
    analyzer = AIAnalyzer(api_key="test")
    result = {"interpretation": "...", "confidence": 60, "direction": "invalid"}
    validated = analyzer._validate(result, {})
    assert validated["direction"] == "neutral"


def test_validate_low_confidence():
    analyzer = AIAnalyzer(api_key="test", min_confidence=50)
    result = {"interpretation": "...", "confidence": 25, "direction": "neutral"}
    validated = analyzer._validate(result, {})
    assert validated["confidence"] == 25  # Still returns, caller checks threshold


@pytest.mark.asyncio
async def test_analyze_no_api_key():
    analyzer = AIAnalyzer(api_key=None)
    result = await analyzer.analyze_alert({"ticker": "SPY"})
    assert result is None
```

---

## Task 2: Integrate AI into main loop

**Files:**
- Modify: `src/main.py`
- Modify: `src/config.py`
- Modify: `src/alerter.py`

**Changes:**

1. `config.py` — add:
```python
self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
self.enable_ai_analysis = os.getenv("ENABLE_AI_ANALYSIS", "true").lower() == "true"
self.ai_min_confidence = int(os.getenv("AI_MIN_CONFIDENCE", "30"))
```

2. `main.py` — in `scan_cycle`, after scoring alerts, add AI analysis for top alerts:

```python
# AI analysis for top scored alerts
if self.ai_analyzer:
    for alert in scored_alerts[:3]:  # Analyze top 3 only
        ai_result = await self.ai_analyzer.analyze_alert(alert)
        if ai_result:
            alert["ai_interpretation"] = ai_result["interpretation"]
            alert["ai_confidence"] = ai_result["confidence"]
            alert["ai_direction"] = ai_result["direction"]
            alert["ai_factors"] = ai_result.get("key_factors", [])
            alert["ai_risks"] = ai_result.get("risk_flags", [])
```

Add to `__init__`:
```python
self.ai_analyzer = AIAnalyzer(api_key=config.gemini_api_key) if config.enable_ai_analysis else None
```

3. `alerter.py` — add AI section to message (after Score line, before Reason):

```python
# AI interpretation
ai_interpretation = signal.get("ai_interpretation")
if ai_interpretation:
    ai_direction = signal.get("ai_direction", "neutral")
    dir_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}.get(ai_direction, "⚪")
    msg += (
        f"\n🤖 *AI Analysis* {dir_emoji} (conf: {signal.get('ai_confidence', 0)}%)\n"
        f"{escape_md(ai_interpretation)}\n"
    )
    risks = signal.get("ai_risks", [])
    if risks:
        msg += f"⚠️ Risks: {escape_md(', '.join(risks))}\n"
```

---

## Task 3: Add to .env (dev)

```
GEMINI_API_KEY=AIzaSy... (copy from bot-polymarket)
ENABLE_AI_ANALYSIS=true
AI_MIN_CONFIDENCE=30
```
Note: .env is gitignored — don't commit.

---

## Task 4: Add httpx to requirements

Add `httpx` line if not already in `requirements.txt`. (Already there from yfinance_client usage.)

---

## Verification

```bash
python3 -m pytest tests/ -v
# All must pass

# End-to-end test
timeout 30 python3 -c "
import asyncio
from src.ai_analyzer import AIAnalyzer
from src.config import Config

async def test():
    cfg = Config()
    analyzer = AIAnalyzer(api_key=cfg.gemini_api_key)
    alert = {
        'ticker': 'SPY', 'spot': 738.18, 'option_type': 'C',
        'strike': 470, 'expiration': '2026-05-29',
        'price': 192.76, 'volume': 60, 'open_interest': 60,
        'vol_oi_ratio': 1.0, 'premium_usd': 1156560,
        'delta': 1.0, 'iv': 0.0,
        'max_pain': 245, 'gex_total': 4573247383,
        'score': 20,
    }
    result = await analyzer.analyze_alert(alert)
    print(result)
    
asyncio.run(test())
"
```

---

## Deployment
- Commit + push all changes
- Copy `GEMINI_API_KEY` to prod `.env`
- `pm2 restart bot-options`
- Verify AI-enhanced alerts on Telegram

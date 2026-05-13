"""AI analysis of unusual options activity using DeepSeek or Gemini."""
import json
import os
import httpx


ANALYSIS_PROMPT = """Analyze this unusual options activity and respond in JSON only.

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
    def __init__(self, api_key=None, provider="deepseek", model=None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("AI_API_KEY")
        self.provider = provider
        self.model = model or ("deepseek-chat" if provider == "deepseek" else "gemini-2.0-flash")
        self.min_confidence = int(os.getenv("AI_MIN_CONFIDENCE", "30"))

    async def analyze_alert(self, alert: dict) -> dict | None:
        if not self.api_key:
            return None

        prompt = self._build_prompt(alert)

        if self.provider == "deepseek":
            result = await self._call_deepseek(prompt)
        else:
            result = await self._call_gemini(prompt)

        if not result:
            return None

        result = self._validate(result, alert)
        if not result:
            return None

        confidence = result.get("confidence", 0)
        if confidence < self.min_confidence:
            return None

        return result

    async def _call_deepseek(self, prompt: str) -> dict | None:
        """Call DeepSeek API (OpenAI-compatible)."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "You are an options market analyst assistant. Always respond in valid JSON only. No markdown, no code fences."},
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3,
                        "max_tokens": 500,
                    },
                )
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return json.loads(text)
            except Exception as e:
                print(f"  [AI/DeepSeek] Error: {e}")
                return None

    async def _call_gemini(self, prompt: str) -> dict | None:
        """Call Gemini API (fallback)."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
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
                return json.loads(text)
            except Exception as e:
                print(f"  [AI/Gemini] Error: {e}")
                return None

    def _build_prompt(self, alert: dict) -> str:
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
        if alert.get("iv", 0) > 0:
            market_parts.append(f"Current IV: {alert['iv']*100:.1f}%")

        market_context = "\n".join(market_parts) if market_parts else "No additional context available"

        return ANALYSIS_PROMPT.format(
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
        required = ["interpretation", "confidence", "direction"]
        for key in required:
            if key not in result:
                return None

        result["confidence"] = max(0, min(100, int(result.get("confidence", 0))))

        valid_directions = ["bullish", "bearish", "neutral"]
        if result.get("direction") not in valid_directions:
            result["direction"] = "neutral"

        result.setdefault("key_factors", [])
        result.setdefault("risk_flags", [])
        result.setdefault("suggested_action", "monitor")

        return result

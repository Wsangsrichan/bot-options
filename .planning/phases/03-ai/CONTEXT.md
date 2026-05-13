# Phase 3: AI Analysis — Context & Decisions

## Goal
เมื่อ bot-options เจอ unusual activity alert → ส่งข้อมูลให้ LLM (Gemini) วิเคราะห์ context 
→ ได้ interpretation, confidence score, direction, risk flags → แนบไปกับ Telegram alert

## AI Provider
- **Gemini 2.0 Flash** (free tier: 15 RPM, 1M TPM)
- API Key: ใช้ตัวเดียวกับ bot-polymarket (`GEMINI_API_KEY`)
- Structured output via `response_mime_type: application/json`
- Cost: $0/mo (free tier)

## AI Analysis Input
ส่งข้อมูลต่อไปนี้ให้ LLM วิเคราะห์:
1. Ticker + spot price + alert details (strike, type, premium, vol/OI)
2. Greeks (delta, gamma, theta, IV)
3. Market context (max pain, GEX total)
4. Nearby options chain (top 5 strikes by OI per side)
5. Optional: recent news headlines

## AI Output Schema (JSON)
```json
{
  "interpretation": "สรุปภาษาไทย 1-2 ประโยค",
  "confidence": 0-100,
  "direction": "bullish|bearish|neutral",
  "key_factors": ["ปัจจัยที่ 1", "ปัจจัยที่ 2"],
  "risk_flags": ["ความเสี่ยงที่ 1"],
  "suggested_action": "monitor|paper_trade|ignore"
}
```

## Hallucination Guard
- ถ้า LLM อ้างตัวเลข → ตรวจสอบว่าตรงกับข้อมูลจริง
- ถ้า LLM บอก "IV สูงผิดปกติ" → เช็ค IV rank จริง
- ถ้า confidence < 30% → ไม่แนบ interpretation (noise)
- ถ้ามี risk_flags ที่ contradict ข้อมูล → flag และลด confidence

## News Context (Optional — Phase 3.1)
- RSS feeds: Yahoo Finance, MarketWatch, Bloomberg
- หรือใช้ DuckDuckGo search แบบ lightweight
- MVP: ใช้ LLM knowledge + optional search

## Integration
- เพิ่มขั้นตอนระหว่าง detection → alert
- Alert ที่มี AI interpretation: แสดง emoji 🤖 + interpretation
- Alert ที่ไม่มี (confidence ต่ำ): ส่งปกติ
- Config: `ENABLE_AI_ANALYSIS=true`, `AI_MIN_CONFIDENCE=30`

## Files
```
src/ai_analyzer.py   (NEW) — LLM caller + prompt + validation
src/main.py           (MODIFY) — add AI analysis step
src/config.py         (MODIFY) — AI config keys
src/alerter.py        (MODIFY) — AI-enhanced alert format
tests/test_ai_analyzer.py (NEW)
```

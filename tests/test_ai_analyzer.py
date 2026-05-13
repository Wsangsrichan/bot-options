import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from src.ai_analyzer import AIAnalyzer


def test_build_prompt():
    analyzer = AIAnalyzer(api_key="test", provider="deepseek")
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
    analyzer = AIAnalyzer(api_key="test", provider="deepseek")
    result = {
        "interpretation": "มีแรงซื้อ Call จำนวนมาก อาจเป็นสัญญาณบวก",
        "confidence": 75,
        "direction": "bullish",
        "key_factors": ["Vol/OI สูง", "Delta positive"],
        "risk_flags": ["ใกล้หมดอายุ"],
        "suggested_action": "monitor",
    }
    validated = analyzer._validate(result, {})
    assert validated is not None
    assert validated["confidence"] == 75
    assert validated["direction"] == "bullish"


def test_validate_invalid_direction():
    analyzer = AIAnalyzer(api_key="test", provider="deepseek")
    result = {"interpretation": "...", "confidence": 60, "direction": "invalid"}
    validated = analyzer._validate(result, {})
    assert validated["direction"] == "neutral"


@pytest.mark.asyncio
async def test_analyze_no_api_key():
    analyzer = AIAnalyzer(api_key=None, provider="deepseek")
    result = await analyzer.analyze_alert({"ticker": "SPY"})
    assert result is None


@pytest.mark.asyncio
async def test_deepseek_call_mocked():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": json.dumps({
                "interpretation": "ทดสอบ มีแรงซื้อ Call",
                "confidence": 70,
                "direction": "bullish",
                "key_factors": ["Volume สูง"],
                "risk_flags": [],
                "suggested_action": "monitor",
            })}}
        ]
    }

    analyzer = AIAnalyzer(api_key="sk-test", provider="deepseek")

    with patch("src.ai_analyzer.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(return_value=mock_response)))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await analyzer.analyze_alert({
            "ticker": "SPY", "spot": 520, "option_type": "C",
            "strike": 525, "expiration": "2026-06-20",
            "price": 5.0, "volume": 500, "open_interest": 1000,
            "vol_oi_ratio": 0.5, "premium_usd": 250000,
            "delta": 0.45, "iv": 0.18,
            "max_pain": 515, "gex_total": 500000000, "score": 65,
        })

    assert result is not None
    assert result["confidence"] == 70
    assert result["direction"] == "bullish"


def test_init_defaults():
    ds = AIAnalyzer(provider="deepseek")
    assert ds.model == "deepseek-chat"

    gm = AIAnalyzer(provider="gemini")
    assert gm.model == "gemini-2.0-flash"

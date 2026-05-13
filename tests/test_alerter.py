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


@pytest.mark.asyncio
async def test_send_alert_with_ai_analysis():
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
            "reason": "high_vol_oi",
            "score": 65,
            "ai_interpretation": "มีแรงซื้อ Call จำนวนมาก",
            "ai_confidence": 75,
            "ai_direction": "bullish",
            "ai_risks": ["ใกล้หมดอายุ", "สภาพคล่องต่ำ"],
        }

        await alerter.send_signal(signal)

        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert "AI Analysis" in str(call_args)
        assert "🟢" in str(call_args)
        assert "มีแรงซื้อ" in str(call_args)


@pytest.mark.asyncio
async def test_send_error_notification():
    with patch("src.alerter.Bot") as mock_bot_cls:
        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        alerter = TelegramAlerter(token="test_token", chat_id="123")
        await alerter.send_error("Connection timeout")

        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert "Connection timeout" in str(call_args)

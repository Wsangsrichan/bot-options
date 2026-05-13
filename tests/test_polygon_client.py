from unittest.mock import MagicMock, patch
import pytest
from src.polygon_client import PolygonClient


@pytest.mark.asyncio
async def test_fetch_options_chain_returns_data():
    mock_response = {
        "status": "OK",
        "results": {
            "underlying_asset": {"price": 520.50, "ticker": "SPY"},
            "options": [
                {
                    "strike_price": 525.0,
                    "expiration_date": "2026-06-20",
                    "contract_type": "call",
                    "greeks": {
                        "bid": 5.20, "ask": 5.35,
                        "delta": 0.42, "gamma": 0.08,
                        "theta": -0.15, "vega": 0.22,
                        "implied_volatility": 0.185
                    },
                    "volume": 1523,
                    "open_interest": 45000
                }
            ]
        }
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = MagicMock()

        client = PolygonClient(api_key="test", api_base="https://test")
        chain = await client.fetch_options_chain("SPY")

        assert chain.ticker == "SPY"
        assert chain.underlying_price == 520.50
        assert len(chain.options) == 1
        assert chain.options[0].strike == 525.0
        assert chain.options[0].delta == 0.42


@pytest.mark.asyncio
async def test_fetch_options_chain_empty():
    mock_response = {"status": "OK", "results": {"options": []}}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value.json = MagicMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = MagicMock()

        client = PolygonClient(api_key="test", api_base="https://test")
        chain = await client.fetch_options_chain("SPY")

        assert len(chain.options) == 0


@pytest.mark.asyncio
async def test_api_error_returns_empty_chain():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = Exception("API down")

        client = PolygonClient(api_key="test", api_base="https://test")
        chain = await client.fetch_options_chain("SPY")

        assert chain.options == []

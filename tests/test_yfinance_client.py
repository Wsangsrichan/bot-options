import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import pandas as pd
from src.yfinance_client import YFinanceClient


def make_call_row(strike=525.0, bid=5.20, ask=5.35, last=5.25, volume=500, oi=1000):
    return {
        "strike": strike, "bid": bid, "ask": ask, "lastPrice": last,
        "volume": volume, "openInterest": oi
    }


def make_put_row(strike=520.0, bid=3.10, ask=3.25, last=3.20, volume=300, oi=800):
    return {
        "strike": strike, "bid": bid, "ask": ask, "lastPrice": last,
        "volume": volume, "openInterest": oi
    }


@pytest.fixture
def mock_yf_ticker():
    mock_stock = MagicMock()
    mock_stock.options = ["2026-06-20"]

    # Mock fast_info
    type(mock_stock).fast_info = PropertyMock()
    mock_stock.fast_info.last_price = 520.50

    # Mock option_chain
    mock_chain = MagicMock()
    calls_df = pd.DataFrame([make_call_row(), make_call_row(strike=530.0)])
    puts_df = pd.DataFrame([make_put_row()])
    mock_chain.calls = calls_df
    mock_chain.puts = puts_df
    mock_stock.option_chain.return_value = mock_chain

    return mock_stock


@pytest.mark.asyncio
async def test_fetch_options_chain_returns_data(mock_yf_ticker):
    with patch("src.yfinance_client.yf.Ticker", return_value=mock_yf_ticker):
        client = YFinanceClient(greeks_max_strikes_per_side=5)
        chain = await client.fetch_options_chain("SPY")

    assert chain.ticker == "SPY"
    assert chain.underlying_price == 520.50
    assert len(chain.options) == 3
    assert chain.options[0].strike == 525.0
    assert chain.options[0].option_type == "C"
    assert chain.options[0].bid == 5.20
    assert chain.options[0].volume == 500
    assert chain.options[0].open_interest == 1000
    # Last call should be a put
    assert chain.options[-1].option_type == "P"


@pytest.mark.asyncio
async def test_fetch_options_chain_empty():
    mock_stock = MagicMock()
    mock_stock.options = []
    type(mock_stock).fast_info = PropertyMock()
    mock_stock.fast_info.last_price = 520.50

    with patch("src.yfinance_client.yf.Ticker", return_value=mock_stock):
        client = YFinanceClient()
        chain = await client.fetch_options_chain("SPY")

    assert len(chain.options) == 0


@pytest.mark.asyncio
async def test_greeks_computed_for_near_the_money(mock_yf_ticker):
    with patch("src.yfinance_client.yf.Ticker", return_value=mock_yf_ticker):
        client = YFinanceClient(greeks_max_strikes_per_side=1)  # Only 1 strike per side
        chain = await client.fetch_options_chain("SPY")

    # 525 is closer to 520.50 than 530 => 525 gets Greeks, 530 doesn't
    call_525 = [o for o in chain.options if o.strike == 525.0 and o.option_type == "C"][0]
    call_530 = [o for o in chain.options if o.strike == 530.0 and o.option_type == "C"][0]

    # Near-the-money (525) should have IV > 0 computed
    assert call_525.iv > 0
    assert call_525.delta != 0

    # Far from money (530) should have all zeros
    assert call_530.iv == 0
    assert call_530.delta == 0


@pytest.mark.asyncio
async def test_api_error_returns_empty_chain():
    mock_stock = MagicMock()
    mock_stock.options = ["2026-06-20"]
    type(mock_stock).fast_info = PropertyMock()
    mock_stock.fast_info.last_price = 520.50
    mock_stock.option_chain.side_effect = Exception("Yahoo Finance error")

    with patch("src.yfinance_client.yf.Ticker", return_value=mock_stock):
        client = YFinanceClient()
        chain = await client.fetch_options_chain("SPY")

    assert chain.options == []


@pytest.mark.asyncio
async def test_close_is_noop():
    client = YFinanceClient()
    await client.close()  # Should not raise

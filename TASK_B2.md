# bot-options Phase 1 - Batch 2: Polygon Client + Calculator

Working directory: /home/deploy-app/bot-options

## Task 3: Polygon API Client

### Create src/polygon_client.py

```python
import asyncio
from dataclasses import dataclass
from datetime import datetime
import httpx

@dataclass
class OptionData:
    strike: float
    expiration: str
    option_type: str  # 'C' or 'P'
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float

@dataclass
class OptionsChain:
    ticker: str
    underlying_price: float
    options: list
    fetched_at: str

class PolygonClient:
    BASE_URL = "https://api.polygon.io"
    
    def __init__(self, api_key, api_base=None):
        self.api_key = api_key
        self.base = api_base or self.BASE_URL
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def fetch_options_chain(self, ticker: str) -> OptionsChain:
        """Fetch full options chain for a ticker from Polygon."""
        url = f"{self.base}/v3/snapshot/options/{ticker}"
        params = {
            "apiKey": self.api_key,
            "limit": 250,
            "contract_type": "call,put",
            "expiration_date.gte": datetime.now().strftime("%Y-%m-%d"),
            "expiration_date.lte": "2027-01-01",
            "order": "strike_price",
            "sort": "asc"
        }
        
        for attempt in range(3):
            try:
                res = await self.client.get(url, params=params)
                res.raise_for_status()
                data = res.json()
                return self._parse_chain(ticker, data)
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    print(f"[POLYGON] Failed after 3 attempts: {e}")
                    return OptionsChain(ticker=ticker, underlying_price=0, options=[], fetched_at="")
    
    def _parse_chain(self, ticker: str, data: dict) -> OptionsChain:
        results = data.get("results", {})
        underlying = results.get("underlying_asset", {})
        raw_options = results.get("options", [])
        
        options = []
        for raw in raw_options:
            greeks = raw.get("greeks", {})
            opt = OptionData(
                strike=raw.get("strike_price", 0),
                expiration=raw.get("expiration_date", ""),
                option_type="C" if raw.get("contract_type") == "call" else "P",
                bid=greeks.get("bid", 0),
                ask=greeks.get("ask", 0),
                last=raw.get("last_trade", {}).get("price", 0) if isinstance(raw.get("last_trade"), dict) else 0,
                volume=raw.get("volume", 0),
                open_interest=raw.get("open_interest", 0),
                delta=greeks.get("delta", 0),
                gamma=greeks.get("gamma", 0),
                theta=greeks.get("theta", 0),
                vega=greeks.get("vega", 0),
                iv=greeks.get("implied_volatility", 0),
            )
            options.append(opt)
        
        return OptionsChain(
            ticker=ticker,
            underlying_price=underlying.get("price", 0),
            options=options,
            fetched_at=datetime.now().isoformat()
        )
    
    async def close(self):
        await self.client.aclose()
```

### Create tests/test_polygon_client.py

```python
import pytest
from unittest.mock import AsyncMock, patch
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
        mock_get.return_value.json = AsyncMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = AsyncMock()
        
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
        mock_get.return_value.json = AsyncMock(return_value=mock_response)
        mock_get.return_value.raise_for_status = AsyncMock()
        
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
```

Verify: `pytest tests/test_polygon_client.py -v` → 3 PASS

---

## Task 4: Options Calculator

### Create src/calculator.py

```python
import numpy as np
from py_vollib.black_scholes import black_scholes as bs_price
from py_vollib.black_scholes.greeks.analytical import delta, gamma, theta, vega, rho
from scipy.optimize import brentq

class OptionsCalculator:
    TOLERANCE = 1e-8

    def compute_delta(self, option_type, S, K, T, r, sigma):
        flag = 'c' if option_type in ('C', 'c', 'call') else 'p'
        return delta(flag, S, K, T, r, sigma)

    def compute_gamma(self, option_type, S, K, T, r, sigma):
        flag = 'c' if option_type in ('C', 'c', 'call') else 'p'
        return gamma(flag, S, K, T, r, sigma)

    def compute_all_greeks(self, option_type, S, K, T, r, sigma):
        flag = 'c' if option_type in ('C', 'c', 'call') else 'p'
        return {
            'delta': delta(flag, S, K, T, r, sigma),
            'gamma': gamma(flag, S, K, T, r, sigma),
            'theta': theta(flag, S, K, T, r, sigma),
            'vega': vega(flag, S, K, T, r, sigma),
            'rho': rho(flag, S, K, T, r, sigma),
        }

    def solve_iv(self, market_price, option_type, S, K, T, r):
        flag = 'c' if option_type in ('C', 'c', 'call') else 'p'
        
        def objective(sigma):
            try:
                price = bs_price(flag, S, K, T, r, sigma)
                return price - market_price
            except Exception:
                return -999

        try:
            iv = brentq(objective, 0.001, 5.0, xtol=self.TOLERANCE)
            return iv
        except ValueError:
            return 0.0

    def compute_iv_rank(self, current_iv, iv_52w_low, iv_52w_high):
        if iv_52w_high <= iv_52w_low:
            return 50.0
        rank = (current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low) * 100
        return max(0.0, min(100.0, rank))

    def compute_vol_oi_ratio(self, volume, open_interest):
        if open_interest == 0:
            return 0.0
        return volume / open_interest

    def compute_premium(self, price, contracts):
        return price * contracts * 100
```

### Create tests/test_calculator.py

```python
from src.calculator import OptionsCalculator

def test_compute_delta():
    calc = OptionsCalculator()
    d = calc.compute_delta(option_type='c', S=100, K=105, T=0.25, r=0.05, sigma=0.20)
    assert 0.30 < d < 0.45

def test_compute_gamma():
    calc = OptionsCalculator()
    g = calc.compute_gamma(option_type='c', S=100, K=100, T=0.25, r=0.05, sigma=0.20)
    assert g > 0.03

def test_compute_all_greeks():
    calc = OptionsCalculator()
    greeks = calc.compute_all_greeks(option_type='p', S=520, K=515, T=0.08, r=0.05, sigma=0.18)
    assert 'delta' in greeks
    assert 'gamma' in greeks
    assert 'theta' in greeks
    assert 'vega' in greeks
    assert 'rho' in greeks
    assert -0.55 < greeks['delta'] < -0.35

def test_solve_iv():
    calc = OptionsCalculator()
    iv = calc.solve_iv(market_price=5.25, option_type='c', S=520, K=525, T=0.10, r=0.05)
    assert 0.10 < iv < 0.25

def test_iv_rank():
    calc = OptionsCalculator()
    rank = calc.compute_iv_rank(current_iv=0.20, iv_52w_low=0.12, iv_52w_high=0.32)
    assert rank == 40.0

def test_compute_premium():
    calc = OptionsCalculator()
    premium = calc.compute_premium(price=5.25, contracts=100)
    assert premium == 52500.0
```

Verify: `pytest tests/test_calculator.py -v` → 6 PASS

---

## Commit
```
feat(phase-1): Polygon API client + options calculator (Greeks, IV)
```

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

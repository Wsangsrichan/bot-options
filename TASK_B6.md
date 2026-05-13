# bot-options Phase 1: Switch to yfinance (free) + self-computed Greeks

Working directory: /home/deploy-app/bot-options

## Context
yfinance is free, no API key needed. Provides options chain (strikes, bid/ask, volume, OI) but no Greeks. We'll compute Greeks ourselves using py_vollib (already in calculator.py).

**Flow:** yfinance chain → market_price=(bid+ask)/2 → solve IV → compute Greeks → OptionData

**Performance:** SPY has ~200+ options per expiration. Computing IV (Newton-Raphson) for all is slow. Strategy: only compute Greeks for near-the-money strikes (spot ± 10%) to keep scan fast.

## Task 1: Update requirements.txt

ADD or ensure present:
```
yfinance
py_vollib  (keep - already used in calculator.py)
scipy  (keep - needed for IV solver)
```

Run: `pip install yfinance py_vollib scipy`

## Task 2: Update config.py

Remove ThetaData creds. yfinance needs NO credentials.

```python
class Config:
    def __init__(self):
        # Required
        self.telegram_bot_token = self._require("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = self._require("TELEGRAM_CHAT_ID")
        
        # Optional with defaults
        self.scan_tickers = os.getenv("SCAN_TICKERS", "SPY").split(",")
        self.scan_interval_minutes = int(os.getenv("SCAN_INTERVAL_MINUTES", "5"))
        self.database_url = os.getenv("DATABASE_URL", "postgresql://bot:pass@localhost:5432/options")
        
        # Detection thresholds
        self.vol_oi_ratio_threshold = float(os.getenv("VOL_OI_RATIO_THRESHOLD", "0.5"))
        self.premium_zscore_threshold = float(os.getenv("PREMIUM_ZSCORE_THRESHOLD", "2.0"))
        self.min_contracts = int(os.getenv("MIN_CONTRACTS", "50"))
        
        # yfinance Greeks computation
        self.greeks_max_strikes_per_side = int(os.getenv("GREEKS_MAX_STRIKES_PER_SIDE", "10"))
```

Update test_config.py — remove ThetaData tests, test defaults.

## Task 3: Create src/yfinance_client.py (replaces thetadata_client.py)

```python
from dataclasses import dataclass
from datetime import datetime, date
import yfinance as yf
from src.calculator import OptionsCalculator


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
    rho: float
    iv: float


@dataclass
class OptionsChain:
    ticker: str
    underlying_price: float
    options: list
    fetched_at: str


class YFinanceClient:
    def __init__(self, greeks_max_strikes_per_side=10):
        self.calc = OptionsCalculator()
        self.max_strikes = greeks_max_strikes_per_side  # Only compute Greeks for nearest N strikes
        self.risk_free_rate = 0.05  # 5% assumed (could fetch from Treasury API later)

    def fetch_options_chain(self, ticker: str) -> OptionsChain:
        """Fetch full options chain from Yahoo Finance, compute Greeks for near-the-money options."""
        try:
            stock = yf.Ticker(ticker)
            
            # Get underlying price
            info = stock.fast_info
            spot = float(getattr(info, 'last_price', 0) or getattr(info, 'regular_market_price', 0))
            if spot <= 0:
                spot = float(stock.history(period="1d")["Close"].iloc[-1])
            
            # Get all expiration dates
            expirations = stock.options
            if not expirations:
                print(f"[YFINANCE] No options data for {ticker}")
                return OptionsChain(ticker=ticker, underlying_price=spot, options=[], fetched_at="")
            
            # Filter to next 60 days only (relevance + performance)
            from datetime import datetime, timedelta
            cutoff = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
            expirations = [e for e in expirations if e <= cutoff]
            
            options = []
            for exp_str in expirations:
                try:
                    chain = stock.option_chain(exp_str)
                    exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
                    T = max((exp_date - datetime.now()).days / 365.0, 0.005)  # min ~2 days
                    
                    # Get ALL options first (for volume/OI stats)
                    all_calls = chain.calls.to_dict('records') if chain.calls is not None else []
                    all_puts = chain.puts.to_dict('records') if chain.puts is not None else []
                    
                    # Select which options get full Greeks computation
                    calls_to_greek = self._select_near_the_money(all_calls, spot, self.max_strikes)
                    puts_to_greek = self._select_near_the_money(all_puts, spot, self.max_strikes)
                    
                    # Process calls
                    for row in all_calls:
                        opt = self._row_to_option(row, 'C', spot, T, exp_str, row in calls_to_greek)
                        if opt:
                            options.append(opt)
                    
                    # Process puts
                    for row in all_puts:
                        opt = self._row_to_option(row, 'P', spot, T, exp_str, row in puts_to_greek)
                        if opt:
                            options.append(opt)
                            
                except Exception as e:
                    print(f"[YFINANCE] Error fetching {exp_str}: {e}")
            
            print(f"[YFINANCE] {ticker}: {len(options)} options across {len(expirations)} expirations")
            return OptionsChain(
                ticker=ticker,
                underlying_price=spot,
                options=options,
                fetched_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            print(f"[YFINANCE] Failed to fetch {ticker}: {e}")
            return OptionsChain(ticker=ticker, underlying_price=0, options=[], fetched_at="")

    def _select_near_the_money(self, options_list, spot, n):
        """Select up to n strikes nearest to spot price for Greeks computation."""
        if not options_list:
            return set()
        # Sort by distance from spot
        sorted_opts = sorted(options_list, key=lambda x: abs(float(x.get('strike', 0)) - spot))
        selected = sorted_opts[:n]
        return {id(o): o for o in selected}  # Use id() for set membership

    def _row_to_option(self, row, option_type, spot, T, exp_str, compute_greeks):
        """Convert a yfinance row to OptionData, computing Greeks if near-the-money."""
        strike = float(row.get('strike', 0))
        bid = float(row.get('bid', 0) or 0)
        ask = float(row.get('ask', 0) or 0)
        last = float(row.get('lastPrice', 0) or 0)
        volume = int(row.get('volume', 0) or 0)
        oi = int(row.get('openInterest', 0) or 0)

        # Compute Greeks only for near-the-money
        delta = gamma = theta = vega = rho = iv = 0.0
        
        if compute_greeks and bid > 0 and ask > 0 and spot > 0 and T > 0:
            market_price = (bid + ask) / 2.0
            try:
                iv = self.calc.solve_iv(market_price, option_type, spot, strike, T, self.risk_free_rate)
                if iv > 0:
                    greeks = self.calc.compute_all_greeks(option_type, spot, strike, T, self.risk_free_rate, iv)
                    delta = greeks['delta']
                    gamma = greeks['gamma']
                    theta = greeks['theta']
                    vega = greeks['vega']
                    rho = greeks['rho']
            except Exception:
                pass  # Leave Greeks at 0 if calculation fails

        return OptionData(
            strike=strike, expiration=exp_str, option_type=option_type,
            bid=bid, ask=ask, last=last if last > 0 else (bid + ask) / 2,
            volume=volume, open_interest=oi,
            delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho, iv=iv
        )

    def close(self):
        pass  # yfinance is stateless
```

## Task 4: Update src/main.py

```python
from src.yfinance_client import YFinanceClient

# In OptionsBot.__init__:
self.client = YFinanceClient(
    greeks_max_strikes_per_side=self.config.greeks_max_strikes_per_side
)
```

## Task 5: Update .env.example + .env

Remove ThetaData creds. Keep Telegram and scan settings.

## Task 6: Update tests

Delete `tests/test_thetadata_client.py`. Create `tests/test_yfinance_client.py` with mocked yfinance.

Test should mock `yf.Ticker().option_chain()` to return sample data and verify parsing + Greeks computation.

## Task 7: Run tests + smoke test

```bash
cd /home/deploy-app/bot-options
pip install yfinance
python3 -m pytest tests/ -v --tb=short
```

Then real test:
```bash
python3 -c "
from src.yfinance_client import YFinanceClient
client = YFinanceClient()
chain = client.fetch_options_chain('SPY')
print(f'SPOT: \${chain.underlying_price}, Options: {len(chain.options)}')
# Show first call with Greeks
calls = [o for o in chain.options if o.option_type == 'C' and o.iv > 0]
if calls:
    o = calls[0]
    print(f'CALL K={o.strike} exp={o.expiration} IV={o.iv:.3f} d={o.delta:.3f} g={o.gamma:.3f}')
"
```

## Commit message
```
refactor(phase-1): switch to yfinance (free) + self-computed Greeks via py_vollib
```

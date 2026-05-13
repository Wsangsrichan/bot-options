import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd
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
        self.max_strikes = greeks_max_strikes_per_side
        self.risk_free_rate = 0.05

    async def fetch_options_chain(self, ticker: str) -> OptionsChain:
        return await asyncio.to_thread(self._fetch_sync, ticker)

    def _fetch_sync(self, ticker: str) -> OptionsChain:
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

            # Filter to next 60 days
            cutoff = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
            expirations = [e for e in expirations if e <= cutoff]

            options = []
            for exp_str in expirations:
                try:
                    chain = stock.option_chain(exp_str)
                    exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
                    T = max((exp_date - datetime.now()).days / 365.0, 0.005)

                    all_calls = chain.calls.to_dict('records') if chain.calls is not None else []
                    all_puts = chain.puts.to_dict('records') if chain.puts is not None else []

                    for row in all_calls:
                        opt = self._row_to_option(row, 'C', spot, T, exp_str, compute_greeks=True)
                        if opt:
                            options.append(opt)

                    for row in all_puts:
                        opt = self._row_to_option(row, 'P', spot, T, exp_str, compute_greeks=True)
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
        if not options_list:
            return set()
        sorted_opts = sorted(options_list, key=lambda x: abs(self._safe_float(x.get('strike', 0)) - spot))
        return {self._safe_float(o['strike']) for o in sorted_opts[:n]}

    def _safe_float(self, val, default=0.0):
        try:
            v = float(val)
            if pd.isna(v):
                return default
            return v
        except (ValueError, TypeError):
            return default

    def _safe_int(self, val, default=0):
        try:
            v = float(val)
            if pd.isna(v):
                return default
            return int(v)
        except (ValueError, TypeError):
            return default

    def _row_to_option(self, row, option_type, spot, T, exp_str, compute_greeks):
        strike = self._safe_float(row.get('strike', 0))
        bid = self._safe_float(row.get('bid', 0))
        ask = self._safe_float(row.get('ask', 0))
        last = self._safe_float(row.get('lastPrice', 0))
        volume = self._safe_int(row.get('volume', 0))
        oi = self._safe_int(row.get('openInterest', 0))

        delta = gamma = theta = vega = rho = iv = 0.0

        if compute_greeks and spot > 0 and strike > 0 and T > 0:
            # Prefer bid/ask midpoint; fall back to lastPrice when market closed
            if bid > 0 and ask > 0:
                market_price = (bid + ask) / 2.0
            elif last > 0:
                market_price = last
            else:
                market_price = 0

            if market_price > 0:
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
                    pass

            # Fallback: heuristic Greeks for deep ITM/OTM where IV solver fails
            if delta == 0 and gamma == 0:
                h = self.calc.heuristic_greeks(option_type, spot, strike, T, self.risk_free_rate)
                if h:
                    delta = h['delta']
                    gamma = h['gamma']
                    theta = h['theta']
                    vega = h['vega']
                    rho = h['rho']

        if last <= 0 and (bid + ask) > 0:
            last = (bid + ask) / 2

        return OptionData(
            strike=strike, expiration=exp_str, option_type=option_type,
            bid=bid, ask=ask, last=last,
            volume=volume, open_interest=oi,
            delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho, iv=iv
        )

    async def close(self):
        pass

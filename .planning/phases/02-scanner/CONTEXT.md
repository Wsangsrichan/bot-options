# Phase 2: Multi-Ticker Scanner — Context

## Decisions

### Data Source: yfinance (free, no API key)
- No rate limit API key needed — but rate-limited by Yahoo (estimated ~60 req/min)
- Supports all ETFs: SPY, QQQ, IWM, DIA, TLT, GLD, VIX, etc.
- No Greeks in data — we compute ourselves (py_vollib + heuristic)

### Storage: SQLite (not TimescaleDB)
- Original plan used TimescaleDB ($) for time-series
- SQLite is free, single-file, no server needed
- Schema: one table per ticker or single `options_snapshots` table with ticker column
- Retention: 90 days (configurable)

### Scanner Concurrency
- yfinance blocks on I/O — use `asyncio.to_thread()` for concurrent fetches
- 7 tickers × ~5s each = ~35s sequential → ~8s concurrent (with 5 concurrent workers)
- Scan interval: 15 min (same as current)

### Max Pain Formula
```
For each strike K:
  total_value_lost_if_expires_at_K = 0
  for each option:
    if CALL and spot_at_expiry < K: call expires worthless → sellers keep premium
    if PUT and spot_at_expiry > K: put expires worthless → sellers keep premium
    total_value_lost += (premium × OI × 100)
  Max Pain = strike where total_value_lost is MINIMUM
```

### GEX (Gamma Exposure) Formula
```
For each strike K:
  GEX_K = gamma_K × OI_K × 100 × spot_price
  Total GEX = Σ GEX_K for all strikes
  Positive = stabilizing force, Negative = amplifying force
```

### Opportunity Score (0-100)
```
Score = w1 × iv_rank_normalized      (0-100, 25%)
      + w2 × vol_oi_normalized        (50%)
      + w3 × premium_zscore_mapped    (0-100, 15%)
      + w4 × gex_contribution         (0-100, 10%)

Weights tunable via .env
```

### Dashboard
- Lightweight Flask app (not FastAPI — keep deps minimal)
- Routes: `/` — top opportunities table, `/ticker/SPY` — detail view, `/api/opportunities` — JSON
- Auto-refresh via meta tag (no WebSocket needed for MVP)
- Port: 3001 (bot-polymarket uses 3000)

### Backtesting
- Replay stored snapshots against actual forward price moves
- Metrics: hit rate (price moved in signal direction within N days), average return
- Output: simple report + CSV export

## Constraints
- Free stack only (yfinance + SQLite + Flask)
- Python 3.12 + asyncio
- PM2 process management
- All features testable with `pytest`
- Cost: $0/mo

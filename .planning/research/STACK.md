# STACK.md — Technology Stack Recommendations

## API Comparison: US Options Data

| API | Monthly Cost | Options Chain | Greeks | IV Data | Flow/Unusual | Real-time | Rating |
|-----|-------------|---------------|--------|---------|--------------|-----------|--------|
| **Polygon.io** | $29–$79 | ✅ Full chain | ✅ | ✅ IV, IV Rank | ❌ | 15-min delay (paid RT) | ⭐⭐⭐⭐⭐ |
| **Tradier** | $35 | ✅ Full chain | ✅ | ✅ | ❌ | ✅ WebSocket | ⭐⭐⭐⭐ |
| **ThetaData** | $20–$65 | ✅ | ✅ | ✅ | ✅ Unusual flow | ✅ RT | ⭐⭐⭐⭐⭐ |
| **yfinance** | Free | ✅ Limited | ❌ | ✅ Basic | ❌ | 15-min delay | ⭐⭐ |
| **CBOE DataShop** | $100+ | ✅ Official | ✅ | ✅ | ✅ | Delayed | ⭐⭐⭐ |
| **Intrinio** | $200+ | ✅ | ✅ | ✅ | ❌ | Delayed | ⭐⭐⭐ |
| **Alpha Vantage** | Free tier | ❌ No options | ❌ | ❌ | ❌ | 15-min | ⭐ |

### Recommendation: **2-Tier Approach**

1. **Primary Scanner: Polygon.io** ($29/mo Basic → $79/mo for real-time)
   - Best coverage, reliable API, good rate limits
   - Options chains with Greeks included at $79 tier
   - 15-min delay acceptable for swing/positional analysis

2. **Unusual Flow: ThetaData** ($20–$65/mo)
   - Specialized in unusual options activity
   - Historical flow data for backtesting
   - Real-time alerts for large trades

**Total API cost: $50–$144/mo**

---

## Backend: Python 3.12+

**Why Python:**
- `py_vollib` — industry standard Black-Scholes + Greeks
- `numpy`/`pandas` — vectorized options calculations
- `scipy` — implied volatility solving (Newton-Raphson)
- `instructor` — structured LLM output for AI analysis
- `asyncio` + `httpx` — concurrent API polling

**Why NOT Node.js:**
- No mature quant libraries for options math
- `py_vollib` has no JS equivalent
- Python is the standard in quant/options world

---

## Database: PostgreSQL 16 + TimescaleDB

- **TimescaleDB** for time-series options data (chains, Greeks over time)
- Automatic partitioning by time — query recent data fast
- Hypertables for continuous aggregation (hourly/daily IV rank)
- SQLite for config and small reference data

---

## Real-time: Hybrid

| Component | Method | Reason |
|-----------|--------|--------|
| Active watchlist (<30 tickers) | Tradier WebSocket | Real-time quotes, fills |
| Broad scanner (>100 tickers) | Polygon REST polling | Rate-limit safe |
| News/sentiment | RSS polling every 5min | Free, no API cost |

---

## Infrastructure

- **Dev:** Docker Compose (Python + PostgreSQL + Redis)
- **Prod:** Hetzner VPS (same as bot-polymarket)
- **Redis:** Cache API responses, rate limit tracking
- **Deployment:** PM2 for process management, mirroring bot-polymarket pattern

## Production Stack Summary

```
┌─────────────────────────────────────────┐
│  Python 3.12 + asyncio (PM2 managed)    │
├──────────────┬──────────────────────────┤
│  PostgreSQL  │  Redis Cache              │
│  + Timescale │  (API rate limits,        │
│              │   option chain cache)      │
├──────────────┼──────────────────────────┤
│  Polygon.io  │  ThetaData                │
│  (chains,    │  (unusual flow,           │
│   Greeks)    │   alerts)                 │
└──────────────┴──────────────────────────┘
```

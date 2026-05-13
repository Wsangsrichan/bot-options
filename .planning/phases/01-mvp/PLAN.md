# Phase 1: PLAN — MVP Implementation

> **Oracle:** Delegate to Claude Code CLI. 1 task = 1 delegation. Verify after each.

## Architecture

```
Polygon API → PolygonClient → OptionsChain
                                  ↓
                         UnusualDetector
                                  ↓
                         TelegramAlerter → User
```

**Project structure:**
```
bot-options/
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── polygon_client.py
│   ├── calculator.py
│   ├── detector.py
│   ├── alerter.py
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_calculator.py
│   ├── test_detector.py
│   └── test_polygon_client.py
├── requirements.txt
├── .env.example
├── ecosystem.config.cjs
└── CLAUDE.md
```

---

## Task 1: Project Scaffold — requirements.txt + test harness

**Files to create:**
- `requirements.txt` — Python deps (httpx, py_vollib, numpy, pandas, python-telegram-bot, pytest, pytest-asyncio, python-dotenv)
- `.env.example` — template with POLYGON_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID + defaults
- `src/__init__.py` — empty
- `tests/__init__.py` — empty  
- `tests/conftest.py` — sample_chain fixture with realistic SPY option data

**Verify:** `pytest tests/ -v` shows "no tests collected" (expected)

---

## Task 2: Config System

**File:** `src/config.py`

Class `Config` that loads from `.env`:
- Required: `POLYGON_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (raise ValueError if missing)
- Defaults: `POLYGON_API_BASE="https://api.polygon.io"`, `SCAN_TICKERS=["SPY"]`, `SCAN_INTERVAL_MINUTES=5`
- Detection thresholds: `vol_oi_ratio_threshold=0.5`, `premium_zscore_threshold=2.0`, `min_contracts=50`

**Tests:** `tests/test_config.py`
1. `test_config_loads_from_env` — verify env vars mapped correctly
2. `test_config_defaults` — verify defaults for optional vars
3. `test_config_raises_on_missing_required` — verify ValueError

**Verify:** `pytest tests/test_config.py -v` → 3 PASS

---

## Task 3: Polygon API Client

**File:** `src/polygon_client.py`

`PolygonClient` class using `httpx.AsyncClient`:
- `fetch_options_chain(ticker)` → GET `/v3/snapshot/options/{ticker}` → parse into `OptionsChain` dataclass
- `OptionData` dataclass: strike, expiration, option_type, bid, ask, last, volume, OI, delta, gamma, theta, vega, iv
- Retry logic: 3 attempts with exponential backoff (1s, 2s, 4s)
- Error handling: return empty chain on failure (don't crash)

**Tests:** `tests/test_polygon_client.py`
1. `test_fetch_options_chain_returns_data` — mock httpx, verify parsing
2. `test_fetch_options_chain_empty` — empty options list
3. `test_api_error_returns_empty_chain` — exception → empty chain, no crash

**Verify:** `pytest tests/test_polygon_client.py -v` → 3 PASS

---

## Task 4: Options Calculator

**File:** `src/calculator.py`

`OptionsCalculator` class using `py_vollib`:
- `compute_delta(option_type, S, K, T, r, sigma)` → float
- `compute_gamma(option_type, S, K, T, r, sigma)` → float
- `compute_all_greeks(...)` → dict with delta, gamma, theta, vega, rho
- `solve_iv(market_price, option_type, S, K, T, r)` → Black-Scholes IV via `scipy.optimize.brentq`
- `compute_iv_rank(current_iv, iv_52w_low, iv_52w_high)` → 0-100
- `compute_vol_oi_ratio(volume, open_interest)` → ratio
- `compute_premium(price, contracts)` → total USD premium (×100 shares/contract)

**Tests:** `tests/test_calculator.py`
1. `test_compute_delta` — OTM call delta in expected range
2. `test_compute_gamma` — ATM gamma > 0
3. `test_compute_all_greeks` — all 5 Greeks returned
4. `test_solve_iv` — IV in reasonable range
5. `test_iv_rank` — rank calculation correct

**Verify:** `pytest tests/test_calculator.py -v` → 5 PASS

---

## Task 5: Unusual Activity Detector

**File:** `src/detector.py`

`UnusualDetector` class:
- `analyze_chain(ticker, underlying_price, options)` → list of alert dicts
- Detection rules:
  1. Volume/OI ratio ≥ threshold (default 0.5) AND volume ≥ min_contracts
  2. Premium z-score ≥ threshold (default 2.0) — z-score computed from current chain stats
- Each alert contains: ticker, strike, expiration, option_type, price, volume, OI, delta, iv, premium_usd, reason

**Tests:** `tests/test_detector.py`
1. `test_detect_high_vol_oi` — high ratio → alert
2. `test_detect_large_premium` — high premium → alert
3. `test_normal_activity_no_alert` — boring data → no alert
4. `test_skip_low_contracts` — volume < min_contracts → no alert

**Verify:** `pytest tests/test_detector.py -v` → 4 PASS

---

## Task 6: Telegram Alerter

**File:** `src/alerter.py`

`TelegramAlerter` class using `python-telegram-bot`:
- `send_signal(signal_dict)` → format Markdown message + send
- Message format: emoji + ticker + direction + strike + expiration + Greeks + reason
- `send_error(msg)` → error notification

**Tests:** `tests/test_alerter.py`
1. `test_send_alert_formats_message` — mock bot, verify message contains key fields

**Verify:** `pytest tests/test_alerter.py -v` → 1 PASS

---

## Task 7: Main Orchestrator

**File:** `src/main.py`

Async loop:
1. Initialize Config → PolygonClient → UnusualDetector → TelegramAlerter
2. Loop: for each ticker → fetch chain → detect → alert (cap 5 alerts/ticker/cycle)
3. Sleep SCAN_INTERVAL_MINUTES
4. Handle SIGINT/SIGTERM gracefully

**Verify:** `python src/main.py` starts without import errors

---

## Task 8: PM2 Config + Smoke Test

**File:** `ecosystem.config.cjs`
- PM2 config: name=bot-options, interpreter=python3.12, restart_delay=10s, max_restarts=5

**Verify:** Full test suite — `pytest tests/ -v --tb=short` → all PASS

---

## Execution Order

```
Task 1 → Task 2 → [Task 3 + Task 4 (parallel)] → [Task 5 + Task 6 (parallel)] → Task 7 → Task 8
```

Tasks 3+4 are independent (different files). Tasks 5+6 are independent. Tasks 5 depends on 3+4.

---

## Success Criteria
- [ ] `pytest tests/ -v` — all tests pass (13+ tests)
- [ ] `python src/main.py` — runs scan loop without crash
- [ ] With real Polygon key → pulls SPY chain successfully
- [ ] With real Telegram token → sends test alert
- [ ] PM2 stable for 24h with < 5 restarts/day

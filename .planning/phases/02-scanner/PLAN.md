# Phase 2: Multi-Ticker Scanner — Implementation Plan

> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Scan 7 ETFs concurrently, compute Max Pain + GEX, score opportunities, store history in SQLite, show dashboard, backtest signals.

**Architecture:** Extend existing Phase 1 codebase — add `src/storage.py` (SQLite), `src/dashboard.py` (Flask), `src/backtester.py`, upgrade `calculator.py` with Max Pain + GEX, upgrade `detector.py` with composite scoring, make `yfinance_client.py` concurrent multi-ticker.

**Tech Stack:** Python 3.12, yfinance, py_vollib, scipy, SQLite3 (stdlib), Flask, asyncio, PM2

---

## Task 1: Create SQLite storage module

**Objective:** Store options chain snapshots with timestamp, queryable by ticker/date

**Files:**
- Create: `src/storage.py`
- Create: `tests/test_storage.py`

**Step 1: Write failing test**

```python
# tests/test_storage.py
import os
import pytest
from datetime import datetime
from src.storage import OptionsStore

@pytest.fixture
def store():
    db_path = "/tmp/test_options.db"
    s = OptionsStore(db_path)
    yield s
    s.close()
    if os.path.exists(db_path):
        os.remove(db_path)

def test_init_creates_tables(store):
    tables = store._list_tables()
    assert "snapshots" in tables

def test_save_and_load_snapshot(store):
    ts = datetime.now().isoformat()
    store.save_snapshot("SPY", 520.5, ts, 100, [
        {"strike": 520, "option_type": "C", "bid": 5.0, "ask": 5.5, "last": 5.25,
         "volume": 500, "open_interest": 1000, "delta": 0.55, "gamma": 0.02,
         "theta": -0.5, "vega": 0.3, "rho": 0.1, "iv": 0.18}
    ])
    
    rows = store.get_snapshots("SPY", limit=10)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "SPY"
    assert rows[0]["underlying_price"] == 520.5
```

**Step 2: Run test → FAIL**

**Step 3: Write `src/storage.py`** — SQLite wrapper with `save_snapshot()`, `get_snapshots()`, `get_latest()`, `close()`. Schema: `snapshots(id, ticker, underlying_price, fetched_at, option_count, options JSON)`. Use `sqlite3` from stdlib.

**Step 4: Run test → PASS**

**Step 5: Commit** — `git add src/storage.py tests/test_storage.py && git commit -m "feat: SQLite storage for options snapshots"`

---

## Task 2: Add Max Pain to calculator

**Objective:** Compute max pain strike from options chain (OI-weighted)

**Files:**
- Modify: `src/calculator.py` (add method)
- Modify: `tests/test_calculator.py` (add test)

**Step 1: Write failing test**

```python
def test_max_pain():
    calc = OptionsCalculator()
    options = [
        {"strike": 520, "option_type": "C", "open_interest": 100, "last": 5.0},
        {"strike": 520, "option_type": "P", "open_interest": 50,  "last": 4.0},
        {"strike": 525, "option_type": "C", "open_interest": 80,  "last": 3.0},
        {"strike": 525, "option_type": "P", "open_interest": 200, "last": 6.0},
    ]
    # Call at 520: calls ITM (100*5*100=50000 pain), puts expire worthless → pain=50000
    # Call at 525: calls expire worthless, puts ITM (200*6*100=120000 pain) → pain=120000
    # Call at 520: pain=50000 vs 525: pain=120000 → max pain=520
    mp = calc.max_pain(options, spot=522.5)
    assert mp == 520.0
```

**Step 2: Run test → FAIL**

**Step 3: Implement `max_pain(options: list[dict], spot: float) -> float`** — iterate all unique strikes, compute total pain (sum of OI × premium × 100 for options that would be ITM), return strike with minimum pain.

**Step 4: Run test → PASS**

**Step 5: Commit**

---

## Task 3: Add GEX (Gamma Exposure) to calculator

**Objective:** Compute net gamma exposure by strike

**Files:**
- Modify: `src/calculator.py` (add method)
- Modify: `tests/test_calculator.py` (add test)

**Step 1: Write failing test**

```python
def test_gamma_exposure():
    calc = OptionsCalculator()
    options = [
        {"strike": 520, "option_type": "C", "gamma": 0.02, "open_interest": 100},
        {"strike": 520, "option_type": "P", "gamma": 0.02, "open_interest": 50},  # puts have same gamma sign for positive
        {"strike": 525, "option_type": "C", "gamma": 0.01, "open_interest": 200},
    ]
    spot = 522.5
    # GEX = Σ gamma × OI × 100 × spot
    # 520 CALL: 0.02 * 100 * 100 * 522.5 = 104500
    # 520 PUT:  0.02 * 50  * 100 * 522.5 = 52250
    # 525 CALL: 0.01 * 200 * 100 * 522.5 = 104500
    # Total GEX = 261250
    gex = calc.gamma_exposure(options, spot)
    assert abs(gex["total"] - 261250) < 1
    
    # Should also return per-strike breakdown
    assert "by_strike" in gex
    assert 520.0 in gex["by_strike"]
```

**Step 2: Run test → FAIL**

**Step 3: Implement `gamma_exposure(options, spot) -> dict`** — returns `{"total": float, "by_strike": {strike: float}, "positive": float, "negative": float}`. Note: CALL gamma is always positive, PUT gamma sign depends on library but typically POSITIVE for puts too (gamma is second derivative, always positive for long positions). Use ABS of gamma.

**Step 4: Run test → PASS**

**Step 5: Commit**

---

## Task 4: Concurrent multi-ticker scanner

**Objective:** Fetch options chains for multiple tickers concurrently

**Files:**
- Modify: `src/yfinance_client.py` (add `fetch_multiple()`)
- Modify: `src/config.py` (change SCAN_TICKERS default)
- Modify: `tests/test_yfinance_client.py` (add test)

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_fetch_multiple_tickers():
    mock_stock = MagicMock()
    mock_stock.options = ["2026-06-20"]
    type(mock_stock).fast_info = PropertyMock()
    mock_stock.fast_info.last_price = 520.50
    mock_chain = MagicMock()
    mock_chain.calls = pd.DataFrame([make_call_row()])
    mock_chain.puts = pd.DataFrame([make_put_row()])
    mock_stock.option_chain.return_value = mock_chain

    with patch("src.yfinance_client.yf.Ticker", return_value=mock_stock):
        client = YFinanceClient()
        chains = await client.fetch_multiple(["SPY", "QQQ"])
    
    assert len(chains) == 2
    assert chains[0].ticker == "SPY"
    assert chains[1].ticker == "QQQ"
```

**Step 2: Run test → FAIL**

**Step 3: Implement `fetch_multiple(tickers: list[str], max_concurrent=5) -> list[OptionsChain]`** — use `asyncio.Semaphore` + `asyncio.gather()` with `asyncio.to_thread()` for concurrent yfinance calls.

**Step 4: Run test → PASS**

**Step 5: Update `.env`** — `SCAN_TICKERS=SPY,QQQ,IWM,DIA,TLT,GLD,VIX`

**Step 6: Commit**

---

## Task 5: Composite opportunity scoring

**Objective:** Rank opportunities with a 0-100 composite score

**Files:**
- Modify: `src/detector.py` (add `score_opportunity()`)
- Modify: `tests/test_detector.py` (add test)

**Step 1: Write failing test**

```python
def test_composite_score():
    detector = UnusualDetector(vol_oi_threshold=0.5, premium_zscore=2.0, min_contracts=10)
    signal = {
        "vol_oi_ratio": 1.5,
        "premium_zscore": 3.5,
        "iv_rank": 65.0,
        "gex_contribution": 0.05,  # 5% of total GEX
    }
    score = detector.score_opportunity(signal)
    assert 0 <= score <= 100
    # High vol/OI + high z-score should score > 50
    assert score > 50
```

**Step 2: Run test → FAIL**

**Step 3: Implement `score_opportunity(signal) -> float`** — weighted composite:
- vol_oi_normalized = min(vol_oi_ratio / 2.0, 1.0) × 100 (cap at 2.0)
- premium_zscore_mapped = min(zscore / 5.0, 1.0) × 100 (cap at 5.0)
- iv_rank_direct = iv_rank (already 0-100)
- gex_normalized = min(abs(gex_contribution) * 10, 1.0) × 100 (cap at 10%)
- Weights from config: `OPPORTUNITY_SCORE_WEIGHTS=25,50,15,10` (IV, Vol/OI, Premium, GEX)

**Step 4: Run test → PASS**

**Step 5: Commit**

---

## Task 6: Integrate storage + scoring into main loop

**Objective:** Save snapshots to SQLite, compute max pain + GEX each cycle, rank and log top 5 opportunities

**Files:**
- Modify: `src/main.py`
- Modify: `src/config.py` (add new config keys)

**Step 1: Modify `OptionsBot.__init__`** — add `self.store = OptionsStore(...)`, add score weights from config

**Step 2: Modify `scan_cycle`** — 
- Use `client.fetch_multiple()` instead of single ticker
- After fetching: store snapshot via `self.store.save_snapshot()`
- Compute max_pain + gex per ticker via `self.calc`
- Score each alert via `self.detector.score_opportunity()`
- Sort alerts by score, send top 5
- Log summary with scores

**Step 3: Update config** — add `DATABASE_PATH=./data/options.db`, `DASHBOARD_PORT=3001`, `OPPORTUNITY_SCORE_WEIGHTS=25,50,15,10`, `MAX_CONCURRENT_FETCHES=5`

**Step 4: Manual end-to-end test** — `python3 src/main.py` → verify multi-ticker scan + storage + scored alerts

**Step 5: Commit**

---

## Task 7: Flask dashboard

**Objective:** Simple web UI showing top opportunities with scores

**Files:**
- Create: `src/dashboard.py`
- Create: `templates/dashboard.html`
- Create: `tests/test_dashboard.py`
- Add: `flask` to `requirements.txt`

**Step 1: Write `src/dashboard.py`** — Flask app:
- `GET /` — HTML table: Ticker, Type, Strike, Exp, Score, Reason, Premium, Time
- `GET /ticker/<ticker>` — detail for one ticker
- `GET /api/opportunities?limit=20` — JSON API
- Reads from SQLite `OptionsStore`, auto-refresh every 60s

**Step 2: Write `templates/dashboard.html`** — simple dark theme HTML table, auto-refresh meta tag

**Step 3: Write failing test** — `test_dashboard_returns_html`, `test_api_returns_json`

**Step 4: Run test → PASS**

**Step 5: Add to `ecosystem.config.cjs`** — new PM2 app entry for dashboard

**Step 6: Commit**

---

## Task 8: Backtesting engine

**Objective:** Replay historical signals against forward price moves, compute hit rate

**Files:**
- Create: `src/backtester.py`
- Create: `tests/test_backtester.py`

**Step 1: Write failing test**

```python
def test_backtest_hit_rate():
    bt = Backtester(store_path="/tmp/test_backtest.db")
    # Insert 2 snapshots: 1 with a signal that was correct, 1 that was wrong
    snapshots = [...]
    results = bt.run(ticker="SPY", forward_days=5)
    assert "hit_rate" in results
    assert 0 <= results["hit_rate"] <= 100
```

**Step 2: Write `src/backtester.py`** — `Backtester` class:
- `run(ticker, forward_days=5)` — for each snapshot, check actual price movement N days later from subsequent snapshots
- Signal direction: CALL → bullish (price should rise), PUT → bearish (price should fall)
- Returns: `{"hit_rate": %, "total_signals": N, "correct": N, "avg_return": %}`

**Step 3: Run test → PASS**

**Step 4: Add CLI** — `python3 src/backtester.py --ticker SPY --days 5`

**Step 5: Commit**

---

## Verification (after all tasks)

```bash
# All tests
python3 -m pytest tests/ -v
# Expected: all pass

# End-to-end
python3 src/main.py
# Expected: multi-ticker scan → SQLite storage → scored alerts → Telegram

# Dashboard
python3 src/dashboard.py
# Visit http://localhost:3001
```

---

## Deployment

After all tests pass:
1. `git push`
2. SSH to prod → `git pull` → `pm2 delete bot-options` → `pm2 start ecosystem.config.cjs`
3. Start dashboard: `pm2 start src/dashboard.py --name options-dashboard --interpreter .venv/bin/python3`
4. Verify alerts arriving via Telegram

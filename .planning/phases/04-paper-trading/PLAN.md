# Phase 4: Paper Trading — Implementation Plan

> **For Hermes:** Use Claude Code via `claude -p` to implement.

**Goal:** Paper trading engine — auto-trade based on AI confidence, track PnL, enforce exit rules.

**Architecture:** Add `paper_trader.py`, `position_manager.py`, `exit_rules.py`. Extend storage, main loop, dashboard, config.

**Tech Stack:** Python 3.12, SQLite, asyncio (no new dependencies).

---

## Task 1: Position Storage & Manager

**Files:**
- Modify: `src/storage.py` (add `paper_positions` table + CRUD)
- Create: `src/position_manager.py`
- Create: `tests/test_position_manager.py`

### 1A: Extend storage.py

Add to `_init_tables`:
```sql
CREATE TABLE IF NOT EXISTS paper_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    option_type TEXT NOT NULL,
    strike REAL NOT NULL,
    expiration TEXT NOT NULL,
    entry_price REAL NOT NULL,
    entry_spot REAL NOT NULL,
    entry_delta REAL,
    entry_iv REAL,
    contracts INTEGER DEFAULT 1,
    entry_time TEXT NOT NULL,
    exit_price REAL,
    exit_time TEXT,
    pnl REAL DEFAULT 0,
    status TEXT DEFAULT 'open'
)
```

Add methods:
- `save_position(ticker, option_type, strike, expiration, entry_price, entry_spot, entry_delta, entry_iv, contracts=1) -> int` — returns position id
- `get_open_positions() -> list[dict]`
- `close_position(position_id, exit_price, exit_time, pnl)`
- `get_position_history(limit=100) -> list[dict]`
- `get_account_summary() -> dict` — {cash, total_invested, total_pnl, open_count, closed_count}

Add new tests in `tests/test_storage.py`:
- `test_save_and_get_open_positions`
- `test_close_position`
- `test_get_account_summary`

### 1B: Create position_manager.py

```python
class PositionManager:
    def __init__(self, store, initial_balance=10000):
        self.store = store
        self.initial_balance = initial_balance
    
    def open_position(self, alert, spot_price) -> int | None:
        """Open paper position from alert. Returns position_id or None."""
        if alert.get('bid', 0) <= 0 or alert.get('ask', 0) <= 0:
            return None
        entry = (alert['bid'] + alert['ask']) / 2
        cost = entry * 100  # 1 contract = 100 shares
        
        summary = self.store.get_account_summary()
        available = self.initial_balance + summary['total_pnl'] - summary['total_invested']
        if cost > available:
            return None  # Not enough cash
        
        return self.store.save_position(
            ticker=alert['ticker'],
            option_type=alert['option_type'],
            strike=alert['strike'],
            expiration=alert['expiration'],
            entry_price=entry,
            entry_spot=spot_price,
            entry_delta=alert.get('delta', 0),
            entry_iv=alert.get('iv', 0),
            contracts=1,
        )
    
    def close_position(self, position_id, exit_price, reason=""):
        pos = ... # get position from store
        pnl = (exit_price - pos['entry_price']) * pos['contracts'] * 100
        self.store.close_position(position_id, exit_price, datetime.now().isoformat(), pnl)
        return pnl
    
    def get_portfolio(self) -> dict:
        """Full portfolio summary."""
        summary = self.store.get_account_summary()
        open_positions = self.store.get_open_positions()
        return {
            'initial_balance': self.initial_balance,
            'cash': self.initial_balance + summary['total_pnl'] - summary['total_invested'],
            'total_pnl': summary['total_pnl'],
            'open_positions': len(open_positions),
            'positions': open_positions,
        }
```

### 1C: Tests

```python
def test_open_position(position_manager, sample_alert):
    pos_id = position_manager.open_position(sample_alert, spot_price=520.0)
    assert pos_id is not None
    
def test_portfolio_summary(position_manager):
    portfolio = position_manager.get_portfolio()
    assert portfolio['initial_balance'] == 10000
```

---

## Task 2: Exit Rules Engine

**Files:**
- Create: `src/exit_rules.py`
- Create: `tests/test_exit_rules.py`

```python
class ExitRules:
    def __init__(self, stop_loss_pct=-0.50, take_profit_pct=1.00, min_dte_days=5):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_dte_days = min_dte_days
    
    def check_position(self, position, current_price, current_date) -> str | None:
        """Check if position should be closed. Returns reason string or None."""
        pnl_pct = (current_price - position['entry_price']) / position['entry_price']
        
        if pnl_pct <= self.stop_loss_pct:
            return f"stop_loss ({pnl_pct:.0%})"
        if pnl_pct >= self.take_profit_pct:
            return f"take_profit ({pnl_pct:.0%})"
        
        exp_date = datetime.strptime(position['expiration'], '%Y-%m-%d')
        days_left = (exp_date - current_date).days
        if days_left < self.min_dte_days:
            return f"dte_threshold ({days_left}d left)"
        
        return None
```

Tests:
```python
def test_stop_loss_triggers():
    rules = ExitRules(stop_loss_pct=-0.50)
    pos = {'entry_price': 5.0, 'expiration': '2026-12-31'}
    assert rules.check_position(pos, current_price=2.0, current_date=datetime(2026,6,1)) == "stop_loss (-60%)"

def test_no_exit():
    rules = ExitRules()
    pos = {'entry_price': 5.0, 'expiration': '2026-12-31'}
    assert rules.check_position(pos, current_price=5.5, current_date=datetime(2026,6,1)) is None
```

---

## Task 3: Paper Trader (main orchestrator)

**Files:**
- Create: `src/paper_trader.py`
- Create: `tests/test_paper_trader.py`

```python
class PaperTrader:
    def __init__(self, position_manager, exit_rules, ai_confidence_threshold=60):
        self.pm = position_manager
        self.rules = exit_rules
        self.confidence_threshold = ai_confidence_threshold
    
    async def evaluate_alert(self, alert, chain) -> bool:
        """Evaluate if we should paper-trade this alert. Returns True if traded."""
        # Only trade if AI confidence above threshold
        ai_conf = alert.get('ai_confidence', 0)
        if ai_conf < self.confidence_threshold:
            return False
        
        # Only trade if direction is clear (not neutral)
        if alert.get('ai_direction') == 'neutral':
            return False
        
        # Try to open position
        pos_id = self.pm.open_position(alert, chain.underlying_price)
        if pos_id:
            print(f"  [PAPER] Opened {alert['option_type']} K={alert['strike']} conf={ai_conf}% — ID={pos_id}")
            return True
        return False
    
    async def check_exits(self, client) -> int:
        """Check all open positions for exit conditions. Returns count of closed positions."""
        closed = 0
        positions = self.pm.store.get_open_positions()
        
        for pos in positions:
            # Get current price (simplified: use last price from yfinance)
            # For now, we estimate current price from spot movement
            # TODO: fetch actual option price
            
            # Skip for MVP — will implement real price fetching later
            pass
        
        return closed
```

Tests: mock position manager, verify threshold logic.

---

## Task 4: Integrate into Main Loop

**Files:**
- Modify: `src/main.py`
- Modify: `src/config.py`

### config.py additions:
```python
self.enable_paper_trading = os.getenv("ENABLE_PAPER_TRADING", "false").lower() == "true"
self.paper_initial_balance = float(os.getenv("PAPER_INITIAL_BALANCE", "10000"))
self.paper_ai_confidence_threshold = int(os.getenv("PAPER_AI_CONFIDENCE_THRESHOLD", "60"))
self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "-0.50"))
self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "1.00"))
self.min_dte_days = int(os.getenv("MIN_DTE_DAYS", "5"))
```

### main.py additions:
```python
# In __init__:
if config.enable_paper_trading:
    self.pm = PositionManager(self.store, config.paper_initial_balance)
    self.exit_rules = ExitRules(config.stop_loss_pct, config.take_profit_pct, config.min_dte_days)
    self.paper_trader = PaperTrader(self.pm, self.exit_rules, config.paper_ai_confidence_threshold)
else:
    self.paper_trader = None

# In scan_cycle, after AI analysis:
if self.paper_trader:
    for alert in scored_alerts:
        if alert.get('ai_interpretation'):
            traded = await self.paper_trader.evaluate_alert(alert, chain)
    # Check exits
    closed = await self.paper_trader.check_exits(self.client)
    if closed:
        print(f"  [PAPER] Closed {closed} position(s)")
```

---

## Task 5: Dashboard — Paper Portfolio Tab

**Files:**
- Modify: `src/dashboard.py`

Add new routes:
- `GET /paper` — paper portfolio page: balance, PnL, open positions table
- `GET /api/paper/portfolio` — JSON with portfolio summary

HTML template: add navigation tabs (Opportunities | Paper Portfolio), show positions table with current PnL.

---

## Task 6: Configuration (.env)

Add to dev `.env`:
```
ENABLE_PAPER_TRADING=true
PAPER_INITIAL_BALANCE=10000
PAPER_AI_CONFIDENCE_THRESHOLD=60
STOP_LOSS_PCT=-0.50
TAKE_PROFIT_PCT=1.00
MIN_DTE_DAYS=5
```

---

## Verification

```bash
python3 -m pytest tests/ -v
# All must pass

# Manual: run bot, verify paper trades appear in log
timeout 45 python3 src/main.py
# Check: "[PAPER] Opened ..." lines in output
```

---

## Deployment
1. `git push`
2. Update prod `.env` with paper trading config
3. `pm2 restart bot-options`
4. Check Telegram for paper trade notifications

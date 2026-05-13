# Phase 4: Paper Trading — Context & Decisions

## Goal
เพิ่ม paper trading engine — จำลองซื้อขาย options ด้วยเงินเสมือน ทดสอบกลยุทธ์ก่อนใช้เงินจริง

## Design Decisions

### Auto vs Manual
- **Paper trading = Auto** — ไม่ต้อง human gate เพราะไม่มีเงินจริง
- ใช้ AI confidence threshold ในการตัดสินใจเข้า trade (configurable)
- Exit rules ทำงานอัตโนมัติทุก cycle

### Virtual Account
- Starting balance: $10,000 (configurable)
- Position size: 1 contract only (fixed for MVP)
- Simulated fills: assume mid-price execution (bid+ask)/2
- Commission: $0.65/contract (mimics real broker)

### Position Lifecycle
```
Alert detected → AI score > threshold → "Buy" paper position
  → Track position (entry price, Greeks, time)
  → Every cycle: check exit rules
     → Stop-loss hit? → Close at loss
     → Take-profit hit? → Close at gain
     → DTE < threshold? → Close before expiry
     → Expired? → Auto-exercise/settle
  → Record realized PnL
```

### Exit Rules
| Rule | Default | Description |
|------|---------|-------------|
| STOP_LOSS_PCT | -50% | Close if position loss > 50% |
| TAKE_PROFIT_PCT | +100% | Close if gain > 100% |
| MIN_DTE_DAYS | 5 | Close if < 5 days to expiration |

### Storage
- New table: `paper_positions` in existing SQLite
- Columns: id, ticker, option_type, strike, expiration, entry_price, entry_spot, entry_delta, entry_iv, contracts, entry_time, exit_price, exit_time, pnl, status (open/closed)

### Dashboard
- Tab/section for paper portfolio
- Summary: cash, total PnL, open positions count
- Open positions table with real-time PnL

### Config
```
ENABLE_PAPER_TRADING=true
PAPER_INITIAL_BALANCE=10000
PAPER_AI_CONFIDENCE_THRESHOLD=60
PAPER_POSITION_SIZE=1
STOP_LOSS_PCT=-0.50
TAKE_PROFIT_PCT=1.00
MIN_DTE_DAYS=5
```

### Telegram Integration (Phase 4.1 — optional)
- Send paper trade notifications to Telegram
- Future: Telegram inline keyboard for buy/skip decisions

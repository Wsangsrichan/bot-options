# Plan: Webull Trade API Integration for bot-options

**Date:** 2026-05-15 09:10 UTC
**Phase:** GSD Phase B7 — Real Broker Integration
**Goal:** ให้ bot-options trade ของจริงผ่าน Webull API แทน paper trading only

---

## Context

- ปัจจุบัน bot-options ใช้ Paper Trading เท่านั้น (`broker_paper.py`)
- Webull มี OpenAPI รองรับ options trading เต็มรูปแบบ
- Python SDK: `webull` package → `ApiClient` + `TradeClient`
- Bot มี abstract `Broker` interface อยู่แล้ว — เหลือแค่ implement คลาสใหม่

---

## Webull API Key Findings

### Auth
```python
from webull import ApiClient
api = ApiClient("<app_key>", "<app_secret>", "us")
api.add_endpoint("us", "<api_endpoint>")
trade_client = TradeClient(api)
```

### Options Order Format (Single-Leg)
```json
{
  "account_id": "...",
  "new_orders": [{
    "client_order_id": "<uuid>",
    "combo_type": "NORMAL",
    "order_type": "LIMIT",
    "limit_price": "11.25",
    "quantity": "1",
    "option_strategy": "SINGLE",
    "side": "BUY",
    "time_in_force": "DAY",
    "entrust_type": "QTY",
    "instrument_type": "OPTION",
    "market": "US",
    "symbol": "AAPL",
    "legs": [{
      "side": "BUY",
      "quantity": "1",
      "symbol": "AAPL",
      "strike_price": "220.00",
      "option_expire_date": "2026-06-19",
      "instrument_type": "OPTION",
      "option_type": "CALL",
      "market": "US"
    }]
  }]
}
```

### Key Constraints
- ❌ No MARKET orders for options — LIMIT only
- ❌ SELL side only supports DAY (ไม่ใช่ GTC)
- ✅ BUY side supports GTC
- ✅ Supported: LIMIT, STOP_LOSS, STOP_LOSS_LIMIT
- ✅ Strategies: SINGLE (เราใช้แค่นี้ก่อน)

### Endpoints Needed
- `POST /trade/order` — place order
- `GET /trade/account/list` — list accounts
- `GET /trade/account/positions` — get positions
- `GET /trade/account/balance` — get balances
- `POST /trade/order/replace` — modify order
- `POST /trade/order/cancel` — cancel order

---

## Files to Change

| File | Action | Description |
|------|--------|-------------|
| `requirements.txt` | MODIFY | Add `webull` package |
| `src/broker_webull.py` | **NEW** | Webull broker implementation |
| `src/config.py` | MODIFY | Add Webull config vars |
| `src/main.py` | MODIFY | Hybrid mode: paper ↔ webull |
| `.env.example` | MODIFY | Document new env vars |

---

## Task Breakdown

### Task 1: Add webull SDK dependency
- Add `webull` to `requirements.txt`
- Install on dev + prod

### Task 2: Create `src/broker_webull.py`
Implement `Broker` abstract class:

```python
class WebullBroker(Broker):
    def __init__(self, app_key, app_secret, endpoint, region="us"):
        # Init ApiClient + TradeClient
    
    def connect(self) -> bool:
        # Verify API key by fetching account list
    
    def buy_option(self, ticker, option_type, strike, expiration,
                   quantity=1, price_limit=None) -> OrderResult:
        # Map to Webull SINGLE-leg option order
        # option_type: "C" → "CALL", "P" → "PUT"
        # Build legs array with strike_price, option_expire_date
    
    def sell_option(self, ...) -> OrderResult:
        # Same as buy but side=SELL
    
    def get_positions(self) -> list[PositionInfo]:
        # Fetch from Webull, map to PositionInfo dataclass
    
    def get_account_value(self) -> float:
        # From balance endpoint
    
    def get_buying_power(self) -> float:
        # From balance endpoint
```

### Task 3: Add config vars
```python
# Webull API
self.webull_app_key = os.getenv("WEBULL_APP_KEY", "")
self.webull_app_secret = os.getenv("WEBULL_APP_SECRET", "")
self.webull_endpoint = os.getenv("WEBULL_ENDPOINT", "")
self.webull_account_id = os.getenv("WEBULL_ACCOUNT_ID", "")
self.broker_mode = os.getenv("BROKER_MODE", "paper")  # "paper" or "webull"
```

### Task 4: Integrate into main.py
- If `BROKER_MODE=webull` → init `WebullBroker` instead of `BrokerPaper`
- Pass broker to `PaperTrader` (or rename to `LiveTrader`)
- Add safety: `DRY_RUN` for real broker (preview orders without executing)

### Task 5: Deduplicate positions
- Check existing positions before opening (prevent double-buy)
- Pattern from paper_trader: scan for same ticker+option_type+strike+expiration

---

## GSD Phases

| Phase | Scope | Duration |
|-------|-------|----------|
| B7.1 | `broker_webull.py` — core implementation | 1 batch |
| B7.2 | Config + main.py integration | 1 batch |
| B7.3 | Live test on dev (dry_run first) | Manual |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Webull SDK not available on pip | Use raw REST + HMAC signing |
| API key requires approval | Test with sandbox endpoint first |
| Real money loss | `BROKER_DRY_RUN=true` default, human gate |
| Options pricing mismatch | Use limit orders with bot's estimated price |
| Rate limits | Respect Webull rate limits in order placement |

---

## Verification

1. `WebullBroker.connect()` returns True with valid credentials
2. `buy_option()` returns `OrderResult(success=True)` with order_id
3. `get_positions()` returns actual positions from Webull
4. `get_account_value()` returns correct balance
5. Bot runs full cycle with `BROKER_MODE=webull` without crashes
6. Paper dashboard still works in parallel

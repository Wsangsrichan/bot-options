# FEATURES.md — Feature Breakdown by Phase

## Phase 1: MVP — Single Ticker Analysis (2 weeks)

**Goal:** Pull options chain for SPY, compute Greeks, flag unusual activity → Telegram alert

| Feature | Priority | Description |
|---------|----------|-------------|
| Data ingestion | P0 | Polygon API poller — fetch options chain for configurable ticker list |
| Black-Scholes engine | P0 | Compute Delta, Gamma, Theta, Vega, Rho for each strike |
| IV calculation | P0 | Solve implied volatility from market price (Newton-Raphson) |
| IV Rank/Percentile | P1 | Compare current IV to 52-week range |
| Unusual activity detector | P0 | Flag volume/OI ratio > threshold, large premium trades |
| Telegram alert | P1 | Send alerts when opportunity detected |
| Config system | P0 | `.env` for API keys, ticker list, thresholds |

**Success criteria:** Pull SPY chain every 5 min, detect at least 1 genuine unusual activity per day with <10% false positive rate.

**Cost:** $29/mo (Polygon Basic) + Hetzner ~$5/mo

---

## Phase 2: Multi-Ticker Scanner (3 weeks)

**Goal:** Scan 20-50 ETF tickers, rank by opportunity score, store history

| Feature | Priority | Description |
|---------|----------|-------------|
| Multi-ticker scanner | P0 | Concurrent scanning of 20-50 ETFs |
| Opportunity scoring | P0 | Composite score: IV Rank + Vol/OI + Greeks alignment + Flow |
| Historical storage | P0 | TimescaleDB — store chains over time for backtesting |
| Max Pain calculator | P1 | Calculate max pain strike from open interest distribution |
| Gamma Exposure (GEX) | P1 | Net gamma by strike for market maker hedging impact |
| Scanner dashboard | P2 | Simple HTML dashboard showing top opportunities |
| Backtesting framework | P1 | Replay historical signals against actual price moves |

**Success criteria:** Scan 30 tickers in <3 min, rank top 5 opportunities, <20% false positive.

**Cost:** $79/mo (Polygon RT) + $20/mo (ThetaData basic)

---

## Phase 3: AI Analysis (2 weeks)

**Goal:** LLM interprets options flow + combines with news sentiment for context

| Feature | Priority | Description |
|---------|----------|-------------|
| AI signal interpreter | P0 | Feed options data + news to DeepSeek, get structured analysis |
| News aggregation | P1 | RSS feeds (Bloomberg, Reuters) for ETF-relevant news |
| Sentiment overlay | P1 | Match unusual flow with news events ("earnings play," "hedge unwind") |
| Structured output | P0 | `instructor` library — JSON output with confidence score + reasoning |
| Hallucination guard | P0 | Validate AI claims against actual data before alerting |

**Success criteria:** AI adds context that reduces false positives by 30% vs pure quantitative signals.

**Cost:** +$0.50/day DeepSeek API (~$15/mo)

---

## Phase 4: Trade Execution (Optional — Human Gate)

**Goal:** Connect to Tradier brokerage for actual trade execution

| Feature | Priority | Description |
|---------|----------|-------------|
| Tradier integration | P0 | OAuth, account info, options order placement |
| Pre-trade checklist | P0 | Mandatory human approval gate before any order |
| Position tracking | P1 | Track open positions, Greeks, PnL |
| Exit rules | P1 | Time-based (DTE threshold), profit target, stop-loss |
| Paper trading | P2 | Simulated trading for strategy validation |

**Human gate is MANDATORY.** No auto-execution. Bot presents analysis → human approves trade.

---

## Out of Scope (v1)

- Multi-leg strategies (spreads, iron condors) — v2
- Auto-execution — never
- Individual stocks (focus on ETFs first)
- Mobile app — Telegram + web dashboard only

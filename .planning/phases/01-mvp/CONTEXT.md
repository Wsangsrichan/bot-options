# Phase 1: MVP — Context & Decisions

## What We're Building

Single-ticker (SPY) options analysis bot that:
1. Pulls options chain from Polygon.io every 5 minutes
2. Computes Greeks using py_vollib
3. Detects unusual activity (volume/OI ratio, large premium trades)
4. Sends formatted alerts to Telegram

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| First ticker | SPY | Most liquid options market, best data quality |
| Data source | Polygon.io Basic ($29/mo) | Cheapest tier with Greeks included |
| Greeks library | py_vollib | Industry standard, no Python alternative |
| IV calculation | Use Polygon-provided IV (not self-calculated) | Avoid divergence, Polygon Greeks are reliable |
| Alert threshold | Vol/OI > 0.5, Premium z-score > 2.0 | Conservative start — tune after 1 week |
| Database | Skip for MVP | TimescaleDB added in Phase 2 |
| AI | Skip for MVP | DeepSeek integration in Phase 3 |
| Backtesting | Skip for MVP | Added in Phase 2 |

## Gray Areas

1. **IV Rank needs 52-week data** — MVP will skip IV Rank (requires historical DB). Phase 2 adds it.
2. **Premium z-score needs statistics** — calculated within single chain, not across history. OK for MVP.
3. **No max pain / GEX** — these are Phase 2 features.

## Success Metrics
- ~10-20 alerts/day (manageable, not spam)
- < 10% false positive rate
- PM2 stable, < 5 restarts/day

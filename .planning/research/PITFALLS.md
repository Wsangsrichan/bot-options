# PITFALLS.md — Risks, Gotchas & Pre-Mortem

## 1. Data Costs — The Hidden Killer

**Risk:** Options data is expensive. A naive "fetch everything" approach burns $500+/mo.

**Mitigation:**
- Start with Polygon $29/mo tier (15-min delayed, enough for swing analysis)
- Only upgrade to $79/mo real-time when Phase 2 scanner demands it
- ThetaData at $20/mo is sufficient for unusual flow
- **Cap:** Hard budget limit of $150/mo for all data APIs combined
- Cache aggressively — same chain doesn't need fetching more than once per 5 min

---

## 2. Black-Scholes Limitations

**The model assumes:**
1. European-style exercise (American options can be exercised anytime — SPY options ARE American)
2. No dividends (ETFs pay dividends — affects put-call parity)
3. Constant volatility (reality: volatility surface is dynamic)
4. Continuous trading (reality: gaps at open, circuit breakers)
5. No transaction costs (reality: bid-ask spread matters)
6. Constant risk-free rate (reality: rates change)

**Mitigation:**
- For short-dated (<1 week) options, Black-Scholes works well enough
- Use binomial tree model (Cox-Ross-Rubinstein) for American-style adjustment
- Account for dividend dates in calculations
- **Don't over-rely on exact Greek values** — use them directionally

---

## 3. Latency Requirements

| Use Case | Max Acceptable Delay | Data Tier Needed |
|----------|---------------------|-----------------|
| Swing/positional analysis (3-30 DTE) | 15 minutes | Polygon Basic ($29) |
| Day trade signals (0-3 DTE) | 1 minute | Polygon RT ($79) |
| 0DTE scalping | <5 seconds | Not feasible at current budget |

**Recommendation:** Focus on 7-45 DTE for Phase 1-2. Avoid 0DTE entirely.

---

## 4. Brokerage Integration Complexity

**Challenges:**
- Tradier OAuth flow needs browser interaction (callback URL)
- Multi-leg orders (spreads) have complex routing
- Order state machine: placed → live → partially_filled → filled → cancelled → rejected
- Rate limits on order placement (varies by broker)

**Decision:** Phase 4 only. Keep bot as **analysis tool** not execution engine for now.

---

## 5. Regulatory CYA

**Required disclaimers:**
- "Not financial advice"
- "For educational purposes only"
- "Past performance does not guarantee future results"
- No personalized recommendations (no user-specific advice)

**Hard rules:**
- Never claim guaranteed returns
- Never use absolute language ("will go up")
- Attribution: make clear decisions come from AI analysis, not certified advisors

---

## 6. Data Quality Edge Cases

| Problem | Detection | Mitigation |
|---------|-----------|------------|
| Stale quotes (no recent trade) | bid=0 or ask=0 | Use mid-market, flag as low-confidence |
| Deep ITM/OTM with zero volume | OI=0, volume=0 | Filter from analysis |
| Adjusted options (splits, mergers) | Root symbol mismatch | Validate against Polygon reference data |
| Pre/post-market quotes | Timestamp check | Only analyze during 09:30-16:00 EST |

---

## 7. False Positive Sources

| False Signal | Likely Cause | Filter |
|-------------|-------------|--------|
| Large put buy + large call buy | Hedge unwind or spread leg | Check if volume appears on BOTH sides |
| Huge premium, low contracts | 1 deep ITM trade | Filter by contract count (>50 contracts) |
| Volume spike on expiration day | Rolling positions | Ignore 0DTE unless specifically tracking |
| Ask-side flow but no follow-through | Dealer inventory adjustment | Require consecutive alerts before flagging |

---

## 8. Operational Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Polygon API down | No data → no signals | Circuit breaker: halt scanning, alert admin |
| TimescaleDB disk full | Data loss | 90-day retention policy, monitoring |
| Market holiday (no trading) | Empty chains → false alerts | Market calendar check before scanning |
| DeepSeek API rate limit | AI enrichment unavailable | Fallback to quantitative-only scoring |
| PM2 restart loop | Duplicate alerts | Dedup via Redis key (ticker+signal+timestamp) |

---

## 9. LLM Hallucination Risks

**Risk:** AI might invent news events, misinterpret flow, or give overconfident predictions.

**Mitigation:**
- **Structured output only** — use `instructor` library to force JSON schema
- **Validate before alert** — confirm AI claims against actual data
- **Confidence calibration** — track AI accuracy over time, adjust thresholds
- **Disclaimers** — every AI-enriched alert includes "AI-generated analysis, verify independently"

---

## 10. Pre-Mortem: Why This Project Could Fail

1. **API costs exceed budget** → mitigation: hard $150/mo cap, start small
2. **Signal quality poor** → mitigation: backtesting framework before scaling
3. **Black-Scholes inaccuracies cause bad entries** → mitigation: use directionally, not precisely
4. **Scope creep** (too many tickers, strategies) → mitigation: strict phase gates
5. **Abandoned after MVP** → mitigation: each phase delivers standalone value
6. **Data overload** (too many alerts, ignored) → mitigation: aggressive dedup + cooldown
7. **Regulatory scare** → mitigation: disclaimers, no auto-execution, human gate

---

## Key Takeaway

> **Start with 1 ticker, 1 signal, 1 alert. Prove value. Then scale.**
>
> The biggest risk is building a complex system that produces noise instead of signal.

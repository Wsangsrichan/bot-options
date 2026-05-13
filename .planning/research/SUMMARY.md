# SUMMARY.md — US Options/ETF Domain Overview

## What is Options Trading?

Options are derivatives that give the buyer the right (not obligation) to buy/sell an underlying asset at a specific price (strike) by a specific date (expiration).

- **Call:** Right to BUY the underlying → bullish bet
- **Put:** Right to SELL the underlying → bearish bet
- **Premium:** Price paid for the option (determined by Black-Scholes model)
- **Strike Price:** Price at which the option can be exercised
- **Expiration:** Date when the option ceases to exist

## The Greeks (Risk Sensitivities)

| Greek | Meaning | Practical Use |
|-------|---------|---------------|
| **Delta** (Δ) | Rate of change vs underlying price | Probability of expiring ITM (roughly). 0.50 delta ≈ 50% chance. |
| **Gamma** (Γ) | Rate of change of Delta | How fast Delta changes. High near expiration = unstable positions. |
| **Theta** (Θ) | Time decay | Daily value erosion. Negative for buyers, positive for sellers. Accelerates last 30 days. |
| **Vega** (ν) | Sensitivity to IV changes | How much premium changes per 1% IV move. Higher for longer DTE. |
| **Rho** (ρ) | Sensitivity to interest rates | Least important for short-term trading. |

## Implied Volatility (IV) — The Edge Variable

IV is the market's expectation of future volatility, derived from option prices via Black-Scholes. **This is where edge lives.**

- **IV Rank:** Where current IV sits in its 52-week range (0-100). >50 = expensive options.
- **IV Percentile:** % of days IV was lower than current. >70% = unusually high IV.
- **IV Skew:** Difference between OTM put and call IV. High skew = fear premium.
- **Term Structure:** IV across different expirations. Contango (further > nearer) = normal. Backwardation = event risk.

## ETF Options — The Focus

| ETF | Underlying | Weekly Options | Avg Volume | Notes |
|-----|-----------|----------------|------------|-------|
| **SPY** | S&P 500 | ✅ | 8M+/day | Most liquid options in the world |
| **QQQ** | Nasdaq-100 | ✅ | 3M+/day | Tech-heavy, higher IV |
| **IWM** | Russell 2000 | ✅ | 2M+/day | Small caps, different behavior |
| **DIA** | Dow Jones 30 | ✅ | 500K/day | Less volatile, lower IV |
| **TLT** | 20+ Year Treasuries | ✅ | 400K/day | Rate-sensitive, bond proxy |
| **GLD** | Gold | ✅ | 200K/day | Commodity, inflation hedge |
| **VIX** | Volatility Index | ✅ | Special | Term structure trading |

ETFs are preferred over individual stocks because:
1. No earnings surprises
2. More predictable IV patterns
3. Deep liquidity
4. Broad market exposure

## Key Signals for Entry Detection

| Signal | What It Measures | Bullish When | Bearish When |
|--------|-----------------|-------------|--------------|
| **Unusual Options Flow** | Large premium trades vs average | Heavy call buying, ask-side | Heavy put buying, ask-side |
| **IV Rank** | Current IV vs 52-week range | IV rank low (options cheap) | IV rank high (options expensive) |
| **Volume/OI Ratio** | Today's volume vs open interest | >1.0 = fresh interest in that strike | <0.3 = stale, old positions |
| **Max Pain** | Strike where most options expire worthless | Price below max pain (magnet up) | Price above max pain (magnet down) |
| **Gamma Exposure (GEX)** | Market maker hedging impact | Positive GEX = stabilizing | Negative GEX = amplifying moves |
| **Put/Call Ratio** | Bearish vs bullish sentiment | Extreme fear (contrarian) >1.2 | Extreme greed <0.5 |
| **Dark Pool Prints** | Institutional block trades | Large buy prints | Large sell prints |

## Common Strategies

| Strategy | When to Use | Max Profit | Max Loss |
|----------|------------|------------|----------|
| Long Call | Bullish, low IV | Unlimited | Premium paid |
| Long Put | Bearish, low IV | Strike - premium | Premium paid |
| Covered Call | Neutral-bullish, high IV | Premium + upside to strike | Stock cost - premium |
| Cash-Secured Put | Want to buy cheaper, high IV | Premium | Strike - premium |
| Bull Put Spread | Mildly bullish, high IV | Net credit | Spread width - credit |
| Iron Condor | Range-bound, high IV | Net credit | Spread width - credit |

**For this bot:** Phase 1 focuses on **signal detection only** (finding opportunities). Trade execution is Phase 4 with mandatory human gate.

## Phase Structure Recommendation

```
Phase 1: MVP (2 weeks)     → Single ticker data + Greeks + alerts
Phase 2: Scanner (3 weeks) → Multi-ticker + scoring + storage
Phase 3: AI (2 weeks)      → LLM interpretation + news context
Phase 4: Execution (TBD)   → Brokerage + human gate
```

**Why this order:** Prove the data pipeline works on 1 ticker → scale to many → add AI intelligence → optional execution.

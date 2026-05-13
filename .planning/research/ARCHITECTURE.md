# ARCHITECTURE.md — System Design

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Telegram User (Haocomm)                  │
│                         ↑↓ alerts                            │
└──────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│                      Alert Manager                           │
│              (dedup, cooldown, priority routing)             │
└─────────────────────────────▲────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│                    Opportunity Scorer                        │
│       Composite score: IV Rank + Flow + Greeks + News        │
└──────▲──────────────▲──────────────▲──────────────▲──────────┘
       │              │              │              │
┌──────┴──────┐ ┌─────┴─────┐ ┌──────┴──────┐ ┌─────┴──────────┐
│ Options     │ │ Flow      │ │ Greeks      │ │ AI Interpreter │
│ Chain Poller│ │ Detector  │ │ Calculator  │ │ (DeepSeek)     │
│ (Polygon)   │ │ (ThetaData│ │ (py_vollib) │ │ + News RSS     │
└──────┬──────┘ └─────┬─────┘ └──────┬──────┘ └─────┬──────────┘
       │              │              │              │
┌──────┴──────────────┴──────────────┴──────────────┴──────────┐
│                  PostgreSQL + TimescaleDB                    │
│         chains | greeks | flow_alerts | opportunity_log      │
└──────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Data Ingestion Pipeline

```
Polygon REST (poll every 5 min / ticker)
    │
    ├─→ GET /v3/snapshot/options/{ticker}
    │   Returns: full chain, IV, Greeks, volume, OI
    │
    ├─→ Parse → normalize → store in TimescaleDB
    │
    └─→ Trigger: chain_updated event

ThetaData REST (poll every 2 min for unusual flow)
    │
    ├─→ GET /v2/bulk_hist/option/flow
    │   Returns: premium >$100K trades, ask/bid side
    │
    └─→ Trigger: unusual_flow event
```

### 2. Options Calculator (`src/calculator.py`)

```python
from py_vollib.black_scholes import black_scholes
from py_vollib.black_scholes.greeks.analytical import delta, gamma, theta, vega, rho

class OptionsCalculator:
    def compute_greeks(self, option_type, S, K, T, r, sigma):
        """Compute all Greeks for a single option"""
        ...

    def solve_iv(self, market_price, option_type, S, K, T, r):
        """Newton-Raphson IV solver — find sigma that matches market price"""
        ...

    def compute_iv_rank(self, ticker, current_iv):
        """IV Rank = percentile of current IV in 52-week history"""
        ...

    def compute_max_pain(self, chain):
        """Strike where total option value (calls+puts) is minimized"""
        ...

    def compute_gex(self, chain):
        """Gamma Exposure: Σ gamma × OI × spot × 100 per strike"""
        ...
```

### 3. Opportunity Scorer (`src/scorer.py`)

**Composite Score Formula:**

```
Score = W1 × IV_Rank_Signal + W2 × Flow_Signal + W3 × Greek_Signal + W4 × Tech_Signal

Where:
- W1=0.30, W2=0.35, W3=0.20, W4=0.15 (Phase 2 calibrates weights)
- IV_Rank_Signal = normalized IV Rank (0-100 → 0-1)
- Flow_Signal = premium_zscore + volume_oi_ratio_zscore
- Greek_Signal = gamma_ramp + delta_divergence
- Tech_Signal = price vs max pain + GEX alignment
```

**Thresholds:**
- Score > 0.65 → HIGH priority alert
- Score 0.45-0.65 → MEDIUM (AI reviews)
- Score < 0.45 → Log only

### 4. Alert Manager (`src/alerts.py`)

```
Rules:
1. Dedup: Same ticker + same signal type → cooldown 30 min
2. Priority: HIGH → immediate Telegram; MEDIUM → batch every 15 min
3. AI Enrichment: HIGH alerts trigger DeepSeek analysis automatically
4. Queue: Redis-backed to prevent duplicate processing
```

### 5. AI Analysis Module (`src/ai_interpreter.py`)

```python
import instructor
from openai import OpenAI

class AIInterpreter:
    def analyze_opportunity(self, options_data, news_snippets):
        """Send structured options data + news to DeepSeek"""
        prompt = f"""
        Options chain for {ticker}:
        - IV Rank: {iv_rank}%
        - Unusual flow: {flow_summary}
        - Greeks alignment: {greeks_summary}
        - Recent news: {news}

        Analyze this as an options trading opportunity.
        Return JSON with: signal_type, confidence (0-1), reasoning, risk_factors
        """
        return client.chat.completions.create(
            model="deepseek-chat",
            response_model=OptionsSignal,
            messages=[{"role": "user", "content": prompt}]
        )
```

### 6. Database Schema

```sql
-- TimescaleDB hypertables
CREATE TABLE option_chains (
    time TIMESTAMPTZ NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    expiration DATE NOT NULL,
    strike DECIMAL(10,2) NOT NULL,
    option_type CHAR(1),  -- 'C' or 'P'
    bid DECIMAL(10,4),
    ask DECIMAL(10,4),
    last DECIMAL(10,4),
    volume INT,
    open_interest INT,
    delta DECIMAL(8,6),
    gamma DECIMAL(8,6),
    theta DECIMAL(8,6),
    vega DECIMAL(8,6),
    implied_volatility DECIMAL(8,6)
);
SELECT create_hypertable('option_chains', 'time');

CREATE TABLE flow_alerts (
    time TIMESTAMPTZ NOT NULL,
    ticker VARCHAR(10),
    premium DECIMAL(12,2),
    contracts INT,
    side VARCHAR(10),  -- 'ask' (bought) or 'bid' (sold)
    strike DECIMAL(10,2),
    expiration DATE
);
SELECT create_hypertable('flow_alerts', 'time');

CREATE TABLE opportunity_log (
    id SERIAL PRIMARY KEY,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    ticker VARCHAR(10),
    score DECIMAL(4,3),
    iv_rank DECIMAL(5,2),
    flow_zscore DECIMAL(5,2),
    signal_type VARCHAR(20),
    ai_confidence DECIMAL(4,3),
    ai_reasoning TEXT,
    alert_sent BOOLEAN DEFAULT FALSE,
    outcome_verified BOOLEAN DEFAULT FALSE
);
```

---

## Deployment (Docker Compose)

```yaml
# docker-compose.yml
services:
  bot:
    build: .
    environment:
      - POLYGON_API_KEY=${POLYGON_API_KEY}
      - THETADATA_API_KEY=${THETADATA_API_KEY}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
      - DATABASE_URL=postgresql://bot:pass@db:5432/options
    depends_on: [db, redis]
    restart: unless-stopped

  db:
    image: timescale/timescaledb:latest-pg16
    environment:
      - POSTGRES_USER=bot
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=options
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

volumes:
  pgdata:
```

---

## Data Flow During Market Hours

```
09:30 EST (Market Open)
  │
  ├─ Every 5 min: Polygon poll → chain snapshot → compute Greeks → store
  ├─ Every 2 min: ThetaData poll → flow alerts → flag unusual
  ├─ Every 15 min: Score all tickers → rank → alert if > threshold
  ├─ Every 30 min: AI batch review of MEDIUM signals
  │
16:00 EST (Market Close)
  │
  └─ Daily summary: Top signals, PnL tracking, DB cleanup (retention: 90 days)
```

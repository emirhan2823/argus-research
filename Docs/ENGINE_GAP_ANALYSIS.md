# ARGUS Engine Gap Analysis

**Legacy Engines (US/BIST) vs Crypto Implementation**

| Date | 2026-02-07 |
|------|------------|
| Status | ANALYSIS COMPLETE |
| Action Required | Plan crypto adaptation of missing engines |

---

## Executive Summary

ArgusTrailerPrompts 2 contains **7 specialized engines** designed for US equities and BIST markets. Our current crypto implementation has **partial coverage**. This document maps what exists vs what's missing and proposes a crypto adaptation plan.

---

## 1. Engine Inventory

### Legacy Engines (SwiftUI / US & BIST)

| # | Engine | Purpose | Data Sources | Output |
|---|--------|---------|--------------|--------|
| 1 | **ATLAS** | Fundamental Analysis | FMP API (P/E, ROE, Debt) | Score 0-100, A-F Grade |
| 2 | **ORION** | Technical Analysis | Candles (RSI, MACD, SMA, Bollinger) | Score 0-100, BUY/HOLD/SELL |
| 3 | **AETHER** | Macro Environment | FRED API + Yahoo (VIX, CPI, DXY) | Risk On/Off/Neutral |
| 4 | **HERMES** | News Sentiment | RSS + Groq AI | Positive/Negative/Neutral |
| 5 | **PHOENIX** | Strategy Aggregation | All 4 engines | Weighted signal + target price |
| 6 | **COUNCIL** | Voting Mechanism | All 4 engines | Net Support (-1 to +1) |
| 7 | **CHIRON** | Machine Learning | Historical trades | Optimized weights |

### Crypto Engines (Python / argus_py)

| # | Engine | Purpose | Data Sources | Output |
|---|--------|---------|--------------|--------|
| 1 | **Aegean** | Momentum/Position | EMA(20), Donchian Channel | Vote (LONG/SHORT/FLAT) |
| 2 | **Orion** | Trend Confirmation | ADX(14), SMA(50) | Vote (LONG/SHORT/FLAT) |
| 3 | **Council** | Voting Aggregation | Aegean + Orion | ConsensusVerdict (GO/NO_GO) |

---

## 2. Gap Analysis

| Engine | Legacy | Crypto | Gap | Priority |
|--------|--------|--------|-----|----------|
| **ORION** | ✅ Full (RSI, MACD, SMA, Bollinger, ATR, Stoch) | ⚠️ Partial (ADX, SMA only) | Missing RSI, MACD, Bollinger patterns | HIGH |
| **ATLAS** | ✅ Fundamental (FMP) | ❌ None | N/A for crypto (no P/E) | ADAPT |
| **AETHER** | ✅ Macro (FRED, VIX) | ❌ None | Need crypto-native macro | HIGH |
| **HERMES** | ✅ News AI (RSS, Groq) | ❌ None | Apply same architecture | MEDIUM |
| **PHOENIX** | ✅ Aggregator | ❌ None | Build after engines exist | LOW |
| **COUNCIL** | ✅ Weighted Voting | ✅ Exists | Different formula | OK |
| **CHIRON** | ✅ ML Learning | ❌ None | Needs trade history | PHASE 2 |

---

## 3. Detailed Comparison

### 3.1 ORION (Technical Analysis)

**Legacy (SwiftUI):**
```
Indicators: RSI(14), MACD(12,26,9), SMA(50,200), EMA(12,26)
            Bollinger(20,2), ATR(14), Stochastic(14)
Categories: Structure (35%), Trend (25%), Momentum (25%), Pattern (15%)
Output: Score 0-100, GÜÇLÜ AL / AL / TUT / SAT / GÜÇLÜ SAT
```

**Crypto (Python):**
```
Indicators: ADX(14), SMA(50)
Categories: Trend strength only
Output: Vote with confidence 0-1
```

**Gap:** Missing 5+ indicators, pattern detection, multi-category scoring

---

### 3.2 ATLAS (Fundamental) → CRYPTO ADAPTATION NEEDED

**Legacy Purpose:** Analyze company financials (P/E, ROE, Debt/Equity)

**Crypto Equivalent - "ATLAS-C" (On-Chain Fundamentals):**

| Legacy Metric | Crypto Equivalent | Data Source |
|---------------|-------------------|-------------|
| P/E Ratio | Market Cap / On-chain Revenue | DefiLlama, Token Terminal |
| ROE | Protocol Revenue / TVL | DefiLlama |
| Gross Margin | Protocol Revenue / Emissions | Token Terminal |
| Debt Ratio | - | N/A |
| Growth Rate | TVL Growth, Volume Growth | DefiLlama |

**Crypto Metrics to Add:**
- **NVT Ratio** (Market Cap / Transaction Volume)
- **MVRV Ratio** (Market Cap / Realized Cap)
- **Active Addresses** (Network activity)
- **Exchange Reserve** (Supply on exchanges)
- **Funding Rate** (Perpetual futures sentiment)

---

### 3.3 AETHER (Macro) → CRYPTO ADAPTATION NEEDED

**Legacy Sources:**
- FRED API: CPI, Unemployment, Fed Funds Rate
- Yahoo: VIX, SPY, GLD, BTC, DXY

**Crypto Equivalent - "AETHER-C" (Crypto Macro):**

| Category | Legacy | Crypto Equivalent |
|----------|--------|-------------------|
| **Risk Indicator** | VIX | Crypto Fear & Greed Index |
| **Monetary Policy** | Fed Funds Rate | Stablecoin Supply Change |
| **Inflation Proxy** | CPI | Bitcoin Dominance |
| **Risk Asset Momentum** | SPY | Total Crypto Market Cap |
| **Safe Haven** | GLD | USDT Dominance |
| **Currency Strength** | DXY | DXY (same) |
| **Leading Indicator** | Initial Claims | Whale Wallet Movement |

**API Sources:**
- Alternative.me (Fear & Greed)
- CoinGecko (Market Cap, Dominance)
- Glassnode / CryptoQuant (On-chain)

---

### 3.4 HERMES (News Sentiment) → DIRECT ADAPTATION

**Legacy Architecture:**
1. RSS feeds (Yahoo Finance)
2. Groq AI sentiment analysis
3. Score aggregation

**Crypto Adaptation:**
- **RSS Sources:** CoinDesk, CoinTelegraph, Decrypt, The Block
- **AI Model:** Same Groq/Llama integration
- **Keywords:** Add crypto-specific terms (halving, ETF, regulation, hack)

---

### 3.5 PHOENIX (Strategy) → BUILD AFTER ENGINES

**Formula:**
```
Signal = Σ(Engine Score × Weight) / 100

Default Weights:
- Technical (Orion): 40%
- Fundamental (Atlas): 30%  
- Macro (Aether): 20%
- Sentiment (Hermes): 10%
```

**Crypto Weights (Proposed):**
```
- Technical (Orion-C): 45%  # Price action dominates crypto
- On-Chain (Atlas-C): 25%  # Fundamentals matter less
- Macro (Aether-C): 20%    # Macro cycles important
- Sentiment (Hermes-C): 10%
```

---

### 3.6 CHIRON (Learning) → PHASE 2

**Requires:** 
- 50+ completed trades with outcomes
- Telemetry: decision, entry, exit, actual return

**Current State:** Telemetry exists (decisions.csv, trades.csv) but no learning loop

---

## 4. Implementation Roadmap

### Phase 1: Enhance Orion (Week 3-4)

```
Task: Add missing indicators to OrionEngine

Files:
- argus_py/models/orion/orion.py
- argus_py/models/orion/indicators.py (NEW)

Indicators to Add:
1. RSI(14) with overbought/oversold signals
2. MACD(12,26,9) with crossover detection
3. Bollinger Bands(20,2) with squeeze detection
4. Stochastic(14,3) with divergence

Estimated: 4-6 hours
```

### Phase 2: Aether-C Crypto Macro (Week 5-6)

```
Task: Build crypto macro regime detector

Files:
- argus_py/models/aether/__init__.py (NEW)
- argus_py/models/aether/aether.py (NEW)
- argus_py/models/aether/data_sources.py (NEW)

Data Sources:
1. Fear & Greed API (Alternative.me)
2. Market Cap + Dominance (CoinGecko)
3. DXY (Yahoo Finance - same as legacy)
4. Funding Rates (Binance/BingX API)

Output: MacroRegime (RISK_ON / RISK_OFF / NEUTRAL)

Estimated: 6-8 hours
```

### Phase 3: Hermes-C News Sentiment (Week 7-8)

```
Task: Port RSS + AI sentiment to crypto

Files:
- argus_py/models/hermes/__init__.py (NEW)
- argus_py/models/hermes/hermes.py (NEW)
- argus_py/models/hermes/rss_reader.py (NEW)
- argus_py/models/hermes/groq_client.py (NEW)

RSS Sources:
- https://feeds.feedburner.com/CoinDesk
- https://cointelegraph.com/rss

Estimated: 4-6 hours
```

### Phase 4: Atlas-C On-Chain (Week 9-10)

```
Task: Build on-chain fundamental analysis

Files:
- argus_py/models/atlas/__init__.py (NEW)
- argus_py/models/atlas/atlas.py (NEW)
- argus_py/models/atlas/onchain.py (NEW)

Metrics:
1. NVT Ratio (for BTC)
2. Exchange Reserve (Glassnode)
3. Funding Rate (already available)
4. Open Interest (BingX API)

Estimated: 6-8 hours
```

### Phase 5: Phoenix Strategy Aggregator (Week 11)

```
Task: Combine all engines into unified signal

Files:
- argus_py/strategy/phoenix.py (NEW)

Formula: Weighted aggregation of all votes
Output: PhoenixSignal with confidence, target, stop

Estimated: 3-4 hours
```

### Phase 6: Chiron Learning (Week 12+)

```
Prerequisite: 50+ trades completed

Task: Implement weight optimization from trade outcomes

Files:
- argus_py/learning/chiron.py (NEW)
- argus_py/learning/weight_optimizer.py (NEW)

Estimated: 8-10 hours
```

---

## 5. API Requirements

| API | Purpose | Free Tier | Required For |
|-----|---------|-----------|--------------|
| **Alternative.me** | Fear & Greed | ✅ Unlimited | Aether-C |
| **CoinGecko** | Market Cap, Dominance | ✅ 10k/month | Aether-C |
| **Glassnode** | On-chain metrics | ⚠️ Limited | Atlas-C (optional) |
| **CryptoQuant** | Exchange reserve | ⚠️ Limited | Atlas-C (optional) |
| **Groq** | AI sentiment | ✅ Free tier | Hermes-C |

---

## 6. Hedge Fund Integration

All engines feed into the Grand Council voting mechanism:

```
┌─────────────────────────────────────────────────────────┐
│                    GRAND COUNCIL                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ ORION-C  │  │ ATLAS-C  │  │ AETHER-C │  │ HERMES-C │ │
│  │ Technical│  │ On-Chain │  │  Macro   │  │Sentiment │ │
│  │   45%    │  │   25%    │  │   20%    │  │   10%    │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │             │             │             │        │
│       └─────────────┴──────┬──────┴─────────────┘        │
│                            │                             │
│                     ┌──────▼──────┐                      │
│                     │   PHOENIX   │                      │
│                     │  Aggregator │                      │
│                     └──────┬──────┘                      │
│                            │                             │
│                     ┌──────▼──────┐                      │
│                     │   CHIRON    │                      │
│                     │  Learning   │                      │
│                     └─────────────┘                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Conclusion

| Metric | Current | After Roadmap |
|--------|---------|---------------|
| Engine Coverage | 3/7 (43%) | 7/7 (100%) |
| Signal Sources | 2 (Aegean, Orion) | 5+ |
| Data Dimensions | Price only | Price + On-chain + Macro + Sentiment |
| Learning | None | Weight optimization |

**Total Estimated Effort:** 30-40 hours over 12 weeks

**Recommendation:** Start with Phase 1 (Orion enhancement) in Week 3-4 after Kill-Switch and Telemetry modules are complete.

---

**Document Status:** READY FOR REVIEW

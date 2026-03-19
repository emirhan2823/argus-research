# ARGUS Swift Architecture Analysis

**Comprehensive Hedge Fund System Documentation**

| Field | Value |
|-------|-------|
| Date | 2026-02-07 |
| Status | ANALYSIS COMPLETE |
| Files | 306 Services, 53 Models, 175 Views |
| Total Code | ~800KB Swift |

---

## 1. Executive Summary

The Swift application is a **fully-featured hedge fund platform** with:

- **7 Analysis Engines** (Atlas, Orion, Aether, Hermes, Phoenix, Demeter, Athena)
- **Grand Council Voting System** (weighted multi-module consensus)
- **Chiron Machine Learning** (regime detection, weight optimization)
- **AutoPilot Execution** (dual-mode: Corse swing + Pulse scalp)
- **Portfolio Risk Management** (institutional-grade limits)
- **Backtesting Engine** (9 strategies, equity curves, trade logs)

---

## 2. Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                        ARGUS GRAND COUNCIL                          │
│                  (ArgusGrandCouncil.swift - 1068 lines)            │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │  ATLAS  │ │  ORION  │ │ AETHER  │ │ HERMES  │ │ PHOENIX │       │
│  │Fundamntl│ │Technical│ │  Macro  │ │  News   │ │ Channel │       │
│  │  30%    │ │  35%    │ │  20%    │ │  10%    │ │   5%    │       │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘       │
│       │          │          │          │          │                │
│  ┌────▼────┐ ┌────▼────┐ ┌────▼────────▼────────▼────┐             │
│  │ DEMETER │ │ ATHENA  │ │        CHIRON             │             │
│  │ Sector  │ │ Factor  │ │   Regime + Learning       │             │
│  └─────────┘ └─────────┘ └────────────┬──────────────┘             │
│                                       │                             │
│                          ┌────────────▼────────────┐               │
│                          │   ArgusDecisionEngine   │               │
│                          │   (867 lines, 6 modules)│               │
│                          └────────────┬────────────┘               │
│                                       │                             │
│                          ┌────────────▼────────────┐               │
│                          │  ArgusAutoPilotEngine   │               │
│                          │  (702 lines, 2 modes)   │               │
│                          └────────────┬────────────┘               │
│                                       │                             │
│                          ┌────────────▼────────────┐               │
│                          │   Portfolio + Broker    │               │
│                          └─────────────────────────┘               │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Engines Detail

### 3.1 ATLAS (Fundamental Analysis)

| File | Lines | Purpose |
|------|-------|---------|
| `AtlasCouncil.swift` | 180 | Fundamental voting |
| `AtlasCouncilMembers.swift` | 600 | 8 specialist voters |
| `AtlasBistEngine.swift` | 150 | BIST adaptation |
| `FundamentalScoreEngine.swift` | 600 | P/E, ROE, Debt scoring |
| `BISTBilancoEngine.swift` | 800 | Turkish balance sheet |

**Metrics:**
- Profitability (ROE, Net Margin)
- Valuation (P/E, P/B, EV/EBITDA)
- Debt (Debt/Equity, Interest Coverage)
- Growth (Revenue, Earnings)
- Dividend Yield

---

### 3.2 ORION (Technical Analysis)

| File | Lines | Purpose |
|------|-------|---------|
| `OrionCouncil.swift` | 250 | Technical voting |
| `OrionAnalysisService.swift` | 600 | Full indicator suite |
| `TechnicalAnalysisEngine.swift` | 600 | Math calculations |
| `IndicatorService.swift` | 150 | API wrapper |
| `ChartPatternEngine.swift` | 400 | Pattern detection |

**Indicators:**
- Trend: SMA(50/200), EMA(12/26), ADX
- Momentum: RSI(14), MACD(12,26,9), Stochastic, CCI
- Volatility: Bollinger(20,2), ATR(14)
- Structure: Donchian Channel, Ichimoku
- Advanced: Williams%R, Aroon, TSI, Parabolic SAR

**Scoring Categories:**
```
Structure: 35% (Price position vs MAs, Ichimoku)
Trend:     25% (ADX strength, EMA alignment)
Momentum:  25% (RSI, MACD crossover, Stoch)
Pattern:   15% (Divergence, Candlestick)
```

---

### 3.3 AETHER (Macro Environment)

| File | Lines | Purpose |
|------|-------|---------|
| `MacroRegimeService.swift` | 810 | FRED + Yahoo data |
| `AetherCouncil.swift` | 160 | Macro voting |
| `SirkiyeEngine.swift` | 500 | BIST flow analysis |

**Data Sources (11 components):**
```
FRED API:
- CPI (Inflation)
- Unemployment
- Fed Funds Rate
- Initial Claims
- Credit Spreads (HY vs IG)

Yahoo Finance:
- VIX (Volatility)
- SPY (Equity Trend)
- GLD (Safe Haven)
- BTC (Risk Appetite)
- DXY (Dollar Strength)
- HYG/LQD (Credit)
```

**Output:**
- `MacroRegime`: RISK_ON / RISK_OFF / NEUTRAL
- Component scores 0-100
- Staleness penalty for old data

---

### 3.4 HERMES (News + Sentiment)

| File | Lines | Purpose |
|------|-------|---------|
| `HermesCouncil.swift` | 170 | Sentiment voting |
| `HermesLLMService.swift` | 350 | Groq AI integration |
| `RSSNewsProvider.swift` | 190 | Multi-source RSS |
| `GeminiNewsService.swift` | 300 | Google AI backup |

**RSS Sources:**
```swift
"BIST_MIX": [
    ("Bloomberg HT", "https://www.bloomberght.com/rss"),
    ("Investing TR", "https://tr.investing.com/rss/news_25.rss"),
    // 15+ more...
],
"CRYPTO": [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CoinTelegraph TR", "https://tr.cointelegraph.com/rss")
]
```

**AI Pipeline:**
1. Fetch RSS headlines
2. Send to Groq (Llama 3.1)
3. Extract sentiment + confidence
4. Aggregate across sources

---

### 3.5 PHOENIX (Channel Reversion)

| File | Lines | Purpose |
|------|-------|---------|
| `PhoenixLogic.swift` | 313 | Pure functional logic |
| `PhoenixScenarioEngine.swift` | 150 | Scenario generation |

**Strategy:**
```
Linear Regression Channel Reversion
- Calculate regression channel (slope, intercept, sigma)
- Entry: Price touches lower band + RSI reversal + Bullish divergence
- Exit: Price reaches mid-band (T1) or upper band (T2)
- R-squared filter for channel validity
```

**Scoring:**
```swift
if touchLowerBand { score += 20 }
if rsiReversal { score += 15 }
if divergence { score += 15 }
if currentRSI < 35 { score += 10 }  // Deeply oversold
if trendOk { score += 5 }
```

---

### 3.6 DEMETER (Sector Analysis)

Purpose: Sector rotation and flow analysis
- BIST: Money flow between sectors
- US: Sector ETF momentum

---

### 3.7 ATHENA (Factor Model)

| File | Lines | Purpose |
|------|-------|---------|
| `AthenaFactorService.swift` | 300 | Multi-factor scoring |
| `AthenaInferenceEngine.swift` | 100 | ML inference |

**Factors:**
- Value (P/E, P/B)
- Momentum (12-month return)
- Quality (ROE, debt)
- Size (Market cap)
- Volatility (Beta)

---

## 4. Grand Council Voting

### 4.1 Vote Flow

```swift
// ArgusGrandCouncil.swift
actor ArgusGrandCouncil {
    func convene(
        symbol: String,
        candles: [Candle],
        financials: FinancialsData?,
        macro: MacroEnvironmentRating?,
        news: NewsInsight?
    ) async -> ArgusGrandDecision
}
```

### 4.2 Action Types

```swift
enum ArgusAction {
    case aggressiveBuy = "HÜCUM"      // Strong Buy
    case accumulate = "BİRİKTİR"     // Gradual Buy
    case hold = "TUT"                 // Wait
    case trim = "AZALT"              // Partial Sell
    case liquidate = "TASFİYE"       // Full Exit
}
```

### 4.3 Weight Dynamics (Chiron)

```swift
// ChironRegimeEngine.swift
func getBaseWeights(for regime: MarketRegime) -> (core: ModuleWeights, pulse: ModuleWeights) {
    switch regime {
    case .trend:
        // Orion dominates in trends
        return (core: ModuleWeights(atlas: 0.25, orion: 0.35, aether: 0.15...))
    case .chop:
        // Reduce all weights in choppy markets
        return (core: ModuleWeights(atlas: 0.20, orion: 0.20, aether: 0.25...))
    case .riskOff:
        // Atlas + Aether dominate, ignore momentum
        return (core: ModuleWeights(atlas: 0.35, orion: 0.05, aether: 0.30...))
    }
}
```

---

## 5. AutoPilot Execution

### 5.1 Dual Strategy Modes

| Mode | Purpose | Holding Period | Stop Loss |
|------|---------|----------------|-----------|
| **CORSE** | Swing trading | Days-weeks | -8% |
| **PULSE** | Scalping | Hours-days | -5% |

### 5.2 Position Management

```swift
// The Harvester (Exit Logic)
if pnlPercent < stopLimit { SELL 100% }
if pnlPercent > 20 { TRIM 30% }
if pnlPercent > 5 && drawdown > 2.5% { TRAILING STOP }
if score < 55 && losing { CUT LOSSES }
```

### 5.3 Entry Logic

```swift
// The Hunter (Entry Logic)
if score > 65 && cashAvailable && !cooldown { BUY }
if score > 75 { AGGRESSIVE BUY (larger size) }
```

---

## 6. Risk Management

### 6.1 Portfolio Limits

```swift
struct RiskLimits {
    var minCashRatio: Double = 0.20          // Min 20% cash
    var maxOpenPositions: Int = 15           // Max 15 positions
    var maxPositionWeight: Double = 0.20     // Max 20% per stock
    var maxSectorWeight: Double = 0.40       // Max 40% per sector
    var minPositionSize: Double = 100.0      // Min $100
    var maxDailyTrades: Int = 20             // Max 20 trades/day
}
```

### 6.2 Pre-Trade Checks

1. Cash ratio after trade
2. Position count limit
3. Single position weight
4. Sector concentration
5. Daily trade count
6. Cooldown period

---

## 7. Backtesting Engine

### 7.1 Strategies Available

```swift
enum BacktestStrategy {
    case buyAndHold
    case rsiMeanReversion
    case goldenCross
    case bollingerBreakout
    case sarTrend
    case argusStandard
    case aggressive
    case conservative
    case orionV2
}
```

### 7.2 Output

```swift
struct BacktestResult {
    let trades: [BacktestTrade]
    let equityCurve: [EquityPoint]
    let totalReturn: Double
    let sharpeRatio: Double
    let maxDrawdown: Double
    let winRate: Double
    let profitFactor: Double
}
```

---

## 8. Python Port Roadmap

### Phase 1: Core Engines (Week 3-4)
- [ ] Enhance `orion.py` with full indicator suite
- [ ] Add RSI, MACD, Bollinger, Stochastic
- [ ] Port multi-category scoring

### Phase 2: Macro (Week 5-6)
- [ ] Create `aether.py` with Fear & Greed API
- [ ] Add crypto-native macro indicators
- [ ] Implement regime detection

### Phase 3: Sentiment (Week 7-8)
- [ ] Port RSS aggregation
- [ ] Integrate Groq for sentiment
- [ ] Create crypto news sources

### Phase 4: Council (Week 9-10)
- [ ] Port weighted voting logic
- [ ] Implement Chiron learning
- [ ] Add regime-based weight adjustment

### Phase 5: AutoPilot (Week 11-12)
- [ ] Port execution logic
- [ ] Implement position management
- [ ] Add risk limits

---

## 9. Key Files Reference

| Category | File | Lines | Priority |
|----------|------|-------|----------|
| **Decision** | `ArgusDecisionEngine.swift` | 867 | P1 |
| **Council** | `ArgusGrandCouncil.swift` | 1068 | P1 |
| **Execution** | `ArgusAutoPilotEngine.swift` | 702 | P2 |
| **Regime** | `ChironRegimeEngine.swift` | 725 | P2 |
| **Backtest** | `ArgusBacktestEngine.swift` | 508 | P2 |
| **Technical** | `TechnicalAnalysisEngine.swift` | 600 | P1 |
| **Macro** | `MacroRegimeService.swift` | 810 | P2 |
| **Risk** | `PortfolioRiskManager.swift` | 299 | P3 |
| **Phoenix** | `PhoenixLogic.swift` | 313 | P3 |

---

## 10. Conclusion

This is a **production-grade hedge fund system** with:

| Metric | Value |
|--------|-------|
| Total Swift Files | 400+ |
| Total Lines | 50,000+ |
| Engines | 7 |
| Indicators | 15+ |
| Data Sources | 20+ |
| Strategies | 9 |

**Recommendation:** Port in phases, starting with Orion enhancement and Council voting system. The Swift codebase provides complete reference implementations for every component.

---

**Document Status:** READY FOR PYTHON PORT PLANNING

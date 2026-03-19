# ARGUS Year 2+ Execution Plan

**Status:** AUTHORITATIVE  
**Created:** 2026-02-10  
**Prerequisite:** CONSTITUTION_V2.md (Year 1 = Phases 1-5, crypto mode, $100 → live)  
**Scope:** Year 2-4 expansion: stocks mode, multi-asset, capital scaling  
**Rule:** This plan activates ONLY after Year 1 Phase 5 gate is passed (live trading with proven track record).

---

## Gate: Year 1 Completion Criteria

Before ANY Year 2 work begins, ALL of the following must be true:

| # | Criterion | Measurement |
|---|-----------|-------------|
| 1 | Live trading for 90+ days | Calendar days since first live trade |
| 2 | Live Sharpe > 0.6 | Rolling 90-day Sharpe on live trades |
| 3 | Max drawdown < 8% (live) | Peak-to-trough on live equity curve |
| 4 | Kill switch never reached LOCKDOWN | RSL history log |
| 5 | 200+ live trades executed | Trade count in SQLite |
| 6 | No critical bugs in production | Incident log clean for 30 days |
| 7 | Capital > $200 | Proven ability to grow from $100 |

**If ANY criterion fails:** Do NOT start Year 2. Fix Year 1 first. The system is not ready for complexity.

---

## Sprint C: US Equities Foundation (Year 2, Month 1-3, ~120h)

### Prerequisites
- Year 1 gate passed
- Alpaca or IBKR account opened and funded
- Market data subscription active

### Deliverables

| # | Task | Hours | Acceptance Criteria |
|---|------|-------|--------------------|
| C.1 | **Stock data adapter** (Alpaca/IBKR) | 20 | OHLCV streaming for SPY, QQQ, 5 tech stocks |
| C.2 | **Stock feature engine** | 20 | Adapted features: remove crypto-native (7), add fundamental (P/E, earnings date, sector momentum) |
| C.3 | **Stock regime detector** | 15 | Rule-based regime for equities (VIX-based, breadth-based) |
| C.4 | **Council architecture** | 20 | 4-engine voting council (Technical, Fundamental, Macro, Sentiment) with bounded voting |
| C.5 | **Technical engine** (stocks) | 15 | Price/TA-based signals for equities |
| C.6 | **Fundamental engine** (stocks) | 15 | P/E ratio, earnings surprise, revenue growth signals |
| C.7 | **Stock backtest validation** | 15 | Walk-forward on 5+ years SPY/QQQ data |

**Sprint C Gate:**
- Stock pipeline produces validated features
- Council produces directional decisions on historical data
- Walk-forward Sharpe > 0 on 4/5 folds
- Regime detector correctly identifies 2020 crash, 2022 bear, 2023/24 recovery

---

## Sprint D: Multi-Asset Integration (Year 2, Month 4-6, ~100h)

### Deliverables

| # | Task | Hours | Acceptance Criteria |
|---|------|-------|--------------------|
| D.1 | **Unified portfolio manager** | 20 | Single portfolio state across crypto + stocks |
| D.2 | **Cross-asset correlation monitor** | 15 | Real-time BTC-SPY, ETH-QQQ correlation tracking |
| D.3 | **Capital allocator** | 15 | Rule-based allocation: crypto X%, stocks Y%, cash Z% |
| D.4 | **Macro engine** (stocks council) | 15 | DXY, 10Y yield, VIX, sector rotation signals |
| D.5 | **Sentiment engine** (stocks council) | 10 | CryptoPanic + financial news sentiment (simple, not NLP) |
| D.6 | **Stock paper trading** (30 days) | 15 | Council decisions in paper mode, Sharpe > 0.5 |
| D.7 | **Cross-asset risk limits** | 10 | Total exposure caps, per-asset-class limits, correlation guard |

**Sprint D Gate:**
- Unified portfolio tracks both crypto and stock positions
- Cross-asset correlation < 0.6 requirement enforced
- Paper trading shows positive Sharpe for stocks mode
- Capital allocation rules tested and documented

---

## Sprint E: BIST + Hardening (Year 2, Month 7-9, ~80h)

### Deliverables

| # | Task | Hours | Acceptance Criteria |
|---|------|-------|--------------------|
| E.1 | **BIST adapter** (IS Yatirim API) | 20 | OHLCV for XU100, THYAO, ASELS |
| E.2 | **BIST feature adaptations** | 10 | TRY-specific features, BIST trading hours |
| E.3 | **Multi-asset dashboard** | 15 | Streamlit: all asset classes, unified PnL |
| E.4 | **Performance attribution** (per asset class) | 10 | Which asset class contributes what to total Sharpe |
| E.5 | **Stress testing** (multi-asset) | 10 | Synthetic 2020-style crash across all asset classes |
| E.6 | **Live scaling crypto** ($100 → $500+) | 15 | Gradual capital increase with monitoring |

**Sprint E Gate:**
- BIST data flowing (even if not trading yet — data first)
- Multi-asset dashboard operational
- Crypto live capital > $300 (proven growth)
- Attribution shows which modes are profitable

---

## Year 3: Capital Scaling + Advanced Features (Month 13-24)

### Gate: Year 2 Completion Criteria

| # | Criterion | Measurement |
|---|-----------|-------------|
| 1 | Crypto live > 6 months | Calendar days |
| 2 | Stocks paper > 90 days | Calendar days |
| 3 | Combined Sharpe > 0.8 | Rolling 6-month |
| 4 | Capital > $1,000 | Total equity |
| 5 | No HALT/LOCKDOWN incidents in 6 months | RSL log |

### Year 3 Sprints (High-Level)

| Sprint | Focus | Hours | Key Deliverable |
|--------|-------|-------|----------------|
| F | Stocks live deployment | 80 | Live trading US equities |
| G | BIST live deployment | 60 | Live trading Turkish market |
| H | ML model upgrade | 80 | Chronos fine-tuned, LightGBM retrained on larger dataset |
| I | Options awareness (research only) | 40 | Research covered calls, put protection |
| J | Commodities research | 40 | XAUUSD, XAGUSD data pipeline (no trading yet) |

### Capital-Readiness Gates

| Capital Level | Unlocks | Risk Adjustment |
|--------------|---------|-----------------|
| < $500 | Crypto only, 2 pairs | Base risk 2% |
| $500 - $2,000 | + US equities (paper → live) | Base risk 1.5% per asset class |
| $2,000 - $10,000 | + BIST, + 3rd crypto pair | Base risk 1.5%, max leverage 2.0 |
| $10,000 - $50,000 | + Options (covered calls only) | Base risk 1%, max leverage 1.5 |
| > $50,000 | Full multi-asset | Base risk 1%, market impact monitoring |

---

## Year 4: Institutional Hardening (Month 25-36)

### Gate: Year 3 Completion Criteria

| # | Criterion | Measurement |
|---|-----------|-------------|
| 1 | Multi-asset live > 6 months | Calendar days |
| 2 | Total capital > $10,000 | Total equity |
| 3 | Combined Sharpe > 1.0 | Rolling 12-month |
| 4 | 1000+ total trades | Trade count |
| 5 | Kelly transition evaluation | SE of win rate < 3% |

### Year 4 Focus Areas

| Area | Description | Gate |
|------|-------------|------|
| **Kelly transition** | If 500+ trades per engine with SE < 3%, transition from fixed fractional to half-Kelly | Backtest Kelly vs fixed fractional, Kelly must show >20% improvement |
| **DeFi yield** | Uniswap LP, Aave lending, Lido staking | Research + backtest only, no live without 6-month paper |
| **Bond allocation** | US Treasury, TR tahvil for stability | Low-risk allocation for capital preservation |
| **Tax optimization** | Automated tax-loss harvesting | Requires legal review for TR tax law |
| **External capital** | Consider managing friend/family capital | Only if 12-month live Sharpe > 1.5 |

---

## Risk Escalation Path

As the system grows in complexity, risk management must grow with it:

| Year | Max Asset Classes | Max Positions | Max DD Kill | Review Cadence |
|------|------------------|--------------|-------------|----------------|
| 1 | 1 (crypto) | 4 | 6% | Weekly |
| 2 | 2 (crypto + stocks) | 8 | 8% | Weekly |
| 3 | 3 (+ BIST) | 12 | 8% | Bi-weekly |
| 4 | 4+ (+ DeFi/bonds) | 16 | 10% | Monthly |

**DD kill relaxation justification:** At higher capital and more diversification, drawdowns are more likely to be regime-driven than system-broken. But the increase is gradual and evidence-based.

---

## Anti-Patterns to Avoid

1. **Starting Year 2 before Year 1 is proven.** The most likely failure mode.
2. **Adding asset classes to fix a broken strategy.** Diversification is not a substitute for alpha.
3. **Increasing complexity faster than testing capacity.** Every new component needs tests, monitoring, and incident response.
4. **Ignoring correlation during expansion.** Crypto and stocks may move together in a macro crash.
5. **Premature Kelly transition.** Fixed fractional is "good enough" until statistics are rock-solid.

---

## Document History

| Version | Date | Change |
|---------|------|--------|
| v1.0 | 2026-02-10 | Initial Year 2+ plan |

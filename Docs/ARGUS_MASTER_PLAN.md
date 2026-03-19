# ARGUS MASTER PLAN

**The 4-Year Blueprint: 2026 → 2030**

**Author:** Founder  
**Version:** 1.0  
**Last Update:** 2026-02-07

---

## Preface: What This Document Is

This is not a feature list.  
This is not a sprint plan.  
This is not an optimization guide.

This is the strategic blueprint for building a serious quantitative trading system from scratch — with limited capital, no team, and high ambition.

The goal: Transform Argus from a prototype into a compounding machine.

---

# 1. VISION

## The 2030 State

Argus in 2030 is:

- **A self-improving trading system** that compounds capital with minimal human intervention
- **A research platform** that can test 100 ideas/month and promote 1-2 survivors
- **A risk-first architecture** where capital preservation is the primary objective
- **A multi-asset engine** operating across crypto, US equities, and alternative markets
- **A transparent system** with full audit trails, explainable decisions, and governance

## What Argus Is NOT

- Not a get-rich-quick scheme
- Not a black-box AI that makes magic predictions
- Not dependent on a single strategy or market
- Not fragile to regime change
- Not a system that needs constant babysitting

## Core Philosophy

```
SKILL > LUCK
PROCESS > OUTCOME
SURVIVAL > GROWTH
COMPOUNDING > SPECULATION
```

The system exists to answer one question:

> "Can I build a machine that makes consistent, risk-adjusted returns over decades?"

If the answer is yes, everything else follows.  
If the answer is no, nothing else matters.

---

# 2. PHASED EVOLUTION

## Timeline Overview

| Era | Period | Focus | Capital Range |
|-----|--------|-------|---------------|
| **Era 0: Foundation** | 2026 H1 | Stability, validation | $30–$500 |
| **Era 1: Proof** | 2026 H2 | Paper trading, 6M+ track record | $500–$2K |
| **Era 2: Pilot** | 2027 | Small live trading, multi-asset | $2K–$10K |
| **Era 3: Scale** | 2028 | Strategy diversification, automation | $10K–$50K |
| **Era 4: Professional** | 2029 | Institutional-grade ops, external capital | $50K–$250K |
| **Era 5: Maturity** | 2030+ | Autonomous operation, compounding | $250K+ |

---

## Era 0: Foundation (2026 H1)

**Duration:** 6 months  
**Capital:** $30 → $500  
**Mode:** Paper trading + backtesting

### Objectives
1. Prove the system doesn't lose money catastrophically
2. Establish walk-forward validation pipeline
3. Build risk infrastructure that cannot be bypassed
4. Create audit trail for every decision
5. Validate data integrity across sources

### Success Criteria
- 12M walk-forward with positive expectancy
- Max drawdown < 15% in simulation
- Zero days where system traded without stop-loss
- All rejections logged with reason codes
- System runs 30 days continuously without crash

### Failure Criteria
- Drawdown > 25% in any window
- System makes trades without risk checks
- Data corruption or lookahead detected
- Unable to reproduce backtest results

### Key Decisions
- DO NOT add live money yet
- DO NOT optimize for returns
- DO focus on reliability and reproducibility

---

## Era 1: Proof (2026 H2)

**Duration:** 6 months  
**Capital:** $500 → $2,000  
**Mode:** Paper trading with real-time data

### Objectives
1. Run paper trading 24/7 for 6+ months
2. Demonstrate consistent signal generation
3. Track paper vs. backtest alignment
4. Build operational muscle (monitoring, alerting, recovery)
5. Accumulate capital externally (job, savings)

### Success Criteria
- 6 months continuous paper operation
- Sharpe > 0.5 (paper, after costs)
- Max drawdown < 12%
- Signal quality improving (conversion rate > 15%)
- Capital accumulated to $2,000+

### Failure Criteria
- Paper performance dramatically worse than backtest
- System unstable (frequent crashes, missed signals)
- Unable to explain why system made decisions
- Zero improvement in signal quality

### Key Activities
- Weekly performance reviews
- Monthly strategy retrospectives
- Quarterly system audits
- Document every bug and fix

---

## Era 2: Pilot (2027)

**Duration:** 12 months  
**Capital:** $2,000 → $10,000  
**Mode:** Small live trading + paper expansion

### Objectives
1. First live trades with real capital
2. Experience real slippage, fills, exchange quirks
3. Add second asset class (US equities or commodities)
4. Handle live P&L emotionally and systematically
5. Build kill-switch reflexes

### Success Criteria
- 12 months live trading without blow-up
- Positive returns (any amount)
- Max drawdown < 10% on live capital
- Live vs. paper variance < 5%
- Second asset class operational

### Failure Criteria
- Drawdown > 15% on live capital
- Emotional override of system decisions
- Technical failures causing losses
- Live performance worse than paper by > 10%

### Risk Rules
- Maximum 1% of capital per trade
- Hard stop at 5% daily loss
- No trading during system updates
- Manual review required for any trade > $500

---

## Era 3: Scale (2028)

**Duration:** 12 months  
**Capital:** $10,000 → $50,000  
**Mode:** Multi-strategy, multi-asset

### Objectives
1. Run 3+ independent strategies
2. Implement portfolio-level risk management
3. Automated strategy rotation based on regime
4. Reduce manual intervention to weekly
5. Build ML feedback loop (v1)

### Success Criteria
- 3 strategies with positive expectancy
- Portfolio Sharpe > 0.8
- Max portfolio drawdown < 8%
- System handles 100+ trades/month
- First ML-assisted predictions deployed

### New Capabilities
- Strategy allocation engine
- Regime detection across assets
- Automated rebalancing
- Performance attribution

---

## Era 4: Professional (2029)

**Duration:** 12 months  
**Capital:** $50,000 → $250,000  
**Mode:** Institutional-grade operations

### Objectives
1. Consider external capital (friends/family, if ever)
2. Full regulatory compliance awareness
3. Professional-grade disaster recovery
4. Multi-broker redundancy
5. Tax-optimized execution

### Success Criteria
- Auditable track record (3+ years)
- Max drawdown < 6%
- Uptime > 99.5%
- Clear governance and controls
- Documentation sufficient for due diligence

### Considerations
- Legal structure (if taking external capital)
- Regulatory requirements
- Insurance
- Operational separation of concerns

---

## Era 5: Maturity (2030+)

**Duration:** Ongoing  
**Capital:** $250,000+  
**Mode:** Autonomous compounding machine

### Characteristics
- System runs with minimal intervention
- New strategies added through research pipeline
- Failed strategies retired automatically
- Capital grows through compounding
- Operator role is oversight, not operation

---

# 3. SYSTEM ARCHITECTURE

## Final Target Architecture (2030)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            ARGUS PLATFORM                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  RESEARCH PLANE                        PRODUCTION PLANE                 │
│  ┌─────────────────┐                   ┌─────────────────┐             │
│  │  Idea Lab       │                   │  Paper Trading  │             │
│  │  Backtesting    │ ─── Promotion ──▶ │  Live Trading   │             │
│  │  Walk-Forward   │                   │  Monitoring     │             │
│  └─────────────────┘                   └─────────────────┘             │
│           │                                     │                       │
│           └──────────────┬──────────────────────┘                       │
│                          ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                      CORE SERVICES                                 │ │
│  ├─────────────┬─────────────┬─────────────┬─────────────┬──────────┤ │
│  │   Market    │   Strategy  │    Risk     │  Execution  │   ML     │ │
│  │    Data     │   Engine    │   Engine    │   Engine    │  Engine  │ │
│  └─────────────┴─────────────┴─────────────┴─────────────┴──────────┘ │
│                          │                                              │
│  ┌───────────────────────▼───────────────────────────────────────────┐ │
│  │                      DATA LAYER                                    │ │
│  ├─────────────┬─────────────┬─────────────┬────────────────────────┤ │
│  │  Time-Series│   Trades    │   Config    │      Artifacts         │ │
│  │  Database   │   Database  │   Store     │      Storage           │ │
│  └─────────────┴─────────────┴─────────────┴────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Core Subsystems

### 1. Market Data Service
- Real-time and historical data ingestion
- Multi-source aggregation
- Data quality validation
- Feature computation pipeline

### 2. Strategy Engine
- Strategy registry and lifecycle
- Signal generation
- Conviction scoring
- Council voting mechanism

### 3. Risk Engine
- Position sizing
- Portfolio risk allocation
- Drawdown monitoring
- Kill-switch controls

### 4. Execution Engine
- Order management
- Broker abstraction
- Fill tracking
- Slippage analysis

### 5. ML Engine (Era 3+)
- Feature store
- Model training pipeline
- Prediction serving
- A/B testing framework

---

# 4. STRATEGY STACK

## Strategy Lifecycle

```
IDEA → HYPOTHESIS → BACKTEST → WALK-FORWARD → PAPER → LIVE → MONITOR → RETIRE
```

### Stage 1: Idea
- Source: market observation, research papers, intuition
- Format: one-paragraph hypothesis
- No code yet

### Stage 2: Hypothesis
- Formalize entry/exit rules
- Define expected behavior by regime
- Specify risk parameters
- Write pseudo-code

### Stage 3: Backtest
- Implement strategy
- Run on historical data
- Measure key metrics:
  - Profit factor
  - Sharpe ratio
  - Max drawdown
  - Win rate
  - Expectancy

**Gate:** Profit factor > 1.2, Sharpe > 0.5

### Stage 4: Walk-Forward
- 12+ months rolling validation
- Out-of-sample testing
- Regime robustness check

**Gate:** Positive expectancy in 60%+ windows

### Stage 5: Paper Trading
- 30–90 days real-time paper
- Compare paper to backtest
- Monitor signal quality

**Gate:** Paper within 20% of backtest performance

### Stage 6: Live Trading
- Start with minimal capital allocation
- Gradual sizing increase based on performance
- Continuous monitoring

### Stage 7: Monitoring
- Daily performance review
- Weekly drawdown check
- Monthly strategy review

### Stage 8: Retirement
Triggers:
- Drawdown > threshold for 30 days
- Profit factor < 1.0 for 60 days
- Regime shift detection
- Manual override

## Strategy Portfolio Rules

| Rule | Limit |
|------|-------|
| Maximum strategies | 10 |
| Minimum strategies | 2 |
| Max allocation per strategy | 30% |
| Max correlation between strategies | 0.5 |
| Required track record for max allocation | 6 months |

---

# 5. RISK GOVERNANCE

## Risk Hierarchy

```
Level 1: POSITION RISK
├── Stop-loss on every trade
├── Max 1-2% capital per position
└── ATR-based dynamic sizing

Level 2: STRATEGY RISK
├── Max drawdown per strategy: 10%
├── Allocation based on track record
└── Automatic reduction on underperformance

Level 3: PORTFOLIO RISK
├── Max total drawdown: 15%
├── Correlation monitoring
└── Sector/asset diversification

Level 4: OPERATIONAL RISK
├── System health monitoring
├── Failover procedures
└── Manual override capability

Level 5: EXISTENTIAL RISK
├── Kill-switch (halt all trading)
├── Capital withdrawal trigger
└── Complete system shutdown procedure
```

## Kill-Switch Protocol

**Trigger Conditions:**
- Daily loss > 5%
- Total drawdown > 10%
- 5 consecutive losses
- System error detected
- Operator manual trigger

**Actions:**
1. Close all new positions
2. Alert operator
3. Log incident with full context
4. Require manual restart

## Risk Reviews

| Frequency | Review |
|-----------|--------|
| Real-time | Position sizing, stop-loss |
| Daily | P&L, drawdown, signal quality |
| Weekly | Strategy performance, allocation |
| Monthly | Full audit, strategy review |
| Quarterly | Architecture review, risk policy update |

---

# 6. ML ROADMAP

## When ML Enters

**Not Now.** ML is dangerous without:
- Sufficient data
- Robust backtesting
- Understanding of edge

ML enters in Era 3 (2028) after the system has proven stable.

## ML Evolution Phases

### Phase ML-0: Traditional Quant (2026-2027)
- Rule-based strategies
- Manual feature engineering
- No ML predictions
- Focus: reliability and understanding

### Phase ML-1: Feature Engineering (2028)
- Build feature store
- Label historical data
- Exploratory analysis
- No live ML yet

### Phase ML-2: Offline Learning (2028-2029)
- Train models on historical data
- Backtest ML-assisted strategies
- Shadow mode (ML suggests, rules decide)
- Compare ML vs. rules

### Phase ML-3: Online Learning (2029-2030)
- Real-time model updates
- ML contributes to decisions
- A/B testing framework
- Model governance

### Phase ML-4: Autonomous (2030+)
- ML-first strategies
- Self-tuning parameters
- Regime-adaptive allocation
- Human oversight only

## ML Principles

1. **ML is not magic.** It's pattern recognition. Bad data = bad patterns.
2. **Interpretability matters.** If you can't explain why ML made a decision, don't trust it.
3. **Start simple.** Linear models before neural networks.
4. **Backtest skeptically.** ML overfits easily.
5. **Paper first.** Always paper trade ML strategies before live.

---

# 7. CAPITAL ROADMAP

## Growth Trajectory

| Stage | Capital | Source | Time to Next |
|-------|---------|--------|--------------|
| Seed | $30 | Personal | 6 months |
| Bootstrap | $500 | Savings + small returns | 6 months |
| Foundation | $2,000 | Savings + returns | 12 months |
| Proof | $10,000 | Returns + savings | 18 months |
| Scale | $50,000 | Compounding | 24 months |
| Professional | $250,000+ | Compounding + (external?) | Ongoing |

## Capital Rules

1. **Never risk what you can't lose.** The first $10K is from savings, not system returns.
2. **Compound, don't withdraw.** Reinvest all returns until $50K.
3. **Don't chase.** If system is down 10%, don't add capital to "recover."
4. **Scale slowly.** Increase allocation only after 3+ months of positive performance.
5. **Separate capital.** Trading capital ≠ emergency fund ≠ living expenses.

## Capital Allocation by Era

| Era | Trading Capital | Reserve | Notes |
|-----|-----------------|---------|-------|
| 0-1 | 80% | 20% | Paper trading, minimal live |
| 2 | 70% | 30% | First live, need buffer |
| 3 | 80% | 20% | Proven system |
| 4-5 | 90% | 10% | Scaled, diversified |

---

# 8. OPERATIONAL MODEL

## Environments

| Environment | Purpose | Data | Execution |
|-------------|---------|------|-----------|
| Local Dev | Development | Sample | None |
| Backtest | Historical testing | Historical | Simulated |
| Paper | Real-time simulation | Real-time | Simulated |
| Live | Production | Real-time | Real |

## Deployment Pipeline

```
Feature Branch → Tests → Main → Paper Deploy → Validation → Live Deploy
                          │                           │
                          └─── Rollback if issues ────┘
```

## Versioning Strategy

- **Code:** Git, semantic versioning
- **Config:** Version-controlled YAML
- **Data:** Timestamped files, checksums
- **Models:** MLflow or similar tracking
- **Artifacts:** Immutable storage

## Disaster Recovery

| Scenario | Response | RTO |
|----------|----------|-----|
| Server crash | Auto-restart | 1 min |
| Exchange API down | Pause trading | 0 (graceful) |
| Data corruption | Rollback to checkpoint | 5 min |
| Total system failure | Manual restart from backup | 1 hour |
| Account compromise | Kill-switch + freeze | Immediate |

## Monitoring Stack

- **Health:** Process alive, API reachable
- **Performance:** P&L, Sharpe, drawdown
- **Quality:** Signal rate, conversion, rejects
- **Infra:** CPU, memory, disk, network

---

# 9. ORGANIZATION MODEL

*If Argus became a company:*

## Year 1-2: Solo Operator
- Single founder does everything
- No employees, no investors
- Focus: proving the system works

## Year 3: Micro Team
- Founder + 1 part-time helper (ops or research)
- Still self-funded
- Focus: scaling operations

## Year 4+: Small Firm
```
┌─────────────────────────────────────┐
│           Founder/CTO               │
├───────────┬───────────┬─────────────┤
│  Research │    Ops    │    Risk     │
│  (1 FTE)  │  (1 FTE)  │  (Founder)  │
└───────────┴───────────┴─────────────┘
```

## Governance Principles

1. **Founder controls risk policy.** No one else can change kill-switch parameters.
2. **Four-eyes principle.** Any code touching live execution requires two reviews.
3. **Audit trail.** Every decision logged.
4. **Separation of duties.** Research doesn't deploy. Ops doesn't trade.

---

# 10. FAILURE MODES

## How Argus Dies

| Mode | Probability | Impact | Prevention |
|------|-------------|--------|------------|
| **Blow-up** | Medium | Fatal | Hard stops, kill-switch, max DD limits |
| **Slow bleed** | High | Fatal | Regular reviews, strategy retirement |
| **Technical failure** | Medium | High | Monitoring, redundancy, backups |
| **Emotional override** | High | High | Automation, rules, discipline |
| **Regulatory** | Low | High | Compliance awareness, legal structure |
| **Market regime shift** | High | Medium | Diversification, regime detection |
| **Burnout** | High | High | Automation, sustainable pace |
| **Overengineering** | Medium | Medium | KISS principle, ship fast |
| **Underengineering** | Medium | High | Testing, validation, quality |

## Prevention Framework

### Technical Failures
- Automated testing
- Continuous integration
- Monitoring and alerting
- Rollback capability

### Trading Failures
- Position limits
- Stop-losses
- Drawdown guards
- Kill-switches

### Human Failures
- Automation over manual
- Rules over discretion
- Documentation over memory
- Review over trust

### Strategic Failures
- Regular retrospectives
- External feedback
- Willingness to pivot
- Kill bad strategies early

---

# 11. NEXT 12 MONTHS

## Priority Stack (Ordered)

### Q1 2026: Foundation
1. Complete 12M walk-forward with no data gaps
2. Stabilize paper trading daemon
3. Document all system decisions
4. Establish weekly review ritual

### Q2 2026: Hardening
1. Run paper trading 24/7 for 3+ months
2. Track paper vs. backtest alignment
3. Fix all edge cases discovered
4. Add second asset class (paper only)

### Q3 2026: Proof
1. Continue paper trading
2. Build track record documentation
3. Prepare for first live trades
4. External capital accumulation (job/savings)

### Q4 2026: Transition
1. First live trades (minimal capital)
2. Compare live vs. paper
3. Iterate on execution quality
4. Prepare for Era 1 → Era 2 transition

## Personal Focus Areas

| Area | Time Allocation |
|------|-----------------|
| System operations | 30% |
| Research & analysis | 25% |
| Infrastructure | 20% |
| Documentation | 15% |
| Learning | 10% |

## What NOT To Do

❌ Add complex ML before system is stable  
❌ Trade large capital before proven  
❌ Add more strategies before existing ones validated  
❌ Optimize for short-term returns  
❌ Skip documentation  
❌ Trade without stops  
❌ Override system decisions emotionally  

## Success Metric for Year 1

Not returns.

> **"Can I run this system for 12 months without a catastrophic failure?"**

If yes: proceed to Era 2.  
If no: fix what broke, try again.

---

# Closing: The Mindset

Building Argus is a marathon, not a sprint.

The market does not reward impatience.  
The market does not reward complexity.  
The market does not reward hope.

The market rewards:
- Discipline
- Risk management
- Patience
- Continuous improvement

Every day, ask:

> "Did the system survive today?"

If yes: compound.  
If no: learn why.

That's the entire game.

---

**Document Version:** 1.0  
**Next Review:** 2026-03-07  
**Owner:** Founder

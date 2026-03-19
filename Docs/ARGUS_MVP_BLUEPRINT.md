# ARGUS MVP Production Blueprint

**6-Month Survival-Grade Execution Plan**

**Version:** 1.0  
**Author:** CTO/Architect  
**Date:** 2026-02-07  
**Reality:** Solo founder, small capital, reliability > returns

---

# 1. Minimum Production Architecture

## What MUST Exist (Non-Negotiable)

```
┌─────────────────────────────────────────────────────────────────┐
│                     MINIMUM VIABLE SYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DATA LAYER              DECISION LAYER         EXECUTION LAYER │
│  ┌──────────┐           ┌──────────────┐       ┌──────────────┐ │
│  │ Market   │──────────▶│   Council    │──────▶│    Paper     │ │
│  │ Adapter  │           │ (Aegean+Orion)│       │   Broker     │ │
│  └──────────┘           └──────────────┘       └──────────────┘ │
│       │                        │                      │          │
│       │                        ▼                      │          │
│       │                 ┌──────────────┐              │          │
│       │                 │  Risk Gate   │              │          │
│       │                 │ (Kill-Switch)│              │          │
│       │                 └──────────────┘              │          │
│       │                        │                      │          │
│       └────────────────────────┴──────────────────────┘          │
│                                │                                 │
│                         ┌──────▼──────┐                         │
│                         │   Logger    │                         │
│                         │ (Decisions, │                         │
│                         │  Trades,    │                         │
│                         │  Rejects)   │                         │
│                         └─────────────┘                         │
│                                                                  │
│  OPERATIONS              SAFETY                                  │
│  ┌──────────┐           ┌──────────────┐                        │
│  │Supervisor│           │ Kill-Switch  │                        │
│  │(Restarts)│           │ (Hard Stop)  │                        │
│  └──────────┘           └──────────────┘                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## What Can Be POSTPONED

| Component | Why Postpone | When to Add |
|-----------|--------------|-------------|
| ML Models | Overkill for MVP, adds complexity | Month 6+ |
| Multi-Asset | One market is enough to prove system | Month 4+ |
| Web Dashboard | CLI + logs is sufficient | Month 5+ |
| Advanced Analytics | Basic metrics first | Month 4+ |
| Telegram/Discord Bot | Nice-to-have | Month 5+ |
| Feature Store | Rule-based is fine initially | Month 4+ |
| Order Book Data | OHLCV is sufficient | Month 6+ |
| GPU Acceleration | Not needed for this scale | Never (this capital) |

## Current Argus State → MVP Gap

| Component | Current State | MVP Required | Gap |
|-----------|---------------|--------------|-----|
| Market Data | Crypto adapter works | Stable, validated | ❌ Add data quality checks |
| Council | Aegean + Orion | Working | ✅ OK |
| Risk Engine | Basic state machine | Enhanced kill-switch | ❌ Needs hardening |
| Paper Broker | Functional | Realistic slippage | ❌ Needs improvement |
| Supervisor | Exists | Auto-restart + alerts | ❌ Needs alerts |
| Logging | CSV files | Structured, queryable | ❌ Needs cleanup |
| Monitoring | None | Basic health checks | ❌ Missing |

---

# 2. 6-Month Execution Roadmap

## Overview

| Period | Focus | Goal |
|--------|-------|------|
| Month 1-2 | **Hardening** | System doesn't crash |
| Month 3-4 | **Validation** | System makes sense |
| Month 5-6 | **Pre-Live** | Ready for real money |

---

## Month 1-2: HARDENING

### Objective
Make the system impossible to break. Zero crashes. Zero data corruptions.

### Week 1-2: Kill-Switch Finalization

**Tasks:**
- [ ] Implement 3-level kill-switch (SOFT/HARD/HALT)
- [ ] Add daily loss trigger (5%)
- [ ] Add total drawdown trigger (8%)
- [ ] Add consecutive loss trigger (5 losses)
- [ ] Add system health trigger (API errors, data gaps)
- [ ] Test kill-switch manually 3x
- [ ] Document kill-switch recovery procedure

**Files:**
```
argus_py/risk/
├── kill_switch.py       # NEW: Dedicated kill-switch module
├── state_machine.py     # MODIFY: Integrate with kill-switch
└── triggers.py          # NEW: Trigger conditions
```

**Success Metric:**
- Kill-switch triggers correctly in 100% of test scenarios
- Recovery from kill-switch is documented and tested

**Failure Risk:**
- Kill-switch not triggered during real emergency
- Mitigation: Test weekly with simulated scenarios

### Week 3-4: Supervisor Hardening

**Tasks:**
- [ ] Add heartbeat monitoring (check every 30 seconds)
- [ ] Add automatic restart on crash
- [ ] Add restart counter (max 3 restarts per hour)
- [ ] Add basic alerting (write to log file, email optional)
- [ ] Add graceful shutdown handling
- [ ] Test crash recovery 5x

**Files:**
```
Scripts/
├── supervisor_v2.py     # MODIFY: Enhanced supervisor
├── healthcheck.py       # NEW: Health check endpoints
└── alerts.py            # NEW: Alert dispatcher
```

**Success Metric:**
- System auto-recovers from crash within 60 seconds
- No more than 3 restarts per hour

**Failure Risk:**
- Infinite restart loop
- Mitigation: Restart counter + cooldown period

### Week 5-6: Data Integrity

**Tasks:**
- [ ] Add data quality checks on load
- [ ] Add gap detection (missing candles)
- [ ] Add spike detection (unrealistic prices)
- [ ] Add checksum validation for cached files
- [ ] Add data freshness check (stale data detection)
- [ ] Log all data quality issues

**Files:**
```
argus_py/data/
├── quality.py           # NEW: Data quality module
├── validators.py        # NEW: Validation functions
└── adapters/crypto.py   # MODIFY: Add quality checks
```

**Success Metric:**
- Zero trading decisions on corrupted data
- All quality issues logged

**Failure Risk:**
- Trade on stale/bad data
- Mitigation: Hard block on quality check failure

### Week 7-8: Logging Cleanup

**Tasks:**
- [ ] Standardize log format (timestamp, level, component, message)
- [ ] Add structured JSON logging option
- [ ] Add log rotation (keep 30 days)
- [ ] Separate logs: decisions.log, trades.log, errors.log, system.log
- [ ] Add request/response logging for broker calls
- [ ] Add performance timing logs

**Files:**
```
argus_py/core/
├── logger.py            # NEW: Centralized logging
└── config.py            # MODIFY: Log config section
```

**Success Metric:**
- Can query any decision from logs
- Logs don't grow unbounded

**Failure Risk:**
- Disk full from logs
- Mitigation: Log rotation + size limits

### Month 1-2 Exit Criteria

| Criterion | Measure | Target |
|-----------|---------|--------|
| Zero unhandled crashes | Crash count | 0 in 7 days |
| Kill-switch works | Manual test count | 5 successful tests |
| Auto-recovery | Recovery time | < 60 seconds |
| Data quality | Issues logged | 100% |
| Log hygiene | Disk usage stable | No runaway growth |

---

## Month 3-4: VALIDATION

### Objective
Prove the system makes sensible decisions. Understand rejection patterns.

### Week 9-10: Decision Audit Framework

**Tasks:**
- [ ] Track all signal → trade conversions
- [ ] Track all rejections with reason codes
- [ ] Calculate conversion rate by regime
- [ ] Calculate conversion rate by strategy
- [ ] Generate weekly audit report
- [ ] Identify top 5 rejection reasons

**Files:**
```
argus_py/reporting/
├── signal_audit.py      # EXISTS: Enhance
├── weekly_report.py     # NEW: Weekly summary generator
└── rejection_analysis.py # NEW: Rejection deep-dive
```

**Success Metric:**
- Conversion rate > 10%
- Top rejection reasons explainable

**Failure Risk:**
- Conversion rate near 0% (over-filtering)
- Mitigation: Tune thresholds based on analysis

### Week 11-12: Backtest vs Paper Alignment

**Tasks:**
- [ ] Run identical 30-day period in backtest and paper
- [ ] Compare signal count
- [ ] Compare trade count
- [ ] Compare rejection reasons
- [ ] Identify and fix divergences
- [ ] Document expected variance

**Files:**
```
Scripts/
├── alignment_check.py   # NEW: Backtest/paper comparison
└── divergence_report.py # NEW: Divergence analyzer
```

**Success Metric:**
- Backtest vs paper signal variance < 5%
- All divergences explained

**Failure Risk:**
- Backtest shows profit, paper shows loss
- Mitigation: Debug until aligned

### Week 13-14: Slippage Reality Check

**Tasks:**
- [ ] Enhance paper broker with realistic slippage model
- [ ] Add spread simulation (bid-ask)
- [ ] Add volume-based slippage
- [ ] Add latency simulation
- [ ] Compare paper fills vs expected
- [ ] Log slippage on every trade

**Files:**
```
argus_py/broker/
├── paper.py             # MODIFY: Enhanced slippage
├── slippage.py          # NEW: Slippage models
└── latency.py           # NEW: Latency simulation
```

**Success Metric:**
- Slippage model validated against historical exchange data
- Average slippage within 1 bps of expectation

**Failure Risk:**
- Underestimate slippage, overestimate profit
- Mitigation: Conservative slippage assumptions

### Week 15-16: 90-Day Paper Run Baseline

**Tasks:**
- [ ] Start continuous 90-day paper trading run
- [ ] Monitor daily (5-minute check)
- [ ] Log weekly performance
- [ ] Document all interventions
- [ ] Do NOT optimize mid-run (observe only)
- [ ] Calculate final metrics at day 90

**Files:**
```
runs/
└── paper_90d_baseline/
    ├── daily/           # Daily snapshots
    ├── weekly/          # Weekly summaries
    └── final_report.md  # 90-day outcome
```

**Success Metric:**
| Metric | Target | Acceptable |
|--------|--------|------------|
| Total Return | > 0% | > -5% |
| Max Drawdown | < 10% | < 15% |
| Sharpe | > 0.5 | > 0.2 |
| System Uptime | > 99% | > 95% |

**Failure Risk:**
- System loses money
- Mitigation: Analyze why, don't over-optimize

### Month 3-4 Exit Criteria

| Criterion | Measure | Target |
|-----------|---------|--------|
| Decision audit working | Weekly reports | 8 weeks |
| Backtest/paper aligned | Variance | < 5% |
| Slippage model realistic | Validation | Documented |
| 90-day run started | Days running | 60+ |

---

## Month 5-6: PRE-LIVE

### Objective
Prepare for first real money. Final safety checks.

### Week 17-18: Broker Integration (Paper → Live-Ready)

**Tasks:**
- [ ] Abstract broker interface (paper and live share same interface)
- [ ] Add ccxt wrapper for crypto exchanges
- [ ] Add balance checking before trade
- [ ] Add order confirmation flow
- [ ] Add fill status tracking
- [ ] Test on testnet (if available)

**Files:**
```
argus_py/broker/
├── base.py              # MODIFY: Abstract interface
├── paper.py             # MODIFY: Implement interface
├── ccxt_live.py         # NEW: Live crypto broker
└── order_tracker.py     # NEW: Order state machine
```

**Success Metric:**
- Paper and live broker pass same test suite
- Testnet trades execute correctly (if testnet exists)

**Failure Risk:**
- Live order fails due to API difference
- Mitigation: Thorough testnet testing

### Week 19-20: Monitoring Dashboard

**Tasks:**
- [ ] Create CLI dashboard (terminal-based)
- [ ] Show current position
- [ ] Show today's P&L
- [ ] Show current drawdown
- [ ] Show kill-switch status
- [ ] Show last N decisions
- [ ] Add refresh rate (every 10 seconds)

**Files:**
```
Scripts/
├── dashboard.py         # NEW: CLI dashboard
└── metrics.py           # NEW: Metric aggregation
```

**Success Metric:**
- Can assess system health in under 10 seconds
- All critical metrics visible

**Failure Risk:**
- Dashboard shows stale data
- Mitigation: Add "last updated" timestamp

### Week 21-22: Disaster Recovery Drill

**Tasks:**
- [ ] Document 5 disaster scenarios
- [ ] Write recovery procedure for each
- [ ] Execute drill 1: Kill-switch trigger
- [ ] Execute drill 2: System crash mid-trade
- [ ] Execute drill 3: Exchange API down
- [ ] Execute drill 4: Data corruption detected
- [ ] Execute drill 5: Network outage
- [ ] Time each recovery
- [ ] Document learnings

**Files:**
```
Docs/
├── DISASTER_RECOVERY.md # NEW: Recovery procedures
└── DRILL_LOG.md         # NEW: Drill results
```

**Success Metric:**
| Scenario | Recovery Target | Actual |
|----------|-----------------|--------|
| Kill-switch | < 1 min | ? |
| Crash | < 2 min | ? |
| API down | < 5 min (graceful) | ? |
| Data corrupt | < 10 min | ? |
| Network out | < 5 min | ? |

**Failure Risk:**
- Don't know how to recover
- Mitigation: Practice drills monthly

### Week 23-24: Go/No-Go Checklist + First Live Trade

**Tasks:**
- [ ] Complete go/no-go checklist (see below)
- [ ] Set up live account with MINIMUM capital ($30-50)
- [ ] Configure live broker with paper risk limits
- [ ] Execute first live trade manually via system
- [ ] Verify fill matches expectation
- [ ] Verify logs capture live trade correctly
- [ ] Close position manually
- [ ] Celebrate or debug

**Go/No-Go Checklist:**
```
SYSTEM STABILITY
[ ] 14 days no crash
[ ] Kill-switch tested this week
[ ] Supervisor recovery tested this week
[ ] Logs rotating correctly

DECISION QUALITY
[ ] 90-day paper run complete
[ ] Total return not catastrophic (> -10%)
[ ] Rejection reasons understood
[ ] No unexplained divergences

OPERATIONAL READINESS
[ ] Disaster recovery drills complete
[ ] Dashboard shows correct metrics
[ ] Live broker tested on testnet
[ ] Recovery procedures documented

MENTAL READINESS
[ ] Accepted that first trades may lose
[ ] Committed to not override system
[ ] Ready to kill-switch if needed
[ ] Not emotionally attached to outcome
```

**Success Metric:**
- First live trade executes without error
- Trade matches paper broker behavior

**Failure Risk:**
- Panic and override system
- Mitigation: Start with tiny capital you can lose

### Month 5-6 Exit Criteria

| Criterion | Measure | Target |
|-----------|---------|--------|
| Live broker ready | Testnet validation | Pass |
| Dashboard working | Usability | 10-second check |
| DR drills complete | Drills | 5 |
| Go/No-Go checklist | Items | 100% |
| First live trade | Execution | Success |

---

# 3. What NOT to Build (Yet)

## Overengineering Risks

| Temptation | Why It's Dangerous | Alternative |
|------------|-------------------|-------------|
| Full ML pipeline | Months of work, unclear payoff | Rule-based strategies first |
| Microservices | Complexity for solo dev | Monolith with modules |
| Kubernetes | Overkill for one process | Simple systemd/launchd |
| Real-time dashboard | Time sink | CLI + logs |
| Multi-exchange arbitrage | Complex, capital intensive | One exchange first |
| Options trading | Different game entirely | Spot only |
| High-frequency features | Need colo, serious infra | 1-minute minimum |

## Unnecessary Complexity

| Feature | Skip Until | Why |
|---------|------------|-----|
| Fancy visualizations | Month 6+ | Logs are enough for MVP |
| Telegram/Slack bots | Month 5+ | Check manually is fine |
| Multiple strategies | Month 4+ | One strategy to validate first |
| Portfolio optimization | Month 6+ | Single asset is enough |
| Alpha factor library | Month 6+ | Simple signals work |
| A/B testing framework | Never (this scale) | Paper test instead |

## Build vs Buy vs Skip

| Component | Decision | Rationale |
|-----------|----------|-----------|
| Market data | Build | Already have adapter |
| Technical indicators | Buy (pandas-ta) | Don't reinvent |
| Broker API | Buy (ccxt) | Don't reinvent |
| ML framework | Skip | Not needed yet |
| Database | Skip (use files) | Overkill for 100 trades/month |
| Message queue | Skip | Single process is fine |
| Container orchestration | Skip | systemd is enough |

---

# 4. Kill-Switch & Disaster Recovery

## Kill-Switch Design

```
┌─────────────────────────────────────────────────────────────┐
│                    KILL-SWITCH LEVELS                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LEVEL 1: SOFT                                               │
│  ├── Triggered by: 3% daily loss / 3 consecutive losses     │
│  ├── Action: Block new trades, existing positions run       │
│  └── Recovery: Automatic after 4 hours or next day          │
│                                                              │
│  LEVEL 2: HARD                                               │
│  ├── Triggered by: 5% daily loss / 5 consecutive losses     │
│  ├── Action: Close all positions at market                  │
│  └── Recovery: Manual restart required                      │
│                                                              │
│  LEVEL 3: HALT                                               │
│  ├── Triggered by: 8% total DD / system error / manual      │
│  ├── Action: Disconnect from exchange, alert operator       │
│  └── Recovery: Full system review required                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Trigger Table

| Trigger | Level | Auto-Recover | Action |
|---------|-------|--------------|--------|
| Daily loss 3% | SOFT | Yes (4h) | Block new |
| Daily loss 5% | HARD | No | Close all |
| Daily loss 8% | HALT | No | Disconnect |
| 3 consecutive losses | SOFT | Yes (4h) | Block new |
| 5 consecutive losses | HARD | No | Close all |
| Total DD 5% | SOFT | Yes (next day) | Block new |
| Total DD 8% | HALT | No | Disconnect |
| API error 3x | SOFT | Yes (5min) | Pause |
| API error 10x | HARD | No | Close + alert |
| Data gap detected | SOFT | Auto (resume) | Pause |
| System crash | HARD | Auto-restart (3x) | Supervisor |
| Manual trigger | Any | No | Whatever specified |

## Recovery Procedures

### SOFT Recovery
```
1. Wait for cooldown period (4 hours or next day)
2. Check logs for trigger reason
3. System auto-resumes if cooldown passed
4. OR manually run: phase19ctl.sh resume
```

### HARD Recovery
```
1. System stops trading
2. Check logs for trigger reason
3. Analyze what went wrong
4. If understood: run 'phase19ctl.sh restart'
5. If not understood: stay in HALT
```

### HALT Recovery
```
1. System disconnected from exchange
2. DO NOT RESTART IMMEDIATELY
3. Full review checklist:
   [ ] Read all logs from incident
   [ ] Understand root cause
   [ ] Document incident
   [ ] Fix if code bug
   [ ] Wait 24 hours minimum
4. Manual restart: 'phase19ctl.sh force-restart --confirm'
```

---

# 5. Monitoring Dashboard Metrics

## Tier 1: Check Every 10 Seconds (CLI Dashboard)

| Metric | Display | Alert If |
|--------|---------|----------|
| System Status | RUNNING/PAUSED/STOPPED | STOPPED |
| Current Position | BTC: +0.01 @ 45000 | - |
| Today P&L | +$12.50 (+0.42%) | < -3% |
| Total Drawdown | -2.3% from peak | > 5% |
| Kill-Switch Level | NORMAL/SOFT/HARD/HALT | Not NORMAL |
| Last Decision | BUY @ 12:34:56 | > 4h ago |
| Last Heartbeat | 3s ago | > 60s ago |

## Tier 2: Check Every Hour (Log Review)

| Metric | Check Method | Concern If |
|--------|--------------|------------|
| Signal Count | grep decisions.log | < 2/hour |
| Trade Count | grep trades.log | < 1/day (if signals exist) |
| Reject Count | grep rejects.log | > 95% rejection rate |
| Error Count | grep errors.log | Any ERROR level |
| API Latency | Log timestamps | > 2 seconds |

## Tier 3: Check Daily (Manual Review)

| Metric | Expected | Action If Wrong |
|--------|----------|-----------------|
| Daily Return | -1% to +2% | Analyze if outside |
| Decisions Made | 10-50 | Check if too few/many |
| Conversion Rate | > 10% | Tune thresholds if low |
| System Uptime | 100% | Check restart count |

## Dashboard Display (CLI)

```
╔═══════════════════════════════════════════════════════════════╗
║                    ARGUS TRADING SYSTEM                        ║
╠═══════════════════════════════════════════════════════════════╣
║  Status: RUNNING                    Last Update: 12:34:56      ║
╠═════════════════════════╦═════════════════════════════════════╣
║  POSITION               ║  PERFORMANCE                         ║
║  Symbol: BTCUSDT        ║  Today P&L:  +$12.50 (+0.41%)       ║
║  Side: LONG             ║  Week P&L:   +$45.00 (+1.52%)       ║
║  Size: 0.01 BTC         ║  Total DD:   -2.3% from peak        ║
║  Entry: $45,000         ║  Sharpe (30d): 0.85                 ║
║  Current: $45,150       ║                                      ║
║  Unrealized: +$1.50     ║  Kill-Switch: NORMAL ✓              ║
╠═════════════════════════╩═════════════════════════════════════╣
║  RECENT DECISIONS                                              ║
║  12:34:56  HOLD  Council: 0.45  Regime: CHOP                  ║
║  12:33:56  HOLD  Council: 0.52  Regime: CHOP                  ║
║  12:32:56  BUY   Council: 0.71  Regime: TREND → EXECUTED      ║
╠═══════════════════════════════════════════════════════════════╣
║  SYSTEM HEALTH                                                 ║
║  Heartbeat: 3s ago ✓   Memory: 234MB ✓   Disk: 45% ✓         ║
║  API Status: OK ✓      Last API Call: 2s ago                  ║
╚═══════════════════════════════════════════════════════════════╝
```

---

# 6. Deployment Strategy

## Current Environment (Month 1-4)

```
LOCAL MAC
├── Paper trading runs continuously
├── Manually check 2-3x per day
├── Logs stored locally
└── Backup to external drive weekly
```

## Pre-Live Environment (Month 5-6)

```
LOCAL MAC (PRODUCTION)
├── Live trading with minimal capital
├── Dedicated terminal window for dashboard
├── Logs backed up daily (iCloud or external)
├── Kill-switch hotkey configured
└── Phone alarm for critical alerts (optional)
```

## Deployment Checklist (Every Restart)

```
[ ] Check current position (should be flat)
[ ] Check account balance
[ ] Verify kill-switch is NORMAL
[ ] Verify data feed is live
[ ] Start supervisor: 'phase19ctl.sh start'
[ ] Confirm heartbeat within 30 seconds
[ ] Check dashboard shows live data
```

## Rollback Procedure

```
If new code causes issues:

1. Trigger kill-switch: 'phase19ctl.sh halt'
2. Close any open positions manually if needed
3. Revert code: 'git checkout HEAD~1'
4. Restart: 'phase19ctl.sh start'
5. Monitor for 30 minutes
6. Document what broke
```

---

# 7. Summary: Month-by-Month Checklist

## Month 1-2 Checklist (HARDENING)

- [ ] Kill-switch 3-level implementation
- [ ] Kill-switch tested 5x
- [ ] Supervisor auto-restart working
- [ ] Supervisor alert on crash
- [ ] Data quality checks added
- [ ] Gap detection working
- [ ] Log format standardized
- [ ] Log rotation configured
- [ ] **14 days no crash achieved**

## Month 3-4 Checklist (VALIDATION)

- [ ] Signal audit reports weekly
- [ ] Rejection analysis complete
- [ ] Backtest/paper variance < 5%
- [ ] Slippage model implemented
- [ ] Slippage validated against real data
- [ ] 90-day paper run started
- [ ] 60+ days of paper run complete
- [ ] **Conversion rate > 10%**

## Month 5-6 Checklist (PRE-LIVE)

- [ ] Live broker abstraction complete
- [ ] Testnet trades successful
- [ ] CLI dashboard working
- [ ] 5 disaster recovery drills complete
- [ ] Recovery procedures documented
- [ ] Go/No-Go checklist 100% complete
- [ ] First live trade executed
- [ ] **System is live-ready**

---

# Final Words

This is not about making money in 6 months.

This is about building a system that CAN make money without killing itself.

After 6 months, you will have:
- A system that doesn't crash
- Logs that explain every decision
- Confidence that it won't blow up
- First live trade under your belt

That's the foundation. Everything else comes after.

---

**Document Version:** 1.0  
**Next Review:** Monthly  
**Owner:** Founder

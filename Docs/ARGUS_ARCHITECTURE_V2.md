# ARGUS Platform Architecture v2.0

**Date:** 2026-02-07  
**Author:** Chief Systems Architect  
**Status:** DRAFT → Review Required

---

## Executive Summary

Argus is transitioning from a research platform to a production-grade quant system. This document defines the target architecture, migration path, and concrete milestones.

**Current State:** Advanced prototype (Phase 19-20)  
**Target State:** Event-driven, ML-ready, multi-asset trading OS  
**Timeline:** 6 months to production-ready

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARGUS PLATFORM v2.0                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │   RESEARCH   │   │  SIMULATION  │   │    PAPER     │   │     LIVE     │ │
│  │     LAB      │──▶│    ENGINE    │──▶│   TRADING    │──▶│   TRADING    │ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘ │
│         │                  │                  │                  │          │
│         └──────────────────┴──────────────────┴──────────────────┘          │
│                                    │                                         │
│  ┌─────────────────────────────────▼─────────────────────────────────────┐  │
│  │                        CORE INFRASTRUCTURE                             │  │
│  ├────────────────┬────────────────┬────────────────┬────────────────────┤  │
│  │   Event Bus    │  State Store   │   Feature      │    Telemetry       │  │
│  │   (Messages)   │  (Positions)   │   Store        │    (Metrics)       │  │
│  └────────────────┴────────────────┴────────────────┴────────────────────┘  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        DOMAIN SERVICES                                   ││
│  ├──────────┬──────────┬──────────┬──────────┬──────────┬─────────────────┤│
│  │ Strategy │   Risk   │ Portfolio│  Market  │ Execution│   Learning     ││
│  │  Engine  │  Engine  │ Manager  │  Data    │  Engine  │   Loop         ││
│  └──────────┴──────────┴──────────┴──────────┴──────────┴─────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        DATA LAYER                                        ││
│  ├──────────────┬──────────────┬──────────────┬────────────────────────────┤│
│  │  TimeSeries  │   Trade DB   │   Config     │       Artifacts            ││
│  │   (OHLCV)    │  (Postgres)  │   (YAML)     │       (S3/Local)           ││
│  └──────────────┴──────────────┴──────────────┴────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Market Data → Adapters → Feature Store → Strategy Engine → Risk Gate → Execution
                                              ↓
                                         Council Vote
                                              ↓
                              ┌───────────────┴───────────────┐
                              │                               │
                           GO + Risk OK                    REJECT
                              ↓                               ↓
                         Broker Execute              Counterfactual Log
                              ↓                               ↓
                         Trade Record                  Learning Loop
                              ↓                               
                         Performance Eval ◄───────────────────┘
```

---

## 2. Target Module Structure

```
argus/
├── core/                       # Shared primitives
│   ├── events.py               # Event bus + message types
│   ├── types.py                # Domain types (Bar, Trade, Signal)
│   ├── config.py               # Unified config loader
│   └── utils.py                # Pure utilities
│
├── data/                       # Data layer (read-only)
│   ├── adapters/               # Market data adapters
│   ├── feature_store/          # Pre-computed features
│   └── cache/                  # Local data cache
│
├── strategy/                   # Strategy layer (stateless)
│   ├── base.py                 # Strategy interface
│   ├── aegean/                 # Momentum model
│   ├── orion/                  # Confirmation model
│   ├── mrie/                   # Regime intelligence
│   └── registry.py             # Strategy discovery
│
├── council/                    # Aggregation + voting
├── risk/                       # Risk management (critical)
├── execution/                  # Execution layer
├── learning/                   # ML/Feedback loop
├── ops/                        # Operations
├── reporting/                  # Observability
└── cli/                        # Entry points
```

---

## 3. Risk Architecture (4 Layers)

| Layer | Scope | Controls |
|-------|-------|----------|
| **Portfolio** | Cross-asset | Correlation, sector, VaR |
| **Position** | Per-trade | ATR stops, size limits |
| **Execution** | Per-order | Slippage, liquidity |
| **Circuit Breaker** | System-wide | Hard stops, kill switch |

---

## 4. Pipeline: Research → Live

| Stage | Entry Criteria | Exit Criteria |
|-------|----------------|---------------|
| Research | Hypothesis | Backtest PF > 1.2 |
| Simulation | Backtest pass | 12M WF stable |
| Paper | WF pass | 30 days, DD < 10% |
| Live | Paper pass + audit | Continuous |

---

## 5. Milestones (Phase 20 → 25)

| Phase | Goal | Timeline |
|-------|------|----------|
| P20 | Signal Quality + Audit | 1 week |
| P21 | Module Restructure | 2 weeks |
| P22 | Learning Loop | 2 weeks |
| P23 | Ops Hardening | 2 weeks |
| P24 | Multi-Asset | 3 weeks |
| P25 | Paper Maturity (30d stable) | 4 weeks |

---

## 6. Anti-Patterns to Avoid

| Pattern | Problem | Solution |
|---------|---------|----------|
| God Object | cli.py 1000+ lines | Split by responsibility |
| Hardcoded Config | Magic numbers | Externalize to YAML |
| Tight Coupling | Strategy knows broker | Use interfaces |
| No Audit Trail | Decisions not logged | Log EVERY decision |
| No Kill Switch | Runaway losses | Test kill switch weekly |

---

## See Also

- [HEDGE_FUND_ROADMAP.md](./HEDGE_FUND_ROADMAP.md) - Sprint board
- [SPRINT2_PLAN.md](./SPRINT2_PLAN.md) - Current sprint
- [sprint1_acceptance_report.md](./sprint1_acceptance_report.md) - Validation

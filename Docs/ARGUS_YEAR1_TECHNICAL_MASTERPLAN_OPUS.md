# ARGUS Year-1 Technical Masterplan (OPUS Edition)

**The Staff+ Engineering Blueprint: Feb 7, 2026 → Feb 7, 2027**

**Author:** Claude Opus (Staff+ Systems Architect)  
**Date:** 2026-02-07T17:27:00+03:00  
**Constraint:** Solo founder + multi-agent workflow, correctness > speed

---

# A. Current Architecture Snapshot (AS-IS)

## 1. Module Map

```
argus-terminal/
├── argus_py/                    # Core Python library
│   ├── adapters/               # Data source adapters (Binance, etc.)
│   ├── broker/                 # Paper/Live execution
│   │   ├── paper.py            # PaperBroker: 441 lines, handles fills/positions
│   │   └── (no live.py yet)
│   ├── core/                   # Exchange rules, base classes
│   ├── council/                # Strategy voting aggregation
│   ├── data/                   # Data loading, caching, reporting
│   ├── exchange/               # Exchange-specific logic
│   ├── lab/                    # Walk-forward, optimization, grid search
│   ├── models/                 # Strategy models (MRIE, etc.)
│   ├── portfolio/              # Portfolio tracking
│   ├── reporting/              # Signal audit, diagnostics
│   ├── risk/                   # 8 modules: sizing, regime, state_machine, etc.
│   ├── runner/                 # Execution runners
│   ├── signals/                # Signal definitions
│   ├── strategy/               # Strategy implementations
│   └── telemetry/              # Event schema
│
├── Scripts/                    # 68 files - operational scripts
│   ├── paper_daemon.py         # Main daemon: 730 lines, PaperDaemon class
│   ├── phase19_*.py/sh         # Phase 19 tooling (supervisor, dashboard, etc.)
│   ├── phase20_*.py            # Phase 20 audit tools
│   └── sprint*_.py             # Sprint-specific scripts
│
├── runs/                       # 442 subdirs - RUN ARTIFACT SPRAWL
│   ├── phase19_twin/           # Live twin sessions
│   ├── pack_*/grid_*/sweep_*/  # Experiment artifacts
│   └── YYYYMMDD_HHMMSS_hash/   # Session directories
│
└── Docs/                       # 24 files - documentation
    ├── ARGUS_MASTER_PLAN.md
    ├── ARGUS_MVP_BLUEPRINT.md
    ├── ARGUS_YEAR1_TECHNICAL_MASTERPLAN.md
    └── PHASE20_STATUS.md
```

## 2. Data Flow (Current)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT DATA FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Binance API                                                                │
│       │                                                                     │
│       ▼                                                                     │
│  fetch_klines() ──► HistoryBook ──► Router ──► Council (Aegean+Orion)      │
│       │                   │            │              │                     │
│       │                   │            │              ▼                     │
│       │                   │            │         Verdict (GO/WAIT/EXIT)     │
│       │                   │            │              │                     │
│       │                   │            │              ▼                     │
│       │                   │            │    RiskStateMachine.check()        │
│       │                   │            │         │         │                │
│       │                   │            │    ALLOW      REJECT               │
│       │                   │            │         │         │                │
│       │                   │            │         ▼         ▼                │
│       │                   │            │    PaperBroker   append_reject()   │
│       │                   │            │    .execute()                      │
│       │                   │            │         │                          │
│       │                   │            │         ▼                          │
│       │                   │       append_decision()  append_trade()         │
│       │                   │            │              │                     │
│       │                   │            ▼              ▼                     │
│       │                   │       decisions.csv   trades.csv                │
│       │                   │                                                 │
│       └───────────────────┴───────────► heartbeat.json                     │
│                                         daemon_state.json                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3. Identified Fragilities

| Category | Issue | Severity | Evidence |
|----------|-------|----------|----------|
| **Silent Failures** | GO decisions without trade, no explicit reject row | HIGH | Recent P19/P20 fixes |
| **Unit Confusion** | risk_pct as % vs fraction (1.0 = 1% vs 100%) | CRITICAL | Fixed in recent commit |
| **Argparse Conflicts** | Duplicate `--max_exp_move_bps` caused crash loops | HIGH | `.rej` files in Scripts/ |
| **Run Dir Chaos** | 442 run directories, no cleanup policy | MEDIUM | `runs/` listing |
| **Patch Conflicts** | 6+ `.rej` files indicating failed patches | MEDIUM | `paper_daemon.py.rej`, etc. |
| **Config Sprawl** | DEFAULT_CONFIG hardcoded in paper_daemon.py | MEDIUM | Lines 33-66 |
| **Missing Tests** | No unit tests for critical math | HIGH | No test_sizing.py |
| **Data Coupling** | HistoryBook tightly coupled to Binance | MEDIUM | No adapter abstraction |
| **No Interface Contracts** | No Protocol/ABC definitions | MEDIUM | Duck typing everywhere |
| **Logging Inconsistency** | Mix of print() and CSV logging | LOW | Code inspection |

## 4. Telemetry Current State

| Log File | Content | Format |
|----------|---------|--------|
| `decisions.csv` | Every bar decision | CSV with timestamp, verdict, scores |
| `trades.csv` | Executed trades + REJECTED rows | CSV with event type |
| `rejects.csv` | Risk-cap rejections | CSV with reason codes |
| `heartbeat.json` | Daemon health | JSON, updated every bar |
| `daemon_state.json` | Broker state snapshot | JSON, on state change |
| `errors.csv` | Exception logs | CSV, append-only |

**Gap:** No structured JSON logging. No log rotation. No aggregation.

---

# B. Target Architecture (TO-BE)

## 1. Module Boundaries (Clean)

```
argus_py/
├── core/                        # Shared infrastructure
│   ├── protocols.py             # ALL interface definitions (ABC/Protocol)
│   ├── config.py                # Centralized YAML config loader
│   ├── logger.py                # Structured logging (JSON + CSV)
│   └── errors.py                # Custom exceptions
│
├── data/                        # Data ingestion layer
│   ├── adapters/
│   │   ├── base.py              # MarketDataAdapter protocol
│   │   ├── binance.py
│   │   └── yfinance.py          # Future: US equities
│   ├── quality/
│   │   ├── validator.py         # Gap detection, spike filter
│   │   └── checksum.py          # File integrity
│   └── cache/
│       └── manager.py           # Parquet cache with versioning
│
├── features/                    # Feature engineering
│   ├── indicators/
│   │   ├── base.py              # Indicator protocol
│   │   ├── momentum.py          # RSI, MACD, etc.
│   │   ├── trend.py             # ADX, MA, etc.
│   │   └── volatility.py        # ATR, Bollinger, etc.
│   └── pipeline.py              # Warmup-aware computation
│
├── strategy/                    # Signal generation
│   ├── base.py                  # Strategy protocol
│   ├── council.py               # Vote aggregation
│   ├── registry.py              # Strategy lifecycle
│   └── builtin/
│       ├── aegean/
│       └── orion/
│
├── risk/                        # Risk management
│   ├── gate.py                  # Entry evaluation
│   ├── sizing.py                # Position sizing (ATR-based)
│   ├── kill_switch.py           # 3-level kill-switch
│   ├── regime.py                # Market regime detection
│   └── performance_guard.py     # DD protection
│
├── broker/                      # Execution layer
│   ├── base.py                  # Broker protocol
│   ├── paper.py                 # Paper trading
│   ├── live/
│   │   ├── ccxt.py              # ccxt wrapper
│   │   └── bingx.py             # BingX-specific
│   └── slippage.py              # Realism models
│
├── evaluation/                  # Backtesting & validation
│   ├── backtest.py              # Offline simulation
│   ├── walk_forward.py          # WF validation
│   ├── counterfactual.py        # "What-if" analysis
│   └── metrics.py               # Performance calculations
│
├── reporting/                   # Output & analysis
│   ├── signal_audit.py
│   ├── performance.py
│   └── visualization.py         # Charts, equity curves
│
└── ops/                         # Operations
    ├── supervisor.py            # Process management
    ├── health.py                # Health checks
    └── alerts.py                # Notification dispatch
```

## 2. Interface Contracts (Critical)

```python
# argus_py/core/protocols.py

from typing import Protocol, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

# ─────────────────────────────────────────────────────────────────────────────
# ENUMS & DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

class Direction(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"

class RiskLevel(Enum):
    NORMAL = "NORMAL"
    SOFT = "SOFT"      # Block new trades
    HARD = "HARD"      # Close positions
    HALT = "HALT"      # Disconnect

@dataclass(frozen=True)
class Bar:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class Signal:
    direction: Direction
    conviction: float  # 0.0 to 1.0
    reason: str
    timestamp: int
    strategy_name: str

@dataclass
class RiskDecision:
    allowed: bool
    level: RiskLevel
    reason: str
    reject_code: Optional[str] = None

@dataclass
class Fill:
    order_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    commission: float
    pnl: float
    timestamp: int
    event: str  # OPEN, CLOSE, REJECTED

# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS (Interfaces)
# ─────────────────────────────────────────────────────────────────────────────

class MarketDataAdapter(Protocol):
    """Interface for all market data sources."""
    
    def fetch_historical(self, symbol: str, start: int, end: int, interval: str) -> List[Bar]: ...
    def fetch_latest(self, symbol: str) -> Optional[Bar]: ...
    def validate(self, bars: List[Bar]) -> tuple[bool, List[str]]: ...

class Strategy(Protocol):
    """Interface for trading strategies."""
    
    name: str
    version: str
    
    def generate_signal(self, features: Dict) -> Signal: ...
    def get_required_features(self) -> List[str]: ...

class RiskGate(Protocol):
    """Interface for risk evaluation."""
    
    def evaluate(self, signal: Signal, state: Dict) -> RiskDecision: ...
    def get_current_level(self) -> RiskLevel: ...

class Broker(Protocol):
    """Interface for order execution."""
    
    def execute(self, symbol: str, direction: Direction, size: float, price: float) -> Fill: ...
    def get_position(self, symbol: str) -> float: ...
    def get_balance(self) -> float: ...
    def close_all(self, price_dict: Dict[str, float]) -> List[Fill]: ...

class Logger(Protocol):
    """Interface for structured logging."""
    
    def log_decision(self, data: Dict) -> None: ...
    def log_trade(self, fill: Fill) -> None: ...
    def log_reject(self, reason: str, detail: Dict) -> None: ...
    def log_error(self, error: Exception, context: Dict) -> None: ...
```

## 3. Deterministic Logging & Reproducibility

### Run Manifest (Every Run)

```yaml
# runs/YYYYMMDD_HHMMSS_hash/manifest.yaml
run_id: "20260207_173000_abc123"
created_at: "2026-02-07T17:30:00+03:00"
git_commit: "a1b2c3d4e5f6"
git_dirty: false

config:
  symbol: "BTCUSDT"
  interval: "1m"
  min_adx: 35.0
  max_exp_move_bps: 80.0
  # ... all parameters

data:
  source: "binance"
  start: "2025-02-07T00:00:00Z"
  end: "2026-02-07T00:00:00Z"
  bars_count: 525600
  checksum: "sha256:abc123..."

seeds:
  numpy: 42
  random: 42

artifacts:
  - decisions.csv
  - trades.csv
  - rejects.csv
  - heartbeat.json
  - metrics.json
```

### Reproducibility Rules

1. **Seed all randomness:** numpy, random, any stochastic components
2. **Version configs:** Every config change = new run
3. **Checksum data:** Validate cached data hasn't changed
4. **Git state:** Record commit hash and dirty status
5. **Immutable runs:** Never modify completed run directories

---

# C. Year-1 Technical Roadmap

## Quarterly Overview

| Quarter | Focus | Exit Criteria |
|---------|-------|---------------|
| **Q1 (Feb-Apr)** | Hardening + Data Integrity | 30 days no crash, all tests green |
| **Q2 (May-Jul)** | Validation + Walk-Forward | 12M WF complete, baseline frozen |
| **Q3 (Aug-Oct)** | Pre-Live + Micro-Live | First live trade, 7 days stable |
| **Q4 (Nov-Jan)** | Scaling + Multi-Agent Maturity | Multi-asset paper, Win laptop integrated |

---

## Q1: Foundation & Hardening (Feb 7 - Apr 30)

### Month 1: Core Stabilization (Feb 7 - Mar 6)

| Week | Objective | Tasks | Files | Tests | Success Criteria |
|------|-----------|-------|-------|-------|------------------|
| 1 | Kill-Switch | Implement 3-level (SOFT/HARD/HALT) | `risk/kill_switch.py` | `test_kill_switch.py` | All 3 levels trigger correctly |
| 2 | Supervisor | Auto-restart, heartbeat, limits | `ops/supervisor.py` | `test_supervisor.py` | Recovery < 60s, max 3 restarts/hr |
| 3 | Data Quality | Gap detection, spike filter | `data/quality/*.py` | `test_data_quality.py` | Zero trades on bad data |
| 4 | Logging | Structured JSON + rotation | `core/logger.py` | `test_logger.py` | Logs queryable, < 100MB/day |

**Expected Artifacts:**
- `Docs/CHANGES/20260207_opus_kill_switch.md`
- `Docs/CHANGES/20260214_opus_supervisor.md`
- `tests/unit/test_kill_switch.py`
- `tests/unit/test_supervisor.py`

### Month 2: Interface Contracts (Mar 7 - Apr 3)

| Week | Objective | Tasks | Files | Tests | Success Criteria |
|------|-----------|-------|-------|-------|------------------|
| 5 | Protocols | Define all interfaces | `core/protocols.py` | Type checking | mypy passes |
| 6 | Broker Abstraction | Paper + Live same interface | `broker/base.py`, `broker/paper.py` | `test_broker.py` | Same tests pass for both |
| 7 | Data Adapter | Abstract data sources | `data/adapters/base.py` | `test_adapters.py` | Binance + mock adapter |
| 8 | Config Cleanup | YAML config, no hardcoding | `config/*.yaml` | Validate on load | No DEFAULT_CONFIG in code |

### Month 3: Testing Infrastructure (Apr 4 - Apr 30)

| Week | Objective | Tasks | Files | Tests | Success Criteria |
|------|-----------|-------|-------|-------|------------------|
| 9 | Unit Tests | Critical math coverage | `tests/unit/test_sizing.py` | 80% coverage on risk/ | All edge cases covered |
| 10 | Integration Tests | GO→OPEN or REJECT | `tests/integration/test_execution.py` | E2E flow | Every GO has trace |
| 11 | Failure Injection | 10 failure scenarios | `tests/failure/*.py` | All pass | System recovers |
| 12 | Replay Determinism | Same input = same output | `verify_determinism.py` | ±0.01% variance | Reproducible |

---

## Q2: Validation & Baseline (May 1 - Jul 31)

### Month 4: Walk-Forward Infrastructure (May)

| Task | Deliverable | Success Metric |
|------|-------------|----------------|
| 12M data backfill | Gapless BTC 1m data | 525,600 bars, 0 gaps |
| Walk-forward runner | `lab/walk_forward.py` v2 | 12M rolling WF completes |
| Metrics framework | Sharpe, DD, PF, WR | All metrics calculate |
| Fee/slippage modeling | Realistic paper fills | Slippage ±1 bps of real |

### Month 5: Baseline Freeze (Jun)

| Task | Deliverable | Success Metric |
|------|-------------|----------------|
| Run 12M walk-forward | `runs/wf_12m_baseline/` | Completes without NO_DATA |
| Document baseline | `Docs/BASELINE_20260601.md` | All metrics recorded |
| External signal overlay | Hirozaki comparison | Benchmark available |
| Freeze commit | Tag `v0.1.0-baseline` | Git tag created |

### Month 6: Alignment Validation (Jul)

| Task | Deliverable | Success Metric |
|------|-------------|----------------|
| 30-day paper run | Continuous paper | 0 crashes |
| Backtest vs paper | `alignment_check.py` | Variance < 5% |
| Rejection analysis | Weekly audit reports | Top-5 reasons documented |
| 90-day paper start | Long-term validation | Running stable |

---

## Q3: Pre-Live & Micro-Live (Aug 1 - Oct 31)

### Month 7: Broker Integration (Aug)

| Task | Deliverable | Success Metric |
|------|-------------|----------------|
| ccxt wrapper | `broker/live/ccxt.py` | Testnet trades work |
| BingX specifics | `broker/live/bingx.py` | Matches manual trades |
| Balance checking | Pre-trade validation | No over-leverage |
| Order lifecycle | Full state machine | All states logged |

### Month 8: Disaster Recovery (Sep)

| Task | Deliverable | Success Metric |
|------|-------------|----------------|
| 5 DR drills | Kill-switch, crash, API, data, network | All < 5min recovery |
| Runbook complete | `Docs/RUNBOOK.md` | Copy-paste commands |
| Go/No-Go checklist | Pre-live validation | 16 items checked |
| Win laptop sync | rsync/SSH setup | Code syncs reliably |

### Month 9: First Live Trade (Oct)

| Task | Deliverable | Success Metric |
|------|-------------|----------------|
| Live account setup | BingX with $30-50 | Account active |
| Micro-live mode | Ultra-small positions | 0.001 BTC max |
| First trade | Via system (not manual) | Fill matches paper |
| 7-day stable | No crashes, fills correct | System survives |

---

## Q4: Scaling & Maturity (Nov 1 - Feb 6, 2027)

### Month 10: Performance Analysis (Nov)

| Task | Deliverable | Success Metric |
|------|-------------|----------------|
| Live vs paper comparison | Variance analysis | < 10% difference |
| Fee impact analysis | Actual vs modeled | Within 20% |
| Slippage calibration | Update model | More realistic |
| Win laptop backtests | Nightly SSH runs | Results sync back |

### Month 11: Multi-Asset Exploration (Dec)

| Task | Deliverable | Success Metric |
|------|-------------|----------------|
| ETH paper trading | Second asset | Running stable |
| SOL exploration | Third asset candidate | Data available |
| Correlation analysis | Cross-asset | Diversification measured |
| Portfolio mode design | Architecture doc | Ready for Q1 2027 |

### Month 12: Year-End Review (Jan 2027)

| Task | Deliverable | Success Metric |
|------|-------------|----------------|
| Year-1 retrospective | `Docs/YEAR1_RETROSPECTIVE.md` | Honest assessment |
| Year-2 roadmap | `Docs/ARGUS_YEAR2_PLAN.md` | Goals defined |
| Codebase cleanup | Remove legacy, .rej files | Clean repo |
| Documentation update | All docs current | No stale info |

---

# D. Test Strategy & Quality Gates

## 1. Test Pyramid

```
                    ┌───────────────┐
                    │   E2E / DR    │   5 tests
                    │   (Monthly)   │
                    └───────┬───────┘
                            │
                ┌───────────┴───────────┐
                │    Integration         │   20 tests
                │    (Weekly)            │
                └───────────┬────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │               Unit Tests               │   100+ tests
        │               (Every commit)           │
        └────────────────────────────────────────┘
```

## 2. Critical Unit Tests Required

| Module | Test File | Critical Cases |
|--------|-----------|----------------|
| `risk/sizing.py` | `test_sizing.py` | ATR calculation, min/max size, leverage |
| `risk/kill_switch.py` | `test_kill_switch.py` | All triggers, recovery, bypass prevention |
| `broker/paper.py` | `test_paper_broker.py` | Slippage, commission, PnL calculation |
| `broker/slippage.py` | `test_slippage.py` | Edge cases, negative prices |
| `core/config.py` | `test_config.py` | Missing keys, type validation |
| `data/quality/*.py` | `test_data_quality.py` | Gap detection, spike filtering |

## 3. Integration Tests

| Test | Purpose | Pass Criteria |
|------|---------|---------------|
| `test_go_produces_trace.py` | Every GO has OPEN or REJECT | 100% coverage |
| `test_full_loop.py` | Data → Signal → Risk → Execution | No silent failures |
| `test_recovery.py` | Crash → Restart → Resume | State preserved |
| `test_determinism.py` | Same run = same output | ±0.01% variance |

## 4. Quality Gates

| Gate | When | Criteria | Blocker? |
|------|------|----------|----------|
| **Unit tests** | Every commit | 100% pass | YES |
| **Type check** | Every commit | mypy clean | YES |
| **Integration** | Every PR | 100% pass | YES |
| **Coverage** | Weekly | > 70% on risk/, broker/ | NO (target) |
| **DR drill** | Monthly | All 5 complete | YES for live scale-up |

---

# E. Operations / Runbook

## 1. Start/Stop Commands

```bash
# ═══════════════════════════════════════════════════════════════════════════
# START DAEMON
# ═══════════════════════════════════════════════════════════════════════════
cd ~/argus-terminal

# Pre-flight
git status                               # Must be clean
python3 -m pytest tests/unit/ -q         # Must pass

# Start supervisor (which manages daemon)
./Scripts/phase19ctl.sh start

# Verify (within 30s)
./Scripts/phase19ctl.sh status
# Expected: "RUNNING" + heartbeat < 60s

# ═══════════════════════════════════════════════════════════════════════════
# STOP DAEMON
# ═══════════════════════════════════════════════════════════════════════════
./Scripts/phase19ctl.sh stop

# Force kill if stuck
./Scripts/phase19ctl.sh halt

# ═══════════════════════════════════════════════════════════════════════════
# RESTART
# ═══════════════════════════════════════════════════════════════════════════
./Scripts/phase19ctl.sh restart

# Force restart (after review)
./Scripts/phase19ctl.sh force-restart --confirm
```

## 2. Monitoring Dashboard

```bash
# Real-time CLI dashboard
./Scripts/phase19_dashboard.sh

# Check heartbeat
cat runs/phase19_twin/SOFT/heartbeat.json | jq '.last_bar_time, .bars_processed'

# Check recent decisions
tail -20 runs/phase19_twin/SOFT/decisions.csv

# Check for rejections
tail -20 runs/phase19_twin/SOFT/rejects.csv

# Check for errors
grep ERROR phase19_daemon.log | tail -10
```

## 3. Disaster Recovery Procedures

### SOFT Recovery (Auto-recoverable)
```bash
# Wait 4 hours OR run:
./Scripts/phase19ctl.sh resume
```

### HARD Recovery (Manual required)
```bash
# 1. Check logs
grep -A5 "KILL_SWITCH HARD" phase19_daemon.log

# 2. Understand root cause
cat runs/phase19_twin/SOFT/daemon_state.json

# 3. If understood, restart
./Scripts/phase19ctl.sh restart
```

### HALT Recovery (Full review required)
```bash
# DO NOT RESTART IMMEDIATELY

# 1. Full log review (minimum 1 hour)
less phase19_daemon.log

# 2. Document incident
echo "Incident: $(date)" >> Docs/INCIDENT_LOG.md

# 3. Wait minimum 24 hours

# 4. Only after review:
./Scripts/phase19ctl.sh force-restart --confirm
```

## 4. Data Management

```bash
# Cleanup old runs (keep last 30 days)
find runs/ -maxdepth 1 -type d -mtime +30 -name "2026*" | xargs rm -rf

# Backup important runs
tar -czf ~/backups/argus_runs_$(date +%Y%m%d).tar.gz \
    runs/phase19_twin \
    runs/wf_12m_baseline

# Never commit large CSVs
echo "runs/**/*.csv" >> .gitignore
echo "runs/**/*.parquet" >> .gitignore
```

## 5. Win Laptop Integration

```bash
# On Mac: Setup SSH key
ssh-keygen -t ed25519 -f ~/.ssh/argus_win

# Add to Win laptop authorized_keys
cat ~/.ssh/argus_win.pub | ssh user@win-laptop "cat >> ~/.ssh/authorized_keys"

# Sync code to Win laptop
rsync -avz --exclude 'runs/' --exclude '.git/' \
    ~/argus-terminal/ user@win-laptop:~/argus-terminal/

# Run nightly backtest on Win (cron on Mac triggers SSH)
ssh user@win-laptop "cd ~/argus-terminal && python3 Scripts/sprint1_walkforward_12m.py"

# Sync results back
rsync -avz user@win-laptop:~/argus-terminal/runs/wf_* ~/argus-terminal/runs/
```

---

# F. Governance / Change Management

## 1. Multi-Agent Workflow

### Agent Signature Format

Every change log must end with:

```markdown
---
## Agent Signature
- **Agent:** Opus-20260207 (or Sonnet/Gemini/Codex)
- **Timestamp:** 2026-02-07T17:30:00+03:00
- **Scope:** `argus_py/risk/kill_switch.py`, `tests/unit/test_kill_switch.py`
- **Tests Run:** `pytest tests/unit/test_kill_switch.py -v` → 12/12 passed
- **Risk:** Kill-switch bypass possible if triggers not tested
- **Rollback:** `git checkout HEAD~1 -- argus_py/risk/kill_switch.py`
```

### Change Log Template

```markdown
# Docs/CHANGES/YYYYMMDD_agent_topic.md

## Summary
[One sentence: what changed and why]

## Files Changed
| File | Action | Lines |
|------|--------|-------|
| `argus_py/risk/kill_switch.py` | CREATE | 150 |
| `tests/unit/test_kill_switch.py` | CREATE | 80 |

## Rationale
[Why this change was needed]

## Commands Run
```bash
pytest tests/unit/test_kill_switch.py -v
./Scripts/phase19ctl.sh status
```

## Expected Outputs
[What should happen when commands are run]

## Rollback Notes
[How to undo if something breaks]

## Agent Signature
[See format above]
```

## 2. End-of-Phase Checklist

```markdown
## Phase XX Completion Checklist

### Code
- [ ] All files committed with clean messages
- [ ] No `.rej` or conflict markers in repo
- [ ] `pytest tests/` passes 100%
- [ ] `mypy argus_py/` has no errors

### Documentation
- [ ] `Docs/PHASES/PHASEXX.md` created/updated
- [ ] `Docs/STATUS.md` updated
- [ ] `Docs/CHANGES/YYYYMMDD_*.md` for each change
- [ ] `CHANGELOG.md` updated

### Artifacts
- [ ] Run artifacts organized in `runs/phaseXX_*/`
- [ ] Metrics documented
- [ ] No large CSVs committed

### Git
- [ ] Commit messages follow: `type(scope): message`
- [ ] PR merged (if applicable)
- [ ] Tag created: `vX.Y.Z-phaseXX`

### Agent Governance
- [ ] All agents left signature
- [ ] No orphan changes

### Next Phase
- [ ] `Docs/PHASES/PHASEXX+1.md` drafted
- [ ] `NEXT.md` updated
```

## 3. Canonical Status Files

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `Docs/STATUS.md` | Global system status | Every phase end |
| `Docs/NEXT.md` | Immediate next actions | Daily |
| `Docs/PHASES/PHASEXX.md` | Phase-specific details | During phase |
| `Docs/CHANGES/*.md` | Individual change logs | Every change |
| `Docs/ARCHITECTURE.md` | System architecture | Monthly |
| `Docs/RUNBOOK.md` | Operations guide | When ops change |
| `Docs/TEST_STRATEGY.md` | Testing approach | Quarterly |

---

# G. Human Benchmark Module (Hirozaki Comparison)

## 1. Data Format

```csv
# Docs/benchmarks/hirozaki_signals.csv
date,time,pair,direction,entry_price,sl_price,tp_price,actual_close,pnl_pct,source
2026-02-07,14:30,BTCUSDT,LONG,97500,96000,100000,99200,1.7,twitter
2026-02-07,18:45,BTCUSDT,SHORT,99200,100500,97000,97500,1.7,twitter
```

## 2. Capture Process (Manual Initially)

```bash
# Add signal entry
./Scripts/add_benchmark_signal.py \
    --trader hirozaki \
    --date 2026-02-07 \
    --pair BTCUSDT \
    --direction LONG \
    --entry 97500 \
    --sl 96000 \
    --tp 100000
```

## 3. Comparison Metrics

| Metric | Argus | Hirozaki | Notes |
|--------|-------|----------|-------|
| Win Rate | X% | Y% | Per period |
| Avg PnL/Trade | X% | Y% | After fees |
| Max Drawdown | X% | Y% | Peak-to-trough |
| Sharpe Ratio | X | Y | Annualized |
| Trade Frequency | X/week | Y/week | Opportunity cost |
| Risk-Adjusted Return | X | Y | Return / Max DD |

## 4. Pitfalls to Avoid

| Pitfall | Mitigation |
|---------|------------|
| **Selection bias** | Only count signals with clear entry/exit, not hindsight |
| **Survivorship** | Track all signals including losses |
| **Leverage normalization** | Normalize to same effective leverage |
| **Timing precision** | Record exact timestamps, not approximate |
| **Fee inclusion** | Apply same fee model to both |

---

# H. Suggestions from Open-Source Repos

## 1. Event-Driven Architecture (from LEAN/Nautilus)

```python
# Event types
@dataclass
class MarketEvent:
    symbol: str
    bar: Bar
    
@dataclass
class SignalEvent:
    signal: Signal
    
@dataclass
class OrderEvent:
    order_id: str
    status: str

# Event bus (simple version)
class EventBus:
    def __init__(self):
        self._handlers: Dict[type, List[Callable]] = {}
    
    def subscribe(self, event_type: type, handler: Callable):
        self._handlers.setdefault(event_type, []).append(handler)
    
    def publish(self, event):
        for handler in self._handlers.get(type(event), []):
            handler(event)
```

**Benefit:** Loose coupling, testable handlers, replay capability.

**When to adopt:** Q2 2026 (after core stability).

## 2. Position Lifecycle (from Freqtrade)

```python
class PositionState(Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    
class Position:
    state: PositionState
    transitions: List[Tuple[datetime, PositionState, str]]
    
    def transition(self, new_state: PositionState, reason: str):
        self.transitions.append((datetime.now(), new_state, reason))
        self.state = new_state
```

**Benefit:** Full audit trail, no ambiguous states.

## 3. Slippage Modeling (from Qlib)

```python
class SlippageModel:
    def calculate(self, price: float, quantity: float, side: str, volume: float) -> float:
        # Impact = k * sqrt(quantity / volume)
        impact = 0.0001 * np.sqrt(quantity / max(volume, 1))
        return price * (1 + impact) if side == "BUY" else price * (1 - impact)
```

**Benefit:** More realistic backtests.

## 4. Walk-Forward Framework (from backtrader)

```python
class WalkForward:
    def run(self, train_months: int, test_months: int, step_months: int):
        results = []
        for train_start, train_end, test_start, test_end in self._generate_windows():
            model = self._train(train_start, train_end)
            metrics = self._test(model, test_start, test_end)
            results.append({
                'train_period': (train_start, train_end),
                'test_period': (test_start, test_end),
                'metrics': metrics
            })
        return results
```

**Benefit:** Systematic validation, no data leakage.

---

# First 7 Days Action Plan

## Day 1 (Feb 7, Friday): Setup & Review

| Time | Task | Command / Output |
|------|------|------------------|
| 09:00 | Read this document thoroughly | - |
| 10:00 | Create canonical status files | See commands below |
| 11:00 | Clean up `.rej` files | `find . -name "*.rej" -delete` |
| 14:00 | Create `Docs/STATUS.md` | Template below |
| 15:00 | Create `Docs/NEXT.md` | Template below |
| 16:00 | Commit governance files | `git add Docs/ && git commit -m "docs: add governance files"` |
| 17:00 | Verify daemon runs | `./Scripts/phase19ctl.sh start && ./Scripts/phase19ctl.sh status` |

```bash
# Create STATUS.md
cat > Docs/STATUS.md << 'EOF'
# ARGUS System Status

**Last Updated:** 2026-02-07  
**Current Phase:** Phase 20  
**System State:** OPERATIONAL

## Active Daemons
- [ ] Phase 19 Paper Daemon: STOPPED

## Recent Metrics
- Paper Run Days: 0
- Crashes (7d): 0
- Last Trade: N/A

## Blockers
- None

## Next Actions
See `NEXT.md`
EOF

# Create NEXT.md
cat > Docs/NEXT.md << 'EOF'
# NEXT: Immediate Actions

**Updated:** 2026-02-07

## Today
1. [ ] Clean `.rej` files
2. [ ] Start paper daemon
3. [ ] Verify heartbeat

## This Week
1. [ ] Implement kill-switch v2
2. [ ] Add unit tests for sizing
3. [ ] Document recovery procedures
EOF
```

## Day 2 (Feb 8, Saturday): Kill-Switch Start

| Time | Task | Command / Output |
|------|------|------------------|
| 09:00 | Create kill_switch.py skeleton | See template |
| 11:00 | Implement SOFT level | Function + test |
| 14:00 | Implement HARD level | Function + test |
| 16:00 | Implement HALT level | Function + test |
| 17:00 | Run tests | `pytest tests/unit/test_kill_switch.py -v` |
| 18:00 | Commit | `git commit -m "feat(risk): implement kill-switch v2"` |

```bash
# Create test file
mkdir -p tests/unit
cat > tests/unit/test_kill_switch.py << 'EOF'
import pytest
from argus_py.risk.kill_switch import KillSwitch, RiskLevel

def test_soft_trigger_on_3pct_loss():
    ks = KillSwitch()
    ks.record_daily_pnl(-0.03)  # 3% loss
    assert ks.get_level() == RiskLevel.SOFT

def test_hard_trigger_on_5pct_loss():
    ks = KillSwitch()
    ks.record_daily_pnl(-0.05)  # 5% loss
    assert ks.get_level() == RiskLevel.HARD

def test_halt_trigger_on_8pct_dd():
    ks = KillSwitch()
    ks.record_total_dd(-0.08)  # 8% DD
    assert ks.get_level() == RiskLevel.HALT
EOF
```

## Day 3 (Feb 9, Sunday): Supervisor Hardening

| Time | Task | Output |
|------|------|--------|
| 09:00 | Add heartbeat monitoring | Lines added to supervisor |
| 11:00 | Add restart counter | 3/hour limit |
| 14:00 | Add graceful shutdown | SIGTERM handling |
| 16:00 | Test crash recovery | Kill and observe restart |
| 17:00 | Document procedures | `Docs/RUNBOOK.md` section |

## Day 4 (Feb 10, Monday): Data Quality

| Time | Task | Output |
|------|------|--------|
| 09:00 | Create `data/quality/validator.py` | Gap detection |
| 11:00 | Add spike filter | Unrealistic price detection |
| 14:00 | Add stale data check | Age > 5min = block |
| 16:00 | Integrate into daemon | Trade blocked on fail |
| 17:00 | Test with bad data | Confirm rejection |

## Day 5 (Feb 11, Tuesday): Logging

| Time | Task | Output |
|------|------|--------|
| 09:00 | Create `core/logger.py` | Structured logging class |
| 11:00 | Add log rotation | 30 days retention |
| 14:00 | Migrate print statements | All use logger |
| 16:00 | Test disk usage | < 100MB/day |
| 17:00 | Document log locations | In RUNBOOK.md |

## Day 6 (Feb 12, Wednesday): Unit Tests

| Time | Task | Output |
|------|------|--------|
| 09:00 | `test_sizing.py` | ATR, min/max size |
| 11:00 | `test_paper_broker.py` | Slippage, commission |
| 14:00 | `test_data_quality.py` | Gap, spike, stale |
| 16:00 | Run full suite | `pytest tests/ -v` |
| 17:00 | Coverage report | `pytest --cov=argus_py` |

## Day 7 (Feb 13, Thursday): Week 1 Wrap

| Time | Task | Output |
|------|------|--------|
| 09:00 | Run paper daemon 4 hours | Observe stability |
| 11:00 | Create change log | `Docs/CHANGES/20260207_opus_week1.md` |
| 14:00 | Update STATUS.md | Current state |
| 15:00 | Update NEXT.md | Week 2 tasks |
| 16:00 | Commit everything | Clean commit |
| 17:00 | Week 1 retro | Document learnings |
| 18:00 | Merge to main | If all green |

---

# Summary: Week 1 Exit Criteria

| Criterion | Target | Actual |
|-----------|--------|--------|
| Kill-switch implemented | 3 levels | ☐ |
| Supervisor hardened | Auto-restart + limits | ☐ |
| Data quality checks | Gap + spike + stale | ☐ |
| Logging structured | JSON + rotation | ☐ |
| Unit tests added | 20+ new tests | ☐ |
| Governance files created | STATUS, NEXT, RUNBOOK | ☐ |
| Paper daemon stable | 4h no crash | ☐ |
| All committed | Clean git status | ☐ |

---

**Document Version:** 1.0  
**Agent:** Claude Opus (Staff+ Systems Architect)  
**Timestamp:** 2026-02-07T17:27:00+03:00  
**Next Review:** End of Week 1 (Feb 13)

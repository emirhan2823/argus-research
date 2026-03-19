# ARGUS Year-1 Technical Masterplan

**Implementation-Ready Operating Plan for Multi-Agent Development**

| Field | Value |
|-------|-------|
| Author | Argus Staff Architect (Opus) |
| Version | 3.0 |
| Date | 2026-02-07T19:26:00+03:00 |
| Status | ACTIVE (Execution Sync Applied: 2026-02-08 09:10 UTC) |

---

# 0. EXECUTION SYNC (AUTHORITATIVE)

> Bu dosyanın altındaki birçok contract/checklist satırı planlama şablonu olarak korunur.  
> Güncel ve otoritatif uygulama durumu: `Docs/DELEGATED_TASKS.md` içindeki `Execution Status Ledger`.

## 0.1 Year-1 Faz Durumu (P20-P24)

| Faz | Durum | Kısa Özet | Kanıt |
|-----|-------|-----------|-------|
| P20 | `✅ DONE` | Telemetry, audit pipeline, kill-switch integration ve ENH1-ENH7 modülleri tamamlandı. | `Docs/DELEGATED_TASKS.md`, `Docs/AGENT_WORK_LOG_P20-005.md`, `Docs/AGENT_WORK_LOG_P20-009_P20-INTEG.md`, `Docs/AGENT_WORK_LOG_P20-ENH1_P20-ENH2_P20-ENH3.md`, `Docs/AGENT_WORK_LOG_P20-ENH4_to_P21-004.md` |
| P21 | `✅ DONE` | Walk-forward, determinism, realism ve CI/packaging (hibrit gate) tamamlandı. | `Docs/DELEGATED_TASKS.md`, `Docs/AGENT_WORK_LOG_P20-ENH4_to_P21-004.md`, `Docs/AGENT_WORK_LOG_P21-003_VERIFY_HYBRID_GATE.md` |
| P22 | `✅ DONE` | Portfolio manager, live broker safety, dashboard ve Chiron learner tamamlandı. | `Docs/DELEGATED_TASKS.md`, `Docs/AGENT_WORK_LOG_P21-003_P22-003_VERIFY_ROUND2.md` |
| P23 | `✅ DONE` | Alerts, backup/restore, profiling, security hardening tamamlandı. | `Docs/DELEGATED_TASKS.md`, `Docs/AGENT_WORK_LOG_P21-003_P22-003_P23-001_P23-004.md` |
| P24 | `✅ DONE` | Multi-exchange adapters, Telegram bot, ML signal model, compliance/reporting tamamlandı. | `Docs/DELEGATED_TASKS.md`, `Docs/AGENT_WORK_LOG_P24-001_P24-003.md`, `Docs/AGENT_WORK_LOG_P24-002_PLUS_REPORT_ENH_AND_LOCAL_TEST.md` |

## 0.2 Yapılamayan / Açık Kalan Kalemler

- Year-1 delegated task setinde `NOT STARTED` kalem kalmadı (`26/26 DONE`).
- Contract dışı operasyon/iyileştirme backlog'u:
  - `SOFT` risk seviyesinde seçici trade politikası kod implementasyonu (plan notu var, kod henüz yok).
  - Full-repo strict `lint-all` temizlik sprinti (hibrit gate aktif; strict temizlik ayrı iş kalemi).
  - Small-live geçişi için uzun paper soak + performans kapısı (operasyonel gate).

---

# 1. TARGET ARCHITECTURE

## 1.1 Module Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ARGUS SYSTEM BOUNDARY                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐  │
│   │    DATA     │────▶│   SIGNAL    │────▶│    RISK     │────▶│   BROKER    │  │
│   │  INGESTION  │     │   ENGINE    │     │   ROUTER    │     │  EXECUTOR   │  │
│   │             │     │             │     │             │     │             │  │
│   │ • Binance   │     │ • Council   │     │ • KillSwitch│     │ • Paper     │  │
│   │ • Cache     │     │ • Aegean    │     │ • Sizing    │     │ • Live      │  │
│   │ • Validate  │     │ • Orion     │     │ • Regime    │     │ • Slippage  │  │
│   └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘  │
│          │                   │                   │                   │          │
│          └───────────────────┴───────────────────┴───────────────────┘          │
│                                      │                                          │
│                                      ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                    TELEMETRY LAYER (Single Source of Truth)              │  │
│   │                                                                          │  │
│   │  decisions.csv │ trades.csv │ rejects.csv │ heartbeat.json │ state.json │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
│          ┌───────────────────────────┼───────────────────────────┐              │
│          ▼                           ▼                           ▼              │
│   ┌─────────────┐            ┌─────────────┐            ┌─────────────┐        │
│   │   AUDIT     │            │  BACKTEST   │            │  DASHBOARD  │        │
│   │  PIPELINE   │            │   ENGINE    │            │    CLI      │        │
│   └─────────────┘            └─────────────┘            └─────────────┘        │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                           SUPERVISOR                                     │  │
│   │              (Health check, restart, kill-switch enforcement)            │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 1.2 Module Ownership

| Module | Path | Owner | Invariants |
|--------|------|-------|------------|
| Data Ingestion | `argus_py/data/` | Codex | No trade on stale (>5min) or gapped data |
| Signal Engine | `argus_py/council/` | Codex | Every call returns valid Verdict |
| Risk Router | `argus_py/risk/` | Codex | Every GO → ALLOW or REJECT with code |
| Broker Executor | `argus_py/broker/` | Codex | Every execute() → Fill or Exception |
| Telemetry | `argus_py/telemetry/` | Codex | Schema validated, atomic writes |
| Audit Pipeline | `argus_py/reporting/` | Sonnet | Weekly reports auto-generated |
| Backtest | `argus_py/lab/` | Codex | Deterministic (same seed → same result) |
| Supervisor | `argus_py/ops/` | Codex | Restarts < 3/hour, heartbeat < 60s |

## 1.3 Telemetry Single Source of Truth

All runtime data flows through these files:

| File | Schema | Update Frequency | Key Invariant |
|------|--------|------------------|---------------|
| `decisions.csv` | See §1.4 | Every bar | One row per bar |
| `trades.csv` | See §1.4 | On execution | Every GO has matching row |
| `rejects.csv` | See §1.4 | On rejection | Every rejection has reason code |
| `heartbeat.json` | See §1.4 | Every 60s | Age < 120s in live mode |
| `daemon_state.json` | See §1.4 | On state change | Equity/positions accurate |

## 1.4 Telemetry Schemas

### decisions.csv

```
timestamp,bar_ts,symbol,verdict,direction,score,adx,exp_move,regime,position_state
```

| Field | Type | Constraint |
|-------|------|------------|
| timestamp | int | Unix epoch ms |
| bar_ts | int | Bar close time |
| symbol | str | e.g., BTCUSDT |
| verdict | enum | GO\|WAIT\|EXIT\|SKIP |
| direction | enum | LONG\|SHORT\|FLAT |
| score | float | 0.0-1.0 |
| adx | float | >= 0 |
| exp_move | float | >= 0 |
| regime | enum | TREND\|CHOP\|UNCERTAIN |
| position_state | enum | FLAT\|LONG\|SHORT |

**Invariant:** If `verdict=GO`, there MUST exist a row in `trades.csv` with matching `bar_ts` where `event` ∈ {OPEN, REJECTED}.

### trades.csv

```
timestamp,symbol,event,side,price,quantity,commission,pnl,position_id,reject_reason
```

| Field | Type | Constraint |
|-------|------|------------|
| event | enum | OPEN\|CLOSE\|REJECTED |
| reject_reason | str | Required if event=REJECTED |

**Invariant:** No row with `event=REJECTED` and empty `reject_reason`.

### rejects.csv

```
timestamp,bar_ts,symbol,code,detail,position_state,risk_level
```

| Field | Type | Valid Values |
|-------|------|--------------|
| code | enum | REJECT_RISK_CAP, REJECT_ALREADY_IN, REJECT_COOLDOWN, REJECT_KILL_SWITCH, REJECT_DATA_QUALITY, REJECT_MIN_SIZE |

### heartbeat.json

```json
{
  "timestamp": 1707312000,
  "last_bar_time": 1707311940,
  "bars_processed": 1500,
  "position_open": true,
  "risk_level": "NORMAL",
  "errors_1h": 0,
  "pid": 12345
}
```

### daemon_state.json

```json
{
  "timestamp": 1707312000,
  "equity": 1025.50,
  "balance": 1000.00,
  "positions": [{"symbol": "BTCUSDT", "side": "LONG", "size": 0.001, "entry": 97500}],
  "kill_switch_level": "NORMAL",
  "consecutive_losses": 0,
  "peak_equity": 1030.00,
  "current_dd_pct": 0.44
}
```

---

# 2. IMPLEMENTATION CONTRACTS

## 2.1 Kill-Switch Contract

**File:** `argus_py/risk/kill_switch.py`

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class RiskLevel(Enum):
    NORMAL = "NORMAL"  # Trading allowed
    SOFT = "SOFT"      # Block new trades, existing run
    HARD = "HARD"      # Close all positions
    HALT = "HALT"      # Disconnect from exchange

@dataclass
class KillSwitchConfig:
    """Configuration for kill-switch triggers."""
    soft_dd_pct: float = 3.0       # Daily loss % to trigger SOFT
    hard_dd_pct: float = 5.0       # Daily loss % to trigger HARD
    halt_dd_pct: float = 8.0       # Total DD % to trigger HALT
    max_consecutive_losses: int = 3 # Losses to trigger SOFT
    max_api_errors: int = 5        # API errors/hour to trigger SOFT
    soft_recovery_hours: float = 4.0
    hard_recovery_hours: float = 24.0

class KillSwitch:
    """
    3-level risk circuit breaker.
    
    INVARIANTS:
    - Level can only increase (NORMAL→SOFT→HARD→HALT) without explicit recovery
    - HALT requires manual confirmation to recover
    - All level changes are logged with reason
    """
    
    def __init__(self, config: KillSwitchConfig) -> None:
        """Initialize with configuration."""
        ...
    
    def check_triggers(self, metrics: dict) -> RiskLevel:
        """
        Evaluate current metrics against trigger thresholds.
        
        Args:
            metrics: {
                'daily_pnl_pct': float,      # e.g., -3.5 for 3.5% loss
                'total_dd_pct': float,       # e.g., -7.0 for 7% drawdown
                'consecutive_losses': int,
                'api_errors_1h': int
            }
        
        Returns:
            Highest triggered RiskLevel
        """
        ...
    
    def activate(self, level: RiskLevel, reason: str) -> None:
        """
        Activate kill-switch at specified level.
        
        Args:
            level: Target level (must be >= current)
            reason: Human-readable reason for activation
        
        Raises:
            ValueError: If level < current level
        """
        ...
    
    def attempt_recovery(self, target_level: RiskLevel, confirm: bool = False) -> bool:
        """
        Attempt to recover to a lower risk level.
        
        Args:
            target_level: Desired level (must be < current)
            confirm: Required True for HALT recovery
        
        Returns:
            True if recovery successful, False if conditions not met
        """
        ...
    
    def get_level(self) -> RiskLevel:
        """Return current risk level."""
        ...
    
    def get_state(self) -> dict:
        """Return full state for serialization."""
        ...
```

**Acceptance Criteria:**
- [ ] SOFT triggers on 3% daily loss
- [ ] HARD triggers on 5% daily loss
- [ ] HALT triggers on 8% total drawdown
- [ ] Level cannot decrease without explicit recovery
- [ ] HALT recovery requires `confirm=True`
- [ ] All transitions logged with timestamp and reason

**Tests Required:** `tests/unit/test_kill_switch.py` (minimum 15 test cases)

---

## 2.2 Telemetry Writer Contract

**File:** `argus_py/telemetry/writer.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import threading

@dataclass
class DecisionRow:
    timestamp: int
    bar_ts: int
    symbol: str
    verdict: str
    direction: str
    score: float
    adx: float
    exp_move: float
    regime: str
    position_state: str

@dataclass
class TradeRow:
    timestamp: int
    symbol: str
    event: str          # OPEN, CLOSE, REJECTED
    side: str
    price: float
    quantity: float
    commission: float
    pnl: float
    position_id: str
    reject_reason: str  # Required if event=REJECTED

@dataclass
class RejectRow:
    timestamp: int
    bar_ts: int
    symbol: str
    code: str           # REJECT_* enum value
    detail: str
    position_state: str
    risk_level: str

class TelemetryWriter:
    """
    Thread-safe, schema-validated telemetry writer.
    
    INVARIANTS:
    - All writes are atomic (no partial rows)
    - Schema validation on every write
    - Heartbeat updates are atomic (write to temp, then rename)
    - Flush guarantees persistence before return
    """
    
    def __init__(self, run_dir: Path) -> None:
        """
        Initialize writer for given run directory.
        Creates CSVs with headers if they don't exist.
        """
        ...
    
    def write_decision(self, row: DecisionRow) -> None:
        """
        Write decision row with schema validation.
        
        Raises:
            ValueError: If any field fails validation
        """
        ...
    
    def write_trade(self, row: TradeRow) -> None:
        """
        Write trade row with schema validation.
        
        INVARIANT: If event=REJECTED, reject_reason must be non-empty.
        
        Raises:
            ValueError: If invariant violated
        """
        ...
    
    def write_reject(self, row: RejectRow) -> None:
        """
        Write rejection row with schema validation.
        
        Raises:
            ValueError: If code not in allowed set
        """
        ...
    
    def update_heartbeat(self, state: dict) -> None:
        """
        Update heartbeat.json atomically.
        
        Writes to .tmp file, then renames to avoid corruption.
        """
        ...
    
    def update_daemon_state(self, state: dict) -> None:
        """Update daemon_state.json atomically."""
        ...
    
    def flush(self) -> None:
        """Force all buffered writes to disk."""
        ...
```

**Acceptance Criteria:**
- [ ] All writes are thread-safe
- [ ] Schema validation catches type errors
- [ ] REJECTED trades without reason raise ValueError
- [ ] Heartbeat writes are atomic (no corruption on crash)
- [ ] flush() guarantees persistence

**Tests Required:** `tests/unit/test_telemetry_writer.py` (minimum 12 test cases)

---

## 2.3 Audit Pipeline Contract

**File:** `argus_py/reporting/audit_pipeline.py`

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from datetime import date

@dataclass
class RejectionBreakdown:
    total_rejects: int
    by_code: Dict[str, int]       # {code: count}
    by_regime: Dict[str, int]     # {regime: count}
    top_5_codes: List[tuple]      # [(code, count), ...]

@dataclass
class ConversionMetrics:
    total_signals: int            # verdict=GO count
    total_opens: int              # event=OPEN count
    total_rejects: int            # event=REJECTED count
    conversion_rate: float        # opens / signals
    by_regime: Dict[str, float]   # {regime: rate}
    by_hour: Dict[int, float]     # {hour: rate}

@dataclass
class WeeklyAuditReport:
    week: str                     # ISO week, e.g., "2026-W06"
    period_start: date
    period_end: date
    
    rejection_breakdown: RejectionBreakdown
    conversion_metrics: ConversionMetrics
    
    # Gate effectiveness
    kill_switch_activations: int
    cooldown_blocks: int
    regime_blocks: int
    
    # Recommendations
    recommendations: List[str]

class AuditPipeline:
    """
    Weekly audit report generator.
    
    Reads telemetry CSVs and produces actionable reports.
    """
    
    def __init__(self, run_dir: Path) -> None:
        """Initialize with run directory containing CSVs."""
        ...
    
    def generate_weekly_report(self, week: str) -> WeeklyAuditReport:
        """
        Generate audit report for specified ISO week.
        
        Args:
            week: ISO week string, e.g., "2026-W06"
        
        Returns:
            Complete audit report
        """
        ...
    
    def to_markdown(self, report: WeeklyAuditReport) -> str:
        """Convert report to markdown format."""
        ...
    
    def to_json(self, report: WeeklyAuditReport) -> str:
        """Convert report to JSON format."""
        ...
```

**Acceptance Criteria:**
- [ ] Reads all CSV files correctly
- [ ] Handles missing files gracefully
- [ ] Rejection breakdown sums to total
- [ ] Conversion rate calculation is correct
- [ ] Recommendations are non-empty

**Tests Required:** `tests/unit/test_audit_pipeline.py` (minimum 10 test cases)

---

# 3. 12-WEEK EXECUTION ROADMAP

## Milestones Overview

| Week | Milestone | Key Deliverable | Gate |
|------|-----------|-----------------|------|
| 1-2 | Kill-Switch v2 | 3-level circuit breaker | All tests pass |
| 3-4 | Telemetry Reliability | Schema-validated writer | GO→trace invariant holds |
| 5-6 | Audit Pipeline | Weekly reporting | Reports generate |
| 7-8 | Walk-Forward Baseline | 12M WF complete | No NO_DATA errors |
| 9-10 | Deterministic Backtest | Reproducible runs | Same seed = same result |
| 11-12 | CI & Packaging | Pre-commit + Makefile | All checks pass |

---

## Week 1-2: Kill-Switch v2

**Objective:** Replace ad-hoc risk checks with formal 3-level kill-switch.

**Deliverables:**

| File | Action | Owner |
|------|--------|-------|
| `argus_py/risk/kill_switch.py` | CREATE | Codex |
| `argus_py/risk/triggers.py` | CREATE | Codex |
| `tests/unit/test_kill_switch.py` | CREATE | Gemini |
| `tests/failure/test_bypass.py` | CREATE | Gemini |
| `Docs/CHANGES/20260207_p20_kill_switch.md` | CREATE | Sonnet |

**Verification Commands:**

```bash
# Unit tests
pytest tests/unit/test_kill_switch.py -v
# Expected: 15+ tests pass

# Bypass attempt test
pytest tests/failure/test_bypass.py -v
# Expected: Bypass blocked

# Integration test
python3 -c "
from argus_py.risk.kill_switch import KillSwitch, KillSwitchConfig, RiskLevel
ks = KillSwitch(KillSwitchConfig())
result = ks.check_triggers({'daily_pnl_pct': -4.0, 'total_dd_pct': -4.0, 'consecutive_losses': 0, 'api_errors_1h': 0})
assert result == RiskLevel.SOFT, f'Expected SOFT, got {result}'
print('PASS: Kill-switch integration')
"
```

**Pass/Fail Gate:**
- [ ] All 15+ unit tests pass
- [ ] Bypass test confirms protection
- [ ] Integration smoke test passes

---

## Week 3-4: Telemetry Reliability

**Objective:** Every GO produces a trace; no silent failures.

**Deliverables:**

| File | Action | Owner |
|------|--------|-------|
| `argus_py/telemetry/writer.py` | CREATE | Codex |
| `argus_py/telemetry/schemas.py` | CREATE | Codex |
| `tests/unit/test_telemetry_writer.py` | CREATE | Gemini |
| `tests/integration/test_go_trace.py` | CREATE | Gemini |
| `Scripts/verify_go_trace.py` | CREATE | Sonnet |

**Verification Commands:**

```bash
# Unit tests
pytest tests/unit/test_telemetry_writer.py -v
# Expected: 12+ tests pass

# Integration test
pytest tests/integration/test_go_trace.py -v
# Expected: All GO decisions have traces

# Verify existing runs
python3 Scripts/verify_go_trace.py runs/phase19_twin/SOFT/
# Expected: "Checked X decisions, 100% have traces"
```

**Pass/Fail Gate:**
- [ ] All unit tests pass
- [ ] verify_go_trace.py shows 100% coverage on test run

---

## Week 5-6: Audit Pipeline

**Objective:** Weekly rejection breakdown and conversion tracking.

**Deliverables:**

| File | Action | Owner |
|------|--------|-------|
| `argus_py/reporting/audit_pipeline.py` | CREATE | Sonnet |
| `Scripts/weekly_audit.py` | CREATE | Sonnet |
| `Docs/templates/weekly_audit.md` | CREATE | Sonnet |
| `tests/unit/test_audit_pipeline.py` | CREATE | Gemini |

**Verification Commands:**

```bash
# Unit tests
pytest tests/unit/test_audit_pipeline.py -v
# Expected: 10+ tests pass

# Generate report
python3 Scripts/weekly_audit.py runs/phase19_twin/SOFT/ --week 2026-W06
# Expected: Markdown report printed
```

**Pass/Fail Gate:**
- [ ] Report generates without errors
- [ ] Rejection counts sum correctly
- [ ] Conversion rate is plausible (0-100%)

---

## Week 7-8: Walk-Forward Baseline

**Objective:** Complete 12-month walk-forward with no errors.

**Deliverables:**

| File | Action | Owner |
|------|--------|-------|
| `argus_py/lab/walk_forward.py` | ENHANCE | Codex |
| `runs/wf_12m_baseline/` | CREATE | Backtest |
| `Docs/BASELINE_20260301.md` | CREATE | Sonnet |

**Verification Commands:**

```bash
# Run walk-forward (on Windows laptop via SSH)
ssh win-laptop "cd ~/argus-terminal && python3 Scripts/sprint1_walkforward_12m.py"
# Expected: 12 windows complete, 0 NO_DATA errors

# Verify results
python3 Scripts/verify_wf_baseline.py runs/wf_12m_baseline/
# Expected: All metrics computed
```

**Pass/Fail Gate:**
- [ ] 12 windows complete
- [ ] Zero NO_DATA errors
- [ ] Sharpe, DD, WR computed

---

## Week 9-10: Deterministic Backtest

**Objective:** Same seed produces identical results.

**Deliverables:**

| File | Action | Owner |
|------|--------|-------|
| `argus_py/lab/determinism.py` | CREATE | Codex |
| `argus_py/lab/manifest.py` | CREATE | Codex |
| `tests/unit/test_determinism.py` | CREATE | Gemini |
| `Scripts/verify_determinism.py` | ENHANCE | Codex |

**Verification Commands:**

```bash
# Run determinism check
python3 Scripts/verify_determinism.py --runs 2
# Expected: "Run 1 vs Run 2: variance 0.00% - DETERMINISTIC"

# Unit tests
pytest tests/unit/test_determinism.py -v
# Expected: All pass
```

**Pass/Fail Gate:**
- [ ] Two runs with same seed produce identical trades.csv
- [ ] Variance reported as 0.00%

---

## Week 11-12: CI & Packaging

**Objective:** Pre-commit hooks, reproducible environment.

**Deliverables:**

| File | Action | Owner |
|------|--------|-------|
| `.pre-commit-config.yaml` | CREATE | Sonnet |
| `Makefile` | CREATE | Sonnet |
| `requirements.txt` | FREEZE | Sonnet |
| `pyproject.toml` | CREATE | Sonnet |

**Verification Commands:**

```bash
# Pre-commit all files
pre-commit run --all-files
# Expected: All pass

# Run via Makefile
make test
# Expected: All tests pass

make install
# Expected: venv created, deps installed
```

**Pass/Fail Gate:**
- [ ] pre-commit passes on all files
- [ ] make test exits 0
- [ ] Fresh clone + make install + make test works

---

# 4. TASK BREAKDOWN TABLE

| Task ID | Description | Owner | Est. | Deps | Definition of Done |
|---------|-------------|-------|------|------|-------------------|
| P20-001 | Kill-switch core class | Codex | 4h | - | Class implements contract |
| P20-002 | Kill-switch triggers | Codex | 2h | P20-001 | All trigger types work |
| P20-003 | Kill-switch tests | Gemini | 3h | P20-001 | 15+ tests pass |
| P20-004 | Kill-switch bypass test | Gemini | 1h | P20-001 | Bypass attempt fails |
| P20-005 | Telemetry writer core | Codex | 4h | - | Class implements contract |
| P20-006 | Telemetry schema validation | Codex | 2h | P20-005 | Invalid data rejected |
| P20-007 | Telemetry writer tests | Gemini | 3h | P20-005 | 12+ tests pass |
| P20-008 | GO-trace verifier | Sonnet | 2h | P20-005 | Script runs correctly |
| P20-009 | Audit pipeline core | Sonnet | 4h | P20-005 | Class implements contract |
| P20-010 | Weekly audit CLI | Sonnet | 2h | P20-009 | Script generates report |
| P20-011 | Audit pipeline tests | Gemini | 3h | P20-009 | 10+ tests pass |
| P21-001 | Walk-forward enhancements | Codex | 6h | - | No NO_DATA errors |
| P21-002 | Determinism module | Codex | 4h | - | Same seed = same result |
| P21-003 | Run manifest writer | Codex | 2h | P21-002 | Manifests created |
| P21-004 | Determinism tests | Gemini | 2h | P21-002 | Tests pass |
| P21-005 | Pre-commit setup | Sonnet | 2h | - | Hooks run |
| P21-006 | Makefile | Sonnet | 2h | - | make test works |
| P21-007 | Requirements freeze | Sonnet | 1h | - | requirements.txt frozen |

---

# 5. COMMIT / MERGE PROTOCOL

## 5.1 Branch Naming

```
<type>/<phase>-<short-description>

Types: feat, fix, refactor, test, docs, chore

Examples:
feat/p20-kill-switch
fix/p20-telemetry-race
test/p20-bypass-prevention
docs/p21-baseline
```

## 5.2 Commit Message Format

```
<type>(<scope>): <short description>

[optional body - wrap at 72 chars]

[optional footer - references, breaking changes]
```

**Examples:**

```
feat(risk): implement 3-level kill-switch

- Add RiskLevel enum with NORMAL/SOFT/HARD/HALT
- Implement trigger evaluation logic
- Add recovery with confirmation for HALT

Refs: P20-001
```

```
fix(telemetry): ensure REJECTED trades have reason

INVARIANT: event=REJECTED requires non-empty reject_reason

Fixes: silent failures in trades.csv
```

## 5.3 Never Commit

Add to `.gitignore` and enforce:

```gitignore
# Large artifacts
runs/**/*.csv
runs/**/*.parquet
runs/2026*/

# Generated
__pycache__/
*.pyc
*.pyo

# Conflicts
*.rej
*.orig

# Logs
*.log
phase*_daemon.log

# Secrets
.env
*.key
secrets/

# OS
.DS_Store
Thumbs.db
```

## 5.4 Pre-Merge Checklist

```markdown
## Pre-Merge Checklist

### Code
- [ ] `git status` clean (no untracked files that should be committed)
- [ ] No `*.rej` files in repo
- [ ] No debug `print()` statements
- [ ] Type hints on all public functions

### Tests
- [ ] `pytest tests/unit/ -v` passes 100%
- [ ] `pytest tests/integration/ -v` passes 100%
- [ ] New code has corresponding tests

### Documentation
- [ ] `Docs/STATUS.md` updated with current state
- [ ] `Docs/CHANGES/<date>_<phase>.md` created
- [ ] Agent Work Log complete with signature
- [ ] `CHANGELOG.md` entry added

### Verification
- [ ] Paper daemon starts: `./Scripts/phase19ctl.sh start`
- [ ] Status shows healthy: `./Scripts/phase19ctl.sh status`
- [ ] Heartbeat recent: `cat runs/phase19_twin/SOFT/heartbeat.json`

### Final
- [ ] Commit messages follow convention
- [ ] Branch rebased on main (no merge commits)
- [ ] PR description explains changes
```

## 5.5 Phase-End Checklist

```markdown
## Phase XX Complete Checklist

### Code Deliverables
- [ ] All planned files created/modified
- [ ] All contracts implemented per spec
- [ ] All tests written and passing

### Quality Gates
- [ ] Unit test coverage > 70% on new code
- [ ] Integration tests pass
- [ ] No regressions in existing tests

### Documentation
- [ ] Docs/PHASES/PHASE_XX.md complete
- [ ] All Agent Work Logs filed
- [ ] CHANGELOG.md updated

### Git
- [ ] All branches merged to main
- [ ] Tag created: `v0.X.0-phaseXX`
- [ ] No orphan branches

### Operational
- [ ] Paper daemon runs 4+ hours without crash
- [ ] Heartbeat updates every 60s
- [ ] No errors in last hour of logs
```

---

# 6. REPO ORIENTATION

## 6.1 Start Here

> **New to Argus? Read this first.**

Argus is a trading research and execution system. Key principles:

1. **Correctness > Speed** - We run long tests, we don't skip validation
2. **Observability** - Everything is logged, nothing fails silently
3. **Multi-Agent** - Multiple AI agents collaborate, each leaves work logs

### Quick Start

```bash
# Clone and setup
git clone <repo>
cd argus-terminal
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run paper daemon
./Scripts/phase19ctl.sh start

# Check status
./Scripts/phase19ctl.sh status

# View dashboard
python3 Scripts/phase19_dashboard.py runs/phase19_twin/SOFT/

# Stop daemon
./Scripts/phase19ctl.sh stop
```

### Directory Structure

| Directory | Purpose |
|-----------|---------|
| `argus_py/` | Core library (don't run directly) |
| `Scripts/` | Executable scripts |
| `tests/` | Test suite |
| `Docs/` | Documentation |
| `runs/` | Runtime artifacts (not committed) |

## 6.2 Top 10 Critical Files

| # | File | Purpose | Look Here For |
|---|------|---------|---------------|
| 1 | `Scripts/paper_daemon.py` | Main trading daemon | Execution loop, bar processing |
| 2 | `argus_py/broker/paper.py` | Paper broker | Position tracking, fills, slippage |
| 3 | `argus_py/risk/sizing.py` | Position sizing | ATR calculation, risk percentages |
| 4 | `argus_py/risk/state_machine.py` | Trading state | Cooldown, consecutive losses |
| 5 | `argus_py/council/router.py` | Signal aggregation | Strategy voting, verdict |
| 6 | `Scripts/phase19ctl.sh` | Daemon control | Start/stop/status commands |
| 7 | `Scripts/phase19_supervisor.py` | Health monitoring | Restart logic, heartbeat |
| 8 | `argus_py/risk/regime.py` | Market regime | ADX thresholds, TREND/CHOP |
| 9 | `argus_py/data/adapters/` | Data sources | Binance API, caching |
| 10 | `Docs/STATUS.md` | Current state | What's working, what's broken |

## 6.3 Where to Find...

| If you need... | Look in... |
|----------------|------------|
| Risk sizing logic | `argus_py/risk/sizing.py` |
| Execution flow | `Scripts/paper_daemon.py:process_bar()` |
| Telemetry writes | `Scripts/paper_daemon.py:append_*()` |
| Strategy signals | `argus_py/council/router.py` |
| Kill-switch (new) | `argus_py/risk/kill_switch.py` |
| Weekly reports | `argus_py/reporting/audit_pipeline.py` |

---

# 7. FEES / REALISM PLAN

## 7.1 Exchange Fee Model

| Exchange | Taker Fee | Maker Fee | Funding (8h) |
|----------|-----------|-----------|--------------|
| Binance Futures | 0.040% | 0.020% | Variable (~0.01%) |
| BingX | 0.040% | 0.020% | Variable |

**Implementation in `argus_py/broker/paper.py`:**

```python
# Current implementation
commission = quantity * price * 0.0004  # 0.04% taker

# Enhanced (to implement)
TAKER_FEE_BPS = 4.0  # 0.04%
MAKER_FEE_BPS = 2.0  # 0.02%
FUNDING_RATE_BPS = 1.0  # Estimated average

def calculate_commission(quantity: float, price: float, is_taker: bool = True) -> float:
    fee_bps = TAKER_FEE_BPS if is_taker else MAKER_FEE_BPS
    return quantity * price * (fee_bps / 10000)

def calculate_funding(position_value: float, hours_held: float) -> float:
    funding_periods = hours_held / 8.0
    return position_value * (FUNDING_RATE_BPS / 10000) * funding_periods
```

## 7.2 Slippage Model

```python
# Current implementation
SLIPPAGE_BPS = 2.0  # 0.02%

# Enhanced (to implement)
def calculate_slippage(price: float, quantity: float, side: str, volume_24h: float) -> float:
    """
    Market impact model:
    - Base slippage: 2 bps
    - Size impact: sqrt(quantity / avg_trade_size) * 1 bps
    - Volatility adjustment: ATR-based
    """
    base_slip = price * (2.0 / 10000)
    size_impact = price * (1.0 / 10000) * np.sqrt(quantity * price / 1000)
    return base_slip + size_impact
```

## 7.3 Validation Against Real Trades

**Protocol:**

1. Execute 5-10 micro trades ($5-10 each) on real exchange
2. Record: intended price, actual fill price, commission charged
3. Compare to paper model predictions
4. Adjust constants if systematic deviation > 20%

**Data Collection:**

```csv
# Docs/benchmarks/real_fills.csv
timestamp,symbol,side,intended_price,fill_price,quantity,commission_expected,commission_actual,slip_model,slip_actual
```

**Validation Script (to create):**

```bash
python3 Scripts/validate_realism.py Docs/benchmarks/real_fills.csv
# Output:
# Slippage: Model avg 2.1 bps, Actual avg 1.8 bps - OK
# Commission: Model avg 4.0 bps, Actual avg 4.0 bps - OK
# Funding: Model avg 1.0 bps/8h, Actual avg 0.8 bps/8h - OK
```

## 7.4 Funding Rate Considerations

- Funding is charged every 8 hours (00:00, 08:00, 16:00 UTC)
- Positive rate = longs pay shorts
- Negative rate = shorts pay longs

**Paper model should:**
1. Track position hold time
2. Apply funding at 8h intervals
3. Use historical average rate (0.01% = 1 bps)

**Not optimizing to noise:**
- Do NOT tune slippage/fees to match specific trades
- Use historical averages over 30+ trades
- Accept 10-20% variance as normal

---

# 8. HARDWARE SYNC PROTOCOL

## 8.1 Mac ↔ Windows Sync

**Mac (Control Tower):**
- Runs 24/7
- Hosts paper daemon, supervisor, dashboards
- Maintains canonical repo state

**Windows (Backtest Runner):**
- Available nights + weekends
- Runs heavy walk-forward, grid search
- Results synced back to Mac

**Sync Commands:**

```bash
# Mac → Windows (code only, no artifacts)
rsync -avz --exclude 'runs/' --exclude '__pycache__/' --exclude '*.pyc' \
    --exclude '.git/' --exclude 'venv/' \
    ~/argus-terminal/ user@win-laptop:~/argus-terminal/

# Windows → Mac (results only)
rsync -avz user@win-laptop:~/argus-terminal/runs/wf_* ~/argus-terminal/runs/

# Quick sync (SSH)
ssh win-laptop "cd ~/argus-terminal && git pull"
```

## 8.2 Nightly Backtest Cron

On Mac, schedule nightly run:

```bash
# /etc/crontab or crontab -e
0 2 * * * /Users/$(whoami)/argus-terminal/Scripts/nightly_backtest.sh
```

**nightly_backtest.sh:**

```bash
#!/bin/bash
# Sync code to Windows
rsync -avz --exclude 'runs/' ~/argus-terminal/ win-laptop:~/argus-terminal/

# Run backtest on Windows
ssh win-laptop "cd ~/argus-terminal && python3 Scripts/sprint1_walkforward_12m.py"

# Sync results back
rsync -avz win-laptop:~/argus-terminal/runs/wf_* ~/argus-terminal/runs/
```

---

**Document End**

| Metadata | Value |
|----------|-------|
| Maintained by | Argus Staff Architect (Opus) |
| Review cycle | Weekly |
| Next review | 2026-02-14 |

# Delegated Task Definitions

Bu dosya, diğer agentlara (Codex/Gemini/Sonnet) delegate edilecek task tanımlarını içerir.

---

## P20-005: Telemetry Writer ✅ DONE

**Assign to:** Codex  
**Priority:** P0  
**Completed:** 2026-02-07  
**Commit:** `240d9b9`

### Objective
Create a thread-safe, schema-validated telemetry writer for decisions, trades, and rejects.

### Contract (implement exactly)

**File:** `argus_py/telemetry/writer.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class DecisionRow:
    timestamp: int
    bar_ts: int
    symbol: str
    verdict: str      # GO|WAIT|EXIT|SKIP
    direction: str    # LONG|SHORT|FLAT
    score: float
    adx: float
    exp_move: float
    regime: str       # TREND|CHOP|UNCERTAIN
    position_state: str

@dataclass
class TradeRow:
    timestamp: int
    symbol: str
    event: str        # OPEN|CLOSE|REJECTED
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
    code: str         # REJECT_* enum
    detail: str
    position_state: str
    risk_level: str

class TelemetryWriter:
    def __init__(self, run_dir: Path) -> None: ...
    def write_decision(self, row: DecisionRow) -> None: ...
    def write_trade(self, row: TradeRow) -> None: ...
    def write_reject(self, row: RejectRow) -> None: ...
    def update_heartbeat(self, state: dict) -> None: ...
    def flush(self) -> None: ...
```

### Invariants
1. Schema validation: `event=REJECTED` requires non-empty `reject_reason`
2. Heartbeat writes must be atomic (write temp, then rename)
3. Thread-safe (use threading.Lock)
4. Create CSVs with headers if don't exist

### Acceptance Criteria
- [x] All writes validate schema
- [x] REJECTED trades without reason raise ValueError
- [x] Heartbeat.json never corrupted on crash
- [x] Thread-safe under concurrent access (8 threads, 50 writes each)

### Verification ✅
```bash
pytest tests/unit/test_telemetry_writer.py -v
# Result: 12 tests passed (383 lines of tests)
```

### Files to Create
1. `argus_py/telemetry/writer.py`
2. `argus_py/telemetry/schemas.py` (optional, for validation)
3. `tests/unit/test_telemetry_writer.py`

---

## P20-009: Audit Pipeline ✅ DONE

**Assign to:** Codex  
**Priority:** P1  
**Completed:** 2026-02-07  
**Commit:** `240d9b9`

### Objective
Create weekly audit report generator that analyzes rejections and conversion rates.

### Contract (implement exactly)

**File:** `argus_py/reporting/audit_pipeline.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from datetime import date

@dataclass
class RejectionBreakdown:
    total_rejects: int
    by_code: Dict[str, int]       # {code: count}
    by_regime: Dict[str, int]
    top_5_codes: List[tuple]      # [(code, count), ...]

@dataclass
class ConversionMetrics:
    total_signals: int            # verdict=GO count
    total_opens: int              # event=OPEN count
    total_rejects: int            # event=REJECTED count
    conversion_rate: float        # opens / signals
    by_regime: Dict[str, float]   # {regime: rate}

@dataclass
class WeeklyAuditReport:
    week: str                     # e.g., "2026-W06"
    period_start: date
    period_end: date
    rejection_breakdown: RejectionBreakdown
    conversion_metrics: ConversionMetrics
    kill_switch_activations: int
    recommendations: List[str]

class AuditPipeline:
    def __init__(self, run_dir: Path) -> None: ...
    def generate_weekly_report(self, week: str) -> WeeklyAuditReport: ...
    def to_markdown(self, report: WeeklyAuditReport) -> str: ...
    def to_json(self, report: WeeklyAuditReport) -> str: ...
```

### Acceptance Criteria
- [x] Reads decisions.csv, trades.csv, rejects.csv
- [x] Handles missing files gracefully
- [x] Rejection counts sum correctly
- [x] Markdown output is readable

### Verification ✅
```bash
pytest tests/unit/test_audit_pipeline.py -v
# Result: 189 lines of tests passed
```

### Files to Create
1. `argus_py/reporting/audit_pipeline.py`
2. `Scripts/weekly_audit.py` (CLI wrapper)
3. `tests/unit/test_audit_pipeline.py`

---

## P20-INTEG: Kill-Switch Integration ✅ DONE

**Assign to:** Codex  
**Priority:** P0  
**Completed:** 2026-02-07  
**Commit:** `240d9b9`

### Objective
Integrate the new kill-switch into paper_daemon.py

### Changes Required

**File:** `Scripts/paper_daemon.py`

1. Import kill-switch:
```python
from argus_py.risk.kill_switch import KillSwitch, KillSwitchConfig, check_and_activate
```

2. Initialize in `PaperDaemon.__init__`:
```python
self.kill_switch = KillSwitch(KillSwitchConfig(
    soft_daily_loss_pct=self.cfg["daily_loss_limit_pct"],
    halt_dd_pct=self.cfg["kill_switch_dd_pct"]
))
```

3. Check before execution in `process_bar`:
```python
metrics = {
    'daily_pnl_pct': daily_pnl_pct,
    'total_dd_pct': current_dd_pct,
    'consecutive_losses': self.consecutive_losses,
    'api_errors_1h': self.api_errors_1h
}
level = check_and_activate(self.kill_switch, metrics)

if not self.kill_switch.can_trade():
    self.append_reject(bar, "REJECT_KILL_SWITCH", f"Level: {level.value}")
    return
```

4. Save state on shutdown:
```python
self.kill_switch.save_state(self.run_dir / "kill_switch_state.json")
```

### Acceptance Criteria
- [x] Kill-switch state persists across restarts
- [x] SOFT blocks new trades
- [x] HARD closes all positions (call broker.close_all)
- [x] REJECT_KILL_SWITCH appears in rejects.csv
- [x] Level visible in heartbeat.json

### Verification ✅
```bash
pytest tests/unit/test_paper_daemon_kill_switch_integration.py -v
# Result: 4 integration tests passed (92 lines)
```

---

## Agent Work Log Template

Her agent tamamladığında bu formatı kullanmalı:

```markdown
# Agent Work Log

## Metadata
- **Agent:** [Codex/Gemini/Sonnet]
- **Task ID:** [P20-XXX]
- **Date:** YYYY-MM-DD HH:MM UTC
- **Duration:** Xh Xm

## Files Changed
| File | Action | Lines |
|------|--------|-------|
| path/file.py | CREATE | 150 |

## Verification
\`\`\`bash
[commands run + output]
\`\`\`

## Risks / Follow-ups
- [Any issues encountered]

---
**Agent Signature:** [Agent] @ [Timestamp]
```

# Phase 20: Signal Quality & Audit

**Status:** IN PROGRESS  
**Started:** 2026-02-07  
**Target:** 1 week

## Deliverables

### P20.1: Signal Audit Pipeline ✅
- [x] `argus_py/reporting/signal_audit.py` - Core audit module
- [x] `Scripts/phase20_signal_audit.py` - CLI runner
- [x] SignalStats, GateStats, AuditReport dataclasses
- [x] Rejection reason breakdown
- [x] Gate effectiveness tracking
- [x] Markdown report generation

### P20.2: Risk Improvements ✅
- [x] ATR-based stop calculator (`sizing.py`)
- [x] Tightened DD limits (8%/5%)
- [x] Progressive cooldown (5/15/50 bars)
- [x] Entry quality scorer (`entry_quality.py`)
- [x] Regime filter tightened (ADX>28)

### P20.3: Diagnostics Enhancement
- [ ] Rejection reason visualization
- [ ] Score distribution charts
- [ ] Gate tuning recommendations

### P20.4: Baseline Freeze
- [ ] Full 12M walk-forward (no NO_DATA)
- [ ] Performance baseline document
- [ ] External signal overlay validation

## New Files Created

| File | Purpose |
|------|---------|
| `argus_py/reporting/signal_audit.py` | Core audit module |
| `argus_py/risk/entry_quality.py` | Entry quality scorer |
| `Scripts/phase20_signal_audit.py` | Audit CLI |
| `Docs/ARGUS_ARCHITECTURE_V2.md` | Platform architecture |

## Risk Parameters Updated

| Parameter | Before | After |
|-----------|--------|-------|
| DD Lockdown | 15% | 8% |
| DD Defensive | 8% | 5% |
| Cooldown (1 loss) | 3 bars | 5 bars |
| Cooldown (2 loss) | - | 15 bars |
| Cooldown (3+ loss) | - | 50 bars |
| ADX TREND threshold | 25 | 28 |

## Commands

```bash
# Run signal audit on session
python3 Scripts/phase20_signal_audit.py runs/phase19_twin/soft

# Run with JSON output
python3 Scripts/phase20_signal_audit.py runs/session --json

# Save report to file
python3 Scripts/phase20_signal_audit.py runs/session -o audit_report.md
```

## Next: P20.3 & P20.4
1. Add visualization for rejection reasons
2. Run full 12M walk-forward
3. Freeze performance baseline

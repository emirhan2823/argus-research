# ARGUS Decision Log

## 2026-02-10 — Sprint A Integration Hardening

### DL-001: External market-intelligence feeds in `MODE=v2`
- Context: `FUTURE_VISION` expects AETHER/HERMES to consume external macro/news feeds, but paper runtime must remain deterministic and offline-safe.
- Decision: In Sprint A, `MODE=v2` defaults to **offline-safe proxy inputs** for AETHER/HERMES; external fetch remains opt-in for later sprint.
- Rationale: Prevent runtime instability/network coupling while wiring modules into production pipeline.

### DL-002: Execution v2 integration without breaking legacy flow
- Context: Existing `PaperBroker` execution path is stable and already used by current soak flow.
- Decision: `ExecutionEngineV2` is integrated behind `MODE=v2` via adapter/gateway over `PaperBroker`; `MODE=legacy` path remains unchanged.
- Rationale: Adapter pattern preserves working core while enabling measurable v2 behavior.

### DL-003: Regime naming mismatch (`v2` vs legacy council)
- Context: v2 regime labels (`BULL_TREND`, `BEAR_TREND`, `HIGH_VOL_CHOP`, `LOW_VOL_CALM`) differ from legacy council labels.
- Decision: Add explicit mapping layer in v2 runtime bridge (`BULL/BEAR -> TREND`, `HIGH_VOL_CHOP -> CHOP`, `LOW_VOL_CALM -> RANGE`).
- Rationale: Enables immediate integration with existing council/risk modules without destructive refactor.

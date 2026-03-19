# Phase 16 Acceptance Criteria

## Phase 15: Determinism Validation
- **Requirement**: Two consecutive executions of the same backtest pack with the same date range and friction settings must produce **identical** results.
- **Metric**:
    - `TradeHash` (SHA1 of Entry/Exit/Price/PnL) must match exactly per scenario.
    - `PositionId` must remain stable (derived from trade parameters, not random).
- **Status**: **PASS**
    - Verified by `scripts/verify_determinism.py`.
    - Report: `runs/phase15_determinism_report.md`.

## Phase 16: Parameter Sensitivity
- **Requirement**: Changing critical strategy parameters (`min_adx`, `max_exp_move_bps`) must produce **distinct** trade sets.
- **Metric**:
    - Intersection of trades between `Baseline` (neutral settings) and `Variants` (active filters) must be `< Total Trades`.
    - Fingerprints must differ.
- **Status**: **PENDING**
    - `cli.py` defaults updated to neutral (`min_adx=0`).
    - Divergence Check script: `scripts/pack_divergence_check.py`.
    - Pass Criteria: `pack_divergence_check.py` returns Exit Code 0.

## Grid Runner
- A grid search over `min_adx` (20, 35, 50) and `max_exp` (40, 80) must produce diverse PnL and trade counts, proving the engine is responsive to tuning.

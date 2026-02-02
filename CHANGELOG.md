
# Changelog

## [v0.5-AdxGate] - 2026-02-02
### Added
- **AdxGate Strategy**: Systematic Trend filtering (`min_adx=45.0`). Replaces manual "Sell Only" bias.
- **Production Guards**: Explicit logging of Regime, ADX, and Gating status in CLI loops.
- **Robustness Suite**: Tools for Temporal, Cross-Asset, and Parameter sweeps (`scripts/sweep_*.sh`).
- **Safety**: `max_exp_move_bps=80.0` default to cap outlier expectations.

### Changed
- **CLI Defaults**: Updated to V5 standard (ADX 45).
- **Reporting**: Added `Avg ADX` and `Regime Distribution` to daily reports.

### Removed
- **Legacy Experiments**: Deprecated `disable_buy` (V1) and experimental logic.

## [v0.4-Combo] - 2026-02-01
- Implemented Phase 3 "Combo" strategy (Sell + MaxExp).
- Added VolTrap V2 (Smart/Conditional).

## [v0.3-Baseline] - 2026-01-30
- Initial Adaptive Baseline.

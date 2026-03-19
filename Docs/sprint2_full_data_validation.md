# Sprint-2 Full-Data Validation

**Generated:** 2026-02-07 03:51 (+03)

## 1) Data Backfill
- Command:
  - `python3 Scripts/sprint2_backfill_btc_cache.py --symbol BTCUSDT --start_date 2024-07-01 --end_date 2025-02-01 --data_dir argus_py/data/cache --skip_existing`
- Result:
  - `BACKFILL_SUMMARY windows=7 downloaded=3 skipped=4 failed=0`

## 2) Full-Data Walk-Forward
- Command:
  - `python3 Scripts/sprint1_walkforward_12m.py --symbol BTCUSDT --asset_class crypto --market_adapter auto --data_dir argus_py/data/cache --start_balance 30 --start_date 2024-02-01 --months 12 --window_timeout_sec 1800 --portfolio_allocator_v1 --portfolio_risk_budget_pct 1.0 --portfolio_max_asset_exposure_pct 35 --portfolio_assumed_stop_loss_pct 2.0 --min_adx 25 --min_expected_move_bps 4 --cost_safety_factor 2.0 --cost_safety_homerun 1.3 --fee_bps 4 --slippage_bps 2 --spread_bps 1`
- Result:
  - `WF12M_SUMMARY windows=12 positive_windows=3 avg_return_pct=-0.2898 compounded_return_pct=-3.4860 avg_max_drawdown_pct=35.9173`
- Artifacts:
  - `runs/sweeps/walkforward_12m_20260207_030424.csv`
  - `runs/sweeps/walkforward_12m_20260207_030424.md`

## 3) External Signal Overlay
- Added module:
  - `argus_py/signals/external.py`
- CLI flags:
  - `--external_signal_file`
  - `--external_signal_max_age_min`
  - `--external_signal_conviction_boost`
  - `--external_signal_block_confidence`
  - `--external_signal_enforce_alignment`
- Policy:
  - external sinyal sadece overlay'dir; hard risk kurallari ve portfolio allocator ustundur.

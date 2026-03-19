# Sprint-2 Plan (Execution + Alternative Signals)

**Window:** 2026-02-07 -> 2026-02-21  
**Goal:** Full-data validation + external information overlay (news + trader feed).

## Track A: Data Completeness
1. Fill missing BTC cache windows (`2024-07-01 -> 2025-02-01`) with monthly files.
2. Re-run 12M walk-forward with full data (no `NO_DATA` windows).
3. Compare full-data metrics against Sprint-1 smoke baseline.

### Commands
- Backfill:
  - `python3 Scripts/sprint2_backfill_btc_cache.py --symbol BTCUSDT --start_date 2024-07-01 --end_date 2025-02-01 --data_dir argus_py/data/cache --skip_existing`
- Full walk-forward:
  - `python3 Scripts/sprint1_walkforward_12m.py --symbol BTCUSDT --asset_class crypto --market_adapter auto --data_dir argus_py/data/cache --start_balance 30 --start_date 2024-02-01 --months 12 --window_timeout_sec 1800 --portfolio_allocator_v1 --portfolio_risk_budget_pct 1.0 --portfolio_max_asset_exposure_pct 35 --portfolio_assumed_stop_loss_pct 2.0 --min_adx 25 --min_expected_move_bps 4 --cost_safety_factor 2.0 --cost_safety_homerun 1.3 --fee_bps 4 --slippage_bps 2 --spread_bps 1`

## Track B: External Signal Overlay (News + Trader)
1. Add external signal ingestion layer from CSV.
2. Integrate into `cli.py` decision stage:
  - aligned signal -> conviction boost
  - opposite high-confidence signal -> optional block
3. Keep hard risk guardrails and portfolio allocator as final authority.

### External Signal File Format
- Columns:
  - `timestamp,symbol,source,direction,confidence,note`
- Example template:
  - `python3 Scripts/sprint2_make_external_signal_template.py`

## Track C: Ops / Observability
1. Keep daemon and kill-switch path stable while adding external overlay.
2. Add staged rollout:
  - Stage-1: `external_signal_enforce_alignment=off` (observe only)
  - Stage-2: enable alignment block only for high confidence (`>=0.75`)

## Risk Policy (Non-Negotiable)
- External sources are **assistive**, not authority.
- No direct auto-copy of a single trader without model/risk confirmation.
- If external signal conflicts with hard stops, hard stops always win.

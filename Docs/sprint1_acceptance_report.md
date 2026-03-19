# Sprint-1 Acceptance Report

**Generated:** 2026-02-07 02:36 (+03)

## Scope
- Target: Sprint-1 acceptance criteria for `12M rolling validation + adapter separation`.
- Run command:
  - `python3 Scripts/sprint1_walkforward_12m.py --symbol BTCUSDT --asset_class crypto --market_adapter auto --data_dir argus_py/data/cache --start_balance 30 --start_date 2024-02-01 --months 12 --max_bars 500 --window_timeout_sec 180 --portfolio_allocator_v1 --portfolio_risk_budget_pct 1.0 --portfolio_max_asset_exposure_pct 35 --portfolio_assumed_stop_loss_pct 2.0 --min_adx 25 --min_expected_move_bps 4 --cost_safety_factor 2.0 --cost_safety_homerun 1.3 --fee_bps 4 --slippage_bps 2 --spread_bps 1`

## Artifacts
- `runs/sweeps/walkforward_12m_20260207_023547.csv`
- `runs/sweeps/walkforward_12m_20260207_023547.md`

## Criteria Check
1. `Tek komutla 12M rolling backtest calisir`
- Status: `PASS`
- Evidence: 12 pencere tamamlandi, script exit code `0`.

2. `Rapor su alanlari verir: return, max drawdown, trades, profit factor, compounded return`
- Status: `PASS`
- Evidence: MD/CSV artifactlarda window bazli `total_return_pct`, `max_drawdown_pct`, `total_trades`, `profit_factor` ve aggregate `compounded_return_pct` bulunuyor.

3. `Adapter katmani ile strateji motoru veri kaynagindan ayrisir`
- Status: `PASS`
- Evidence: `argus_py/adapters/` factory uzerinden market yukleme aktif; adapter testleri gecti.

## Important Notes
- `2024-08` ve sonrasi pencerelerde cache kapsaminda veri olmadigi icin `status=NO_DATA` raporlandi.
- Bu acceptance kosusu hizli dogrulama modundadir (`max_bars=500`).

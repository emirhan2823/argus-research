# Argus Hedge Fund Roadmap & Sprint Board

**Last Update:** 2026-02-07 03:51 (+03)  
**Status:** `ACTIVE`  
**Owner:** Emirhan + Codex

## 1) Mission
Single-market bot yerine, kripto + hisse + ETF + emtia gibi varlıklarda çalışan moduler bir "multi-asset yatırım isletim sistemi" kurmak.

## 2) Reality Check (Non-Negotiable)
- `%90 win-rate` hedefi yerine `risk-adjusted return` hedeflenir.
- Ana KPI seti:
  - `Net Return (cost sonrası)`
  - `Max Drawdown`
  - `Profit Factor`
  - `Sharpe/Sortino`
  - `Walk-forward stability`
- Kural: Sistem kanitlanmadan leverage artmaz.

## 3) Current Baseline (Known)
- 5 aylik walk-forward (2024-02 -> 2024-07):
  - `avg_return_pct`: `+0.7094`
  - `compounded_return_pct`: `+3.5622`
  - `positive_windows`: `3/5`
  - `avg_max_dd_pct`: `21.9885` (yuksek, iyilestirilmeli)
- Reference CSV:
  - `runs/sweeps/walkforward_small30_monthly_20260207_002637.csv`

## 4) Roadmap Phases

| Phase | Scope | Exit Criteria |
|---|---|---|
| P0 | Risk foundation + paper stability | Hard stops aktif, reject/fill loglari temiz, testler yesil |
| P1 | Multi-market data/broker adapter iskeleti | En az 3 market adapter (crypto/us/bist mock) |
| P2 | Portfolio allocator v1 | Risk budget ile varliklar arasi dagitim |
| P3 | 12M walk-forward automation | Tek komutla aylik rolling rapor |
| P4 | 24/7 paper + observability | Heartbeat/restart/alert akisi stabil |
| P5 | Small-cap live pilot | Kucuk sermaye, sabit risk, strict guardrails |

## 5) Sprint Cadence
- Sprint suresi: `2 hafta`
- Ritm:
  - Gunluk: kisa status + blocker
  - Sprint sonu: KPI review + karar (devam/pivot)
- Definition of Done (global):
  - Kod + test + run artifact + karar notu

## 6) Sprint Board

### Sprint-0 (Completed)
**Window:** 2026-02-06 -> 2026-02-07  
**Goal:** Small account risk guvenligi ve temel stabilite.

- [x] `SMALL` profile leverage cap `1.0x` yapildi.
- [x] Execution risk broker hard cap ile hizalandi.
- [x] Float-boundary `REJECT_RISK_CAP` false positive fix.
- [x] Backtest hard barriers eklendi:
  - `hard_stop_daily_loss_pct`
  - `hard_stop_total_dd_pct`
- [x] Paper daemon tarafina daily-stop + kill-switch eklendi.
- [x] 5-window walk-forward tamamlandi ve raporlandi.

### Sprint-1 (In Progress)
**Window:** 2026-02-07 -> 2026-02-21  
**Goal:** Multi-asset mimari iskeleti + 12M validation pipeline.

- [x] Bu roadmap dosyasi olusturuldu.
- [x] `argus_py/adapters/` altinda market adapter interface tanimla.
- [x] `crypto` adapterini mevcut kaynakla interface'e bagla.
- [x] `us_equity` adapteri icin stub + mock data feed ekle.
- [x] `bist` adapteri icin stub + data contract tanimla.
- [x] Portfolio allocator v1 (`risk budget + max exposure`) taslagi yaz.
- [x] 12 aylik rolling walk-forward runner script'i ekle.
- [x] Sprint-1 kabul kriterlerini kozan ilk raporu uret.

### Sprint-2 (Planned)
**Window:** 2026-02-21 -> 2026-03-06  
**Goal:** Full-data validation + external signal overlay + ops stabilization.

- [x] Sprint-2 teknik plan dokumani olustur (`Docs/SPRINT2_PLAN.md`).
- [x] External signal ingest modulu eklendi (`argus_py/signals/external.py`).
- [x] CLI external overlay entegrasyonu eklendi (`--external_signal_*`).
- [x] Cache backfill araci eklendi (`Scripts/sprint2_backfill_btc_cache.py`).
- [x] Missing aylik veri indirimi tamamlandi (`2024-07 -> 2025-02`).
- [x] Full-data 12M walk-forward artifact uretildi.

## 7) Sprint-1 Acceptance Criteria
- Tek komutla 12M rolling backtest calisir.
- Rapor en az su alanlari verir:
  - window return
  - max drawdown
  - trade count
  - profit factor
  - compounded return
- Adapter katmani ile strateji motoru veri kaynagindan ayrisir.

## 8) Priority Backlog (Ordered)
1. Adapter interface + crypto wiring
2. 12M walk-forward automation
3. Portfolio allocator v1
4. Twin daemon (STRICT/SOFT) icin cross-asset extension
5. Live pilot checklist (compliance + ops + kill-switch drills)

## 9) Update Protocol (How We Track)
- Her kod degisikliginden sonra bu dosyada su alanlar guncellenir:
  - `Last Update`
  - `Sprint Board` checkbox
  - gerekirse `Current Baseline`
- Her ciddi run icin run artifact yolu eklenir (CSV/summary/run_id).

## 10) Decision Log
- 2026-02-07:
  - Kaldirac artisi performans-dogrulama bazli, kademeli olacak.
  - Kisa vadede hedef: "hizli buyume" degil, "stabil ve olceklenebilir sistem".
  - Adapter katmani acildi (`crypto/us_equity/bist`) ve CLI market yukleme adapter factory uzerinden calisir hale getirildi.
  - Adapter katmani icin unit testler eklendi (`test_market_adapters.py`) ve gecti.
  - `Scripts/sprint1_walkforward_12m.py` eklendi (timeout/progress/max_bars destekli), smoke artifact:
    - `runs/sweeps/walkforward_12m_20260207_020403.csv`
    - `runs/sweeps/walkforward_12m_20260207_020403.md`
  - Portfolio allocator v1 eklendi (`risk budget + max exposure`) ve CLI entegrasyonu yapildi.
  - Guncel smoke artifact:
    - `runs/sweeps/walkforward_12m_20260207_022809.csv`
    - `runs/sweeps/walkforward_12m_20260207_022809.md`
  - Walk-forward stabilite fixleri:
    - `crypto_csv_adapter` tarih filtreleme + `max_bars` sirasi duzeltildi (range once, cap sonra).
    - `cli.py` icinde `adaptive_safety` undefined referansi kaldirildi.
    - `cli.py` metrik kaydi `continue` yollarinda da alinacak sekilde duzeltildi (summary.json her pencerede uretiliyor).
    - tek-bar pencereler icin equity curve seed eklendi (summary artifact garanti).
  - Sprint-1 acceptance artifact:
    - `runs/sweeps/walkforward_12m_20260207_023547.csv`
    - `runs/sweeps/walkforward_12m_20260207_023547.md`
    - `Docs/sprint1_acceptance_report.md`
  - Veri kapsama notu:
    - `2024-08` sonrasi cache kapsaminda veri yok; pencereler `NO_DATA` olarak raporlandi.
  - Sprint-2 baseline hazirlik:
    - External signal (news/trader) overlay kodu eklendi.
    - External signal template script'i eklendi (`Scripts/sprint2_make_external_signal_template.py`).
    - Missing-data backfill script'i eklendi (`Scripts/sprint2_backfill_btc_cache.py`).
  - Sprint-2 veri tamamlama:
    - Backfill sonucu: `windows=7 downloaded=3 skipped=4 failed=0`
    - Yeni cache dosyalari:
      - `argus_py/data/cache/BTCUSDT_1m_2024-11-01_2024-12-01.csv`
      - `argus_py/data/cache/BTCUSDT_1m_2024-12-01_2025-01-01.csv`
      - `argus_py/data/cache/BTCUSDT_1m_2025-01-01_2025-02-01.csv`
  - Sprint-2 full-data walk-forward artifact:
    - `runs/sweeps/walkforward_12m_20260207_030424.csv`
    - `runs/sweeps/walkforward_12m_20260207_030424.md`
    - `Docs/sprint2_full_data_validation.md`

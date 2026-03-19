# ARGUS Terminal - Proje Rehberi (A'dan Z'ye)

Bu dokuman, repodaki Python tabanli ARGUS trading sistemini bastan sona anlatir.
Amac: bu dosyayi okuyan birinin proje mimarisini, engine rollerini, veri akislarini,
backtest/paper operasyonlarini ve raporlama katmanini tek yerden anlayabilmesi.

Not:
- Bu rehber `src/` ve `Scripts/` icindeki aktif Python stack icindir.
- Klasik `README.md` iceriginde iOS/Swift kismi da var; bu dosya daha cok runtime trading stack'e odaklanir.

## 1) Proje Neyi Cozuyor?

ARGUS, cok-engine'li bir karar sistemi kurar:
- Piyasa verisini toplar (`mock`, `live`, `replay`).
- Feature vektorunu uretir.
- Rejimi tespit eder (`TRENDING`, `RANGING`, `VOLATILE`, `CRISIS`).
- Uygun engine(ler) ile sinyal uretir.
- Cok asamali filtre/gate/sizing/risk kontrolunden gecirir.
- `paper`, `live`, `backtest` modlarinda karar ve trade akisini calistirir.
- Tum sureci SQLite + rapor dosyalari ile kaydeder.

## 2) Ust Seviye Mimari

Ana giris:
- `src/main.py` -> `ArgusPipeline`

Temel akış:
1. Data acquisition (`DataFactory`)
2. Sentinel data-quality kontrolu
3. Feature build (`FeatureVector`)
4. Regime detection ve state machine
5. Engine routing/orchestration
6. MDE filtreleri ve gate zinciri
7. Sizing + risk + pre-trade validation
8. Execution (`auto` veya `advisory`)
9. Telemetry/log/persist

Ana modlar:
- `paper`: simulasyon ve operasyonel runtime
- `live`: gercek veri + gercek operasyon modu (runtime guvenlik semantiklerini korur)
- `backtest`: replay/forward-sim ve analiz odakli calisma

## 3) Dizin Haritasi

Ana dizinler:
- `src/core`: tipler, sabitler, config modelleri
- `src/data`: data factory, replay loader, local store, exchange clients
- `src/features`: feature paketleri (orn. `feature_pack_v0`)
- `src/regime`: regime classifier, validator, trend gate, orchestrator
- `src/engines`: sinyal ureten engine siniflari
- `src/mde`: gate, router, sizing, precision/confluence/trade quality
- `src/risk`: kill switch, pre-trade, validated sizing, dynamic risk modulleri
- `src/execution`: order execution ve precision entry/exit
- `src/backtest`: simulator + analysis/report katmani
- `src/v25`: config/bootstrap/contracts/db/telemetry seam
- `src/orchestration`: ORION meta-orchestrator
- `src/runtime`: 7/24 paper supervisor ve runtime guard
- `src/telemetry`: event logger

Operasyon klasorleri:
- `Scripts`: tum operasyon/script girisleri
- `config`: `base.yaml`, `engines.yaml`, `risk.yaml`, `regimes.yaml`, `telemetry.yaml`
- `data`: lokal market data cache/storage
- `runs`: runtime/backtest ciktilari
- `reports`: analiz raporlari
- `tests`: unit/integration/stress testleri

## 4) Konfigurasyon Katmani

Config dosyalari:
- `config/base.yaml`: sistem modu, asset siniflari, sembol listeleri, timeframe
- `config/engines.yaml`: her engine'in parametreleri + v2.5 filtre ayarlari
- `config/risk.yaml`: sizing, drawdown, kill-switch, fee model, growth sizer
- `config/regimes.yaml`: regime threshold ve transition kurallari
- `config/telemetry.yaml`: log/alert/retention ayarlari

Yukleme:
- `src/core/config.py`
- YAML dosyalari pydantic modellerine parse edilir, tip guvenligi saglanir.

## 5) Veri Katmani (Data Layer)

### 5.1 DataFactory
Dosya: `src/data/data_factory.py`

Mode'lar:
- `mock`: exchange->local fallback
- `live`: explicit canli veri mode'u
- `replay`: deterministic parquet replay (`data/binance`)

Ozet:
- `fetch_ohlcv()` her modda uygun kaynaktan OHLCV dondurur.
- `replay` modunda `ReplayLoader` kullanilir.
- `evolve` modunda lokal/parquet deterministic akıs zorlanir.

### 5.2 ReplayLoader
Dosya: `src/data/replay_loader.py`

- Month-partitioned parquet dosyalarini sadece gerekli aylari okuyarak yukler.
- Tarih araligi filtreler, sort + dedup yapar.
- Opsiyonel integrity check ile gap/duzen kontrolu yapar.

### 5.3 LocalStore
Dosya: `src/data/local_store.py`

Storage layout:
- `data/binance/{SYMBOL}/{INTERVAL}/{YYYY-MM}.parquet`

Ozellikler:
- Append-safe merge
- Timestamp bazli dedup
- Sorted deterministic kayit
- Integrity raporu (`total_bars`, `gap_count`, vb)

## 6) Core Data Contract'lari

Dosya: `src/core/types.py`

Kritik modeller:
- `FeatureVector`: teknik + hacim + microstructure + crypto-native + sentiment + ML alanlari
- `RegimeState`: rejim, guven, stabilite, yon
- `EngineSignal`: engine ciktisi (bias, confidence, stop/target beklenti)
- `Decision`: execution oncesi nihai karar
- `ExecutionResult`: emir sonucu
- `TradeRecord`: kapanmis trade kaydi

Onemli not:
- Modeller strict/frozen ve NaN reject semantigi ile gelir.

## 7) Regime Katmani

### 7.1 Rule-Based Regime Classifier
Dosya: `src/regime/rule_based.py`

Priority:
1. `CRISIS`
2. `VOLATILE`
3. `TRENDING`
4. `RANGING`

### 7.2 Regime Validator (v6)
Dosya: `src/regime/regime_validator.py`

- Declared regime'i trend/volatility/structure skorlariyla dogrular.
- Gerekirse override eder, `TRANSITION` rejimi uretebilir.
- Hysteresis + cooldown ile flip-flop azaltir.

### 7.3 Trend Gate (v6)
Dosya: `src/regime/trend_gate.py`

- 5 kosulun hepsi saglanirsa trend verified kabul eder.
- Verified trend durumunda engine/risk tarafinda boost politikalarina zemin olusturur.

### 7.4 Engine Orchestrator (v6)
Dosya: `src/regime/engine_orchestrator.py`

- Validated regime'e gore engine enable/disable listesi verir.
- Trend verified ise `rr_mult`, `size_mult`, trailing override uretir.
- MR strict mode ile belirli kosullarda MR engine'leri kisar.

## 8) Engine Katalogu (Ne Is Yapar?)

Engine role referansi:
- `src/regime/engine_roles.py`

### 8.1 TITAN
Dosya: `src/engines/titan/engine.py`

Rol:
- Trend engine

Mantik:
- Dual setup: `REVERSAL` + `CONTINUATION`
- ADX/EMA/structure tabanli trend karar mekanizmasi
- `TRENDING` rejime odakli

### 8.2 NAUTILUS
Dosya: `src/engines/nautilus/engine.py`

Rol:
- Mean reversion (range specialist)

Mantik:
- BB reversion
- Funding reversion
- Micro reversion (range mapper + microstructure)
- `RANGING` rejim odakli

### 8.3 HYDRA
Dosya: `src/engines/hydra/engine.py`

Rol:
- Scalping

Mantik:
- BB + RSI + orderbook imbalance + volume delta
- Dusuk ADX ortaminda hizli/kisa sureli setup
- Siki stop ve hizli TP yapisi

### 8.4 POSEIDON
Dosya: `src/engines/poseidon/engine.py`

Rol:
- Mean Reversion Consortium

Mantik:
- Coklu indicator oylamasi (BB, RSI, CCI, WillR, VWAP, CMF, WaveTrend, HARSI, Entropy ST)
- Agirlikli score ile signal grade (STRONG/NORMAL/WEAK)
- Konsorsiyum ve profil katmanlari ile birlestirme

### 8.5 AEGEAN
Dosya: `src/engines/aegean/engine.py`

Rol:
- Hybrid (trend+range adaptif)

Mantik:
- Exponential RSI + Momentum Linear Regression Channel
- Rejim bazli parametre seti
- MTF trend filter

### 8.6 PHOENIX
Dosya: `src/engines/phoenix/engine.py`

Rol:
- Carry/Basis

Mantik:
- Funding harvest
- Basis trade
- Non-crypto carry benzeri proxy

### 8.7 HERMES
Dosya: `src/engines/hermes/engine.py`

Rol:
- Sentiment / veto overlay

Mantik:
- Haber sentiment skoruna gore sinyal, block, close, SL/TP adjustment instruction
- Kritik negatif senaryoda agresif koruma

### 8.8 GEMINI
Dosya: `src/engines/gemini/engine.py`

Rol:
- Pairs/correlation

Mantik:
- Correlation tracker + spread z-score sinyalinden tek-leg `EngineSignal` turetir.

### 8.9 ATLAS (overlay)
Dosya: `src/engines/atlas/risk_overlay.py`

Rol:
- Risk multiplier overlay

Mantik:
- Macro/flow context'e gore risk on/off katsayisi verir.

## 9) Routing ve MDE Katmani

### 9.1 Router
Dosya: `src/mde/router.py`

- Static fallback map + optional orchestrated routing destekler.
- HERMES override/boost semantigi uygular.

### 9.2 Sequential Gates
Dosya: `src/mde/gates.py`

Gate bloklari:
- Sentinel hard block
- Crisis rejim
- Hermes block
- Risk switch level
- Signal var/yok
- Min confidence
- Net expected return
- Reward/risk
- Crypto fee-aware gate (RR/TP/edge)

### 9.3 Precision Filter
Dosya: `src/mde/precision_filter.py`

- Entry kalitesini grade'ler (`A/B/C/D/F` benzeri)
- Confidence adjust/reject mekanizmasi

### 9.4 Confluence Filter
Dosya: `src/mde/confluence_filter.py`

- Bagimsiz faktorlerden coklu onay ister.
- MTF, volume, momentum, volatility, orderbook, statistical edge eksenleri

### 9.5 Trade Quality
Dosya: `src/mde/trade_quality.py`

- Sinyal quality + precision + confluence + regime alignment + RR birlesik skoru
- Final grade (`A/B/C/D`) ile son kalite karari

### 9.6 Sizing
Dosya: `src/mde/sizing.py`

- Atlas/sentinel/regime/dd/rsl/hermes multipliers ile risk-per-trade hesaplar.

## 10) Risk Katmani

### 10.1 Kill Switch
Dosya: `src/risk/kill_switch.py`

- Drawdown bazli risk level (`NORMAL`..`LOCKDOWN`)
- Trade izni ve size multiplier kontrolu
- Durum SQLite'a persist edilir

### 10.2 Pre-Trade Checker
Dosya: `src/risk/pre_trade.py`

- Position size/leverage/trade count/correlation/stop/allocation kontrolleri
- Hafta sonu ve funding blackout gibi guard'lar
- Validated sizing entegrasyonu

### 10.3 Validated Sizer
Dosya: `src/risk/validated_sizer.py`

- Fee-aware notional hesaplar
- Gate9 (fee burden vs risk) uygular
- Derived leverage kontrolu yapar

### 10.4 Diger Risk Modulleri
- `src/risk/dynamic_risk_manager.py`
- `src/risk/breakeven_lock.py`
- `src/risk/leverage_calibrator.py`
- `src/risk/scale_in_orchestrator.py`
- `src/risk/auto_risk_optimizer.py`

## 11) Execution Katmani

Dosya: `src/execution/executor.py`

Calisma:
- `advisory`: emir gondermez, mesaj uretir
- `auto`: broker adapter ile order place eder

Ek yetenekler:
- Hyper precision entry (`execute_with_precision`)
- Partial close (`execute_partial_close`)
- Trailing stop update helper

## 12) ORION Meta-Orchestrator

Dosya: `src/orchestration/orion.py`

ORION ne yapar:
- Soft regime olasiliklari
- Transition skoru
- Engine weight vektoru
- PAF state machine (Probe/Arm/Fire)
- Dynamic risk posture

Ne yapmaz:
- Engine yerine dogrudan sinyal uretmez
- Temel safety semantiklerini bypass etmez

CLI:
- `--orion` ile aktif edilir.

## 13) Telemetry ve Veritabani

### 13.1 v2.5 DB bootstrap
- `src/v25/bootstrap.py`
- `src/v25/db/migrations.py`

Kritik tablolar:
- `decisions`
- `trades`
- `ledger`
- `kill_switch_state`
- `sqs_log`
- `regime_history`
- `backtest_runs`, `backtest_trades`, `backtest_equity_curve`
- `dynamic_exit_log`
- `validated_sizing_log`
- `whale_momentum_log`
- `correlation_logs`, `correlation_signals`

### 13.2 Event logger
- `src/telemetry/event_logger.py`: `telemetry_events` tablosu
- `src/v25/telemetry/log_writer.py`: append-only DB yazicilari

## 14) Backtest Stack

### 14.1 Stateful simulator
Dosya: `src/backtest/backtest_simulator.py`

- Position lifecycle (entry -> SL/TP -> BE lock -> trailing -> time stop)
- Engine-aware trade davranislari
- Virtual account/equity/drawdown takibi

### 14.2 Analysis/report
Dosyalar:
- `src/backtest/analysis/extractor.py`
- `src/backtest/analysis/report_writer.py`
- `src/backtest/analysis/*`

Uretilenler:
- Enriched trade dataset
- Correlation/bucket/pattern raporlari
- Long-short tuning
- Exit diagnostics

### 14.3 WAR Backtest Lab
Script: `Scripts/war_backtest_lab.py`

- Senaryo presetleri (`Scripts/scenarios/backtest_scenarios.yaml`)
- Aylik slice bazli kosu
- ORION on/off matrix
- Coverage + summary + long/short + bear edge + early/flip raporlari

## 15) Runtime Ops ve Script Ekosistemi

`Scripts/` klasoru genis bir operasyon toolbox'i saglar.

One cikan script gruplari:
- Data edinim:
  - `Scripts/download_ohlcv.py`
  - `Scripts/unify_market_data.py`
  - `Scripts/backfill.py`
  - `Scripts/dataset_check.py`
- Backtest/analiz:
  - `Scripts/war_backtest_lab.py`
  - `Scripts/analyze_backtest.py`
  - `Scripts/backtest_analyzer.py`
  - `Scripts/validate_titan_v2.py`
- Paper/daemon/supervisor:
  - `Scripts/paper_daemon.py`
  - `Scripts/paper_v2_daemon.py`
  - `Scripts/soak_start.sh`, `soak_status.sh`, `soak_stop.sh`
  - Windows esdegerleri (`win_*`, `windows_*`)
- Governance/diagnostics:
  - `Scripts/strategy_registry.py`
  - `Scripts/phase19_*`
  - `Scripts/reliability_watchdog.py`

## 16) Tipik Is Akislari (Pratik)

### 16.1 Data indir + dataset smoke check

```bash
python Scripts/download_ohlcv.py --symbol BTCUSDT --interval 15m --start 2020-01-01 --end 2024-12-31 --store-root data/binance
python Scripts/dataset_check.py --symbol BTCUSDT --interval 15m --store-root data/binance
```

### 16.2 Backtest (replay + forward-sim)

```bash
python -m src.main --mode backtest --assets crypto --v25 --v25-db runs/v25/argus_v25.db --symbols BTCUSDT --timeframe 15m --forward-sim --max-cycles 500
```

### 16.3 WAR senaryo backtesti

```bash
python Scripts/war_backtest_lab.py --scenario covid_crash_2020 --symbols BTCUSDT --timeframe 15m --orion off --cache-root data/binance
```

### 16.4 Paper mode

```bash
python -m src.main --mode paper --assets crypto --v25 --v25-db runs/v25/argus_v25.db --live-data --symbols BTCUSDT,ETHUSDT --timeframe 15m
```

### 16.5 ORION acik paper/backtest

```bash
python -m src.main --mode backtest --assets crypto --v25 --v25-db runs/v25/argus_v25.db --orion --symbols BTCUSDT --timeframe 15m
```

### 16.6 Engine optimization (backtest-only)

```bash
python -m src.main --mode backtest --optimize-engines --optimize-assets BTCUSDT,ETHUSDT --optimize-start 2020-01-01 --optimize-end 2026-01-01
```

### 16.7 Strategy profile matrix (MR/Trend/Pump + Long/Short + Vol bucket)

`src/main.py` artik su flag'leri destekler:
- `--enable-strategy-profiles`
- `--strategy-profiles-config <path>`
- `--replay-start` + `--replay-end` (window bazli deterministic backtest)
- `--backtest-sonar` (replay veriden dinamik coin kesfi)

Ornek:

```bash
python -m src.main --mode backtest --assets crypto --v25 --v25-db runs/v25/argus_v25.db --timeframe 1h --replay-start 2024-02-24T00:00:00Z --replay-end 2024-03-26T23:00:00Z --backtest-sonar --strategy-profiles-config config/strategy_profiles.yaml --enable-strategy-profiles
```

### 16.8 Profil campaign lab (otomatik varyant tarama)

Bu script profile matrix varyantlarini calistirir, leaderboard uretir ve en iyi YAML'i cikarir:

```bash
python Scripts/profile_backtest_lab.py --replay-start 2024-02-24T00:00:00Z --replay-end 2024-03-26T23:00:00Z --timeframe 1h --backtest-sonar
```

Yeni listing simulasyonu ile SONAR testi:

```bash
python Scripts/profile_backtest_lab.py --replay-start 2024-02-24T00:00:00Z --replay-end 2024-03-26T23:00:00Z --timeframe 1h --backtest-sonar --inject-synthetic-listing --synthetic-symbol HYPESIMUSDT --synthetic-source BTCUSDT --synthetic-listing-time 2024-03-05T00:00:00Z
```

### 16.9 BTC/ETH high-liquidity optimize (1h + 15m)

Yeni katman:
- `config/high_liquidity_filters.yaml`
- `--liquidity-policy-config <path>`

Bu optimize script'i:
- ETHUSDT 15m coverage yoksa backfill dener
- 1h + 15m baseline/candidate kosularini yapar
- drawdown guardrail (`candidate_dd <= baseline_dd * 1.15`) ile winner secer
- `--apply-winner` verilirse winner'i `config/high_liquidity_filters.yaml` ve
  `config/strategy_profiles.yaml` metadata alanina yazar

```bash
python Scripts/high_liquidity_optimize.py --replay-start 2024-02-24T00:00:00Z --replay-end 2024-03-26T23:00:00Z --symbols BTCUSDT,ETHUSDT --timeframes 1h,15m --apply-winner
```

## 17) Cikti Dosyalari ve Nerede Ne Uretilir?

Genel:
- Runtime/backtest run artefact'lari: `runs/`
- Analiz markdown/csv: `reports/`

WAR Backtest Lab ana ciktilari:
- `WAR_BACKTEST_SCENARIO_SUMMARY.csv/.md`
- `WAR_BACKTEST_DATA_COVERAGE.md`
- `WAR_BACKTEST_ENGINE_BREAKDOWN.csv`
- `WAR_BACKTEST_REGIME_BREAKDOWN.csv`
- `WAR_BACKTEST_EQUITY_CURVE.csv`
- `WAR_BACKTEST_DRAWDOWN_CURVE.csv`
- `LONG_SHORT_BREAKDOWN.csv`
- `BEAR_EDGE_REPORT.md`
- `EARLY_ENTRY_REPORT.md`
- `FLIP_COMPARISON_REPORT.md`

## 18) Test Altyapisi

Test klasorleri:
- `tests/unit`
- `tests/integration`
- `tests/backtest`
- `tests/engines`, `tests/mde`, `tests/risk`, `tests/regime`, vb.

Calistirma:

```bash
pytest -q
```

## 19) Engine-Rejim Gercek Calisma Notu

Kodda iki seviyeli davranis var:
- Legacy static map (`REGIME_TO_ENGINE`)
- v6 dynamic orchestrator (`RegimeValidator + TrendGate + EngineOrchestrator`)

Pratikte `run_once` icinde v6 orchestration denenir,
basarisiz olursa static router fallback devreye girer.

Bu nedenle engine aktivasyonu tek satir static map'ten ibaret degildir.

## 20) Guclu Yanlar / Kritik Dikkat Noktalari

Guclu taraflar:
- Moduler engine mimarisi
- Replay/backtest deterministik data altyapisi
- Cok katmanli safety (sentinel + gates + kill switch + pre-trade)
- SQLite tabanli kalici telemetry
- WAR senaryo laboratuvari

Dikkat edilmesi gerekenler:
- Script ekosistemi buyuk; naming/entry point standardi korumak onemli
- Config uyumsuzluklari tum pipeline'i etkiler
- `1m` gibi alt timeframe bagimliliklari yoksa bazi analizlerde warning gelebilir
- Buyuk backtest kosularinda run/report dizinleri hizla buyur

## 21) Kisaca "Bu Projede Nereye Bakmaliyim?"

Yeni baslayan icin sira:
1. `src/main.py`
2. `src/core/types.py`
3. `src/data/data_factory.py` + `src/data/replay_loader.py`
4. `src/regime/*`
5. `src/mde/*`
6. `src/engines/*`
7. `src/risk/*` + `src/execution/executor.py`
8. `Scripts/war_backtest_lab.py`
9. `tests/` klasorleri

Bu sirayi izlersen proje davranisini yuksek dogrulukla ve hizli sekilde cozersin.

---

## Ek: Hizli Komut Referansi

Dataset coverage:

```bash
python Scripts/dataset_check.py --symbol BTCUSDT --interval 15m
```

Backtest smoke:

```bash
python -m src.main --mode backtest --assets crypto --v25 --v25-db runs/v25/argus_v25.db --symbols BTCUSDT --timeframe 15m --forward-sim --max-cycles 200
```

WAR lab quick:

```bash
python Scripts/war_backtest_lab.py --scenario bull_2024 --symbols BTCUSDT --timeframe 15m --orion off --max-cycles-per-scenario 1344 --cache-root data/binance
```

Profile lab quick:

```bash
python Scripts/profile_backtest_lab.py --replay-start 2024-02-24T00:00:00Z --replay-end 2024-03-26T23:00:00Z --timeframe 1h --backtest-sonar
```

High-liquidity quick:

```bash
python Scripts/high_liquidity_optimize.py --replay-start 2024-02-24T00:00:00Z --replay-end 2024-03-26T23:00:00Z --symbols BTCUSDT,ETHUSDT --timeframes 1h,15m --max-candidates 24 --apply-winner
```

Paper quick:

```bash
python -m src.main --mode paper --assets crypto --v25 --v25-db runs/v25/argus_v25.db --live-data --symbols BTCUSDT --timeframe 15m
```

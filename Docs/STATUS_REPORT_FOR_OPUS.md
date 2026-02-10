# 1) Repo Snapshot (What exists today)

## Top-level tree summary
Bu repo tek amaçlı bir Python trading reposu değil; aynı workspace içinde iOS/Swift ve araştırma artifaktları da var. Trading tarafının aktif çalışma yüzeyi aşağıdaki klasörlerde:

- Kod çekirdeği: `argus_py/`
- Operasyon scriptleri: `Scripts/` (ve birebir kopya: `scripts/`)
- Testler: `tests/`
- Plan/kontrat/durum dokümanları: `Docs/`
- Çalışma çıktıları: `runs/`, `reports/`, `logs/`

## Rough LOC (mevcut repo gerçekliği)
Aşağıdaki değerler hızlı sayım (`*.py`, `*.md`) ile yaklaşık:

| Folder | File count | Rough LOC |
|---|---:|---:|
| `argus_py` | 124 `.py` | 14,001 |
| `tests` | 30 `.py` | 3,801 |
| `Docs` | 47 `.md` | 22,375 |
| `Scripts` | 53 `.py` | 6,803 |

## What runs today?
Çalışan ve operasyonel görünen entrypoint’ler:

- Paper daemon (ana runtime): `Scripts/paper_daemon.py` (`PaperDaemon`)
- Paper soak kontrolü: `Scripts/soak_start.sh`, `Scripts/soak_status.sh`, `Scripts/soak_stop.sh`, `Scripts/soak_smoke.sh`
- Dashboard: `Scripts/dashboard.py` + API backend `argus_py/dashboard/app.py` (`/api/status`, `/api/trades`, `/api/equity`, `/api/rejections`)
- Twin supervisor: `Scripts/phase19ctl.sh` + `Scripts/phase19_supervisor.py`
- Nightly/autopilot: `Scripts/year2_autopilot.py`, `Scripts/nightly_eval.py`, `Scripts/gate_recheck.py`, `Scripts/year2_generate_metrics.py`
- Walk-forward/backtest yüzeyi: `Scripts/sprint1_walkforward_12m.py`, `Scripts/backtest_pack.sh`, `argus_py/runner/cli.py`

Not: `argus_py/runner/live_cli.py` dosyası mevcut ama `tick()` içinde strateji/execution hattı yorum/TODO seviyesinde; canlı operasyon için tam-kapanmış bir pipeline görünmüyor.

## Current decision style: voting council vs routing
Kod gerçekliği hibrit ama merkezde **voting council** var:

- Aktif karar çekirdeği: `argus_py/council/aggregator.py` -> `Council.deliberate(...)`
- Aktif paper akışı: `Scripts/paper_daemon.py` içinde `AegeanEngine` + `OrionEngine` + `Council.deliberate(...)`
- Routing mevcut ama daha çok **risk/policy mode** amaçlı: `argus_py/strategy/router.py` -> `ModeRouter.update(...)`
- Rejim algılayıcı mevcut: `argus_py/risk/regime.py` -> `RegimeDetector.detect(...)`

Ek not: `argus_py/council/council.py` içindeki `GrandCouncil` (Orion+Aether+Hermes+Phoenix+Aegean) ayrı bir ikinci konsept olarak mevcut, fakat `Scripts/paper_daemon.py` içinde kullanılmıyor.

---

# 2) Engines Inventory (What engines exist in code)

| Engine Name | Location (path) | Inputs used | Output type | Active regimes if any | Notes (correlation risk, overlap) |
|---|---|---|---|---|---|
| Orion | `argus_py/models/orion/orion.py` (`OrionEngine.calculate`) | `List[Bar]`, çoklu teknik gösterge (SMA/EMA/BB/ADX/ATR/RSI/MACD/Stoch) | `Vote` (`argus_py/council/defs.py`) | Explicit regime gate yok; `trend_active` metadata var | Trend/momentum ağırlıklı; Aegean ile teknik korelasyon riski yüksek |
| Aegean | `argus_py/models/aegean/aegean.py` (`AegeanEngine.calculate`) | `List[Bar]`, EMA slope + Donchian position | `Vote` | Explicit regime gate yok | Range/chop benzeri davranış üretir; Orion ile aynı price serisine bağlı |
| Phoenix | `argus_py/models/phoenix/phoenix.py` (`PhoenixEngine.analyze`) | `closes/highs/lows` | `PhoenixAdvice` | Kod içinde explicit regime enum yok | Mean-reversion kanal motoru; daemonda ana karar hattına doğrudan bağlı değil |
| Hermes | `argus_py/models/hermes/hermes.py` (`HermesEngine.analyze`) | RSS haber akışı, opsiyonel Groq, keyword fallback | `HermesResult` | Regime üretmez; sentiment overlay | Data kalitesi ve haber gecikmesine duyarlı |
| Aether | `argus_py/models/aether/aether.py` (`AetherEngine.evaluate`) | Fear&Greed, dominance, global mcap, DXY, funding | `AetherResult` (`MacroRegime`) | `RISK_ON`/`RISK_OFF`/`NEUTRAL` | Makro overlay; sinyal değil risk bias üretir |
| Chiron | `argus_py/models/chiron/chiron.py` (`ChironRegimeEngine.evaluate`) | `RegimeContext` (orion/aether/hermes scores + adx/chop/vol) | `ChironResult` | `TREND`, `CHOP`, `RISK_OFF`, `NEWS_SHOCK`, `NEUTRAL` | Weight orchestration yapıyor; paper daemon ana flow’da kullanılmıyor |
| TopHunter Short V1 | `argus_py/strategy/tophunter_short.py` (`evaluate_tophunter_short_v1`) | `List[Bar]`, ADX filtresi, pivot yapısı | `TopHunterSignal` | ADX `< max_adx` (default 20) | Paper-only risk cap mantığı daemonda uygulanıyor |
| Council (active) | `argus_py/council/aggregator.py` (`Council.deliberate`) | `List[Vote]` (fiilen Orion + Aegean) + regime string | `ConsensusVerdict` | `TREND/CHOP` ağırlık adaptasyonu | Şu an canlı karar merkezi; iki teknik motorla sınırlı |
| GrandCouncil (secondary) | `argus_py/council/council.py` (`GrandCouncil.convene`) | Orion/Aether/Hermes/Phoenix/Aegean skorları | `CouncilDecision` | Regime’e göre `CouncilWeights` | Tasarım var ama aktif runtime’da wire edilmemiş |

---

# 3) v2.0 Target Inventory (What the docs claim)

Aşağıdaki v2.0 iddiaları dokümanlarda mevcut:

- 3 engine + 2 overlay: **TITAN / NAUTILUS / PHOENIX** + **ATLAS / SENTINEL**
- Rejim seti: **TRENDING / RANGING / VOLATILE / CRISIS**
- Karar modeli: **MDE v2.0 routing** (voting değil)
- Risk: **RSL v2.0** ve kill-switch katmanları
- Gate modeli: Paper -> Micro-live -> Live

## Doküman kanıtları (dosya + timestamp)

| Doc | Timestamp | v2.0 içeriği |
|---|---|---|
| `Docs/FUTURE_VISION.md` | `2026-02-10 04:06:44` | TITAN/NAUTILUS/SENTINEL/ATLAS, MDE v2.0 routing, RSL v2.0, 4-state regime ve “authoritative v2.0 folder structure” tanımları var |
| `Docs/ARGUS_YEAR2_TECHNICAL_PLAN.md` | `2026-02-08 13:03:34` | Paper->Micro-live->Live gate tabloları, nightly artifacts, risk policy, realism varsayımları |
| `Docs/FUTURE_VISION_2.md` | `2026-02-08 13:14:47` | Year-2 vizyonu ve referans entegrasyon hattı; execution sync bağlamı |
| `Docs/AUTOPILOT.md` | `2026-02-09 00:07:58` | Night loop ve paper-only operasyon ilkeleri |
| `Docs/YEAR2_AUTOPILOT_RUNBOOK.md` | `2026-02-09 00:08:07` | Çalıştırma komutları ve nightly/gate operasyon prosedürü |

---

# 4) Conflict Map (Reality vs Spec)

## Code’da var ama v2.0’a göre deprecated/uyumsuz

- Council-voting merkezli karar hattı aktif (`argus_py/council/aggregator.py`, `Scripts/paper_daemon.py`) ama v2.0 metinleri routing-MDE modelini hedefliyor.
- Rejim sınıfları kodda ağırlıklı olarak `TREND/CHOP/...` (`argus_py/risk/regime.py`, `argus_py/models/chiron/chiron.py`) iken v2.0 hedefi `TRENDING/RANGING/VOLATILE/CRISIS`.
- `Orion/Aegean` aktif ana motorlar; v2.0’da bunların yerine `TITAN/NAUTILUS` öneriliyor.

## Docs’ta var ama code’da yok

- `SENTINEL` data-quality overlay için kod klasörü yok (v2.0 dokümanda geçiyor).
- `MDE v2.0` (tek-lead-engine routing) için `argus_py/mde/*` benzeri bir implementation yok.
- `RSL v2.0` adıyla ayrı katman yok; mevcutta kill-switch var (`argus_py/risk/kill_switch.py`) ama dokümandaki tam RSL ayrımı yok.
- TITAN/NAUTILUS adında engine modülleri yok (kodda Orion/Aegean/Phoenix/Hermes/Aether/Chiron var).

## Multiple competing visions (doküman çatışmaları)

1. `Docs/FUTURE_VISION.md` kendi içinde iki vizyon taşıyor:
- Erken bölümlerde geniş, komite/voting ağırlıklı çoklu engine yaklaşımı
- Sonraki bölümlerde “v2.0 routing, command chain, 3 engine + overlays” yaklaşımı

2. `Docs/ARGUS_YEAR1_TECHNICAL_MASTERPLAN.md` + `Docs/DELEGATED_TASKS.md` yürütülmüş gerçekliği Orion/Aegean/Council stack üzerine kuruyor.

3. `Docs/ARGUS_ARCHITECTURE_V2.md` daha soyut platform-mimari taslağı; güncel operasyon runbook’u (`Docs/YEAR2_AUTOPILOT_RUNBOOK.md`) ile birebir aynı seviye detayda değil.

Sonuç: repo gerçekliği ile “nihai v2.0 anlatısı” arasında henüz migration tamamlanmamış.

---

# 5) Minimal Path Forward (Delete / Keep / Modify)

## A) KEEP (non-negotiable spine)

Aşağıdaki omurga korunmalı:

- Risk & safety: `argus_py/risk/kill_switch.py`, `Scripts/paper_daemon.py` kill-switch guard akışı
- Telemetry contracts: `heartbeat.json`, `metrics.json`, `decisions.csv`, `trades.csv`, `rejects.csv`
- Observability: `argus_py/dashboard/app.py`, `Scripts/status_reader.py`, `Scripts/year2_generate_metrics.py`
- Operations infra: `Scripts/soak_start.sh`, `Scripts/soak_status.sh`, `Scripts/soak_stop.sh`, `Scripts/soak_smoke.sh`
- Audit/Gate: `Scripts/weekly_audit.py`, `Scripts/nightly_eval.py`, `Scripts/gate_recheck.py`

## B) DELETE or ARCHIVE (şimdilik kompleksite azaltma)

Silme yerine `Docs/_archive/` ve gerekiyorsa `argus_py/_experimental/` yaklaşımı önerilir.

- Çift script ağacı (`Scripts/` ve `scripts/`) tekine indirilmeli; diğeri arşivlenmeli
- Aktif akışa bağlı olmayan konsept kodu (ör. `GrandCouncil` path’i) “experimental” etiketiyle izole edilmeli
- Çatışmalı/tekrarlı plan dokümanları arşive alınmalı (Section 6 listesi)

## C) MVP için tutulacak 2 engine (bugünkü kod tabanına göre)

Öneri:

- Trend engine: **Orion** (`argus_py/models/orion/orion.py`)
- Mean-reversion engine: **Aegean** (`argus_py/models/aegean/aegean.py`)

Rasyonel:

- İkisi de aktif paper daemon flow’da entegre ve test kapsaması mevcut
- Phoenix şu an sağlam ama ana karar pipeline’ında lead engine değil; ikinci adımda üçüncü motor olarak alınabilir

## D) Decision style seçimi

- **Crypto mode (öncelik): regime routing (MDE benzeri) önerilir**
- **Stocks mode (sonra): bounded voting council opsiyonel**

Rasyonel:

- 24/7 kriptoda hızlı regime değişimi ve risk gating ihtiyacı daha yüksek; “tek lead engine + sert risk kapısı” operasyonel olarak daha denetlenebilir
- Voting yaklaşımı çoklu sinyal korelasyonu ve tartışmalı ağırlık yönetimi yaratıyor; stok tarafında daha düşük frekansta opsiyonel kalabilir

---

# 6) “Source of Truth” file selection (2–3 docs)

## Authoritative (önerilen minimal set)

1. `Docs/DELEGATED_TASKS.md`
- Neden: Uygulanan işlerin kanıt/ledger bazlı gerçeği burada

2. `Docs/ARGUS_YEAR2_TECHNICAL_PLAN.md`
- Neden: Stage gate, risk policy, nightly artifact ve operasyon contract’ı içeriyor

3. `Docs/YEAR2_AUTOPILOT_RUNBOOK.md`
- Neden: Günlük/nightly operasyon komutları ve fallback akışı pratik olarak burada

## Non-authoritative (archive’a alınması önerilenler)

Aşağıdakiler çakışma/tekrar riski taşıyor; `Docs/_archive/` altına alınmalı:

- `Docs/FUTURE_VISION_2.md`
- `Docs/ARGUS_YEAR1_TECHNICAL_MASTERPLAN_OPUS.md`
- `Docs/ARGUS_MASTER_PLAN.md`
- `Docs/ARGUS_ARCHITECTURE_V2.md` (referans olarak kalabilir ama aktif kontrat değil)
- `Docs/PHASE20_STATUS.md` (kısmen güncelliğini yitirmiş)

Not: `Docs/FUTURE_VISION.md` tamamen silinmemeli; “vision/reference” etiketi ile non-contract doküman olarak tutulmalı.

---

# 7) Constitution Blueprint (Outline only)

Aşağıdaki iskelet, `Docs/CONSTITUTION_V2.md` için decision-complete outline’dır:

## I. Purpose and Scope
- Amaç: paper-first, audit-ready, risk-bounded research-to-production pipeline
- Kapsam: kripto öncelikli, canlı geçiş gate kontrollü

## II. Modes
- CRYPTO mode (default)
- STOCKS mode (later/optional)
- Mode-specific session windows ve data dependencies

## III. Decision Pipeline and Gates
1. Data ingest + validation
2. Regime classification
3. Engine selection (lead engine by regime)
4. Decision generation
5. Risk gate + kill-switch veto
6. Execution simulator/paper broker
7. Telemetry emit

Gate tanımları:
- Gate A: Paper -> Micro-live
- Gate B: Micro-live -> Live
- Gate C: Live scale-up
- Her gate için pass/fail metrikleri (DD, uptime, slippage, error rate, trades, drift)

## IV. Risk / Kill-switch Policy
- Risk levels: NORMAL/SOFT/HARD/HALT
- dailyLossCap, cooldown, consecutive loss policy
- Manual override ve incident drill prosedürü

## V. Data Contracts (runtime validation required)
- `decisions.csv`, `trades.csv`, `rejects.csv`, `heartbeat.json`, `metrics.json`, `daemon_state.json`
- Reject code schema zorunluluğu (`normalize_reject`, `validate_reject`)
- Atomic write ve schema drift policy

## VI. Telemetry Event Contract
- Mandatory events: decision_made, risk_verdict, execution_result, reject_logged, heartbeat_update
- Strategy tags: `strategy_id`, `trigger_type`, `regime_filter`
- Dashboard/API minimum alanlar

## VII. Folder Structure (operational)
- `argus_py/` runtime core
- `Scripts/` operations + batch
- `runs/year2/*` canonical runtime outputs
- `reports/year2/*` canonical reports
- `Docs/` active contracts + `_archive/`

## VIII. Codex Implementation Phases + Acceptance
- Phase 1: source-of-truth cleanup + docs archive
- Phase 2: decision pipeline normalization (routing + lead-engine contract)
- Phase 3: risk/telemetry hardening
- Phase 4: gate automation and incident drills

Acceptance criteria:
- Tüm unit testler yeşil
- Nightly artifacts eksiksiz
- Gate raporları deterministik
- Paper soak uptime/error targets sağlanıyor

---

# 8) Appendices

## A: Commands to run tests / paper mode / backtest

```bash
# Unit tests
make test

# Full tests
make test-all

# Paper soak start/status/stop
Scripts/soak_start.sh council
Scripts/soak_status.sh
Scripts/soak_stop.sh

# Fast smoke (start -> status -> stop)
Scripts/soak_smoke.sh council

# Dashboard
venv/bin/python Scripts/dashboard.py runs/year2/paper_main --host 127.0.0.1 --port 18081

# Status JSON reader
venv/bin/python Scripts/status_reader.py --run-dir runs/year2/paper_main

# Backtest pack
Scripts/backtest_pack.sh BTCUSDT 2024-01-01 2024-01-05

# Walk-forward baseline
venv/bin/python Scripts/sprint1_walkforward_12m.py --help

# Nightly evaluation
venv/bin/python Scripts/nightly_eval.py --run-dir runs/year2/paper_main --reports-dir reports/year2

# Gate re-check
venv/bin/python Scripts/gate_recheck.py --run-dir runs/year2/paper_main --reports-dir reports/year2
```

## B: Open questions / missing pieces

- `Scripts/` ve `scripts/` çiftliği resmi olarak hangisi canonical olacak?
- `argus_py/runner/live_cli.py` canlıya uygun tam execution pipeline’a ne zaman tamamlanacak?
- v2.0 routing modeli için mevcut council akışı nasıl migrate edilecek (tek adım mı, compat phase mi)?
- `FUTURE_VISION.md` içindeki iç çelişkilerden hangisi resmi strateji seti olarak kilitlenecek?

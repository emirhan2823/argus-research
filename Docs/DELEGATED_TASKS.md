# Delegated Task Definitions

Bu dosya, diğer agentlara (Codex/Gemini/Sonnet) delegate edilecek task tanımlarını içerir.

## Execution Status Ledger (Synced: 2026-02-08 09:10 UTC)

| Task ID | Assigned To | Status | Nasıl Yapıldı (kısa) | Kanıt (dosya/test/log) |
|---|---|---|---|---|
| `P20-005` | `Codex` | `✅ DONE` | TelemetryWriter thread-safe lock, şema validasyonu ve atomic heartbeat yazımı ile implement edildi; unit testlerle davranış doğrulandı. | `Docs/AGENT_WORK_LOG_P20-005.md`; `pytest tests/unit/test_telemetry_writer.py -v` |
| `P20-009` | `Codex` | `✅ DONE` | Weekly audit pipeline decisions/trades/rejects akışını okuyup markdown rapor üretecek şekilde yazıldı; audit testleri geçti. | `Docs/AGENT_WORK_LOG_P20-009_P20-INTEG.md`; `pytest tests/unit/test_audit_pipeline.py -v` |
| `P20-INTEG` | `Codex` | `✅ DONE` | Kill-switch paper daemon entegrasyonu (persist + SOFT/HARD davranışı + heartbeat görünürlüğü) eklendi; entegrasyon testleri doğrulandı. | `Docs/AGENT_WORK_LOG_P20-009_P20-INTEG.md`; `pytest tests/unit/test_paper_daemon_kill_switch_integration.py -v` |
| `P20-ENH1` | `Codex` | `✅ DONE` | Orion göstergeleri ve scoring bileşenleri Swift contract’a uyumlu genişletildi; indicator testleri yeşil. | `Docs/AGENT_WORK_LOG_P20-ENH1_P20-ENH2_P20-ENH3.md`; `pytest tests/unit/test_orion_indicators.py -v` |
| `P20-ENH2` | `Codex` | `✅ DONE` | Aether-C macro engine (FGI/DXY/funding/cache fallback) modüler veri katmanıyla implement edildi; engine testleri geçti. | `Docs/AGENT_WORK_LOG_P20-ENH1_P20-ENH2_P20-ENH3.md`; `pytest tests/unit/test_aether_engine.py -v` |
| `P20-ENH3` | `Codex` | `✅ DONE` | Hermes-C sentiment engine RSS + keyword fallback + opsiyonel LLM entegrasyonu ile eklendi; sentiment testleri doğrulandı. | `Docs/AGENT_WORK_LOG_P20-ENH1_P20-ENH2_P20-ENH3.md`; `pytest tests/unit/test_hermes_engine.py -v` |
| `P20-ENH4` | `Codex` | `✅ DONE` | Council weighted voting ve veto mantığı yeni council modülleriyle implement edildi; council testleri geçti. | `Docs/AGENT_WORK_LOG_P20-ENH4_to_P21-004.md`; `pytest tests/unit/test_council.py -v` |
| `P20-ENH5` | `Codex` | `✅ DONE` | Chiron regime detection + indicator/weight state logic eklendi; regime testleri doğrulandı. | `Docs/AGENT_WORK_LOG_P20-ENH4_to_P21-004.md`; `pytest tests/unit/test_chiron.py -v` |
| `P20-ENH6` | `Codex` | `✅ DONE` | Phoenix channel reversion stratejisi (regression channel + scoring + target/SL) implement edildi; strateji testleri geçti. | `Docs/AGENT_WORK_LOG_P20-ENH4_to_P21-004.md`; `pytest tests/unit/test_phoenix.py -v` |
| `P20-ENH7` | `Codex` | `✅ DONE` | AutoPilot position management (Corse/Pulse, stop/trim/trailing/sizing) eklendi; karar akışı testleri doğrulandı. | `Docs/AGENT_WORK_LOG_P20-ENH4_to_P21-004.md`; `pytest tests/unit/test_autopilot.py -v` |
| `P21-001` | `Codex` | `✅ DONE` | Walk-forward modülü yeni window/report akışıyla refactor edildi; runner ve unit test kapsamı ile doğrulandı. | `Docs/AGENT_WORK_LOG_P20-ENH4_to_P21-004.md`; `pytest tests/unit/test_walk_forward.py -v` |
| `P21-002` | `Codex` | `✅ DONE` | Determinism manager + verify script ile seed/hash manifest kontrolü eklendi; determinism testleri ve script çıktısı doğrulandı. | `Docs/AGENT_WORK_LOG_P20-ENH4_to_P21-004.md`; `pytest tests/unit/test_determinism.py -v`; `python3 Scripts/verify_determinism.py --runs 2 --seed 42` |
| `P21-003` | `Sonnet` | `✅ DONE` | CI/packaging acceptance, hibrit kalite kapısıyla kapatıldı: `make install`, `make test`, `make lint`, `make pre-commit` başarıyla çalıştı; kalite kapısı aktif çekirdek modüllere uygulanırken `lint-all` strict modu teknik borç cleanup’u için korunmuştur. | `Docs/AGENT_WORK_LOG_P21-003_VERIFY_HYBRID_GATE.md`; `make install`; `make test`; `make lint`; `make pre-commit`; `venv/bin/pre-commit run --files argus_py/alerts/__init__.py argus_py/alerts/dispatcher.py argus_py/dashboard/app.py argus_py/security/vault.py argus_py/security/audit.py` |
| `P21-004` | `Codex` | `✅ DONE` | Realism engine (commission/slippage/funding) paper broker akışına bağlandı; maliyet model testleri geçti. | `Docs/AGENT_WORK_LOG_P20-ENH4_to_P21-004.md`; `pytest tests/unit/test_realism.py -v` |
| `P22-001` | `Codex` | `✅ DONE` | Multi-symbol portfolio manager (bucket exposure, limit checks, ranking) modülü eklendi; portfolio testleri geçti. | `tests/unit/test_portfolio_manager.py`; `pytest tests/unit/test_portfolio_manager.py -q` |
| `P22-002` | `Codex` | `✅ DONE` | Live broker bridge/safety katmanı ile testnet order ve guardrail akışı implement edildi; live broker testleri geçti. | `tests/unit/test_live_broker.py`; `pytest tests/unit/test_live_broker.py -q` |
| `P22-003` | `Sonnet` | `✅ DONE` | Dashboard backend/frontend/CLI implementasyonu unit test ve canlı Flask smoke testi ile doğrulandı; `/api/status`, `/api/trades`, `/api/equity`, `/api/rejections` endpointleri gerçek run verisiyle `200` döndü. | `Docs/AGENT_WORK_LOG_P21-003_P22-003_VERIFY_ROUND2.md`; `pytest tests/unit/test_dashboard.py -v`; `venv/bin/python Scripts/dashboard.py runs/phase19_twin/SOFT --host 127.0.0.1 --port 18080` |
| `P22-004` | `Codex` | `✅ DONE` | Chiron learner (outcome ingest + weight optimization + state persistence) eklendi; learner testleri geçti. | `tests/unit/test_chiron_learner.py`; `pytest tests/unit/test_chiron_learner.py -q` |
| `P23-001` | `Sonnet` | `✅ DONE` | Multi-channel alert dispatcher (`telegram/discord/email-stub`) ve alert template katmanı eklendi; async alert testleri ile davranış doğrulandı. | `Docs/AGENT_WORK_LOG_P21-003_P22-003_P23-001_P23-004.md`; `pytest tests/unit/test_alerts.py -v` |
| `P23-002` | `Codex` | `✅ DONE` | Disaster recovery backup/restore modülü required file checks ile eklendi; backup testleri doğrulandı. | `tests/unit/test_backup.py`; `pytest tests/unit/test_backup.py -q` |
| `P23-003` | `Codex` | `✅ DONE` | Profiling modülü eklenerek performance ölçüm alt yapısı kuruldu; profiler testleri geçti. | `tests/unit/test_profiler.py`; `pytest tests/unit/test_profiler.py -q` |
| `P23-004` | `Sonnet` | `✅ DONE` | Secure vault + audit logger eklendi (`argus_py/security/*`); key storage/encrypt-decrypt/API key retrieval ve audit log akışı testlerle doğrulandı. | `Docs/AGENT_WORK_LOG_P21-003_P22-003_P23-001_P23-004.md`; `pytest tests/unit/test_vault.py -v` |
| `P24-001` | `Codex` | `✅ DONE` | Unified async exchange adapters (Binance/Bybit/OKX) interface ile yazıldı; exchange unit testleri geçti. | `Docs/AGENT_WORK_LOG_P24-001_P24-003.md`; `pytest tests/unit/test_exchanges.py -v` |
| `P24-002` | `Sonnet` | `✅ DONE` | Telegram bot command seti (`status/trades/killswitch/report/balance`) Codex tarafından tamamlandı ve local command smoke-test yapıldı; latest log önceki versiyonu override eder. | `Docs/AGENT_WORK_LOG_P24-002_PLUS_REPORT_ENH_AND_LOCAL_TEST.md`; `pytest tests/unit/test_telegram_bot.py -v`; `python3 Scripts/telegram_local_command_test.py --run-dir runs/phase19_twin/STRICT --user-id 1` |
| `P24-003` | `Codex` | `✅ DONE` | ML signal model + feature engineering + training script tamamlandı; ML testleri ve script e2e doğrulandı. | `Docs/AGENT_WORK_LOG_P24-001_P24-003.md`; `pytest tests/unit/test_ml_model.py -v` |
| `P24-004` | `Sonnet` | `✅ DONE` | Compliance & reporting modülü (8949, PnL statement, CSV export) Codex tarafından tamamlandı ve komisyon bazlı cost-basis güncellemesi uygulandı; son log eski logu override eder. | `Docs/AGENT_WORK_LOG_P24-002_PLUS_REPORT_ENH_AND_LOCAL_TEST.md`; `pytest tests/unit/test_compliance.py -v`; `python3 Scripts/generate_tax_report.py runs/20260203_215219_56c032/trades.csv --year 2024 --output runs/20260203_215219_56c032/tax_report_2024.csv --statement-json runs/20260203_215219_56c032/tax_report_2024_summary.json` |

---

## Execution Summary (As of 2026-02-08 09:10 UTC)

- Toplam izlenen task: `26`
- Tamamlanan task: `26`
- Kısmi task: `0`
- Başlanmayan task: `0`
- Contract dışı açık kalan operasyon kalemleri:
  - `SOFT` risk seviyesinde seçici trade politikası kod implementasyonu (plan notu mevcut, kod henüz yok).
  - Tüm repo için strict `lint-all` temizlik sprinti (hibrit kalite kapısı aktif, strict kapı korunuyor).
  - Small-live geçişi öncesi uzun paper soak + performans review kapısı.

---

## P20-005: Telemetry Writer ✅ DONE

**Assign to:** Codex  
**Priority:** P0  
**Completed:** 2026-02-07  
**Commit:** `240d9b9`

### Objective
Create a thread-safe, schema-validated telemetry writer for decisions, trades, and rejects.

### Contract (implement exactly)

**File:** `argus_py/telemetry/writer.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class DecisionRow:
    timestamp: int
    bar_ts: int
    symbol: str
    verdict: str      # GO|WAIT|EXIT|SKIP
    direction: str    # LONG|SHORT|FLAT
    score: float
    adx: float
    exp_move: float
    regime: str       # TREND|CHOP|UNCERTAIN
    position_state: str

@dataclass
class TradeRow:
    timestamp: int
    symbol: str
    event: str        # OPEN|CLOSE|REJECTED
    side: str
    price: float
    quantity: float
    commission: float
    pnl: float
    position_id: str
    reject_reason: str  # Required if event=REJECTED

@dataclass
class RejectRow:
    timestamp: int
    bar_ts: int
    symbol: str
    code: str         # REJECT_* enum
    detail: str
    position_state: str
    risk_level: str

class TelemetryWriter:
    def __init__(self, run_dir: Path) -> None: ...
    def write_decision(self, row: DecisionRow) -> None: ...
    def write_trade(self, row: TradeRow) -> None: ...
    def write_reject(self, row: RejectRow) -> None: ...
    def update_heartbeat(self, state: dict) -> None: ...
    def flush(self) -> None: ...
```

### Invariants
1. Schema validation: `event=REJECTED` requires non-empty `reject_reason`
2. Heartbeat writes must be atomic (write temp, then rename)
3. Thread-safe (use threading.Lock)
4. Create CSVs with headers if don't exist

### Acceptance Criteria
- [x] All writes validate schema
- [x] REJECTED trades without reason raise ValueError
- [x] Heartbeat.json never corrupted on crash
- [x] Thread-safe under concurrent access (8 threads, 50 writes each)

### Verification ✅
```bash
pytest tests/unit/test_telemetry_writer.py -v
# Result: 12 tests passed (383 lines of tests)
```

### Files to Create
1. `argus_py/telemetry/writer.py`
2. `argus_py/telemetry/schemas.py` (optional, for validation)
3. `tests/unit/test_telemetry_writer.py`

---

## P20-009: Audit Pipeline ✅ DONE

**Assign to:** Codex  
**Priority:** P1  
**Completed:** 2026-02-07  
**Commit:** `240d9b9`

### Objective
Create weekly audit report generator that analyzes rejections and conversion rates.

### Contract (implement exactly)

**File:** `argus_py/reporting/audit_pipeline.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from datetime import date

@dataclass
class RejectionBreakdown:
    total_rejects: int
    by_code: Dict[str, int]       # {code: count}
    by_regime: Dict[str, int]
    top_5_codes: List[tuple]      # [(code, count), ...]

@dataclass
class ConversionMetrics:
    total_signals: int            # verdict=GO count
    total_opens: int              # event=OPEN count
    total_rejects: int            # event=REJECTED count
    conversion_rate: float        # opens / signals
    by_regime: Dict[str, float]   # {regime: rate}

@dataclass
class WeeklyAuditReport:
    week: str                     # e.g., "2026-W06"
    period_start: date
    period_end: date
    rejection_breakdown: RejectionBreakdown
    conversion_metrics: ConversionMetrics
    kill_switch_activations: int
    recommendations: List[str]

class AuditPipeline:
    def __init__(self, run_dir: Path) -> None: ...
    def generate_weekly_report(self, week: str) -> WeeklyAuditReport: ...
    def to_markdown(self, report: WeeklyAuditReport) -> str: ...
    def to_json(self, report: WeeklyAuditReport) -> str: ...
```

### Acceptance Criteria
- [x] Reads decisions.csv, trades.csv, rejects.csv
- [x] Handles missing files gracefully
- [x] Rejection counts sum correctly
- [x] Markdown output is readable

### Verification ✅
```bash
pytest tests/unit/test_audit_pipeline.py -v
# Result: 189 lines of tests passed
```

### Files to Create
1. `argus_py/reporting/audit_pipeline.py`
2. `Scripts/weekly_audit.py` (CLI wrapper)
3. `tests/unit/test_audit_pipeline.py`

---

## P20-INTEG: Kill-Switch Integration ✅ DONE

**Assign to:** Codex  
**Priority:** P0  
**Completed:** 2026-02-07  
**Commit:** `240d9b9`

### Objective
Integrate the new kill-switch into paper_daemon.py

### Changes Required

**File:** `Scripts/paper_daemon.py`

1. Import kill-switch:
```python
from argus_py.risk.kill_switch import KillSwitch, KillSwitchConfig, check_and_activate
```

2. Initialize in `PaperDaemon.__init__`:
```python
self.kill_switch = KillSwitch(KillSwitchConfig(
    soft_daily_loss_pct=self.cfg["daily_loss_limit_pct"],
    halt_dd_pct=self.cfg["kill_switch_dd_pct"]
))
```

3. Check before execution in `process_bar`:
```python
metrics = {
    'daily_pnl_pct': daily_pnl_pct,
    'total_dd_pct': current_dd_pct,
    'consecutive_losses': self.consecutive_losses,
    'api_errors_1h': self.api_errors_1h
}
level = check_and_activate(self.kill_switch, metrics)

if not self.kill_switch.can_trade():
    self.append_reject(bar, "REJECT_KILL_SWITCH", f"Level: {level.value}")
    return
```

4. Save state on shutdown:
```python
self.kill_switch.save_state(self.run_dir / "kill_switch_state.json")
```

### Acceptance Criteria
- [x] Kill-switch state persists across restarts
- [x] SOFT blocks new trades
- [x] HARD closes all positions (call broker.close_all)
- [x] REJECT_KILL_SWITCH appears in rejects.csv
- [x] Level visible in heartbeat.json

### Verification ✅
```bash
pytest tests/unit/test_paper_daemon_kill_switch_integration.py -v
# Result: 4 integration tests passed (92 lines)
```

---

## P20-ENH1: Orion Engine Enhancement

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 6 hours

### Objective
Enhance OrionEngine with full technical indicator suite matching Swift implementation.

### Current State
```python
# argus_py/models/orion/orion.py (current)
# Only has: ADX(14), SMA(50)
```

### Target State (from Swift TechnicalAnalysisEngine)

**File:** `argus_py/models/orion/indicators.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import pandas as pd

@dataclass
class IndicatorResult:
    value: float
    signal: str  # BULLISH|BEARISH|NEUTRAL
    strength: float  # 0-100

class IndicatorService:
    """Technical indicators matching Swift TechnicalAnalysisEngine"""
    
    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
        """Relative Strength Index"""
        ...
    
    @staticmethod
    def macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9
            ) -> Tuple[List[float], List[float], List[float]]:
        """MACD (line, signal, histogram)"""
        ...
    
    @staticmethod
    def bollinger(closes: List[float], period: int = 20, std_mult: float = 2.0
                 ) -> Tuple[List[float], List[float], List[float]]:
        """Bollinger Bands (upper, middle, lower)"""
        ...
    
    @staticmethod
    def stochastic(highs: List[float], lows: List[float], closes: List[float],
                   k_period: int = 14, d_period: int = 3
                  ) -> Tuple[List[float], List[float]]:
        """Stochastic (%K, %D)"""
        ...
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], 
            period: int = 14) -> List[Optional[float]]:
        """Average True Range"""
        ...
    
    @staticmethod
    def cci(highs: List[float], lows: List[float], closes: List[float],
            period: int = 20) -> List[Optional[float]]:
        """Commodity Channel Index"""
        ...
```

**File:** `argus_py/models/orion/orion.py` (MODIFY)

```python
@dataclass
class OrionScoreComponents:
    structure: float   # 0-35 (price vs MAs, channel position)
    trend: float       # 0-25 (ADX strength, EMA alignment)  
    momentum: float    # 0-25 (RSI, MACD, Stochastic)
    pattern: float     # 0-15 (divergence detection)

class OrionEngine:
    def calculate(self, history: List[Bar]) -> Optional[Vote]:
        # 1. Structure Score (35 max)
        sma50 = IndicatorService.sma(closes, 50)
        sma200 = IndicatorService.sma(closes, 200)
        bb = IndicatorService.bollinger(closes)
        structure_score = self._score_structure(price, sma50, sma200, bb)
        
        # 2. Trend Score (25 max)
        adx = IndicatorService.adx(highs, lows, closes)
        ema12 = IndicatorService.ema(closes, 12)
        ema26 = IndicatorService.ema(closes, 26)
        trend_score = self._score_trend(adx, ema12, ema26, price)
        
        # 3. Momentum Score (25 max)
        rsi = IndicatorService.rsi(closes)
        macd = IndicatorService.macd(closes)
        stoch = IndicatorService.stochastic(highs, lows, closes)
        momentum_score = self._score_momentum(rsi, macd, stoch)
        
        # 4. Pattern Score (15 max)
        pattern_score = self._detect_divergence(closes, rsi)
        
        total = structure_score + trend_score + momentum_score + pattern_score
        return Vote(...)
```

### Scoring Logic (from Swift OrionAnalysisService)

```python
def _score_structure(self, price, sma50, sma200, bb) -> float:
    score = 0
    # Price above both MAs: +15
    if price > sma50[-1] and price > sma200[-1]:
        score += 15
    # Golden Cross (SMA50 > SMA200): +10
    if sma50[-1] > sma200[-1]:
        score += 10
    # Price in lower Bollinger band: +10 (oversold opportunity)
    if price < bb.lower[-1]:
        score += 10
    return min(35, score)

def _score_momentum(self, rsi, macd, stoch) -> float:
    score = 0
    # RSI 30-70 normal, <30 oversold (+10), >70 overbought (-5)
    if rsi[-1] < 30:
        score += 10
    elif rsi[-1] > 70:
        score -= 5
    # MACD histogram positive: +8
    if macd.histogram[-1] > 0:
        score += 8
    # Stochastic %K > %D (bullish crossover): +7
    if stoch.k[-1] > stoch.d[-1]:
        score += 7
    return max(0, min(25, score))
```

### Acceptance Criteria
- [ ] RSI matches Swift output (test with known values)
- [ ] MACD crossover detection works
- [ ] Bollinger squeeze detection works
- [ ] Total score 0-100 with 4 components
- [ ] Backward compatible with existing Vote interface

### Verification
```bash
pytest tests/unit/test_orion_indicators.py -v
# Expected: 15+ indicator tests pass

python -c "
from argus_py.models.orion.orion import OrionEngine
from argus_py.data.loader import load_csv
bars = load_csv('argus_py/data/BTCUSDT.csv')[-200:]
engine = OrionEngine()
vote = engine.calculate(bars)
print(f'Score: {vote.score}, Direction: {vote.direction}')
print(f'Components: structure={vote.metadata.get(\"structure\")}, trend={vote.metadata.get(\"trend\")}')
"
```

### Files to Create/Modify
1. `argus_py/models/orion/indicators.py` (NEW - 200 lines)
2. `argus_py/models/orion/orion.py` (MODIFY - add scoring)
3. `tests/unit/test_orion_indicators.py` (NEW - 150 lines)

---

## P20-ENH2: Aether-C Crypto Macro Engine

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 6 hours

### Objective
Create crypto-native macro regime detector (Aether-C) using free APIs.

### Data Sources (All Free)

| Source | API | Data |
|--------|-----|------|
| Alternative.me | `https://api.alternative.me/fng/` | Fear & Greed Index |
| CoinGecko | `https://api.coingecko.com/api/v3/global` | Market Cap, BTC Dominance |
| Yahoo Finance | yfinance library | DXY (Dollar Index) |
| Binance | Public API | Funding Rates |

### Contract

**File:** `argus_py/models/aether/__init__.py` (NEW)
**File:** `argus_py/models/aether/aether.py` (NEW)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional
import httpx

class MacroRegime(Enum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"  
    NEUTRAL = "NEUTRAL"

@dataclass
class AetherComponents:
    fear_greed: float         # 0-100 (from Alternative.me)
    btc_dominance: float      # 0-100 (from CoinGecko)
    total_mcap_change: float  # % change 24h
    dxy_trend: str            # UP|DOWN|FLAT
    funding_rate: float       # Perpetual funding (from Binance)

@dataclass
class AetherResult:
    regime: MacroRegime
    score: float              # 0-100
    components: AetherComponents
    reasoning: str

class AetherEngine:
    """Crypto macro environment detector"""
    
    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self._cache: Optional[AetherResult] = None
        self._cache_time: float = 0
    
    async def evaluate(self, force_refresh: bool = False) -> AetherResult:
        """Main evaluation - returns cached if fresh"""
        ...
    
    async def _fetch_fear_greed(self) -> int:
        """Fetch from Alternative.me API"""
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.alternative.me/fng/?limit=1")
            data = r.json()
            return int(data["data"][0]["value"])
    
    async def _fetch_global_metrics(self) -> Dict:
        """Fetch from CoinGecko"""
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.coingecko.com/api/v3/global")
            return r.json()["data"]
    
    async def _fetch_dxy(self) -> float:
        """Fetch DXY from Yahoo Finance"""
        import yfinance as yf
        dxy = yf.Ticker("DX-Y.NYB")
        hist = dxy.history(period="5d")
        return hist["Close"].iloc[-1]
    
    async def _fetch_funding_rate(self, symbol: str = "BTCUSDT") -> float:
        """Fetch from Binance public API"""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1"
            )
            data = r.json()
            return float(data[0]["fundingRate"])
```

### Scoring Logic

```python
def _calculate_score(self, components: AetherComponents) -> float:
    score = 50  # Neutral baseline
    
    # Fear & Greed (weight: 30%)
    # <25 = Extreme Fear (+15), >75 = Extreme Greed (-10)
    if components.fear_greed < 25:
        score += 15  # Contrarian - good to buy
    elif components.fear_greed > 75:
        score -= 10  # Overheated
    elif components.fear_greed > 50:
        score += 5   # Mild greed = momentum
    
    # BTC Dominance (weight: 20%)
    # >50% = Risk-off (money flowing to BTC), <40% = Alt season
    if components.btc_dominance > 50:
        score -= 5   # Conservative market
    elif components.btc_dominance < 40:
        score += 10  # Alt season = risk-on
    
    # Total Market Cap Change (weight: 20%)
    if components.total_mcap_change > 3:
        score += 10  # Strong inflow
    elif components.total_mcap_change < -3:
        score -= 10  # Outflow
    
    # DXY Trend (weight: 15%)
    if components.dxy_trend == "DOWN":
        score += 8   # Weak dollar = risk-on
    elif components.dxy_trend == "UP":
        score -= 5   # Strong dollar = headwind
    
    # Funding Rate (weight: 15%)
    if components.funding_rate > 0.001:
        score -= 5   # Overleveraged longs
    elif components.funding_rate < -0.001:
        score += 8   # Shorts paying = bullish
    
    return max(0, min(100, score))

def _determine_regime(self, score: float) -> MacroRegime:
    if score >= 60:
        return MacroRegime.RISK_ON
    elif score <= 40:
        return MacroRegime.RISK_OFF
    return MacroRegime.NEUTRAL
```

### Acceptance Criteria
- [ ] Fear & Greed API works (no API key needed)
- [ ] CoinGecko rate limit handled (10 req/min)
- [ ] DXY fetch works via yfinance
- [ ] Funding rate from Binance public API
- [ ] Cache prevents excessive API calls
- [ ] Returns MacroRegime enum

### Verification
```bash
pytest tests/unit/test_aether_engine.py -v

python -c "
import asyncio
from argus_py.models.aether.aether import AetherEngine

async def test():
    engine = AetherEngine()
    result = await engine.evaluate()
    print(f'Regime: {result.regime.value}')
    print(f'Score: {result.score}')
    print(f'Fear/Greed: {result.components.fear_greed}')
    print(f'BTC Dom: {result.components.btc_dominance}%')

asyncio.run(test())
"
```

### Files to Create
1. `argus_py/models/aether/__init__.py` (NEW)
2. `argus_py/models/aether/aether.py` (NEW - 200 lines)
3. `argus_py/models/aether/data_sources.py` (NEW - 100 lines)
4. `tests/unit/test_aether_engine.py` (NEW - 100 lines)

### Dependencies to Add
```bash
pip install httpx yfinance
```

---

## P20-ENH3: Hermes-C Crypto Sentiment Engine

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 4 hours

### Objective
Port RSS + AI sentiment analysis for crypto news.

### RSS Sources (Crypto-Focused)

```python
CRYPTO_RSS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed"),
]
```

### Contract

**File:** `argus_py/models/hermes/__init__.py` (NEW)
**File:** `argus_py/models/hermes/hermes.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
import feedparser
from groq import Groq

class Sentiment(Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"

@dataclass
class NewsArticle:
    title: str
    source: str
    url: str
    published: str
    sentiment: Optional[Sentiment] = None
    confidence: float = 0.0

@dataclass  
class HermesResult:
    overall_sentiment: Sentiment
    sentiment_score: float      # -100 to +100
    articles_analyzed: int
    top_headlines: List[str]
    reasoning: str

class HermesEngine:
    """Crypto news sentiment analyzer"""
    
    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq = Groq(api_key=groq_api_key) if groq_api_key else None
    
    async def analyze(self, symbol: str = "BTC", limit: int = 10) -> HermesResult:
        """Fetch and analyze recent crypto news"""
        articles = await self._fetch_news(limit)
        
        if self.groq:
            articles = await self._analyze_with_ai(articles)
        else:
            articles = self._analyze_with_keywords(articles)
        
        return self._aggregate_sentiment(articles)
    
    async def _fetch_news(self, limit: int) -> List[NewsArticle]:
        """Fetch from RSS feeds"""
        articles = []
        for name, url in CRYPTO_RSS_FEEDS:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit // len(CRYPTO_RSS_FEEDS)]:
                articles.append(NewsArticle(
                    title=entry.title,
                    source=name,
                    url=entry.link,
                    published=entry.get("published", "")
                ))
        return articles[:limit]
    
    async def _analyze_with_ai(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Use Groq (Llama 3.1) for sentiment"""
        prompt = self._build_prompt([a.title for a in articles])
        
        response = self.groq.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        # Parse response and update articles
        ...
        return articles
    
    def _analyze_with_keywords(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Fallback keyword-based sentiment"""
        BULLISH = ["surge", "rally", "bullish", "rise", "gain", "adoption", "etf approved"]
        BEARISH = ["crash", "dump", "bearish", "fall", "hack", "ban", "regulation"]
        
        for article in articles:
            title_lower = article.title.lower()
            bull_count = sum(1 for w in BULLISH if w in title_lower)
            bear_count = sum(1 for w in BEARISH if w in title_lower)
            
            if bull_count > bear_count:
                article.sentiment = Sentiment.POSITIVE
                article.confidence = 0.6
            elif bear_count > bull_count:
                article.sentiment = Sentiment.NEGATIVE
                article.confidence = 0.6
            else:
                article.sentiment = Sentiment.NEUTRAL
                article.confidence = 0.4
        
        return articles
```

### AI Prompt Template

```python
SENTIMENT_PROMPT = '''
Analyze the sentiment of these crypto news headlines.
Return JSON: {"headlines": [{"index": 0, "sentiment": "POSITIVE|NEGATIVE|NEUTRAL", "confidence": 0.0-1.0}]}

Headlines:
{headlines}
'''
```

### Acceptance Criteria
- [ ] RSS parsing works for all 5 sources
- [ ] Keyword fallback works without API key
- [ ] Groq integration works when key provided
- [ ] Overall sentiment aggregated correctly
- [ ] Rate limiting for RSS fetches

### Verification
```bash
pytest tests/unit/test_hermes_engine.py -v

# Without AI (keyword only)
python -c "
import asyncio
from argus_py.models.hermes.hermes import HermesEngine

async def test():
    engine = HermesEngine()  # No API key
    result = await engine.analyze()
    print(f'Sentiment: {result.overall_sentiment.value}')
    print(f'Score: {result.sentiment_score}')
    print(f'Headlines: {len(result.top_headlines)}')

asyncio.run(test())
"
```

### Files to Create
1. `argus_py/models/hermes/__init__.py` (NEW)
2. `argus_py/models/hermes/hermes.py` (NEW - 150 lines)
3. `argus_py/models/hermes/rss_reader.py` (NEW - 50 lines)
4. `tests/unit/test_hermes_engine.py` (NEW - 80 lines)

### Dependencies
```bash
pip install feedparser groq
```

---

## P20-ENH4: Council Weighted Voting System

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 5 hours

### Objective
Implement weighted voting aggregator that combines all engine outputs (matching Swift ArgusGrandCouncil).

### Current State
```python
# argus_py/council/aggregator.py (current)
# Only aggregates Aegean + Orion with fixed weights
```

### Target State

**File:** `argus_py/council/council.py` (NEW)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from argus_py.models.orion.orion import OrionVote
from argus_py.models.aether.aether import AetherResult
from argus_py.models.hermes.hermes import HermesResult

class CouncilAction(Enum):
    AGGRESSIVE_BUY = "AGGRESSIVE_BUY"  # 80%+ allocation
    ACCUMULATE = "ACCUMULATE"          # 50% allocation
    HOLD = "HOLD"
    TRIM = "TRIM"                      # Sell 50%
    LIQUIDATE = "LIQUIDATE"            # Sell 100%

class SignalStrength(Enum):
    STRONG = "STRONG"
    NORMAL = "NORMAL"
    WEAK = "WEAK"  
    VETOED = "VETOED"

@dataclass
class ModuleVote:
    module: str           # "orion", "aether", "hermes", "phoenix"
    score: float          # 0-100
    direction: str        # LONG|SHORT|FLAT
    confidence: float     # 0-1
    reasons: List[str]

@dataclass
class CouncilDecision:
    action: CouncilAction
    strength: SignalStrength
    confidence: float             # 0-100
    reasoning: str
    votes: List[ModuleVote]
    weights_used: Dict[str, float]

class CouncilWeights:
    """Dynamic weights based on regime"""
    
    TREND_WEIGHTS = {
        "orion": 0.35,     # Technical dominates
        "aether": 0.20,
        "hermes": 0.15,
        "phoenix": 0.20,
        "aegean": 0.10
    }
    
    CHOP_WEIGHTS = {
        "orion": 0.15,     # Reduce technical
        "aether": 0.30,    # Macro more important
        "hermes": 0.20,
        "phoenix": 0.25,   # Reversion works in chop
        "aegean": 0.10
    }
    
    RISK_OFF_WEIGHTS = {
        "orion": 0.10,
        "aether": 0.40,    # Macro dominates
        "hermes": 0.30,    # News critical
        "phoenix": 0.10,
        "aegean": 0.10
    }
    
    @classmethod
    def get_for_regime(cls, regime: str) -> Dict[str, float]:
        if regime == "TREND":
            return cls.TREND_WEIGHTS
        elif regime == "CHOP":
            return cls.CHOP_WEIGHTS
        elif regime == "RISK_OFF":
            return cls.RISK_OFF_WEIGHTS
        return cls.TREND_WEIGHTS  # Default


class GrandCouncil:
    """Aggregates all engine votes into final decision"""
    
    def convene(
        self,
        orion_vote: Optional[OrionVote],
        aether_result: Optional[AetherResult],
        hermes_result: Optional[HermesResult],
        phoenix_score: Optional[float],
        aegean_vote: Optional[ModuleVote],
        regime: str = "TREND"
    ) -> CouncilDecision:
        
        # 1. Get regime-aware weights
        weights = CouncilWeights.get_for_regime(regime)
        
        # 2. Collect votes
        votes = self._collect_votes(orion_vote, aether_result, hermes_result, 
                                     phoenix_score, aegean_vote)
        
        # 3. Calculate weighted score
        weighted_score = self._calculate_weighted_score(votes, weights)
        
        # 4. Determine action
        action = self._determine_action(weighted_score, votes)
        
        # 5. Check for vetoes
        strength = self._check_vetoes(votes, action)
        
        return CouncilDecision(
            action=action,
            strength=strength,
            confidence=weighted_score,
            reasoning=self._generate_reasoning(votes, action),
            votes=votes,
            weights_used=weights
        )
    
    def _calculate_weighted_score(self, votes: List[ModuleVote], 
                                   weights: Dict[str, float]) -> float:
        total_weight = 0
        weighted_sum = 0
        
        for vote in votes:
            if vote.module in weights:
                w = weights[vote.module]
                weighted_sum += vote.score * w
                total_weight += w
        
        return weighted_sum / total_weight if total_weight > 0 else 50.0
    
    def _determine_action(self, score: float, votes: List[ModuleVote]) -> CouncilAction:
        # Count directions
        long_count = sum(1 for v in votes if v.direction == "LONG")
        short_count = sum(1 for v in votes if v.direction == "SHORT")
        
        if score >= 75 and long_count >= 3:
            return CouncilAction.AGGRESSIVE_BUY
        elif score >= 60 and long_count >= 2:
            return CouncilAction.ACCUMULATE
        elif score <= 35 and short_count >= 3:
            return CouncilAction.LIQUIDATE
        elif score <= 45 and short_count >= 2:
            return CouncilAction.TRIM
        return CouncilAction.HOLD
    
    def _check_vetoes(self, votes: List[ModuleVote], action: CouncilAction) -> SignalStrength:
        # Aether RISK_OFF vetoes buys
        aether = next((v for v in votes if v.module == "aether"), None)
        if aether and aether.score < 30 and action in [CouncilAction.AGGRESSIVE_BUY, CouncilAction.ACCUMULATE]:
            return SignalStrength.VETOED
        
        # Hermes extreme negative vetoes buys
        hermes = next((v for v in votes if v.module == "hermes"), None)
        if hermes and hermes.score < 20 and action in [CouncilAction.AGGRESSIVE_BUY, CouncilAction.ACCUMULATE]:
            return SignalStrength.VETOED
        
        # Strong consensus
        if all(v.confidence > 0.7 for v in votes if v.confidence > 0):
            return SignalStrength.STRONG
        
        return SignalStrength.NORMAL
```

### Acceptance Criteria
- [ ] Regime-based weight selection works
- [ ] Weighted score calculation correct
- [ ] Veto logic blocks inappropriate actions
- [ ] All module votes collected correctly
- [ ] Output matches CouncilDecision schema

### Verification
```bash
pytest tests/unit/test_council.py -v

python -c "
from argus_py.council.council import GrandCouncil, ModuleVote

council = GrandCouncil()
decision = council.convene(
    orion_vote=ModuleVote('orion', 75, 'LONG', 0.8, ['Trend up']),
    aether_result=None,
    hermes_result=None,
    phoenix_score=65,
    aegean_vote=ModuleVote('aegean', 70, 'LONG', 0.7, ['Momentum']),
    regime='TREND'
)
print(f'Action: {decision.action.value}')
print(f'Strength: {decision.strength.value}')
print(f'Confidence: {decision.confidence:.1f}')
"
```

### Files to Create
1. `argus_py/council/council.py` (NEW - 250 lines)
2. `argus_py/council/weights.py` (NEW - 50 lines)
3. `tests/unit/test_council.py` (NEW - 100 lines)

---

## P20-ENH5: Chiron Regime Detection Engine

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 4 hours

### Objective
Implement regime detector that adjusts engine weights dynamically (matching Swift ChironRegimeEngine).

### Contract

**File:** `argus_py/models/chiron/__init__.py` (NEW)
**File:** `argus_py/models/chiron/chiron.py` (NEW)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, List
import json
from pathlib import Path

class MarketRegime(Enum):
    TREND = "TREND"
    CHOP = "CHOP"
    RISK_OFF = "RISK_OFF"
    NEWS_SHOCK = "NEWS_SHOCK"
    NEUTRAL = "NEUTRAL"

@dataclass
class RegimeContext:
    orion_score: Optional[float]
    aether_score: Optional[float]
    hermes_score: Optional[float]
    adx: float
    chop_index: float        # Choppiness Index
    recent_volatility: float  # ATR / Price %

@dataclass
class ChironResult:
    regime: MarketRegime
    core_weights: Dict[str, float]    # Long-term components
    pulse_weights: Dict[str, float]   # Short-term components
    explanation: str
    confidence: float

class ChironRegimeEngine:
    """Detects market regime and adjusts weights"""
    
    def __init__(self, state_path: Optional[Path] = None):
        self.state_path = state_path
        self._last_regime: MarketRegime = MarketRegime.NEUTRAL
    
    def evaluate(self, context: RegimeContext) -> ChironResult:
        regime = self._detect_regime(context)
        core, pulse = self._get_base_weights(regime)
        
        # Adjust for missing data
        core = self._adjust_for_missing(core, context)
        pulse = self._adjust_for_missing(pulse, context)
        
        return ChironResult(
            regime=regime,
            core_weights=core,
            pulse_weights=pulse,
            explanation=self._explain(regime, context),
            confidence=self._calculate_confidence(context)
        )
    
    def _detect_regime(self, ctx: RegimeContext) -> MarketRegime:
        aether = ctx.aether_score or 50
        orion = ctx.orion_score or 50
        hermes = ctx.hermes_score or 50
        
        # 1. Check for News Shock
        if hermes < 20 or hermes > 85:
            return MarketRegime.NEWS_SHOCK
        
        # 2. Check for Risk-Off
        if aether < 35:
            return MarketRegime.RISK_OFF
        
        # 3. Check for Trend
        if ctx.adx >= 25 and ctx.chop_index < 45:
            return MarketRegime.TREND
        
        # 4. Check for Chop
        if ctx.chop_index > 60 or (ctx.adx < 20 and 40 < orion < 60):
            return MarketRegime.CHOP
        
        return MarketRegime.NEUTRAL
    
    def _get_base_weights(self, regime: MarketRegime) -> tuple:
        WEIGHT_TABLE = {
            MarketRegime.TREND: (
                {"orion": 0.35, "aether": 0.20, "hermes": 0.15, "phoenix": 0.20, "aegean": 0.10},
                {"orion": 0.40, "phoenix": 0.30, "hermes": 0.15, "aegean": 0.15}
            ),
            MarketRegime.CHOP: (
                {"orion": 0.15, "aether": 0.30, "hermes": 0.20, "phoenix": 0.25, "aegean": 0.10},
                {"phoenix": 0.40, "hermes": 0.25, "orion": 0.20, "aegean": 0.15}
            ),
            MarketRegime.RISK_OFF: (
                {"aether": 0.40, "hermes": 0.30, "orion": 0.10, "phoenix": 0.10, "aegean": 0.10},
                {"hermes": 0.50, "aether": 0.30, "phoenix": 0.10, "orion": 0.10}
            ),
            MarketRegime.NEWS_SHOCK: (
                {"hermes": 0.50, "aether": 0.25, "orion": 0.10, "phoenix": 0.05, "aegean": 0.10},
                {"hermes": 0.60, "aether": 0.20, "phoenix": 0.10, "orion": 0.10}
            ),
            MarketRegime.NEUTRAL: (
                {"orion": 0.25, "aether": 0.25, "hermes": 0.20, "phoenix": 0.20, "aegean": 0.10},
                {"orion": 0.25, "phoenix": 0.25, "hermes": 0.25, "aegean": 0.25}
            )
        }
        return WEIGHT_TABLE.get(regime, WEIGHT_TABLE[MarketRegime.NEUTRAL])
    
    def _adjust_for_missing(self, weights: Dict[str, float], ctx: RegimeContext) -> Dict[str, float]:
        """Zero out weights for missing modules, redistribute"""
        adjusted = weights.copy()
        
        if ctx.orion_score is None:
            adjusted["orion"] = 0
        if ctx.aether_score is None:
            adjusted["aether"] = 0
        if ctx.hermes_score is None:
            adjusted["hermes"] = 0
        
        # Normalize
        total = sum(adjusted.values())
        if total > 0:
            return {k: v/total for k, v in adjusted.items()}
        return adjusted
    
    def save_state(self, path: Path):
        state = {"last_regime": self._last_regime.value}
        path.write_text(json.dumps(state))
    
    def load_state(self, path: Path):
        if path.exists():
            state = json.loads(path.read_text())
            self._last_regime = MarketRegime(state.get("last_regime", "NEUTRAL"))
```

### Choppiness Index Calculation

```python
def calculate_chop_index(highs: List[float], lows: List[float], 
                          closes: List[float], period: int = 14) -> float:
    """Choppiness Index: 0-100, higher = more choppy"""
    import math
    
    atr_sum = 0
    for i in range(1, period + 1):
        tr = max(highs[-i] - lows[-i], 
                 abs(highs[-i] - closes[-i-1]),
                 abs(lows[-i] - closes[-i-1]))
        atr_sum += tr
    
    highest = max(highs[-period:])
    lowest = min(lows[-period:])
    
    if highest == lowest:
        return 50.0
    
    chop = 100 * math.log10(atr_sum / (highest - lowest)) / math.log10(period)
    return max(0, min(100, chop))
```

### Acceptance Criteria
- [ ] All 5 regimes detected correctly
- [ ] Weight tables match Swift implementation
- [ ] Missing module adjustment works
- [ ] State persistence works
- [ ] Choppiness Index calculation correct

### Verification
```bash
pytest tests/unit/test_chiron.py -v

python -c "
from argus_py.models.chiron.chiron import ChironRegimeEngine, RegimeContext

engine = ChironRegimeEngine()
result = engine.evaluate(RegimeContext(
    orion_score=45,
    aether_score=30,
    hermes_score=50,
    adx=15,
    chop_index=65,
    recent_volatility=2.5
))
print(f'Regime: {result.regime.value}')
print(f'Core Weights: {result.core_weights}')
"
```

### Files to Create
1. `argus_py/models/chiron/__init__.py` (NEW)
2. `argus_py/models/chiron/chiron.py` (NEW - 200 lines)
3. `argus_py/models/chiron/indicators.py` (NEW - choppiness calc - 50 lines)
4. `tests/unit/test_chiron.py` (NEW - 80 lines)

---

## P20-ENH6: Phoenix Channel Reversion Strategy

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 4 hours

### Objective
Port linear regression channel reversion strategy (matching Swift PhoenixLogic).

### Contract

**File:** `argus_py/models/phoenix/__init__.py` (NEW)
**File:** `argus_py/models/phoenix/phoenix.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np

@dataclass
class ChannelLevels:
    upper: float
    middle: float
    lower: float
    slope: float
    r_squared: float  # Channel validity

@dataclass
class PhoenixSignals:
    touch_lower_band: bool
    rsi_reversal: bool
    bullish_divergence: bool
    trend_ok: bool

@dataclass
class PhoenixAdvice:
    score: float           # 0-100
    entry_price: float
    stop_loss: float       # Invalidation level
    target_1: float        # Mid-band
    target_2: float        # Upper-band
    channel: ChannelLevels
    signals: PhoenixSignals
    reason: str
    r_squared: float

class PhoenixEngine:
    """Linear Regression Channel Mean Reversion"""
    
    def __init__(self, lookback: int = 60, channel_k: float = 2.0):
        self.lookback = lookback
        self.channel_k = channel_k
    
    def analyze(self, closes: List[float], highs: List[float], 
                lows: List[float]) -> Optional[PhoenixAdvice]:
        
        if len(closes) < self.lookback:
            return None
        
        # 1. Calculate Linear Regression Channel
        channel = self._calculate_channel(closes[-self.lookback:])
        
        # 2. Check R-Squared validity (must be > 0.25)
        if channel.r_squared < 0.25:
            return PhoenixAdvice(
                score=0, entry_price=closes[-1], stop_loss=0, target_1=0, target_2=0,
                channel=channel, signals=PhoenixSignals(False, False, False, False),
                reason="Channel weak (R² < 0.25)", r_squared=channel.r_squared
            )
        
        # 3. Calculate RSI
        rsi = self._calculate_rsi(closes, 14)
        current_rsi = rsi[-1] if rsi else 50
        
        # 4. Detect signals
        price = closes[-1]
        signals = PhoenixSignals(
            touch_lower_band=price <= channel.lower * 1.005,
            rsi_reversal=current_rsi < 35 and rsi[-2] < current_rsi if len(rsi) > 1 else False,
            bullish_divergence=self._check_divergence(closes, rsi),
            trend_ok=channel.slope > -(channel.middle * 0.0005)
        )
        
        # 5. Calculate score
        score = self._calculate_score(signals, current_rsi, channel)
        
        # 6. Calculate levels
        atr = self._calculate_atr(highs, lows, closes, 14)
        stop_loss = channel.lower - (1.25 * atr) if signals.touch_lower_band else price - (2 * atr)
        
        return PhoenixAdvice(
            score=score,
            entry_price=price,
            stop_loss=stop_loss,
            target_1=channel.middle,
            target_2=channel.upper if channel.slope > 0 else channel.middle + (channel.upper - channel.middle) * 0.5,
            channel=channel,
            signals=signals,
            reason=self._generate_reason(score, signals, channel.slope),
            r_squared=channel.r_squared
        )
    
    def _calculate_channel(self, closes: List[float]) -> ChannelLevels:
        """Linear Regression Channel with R-squared"""
        n = len(closes)
        x = np.arange(n)
        y = np.array(closes)
        
        # Linear regression
        x_mean = x.mean()
        y_mean = y.mean()
        
        slope = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
        intercept = y_mean - slope * x_mean
        
        # Calculate regression line values
        y_pred = slope * x + intercept
        
        # Standard deviation of residuals
        residuals = y - y_pred
        sigma = np.std(residuals)
        
        # R-squared
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        mid = y_pred[-1]
        upper = mid + (self.channel_k * sigma)
        lower = mid - (self.channel_k * sigma)
        
        return ChannelLevels(upper, mid, lower, slope, r_squared)
    
    def _calculate_score(self, signals: PhoenixSignals, rsi: float, 
                          channel: ChannelLevels) -> float:
        score = 50.0
        
        # Mean reversion signals
        if signals.touch_lower_band:
            score += 20
        if signals.rsi_reversal:
            score += 15
        if signals.bullish_divergence:
            score += 15
        if rsi < 35:
            score += 10
        if signals.trend_ok:
            score += 5
        
        # Penalties
        if channel.slope < 0:
            score -= 15
        sigma_pct = (channel.upper - channel.lower) / channel.middle / 2
        if sigma_pct > 0.08:  # High volatility
            score -= 10
        if rsi > 50:
            score -= 15
        
        return max(0, min(100, score))
```

### Acceptance Criteria
- [ ] Linear regression channel calculation matches Swift
- [ ] R-squared filter works (reject weak channels)
- [ ] RSI divergence detection works
- [ ] Scoring logic matches Swift PhoenixLogic
- [ ] Stop loss and targets calculated correctly

### Verification
```bash
pytest tests/unit/test_phoenix.py -v

python -c "
from argus_py.models.phoenix.phoenix import PhoenixEngine
from argus_py.data.loader import load_csv

bars = load_csv('argus_py/data/BTCUSDT.csv')[-100:]
closes = [b.close for b in bars]
highs = [b.high for b in bars]
lows = [b.low for b in bars]

engine = PhoenixEngine()
advice = engine.analyze(closes, highs, lows)
print(f'Score: {advice.score}')
print(f'R²: {advice.r_squared:.3f}')
print(f'Entry: {advice.entry_price:.2f}, SL: {advice.stop_loss:.2f}')
print(f'T1: {advice.target_1:.2f}, T2: {advice.target_2:.2f}')
"
```

### Files to Create
1. `argus_py/models/phoenix/__init__.py` (NEW)
2. `argus_py/models/phoenix/phoenix.py` (NEW - 200 lines)
3. `tests/unit/test_phoenix.py` (NEW - 80 lines)

---

## P20-ENH7: AutoPilot Position Management

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 5 hours

### Objective
Implement automated position entry/exit logic (matching Swift ArgusAutoPilotEngine).

### Contract

**File:** `argus_py/autopilot/__init__.py` (NEW)
**File:** `argus_py/autopilot/autopilot.py` (NEW)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

class AutoPilotMode(Enum):
    CORSE = "CORSE"   # Swing: wider stops, longer holds
    PULSE = "PULSE"   # Scalp: tight stops, quick exits

@dataclass
class TradePosition:
    symbol: str
    entry_price: float
    quantity: float
    mode: AutoPilotMode
    entry_time: float
    high_water_mark: float  # For trailing stop
    engine: str             # Which engine triggered

@dataclass
class AutoPilotSignal:
    action: str             # BUY|SELL|TRIM|HOLD
    quantity: float
    reason: str
    stop_loss: Optional[float]
    take_profit: Optional[float]
    trim_percentage: Optional[float]

@dataclass
class AutoPilotConfig:
    # Risk limits
    max_risk_per_trade_pct: float = 1.0   # 1% of portfolio
    max_equity_exposure: float = 1.0       # 100%
    
    # Corse (Swing) settings
    corse_stop_pct: float = 8.0
    corse_trim_threshold_pct: float = 20.0
    corse_trailing_activation_pct: float = 5.0
    corse_trailing_distance_pct: float = 2.5
    
    # Pulse (Scalp) settings
    pulse_stop_pct: float = 5.0
    pulse_trim_threshold_pct: float = 10.0
    pulse_trailing_activation_pct: float = 3.0
    pulse_trailing_distance_pct: float = 1.5
    
    # Entry
    min_score_for_entry: float = 65.0
    min_confidence_pct: float = 40.0


class AutoPilotEngine:
    """Handles position entry and exit logic"""
    
    def __init__(self, config: AutoPilotConfig = None):
        self.config = config or AutoPilotConfig()
    
    def evaluate(
        self,
        symbol: str,
        current_price: float,
        council_score: float,
        council_action: str,
        existing_position: Optional[TradePosition],
        portfolio_equity: float,
        cash_available: float
    ) -> AutoPilotSignal:
        
        if existing_position:
            return self._manage_existing(symbol, current_price, council_score, existing_position)
        else:
            return self._evaluate_entry(symbol, current_price, council_score, council_action,
                                        portfolio_equity, cash_available)
    
    def _manage_existing(self, symbol: str, price: float, score: float,
                          pos: TradePosition) -> AutoPilotSignal:
        """The Harvester - manage open positions"""
        pnl_pct = ((price - pos.entry_price) / pos.entry_price) * 100
        mode = pos.mode
        cfg = self.config
        
        # Get mode-specific thresholds
        if mode == AutoPilotMode.CORSE:
            stop_pct = cfg.corse_stop_pct
            trim_pct = cfg.corse_trim_threshold_pct
            trail_activate = cfg.corse_trailing_activation_pct
            trail_distance = cfg.corse_trailing_distance_pct
        else:  # PULSE
            stop_pct = cfg.pulse_stop_pct
            trim_pct = cfg.pulse_trim_threshold_pct
            trail_activate = cfg.pulse_trailing_activation_pct
            trail_distance = cfg.pulse_trailing_distance_pct
        
        # 1. HARD STOP
        if pnl_pct < -stop_pct:
            return AutoPilotSignal("SELL", pos.quantity, f"Stop Loss ({pnl_pct:.1f}%)", None, None, None)
        
        # 2. TRIM PROFITS
        if pnl_pct > trim_pct:
            return AutoPilotSignal("TRIM", pos.quantity * 0.3, f"Profit Taking ({pnl_pct:.1f}%)", None, None, 0.3)
        
        # 3. TRAILING STOP
        drawdown_from_high = ((pos.high_water_mark - price) / pos.high_water_mark) * 100
        if pnl_pct > trail_activate and drawdown_from_high > trail_distance:
            return AutoPilotSignal("SELL", pos.quantity, f"Trailing Stop (DD: {drawdown_from_high:.1f}%)", None, None, None)
        
        # 4. THESIS BROKEN
        score_threshold = 55 if mode == AutoPilotMode.CORSE else 50
        if score < score_threshold and pnl_pct < 0:
            return AutoPilotSignal("SELL", pos.quantity, f"Thesis Broken (Score: {score:.0f})", None, None, None)
        
        return AutoPilotSignal("HOLD", 0, "Position OK", None, None, None)
    
    def _evaluate_entry(self, symbol: str, price: float, score: float, action: str,
                         equity: float, cash: float) -> AutoPilotSignal:
        """The Hunter - find new entries"""
        
        if score < self.config.min_score_for_entry:
            return AutoPilotSignal("HOLD", 0, f"Score too low ({score:.0f})", None, None, None)
        
        if action not in ["AGGRESSIVE_BUY", "ACCUMULATE"]:
            return AutoPilotSignal("HOLD", 0, f"No buy signal ({action})", None, None, None)
        
        # Calculate position size (1% risk)
        risk_amount = equity * (self.config.max_risk_per_trade_pct / 100)
        assumed_stop_pct = 5.0  # Default 5% stop
        position_value = risk_amount / (assumed_stop_pct / 100)
        
        # Cap by available cash
        position_value = min(position_value, cash * 0.95)
        quantity = position_value / price
        
        if quantity <= 0:
            return AutoPilotSignal("HOLD", 0, "Insufficient cash", None, None, None)
        
        stop_loss = price * (1 - assumed_stop_pct / 100)
        take_profit = price * 1.15  # 15% target
        
        return AutoPilotSignal("BUY", quantity, f"Entry Signal (Score: {score:.0f})", stop_loss, take_profit, None)
    
    def update_high_water_mark(self, position: TradePosition, current_price: float) -> TradePosition:
        """Update position's high water mark for trailing stop"""
        if current_price > position.high_water_mark:
            position.high_water_mark = current_price
        return position
```

### Acceptance Criteria
- [ ] Corse vs Pulse mode differences work
- [ ] Stop loss triggers at correct thresholds
- [ ] Trim profits at correct thresholds
- [ ] Trailing stop activates and triggers correctly
- [ ] Position sizing respects 1% risk rule
- [ ] High water mark updates correctly

### Verification
```bash
pytest tests/unit/test_autopilot.py -v

python -c "
from argus_py.autopilot.autopilot import AutoPilotEngine, TradePosition, AutoPilotMode

engine = AutoPilotEngine()

# Test new entry
signal = engine.evaluate(
    symbol='BTCUSDT',
    current_price=50000,
    council_score=72,
    council_action='ACCUMULATE',
    existing_position=None,
    portfolio_equity=10000,
    cash_available=5000
)
print(f'Entry: {signal.action}, Qty: {signal.quantity:.4f}, Reason: {signal.reason}')

# Test exit
pos = TradePosition('BTCUSDT', 50000, 0.1, AutoPilotMode.PULSE, 0, 52000, 'orion')
signal = engine.evaluate('BTCUSDT', 48000, 45, 'HOLD', pos, 10000, 0)
print(f'Exit: {signal.action}, Reason: {signal.reason}')
"
```

### Files to Create
1. `argus_py/autopilot/__init__.py` (NEW)
2. `argus_py/autopilot/autopilot.py` (NEW - 250 lines)
3. `argus_py/autopilot/config.py` (NEW - 50 lines)
4. `tests/unit/test_autopilot.py` (NEW - 120 lines)

---

# PHASE 21: Infrastructure & Quality (Weeks 7-12)

---

## P21-001: Walk-Forward Enhancements

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 6 hours

### Objective
Make walk-forward backtest robust: no NO_DATA errors, proper windowing, 12-month baseline.

### Current State
```python
# argus_py/lab/walk_forward.py exists but has issues:
# - Some windows fail with NO_DATA
# - Windowing logic not clear
# - No proper result aggregation
```

### Contract

**File:** `argus_py/lab/walk_forward.py` (ENHANCE)

```python
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import date, timedelta
import pandas as pd
from pathlib import Path

@dataclass
class WFWindow:
    start: date
    end: date
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    
@dataclass
class WFResult:
    window: WFWindow
    train_trades: int
    test_trades: int
    train_sharpe: float
    test_sharpe: float
    test_pnl: float
    test_dd: float
    test_wr: float

@dataclass
class WFReport:
    windows: List[WFResult]
    aggregate_sharpe: float
    aggregate_pnl: float
    aggregate_dd: float
    no_data_windows: List[int]  # Should be empty

class WalkForwardEngine:
    """Walk-forward optimization engine with proper error handling."""
    
    def __init__(self, data_path: Path, output_dir: Path):
        self.data_path = data_path
        self.output_dir = output_dir
    
    def create_windows(
        self,
        start_date: date,
        end_date: date,
        train_months: int = 6,
        test_months: int = 1,
        step_months: int = 1
    ) -> List[WFWindow]:
        """
        Create non-overlapping test windows with rolling training.
        
        Args:
            start_date: Overall start
            end_date: Overall end
            train_months: Training window size
            test_months: Test window size
            step_months: Step between windows
        
        Returns:
            List of WFWindow objects
        """
        ...
    
    def validate_data(self, window: WFWindow) -> Tuple[bool, str]:
        """
        Check if sufficient data exists for window.
        
        Returns:
            (is_valid, error_message)
        """
        ...
    
    def run_window(self, window: WFWindow) -> WFResult:
        """
        Run single window: train, then test.
        
        Raises:
            ValueError: If data validation fails
        """
        ...
    
    def run_full(
        self,
        start_date: date,
        end_date: date,
        symbols: List[str] = ["BTCUSDT"],
        skip_invalid: bool = True
    ) -> WFReport:
        """
        Run full walk-forward simulation.
        
        Args:
            skip_invalid: If True, skip windows with no data instead of failing
        
        Returns:
            Complete report with all window results
        """
        ...
    
    def save_report(self, report: WFReport, filename: str) -> Path:
        """Save report as JSON and CSV."""
        ...
```

### Window Creation Logic

```python
def create_windows(self, start_date, end_date, train_months=6, test_months=1, step_months=1):
    windows = []
    current_test_start = start_date + timedelta(days=train_months * 30)
    
    while current_test_start + timedelta(days=test_months * 30) <= end_date:
        train_start = current_test_start - timedelta(days=train_months * 30)
        train_end = current_test_start - timedelta(days=1)
        test_end = current_test_start + timedelta(days=test_months * 30) - timedelta(days=1)
        
        windows.append(WFWindow(
            start=train_start,
            end=test_end,
            train_start=train_start,
            train_end=train_end,
            test_start=current_test_start,
            test_end=test_end
        ))
        
        current_test_start += timedelta(days=step_months * 30)
    
    return windows
```

### Acceptance Criteria
- [ ] 12-month run completes without NO_DATA errors
- [ ] Each window produces train + test metrics
- [ ] Aggregate metrics calculated correctly
- [ ] Report saves to JSON and CSV
- [ ] Invalid windows logged but don't crash

### Verification
```bash
pytest tests/unit/test_walk_forward.py -v

python -c "
from argus_py.lab.walk_forward import WalkForwardEngine
from datetime import date
from pathlib import Path

engine = WalkForwardEngine(
    data_path=Path('argus_py/data'),
    output_dir=Path('runs/wf_test')
)

windows = engine.create_windows(
    start_date=date(2025, 1, 1),
    end_date=date(2026, 1, 1),
    train_months=6,
    test_months=1
)
print(f'Created {len(windows)} windows')
for w in windows[:3]:
    print(f'  Train: {w.train_start} to {w.train_end}')
    print(f'  Test:  {w.test_start} to {w.test_end}')
"
```

### Files to Modify/Create
1. `argus_py/lab/walk_forward.py` (ENHANCE - 300 lines)
2. `Scripts/sprint1_walkforward_12m.py` (ENHANCE)
3. `tests/unit/test_walk_forward.py` (NEW - 100 lines)

---

## P21-002: Deterministic Backtest Module

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 4 hours

### Objective
Guarantee reproducibility: same seed → identical results.

### Contract

**File:** `argus_py/lab/determinism.py` (NEW)

```python
from dataclasses import dataclass
from typing import Any, Dict, List
import hashlib
import json
from pathlib import Path
import random
import numpy as np

@dataclass
class RunManifest:
    run_id: str
    seed: int
    timestamp: str
    git_commit: str
    config_hash: str
    data_hash: str
    result_hash: str

class DeterminismManager:
    """Ensures reproducible backtest runs."""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
    
    def initialize(self) -> None:
        """
        Set all random seeds for reproducibility.
        Must be called before any randomness is used.
        """
        random.seed(self.seed)
        np.random.seed(self.seed)
        # If using torch: torch.manual_seed(self.seed)
    
    def hash_config(self, config: Dict[str, Any]) -> str:
        """Generate hash of configuration."""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    def hash_data(self, data_path: Path) -> str:
        """Generate hash of input data."""
        if data_path.is_file():
            return hashlib.sha256(data_path.read_bytes()).hexdigest()[:16]
        else:
            # Hash all CSV files in directory
            file_hashes = []
            for f in sorted(data_path.glob("*.csv")):
                file_hashes.append(hashlib.sha256(f.read_bytes()).hexdigest())
            return hashlib.sha256("".join(file_hashes).encode()).hexdigest()[:16]
    
    def hash_results(self, trades_csv: Path) -> str:
        """Generate hash of trade results."""
        if trades_csv.exists():
            return hashlib.sha256(trades_csv.read_bytes()).hexdigest()[:16]
        return "NO_TRADES"
    
    def get_git_commit(self) -> str:
        """Get current git commit hash."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True
            )
            return result.stdout.strip()[:8]
        except:
            return "UNKNOWN"
    
    def create_manifest(
        self,
        run_id: str,
        config: Dict[str, Any],
        data_path: Path,
        trades_csv: Path
    ) -> RunManifest:
        """Create manifest for a completed run."""
        from datetime import datetime
        return RunManifest(
            run_id=run_id,
            seed=self.seed,
            timestamp=datetime.now().isoformat(),
            git_commit=self.get_git_commit(),
            config_hash=self.hash_config(config),
            data_hash=self.hash_data(data_path),
            result_hash=self.hash_results(trades_csv)
        )
    
    def save_manifest(self, manifest: RunManifest, path: Path) -> None:
        """Save manifest to JSON file."""
        path.write_text(json.dumps({
            "run_id": manifest.run_id,
            "seed": manifest.seed,
            "timestamp": manifest.timestamp,
            "git_commit": manifest.git_commit,
            "config_hash": manifest.config_hash,
            "data_hash": manifest.data_hash,
            "result_hash": manifest.result_hash
        }, indent=2))
    
    def compare_runs(self, manifest1: RunManifest, manifest2: RunManifest) -> Dict[str, bool]:
        """Compare two runs for determinism."""
        return {
            "same_seed": manifest1.seed == manifest2.seed,
            "same_config": manifest1.config_hash == manifest2.config_hash,
            "same_data": manifest1.data_hash == manifest2.data_hash,
            "same_result": manifest1.result_hash == manifest2.result_hash,
            "is_deterministic": manifest1.result_hash == manifest2.result_hash
        }
```

### Verification Script

**File:** `Scripts/verify_determinism.py` (ENHANCE)

```python
#!/usr/bin/env python3
"""Verify backtest determinism by running twice and comparing."""

import argparse
from pathlib import Path
from argus_py.lab.determinism import DeterminismManager

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    dm = DeterminismManager(seed=args.seed)
    manifests = []
    
    for i in range(args.runs):
        dm.initialize()  # Reset seeds
        
        # Run backtest
        run_id = f"determinism_check_{i}"
        run_dir = Path(f"runs/{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # ... run backtest ...
        
        manifest = dm.create_manifest(
            run_id=run_id,
            config={"seed": args.seed},
            data_path=Path("argus_py/data"),
            trades_csv=run_dir / "trades.csv"
        )
        dm.save_manifest(manifest, run_dir / "manifest.json")
        manifests.append(manifest)
    
    # Compare
    for i in range(1, len(manifests)):
        comparison = dm.compare_runs(manifests[0], manifests[i])
        result = "DETERMINISTIC" if comparison["is_deterministic"] else "NON-DETERMINISTIC"
        print(f"Run 0 vs Run {i}: {result}")
        if not comparison["is_deterministic"]:
            print(f"  Config match: {comparison['same_config']}")
            print(f"  Data match: {comparison['same_data']}")
            print(f"  Result match: {comparison['same_result']}")

if __name__ == "__main__":
    main()
```

### Acceptance Criteria
- [ ] DeterminismManager.initialize() sets all seeds
- [ ] Config hashing is stable (same config → same hash)
- [ ] Data hashing works for files and directories
- [ ] Manifest captures all relevant metadata
- [ ] Two runs with same seed produce identical trades.csv

### Verification
```bash
pytest tests/unit/test_determinism.py -v

python Scripts/verify_determinism.py --runs 2 --seed 42
# Expected: "Run 0 vs Run 1: DETERMINISTIC"
```

### Files to Create
1. `argus_py/lab/determinism.py` (NEW - 150 lines)
2. `Scripts/verify_determinism.py` (ENHANCE - 100 lines)
3. `tests/unit/test_determinism.py` (NEW - 80 lines)

---

## P21-003: CI & Packaging

**Assign to:** Sonnet  
**Priority:** P2  
**Estimated:** 4 hours

### Objective
Pre-commit hooks, Makefile, reproducible environment.

### Deliverables

**File:** `.pre-commit-config.yaml` (NEW)

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: check-merge-conflict
      - id: detect-private-key
  
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        language_version: python3.11
  
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]
  
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=100', '--ignore=E203,W503']
  
  - repo: local
    hooks:
      - id: no-print-statements
        name: No print() in production code
        entry: bash -c 'git diff --cached --name-only | xargs grep -l "print(" argus_py/ 2>/dev/null && exit 1 || exit 0'
        language: system
        pass_filenames: false
      
      - id: no-large-csv
        name: No CSV files > 1MB
        entry: bash -c 'find . -name "*.csv" -size +1M | head -1 | grep . && exit 1 || exit 0'
        language: system
        pass_filenames: false
```

**File:** `Makefile` (NEW)

```makefile
.PHONY: install test lint format clean run-daemon stop-daemon status

PYTHON := python3
VENV := venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

# Installation
install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	$(VENV)/bin/pre-commit install

# Testing
test:
	$(PYTEST) tests/unit/ -v --tb=short

test-integration:
	$(PYTEST) tests/integration/ -v --tb=short

test-all:
	$(PYTEST) tests/ -v --tb=short

test-coverage:
	$(PYTEST) tests/unit/ --cov=argus_py --cov-report=html

# Linting
lint:
	$(VENV)/bin/flake8 argus_py/ Scripts/
	$(VENV)/bin/mypy argus_py/ --ignore-missing-imports

format:
	$(VENV)/bin/black argus_py/ Scripts/ tests/
	$(VENV)/bin/isort argus_py/ Scripts/ tests/

# Pre-commit
pre-commit:
	$(VENV)/bin/pre-commit run --all-files

# Daemon control
run-daemon:
	./Scripts/phase19ctl.sh start

stop-daemon:
	./Scripts/phase19ctl.sh stop

status:
	./Scripts/phase19ctl.sh status

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .mypy_cache htmlcov

# Development
dev-sync:
	$(PIP) freeze > requirements-frozen.txt
```

**File:** `pyproject.toml` (NEW)

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "argus-terminal"
version = "0.21.0"
description = "Autonomous crypto trading system"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}

[tool.black]
line-length = 100
target-version = ['py310', 'py311']
include = '\.pyi?$'

[tool.isort]
profile = "black"
line_length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

**File:** `requirements-dev.txt` (NEW)

```
# Development dependencies
pytest>=7.4.0
pytest-cov>=4.1.0
black>=24.1.0
isort>=5.13.0
flake8>=7.0.0
mypy>=1.8.0
pre-commit>=3.6.0
```

### Acceptance Criteria
- [ ] `make install` creates venv and installs deps
- [ ] `make test` runs all unit tests
- [ ] `make lint` checks code quality
- [ ] `make format` formats all code
- [ ] `pre-commit run --all-files` passes
- [ ] Fresh clone → make install → make test works

### Verification
```bash
# Fresh setup
rm -rf venv
make install
make test
make lint
make pre-commit

# Expected: All pass
```

### Files to Create
1. `.pre-commit-config.yaml` (NEW)
2. `Makefile` (NEW)
3. `pyproject.toml` (NEW)
4. `requirements-dev.txt` (NEW)

---

## P21-004: Fee & Slippage Realism Model

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 3 hours

### Objective
Accurate fee and slippage modeling for realistic P&L estimates.

### Contract

**File:** `argus_py/broker/realism.py` (NEW)

```python
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class FeeModel:
    """Exchange fee configuration."""
    taker_bps: float = 4.0     # 0.04% Binance Futures
    maker_bps: float = 2.0     # 0.02%
    funding_bps: float = 1.0   # Avg 0.01% per 8h

@dataclass
class SlippageModel:
    """Market impact configuration."""
    base_bps: float = 2.0      # Base slippage
    size_impact_bps: float = 1.0  # Per sqrt($1000)
    volatility_mult: float = 1.5  # ATR multiplier

@dataclass
class RealismConfig:
    fees: FeeModel = None
    slippage: SlippageModel = None
    
    def __post_init__(self):
        self.fees = self.fees or FeeModel()
        self.slippage = self.slippage or SlippageModel()

class RealismEngine:
    """Realistic fee and slippage calculator."""
    
    def __init__(self, config: RealismConfig = None):
        self.config = config or RealismConfig()
    
    def calculate_commission(
        self,
        quantity: float,
        price: float,
        is_taker: bool = True
    ) -> float:
        """Calculate trading commission."""
        fee_bps = self.config.fees.taker_bps if is_taker else self.config.fees.maker_bps
        notional = quantity * price
        return notional * (fee_bps / 10000)
    
    def calculate_slippage(
        self,
        price: float,
        quantity: float,
        side: str,
        atr: Optional[float] = None,
        volume_24h: Optional[float] = None
    ) -> float:
        """
        Calculate market impact slippage.
        
        Returns:
            Slippage amount (positive = adverse, subtract from price for buys)
        """
        cfg = self.config.slippage
        notional = quantity * price
        
        # Base slippage
        base = price * (cfg.base_bps / 10000)
        
        # Size impact (sqrt scaling)
        size_impact = price * (cfg.size_impact_bps / 10000) * np.sqrt(notional / 1000)
        
        # Volatility adjustment
        vol_adj = 1.0
        if atr:
            atr_pct = atr / price * 100
            vol_adj = 1.0 + (atr_pct - 1.0) * (cfg.volatility_mult - 1.0)  # Scale around 1% ATR
        
        total = (base + size_impact) * max(0.5, vol_adj)
        
        # Adverse direction
        return total if side == "BUY" else -total
    
    def calculate_funding(
        self,
        position_value: float,
        hours_held: float,
        avg_funding_rate: Optional[float] = None
    ) -> float:
        """
        Calculate funding cost for futures position.
        
        Args:
            position_value: Notional value
            hours_held: How long position held
            avg_funding_rate: Override default rate
        
        Returns:
            Funding cost (positive = paid, negative = received)
        """
        rate_bps = avg_funding_rate or self.config.fees.funding_bps
        funding_periods = hours_held / 8.0
        return position_value * (rate_bps / 10000) * funding_periods
    
    def get_effective_price(
        self,
        price: float,
        quantity: float,
        side: str,
        atr: Optional[float] = None
    ) -> float:
        """Get effective fill price including slippage."""
        slip = self.calculate_slippage(price, quantity, side, atr)
        if side == "BUY":
            return price + slip  # Pay more
        else:
            return price - abs(slip)  # Receive less
    
    def estimate_round_trip_cost(
        self,
        price: float,
        quantity: float,
        hold_hours: float = 24.0,
        atr: Optional[float] = None
    ) -> dict:
        """Estimate total round-trip trading costs."""
        notional = quantity * price
        
        # Entry
        entry_commission = self.calculate_commission(quantity, price, is_taker=True)
        entry_slippage = abs(self.calculate_slippage(price, quantity, "BUY", atr))
        
        # Exit
        exit_commission = self.calculate_commission(quantity, price, is_taker=True)
        exit_slippage = abs(self.calculate_slippage(price, quantity, "SELL", atr))
        
        # Funding
        funding = self.calculate_funding(notional, hold_hours)
        
        total = entry_commission + exit_commission + entry_slippage + exit_slippage + funding
        
        return {
            "notional": notional,
            "entry_commission": entry_commission,
            "exit_commission": exit_commission,
            "entry_slippage": entry_slippage,
            "exit_slippage": exit_slippage,
            "funding": funding,
            "total_cost": total,
            "cost_bps": (total / notional) * 10000
        }
```

### Integration with Paper Broker

Modify `argus_py/broker/paper.py`:

```python
from argus_py.broker.realism import RealismEngine, RealismConfig

class PaperBroker:
    def __init__(self, ...):
        self.realism = RealismEngine(RealismConfig())
    
    def execute_order(self, symbol, side, quantity, price, atr=None):
        # Get realistic fill price
        fill_price = self.realism.get_effective_price(price, quantity, side, atr)
        
        # Calculate commission
        commission = self.realism.calculate_commission(quantity, fill_price)
        
        # Execute at realistic price
        ...
```

### Acceptance Criteria
- [ ] Commission calculation matches Binance (0.04% taker)
- [ ] Slippage scales with position size
- [ ] Funding calculated correctly for 8h periods
- [ ] Round-trip cost estimation accurate
- [ ] Paper broker uses realism engine

### Verification
```bash
pytest tests/unit/test_realism.py -v

python -c "
from argus_py.broker.realism import RealismEngine

engine = RealismEngine()

# Test $1000 BTC trade
costs = engine.estimate_round_trip_cost(
    price=50000,
    quantity=0.02,  # $1000 notional
    hold_hours=24,
    atr=500
)
print(f'Notional: \${costs[\"notional\"]:.2f}')
print(f'Entry Commission: \${costs[\"entry_commission\"]:.2f}')
print(f'Entry Slippage: \${costs[\"entry_slippage\"]:.2f}')
print(f'Funding (24h): \${costs[\"funding\"]:.2f}')
print(f'Total Cost: \${costs[\"total_cost\"]:.2f} ({costs[\"cost_bps\"]:.1f} bps)')
"
# Expected: ~$1.50 total ($0.40 comm x2 + ~$0.30 slip x2 + ~$0.30 funding)
```

### Files to Create
1. `argus_py/broker/realism.py` (NEW - 150 lines)
2. `argus_py/broker/paper.py` (MODIFY - integrate realism)
3. `tests/unit/test_realism.py` (NEW - 60 lines)

---

# PHASE 22: Advanced Features (Months 3-6)

---

## P22-001: Multi-Symbol Portfolio Manager

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 8 hours

### Objective
Extend from single BTC to multi-symbol trading with portfolio-level risk management.

### Contract

**File:** `argus_py/portfolio/manager.py` (NEW)

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

class CorrelationBucket(Enum):
    BTC_ECOSYSTEM = "BTC_ECOSYSTEM"    # BTC, WBTC
    ETH_ECOSYSTEM = "ETH_ECOSYSTEM"    # ETH, stETH
    ALTCOIN_MAJOR = "ALTCOIN_MAJOR"    # SOL, BNB, XRP
    ALTCOIN_MID = "ALTCOIN_MID"        # LINK, AVAX, DOT
    STABLECOIN = "STABLECOIN"          # Excluded from trading

@dataclass
class SymbolConfig:
    symbol: str
    enabled: bool = True
    max_position_pct: float = 20.0     # Max 20% of portfolio
    bucket: CorrelationBucket = CorrelationBucket.ALTCOIN_MID
    min_score_for_entry: float = 65.0
    priority: int = 1                   # 1=highest

@dataclass
class PortfolioLimits:
    max_total_exposure_pct: float = 100.0
    max_correlated_exposure_pct: float = 40.0  # Max in same bucket
    max_open_positions: int = 5
    max_daily_trades: int = 10
    min_cash_reserve_pct: float = 10.0

@dataclass
class PortfolioState:
    positions: Dict[str, float]         # symbol -> value
    cash: float
    total_equity: float
    exposure_by_bucket: Dict[str, float]
    daily_trades: int
    daily_pnl: float

@dataclass
class AllocationDecision:
    symbol: str
    action: str                          # BUY|SELL|HOLD|SKIP
    target_allocation_pct: float
    current_allocation_pct: float
    reason: str
    blocked_by: Optional[str] = None

class PortfolioManager:
    """
    Multi-symbol portfolio manager with correlation awareness.
    
    Responsibilities:
    - Track positions across multiple symbols
    - Enforce portfolio-level limits
    - Rebalance based on signals
    - Prevent over-concentration in correlated assets
    """
    
    def __init__(
        self,
        symbols: List[SymbolConfig],
        limits: PortfolioLimits = None
    ):
        self.symbols = {s.symbol: s for s in symbols}
        self.limits = limits or PortfolioLimits()
        self.state = PortfolioState(
            positions={}, cash=0, total_equity=0,
            exposure_by_bucket={}, daily_trades=0, daily_pnl=0
        )
    
    def update_state(self, positions: Dict[str, float], cash: float) -> None:
        """Update portfolio state from broker."""
        self.state.positions = positions
        self.state.cash = cash
        self.state.total_equity = sum(positions.values()) + cash
        
        # Calculate bucket exposures
        self.state.exposure_by_bucket = {}
        for symbol, value in positions.items():
            if symbol in self.symbols:
                bucket = self.symbols[symbol].bucket.value
                self.state.exposure_by_bucket[bucket] = \
                    self.state.exposure_by_bucket.get(bucket, 0) + value
    
    def can_open_position(self, symbol: str, value: float) -> tuple:
        """
        Check if new position is allowed.
        
        Returns:
            (allowed: bool, reason: str)
        """
        if symbol not in self.symbols:
            return False, "Symbol not configured"
        
        config = self.symbols[symbol]
        
        # Check if already in position
        if symbol in self.state.positions:
            return False, "Already in position"
        
        # Check max positions
        if len(self.state.positions) >= self.limits.max_open_positions:
            return False, f"Max positions ({self.limits.max_open_positions}) reached"
        
        # Check daily trades
        if self.state.daily_trades >= self.limits.max_daily_trades:
            return False, "Max daily trades reached"
        
        # Check cash reserve
        min_cash = self.state.total_equity * (self.limits.min_cash_reserve_pct / 100)
        if self.state.cash - value < min_cash:
            return False, "Would violate cash reserve"
        
        # Check single position limit
        max_position = self.state.total_equity * (config.max_position_pct / 100)
        if value > max_position:
            return False, f"Exceeds max position size ({config.max_position_pct}%)"
        
        # Check total exposure
        new_exposure = sum(self.state.positions.values()) + value
        max_exposure = self.state.total_equity * (self.limits.max_total_exposure_pct / 100)
        if new_exposure > max_exposure:
            return False, "Would exceed total exposure limit"
        
        # Check correlated exposure
        bucket = config.bucket.value
        current_bucket = self.state.exposure_by_bucket.get(bucket, 0)
        max_bucket = self.state.total_equity * (self.limits.max_correlated_exposure_pct / 100)
        if current_bucket + value > max_bucket:
            return False, f"Would exceed {bucket} correlation limit"
        
        return True, "OK"
    
    def rank_opportunities(
        self,
        signals: Dict[str, float]  # symbol -> score
    ) -> List[AllocationDecision]:
        """
        Rank trading opportunities by priority and score.
        
        Returns:
            Sorted list of allocation decisions
        """
        decisions = []
        
        for symbol, score in signals.items():
            if symbol not in self.symbols:
                continue
            
            config = self.symbols[symbol]
            if not config.enabled:
                continue
            
            if score < config.min_score_for_entry:
                decisions.append(AllocationDecision(
                    symbol=symbol, action="SKIP",
                    target_allocation_pct=0, current_allocation_pct=0,
                    reason=f"Score {score:.0f} < {config.min_score_for_entry}"
                ))
                continue
            
            # Calculate target allocation
            target_pct = min(config.max_position_pct, score / 5)  # Scale by score
            current_pct = (self.state.positions.get(symbol, 0) / 
                          self.state.total_equity * 100) if self.state.total_equity > 0 else 0
            
            allowed, reason = self.can_open_position(symbol, 
                self.state.total_equity * target_pct / 100)
            
            decisions.append(AllocationDecision(
                symbol=symbol,
                action="BUY" if allowed else "HOLD",
                target_allocation_pct=target_pct,
                current_allocation_pct=current_pct,
                reason=f"Score: {score:.0f}",
                blocked_by=None if allowed else reason
            ))
        
        # Sort by priority, then score
        decisions.sort(key=lambda d: (
            self.symbols.get(d.symbol, SymbolConfig(d.symbol)).priority,
            -signals.get(d.symbol, 0)
        ))
        
        return decisions
```

### Default Symbol List

```python
DEFAULT_CRYPTO_SYMBOLS = [
    SymbolConfig("BTCUSDT", bucket=CorrelationBucket.BTC_ECOSYSTEM, priority=1, max_position_pct=30),
    SymbolConfig("ETHUSDT", bucket=CorrelationBucket.ETH_ECOSYSTEM, priority=1, max_position_pct=25),
    SymbolConfig("SOLUSDT", bucket=CorrelationBucket.ALTCOIN_MAJOR, priority=2, max_position_pct=15),
    SymbolConfig("BNBUSDT", bucket=CorrelationBucket.ALTCOIN_MAJOR, priority=2, max_position_pct=15),
    SymbolConfig("XRPUSDT", bucket=CorrelationBucket.ALTCOIN_MAJOR, priority=3, max_position_pct=10),
    SymbolConfig("LINKUSDT", bucket=CorrelationBucket.ALTCOIN_MID, priority=3, max_position_pct=10),
    SymbolConfig("AVAXUSDT", bucket=CorrelationBucket.ALTCOIN_MID, priority=3, max_position_pct=10),
]
```

### Acceptance Criteria
- [ ] Multi-symbol state tracking works
- [ ] Correlation bucket limits enforced
- [ ] Position limits checked correctly
- [ ] Opportunity ranking by priority
- [ ] Cash reserve maintained

### Verification
```bash
pytest tests/unit/test_portfolio_manager.py -v

python -c "
from argus_py.portfolio.manager import PortfolioManager, SymbolConfig, CorrelationBucket

pm = PortfolioManager([
    SymbolConfig('BTCUSDT', bucket=CorrelationBucket.BTC_ECOSYSTEM, max_position_pct=30),
    SymbolConfig('ETHUSDT', bucket=CorrelationBucket.ETH_ECOSYSTEM, max_position_pct=25),
])

pm.update_state(positions={'BTCUSDT': 3000}, cash=7000)
print(f'Total Equity: \${pm.state.total_equity}')
print(f'BTC Exposure: {pm.state.exposure_by_bucket}')

allowed, reason = pm.can_open_position('ETHUSDT', 2500)
print(f'Can open ETH? {allowed} - {reason}')
"
```

### Files to Create
1. `argus_py/portfolio/__init__.py` (NEW)
2. `argus_py/portfolio/manager.py` (NEW - 300 lines)
3. `argus_py/portfolio/symbols.py` (NEW - default configs)
4. `tests/unit/test_portfolio_manager.py` (NEW - 150 lines)

---

## P22-002: Live Trading Bridge

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 10 hours

### Objective
Bridge paper broker to live Binance Futures with safety guardrails.

### Contract

**File:** `argus_py/broker/live.py` (NEW)

```python
from dataclasses import dataclass
from typing import Optional, Dict
from enum import Enum
import hmac
import hashlib
import time
import httpx

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class LiveConfig:
    api_key: str
    api_secret: str
    testnet: bool = True              # Start with testnet!
    base_url: str = None
    max_order_value: float = 100.0    # Safety cap per order
    max_daily_volume: float = 1000.0  # Safety cap per day
    require_confirmation: bool = True  # Confirm before execute
    
    def __post_init__(self):
        if self.base_url is None:
            self.base_url = (
                "https://testnet.binancefuture.com" if self.testnet
                else "https://fapi.binance.com"
            )

@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None
    reduce_only: bool = False

@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str]
    fill_price: Optional[float]
    fill_quantity: Optional[float]
    commission: Optional[float]
    error: Optional[str]

class LiveBroker:
    """
    Live Binance Futures broker with safety guardrails.
    
    SAFETY FEATURES:
    - Testnet by default
    - Max order value cap
    - Max daily volume cap
    - Optional confirmation prompt
    - All orders logged
    """
    
    def __init__(self, config: LiveConfig):
        self.config = config
        self.daily_volume = 0.0
        self.orders_today = []
        self._client = httpx.Client(timeout=10.0)
    
    def _sign(self, params: Dict) -> str:
        """Create HMAC SHA256 signature."""
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return hmac.new(
            self.config.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _request(self, method: str, endpoint: str, params: Dict) -> Dict:
        """Make signed API request."""
        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._sign(params)
        
        headers = {"X-MBX-APIKEY": self.config.api_key}
        url = f"{self.config.base_url}{endpoint}"
        
        if method == "GET":
            response = self._client.get(url, params=params, headers=headers)
        else:
            response = self._client.post(url, params=params, headers=headers)
        
        response.raise_for_status()
        return response.json()
    
    def get_account(self) -> Dict:
        """Get account information."""
        return self._request("GET", "/fapi/v2/account", {})
    
    def get_positions(self) -> Dict[str, float]:
        """Get current positions."""
        account = self.get_account()
        positions = {}
        for pos in account.get("positions", []):
            amt = float(pos["positionAmt"])
            if amt != 0:
                positions[pos["symbol"]] = amt
        return positions
    
    def get_balance(self) -> float:
        """Get available USDT balance."""
        account = self.get_account()
        for asset in account.get("assets", []):
            if asset["asset"] == "USDT":
                return float(asset["availableBalance"])
        return 0.0
    
    def _check_safety(self, order: OrderRequest, notional: float) -> tuple:
        """Check safety limits before execution."""
        # Check order size
        if notional > self.config.max_order_value:
            return False, f"Order value ${notional:.2f} exceeds max ${self.config.max_order_value}"
        
        # Check daily volume
        if self.daily_volume + notional > self.config.max_daily_volume:
            return False, f"Would exceed daily volume limit ${self.config.max_daily_volume}"
        
        return True, "OK"
    
    def execute(self, order: OrderRequest, current_price: float) -> OrderResult:
        """
        Execute order with safety checks.
        
        Args:
            order: Order to execute
            current_price: Current market price for notional calculation
        
        Returns:
            OrderResult with fill details or error
        """
        notional = order.quantity * current_price
        
        # Safety checks
        safe, reason = self._check_safety(order, notional)
        if not safe:
            return OrderResult(
                success=False, order_id=None, fill_price=None,
                fill_quantity=None, commission=None, error=reason
            )
        
        # Confirmation prompt (if enabled)
        if self.config.require_confirmation:
            print(f"\n⚠️  LIVE ORDER CONFIRMATION")
            print(f"   {order.side.value} {order.quantity} {order.symbol}")
            print(f"   Notional: ${notional:.2f}")
            confirm = input("   Type 'YES' to confirm: ")
            if confirm != "YES":
                return OrderResult(
                    success=False, order_id=None, fill_price=None,
                    fill_quantity=None, commission=None, error="User cancelled"
                )
        
        try:
            params = {
                "symbol": order.symbol,
                "side": order.side.value,
                "type": order.order_type.value,
                "quantity": order.quantity,
            }
            if order.reduce_only:
                params["reduceOnly"] = "true"
            if order.order_type == OrderType.LIMIT and order.price:
                params["price"] = order.price
                params["timeInForce"] = "GTC"
            
            result = self._request("POST", "/fapi/v1/order", params)
            
            # Update daily tracking
            self.daily_volume += notional
            self.orders_today.append({
                "time": time.time(),
                "order": order,
                "result": result
            })
            
            return OrderResult(
                success=True,
                order_id=str(result.get("orderId")),
                fill_price=float(result.get("avgPrice", current_price)),
                fill_quantity=float(result.get("executedQty", order.quantity)),
                commission=float(result.get("commission", 0)),
                error=None
            )
            
        except Exception as e:
            return OrderResult(
                success=False, order_id=None, fill_price=None,
                fill_quantity=None, commission=None, error=str(e)
            )
    
    def close_position(self, symbol: str, current_price: float) -> OrderResult:
        """Close entire position for symbol."""
        positions = self.get_positions()
        if symbol not in positions:
            return OrderResult(
                success=False, order_id=None, fill_price=None,
                fill_quantity=None, commission=None, error="No position"
            )
        
        quantity = abs(positions[symbol])
        side = OrderSide.SELL if positions[symbol] > 0 else OrderSide.BUY
        
        return self.execute(
            OrderRequest(symbol=symbol, side=side, quantity=quantity, reduce_only=True),
            current_price
        )
```

### Safety Guardrails

```python
# PRODUCTION CHECKLIST (must pass before live trading)
LIVE_TRADING_CHECKLIST = [
    "testnet=True verified working",
    "max_order_value set to acceptable loss",
    "max_daily_volume set to daily risk budget",
    "require_confirmation=True for initial testing",
    "Kill-switch integration verified",
    "API keys have trade permission only (no withdraw)",
    "IP whitelist configured on Binance",
    "Testnet paper run for 7+ days without issues",
]
```

### Acceptance Criteria
- [ ] Testnet orders execute correctly
- [ ] Safety limits block oversized orders
- [ ] Confirmation prompt works
- [ ] Daily volume tracking accurate
- [ ] Position close works
- [ ] Error handling robust

### Verification
```bash
pytest tests/unit/test_live_broker.py -v

# Testnet integration (requires API keys)
python -c "
from argus_py.broker.live import LiveBroker, LiveConfig

config = LiveConfig(
    api_key='YOUR_TESTNET_KEY',
    api_secret='YOUR_TESTNET_SECRET',
    testnet=True,
    max_order_value=50.0,
    require_confirmation=False
)

broker = LiveBroker(config)
balance = broker.get_balance()
print(f'Testnet Balance: \${balance:.2f}')
positions = broker.get_positions()
print(f'Positions: {positions}')
"
```

### Files to Create
1. `argus_py/broker/live.py` (NEW - 300 lines)
2. `argus_py/broker/safety.py` (NEW - guardrails)
3. `tests/unit/test_live_broker.py` (NEW - 100 lines, mocked)
4. `Docs/LIVE_TRADING_CHECKLIST.md` (NEW)

---

## P22-003: Real-Time Dashboard

**Assign to:** Sonnet  
**Priority:** P2  
**Estimated:** 6 hours

### Objective
Web-based real-time dashboard for monitoring paper/live trading.

### Contract

**File:** `argus_py/dashboard/app.py` (NEW)

```python
from flask import Flask, jsonify, render_template
from pathlib import Path
import json
import csv
from datetime import datetime

app = Flask(__name__)

class DashboardData:
    """Data provider for dashboard."""
    
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
    
    def get_heartbeat(self) -> dict:
        """Get latest heartbeat data."""
        path = self.run_dir / "heartbeat.json"
        if path.exists():
            return json.loads(path.read_text())
        return {"error": "No heartbeat"}
    
    def get_state(self) -> dict:
        """Get daemon state."""
        path = self.run_dir / "daemon_state.json"
        if path.exists():
            return json.loads(path.read_text())
        return {"error": "No state"}
    
    def get_recent_trades(self, limit: int = 20) -> list:
        """Get recent trades from CSV."""
        path = self.run_dir / "trades.csv"
        if not path.exists():
            return []
        
        trades = []
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(row)
        
        return trades[-limit:]
    
    def get_recent_decisions(self, limit: int = 50) -> list:
        """Get recent decisions."""
        path = self.run_dir / "decisions.csv"
        if not path.exists():
            return []
        
        decisions = []
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                decisions.append(row)
        
        return decisions[-limit:]
    
    def get_equity_curve(self) -> list:
        """Calculate equity curve from trades."""
        trades = self.get_recent_trades(1000)
        curve = []
        equity = 1000  # Starting equity
        
        for trade in trades:
            if trade.get("event") == "CLOSE":
                pnl = float(trade.get("pnl", 0))
                equity += pnl
                curve.append({
                    "timestamp": trade["timestamp"],
                    "equity": equity
                })
        
        return curve
    
    def get_rejection_summary(self) -> dict:
        """Summarize rejections by code."""
        path = self.run_dir / "rejects.csv"
        if not path.exists():
            return {}
        
        summary = {}
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get("code", "UNKNOWN")
                summary[code] = summary.get(code, 0) + 1
        
        return summary

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    data = DashboardData(Path(app.config["RUN_DIR"]))
    return jsonify({
        "heartbeat": data.get_heartbeat(),
        "state": data.get_state()
    })

@app.route("/api/trades")
def api_trades():
    data = DashboardData(Path(app.config["RUN_DIR"]))
    return jsonify(data.get_recent_trades(50))

@app.route("/api/equity")
def api_equity():
    data = DashboardData(Path(app.config["RUN_DIR"]))
    return jsonify(data.get_equity_curve())

@app.route("/api/rejections")
def api_rejections():
    data = DashboardData(Path(app.config["RUN_DIR"]))
    return jsonify(data.get_rejection_summary())

def create_app(run_dir: str):
    app.config["RUN_DIR"] = run_dir
    return app
```

### Frontend Template

**File:** `argus_py/dashboard/templates/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Argus Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; margin: 0; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .card { background: #16213e; border-radius: 12px; padding: 20px; }
        .card h3 { margin-top: 0; color: #00d9ff; }
        .status-ok { color: #00ff88; }
        .status-warn { color: #ffaa00; }
        .status-error { color: #ff4444; }
        .metric { font-size: 2em; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #333; }
        #equity-chart { max-height: 300px; }
    </style>
</head>
<body>
    <h1>🛡️ Argus Trading Dashboard</h1>
    
    <div class="grid">
        <div class="card">
            <h3>System Status</h3>
            <div id="status">Loading...</div>
        </div>
        
        <div class="card">
            <h3>Portfolio</h3>
            <div id="portfolio">Loading...</div>
        </div>
        
        <div class="card">
            <h3>Risk Level</h3>
            <div id="risk" class="metric">--</div>
        </div>
    </div>
    
    <div class="card" style="margin-top: 20px;">
        <h3>Equity Curve</h3>
        <canvas id="equity-chart"></canvas>
    </div>
    
    <div class="grid" style="margin-top: 20px;">
        <div class="card">
            <h3>Recent Trades</h3>
            <table id="trades-table">
                <tr><th>Time</th><th>Symbol</th><th>Side</th><th>P&L</th></tr>
            </table>
        </div>
        
        <div class="card">
            <h3>Rejection Summary</h3>
            <div id="rejections"></div>
        </div>
    </div>
    
    <script>
        async function fetchData() {
            const status = await fetch('/api/status').then(r => r.json());
            const trades = await fetch('/api/trades').then(r => r.json());
            const equity = await fetch('/api/equity').then(r => r.json());
            const rejections = await fetch('/api/rejections').then(r => r.json());
            
            updateStatus(status);
            updateTrades(trades);
            updateEquityChart(equity);
            updateRejections(rejections);
        }
        
        function updateStatus(data) {
            const hb = data.heartbeat;
            const state = data.state;
            
            document.getElementById('status').innerHTML = `
                <p>Last Update: ${new Date(hb.timestamp * 1000).toLocaleString()}</p>
                <p>Bars Processed: ${hb.bars_processed}</p>
                <p class="${hb.errors_1h === 0 ? 'status-ok' : 'status-warn'}">
                    Errors (1h): ${hb.errors_1h}
                </p>
            `;
            
            document.getElementById('portfolio').innerHTML = `
                <p class="metric">$${state.equity?.toFixed(2) || '--'}</p>
                <p>Balance: $${state.balance?.toFixed(2) || '--'}</p>
                <p>Drawdown: ${state.current_dd_pct?.toFixed(2) || '--'}%</p>
            `;
            
            const riskLevel = state.kill_switch_level || 'NORMAL';
            const riskClass = riskLevel === 'NORMAL' ? 'status-ok' : 
                             riskLevel === 'SOFT' ? 'status-warn' : 'status-error';
            document.getElementById('risk').innerHTML = `<span class="${riskClass}">${riskLevel}</span>`;
        }
        
        // ... more update functions ...
        
        setInterval(fetchData, 5000);
        fetchData();
    </script>
</body>
</html>
```

### CLI Runner

**File:** `Scripts/dashboard.py`

```python
#!/usr/bin/env python3
import argparse
from argus_py.dashboard.app import create_app

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", help="Path to run directory")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    
    app = create_app(args.run_dir)
    print(f"🛡️ Argus Dashboard running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)

if __name__ == "__main__":
    main()
```

### Acceptance Criteria
- [ ] Dashboard loads without errors
- [ ] Status updates every 5 seconds
- [ ] Equity chart renders correctly
- [ ] Trade history displays
- [ ] Rejection summary accurate

### Verification
```bash
# Start dashboard
python Scripts/dashboard.py runs/phase19_twin/SOFT/ --port 8080

# Open browser to http://localhost:8080
# Verify all panels load and update
```

### Files to Create
1. `argus_py/dashboard/__init__.py` (NEW)
2. `argus_py/dashboard/app.py` (NEW - 200 lines)
3. `argus_py/dashboard/templates/index.html` (NEW)
4. `Scripts/dashboard.py` (NEW - CLI runner)

### Dependencies
```bash
pip install flask
```

---

## P22-004: Chiron ML Learning Module

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 8 hours

### Objective
Implement ML-based weight optimization from historical trade outcomes.

### Contract

**File:** `argus_py/models/chiron/learner.py` (NEW)

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path
import numpy as np
from datetime import datetime

@dataclass
class TradeOutcome:
    timestamp: int
    symbol: str
    regime: str
    engine_scores: Dict[str, float]  # orion, aether, hermes, phoenix
    verdict: str
    pnl: float
    hold_duration: float

@dataclass
class LearningRecord:
    regime: str
    weights: Dict[str, float]
    sample_count: int
    avg_pnl: float
    win_rate: float
    sharpe: float
    last_updated: str

class ChironLearner:
    """
    ML-based weight optimizer for Council voting.
    
    Uses historical trade outcomes to optimize engine weights per regime.
    """
    
    def __init__(self, state_path: Optional[Path] = None):
        self.state_path = state_path
        self.records: Dict[str, LearningRecord] = {}
        self.outcomes: List[TradeOutcome] = []
        
        if state_path and state_path.exists():
            self.load_state()
    
    def add_outcome(self, outcome: TradeOutcome) -> None:
        """Record a trade outcome for learning."""
        self.outcomes.append(outcome)
    
    def optimize_weights(
        self,
        regime: str,
        min_samples: int = 30
    ) -> Optional[Dict[str, float]]:
        """
        Optimize weights for a specific regime using gradient-free optimization.
        
        Uses historical outcomes to find weight combination that maximizes Sharpe.
        """
        # Filter outcomes for this regime
        regime_outcomes = [o for o in self.outcomes if o.regime == regime]
        
        if len(regime_outcomes) < min_samples:
            return None  # Not enough data
        
        # Extract features and targets
        engines = ["orion", "aether", "hermes", "phoenix", "aegean"]
        X = np.array([[o.engine_scores.get(e, 50) for e in engines] 
                      for o in regime_outcomes])
        y = np.array([o.pnl for o in regime_outcomes])
        
        # Simple optimization: weight by correlation with positive outcomes
        best_weights = self._optimize_correlation(X, y, engines)
        
        # Calculate performance metrics
        win_rate = np.mean(y > 0)
        avg_pnl = np.mean(y)
        sharpe = np.mean(y) / np.std(y) if np.std(y) > 0 else 0
        
        # Store record
        self.records[regime] = LearningRecord(
            regime=regime,
            weights=best_weights,
            sample_count=len(regime_outcomes),
            avg_pnl=avg_pnl,
            win_rate=win_rate,
            sharpe=sharpe,
            last_updated=datetime.now().isoformat()
        )
        
        return best_weights
    
    def _optimize_correlation(
        self,
        X: np.ndarray,
        y: np.ndarray,
        engines: List[str]
    ) -> Dict[str, float]:
        """
        Simple correlation-based weight optimization.
        
        Weights engines by their correlation with positive outcomes.
        """
        weights = {}
        
        for i, engine in enumerate(engines):
            scores = X[:, i]
            
            # Correlation between engine score and P&L
            if np.std(scores) > 0 and np.std(y) > 0:
                corr = np.corrcoef(scores, y)[0, 1]
            else:
                corr = 0
            
            # Convert correlation to weight (0.1 to 0.4 range)
            weights[engine] = max(0.1, min(0.4, 0.25 + corr * 0.15))
        
        # Normalize to sum to 1
        total = sum(weights.values())
        return {k: v/total for k, v in weights.items()}
    
    def get_optimal_weights(self, regime: str) -> Optional[Dict[str, float]]:
        """Get previously optimized weights for regime."""
        if regime in self.records:
            return self.records[regime].weights
        return None
    
    def load_outcomes_from_csv(self, trades_csv: Path, decisions_csv: Path) -> int:
        """Load historical outcomes from telemetry CSVs."""
        import csv
        
        # Load decisions for engine scores
        decisions = {}
        with open(decisions_csv) as f:
            for row in csv.DictReader(f):
                key = (row["bar_ts"], row["symbol"])
                decisions[key] = row
        
        # Load trades and match with decisions
        count = 0
        with open(trades_csv) as f:
            for row in csv.DictReader(f):
                if row["event"] != "CLOSE":
                    continue
                
                # Find matching decision (simplified)
                # ... matching logic ...
                
                self.outcomes.append(TradeOutcome(
                    timestamp=int(row["timestamp"]),
                    symbol=row["symbol"],
                    regime="TREND",  # From decision
                    engine_scores={},  # From decision
                    verdict="GO",
                    pnl=float(row["pnl"]),
                    hold_duration=0
                ))
                count += 1
        
        return count
    
    def save_state(self) -> None:
        """Save learning state to disk."""
        if not self.state_path:
            return
        
        state = {
            "records": {k: {
                "regime": v.regime,
                "weights": v.weights,
                "sample_count": v.sample_count,
                "avg_pnl": v.avg_pnl,
                "win_rate": v.win_rate,
                "sharpe": v.sharpe,
                "last_updated": v.last_updated
            } for k, v in self.records.items()},
            "outcomes_count": len(self.outcomes)
        }
        
        self.state_path.write_text(json.dumps(state, indent=2))
    
    def load_state(self) -> None:
        """Load learning state from disk."""
        if not self.state_path or not self.state_path.exists():
            return
        
        state = json.loads(self.state_path.read_text())
        
        for k, v in state.get("records", {}).items():
            self.records[k] = LearningRecord(**v)
```

### Weekly Learning Script

**File:** `Scripts/chiron_learn.py`

```python
#!/usr/bin/env python3
"""
Weekly Chiron learning job.
Analyzes past week's trades and updates weight recommendations.
"""

import argparse
from pathlib import Path
from argus_py.models.chiron.learner import ChironLearner

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", help="Run directory with CSVs")
    parser.add_argument("--output", default="chiron_weights.json")
    args = parser.parse_args()
    
    run_dir = Path(args.run_dir)
    learner = ChironLearner(state_path=Path(args.output))
    
    # Load historical data
    count = learner.load_outcomes_from_csv(
        run_dir / "trades.csv",
        run_dir / "decisions.csv"
    )
    print(f"Loaded {count} trade outcomes")
    
    # Optimize for each regime
    for regime in ["TREND", "CHOP", "RISK_OFF", "NEUTRAL"]:
        weights = learner.optimize_weights(regime)
        if weights:
            record = learner.records[regime]
            print(f"\n{regime}:")
            print(f"  Samples: {record.sample_count}")
            print(f"  Win Rate: {record.win_rate:.1%}")
            print(f"  Sharpe: {record.sharpe:.2f}")
            print(f"  Weights: {weights}")
    
    learner.save_state()
    print(f"\nSaved to {args.output}")

if __name__ == "__main__":
    main()
```

### Acceptance Criteria
- [ ] Outcome recording works
- [ ] Weight optimization produces valid weights
- [ ] Correlation-based optimization reasonable
- [ ] State persistence works
- [ ] CSV loading works

### Verification
```bash
pytest tests/unit/test_chiron_learner.py -v

python Scripts/chiron_learn.py runs/phase19_twin/SOFT/ --output chiron_test.json
# Expected: Weight recommendations per regime
```

### Files to Create
1. `argus_py/models/chiron/learner.py` (NEW - 250 lines)
2. `Scripts/chiron_learn.py` (NEW - 80 lines)
3. `tests/unit/test_chiron_learner.py` (NEW - 100 lines)

---

# PHASE 23: Production Readiness (Months 6-9)

---

## P23-001: Alert & Notification System

**Assign to:** Sonnet  
**Priority:** P1  
**Estimated:** 5 hours

### Objective
Multi-channel alerting: Telegram, Discord, Email for trading events and system health.

### Contract

**File:** `argus_py/alerts/dispatcher.py` (NEW)

```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import httpx

class AlertLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class AlertChannel(Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"

@dataclass
class AlertConfig:
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook: Optional[str] = None
    email_smtp: Optional[str] = None
    email_to: Optional[str] = None

@dataclass
class Alert:
    level: AlertLevel
    title: str
    message: str
    channels: List[AlertChannel]
    timestamp: float

class AlertDispatcher:
    def __init__(self, config: AlertConfig):
        self.config = config
    
    async def send(self, alert: Alert) -> dict:
        results = {}
        for channel in alert.channels:
            if channel == AlertChannel.TELEGRAM:
                results["telegram"] = await self._send_telegram(alert)
            elif channel == AlertChannel.DISCORD:
                results["discord"] = await self._send_discord(alert)
        return results
    
    async def _send_telegram(self, alert: Alert) -> bool:
        if not self.config.telegram_bot_token:
            return False
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}[alert.level.value]
        text = f"{emoji} *{alert.title}*\n{alert.message}"
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={
                "chat_id": self.config.telegram_chat_id,
                "text": text, "parse_mode": "Markdown"
            })
            return r.status_code == 200
    
    async def _send_discord(self, alert: Alert) -> bool:
        if not self.config.discord_webhook:
            return False
        colors = {"INFO": 3447003, "WARNING": 16776960, "CRITICAL": 15158332}
        async with httpx.AsyncClient() as client:
            r = await client.post(self.config.discord_webhook, json={
                "embeds": [{"title": alert.title, "description": alert.message, 
                           "color": colors[alert.level.value]}]
            })
            return r.status_code == 204
```

### Alert Types
- Trade executed (BUY/SELL)
- Position closed (P&L)
- Kill-switch activated
- Heartbeat stale (>5min)
- Daily summary

### Files to Create
1. `argus_py/alerts/__init__.py`
2. `argus_py/alerts/dispatcher.py` (150 lines)
3. `argus_py/alerts/templates.py` (message formatting)
4. `tests/unit/test_alerts.py`

---

## P23-002: Disaster Recovery & Backup

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 4 hours

### Objective
Automated state backup and recovery from crashes.

### Contract

**File:** `argus_py/recovery/backup.py` (NEW)

```python
from dataclasses import dataclass
from pathlib import Path
import shutil
import json
from datetime import datetime

@dataclass
class BackupConfig:
    backup_dir: Path
    max_backups: int = 24  # Keep 24 hourly backups
    interval_minutes: int = 60

class BackupManager:
    def __init__(self, run_dir: Path, config: BackupConfig):
        self.run_dir = run_dir
        self.config = config
    
    def create_backup(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.config.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(parents=True)
        
        # Copy critical files
        for f in ["daemon_state.json", "trades.csv", "decisions.csv", "rejects.csv"]:
            src = self.run_dir / f
            if src.exists():
                shutil.copy2(src, backup_path / f)
        
        self._cleanup_old_backups()
        return backup_path
    
    def restore_latest(self) -> bool:
        backups = sorted(self.config.backup_dir.glob("backup_*"))
        if not backups:
            return False
        latest = backups[-1]
        for f in latest.iterdir():
            shutil.copy2(f, self.run_dir / f.name)
        return True
    
    def _cleanup_old_backups(self):
        backups = sorted(self.config.backup_dir.glob("backup_*"))
        while len(backups) > self.config.max_backups:
            shutil.rmtree(backups.pop(0))
```

### Files to Create
1. `argus_py/recovery/__init__.py`
2. `argus_py/recovery/backup.py` (100 lines)
3. `argus_py/recovery/restore.py` (state validation)
4. `tests/unit/test_backup.py`

---

## P23-003: Performance Profiling

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 3 hours

### Objective
Identify bottlenecks in bar processing loop.

### Contract

**File:** `argus_py/profiling/profiler.py` (NEW)

```python
import time
from dataclasses import dataclass, field
from typing import Dict, List
from contextlib import contextmanager

@dataclass
class ProfileResult:
    name: str
    calls: int = 0
    total_ms: float = 0.0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    
    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.calls if self.calls > 0 else 0

class Profiler:
    def __init__(self):
        self.results: Dict[str, ProfileResult] = {}
    
    @contextmanager
    def measure(self, name: str):
        start = time.perf_counter()
        yield
        elapsed = (time.perf_counter() - start) * 1000
        
        if name not in self.results:
            self.results[name] = ProfileResult(name)
        r = self.results[name]
        r.calls += 1
        r.total_ms += elapsed
        r.min_ms = min(r.min_ms, elapsed)
        r.max_ms = max(r.max_ms, elapsed)
    
    def report(self) -> str:
        lines = ["=== Performance Profile ==="]
        for name, r in sorted(self.results.items(), key=lambda x: -x[1].total_ms):
            lines.append(f"{name}: {r.calls} calls, avg={r.avg_ms:.2f}ms, total={r.total_ms:.0f}ms")
        return "\n".join(lines)
```

### Usage in Daemon
```python
profiler = Profiler()
with profiler.measure("data_fetch"):
    bars = fetch_bars()
with profiler.measure("strategy_eval"):
    signal = evaluate_strategy(bars)
# Print every 1000 bars
if bar_count % 1000 == 0:
    print(profiler.report())
```

### Files to Create
1. `argus_py/profiling/profiler.py` (80 lines)
2. `tests/unit/test_profiler.py`

---

## P23-004: Security Hardening

**Assign to:** Sonnet  
**Priority:** P1  
**Estimated:** 4 hours

### Objective
Secure API key storage, audit logging, rate limiting.

### Contract

**File:** `argus_py/security/vault.py` (NEW)

```python
import os
import base64
from cryptography.fernet import Fernet
from pathlib import Path

class SecureVault:
    def __init__(self, key_file: Path = None):
        self.key_file = key_file or Path.home() / ".argus" / "vault.key"
        self._fernet = None
    
    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            if self.key_file.exists():
                key = self.key_file.read_bytes()
            else:
                key = Fernet.generate_key()
                self.key_file.parent.mkdir(parents=True, exist_ok=True)
                self.key_file.write_bytes(key)
                os.chmod(self.key_file, 0o600)
            self._fernet = Fernet(key)
        return self._fernet
    
    def encrypt(self, plaintext: str) -> str:
        return self._get_fernet().encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        return self._get_fernet().decrypt(ciphertext.encode()).decode()
    
    def store_api_key(self, name: str, key: str):
        secrets_file = self.key_file.parent / "secrets.enc"
        secrets = self._load_secrets()
        secrets[name] = self.encrypt(key)
        secrets_file.write_text(json.dumps(secrets))
    
    def get_api_key(self, name: str) -> str:
        secrets = self._load_secrets()
        return self.decrypt(secrets[name]) if name in secrets else None
```

### Files to Create
1. `argus_py/security/__init__.py`
2. `argus_py/security/vault.py` (100 lines)
3. `argus_py/security/audit.py` (action logging)
4. `tests/unit/test_vault.py`

---

# PHASE 24: Scale & Expansion (Months 9-12)

---

## P24-001: Multi-Exchange Support

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 12 hours

### Objective
Support Binance, Bybit, OKX with unified interface.

### Contract

**File:** `argus_py/exchanges/base.py` (NEW)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Ticker:
    symbol: str
    bid: float
    ask: float
    last: float
    volume_24h: float

@dataclass
class OrderFill:
    order_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    commission: float

class ExchangeAdapter(ABC):
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker: ...
    
    @abstractmethod
    async def get_balance(self, asset: str) -> float: ...
    
    @abstractmethod
    async def get_positions(self) -> Dict[str, float]: ...
    
    @abstractmethod
    async def market_order(self, symbol: str, side: str, qty: float) -> OrderFill: ...
    
    @abstractmethod
    async def close_position(self, symbol: str) -> OrderFill: ...
```

**File:** `argus_py/exchanges/binance.py`, `bybit.py`, `okx.py` (implementations)

### Files to Create
1. `argus_py/exchanges/__init__.py`
2. `argus_py/exchanges/base.py` (interface)
3. `argus_py/exchanges/binance.py` (200 lines)
4. `argus_py/exchanges/bybit.py` (200 lines)
5. `argus_py/exchanges/okx.py` (200 lines)
6. `tests/unit/test_exchanges.py`

---

## P24-002: Telegram Bot Interface

**Assign to:** Sonnet  
**Priority:** P2  
**Estimated:** 6 hours

### Objective
Control and monitor Argus via Telegram commands.

### Commands
- `/status` - Current positions, equity, drawdown
- `/trades` - Recent 5 trades
- `/killswitch [soft|hard|off]` - Control kill-switch
- `/report` - Daily/weekly summary
- `/balance` - Account balance

### Contract

**File:** `argus_py/bot/telegram_bot.py` (NEW)

```python
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pathlib import Path

class ArgusTelegramBot:
    def __init__(self, token: str, run_dir: Path, allowed_users: list):
        self.token = token
        self.run_dir = run_dir
        self.allowed_users = allowed_users
    
    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in self.allowed_users:
            return
        state = self._load_state()
        msg = f"🛡️ *Argus Status*\n"
        msg += f"Equity: ${state.get('equity', 0):.2f}\n"
        msg += f"Drawdown: {state.get('current_dd_pct', 0):.2f}%\n"
        msg += f"Kill-Switch: {state.get('kill_switch_level', 'NORMAL')}"
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    def run(self):
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("trades", self.cmd_trades))
        app.add_handler(CommandHandler("killswitch", self.cmd_killswitch))
        app.run_polling()
```

### Files to Create
1. `argus_py/bot/__init__.py`
2. `argus_py/bot/telegram_bot.py` (200 lines)
3. `Scripts/run_telegram_bot.py`

---

## P24-003: ML Signal Generator

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 10 hours

### Objective
XGBoost/LightGBM model for signal prediction.

### Contract

**File:** `argus_py/ml/signal_model.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from pathlib import Path

@dataclass
class MLFeatures:
    rsi_14: float
    macd_hist: float
    bb_position: float  # 0-1 within bands
    atr_pct: float
    volume_ratio: float
    fear_greed: float
    funding_rate: float

@dataclass
class MLPrediction:
    direction: str  # UP|DOWN|FLAT
    confidence: float
    expected_return: float

class SignalModel:
    def __init__(self, model_path: Optional[Path] = None):
        self.model = None
        if model_path and model_path.exists():
            self.load(model_path)
    
    def train(self, features: np.ndarray, labels: np.ndarray):
        import lightgbm as lgb
        dataset = lgb.Dataset(features, label=labels)
        params = {
            "objective": "multiclass", "num_class": 3,
            "metric": "multi_logloss", "verbosity": -1
        }
        self.model = lgb.train(params, dataset, num_boost_round=100)
    
    def predict(self, features: MLFeatures) -> MLPrediction:
        if self.model is None:
            return MLPrediction("FLAT", 0.5, 0.0)
        
        x = np.array([[features.rsi_14, features.macd_hist, features.bb_position,
                       features.atr_pct, features.volume_ratio, features.fear_greed,
                       features.funding_rate]])
        probs = self.model.predict(x)[0]
        direction = ["DOWN", "FLAT", "UP"][np.argmax(probs)]
        return MLPrediction(direction, max(probs), probs[2] - probs[0])
    
    def save(self, path: Path):
        self.model.save_model(str(path))
    
    def load(self, path: Path):
        import lightgbm as lgb
        self.model = lgb.Booster(model_file=str(path))
```

### Training Script

**File:** `Scripts/train_ml_model.py`

```python
#!/usr/bin/env python3
from argus_py.ml.signal_model import SignalModel
from pathlib import Path
import pandas as pd

def main():
    # Load historical data with features and outcomes
    df = pd.read_csv("runs/training_data.csv")
    features = df[["rsi_14", "macd_hist", "bb_position", "atr_pct", 
                   "volume_ratio", "fear_greed", "funding_rate"]].values
    labels = df["outcome"].values  # 0=down, 1=flat, 2=up
    
    model = SignalModel()
    model.train(features, labels)
    model.save(Path("models/signal_model.lgb"))
    print("Model trained and saved")

if __name__ == "__main__":
    main()
```

### Files to Create
1. `argus_py/ml/__init__.py`
2. `argus_py/ml/signal_model.py` (150 lines)
3. `argus_py/ml/feature_eng.py` (feature extraction)
4. `Scripts/train_ml_model.py`
5. `tests/unit/test_ml_model.py`

---

## P24-004: Compliance & Reporting

**Assign to:** Sonnet  
**Priority:** P2  
**Estimated:** 4 hours

### Objective
Tax-ready trade reports, P&L statements.

### Contract

**File:** `argus_py/reporting/compliance.py` (NEW)

```python
from dataclasses import dataclass
from typing import List
from datetime import date
from pathlib import Path
import csv

@dataclass
class TaxLot:
    symbol: str
    buy_date: date
    buy_price: float
    sell_date: date
    sell_price: float
    quantity: float
    pnl: float
    hold_days: int
    short_term: bool  # <1 year

class ComplianceReporter:
    def __init__(self, trades_csv: Path):
        self.trades_csv = trades_csv
    
    def generate_8949(self, year: int) -> List[TaxLot]:
        """Generate IRS Form 8949 compatible report."""
        lots = []
        # Match buys with sells using FIFO
        # ... implementation
        return [l for l in lots if l.sell_date.year == year]
    
    def generate_pnl_statement(self, start: date, end: date) -> dict:
        """Generate P&L statement for period."""
        lots = self._get_lots_in_range(start, end)
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "total_trades": len(lots),
            "realized_pnl": sum(l.pnl for l in lots),
            "short_term_pnl": sum(l.pnl for l in lots if l.short_term),
            "long_term_pnl": sum(l.pnl for l in lots if not l.short_term),
            "win_rate": sum(1 for l in lots if l.pnl > 0) / len(lots) if lots else 0
        }
    
    def export_csv(self, lots: List[TaxLot], output: Path):
        with open(output, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Symbol", "Buy Date", "Buy Price", "Sell Date", 
                           "Sell Price", "Quantity", "P&L", "Term"])
            for l in lots:
                writer.writerow([l.symbol, l.buy_date, l.buy_price, l.sell_date,
                               l.sell_price, l.quantity, l.pnl, 
                               "Short" if l.short_term else "Long"])
```

### Files to Create
1. `argus_py/reporting/compliance.py` (150 lines)
2. `Scripts/generate_tax_report.py`
3. `tests/unit/test_compliance.py`

---

## Agent Work Log Template

Her agent tamamladığında bu formatı kullanmalı:

```markdown
# Agent Work Log

## Metadata
- **Agent:** [Codex/Gemini/Sonnet]
- **Task ID:** [P20-XXX]
- **Date:** YYYY-MM-DD HH:MM UTC
- **Duration:** Xh Xm

## Files Changed
| File | Action | Lines |
|------|--------|-------|
| path/file.py | CREATE | 150 |

## Verification
\`\`\`bash
[commands run + output]
\`\`\`

## Risks / Follow-ups
- [Any issues encountered]

---
**Agent Signature:** [Agent] @ [Timestamp]
```

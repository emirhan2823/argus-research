# Argus: All-Weather Kisisel Fon Yonetim Sistemi

**Created:** 2026-02-07  
**Major Revision:** 2026-02-09 - Founder Vision + All-Weather Architecture  
**Status:** COMPLETE - Full Strategic Blueprint v3.0  
**Timeline:** Year 1-5 (2026-2030)  
**Sections:** 21 (Founder Vision + All-Weather + Multi-Asset + Fund Metrics + Year-1 Summary + Year-2 Vision + Reference Repos + Growth Strategy + 24/7 Ops + Gate System + Risk + Strategies)

---

## 0. Kurucunun Vizyonu (Founder's Vision)

### Argus Nedir?

Argus, bir "trading bot" degildir. Argus, **kisisel bir fon yonetim sistemidir** - kurucusunun sermayesini **her piyasa kosulunda** buyuten, 7/24 otonom calisan, profesyonel bir hedge fund yoneticisi seviyesinde karar veren bir sistemdir.

### Motivasyon ve Amac

| Hedef | Aciklama |
|-------|----------|
| **Okul Masraflari** | Egitim giderlerinin sistem kazanclariyla karsilanmasi |
| **AI/ML Donanimi** | Kazanclarla GPU/bilgisayar alimi, modellerin yerelde egitilmesi |
| **Finansal Bagimsizlik** | 3 haneli sermayeden ($100) 6-7 haneli seviyeye ($100K+) buyume |
| **Kisisel Fon Yoneticisi** | Uzun vadede tum finansal varliklar icin otonom yonetim asistani |

### Temel Felsefe

> "Piyasa yukari giderse kazan. Asagi giderse kazan. Yana giderse kazan. Cokulurse hayatta kal ve toparlanmada kazan. HER KOSULDA kazan."

Bu felsefe Argus'un tum mimarisini, strateji secimini ve risk yonetimini belirler. Tek bir piyasa kosuluna bagimli bir sistem **basarisizliga mahkumdur**. Argus, Ray Dalio'nun All-Weather yaklasimini bireysel seviyeye adapte eder.

### Mevcut Donanim ("The Beast")

| Bilesen | Detay |
|---------|-------|
| CPU | Intel i7-11800H (8C/16T) |
| RAM | 32 GB DDR4 |
| GPU | NVIDIA RTX A3000M (6GB VRAM) |
| Kullanim | 7/24 trading + ML model egitimi + backtesting |

### Uzun Vadeli Vizyon

Argus sadece kripto ile sinirli kalmayacak. Nihai hedef:
- **Kripto** (mevcut - aktif)
- **ABD Hisse Senetleri** (Year 2)
- **BIST** (Year 2-3)
- **Emtialar** (Altin, Gumus, Petrol) (Year 3)
- **DeFi Yield** (Year 3)
- **Tahvil/Bono** (Year 4)

Tum bunlari yoneten tek bir sistem: **Argus - Kisisel Finansal Asistan**.

---

## 1. All-Weather Trading System Mimarisi

### Neden "All-Weather"?

Cogu trader ve bot **tek bir piyasa kosulunda** calisir:
- Trend-following botlar → **yana piyasada para kaybeder**
- Mean-reversion botlar → **guclu trendde para kaybeder**
- Sadece long botlar → **bear market'te yok olur**

Argus farkli: **7 farkli piyasa kosulunu tanimlayip her birine ozel strateji atar**.

### 7 Piyasa Kosulu ve Strateji Haritasi

| # | Piyasa Kosulu | Tanimlama Kriterleri | Birincil Strateji | Yedek Strateji |
|---|---------------|---------------------|-------------------|----------------|
| 1 | **Bull Trend** | ADX>25, fiyat>MA200, artan hacim | Orion Trend-Follow (Long) | Phoenix Momentum |
| 2 | **Bear Trend** | ADX>25, fiyat<MA200, artan satis | Orion Trend-Follow (Short) | Hedge + stablecoin |
| 3 | **Bull Volatile** | VIX/ATR yuksek, yukari bias | Phoenix Momentum (kisa vadeli) | Hydra Scalp |
| 4 | **Bear Volatile** | VIX/ATR yuksek, asagi bias | Hedge pozisyonlar + Titan DCA | Stablecoin park |
| 5 | **Range/Choppy** | ADX<20, Bollinger daralma | Hydra Mean-Reversion/Scalp | Grid Trading |
| 6 | **Crash/Black Swan** | Ani dusus >15%, panik | ACIL: %80 stablecoin, kill-switch | Kademeli DCA alim |
| 7 | **Recovery** | Crash sonrasi toparlanma, artan hacim | Titan DCA + Orion Long | Phoenix Momentum |

### Rejim Gecis Matrisi

```
Bull Trend <-> Bull Volatile <-> Crash
    |              |               |
Range/Choppy <-> Bear Volatile <- Recovery
    |              |
Bear Trend  <-> Bear Volatile
```

Her gecis icin:
- **Gecis suresi:** Minimum 4 saat onay (whipsaw korumasi)
- **Pozisyon ayarlama:** Kademeli (bir anda %100 degisim yok)
- **Gecis kaybi limiti:** Maksimum %2 portfolio (bkz. Section 3 metrikleri)

### Portfoy Alokasyonu - Rejime Gore

| Rejim | Trend-Follow | Mean-Rev | Momentum | DCA | Cash/Stable |
|-------|-------------|----------|----------|-----|-------------|
| Bull Trend | %40 | %10 | %30 | %10 | %10 |
| Bear Trend | %30 (short) | %10 | %10 | %20 | %30 |
| Bull Volatile | %20 | %15 | %35 | %10 | %20 |
| Bear Volatile | %10 | %10 | %10 | %20 | %50 |
| Range/Choppy | %10 | %40 | %10 | %15 | %25 |
| Crash | %0 | %0 | %0 | %10 | %90 |
| Recovery | %25 | %15 | %25 | %25 | %10 |

### Neden Calisiyor?

1. **Negatif Korelasyon:** Bull stratejileri ve Bear stratejileri birbirini dengeler
2. **Rejim Algilama:** Yanlis stratejiyi yanlis zamanda calistirmak yerine, dogru zamanda dogru arac
3. **Asimetrik Risk:** Crash'te %90 cash = hayatta kalma garantisi; Recovery'de agresif giris = kayiplari hizla telafi
4. **Kademeli Gecis:** Ani rejim degisikliklerinde whipsaw'dan korunma

---

## 2. Multi-Asset Kisisel Finansal Asistan

### Varlik Sinifi Genisleme Yol Haritasi

| Faz | Varlik | Zaman | Platform/Borsa | Oncelik |
|-----|--------|-------|----------------|---------|
| Faz 1 | **Kripto** (BTC, ETH, top altcoin) | Year 1 (simdi) | Binance, Bybit | AKTIF |
| Faz 2 | **ABD Hisse Senetleri** (SPY, QQQ, tech) | Year 2 Q1-Q2 | Alpaca, IBKR | Yuksek |
| Faz 3 | **BIST** (XU100, THYAO, ASELS) | Year 2 Q3-Q4 | IS Yatirim API | Orta |
| Faz 4 | **Emtialar** (XAUUSD, XAGUSD, Petrol) | Year 3 Q1-Q2 | IBKR, forex broker | Orta |
| Faz 5 | **DeFi Yield** (LP, staking, lending) | Year 3 Q3-Q4 | Uniswap, Aave, Lido | Dusuk |
| Faz 6 | **Tahvil/Bono** (US Treasury, TR tahvil) | Year 4 | IBKR, Hazine | Dusuk |

### Amac-Bazli Portfoy Alokasyonu

Argus, kazanclari **amaca gore** ayirir:

| Amac | Hedef Oran | Risk Profili | Varlik Tercihi |
|------|-----------|-------------|----------------|
| **Okul Fonu** | %30 | Dusuk risk | Stablecoin yield, DCA, tahvil |
| **Bilgisayar/GPU Fonu** | %20 | Orta risk | Swing trade kazanclari |
| **Buyume Fonu** | %40 | Yuksek risk | Aktif trading, momentum |
| **Acil Durum** | %10 | Minimum risk | USDT/USDC, banka |

### Gelecek: "Kisisel Finansal Asistan" Ozellikleri

Year 3+ sonrasi Argus su ozelliklere sahip olacak:
- **Otomatik butce yonetimi:** Aylik gelir/gider takibi
- **Hedef bazli yatirim:** "6 ayda laptop icin 2000$ biriktir" → sistem otomatik strateji secer
- **Vergi optimizasyonu:** Kar/zarar dengeleme, vergi raporlama
- **Portfoy rebalancing:** Aylik otomatik dengeleme
- **Risk raporu:** Haftalik PDF rapor - neredesin, nereye gidiyorsun

---

## 3. Profesyonel Fon Yoneticisi Metrikleri

### Basari Kriterleri (KPI'lar)

Argus, bir amator bot degil, **profesyonel fon yoneticisi standartlarinda** olculecek:

| Metrik | Hedef | Aciklama |
|--------|-------|----------|
| **Sharpe Ratio** | > 1.5 | Risk-ayarli getiri (Rf=0 varsayim) |
| **Sortino Ratio** | > 2.0 | Sadece downside risk'e gore getiri |
| **Max Drawdown** | < %8 | En kotu tepeden dibe dusus |
| **Win Rate** | > %55 | Kar eden islem orani |
| **Profit Factor** | > 1.8 | Toplam kar / Toplam zarar |
| **Calmar Ratio** | > 2.0 | Yillik getiri / Max drawdown |
| **Monthly Return** | > %5 | Aylik ortalama net getiri |
| **Recovery Factor** | > 3.0 | Net kar / Max drawdown |

### Benchmark Karsilastirmalari

| Benchmark | Beklenen Argus Ustunlugu |
|-----------|------------------------|
| BTC Buy & Hold | Daha dusuk drawdown, benzer veya daha yuksek getiri |
| S&P 500 | 2-3x yillik getiri (daha yuksek risk ile) |
| Top Crypto Hedge Funds | Rekabetci Sharpe, daha dusuk AUM |
| %5 Mevduat Faizi | 10x+ getiri (cok daha yuksek risk) |

### All-Weather Ozel Metrikler

Bu metrikler Argus'un **her kosulda kazanma** iddiasini olcer:

| Metrik | Hedef | Olcum |
|--------|-------|-------|
| **Bear Market Return** | > %0 (pozitif) | Bear rejimindeki toplam getiri |
| **Crash Survival Rate** | %100 | Crash'te portfoy kaybi < %10 |
| **Regime Transition Loss** | < %2 | Rejim gecislerindeki kayip |
| **All-Weather Score** | > 0.7 | (Pozitif aylar / Toplam aylar) |
| **Worst Month** | > -%5 | En kotu aydaki kayip |
| **Consecutive Loss Days** | < 5 | Art arda kayipli gun sayisi |

### Raporlama Takvimi

| Rapor | Siklik | Icerik |
|-------|--------|--------|
| Gunluk Ozet | Her gun 00:00 UTC | PnL, islem sayisi, rejim durumu |
| Haftalik Analiz | Pazar | KPI tablosu, strateji performansi |
| Aylik Rapor | Ay sonu | Tam metrik seti, benchmark karsilastirma |
| Ceyreklik Review | 3 ayda bir | Strateji ekleme/cikarma karari, parametre guncelleme |

---

## 4. Year-1 Roadmap Summary ✅

| Phase | Dönem | Focus | Tasks |
|-------|-------|-------|-------|
| P20 | Month 1-2 | Engine Enhancement | 7 tasks (34h) |
| P21 | Month 2-3 | Infrastructure | 4 tasks (17h) |
| P22 | Month 3-6 | Advanced Features | 4 tasks (32h) |
| P23 | Month 6-9 | Production Ready | 4 tasks (16h) |
| P24 | Month 9-12 | Scale & Expansion | 4 tasks (32h) |

**Total Year-1:** 23 tasks, ~131 saat

## 4.1 Execution Sync (As of 2026-02-08 09:10 UTC)

- Year-1 delegated execution seti (`P20`-`P24`) tamamlandı (`26/26 DONE`).
- Otoritatif kanıt kaynağı: `Docs/DELEGATED_TASKS.md` + `Docs/AGENT_WORK_LOG_*.md`.

### Done / Not Done Snapshot

| Item | Status | Note |
|------|--------|------|
| Year-1 P20-P24 delivery | `✅ DONE` | Engine, risk, telemetry, dashboard, bot, ML, compliance katmanları teslim edildi. |
| Small-live rollout | `⬜ NOT STARTED` | Paper operasyon sürüyor; canlıya geçiş gate'i beklemede. |
| SOFT-selective trade policy (planned) | `⬜ NOT STARTED` | Plan notu var, kod implementasyonu henüz yok. |
| Full-repo strict lint cleanup (`lint-all`) | `⬜ NOT STARTED` | Hibrit kalite kapısı aktif; global strict cleanup ayrı sprint. |

---

## 5. Year 2+ Vision (After 12 Months)

### 🚀 Phase 25: Advanced Trading (Year 2 Q1)

| Feature | Description | Complexity |
|---------|-------------|------------|
| **Options Trading** | Hedging with BTC/ETH options | High |
| **Arbitrage Engine** | Cross-exchange price arbitrage | Medium |
| **Grid Trading** | Range-bound automated grid | Medium |
| **DCA Bot** | Dollar-cost averaging automation | Low |
| **Copy Trading** | Signal provider/follower system | High |

### 🧠 Phase 26: AI/ML Evolution (Year 2 Q2)

| Feature | Description | Complexity |
|---------|-------------|------------|
| **Reinforcement Learning** | Q-learning for dynamic strategy | Very High |
| **Sentiment NLP v2** | Fine-tuned LLM for crypto news | High |
| **Order Flow Analysis** | Tape reading, large order detection | High |
| **Anomaly Detection** | Unusual market behavior alerts | Medium |
| **AutoML Parameter Tuning** | Automated hyperparameter search | Medium |

### 🌐 Phase 27: Ecosystem Expansion (Year 2 Q3)

| Feature | Description | Complexity |
|---------|-------------|------------|
| **DeFi Integration** | Uniswap/Aave yield strategies | High |
| **On-Chain Analytics** | Whale wallet tracking | Medium |
| **NFT Market Signals** | Floor price, volume analysis | Low |
| **CEX/DEX Hybrid** | Route orders to best venue | High |
| **Social Trading** | Community signals aggregation | Medium |

### 🏢 Phase 28: Enterprise Features (Year 2 Q4)

| Feature | Description | Complexity |
|---------|-------------|------------|
| **Multi-Tenant SaaS** | White-label trading platform | Very High |
| **Fund Management** | Multiple portfolio management | High |
| **Investor Portal** | Performance dashboards for LPs | Medium |
| **Regulatory Reporting** | MiFID II / SEC compliance | High |
| **API Marketplace** | Sell signals as a service | Medium |

---

## 6. Reference Repositories & Integration Plan

### 6.1 When to Use Reference Repos

| Repo | Use Case | Integration Phase |
|------|----------|-------------------|
| **freqtrade** | Strategy backtesting, indicator lib | P20-ENH1 (Orion indicators) |
| **jesse** | Event-driven architecture patterns | P21-001 (Walk-forward) |
| **hummingbot** | Exchange connectors, market making | P24-001 (Multi-exchange) |
| **zipline-reloaded** | Pipeline API, factor model | P24-003 (ML signals) |
| **vectorbt** | Vectorized backtesting | P21-002 (Determinism) |

### 6.2 Specific Integration Points

#### freqtrade → Orion Engine (P20-ENH1)
```python
# Reference: freqtrade/freqtrade/strategy/hyper.py
# Use their indicator implementations as validation
# Compare our RSI/MACD/Bollinger outputs with theirs

from freqtrade.vendor.qtpylib import indicators as qtpylib
# Cross-validate our IndicatorService outputs
```

**When:** During P20-ENH1 development  
**How:** Extract indicator logic for validation, not direct import

---

#### jesse → Walk-Forward (P21-001)
```python
# Reference: jesse-ai/jesse/modes/backtest_mode.py
# Their window management is battle-tested

# Study their approach to:
# - Data windowing without lookahead
# - In-sample/out-of-sample splits
# - Walk-forward validation loop
```

**When:** During P21-001 development  
**How:** Study architecture, implement similar patterns

---

#### hummingbot → Multi-Exchange (P24-001)
```python
# Reference: hummingbot/connector/exchange/
# They have unified exchange interfaces

# Study their:
# - ExchangeBase class
# - Order lifecycle management
# - Rate limiting patterns
# - WebSocket connection handling
```

**When:** During P24-001 development  
**How:** Use as architectural reference for ExchangeAdapter

---

#### vectorbt → Backtesting Performance (P21-002)
```python
# Reference: vectorbt/portfolio/base.py
# Vectorized operations are 10-100x faster

# Consider for:
# - Portfolio simulation speedup
# - Large-scale grid search
# - Monte Carlo simulations
```

**When:** After P21-002, optimization phase  
**How:** Refactor hot paths to use vectorized operations

---

### 6.3 Reference Repo Study Schedule

| Week | Task | Repos to Study |
|------|------|----------------|
| P20 Start | Indicator validation | freqtrade |
| P21 Start | Backtest architecture | jesse, vectorbt |
| P22 Start | Portfolio patterns | zipline-reloaded |
| P24 Start | Exchange connectors | hummingbot |

---

## 7. Technology Roadmap

### Current Stack (Year 1)
- Python 3.11+
- httpx (async HTTP)
- pandas/numpy (data)
- pytest (testing)
- Flask (dashboard)

### Future Stack Additions (Year 2+)
- **Rust** - Performance-critical paths (order matching, tick processing)
- **TimescaleDB** - Time-series storage for millions of bars
- **Redis** - Real-time state, pub/sub
- **Kubernetes** - Container orchestration
- **Kafka** - Event streaming for multi-node
- **MLflow** - ML experiment tracking

---

## 8. Scaling Milestones

| AUM | Infrastructure | Team Size |
|-----|----------------|-----------|
| $10K | Single Mac, paper trading | 1 (you) |
| $100K | VPS + testnet validation | 1-2 |
| $500K | Dedicated server, monitoring | 2-3 |
| $1M | Multi-region, redundancy | 3-5 |
| $10M | Full ops team, compliance | 5-10 |

---

## 9. Risk Evolution

| Phase | Max Position | Leverage | Daily Loss Limit |
|-------|--------------|----------|------------------|
| Paper (now) | 100% | 1x | None |
| Pilot ($1K) | 20% | 1x | 3% |
| Small ($10K) | 15% | 1x | 2% |
| Medium ($100K) | 10% | 1-2x | 1.5% |
| Large ($1M+) | 5% | 1-3x | 1% |

---

## 10. Next Actions (Post Year-1)

1. **Evaluate Year-1 Performance**
   - Compile all walk-forward results
   - Calculate real vs paper divergence
   - Identify best/worst performing modules

2. **Select Year-2 Priorities**
   - Based on performance data
   - User feedback if applicable
   - Market conditions

3. **Architecture Review**
   - Scale bottlenecks identified
   - Code quality audit
   - Technical debt assessment

---

# REFERENCE REPO INTEGRATION TASKS

---

## Reference Integration Status (As of 2026-02-08 09:10 UTC)

| Ref Task | Status | Kısa Not |
|----------|--------|----------|
| `REF-001` freqtrade Indicator Validator | `⚠️ PARTIAL` | Orion göstergeleri geliştirildi (`P20-ENH1`), ancak `argus_py/validation/indicator_validator.py` contract dosyaları henüz yok. |
| `REF-002` jesse Window Manager | `⚠️ PARTIAL` | `argus_py/lab/walk_forward.py` ile WF altyapısı tamamlandı, ancak `argus_py/lab/window_manager.py` contract dosyası yok. |
| `REF-003` hummingbot Connector Pattern | `⚠️ PARTIAL` | Multi-exchange adaptörler (`argus_py/exchanges/base.py`, `binance.py`, `bybit.py`, `okx.py`) tamamlandı; contract'taki `connector.py` isimlendirmesi birebir uygulanmadı. |
| `REF-004` vectorbt Vectorized Backtesting | `⬜ NOT STARTED` | `argus_py/lab/vectorized.py` ve benchmark/test dosyaları henüz yok. |
| `REF-005` zipline Factor Pipeline | `⬜ NOT STARTED` | `argus_py/ml/factor_pipeline.py` ve ilgili testler henüz yok. |

---

## REF-001: freqtrade Indicator Library Integration

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 4 hours  
**Use In:** P20-ENH1 (Orion Engine)

### Objective
Extract and validate indicator implementations from freqtrade for cross-checking our IndicatorService.

### Source Files to Study
```
freqtrade/
├── freqtrade/strategy/hyper.py          # HyperOpt patterns
├── freqtrade/vendor/qtpylib/indicators.py  # Core indicators
└── freqtrade/technical/indicators.py    # Extended indicators
```

### Contract

**File:** `argus_py/validation/indicator_validator.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

@dataclass
class ValidationResult:
    indicator: str
    our_values: List[float]
    reference_values: List[float]
    max_diff: float
    passed: bool

class IndicatorValidator:
    """Cross-validate our indicators against freqtrade implementations."""
    
    def validate_rsi(self, closes: List[float], period: int = 14) -> ValidationResult:
        from argus_py.models.orion.indicators import IndicatorService
        
        # Our implementation
        our_rsi = IndicatorService.rsi(closes, period)
        
        # freqtrade reference (qtpylib style)
        ref_rsi = self._freqtrade_rsi(closes, period)
        
        max_diff = max(abs(a - b) for a, b in zip(our_rsi, ref_rsi) if a and b)
        return ValidationResult("RSI", our_rsi, ref_rsi, max_diff, max_diff < 0.01)
    
    def _freqtrade_rsi(self, closes: List[float], period: int) -> List[float]:
        """Reference RSI from freqtrade/qtpylib."""
        import pandas as pd
        close = pd.Series(closes)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return (100 - (100 / (1 + rs))).tolist()
    
    def validate_all(self, closes: List[float]) -> dict:
        return {
            "rsi": self.validate_rsi(closes),
            "macd": self.validate_macd(closes),
            "bollinger": self.validate_bollinger(closes),
            "stochastic": self.validate_stochastic(closes),
        }
```

### Acceptance Criteria
- [ ] RSI diff < 0.01 vs freqtrade
- [ ] MACD diff < 0.01 vs freqtrade
- [ ] Bollinger bands match within tolerance
- [ ] Stochastic %K/%D match

### Verification
```bash
pytest tests/unit/test_indicator_validator.py -v

python -c "
from argus_py.validation.indicator_validator import IndicatorValidator
import random

closes = [random.uniform(40000, 50000) for _ in range(100)]
validator = IndicatorValidator()
results = validator.validate_all(closes)

for name, result in results.items():
    status = '✅' if result.passed else '❌'
    print(f'{status} {name}: max_diff={result.max_diff:.6f}')
"
```

### Files to Create
1. `argus_py/validation/__init__.py`
2. `argus_py/validation/indicator_validator.py` (150 lines)
3. `tests/unit/test_indicator_validator.py`

---

## REF-002: jesse Walk-Forward Architecture

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 3 hours  
**Use In:** P21-001 (Walk-Forward)

### Objective
Study jesse's backtest architecture for walk-forward window management patterns.

### Source Files to Study
```
jesse/
├── jesse/modes/backtest_mode.py      # Main backtest loop
├── jesse/services/candle.py          # Candle management
└── jesse/helpers.py                  # Time utilities
```

### Key Patterns to Extract

**1. Window Management (no lookahead)**
```python
# jesse pattern: strict time boundaries
class WindowManager:
    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end
        self._cache = {}
    
    def get_candles(self, symbol: str, tf: str, limit: int) -> np.ndarray:
        """Only return candles UP TO current time - no future data."""
        candles = self._fetch_all(symbol, tf)
        # Critical: filter by time
        return candles[candles[:, 0] <= self.current_time][-limit:]
```

**2. In-Sample/Out-of-Sample Split**
```python
# jesse pattern: clean separation
def split_data(data: pd.DataFrame, train_ratio: float = 0.7):
    split_idx = int(len(data) * train_ratio)
    train = data.iloc[:split_idx].copy()
    test = data.iloc[split_idx:].copy()
    return train, test
```

### Contract

**File:** `argus_py/lab/window_manager.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Generator
from datetime import date, timedelta
import pandas as pd

@dataclass
class TimeWindow:
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    window_id: int

class WindowManager:
    """
    Walk-forward window manager inspired by jesse architecture.
    Guarantees no lookahead bias.
    """
    
    def __init__(self, train_months: int = 6, test_months: int = 1):
        self.train_months = train_months
        self.test_months = test_months
    
    def generate_windows(
        self,
        start: date,
        end: date,
        step_months: int = 1
    ) -> Generator[TimeWindow, None, None]:
        """Generate rolling windows with proper train/test splits."""
        window_id = 0
        current = start + timedelta(days=self.train_months * 30)
        
        while current + timedelta(days=self.test_months * 30) <= end:
            yield TimeWindow(
                train_start=current - timedelta(days=self.train_months * 30),
                train_end=current - timedelta(days=1),
                test_start=current,
                test_end=current + timedelta(days=self.test_months * 30) - timedelta(days=1),
                window_id=window_id
            )
            current += timedelta(days=step_months * 30)
            window_id += 1
    
    def slice_data(self, df: pd.DataFrame, window: TimeWindow, mode: str) -> pd.DataFrame:
        """
        Slice dataframe for train or test period.
        CRITICAL: Ensures no future data leaks.
        """
        if mode == "train":
            mask = (df.index >= window.train_start) & (df.index <= window.train_end)
        else:
            mask = (df.index >= window.test_start) & (df.index <= window.test_end)
        return df.loc[mask].copy()
```

### Acceptance Criteria
- [ ] Windows generate correctly
- [ ] No overlap between train and test
- [ ] Data slicing respects boundaries
- [ ] Proper date handling

### Files to Create
1. `argus_py/lab/window_manager.py` (100 lines)
2. `tests/unit/test_window_manager.py`

---

## REF-003: hummingbot Exchange Connector Pattern

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 6 hours  
**Use In:** P24-001 (Multi-Exchange)

### Objective
Study hummingbot's exchange connector architecture for unified multi-exchange support.

### Source Files to Study
```
hummingbot/
├── hummingbot/connector/exchange_base.py      # Base interface
├── hummingbot/connector/exchange/binance/     # Binance impl
├── hummingbot/connector/exchange/kucoin/      # KuCoin impl
└── hummingbot/core/rate_oracle/               # Rate limiting
```

### Key Patterns to Extract

**1. Unified Exchange Interface**
```python
# hummingbot pattern: abstract base
class ExchangeBase(ABC):
    @abstractmethod
    async def get_order_book(self, symbol: str) -> OrderBook: ...
    
    @abstractmethod
    async def create_order(self, order: OrderRequest) -> OrderResult: ...
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...
    
    @abstractmethod
    async def get_balances(self) -> Dict[str, Decimal]: ...
```

**2. Rate Limiting Pattern**
```python
# hummingbot pattern: per-exchange limits
class RateLimiter:
    def __init__(self, calls_per_second: float):
        self.calls_per_second = calls_per_second
        self._last_call = 0
    
    async def acquire(self):
        now = time.time()
        wait = (1 / self.calls_per_second) - (now - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.time()
```

### Contract

**File:** `argus_py/exchanges/connector.py` (NEW)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional
from decimal import Decimal
import asyncio

@dataclass
class OrderBook:
    bids: list  # [(price, qty), ...]
    asks: list
    timestamp: int

@dataclass
class Balance:
    free: Decimal
    locked: Decimal
    total: Decimal

class ExchangeConnector(ABC):
    """
    Unified exchange interface inspired by hummingbot.
    All exchanges implement this interface.
    """
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self._rate_limiter = RateLimiter(10)  # 10 calls/sec default
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> dict: ...
    
    @abstractmethod
    async def get_order_book(self, symbol: str, depth: int = 20) -> OrderBook: ...
    
    @abstractmethod
    async def get_balances(self) -> Dict[str, Balance]: ...
    
    @abstractmethod
    async def place_market_order(
        self, symbol: str, side: str, quantity: Decimal
    ) -> str: ...
    
    @abstractmethod
    async def place_limit_order(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal
    ) -> str: ...
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> dict: ...

class RateLimiter:
    def __init__(self, calls_per_second: float = 10):
        self.interval = 1.0 / calls_per_second
        self._last_call = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self.interval - (now - self._last_call)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_call = asyncio.get_event_loop().time()
```

### Files to Create
1. `argus_py/exchanges/connector.py` (base interface)
2. `argus_py/exchanges/binance_connector.py` (200 lines)
3. `argus_py/exchanges/bybit_connector.py` (200 lines)
4. `tests/unit/test_exchange_connectors.py`

---

## REF-004: vectorbt Vectorized Backtesting

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 4 hours  
**Use In:** P21-002, Performance Optimization

### Objective
Apply vectorbt patterns for 10-100x faster backtesting.

### Source Files to Study
```
vectorbt/
├── vectorbt/portfolio/base.py         # Portfolio simulation
├── vectorbt/indicators/factory.py     # Indicator factory
└── vectorbt/signals/factory.py        # Signal generation
```

### Key Pattern: Vectorized Portfolio Simulation
```python
# vectorbt pattern: no loops
import numpy as np

def vectorized_portfolio(
    prices: np.ndarray,
    entries: np.ndarray,  # boolean
    exits: np.ndarray,    # boolean
    size: float = 1.0
) -> np.ndarray:
    """
    Calculate equity curve without Python loops.
    10-100x faster than iterative approach.
    """
    # Position state (1 = long, 0 = flat)
    position = np.zeros(len(prices))
    position[entries] = 1
    position[exits] = 0
    position = np.maximum.accumulate(position)  # Hold until exit
    
    # Returns
    returns = np.diff(prices) / prices[:-1]
    returns = np.insert(returns, 0, 0)
    
    # Equity
    portfolio_returns = returns * position * size
    equity = np.cumprod(1 + portfolio_returns)
    
    return equity
```

### Contract

**File:** `argus_py/lab/vectorized.py` (NEW)

```python
import numpy as np
from dataclasses import dataclass
from typing import Tuple

@dataclass
class VectorizedResult:
    equity_curve: np.ndarray
    total_return: float
    sharpe: float
    max_dd: float
    trades: int

class VectorizedBacktest:
    """
    High-performance backtesting using vectorbt patterns.
    Avoids Python loops for 10-100x speedup.
    """
    
    def __init__(self, prices: np.ndarray):
        self.prices = prices
        self.returns = np.diff(prices) / prices[:-1]
        self.returns = np.insert(self.returns, 0, 0)
    
    def run(
        self,
        entries: np.ndarray,
        exits: np.ndarray,
        position_size: float = 1.0
    ) -> VectorizedResult:
        # Vectorized position tracking
        position = np.zeros(len(self.prices))
        
        # Entry signals start positions
        in_position = False
        for i in range(len(self.prices)):
            if entries[i] and not in_position:
                in_position = True
            if exits[i] and in_position:
                in_position = False
            position[i] = 1.0 if in_position else 0.0
        
        # Calculate equity (vectorized)
        portfolio_returns = self.returns * position * position_size
        equity = np.cumprod(1 + portfolio_returns) * 1000  # Start with 1000
        
        # Metrics (vectorized)
        total_return = (equity[-1] / equity[0] - 1) * 100
        sharpe = np.mean(portfolio_returns) / np.std(portfolio_returns) * np.sqrt(252) if np.std(portfolio_returns) > 0 else 0
        max_dd = self._max_drawdown(equity)
        trades = int(np.sum(np.diff(position) == 1))
        
        return VectorizedResult(equity, total_return, sharpe, max_dd, trades)
    
    def _max_drawdown(self, equity: np.ndarray) -> float:
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak
        return float(np.max(dd) * 100)
```

### Performance Comparison
```python
# Iterative: ~10s for 1M bars
# Vectorized: ~0.1s for 1M bars
```

### Files to Create
1. `argus_py/lab/vectorized.py` (150 lines)
2. `tests/unit/test_vectorized.py`
3. `Scripts/benchmark_vectorized.py`

---

## REF-005: zipline Factor Model Integration

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 5 hours  
**Use In:** P24-003 (ML Signals)

### Objective
Study zipline's Pipeline API for factor-based signal generation.

### Key Pattern: Factor Pipeline
```python
# zipline pattern: declarative factors
from zipline.pipeline import Pipeline
from zipline.pipeline.factors import RSI, MACD

def make_pipeline():
    rsi = RSI(window_length=14)
    macd = MACD(fast_period=12, slow_period=26)
    
    return Pipeline(
        columns={
            'rsi': rsi,
            'macd_signal': macd.signal,
            'buy': (rsi < 30) & (macd.signal > 0),
            'sell': (rsi > 70) & (macd.signal < 0),
        }
    )
```

### Contract

**File:** `argus_py/ml/factor_pipeline.py` (NEW)

```python
from dataclasses import dataclass
from typing import Dict, Callable, List
import pandas as pd
import numpy as np

@dataclass
class Factor:
    name: str
    compute: Callable[[pd.DataFrame], pd.Series]
    
class FactorPipeline:
    """
    Factor-based signal generation inspired by zipline Pipeline.
    """
    
    def __init__(self):
        self.factors: Dict[str, Factor] = {}
    
    def add_factor(self, name: str, compute: Callable):
        self.factors[name] = Factor(name, compute)
    
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        result = pd.DataFrame(index=df.index)
        for name, factor in self.factors.items():
            result[name] = factor.compute(df)
        return result
    
    # Built-in factors
    @staticmethod
    def rsi_factor(period: int = 14):
        def compute(df: pd.DataFrame) -> pd.Series:
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        return compute
    
    @staticmethod
    def momentum_factor(period: int = 20):
        def compute(df: pd.DataFrame) -> pd.Series:
            return df['close'].pct_change(period)
        return compute
```

### Files to Create
1. `argus_py/ml/factor_pipeline.py` (200 lines)
2. `argus_py/ml/builtin_factors.py` (common factors)
3. `tests/unit/test_factor_pipeline.py`

---

## 11. 24/7 Otonom Calisma Mimarisi

### 11.1 Temel Felsefe

Kripto piyasasi 7/24 acik. Gece 03:00'te gelen likidation cascade'i kacirmak, en kolay parayi kacirmak demek. Sistem **insanin uyudugu saatlerde bile** tam otomatik calismali.

### 11.2 Hibrit Altyapi: Beast + Soldier

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ARGUS HYBRID INFRASTRUCTURE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  "THE BEAST" (Yerel Laptop)              "THE SOLDIER" (Cloud VPS)   │
│  ┌───────────────────────────┐           ┌──────────────────────┐   │
│  │  i7-11800H / 32GB / A3000M│           │  1-2 vCPU / 2-4GB   │   │
│  │                           │           │                      │   │
│  │  - Arastirma & Backtest   │  Model/   │  - 24/7 Execution    │   │
│  │  - ML Training (GPU)      │  Config   │  - WebSocket Listen  │   │
│  │  - HyperOpt (16 paralel)  │ ──────▶  │  - Order Routing     │   │
│  │  - LLM Sentiment (local)  │  Sync     │  - Heartbeat         │   │
│  │  - Walk-Forward Optim.    │           │  - Kill-Switch       │   │
│  └───────────────────────────┘           └──────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Beast Kullanim Alanlari:**
- CPU (8c/16t): 16 paralel backtest -> HyperOpt 100x daha hizli
- RAM (32GB): 5 yillik 1m tick verisi memory'de analiz
- GPU (RTX A3000M 6GB): XGBoost/LightGBM GPU egitimi, Ollama ile lokal LLM (Llama3 Q4)

**Soldier Spec:**
- Instance: `t3.medium` (2 vCPU, 4GB) veya `c5.large` (compute optimized)
- Lokasyon: `ap-northeast-1` (Tokyo) - Binance sunucusuna yakin
- OS: Ubuntu 22.04 LTS Minimal

### 11.3 Process Yonetimi

```
┌─────────────────────────────────────────────────────────┐
│  PM2 Process Manager                                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  pm2 start Scripts/paper_daemon.py --name argus-core     │
│  pm2 start Scripts/dashboard.py --name argus-web         │
│  pm2 start Scripts/year2_autopilot.py --name argus-night │
│                                                          │
│  Auto-restart on crash                                   │
│  Memory limit watchdog                                   │
│  Log rotation                                            │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  Nginx Reverse Proxy + Certbot SSL                       │
│  Dashboard: https://argus.yourdomain.com                 │
│  API: https://api.argus.yourdomain.com                   │
└─────────────────────────────────────────────────────────┘
```

### 11.4 Gece Autopilot Dongusu

Her gece (01:00 lokal) otomatik calisan batch:

| Adim | Script | Cikti |
|------|--------|-------|
| 1. Determinizm Check | `Scripts/verify_determinism.py` | Pass/Fail |
| 2. Metrik Paketi | `Scripts/year2_generate_metrics.py` | `metrics.json` |
| 3. Walk-Forward Refresh | `Scripts/sprint1_walkforward_12m.py` | window-level CSV |
| 4. Haftalik Audit | `Scripts/weekly_audit.py` | `weekly_audit.json` |
| 5. Sinyal Audit | `Scripts/phase20_signal_audit.py` | `signal_audit.md` |
| 6. ML Model Refresh | `Scripts/train_ml_model.py` | `signal_model.lgb` |
| 7. TopHunter Sweep | `Scripts/tophunter_sweep.py` | `tophunter_tuning.md` |
| 8. Strateji Governance | `Scripts/strategy_registry.py` | `strategy_governance.md` |

**Fallback Kurallari:**
- Bir profil `MAX_RESTARTS_PER_HOUR` asarsa, sadece o profil durdurulur
- Heartbeat > 180s stale ise, yalniz o profil restart edilir
- Kill-switch `HARD/HALT` ise: yeni giris yok, mevcut pozisyonlar politikaya gore

### 11.5 Monitoring & Alert Stack

```
Health Check (her dakika cron):
├── localhost:8080/health ping
├── PM2 status kontrolu
├── Heartbeat freshness (< 3 dk)
└── Portfolio DD watchdog (> 5% -> HARD KILL)

Alert Kanallari:
├── Telegram Bot (anlik)
├── Discord Webhook (anlik)
└── Email (gecikme tolere edilir)
```

| Alert | Tetikleyici | Kanal |
|-------|-------------|-------|
| `alert_kill_switch` | Risk level `SOFT/HARD/HALT` | Telegram + Discord |
| `alert_heartbeat_stale` | > 3 dk heartbeat yok | Telegram |
| `alert_execution_anomaly` | Slippage > p99 | Telegram + Discord |
| `alert_drift_spike` | Drift > gate threshold 2x ust uste | Telegram |
| `alert_night_batch_fail` | Artifact eksik 06:00'a kadar | Telegram + Email |

### 11.6 Uptime Hedefleri

| Faz | Hedef Uptime | RTO |
|-----|-------------|-----|
| Paper | >= 99.0% | 1 dk (auto-restart) |
| Micro-live | >= 99.5% | 1 dk |
| Live | >= 99.7% | 30 sn |
| Scale | >= 99.9% | 15 sn (multi-region) |

---

## 12. 3 Haneden 6-7 Haneye: Sermaye Buyume Yol Haritasi

### 12.1 Matematiksel Gerceklik

$100'dan $100,000'e = **1000x** buyume. Tek lineer strateji ile kisa surede imkansiz (yikim riski olmadan).

**Kazanma Formulu:**
```
Buyume = (Edge x Frekans) - (Risk + Maliyet)
```

- **Edge** = Strateji kalitesi (pozitif beklenti)
- **Frekans** = Islem sayisi (bilesik getiri hizi)
- **Risk** = Drawdown kontrolu (hayatta kalma)
- **Maliyet** = Fee + slippage + latency

### 12.2 Buyume Fazlari

| Faz | Sermaye | Odak | Stratejiler | Risk/Trade | Tahmini Sure |
|-----|---------|------|-------------|------------|-------------|
| **Micro** | $100 - $1,000 | Agresif buyume, yuksek frekans | Hydra Scalp + Titan DCA | 2% | 6 ay |
| **Base** | $1,000 - $10,000 | Stabilite, trend ekleme | + Orion Trend | 1.5% | 12 ay |
| **Acceleration** | $10,000 - $50,000 | Diversifikasyon | + Phoenix Revert + Argo Arb | 1% | 18 ay |
| **6-Figure** | $50,000 - $100,000+ | Sermaye koruma | Portfolio balancing + DeFi yield | 0.5-1% | 24 ay |

### 12.3 Era Bazli Detay (4 Yillik Bakis)

| Era | Donem | Sermaye | Mod | Kaynak |
|-----|-------|---------|-----|--------|
| Era 0: Foundation | 2026 H1 | $30 - $500 | Paper + backtest | Kisisel birikim |
| Era 1: Proof | 2026 H2 | $500 - $2,000 | Paper 24/7 | Birikim + kucuk getiri |
| Era 2: Pilot | 2027 | $2,000 - $10,000 | Kucuk canli | Getiri + birikim |
| Era 3: Scale | 2028 | $10,000 - $50,000 | Multi-strateji | Bilesik getiri |
| Era 4: Professional | 2029 | $50,000 - $250,000 | Kurumsal ops | Bilesik + (dis sermaye?) |
| Era 5: Maturity | 2030+ | $250,000+ | Otonom makine | Bilesik getiri |

### 12.4 Sermaye Kurallari (Degismez)

1. **Kaybedebileceginizi risk edin.** Ilk $10K birikim + is gelirinizden, sistem getirisinden degil.
2. **Bilesikleyin, cekmeyin.** $50K'ye kadar tum getirileri yeniden yatirin.
3. **Kovalamak yok.** Sistem %10 dususteyse, "kurtarmak" icin ekstra para eklemeyin.
4. **Yavas olceklendirin.** Pozisyon artisi yalniz 3+ ay pozitif performanstan sonra.
5. **Ayristirin.** Trading sermayesi != Acil durum fonu != Yasam giderleri.

### 12.5 Bilesik Getiri Projeksiyonu (Baslangic: $100)

| Aylik Getiri | 12 Ay Sonrasi | 24 Ay Sonrasi | 36 Ay Sonrasi | 48 Ay Sonrasi |
|-------------|---------------|---------------|---------------|---------------|
| %3 | $143 | $203 | $289 | $411 |
| %5 | $180 | $323 | $580 | $1,040 |
| %8 | $252 | $634 | $1,594 | $4,010 |
| %10 | $314 | $985 | $3,091 | $9,700 |
| %15 | $535 | $2,862 | $15,308 | $81,871 |

> **Not:** Saf bilesik getiri hesabidir. Gercekte drawdown, fee, slippage ve disi birikim eklenince tablo degisir. Ancak %8-10 tutarli aylik getiri ile $100K'ya 3-4 yilda ulasmak matematiksel olarak mumkun.

### 12.6 "Senior Quant" Direktifleri

1. **Fee ile savasmayin.** Kucuk hesapta taker fee oldurucu. **Her zaman Limit Order (Post-Only)** kullanin (acil cikislar haric).
2. **Execution = Alpha.** Slippage de bir fee'dir. TWAP ve Chase-Limit mantigi implement edin.
3. **Veri = Edge.** Herkesin fiyat verisi var. **Orderbook Imbalance** ve **Liquidation Cascade** verisini alin.
4. **Korelasyon = Gizli Risk.** BTC ve ETH %90 korelasyondaysa, her ikisinin pozisyonunu yariya dusurun.

---

## 13. Strateji Portfolyosu ("Futbol Takimi")

### 13.1 Neden Tek Strateji Yetmez

Tek bir yildiz oyuncuya guvenmeyin. Bir takim kurun. Her piyasa kosulunda en az bir strateji kazanc saglayacak sekilde diversifiye edin.

### 13.2 Strateji Envanteri

| Strateji | Rejim Uygunlugu | Hedef | Timeframe | Mevcut Durum |
|----------|-----------------|-------|-----------|-------------|
| **Orion Trend** | Bull/Bear Trend | Buyuk hareketleri yakala (haftalik) | 1h-4h | Mevcut (Refine) |
| **Phoenix Revert** | High Vol Choppy | Wichleri fade et | 15m-1h | Mevcut (Refine) |
| **Hydra Scalp** | Low Vol Calm | 5-15m kucuk scalplar | 5m-15m | YENI |
| **Argo Arbitrage** | Any | Risksiz spread / funding farming | Tick-level | YENI |
| **Titan HODL** | Bull Trend | Akilli DCA (sadece dip alim) | 1d | YENI |
| **TopHunter Short** | Bear/Chop | Yapisal kirilim sonrasi short | 1h | Paper-Only |

### 13.3 Rejim-Strateji Matrisi

```
Rejim = BULL_TREND  ->  Orion (Long) + Titan DCA       -> Phoenix OFF, Hydra LOW
Rejim = BEAR_TREND  ->  Orion (Short) + TopHunter       -> Titan OFF, Hydra LOW
Rejim = HIGH_VOL    ->  Phoenix + Grid                   -> Orion OFF (trend'de oldurur)
Rejim = LOW_VOL     ->  Hydra Scalp + Argo Funding      -> Orion BEKLE, Phoenix BEKLE
```

### 13.4 Strateji Lifecycle

```
FIKIR -> HIPOTEZ -> BACKTEST -> WALK-FORWARD -> PAPER -> LIVE -> MONITOR -> EMEKLILIK
```

**Gate Metrikleri:**
- Backtest Gate: Profit Factor > 1.2, Sharpe > 0.5
- Walk-Forward Gate: %60+ pencerede pozitif beklenti
- Paper Gate: Paper sonuclari backtest'in %20'si icinde
- Emeklilik Tetikleyicileri: 30 gun DD > threshold VEYA 60 gun PF < 1.0

### 13.5 Portfolyo Kurallari

| Kural | Limit |
|-------|-------|
| Maks strateji sayisi | 10 |
| Min strateji sayisi | 2 |
| Maks tek strateji alokasyonu | %30 |
| Maks stratejiler arasi korelasyon | 0.5 |
| Maks alokasyon icin gereken track record | 6 ay |

---

## 14. Market Rejim Motoru ("Hava Istasyonu")

### 14.1 Neden Gerekli

Tek bir strateji tum hava kosullarinda kazanamaz. "Hava Istasyonu" (Rejim Dedektoru) stratejileri otomatik degistirir.

### 14.2 Rejim Siniflandirmasi

Her 4 saatte bir piyasa durumunu 4 kovaya siniflandir:

| Rejim | HV Rank | ADX | Funding | Aktif Strateji |
|-------|---------|-----|---------|----------------|
| **BULL_TREND** | Any | > 25 | > 0 | Orion (Long), Titan |
| **BEAR_TREND** | Any | > 25 | < 0 | Orion (Short), TopHunter |
| **HIGH_VOL_CHOP** | > 80 percentile | < 25 | Any | Phoenix, Grid |
| **LOW_VOL_CALM** | < 40 percentile | < 20 | Any | Hydra, Argo |

### 14.3 Girdiler

| Girdi | Kaynak | Kullanim |
|-------|--------|----------|
| VIX Proxy | Crypto HV (24h rolling) | Volatilite seviyesi |
| ADX(14) | Fiyat verisi | Trend gucu |
| Avg Funding Rate (3d) | Binance/Bybit API | Piyasa sentiment |
| Long/Short Ratio | Exchange API | Kalabalik pozisyon |
| On-Chain Inflow | Glassnode / CryptoQuant | Balina hareketi |
| Market Breadth | CoinGecko (% coins > MA200) | Genel piyasa sagligi |

### 14.4 Contract Tasarimi

**Dosya:** `argus_py/regime/classifier.py` (PLANLI)

- `MarketRegime` enum: `BULL_TREND`, `BEAR_TREND`, `HIGH_VOL_CHOP`, `LOW_VOL_CALM`
- `RegimeSnapshot` dataclass: regime, confidence, hv_percentile, adx_value, avg_funding_3d, market_breadth, timestamp
- `RegimeClassifier` sinifi:
  - `classify(hv_rank, adx, funding, breadth) -> RegimeSnapshot`
  - `get_active_strategies(regime) -> list` (rejime gore hangi stratejiler aktif)
  - `_calc_confidence(...)` (siniflandirma guveni 0-1)

**Olusturulacak Dosyalar:**
1. `argus_py/regime/__init__.py`
2. `argus_py/regime/classifier.py` (~150 satir)
3. `argus_py/regime/data_sources.py` (API entegrasyonu)
4. `tests/unit/test_regime_classifier.py`

---

## 15. 7 Motor Kripto Adaptasyonu

### 15.1 Motor Envanteri ve Kapsam

Swift legacy'de 7 analiz motoru var. Python kripto implementasyonundaki durum:

| # | Motor | Legacy (Swift) | Kripto (Python) | Gap | Oncelik |
|---|-------|----------------|-----------------|-----|---------|
| 1 | **ORION** | Full (RSI,MACD,BB,ATR,Stoch) | Partial (ADX,SMA) | 5+ indikatoru eksik | HIGH |
| 2 | **ATLAS** | Fundamental (FMP P/E,ROE) | Yok | On-chain adaptasyon gerek | HIGH |
| 3 | **AETHER** | Macro (FRED,VIX,DXY) | Yok | Kripto macro gerek | HIGH |
| 4 | **HERMES** | News AI (RSS+Groq) | Yok | Ayni mimari portu | MEDIUM |
| 5 | **PHOENIX** | Channel Reversion | Mevcut (taslak) | Refine gerek | OK |
| 6 | **COUNCIL** | Weighted Voting | Mevcut | Farkli formul | OK |
| 7 | **CHIRON** | ML Weight Learning | Yok | Trade gecmisi lazim | PHASE 2 |

### 15.2 ATLAS-C: On-Chain Fundamental Analiz

**Legacy ATLAS** sirket bilancolarini analiz eder (P/E, ROE, Borc). Kripto'da bilancu yok ama on-chain metrikleri var.

| Legacy Metrik | Kripto Karsiligi | Veri Kaynagi |
|---------------|------------------|-------------|
| P/E Ratio | NVT Ratio (Market Cap / Tx Volume) | CoinGecko / Glassnode |
| ROE | Protocol Revenue / TVL | DefiLlama, Token Terminal |
| Gross Margin | Protocol Revenue / Emissions | Token Terminal |
| Growth Rate | TVL Growth, Volume Growth | DefiLlama |
| N/A | MVRV Ratio (MC / Realized Cap) | Glassnode |
| N/A | Exchange Reserve | CryptoQuant |
| N/A | Active Addresses | Glassnode |
| N/A | Funding Rate | Binance API |

**Contract Tasarimi:** `argus_py/models/atlas/atlas_c.py` (PLANLI)

- `OnChainScore` dataclass: nvt_score, mvrv_score, exchange_reserve, active_addresses, funding_rate, composite
- `AtlasCrypto` sinifi: Weighted average ile composite skor hesaplar
- Agirliklar: NVT %25, MVRV %25, Exchange Reserve %20, Active Addresses %15, Funding %15

### 15.3 AETHER-C: Kripto Makro Ortam

| Kategori | Legacy | Kripto Karsiligi | API |
|----------|--------|------------------|-----|
| Risk Indikatoru | VIX | Crypto Fear & Greed Index | Alternative.me |
| Para Politikasi | Fed Funds Rate | Stablecoin Supply Change | CoinGecko |
| Enflasyon Proxy | CPI | Bitcoin Dominance | CoinGecko |
| Risk Asset Momentum | SPY | Total Crypto Market Cap | CoinGecko |
| Guvenli Liman | GLD | USDT Dominance | CoinGecko |
| Doviz Gucu | DXY | DXY (ayni) | Yahoo Finance |
| Oncul Gosterge | Initial Claims | Whale Wallet Movement | Glassnode |

**Contract Tasarimi:** `argus_py/models/aether/aether_c.py` (PLANLI)

- `MacroRegime` enum: `RISK_ON`, `RISK_OFF`, `NEUTRAL`
- `AetherCrypto` sinifi:
  - Fear & Greed (%30 agirlik) + BTC Dominance (%20) + MCap Trend (%30) + DXY (%20)
  - Skor > 65 = RISK_ON, < 35 = RISK_OFF, arasi NEUTRAL

### 15.4 HERMES-C: Kripto Haber Sentiment

Mimari Legacy ile ayni: RSS -> LLM -> Score

**Kripto RSS Kaynaklari:**
- CoinDesk, CoinTelegraph, The Block, Decrypt
- CoinTelegraph TR, BloombergHT (BIST icin)

**AI Pipeline:**
1. RSS headline'lari topla
2. Groq'a (Llama 3.1) veya Lokal Ollama'ya gonder
3. Sentiment + confidence cikar
4. Kaynaklarda aggregate et

**Contract Tasarimi:** `argus_py/models/hermes/hermes_c.py` (PLANLI)

- `LLMSentimentEngine`: Ollama endpoint'e baglanir (zero-cost lokal LLM)
- `SentimentResult` dataclass: score (-1 to 1), summary, entities
- GPU kullanimi: RTX A3000M uzerinde Llama3 Q4 quantized model

### 15.5 CHIRON: Ogrenme Motoru (Phase 2)

**On Kosul:** 50+ tamamlanmis trade ile telemetri (decisions.csv, trades.csv)
**Mevcut Durum:** Telemetri mevcut, ogrenme dongusu henuz yok

**Contract Tasarimi:** `argus_py/learning/chiron.py` (PLANLI)

- Her rejim icin en iyi agirlik setini bulma
- Objective: maximize Sharpe, minimize DD
- Trade sonuclarina gore motor agirliklarini optimize etme

### 15.6 Kripto Council Agirliklari (Onerilen)

```
Technical (Orion-C):  45%   # Fiyat aksiyonu kripto'da baskin
On-Chain (Atlas-C):   25%   # Fundamentaller daha az onemli
Macro (Aether-C):     20%   # Makro donguleri onemli
Sentiment (Hermes-C): 10%   # Gurultu/sinyal orani dusuk
```

### 15.7 Implementasyon Takvimi

| Hafta | Gorev | Motor | Tahmini Sure |
|-------|-------|-------|-------------|
| H1-H2 | Orion Enhancement (RSI,MACD,BB,Stoch) | ORION | 4-6 saat |
| H3-H4 | Aether-C Kripto Macro | AETHER | 6-8 saat |
| H5-H6 | Hermes-C News Sentiment | HERMES | 4-6 saat |
| H7-H8 | Atlas-C On-Chain | ATLAS | 6-8 saat |
| H9 | Phoenix Aggregator Refine | PHOENIX | 3-4 saat |
| H10+ | Chiron Learning (50+ trade sonrasi) | CHIRON | 8-10 saat |

**Toplam:** 30-40 saat, 12 hafta

---

## 16. Paper -> Micro-Live -> Live Gate Sistemi

### 16.1 Gate Felsefesi

Hicbir asamaya kanitlanmadan gecilemez. Her gate'in sayisal gecis kriteri var.

### 16.2 Gate A: Paper -> Micro-Live

| Metrik | Gecis Esigi | Basarisizlik | Kaynak |
|--------|-------------|-------------|--------|
| Max Drawdown | <= %6.0 (30 gun rolling) | > %6.0 | heartbeat.json, weekly_audit |
| Uptime | >= %99.0 | < %99.0 | status.log |
| Slippage | median <= 6 bps, p95 <= 12 bps | Ust sinir asilirsa | trades.csv |
| Hata Orani | <= %0.20 bar basina | > %0.20 | rejects.csv |
| Trade Sayisi | >= 200 gecerli paper trade | < 200 | trades.csv |
| Drift | <= 10 bps median | > 10 bps | signal_audit |

**Promosyon Kurali:** Tum metrikler **2 ardisik haftalik review'da** gecmeli.

### 16.3 Gate B: Micro-Live -> Live

| Metrik | Gecis Esigi | Basarisizlik | Kaynak |
|--------|-------------|-------------|--------|
| Max Drawdown | <= %4.0 (45 gun rolling) | > %4.0 | broker equity |
| Uptime | >= %99.5 | < %99.5 | heartbeat |
| Slippage Delta | median <= +4 bps, p95 <= +10 bps | Ust sinir | model vs live fills |
| Hata Orani | <= %0.10 kritik hata/bar | > %0.10 | rejects/errors |
| Trade Sayisi | >= 100 micro-live fill | < 100 | micro-live trades.csv |
| Drift | paper vs micro-live <= %15 relative | > %15 | paired-run drift |

**Promosyon Kurali:** Tum metrikler pass + kill-switch hicbir zaman `HARD/HALT`'da 1 cycle'dan fazla kalmamis olmali.

### 16.4 Gate C: Live Scale-Up (Stage-1 -> Stage-2)

| Metrik | Gecis Esigi | Kaynak |
|--------|-------------|--------|
| 90 gun Max DD | <= %5.0 | live equity curve |
| Calisma Stabilitesi | >= %99.7 | heartbeat + supervisor |
| Slippage Stabilitesi | p95 <= 12 bps | fills vs model |
| Incident Rate | 0 cozulmemis kritik incident | incident log |
| Trade Throughput | >= 250 fill / 90 gun | trades.csv |
| Drift Stabilitesi | aylik trend artmayan | aylik drift paketi |

### 16.5 Stage Progression Timeline

```
Paper Trading (3+ ay)
    |
    v  Gate A Pass
Micro-Live (3+ ay, max $100 risk)
    |
    v  Gate B Pass  
Live Stage-1 (3+ ay, conservative risk)
    |
    v  Gate C Pass
Live Stage-2 (olceklendirme)
    |
    v  90 gun daha stability
Full Scale (portfolio diversifikasyonu)
```

### 16.6 Risk Profili Progresyonu

| Parametre | Paper | Micro-Live | Live S1 | Live S2 |
|-----------|-------|-----------|---------|---------|
| `dailyLossCap` | %3.0 | %2.0 | %1.5 | %1.0 |
| `maxRiskPerTrade` | %1.0 | %0.50 | %0.35 | %0.25 |
| `maxConcurrentPos` | 3 | 2 | 2 | 3 |
| `minCashReserve` | %10 | %20 | %25 | %20 |

---

## 17. Risk Yonetimi: "Iron Risk" Detay

### 17.1 Iron Risk Felsefesi

> "Hayatta kalma > Kar. %50 kaybedersen, sifira donmek icin %100 kazanman lazim."

Risk yonetimi sistemin **cekirdegine** kodlanir. Bypass edilemez.

### 17.2 5 Katmanli Risk Hiyerarsisi

```
Katman 1: POZISYON RISKI
  - Her trade'de stop-loss (zorunlu)
  - Maks sermayenin %1-2'si pozisyon basina
  - ATR bazli dinamik boyutlandirma

Katman 2: STRATEJI RISKI
  - Strateji basina maks DD: %10
  - Track record'a gore alokasyon
  - Dusuk performansta otomatik azaltma

Katman 3: PORTFOLYO RISKI
  - Toplam maks DD: %15
  - Korelasyon izleme
  - Sektor/varlik diversifikasyonu

Katman 4: OPERASYONEL RISK
  - Sistem sagligi izleme
  - Failover proseduru
  - Manuel override yetkinligi

Katman 5: VAROLUSSEL RISK
  - Kill-switch (tum trading'i durdur)
  - Sermaye cekme tetikleyicisi
  - Tam sistem kapatma proseduru
```

### 17.3 Pozisyon Boyutlandirma Formulu

```
Position Size = (Hesap * Risk%) / (ATR * 1.5)

Ornek:
  Hesap = $10,000
  Risk = %1 = $100
  ATR = $500
  Stop Distance = $500 * 1.5 = $750
  Position Size = $100 / $750 = 0.133 BTC

Kural: Position Size asla hesabin %20'sinden fazla olamaz
```

**Prensip:** Volatil piyasada daha kucuk pozisyon, sakin piyasada daha buyuk pozisyon.

### 17.4 Korelasyon Kontrol

- BTC-ETH korelasyonu > 0.7 ise: her iki pozisyonu `(1 - corr/2)` ile carp
- Ornek: corr = 0.9 -> scale = 0.55 -> her pozisyon neredeyse yariya iner
- Amac: Birbirine bagli varliklarda cift risk almamak

### 17.5 Kill-Switch Protokolu

| Tetikleyici | Level | Aksiyon |
|-------------|-------|---------|
| Gunluk kayip > %3 | `SOFT` | Yeni giris durdur, mevcut pozisyonlar devam |
| Gunluk kayip > %5 | `HARD` | Tum yeni islemler durdur |
| Toplam DD > %10 | `HALT` | Tum pozisyonlari kapat, 24 saat sogurum |
| 5 ardisik kayip | `SOFT` | 30 dk yeni giris yok |
| Sistem hatasi | `HARD` | Alert + inceleme bekle |
| Manuel tetik | `HALT` | Tam durdurma, manuel restart gerekir |

### 17.6 Kill-Switch Sonrasi Recovery

1. `SOFT` recovery: Otomatik, sonraki bar'da normal devam
2. `HARD` recovery: 12 saat paper-only zorunlu
3. `HALT` recovery: Manuel restart + incident raporu zorunlu

### 17.7 Cooldown Kurallari

| Kural | Deger |
|-------|-------|
| Loss streak cooldown | 3 ardisik kayip -> 30 dk pause |
| Yuksek volatilite cooldown | Slippage p95 esik asarsa -> 15 dk pause |
| Post-kill-switch cooldown | HARD'dan recovery -> 12 saat paper-only |
| SOFT selective mode | Yalniz yuksek conviction giris, %25-40 normal boyut |

---

## 18. Alpha Factory & Arastirma Pipeline'i

### 18.1 Surec

```
Veri Golu -> Factor Lab -> Walk-Forward -> Paper Soak -> Production
     |            |              |              |              |
  Ingest:    Test 100+      Her Pazar:      30+ gun        Mezun
  OHLCV +    sinyal         Son 6 ay        paper          strateji
  Orderbook  candidate      uzerinde        trading
  + Twitter  IC > 0.05      retrain         Paper ~
  + Whale    survivors      Son 2 hafta     Backtest
                            unseen test
```

### 18.2 Factor Lab

Her hafta 100+ sinyal adayini test eden otomatik pipeline:

- Girdiler: Teknik (RSI, MACD, BB, Stoch, ADX, OBV), On-chain (NVT, MVRV, Exchange Reserve), Sentiment (Fear & Greed, LLM Score), Microstructure (OBI, Volume Delta), Cross-asset (BTC Dominance, DXY, SPY corr)
- Degerlendirme: IC (Information Coefficient) hesapla, IC > 0.05 olanlari promote et
- Hit Rate: Faktor yonu ile gelecek getiri yonunun eslestigi oran

### 18.3 Walk-Forward Optimizer

```
Her Pazar:
1. Son 6 ayin verisinde parametreleri optimize et
2. Son 2 haftalik (gorunmeyen) veride test et
3. Verimli ise -> config.yaml'i guncelle
4. Verimli degilse -> mevcut config'i koru
```

### 18.4 Arastirma Ritmi

| Frekans | Aktivite |
|---------|----------|
| Gunluk | Telemetri inceleme, anomali taramasi |
| Haftalik | Performans review, factor screening |
| Aylik | Strateji retrospektifi, yeni hipotez |
| Ceyreklik | Mimari review, teknik borc degerlendirmesi |

### 18.5 GPU-Hizlandirilmis Feature Engineering

Beast'in RTX A3000M'i ile:
- 100+ teknik indikatoru 5 yillik 1m veri uzerinde saniyeler icinde hesapla (cuDF / RAPIDS)
- XGBoost/LightGBM modellerini GPU'da egit
- Lokal LLM (Ollama Mistral/Llama3) ile zero-cost sentiment analizi
- 16 paralel multiprocessing ile optimize_hydra.py tipi grid search

---

## 19. 4 Yillik Master Plan Ozeti (2026-2030)

### 19.1 Era 0: Foundation (2026 H1)
- **Sermaye:** $30 -> $500
- **Mod:** Paper + backtest
- **Basari:** 12M walk-forward pozitif beklenti, DD < %15, 30 gun kesintisiz calisma
- **Yapma:** Canli para yatirma, getiri optimize etme

### 19.2 Era 1: Proof (2026 H2)
- **Sermaye:** $500 -> $2,000
- **Mod:** Paper 24/7 (gercek zamanli veri ile)
- **Basari:** 6 ay kesintisiz paper, Sharpe > 0.5, DD < %12
- **Aktivite:** Haftalik performans review, aylik strateji retrospektifi

### 19.3 Era 2: Pilot (2027)
- **Sermaye:** $2,000 -> $10,000
- **Mod:** Kucuk canli + paper genisleme
- **Basari:** 12 ay canli (blow-up yok), pozitif getiri, DD < %10, ikinci varlik sinifi
- **Risk:** Trade basina maks %1, gunluk %5 hard stop

### 19.4 Era 3: Scale (2028)
- **Sermaye:** $10,000 -> $50,000
- **Mod:** Multi-strateji, multi-asset
- **Basari:** 3+ strateji pozitif, Portfolio Sharpe > 0.8, DD < %8
- **Yeni:** Strateji alokasyon motoru, rejim tespiti cross-asset, ML feedback loop v1

### 19.5 Era 4: Professional (2029)
- **Sermaye:** $50,000 -> $250,000
- **Mod:** Kurumsal seviye operasyon
- **Basari:** 3+ yillik denetlenebilir track record, DD < %6, Uptime > %99.5
- **Degerlendir:** Dis sermaye (arkadaslar/aile), yasal yapi, sigorta

### 19.6 Era 5: Maturity (2030+)
- **Sermaye:** $250,000+
- **Mod:** Otonom bilesik makine
- **Karakter:** Minimal mudahale, arastirma pipeline'indan yeni stratejiler, basarisiz stratejiler otomatik emekli, operator rolu gozlem

### 19.7 Her Gun Sorun: "Sistem bugun hayatta kaldi mi?"

```
Evet -> Bilesikle.
Hayir -> Nedenini ogren.
Tum oyun bu.
```

---

## 20. Basarisizlik Modlari ve Onleme Cercevesi

### 20.1 Argus Nasil Olur?

| Mod | Olasilik | Etki | Onleme |
|-----|----------|------|--------|
| **Blow-up (Buyuk Kayip)** | Orta | Olumcul | Hard stop, kill-switch, DD limit |
| **Yavas Kanama** | Yuksek | Olumcul | Duzenli review, strateji emekliligi |
| **Teknik Ariza** | Orta | Yuksek | Monitoring, redundancy, backup |
| **Duygusal Override** | Yuksek | Yuksek | Otomasyon, kurallar, disiplin |
| **Regulasyon** | Dusuk | Yuksek | Uyum farkindaligi, yasal yapi |
| **Rejim Degisimi** | Yuksek | Orta | Diversifikasyon, rejim tespiti |
| **Tukenmislik** | Yuksek | Yuksek | Otomasyon, surdurulebilir tempo |
| **Asiri Muhendislik** | Orta | Orta | KISS prensibi, hizli ship |
| **Yetersiz Muhendislik** | Orta | Yuksek | Test, validasyon, kalite |

### 20.2 Onleme Cercevesi

**Teknik Arizalar:**
- Otomatik test suite (pytest), CI/CD pipeline
- Monitoring + alerting, Rollback yetkinligi

**Trading Basarisizliklari:**
- Pozisyon limitleri, Stop-loss (zorunlu)
- Drawdown korumalari, Kill-switch

**Insan Basarisizliklari:**
- Otomasyon > Manuel
- Kurallar > Takdir
- Dokumantasyon > Hafiza
- Review > Guven

**Stratejik Basarisizliklar:**
- Duzenli retrospektif, Dis geri bildirim
- Pivot istekliligi, Kotu stratejileri erken oldur

### 20.3 Incident Drill (3 Ayda Bir)

**Prosedur:**
1. Anomali simule et (stale heartbeat / error spike)
2. Alert'in ateslendigini dogrula
3. Triage: `soak_status.sh` + `status_reader.py`
4. Containment: Kill-switch seviyesini dogrula
5. Recovery: Restart + heartbeat dogrulama
6. Postmortem: Incident template + kok neden + aksiyon

---

## 21. Hydra / Argo / Titan: Yeni Strateji Planlari

### 21.1 HYDRA SCALP: Dusuk Volatilite Scalper

**Objective:** Dusuk volatilite rejimlerinde karli kucuk scalplar.
**Timeframe:** 5m ve 15m
**Pairler:** Yalniz yuksek likidite (BTC, ETH, SOL)

**Alpha Faktorleri:**
1. **Bollinger Band Mean Reversion:** Fiyat alt banda dokunur + ADX < 25 + RSI < 30
2. **Orderbook Imbalance (OBI):** `(BidVol - AskVol) / (BidVol + AskVol) > 0.2`
3. **Volume Delta:** Son 3 mum'da alis hacmi > satis hacmi

**Execution:**
- Order Type: LIMIT (Maker) at BestBid
- Chase: 10 sn icinde dolmazsa, reprice (maks 3 deneme)
- TP: Band Basis (SMA 20) veya +%0.4
- SL: 1.5x ATR entry altinda veya -%0.3 sabit

**Gate:** Paper soak min 200 trade, DD <= %3, Win Rate >= %55, PF >= 1.3

**Dosya Plani:** `argus_py/strategies/hydra.py`

---

### 21.2 ARGO ARBITRAGE: Funding Rate Farmer

**Objective:** Borsalar arasi funding rate farki veya spot-futures basis trade ile risksiz spread yakalama.

**Strateji Turleri:**
1. **Funding Rate Arb:** Pozitif funding'de spot long + perp short -> funding geliri topla
2. **Cross-Exchange Spread:** Binance vs Bybit fiyat farki > fee+slippage ise simultane al/sat
3. **Basis Trade:** Spot vs quarterly futures spread

**Esik:** Min funding threshold = %0.05 per 8h = yillik ~%18.25

**Mantik:**
- Pozitif funding: short perp + long spot -> her 8 saatte funding geliri al
- Negatif funding: long perp + short spot (margin gerekir)
- Delta-neutral olmali (net piyasa riski sifir)

**Risk:** Market riski yok (delta-neutral), ancak execution risk ve likidite riski var.

**Gate:** 6 ay paper soak, pozitif toplam getiri, maks DD < %2

**Dosya Plani:** `argus_py/strategies/argo.py`

---

### 21.3 TITAN DCA: Akilli Ortalama Maliyet

**Objective:** Gunluk otomatik $X alim, ama **yalniz** rejim `BEAR_TREND` **degilse**.

**Mantik:**
- Normal DCA: her gun $10 al (koru)
- Akilli DCA: dip'lerde daha cok al, tepe'lerde daha az al
- RSI < 30 -> 2x multiplier (dip'te 2 kat al)
- RSI < 40 -> 1.5x multiplier
- RSI > 70 -> 0.5x multiplier (pahali'da yarim al)
- ATH'den %30+ dususte -> ek 1.5x bonus
- Rejim = BEAR_TREND -> 0 (hic alma, bekle)

**Gate:** 6 ay paper soak, toplam getiri > basit DCA getirisi, DD < %15

**Dosya Plani:** `argus_py/strategies/titan.py`

---

### 21.4 Yeni Strateji Implementasyon Takvimi

| Strateji | Baslangic | Tahmini Sure | Bagimlilik |
|----------|-----------|-------------|------------|
| Hydra Scalp | Rejim motoru hazir oldugunda | 15 saat | Regime Classifier + OBI veri |
| Argo Arb | Multi-exchange connector hazir | 20 saat | REF-003 (hummingbot pattern) |
| Titan DCA | Rejim motoru hazir | 8 saat | Regime Classifier |
| TopHunter Short | Simdiden spec mevcut | 10 saat | Pivot detection |

**Toplam Yeni Strateji Eforu:** ~53 saat

---

# EXECUTION PRIORITY MATRIX

| Oncelik | Gorev | Tahmini Sure | Bagimlilik |
|---------|-------|-------------|------------|
| P0 | Rejim Motoru (Section 14) | 10 saat | Veri API'leri |
| P0 | Paper 24/7 Stabilite (Section 11) | 8 saat | PM2 + monitoring |
| P1 | Orion Enhancement (7 motor, Section 15) | 6 saat | Mevcut kod |
| P1 | Gate A Metrik Altyapisi (Section 16) | 6 saat | Telemetri |
| P1 | Iron Risk Kernel (Section 17) | 8 saat | Kill-switch mevcut |
| P2 | Hydra Scalp Stratejisi (Section 21) | 15 saat | P0 rejim motoru |
| P2 | Aether-C Macro (Section 15) | 8 saat | API entegrasyonu |
| P2 | Titan DCA (Section 21) | 8 saat | P0 rejim motoru |
| P3 | Hermes-C Sentiment (Section 15) | 6 saat | RSS + LLM |
| P3 | Atlas-C On-Chain (Section 15) | 8 saat | Glassnode/CoinGecko |
| P3 | Argo Arbitrage (Section 21) | 20 saat | Multi-exchange |
| P4 | Chiron Learning (Section 15) | 10 saat | 50+ trade |
| P4 | Factor Lab Automasyonu (Section 18) | 12 saat | Feature store |

**Toplam Tahmini Efor:** ~125 saat (~3 ay part-time, hafta 10 saat)

---

---

## 22. GitHub Repo Arastirmasi: Implement Edilecek Ozellikler ve Motorlar

### 22.1 Arastirilan Repolar ve Kategorileri

Asagidaki acik kaynakli repolar incelendi ve Argus'a uygulanabilir ozellikler cikarildi:

| Kategori | Repo | GitHub | Yildiz | Uygunluk |
|----------|------|--------|--------|----------|
| **Quant Platform** | Microsoft Qlib | microsoft/qlib | 17k+ | Cok Yuksek |
| **Quant Platform** | Goldman Sachs gs-quant | goldmansachs/gs-quant | 3k+ | Yuksek |
| **Trading Engine** | Freqtrade | freqtrade/freqtrade | 30k+ | Cok Yuksek |
| **Trading Engine** | Jesse | jesse-ai/jesse | 6k+ | Yuksek |
| **Trading Engine** | NautilusTrader | nautilus-trader/nautilus_trader | 2k+ | Orta |
| **RL Trading** | FinRL | AI4Finance-LLC/FinRL | 10k+ | Yuksek |
| **ML Finance** | mlfinlab (Hudson Thames) | hudson-and-thames/mlfinlab | 4k+ | Cok Yuksek |
| **Portfolio Opt** | PyPortfolioOpt | robertmartin8/PyPortfolioOpt | 4k+ | Yuksek |
| **Portfolio Opt** | skfolio | skfolio/skfolio | 1k+ | Orta |
| **Backtesting** | Backtrader | mementum/backtrader | 14k+ | Yuksek |
| **Research Terminal** | OpenBB | OpenBB-finance/OpenBBTerminal | 30k+ | Orta |
| **Time Series** | Amazon Chronos | amazon-science/chronos-forecasting | 3k+ | Cok Yuksek |
| **GPU Finance** | tf-quant-finance | google/tf-quant-finance | 4k+ | Orta |
| **Crypto Bot** | OctoBot | Drakkar-Software/OctoBot | 3k+ | Orta |

### 22.2 Freqtrade'den Alinacak Ozellikler

Freqtrade dunyanin en populer acik kaynak kripto trading botudur. Asagidaki ozellikler Argus'a implement edilecek:

| # | Ozellik | Freqtrade Kaynagi | Argus Entegrasyonu | Oncelik |
|---|---------|-------------------|-------------------|---------|
| 1 | **Hyperopt (Optuna)** | `freqtrade/optimize/` | Strateji parametre optimizasyonu, Bayesian search | P0 |
| 2 | **Pairlist Yonetimi** | `freqtrade/plugins/pairlist/` | Dinamik coin secimi (volume, change%, volatility) | P0 |
| 3 | **FreqAI Entegrasyonu** | `freqtrade/freqai/` | ML modellerin strateji icine entegrasyonu | P1 |
| 4 | **Recursive Analysis** | `freqtrade/data/btanalysis.py` | Backtestlerde lookahead bias tespiti | P1 |
| 5 | **Custom ROI & Trailing** | `freqtrade/strategy/` | Trade bazli dinamik ROI tablosu | P1 |
| 6 | **Telegram Bot** | `freqtrade/rpc/telegram/` | Gelismis Telegram kontrol (force buy/sell, status) | P2 |
| 7 | **Plot Annotations** | `freqtrade/plot/` | Trade giris/cikis chart annotasyonlari | P2 |
| 8 | **Data Format (Feather)** | `freqtrade/data/converter.py` | JSON yerine Feather/Parquet (10x hiz) | P1 |
| 9 | **Sharpe/Sortino/Calmar** | FreqUI live metrics | Dashboard'da canli metrik gosterimi | P1 |

### 22.3 Microsoft Qlib'den Alinacak Ozellikler

Qlib, Microsoft'un AI-odakli yatirim platformudur. 40+ SOTA model icerir:

| # | Ozellik | Qlib Modulu | Argus Kullanimi | Oncelik |
|---|---------|-------------|-----------------|---------|
| 1 | **Alpha Factor Pipeline** | `qlib/contrib/model/` | Factor-bazli sinyal uretimi (IC>0.05) | P1 |
| 2 | **LightGBM Entegrasyonu** | `qlib/contrib/model/gbdt.py` | Hizli feature importance + alpha prediction | P0 |
| 3 | **Temporal Fusion Transformer** | `qlib/contrib/model/pytorch_tft.py` | Multi-horizon tahmin (1h, 4h, 1d) | P2 |
| 4 | **LSTM/GRU Models** | `qlib/contrib/model/pytorch_lstm.py` | Sequence-bazli fiyat pattern tanima | P1 |
| 5 | **DataHandler & Cache** | `qlib/data/` | 2-seviye cache (memory+disk), hizli data erisim | P1 |
| 6 | **Walk-Forward Validation** | `qlib/workflow/` | Rolling window backtesting, concept drift tespiti | P0 |
| 7 | **IC (Information Coeff.)** | `qlib/contrib/evaluate/` | Faktor kalite olcumu, alpha decay takibi | P1 |
| 8 | **qrun CLI** | `qlib/workflow/cli.py` | Tek config ile end-to-end pipeline calistirma | P2 |

### 22.4 mlfinlab'dan Alinacak Ozellikler (Marcos Lopez de Prado)

"Advances in Financial Machine Learning" kitabindan profesyonel quant teknikleri:

| # | Ozellik | Aciklama | Neden Onemli | Oncelik |
|---|---------|----------|-------------|---------|
| 1 | **Triple Barrier Method** | Take-profit + stop-loss + time-limit labels | Gercekci ML etiketleme, fixed-horizon'dan 3x iyi | P0 |
| 2 | **Meta-Labeling** | 2. model ile pozisyon boyutlandirma | Win rate %55→%65 artirma potansiyeli | P0 |
| 3 | **Fractional Differentiation** | Stationarity + memory korunarak feature eng. | ML modellere stasyoner ama bilgi kaybisiz veri | P1 |
| 4 | **CUSUM Filter** | Event-driven sampling | Noise azaltma, anlamli eventlere odaklanma | P1 |
| 5 | **Entropy Features** | Shannon, plug-in, Lempel-Ziv entropy | Piyasa bilgi yogunlugu olcumu | P2 |
| 6 | **Bet Sizing** | Kelly criterion + meta-label sizing | Optimal pozisyon boyutu (overleveraj onleme) | P1 |
| 7 | **Feature Importance** | MDI, MDA, SFI yontemleri | Overfitting tespiti, gercek vs sahte alpha | P1 |
| 8 | **Structural Breaks** | SADF, Chow test | Rejim degisikligi erken tespit | P2 |

### 22.5 FinRL'den Alinacak Ozellikler (Deep RL Trading)

| # | Ozellik | FinRL Modulu | Argus Kullanimi | Oncelik |
|---|---------|-------------|-----------------|---------|
| 1 | **PPO Agent** | `finrl/agents/stablebaselines3/` | En stabil RL ajan, kripto portfoy yonetimi | P1 |
| 2 | **A2C Agent** | Ayni | PPO ile ensemble stratejide kullanim | P2 |
| 3 | **Ensemble Strategy** | `finrl/meta/env_stock_trading/` | PPO+A2C+DDPG secimi (en iyi Sharpe'i sec) | P2 |
| 4 | **Crypto Env** | `FinRL_Crypto/` | BTC, ETH, top-10 altcoin icin gym ortami | P1 |
| 5 | **Overfitting Kontrolu** | Walk-forward + cross-val | Kripto RL'de overfitting %40 azaltma | P1 |
| 6 | **Paper Trading Mode** | `finrl/meta/paper_trading/` | RL ajanin paper trade ile validasyonu | P1 |

### 22.6 PyPortfolioOpt & skfolio'dan Alinacak Ozellikler

| # | Ozellik | Aciklama | Argus Kullanimi | Oncelik |
|---|---------|----------|-----------------|---------|
| 1 | **Efficient Frontier** | Markowitz mean-variance optimization | Multi-coin optimal agirlik hesabi | P1 |
| 2 | **Black-Litterman** | Goruslerle piyasa dengesini birlestirme | Rejim motorundan gelen gorusleri portfoye yansitma | P2 |
| 3 | **HRP (Hierarchical Risk Parity)** | Korelasyon-bazli hierarchical clustering | Covariance matrix tersine gerek yok, robust | P1 |
| 4 | **CVaR Optimization** | Conditional Value at Risk minimize | Tail risk minimizasyonu (crash koruma) | P1 |
| 5 | **Risk Budgeting** | Her stratejiye risk butcesi | All-weather portfoy rejim-bazli risk dagitimi | P1 |

### 22.7 Diger Repolardan Alinacak Ozellikler

| Repo | Ozellik | Argus Kullanimi | Oncelik |
|------|---------|-----------------|---------|
| **Backtrader** | Cerebro multi-strategy engine | Birden fazla stratejiyi paralel calistirma | P2 |
| **Jesse** | AI-powered optimize (Optuna+GP) | Bayesian + Gaussian Process hyperopt | P2 |
| **NautilusTrader** | Event-driven architecture (Rust core) | Kritik yollarda Rust/Cython performans | P3 |
| **OpenBB** | Macro data aggregation | Fed, ECB, TCMB verisi tek API'den | P2 |
| **tf-quant-finance** | GPU Monte Carlo simulations | Risk senaryolari GPU'da 100x hizli | P2 |
| **OctoBot** | Strategy marketplace pattern | Strateji paylasim/import sistemi | P3 |

---

## 23. ML/AI Motoru: RTX A3000M Uzerinde Model Plani

### 23.1 Donanim Kisitlari ve Firsatlar

| Bilesen | Deger | ML Etkisi |
|---------|-------|-----------|
| **GPU** | RTX A3000M (6GB VRAM) | ~300M parametreye kadar FP16 training |
| **RAM** | 32 GB DDR4 | LightGBM/XGBoost icin yeterli, buyuk datasetler OK |
| **CPU** | i7-11800H (8C/16T) | Scikit-learn, feature eng, data processing icin guclu |
| **Disk** | SSD (varsayim) | Data I/O darbogazsiz |

### 23.2 VRAM Butcesi ve Model Sinirlari

6GB VRAM ile neler yapilabilir:

| Model Tipi | Parametre | VRAM (FP16) | Uygun mu? |
|------------|-----------|-------------|-----------|
| LightGBM / XGBoost | N/A (CPU) | 0 GB | EVET - CPU'da calisir |
| LSTM (2 layer, 128 hidden) | ~500K | 0.2 GB | EVET |
| GRU (2 layer, 256 hidden) | ~1M | 0.3 GB | EVET |
| Temporal Fusion Transformer | ~5M | 0.5 GB | EVET |
| **Chronos-Bolt Tiny** | **9M** | **0.02 GB** | **EVET - IDEAL** |
| **Chronos-Bolt Mini** | **21M** | **0.04 GB** | **EVET - IDEAL** |
| **Chronos-Bolt Small** | **48M** | **0.1 GB** | **EVET - IDEAL** |
| **Chronos-Bolt Base** | **205M** | **0.4 GB** | **EVET** |
| Chronos-T5 Large | 710M | ~1.4 GB | EVET (tight) |
| FinRL PPO Agent | ~2M | 0.3 GB | EVET |
| BERT-tiny (sentiment) | 4M | 0.1 GB | EVET |
| DistilBERT (sentiment) | 66M | 0.2 GB | EVET |

**Sonuc:** 6GB VRAM ile Argus'un ihtiyac duydugu TUM modeller rahatca egitilip calistirilabilir.

### 23.3 Amazon Chronos Entegrasyonu (Oncelik: P0)

Chronos, Amazon'un pretrained zaman serisi tahmin modelidir. Argus icin **en kritik ML bileseni** olacak.

#### Neden Chronos?

| Avantaj | Aciklama |
|---------|----------|
| **Zero-shot** | Egitim olmadan direkt tahmin yapabilir |
| **Probabilistic** | Tek nokta degil, olasilik dagılımı verir (confidence interval) |
| **Pretrained** | Dev veri setleriyle on-egitimli, fine-tune opsiyonel |
| **Tiny VRAM** | Bolt-Base 205M bile sadece 0.4GB VRAM |
| **250x Hizli** | Chronos-Bolt, orijinal Chronos'tan 250x daha hizli |

#### Chronos Kullanim Plani

| Kullanim | Model | Input | Output | Siklik |
|----------|-------|-------|--------|--------|
| **Fiyat Tahmini** | Chronos-Bolt Base | Son 512 candle (1h) | Sonraki 24 candle olasilik dagılımı | Her saat |
| **Volatilite Tahmini** | Chronos-Bolt Small | ATR/volatilite serisi | 12 saat volatilite band | Her 4 saat |
| **Rejim Ongorusu** | Chronos-Bolt Mini | Rejim gosterge serisi | Rejim degisim olasiligi | Her 4 saat |
| **Volume Profil** | Chronos-Bolt Tiny | Hacim zaman serisi | Volume spike olasiligi | Her saat |

#### Implementasyon Adimlari

```
1. pip install git+https://github.com/amazon-science/chronos-forecasting.git
2. from chronos import ChronosPipeline
3. pipeline = ChronosPipeline.from_pretrained("amazon/chronos-bolt-base")
4. forecast = pipeline.predict(context_tensor, prediction_length=24)
5. median = forecast.median(dim=1)       # nokta tahmin
6. lower = forecast.quantile(0.1, dim=1) # %10 alt sinir
7. upper = forecast.quantile(0.9, dim=1) # %90 ust sinir
```

#### Chronos Fine-Tuning Plani

| Asama | Veri | Yontem | Hedef |
|-------|------|--------|-------|
| Faz 1 | BTC/ETH 2020-2026 1h candles | Zero-shot (fine-tune yok) | Baseline performans |
| Faz 2 | Top-20 kripto, 1h+4h candles | LoRA fine-tune (VRAM dostu) | %10-20 MAPE iyilesmesi |
| Faz 3 | Multi-asset (kripto + hisse) | Full fine-tune | Cross-asset transfer learning |

### 23.4 LightGBM + XGBoost Ensemble (Oncelik: P0)

CPU-bazli, hizli, yorumlanabilir modeller. Argus'un "ana beyni" olacak:

| Ozellik | Detay |
|---------|-------|
| **Task** | Sonraki 1h/4h/1d yon tahmini (UP/DOWN/NEUTRAL) |
| **Features (100+)** | RSI, MACD, BB, ATR, OBV, VWAP, funding rate, open interest, Chronos output, rejim skoru |
| **Labeling** | Triple Barrier Method (mlfinlab) |
| **Meta-Label** | 2. model pozisyon boyutlandirma |
| **Training** | Walk-forward (son 90 gun train, 30 gun test, 7 gun rolling) |
| **Inference** | Her candle kapanisinda (~1 saniye CPU) |
| **Feature Importance** | MDI + MDA → otomatik feature selection |

### 23.5 LSTM/GRU Sequence Model (Oncelik: P1)

| Parametre | Deger |
|-----------|-------|
| **Mimari** | 2-layer Bi-LSTM, 128 hidden units |
| **Input** | Son 168 candle (7 gun, 1h), 30+ feature |
| **Output** | Sonraki 4h fiyat yonu + confidence |
| **Training** | GPU (RTX A3000M), ~15 dk/epoch |
| **Batch Size** | 64 (VRAM rahat) |
| **Regularization** | Dropout 0.3, early stopping |
| **Framework** | PyTorch |

### 23.6 FinRL Reinforcement Learning Agent (Oncelik: P2)

| Parametre | Deger |
|-----------|-------|
| **Algoritma** | PPO (birincil), A2C (yedek) |
| **Ortam** | Custom CryptoEnv (Gymnasium) |
| **State Space** | Fiyat, hacim, teknik ind., portfoy durumu, Chronos tahmini |
| **Action Space** | Continuous [0,1] → her coin icin allocation |
| **Reward** | Risk-adjusted return (Sharpe-bazli) |
| **Training** | 100K step, ~2 saat GPU |
| **Ensemble** | PPO + A2C → 30 gunluk rolling window'da en iyi Sharpe'i sec |

### 23.7 Sentiment Analiz Modeli (Oncelik: P2)

| Parametre | Deger |
|-----------|-------|
| **Model** | DistilBERT fine-tuned on crypto news |
| **VRAM** | 0.2 GB |
| **Input** | Crypto Twitter, Reddit, haberler |
| **Output** | Sentiment skoru [-1, +1] |
| **Kaynak** | CryptoPanic API, Twitter API, Reddit API |
| **Siklik** | Her 15 dk sentiment guncelleme |
| **Entegrasyon** | LightGBM feature olarak + rejim motoruna input |

### 23.8 ML Model Pipeline Mimarisi

```
                    ┌─────────────────┐
                    │  DATA PIPELINE  │
                    │ OHLCV + OnChain │
                    │ + Sentiment     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ FEATURE ENGINE  │
                    │ 100+ features   │
                    │ Triple Barrier  │
                    │ Frac. Diff.     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───────┐ ┌───▼────────┐ ┌───▼──────────┐
     │   LightGBM +   │ │  Chronos   │ │  LSTM/GRU    │
     │   XGBoost      │ │  Bolt Base │ │  Sequence    │
     │   (CPU, <1s)   │ │  (GPU,<2s) │ │  (GPU, <3s)  │
     └────────┬───────┘ └───┬────────┘ └───┬──────────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │  META-LABELER   │
                    │  Ensemble Vote  │
                    │  + Bet Sizing   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  DECISION       │
                    │  BUY/SELL/HOLD  │
                    │  + Position Size│
                    └─────────────────┘
```

### 23.9 Model Performans Hedefleri

| Model | Metrik | Hedef | Minimum |
|-------|--------|-------|---------|
| LightGBM (yon) | Accuracy | %60 | %55 |
| LightGBM (yon) | F1-Score | 0.58 | 0.52 |
| Chronos (fiyat) | MAPE | %3 (1h) | %5 |
| Chronos (fiyat) | CRPS | <0.05 | <0.08 |
| LSTM (yon) | Accuracy | %58 | %53 |
| Ensemble | Accuracy | %63 | %57 |
| Meta-Labeler | Precision | %70 | %60 |
| Sentiment | Correlation w/ return | 0.15 | 0.08 |
| PPO Agent | Sharpe Ratio | 1.5 | 1.0 |

### 23.10 ML Training Takvimi

| Hafta | Gorev | Cikti |
|-------|-------|-------|
| Hafta 1 | Feature pipeline + Triple Barrier | Labeled dataset hazir |
| Hafta 2 | LightGBM baseline + walk-forward | Baseline Accuracy raporu |
| Hafta 3 | Chronos-Bolt zero-shot test | MAPE/CRPS benchmark |
| Hafta 4 | LSTM training + hyperopt | Sequence model hazir |
| Hafta 5 | Ensemble + Meta-labeling | Kombine model |
| Hafta 6 | Chronos fine-tune (LoRA) | Iyilestirilmis tahmin |
| Hafta 7 | FinRL PPO agent | RL agent paper trade |
| Hafta 8 | Sentiment model | NLP pipeline |
| Hafta 9-10 | Full integration + paper test | End-to-end ML pipeline |

---

## 24. Mac'ten Windows'a Proje Tasima Plani

### 24.1 Neden Tasima Gerekli?

| Konu | Mac (Mevcut) | Windows Laptop (Hedef) |
|------|-------------|----------------------|
| **GPU** | Yok (Apple Silicon veya Intel iGPU) | RTX A3000M 6GB CUDA |
| **ML Training** | Yavas (CPU only) | 10-50x hizli (CUDA) |
| **CUDA** | Desteklenmiyor | Tam destek |
| **PyTorch GPU** | MPS (sinirli) | CUDA (tam destek) |
| **7/24 Calisma** | Uygun degil | "The Beast" - 7/24 acik kalacak |

### 24.2 Tasima Oncesi Windows Hazirlik

| Adim | Gorev | Detay |
|------|-------|-------|
| 1 | **Python 3.11+ kur** | python.org veya miniconda |
| 2 | **CUDA Toolkit 12.x kur** | NVIDIA developer sitesinden |
| 3 | **cuDNN kur** | PyTorch GPU icin gerekli |
| 4 | **Git kur** | git-scm.com |
| 5 | **VS Code kur** | Eklentiler: Python, Pylance, GitLens |
| 6 | **Node.js 18+ kur** | Dashboard/web UI icin |
| 7 | **PM2 kur** | `npm install -g pm2` (Windows servisi) |
| 8 | **WSL2 (opsiyonel)** | Linux ortami gerekirse |

### 24.3 Proje Transfer Yontemi

| Yontem | Avantaj | Dezavantaj | Oneri |
|--------|---------|------------|-------|
| **GitHub Push/Pull** | En temiz, versiyonlu | Buyuk dosyalar icin yavas | **BIRINCIL** |
| **USB/SSD Transfer** | Hizli, buyuk dosyalar OK | Versiyon takibi yok | Data dosyalari icin |
| **rsync over SSH** | Incremental, hizli | Setup gerekli | Buyuk dataset icin |

#### Onerilen Akis:

```
[MAC]                           [WINDOWS]
  |                                |
  ├── git push (kod + docs)──────>├── git clone
  |                                |
  ├── SSD ile transfer ──────────>├── data/ ve models/ klasoru
  |   (OHLCV data, trained        |
  |    models, backtest results)   |
  |                                |
  └── .env dosyasi (MANUAL) ────>└── .env (API keys, secrets)
```

### 24.4 Windows'a Ozel Ayarlar

| Konu | Mac Karsiligi | Windows Cozumu |
|------|---------------|----------------|
| Cron jobs | launchd / cron | **Task Scheduler** veya **PM2** |
| Process manager | pm2 | **PM2** (Windows destekler) |
| Shell scripts | .sh | **.bat** veya **.ps1** (PowerShell) |
| File paths | `/Users/emirhan/` | `C:\Users\emirhan\` |
| Line endings | LF | **Git: `core.autocrlf=true`** |
| Python venv | `python3 -m venv` | `python -m venv` |
| CUDA check | N/A | `nvidia-smi`, `torch.cuda.is_available()` |

### 24.5 CUDA Dogrulama Scripti

Windows'ta ilk is olarak calistirilacak:

```python
# verify_gpu.py
import torch
import sys

print(f"Python: {sys.version}")
print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")
    
    # Quick benchmark
    x = torch.randn(10000, 10000, device='cuda')
    import time
    start = time.time()
    y = x @ x
    torch.cuda.synchronize()
    print(f"10Kx10K matmul: {time.time()-start:.3f}s")
else:
    print("HATA: CUDA bulunamadi! CUDA Toolkit ve cuDNN kontrol edin.")
```

### 24.6 Tasima Checklist

| # | Gorev | Durum |
|---|-------|-------|
| 1 | Windows'ta Python 3.11 + venv olustur | ⬜ |
| 2 | CUDA 12.x + cuDNN kur | ⬜ |
| 3 | `verify_gpu.py` calistir, CUDA dogrula | ⬜ |
| 4 | GitHub'dan repo clone | ⬜ |
| 5 | `pip install -r requirements.txt` | ⬜ |
| 6 | `.env` dosyasini olustur (API keys) | ⬜ |
| 7 | Data dosyalarini SSD ile tasi | ⬜ |
| 8 | `pytest` calistir, tum testler gecsin | ⬜ |
| 9 | Paper trading baslatildi mi? | ⬜ |
| 10 | PM2 ile 7/24 servis aktif mi? | ⬜ |
| 11 | Telegram bot baglandi mi? | ⬜ |
| 12 | Chronos modeli GPU'da calisiyor mu? | ⬜ |
| 13 | LightGBM training calisiyor mu? | ⬜ |
| 14 | Monitoring dashboard aktif mi? | ⬜ |

### 24.7 Tasima Sonrasi Mac Rolu

Mac tamamen devre disi birakilmayacak:

| Mac Gorevi | Aciklama |
|------------|----------|
| **Uzaktan izleme** | SSH/Telegram ile Beast'i izleme |
| **Kod gelistirme** | VS Code + Git, push to GitHub |
| **Dokuman yazma** | Planning, strategy research |
| **Yedek erisim** | Beast cokerse Mac'ten mudahale |

---

## 25. Implementasyon Yol Haritasi ve Sprint Plani

### 25.1 Faz 0: Altyapi Tasima (Hafta 1-2)

| Gorev | Tahmini Sure | Bagimlilik |
|-------|-------------|------------|
| Windows CUDA/Python environment | 4 saat | Yok |
| GitHub repo clone + test | 2 saat | Environment |
| Data transfer (SSD) | 2 saat | Clone |
| PM2 setup + 7/24 servis | 3 saat | Clone |
| verify_gpu.py dogrulama | 1 saat | CUDA |
| **Faz 0 Toplam** | **12 saat** | |

### 25.2 Faz 1: ML Foundation (Hafta 3-6)

| Gorev | Tahmini Sure | Bagimlilik |
|-------|-------------|------------|
| Feature pipeline (100+ feature) | 12 saat | Data |
| Triple Barrier labeling (mlfinlab) | 8 saat | Feature pipeline |
| Fractional differentiation | 4 saat | Feature pipeline |
| LightGBM baseline model | 8 saat | Labels |
| Walk-forward validation framework | 10 saat | Model |
| Chronos-Bolt zero-shot integration | 6 saat | Data |
| Chronos-Bolt fine-tune (LoRA) | 8 saat | Zero-shot baseline |
| Meta-labeling model | 6 saat | LightGBM |
| Ensemble voting system | 6 saat | All models |
| **Faz 1 Toplam** | **68 saat** | |

### 25.3 Faz 2: Strateji Guclendrme (Hafta 7-10)

| Gorev | Tahmini Sure | Bagimlilik |
|-------|-------------|------------|
| Hyperopt (Optuna) entegrasyonu | 8 saat | Walk-forward |
| Dinamik Pairlist motoru | 6 saat | Data pipeline |
| PyPortfolioOpt HRP entegrasyonu | 6 saat | Multi-coin |
| CVaR optimization | 4 saat | HRP |
| LSTM/GRU sequence model | 10 saat | Feature pipeline |
| Telegram bot gelismis komutlar | 8 saat | Trading engine |
| Data format (Feather/Parquet) | 4 saat | Data pipeline |
| **Faz 2 Toplam** | **46 saat** | |

### 25.4 Faz 3: Advanced AI (Hafta 11-16)

| Gorev | Tahmini Sure | Bagimlilik |
|-------|-------------|------------|
| FinRL PPO agent | 12 saat | Gym environment |
| FinRL A2C + ensemble | 8 saat | PPO |
| Sentiment model (DistilBERT) | 10 saat | NLP data |
| Structural break detection | 6 saat | Feature pipeline |
| CUSUM event filter | 4 saat | Data pipeline |
| Feature importance (MDI/MDA) | 4 saat | LightGBM |
| Bet sizing (Kelly + meta-label) | 6 saat | Meta-labeling |
| Black-Litterman portfoy | 8 saat | Rejim motoru |
| **Faz 3 Toplam** | **58 saat** | |

### 25.5 Faz 4: Production Polish (Hafta 17-20)

| Gorev | Tahmini Sure | Bagimlilik |
|-------|-------------|------------|
| End-to-end ML pipeline CI | 8 saat | All models |
| Model monitoring & drift detection | 6 saat | Production |
| A/B test framework (model vs baseline) | 6 saat | Paper trade |
| Dashboard ML metrics panel | 8 saat | Frontend |
| Auto-retraining pipeline | 6 saat | Walk-forward |
| Incident response for ML failures | 4 saat | Monitoring |
| **Faz 4 Toplam** | **38 saat** | |

### 25.6 Toplam Efor Ozeti

| Faz | Sure | Kumulatif |
|-----|------|-----------|
| Faz 0: Altyapi Tasima | 12 saat | 12 saat |
| Faz 1: ML Foundation | 68 saat | 80 saat |
| Faz 2: Strateji Guclendirme | 46 saat | 126 saat |
| Faz 3: Advanced AI | 58 saat | 184 saat |
| Faz 4: Production Polish | 38 saat | 222 saat |
| **TOPLAM** | **222 saat** | ~5.5 ay (hafta 10 saat) |

### 25.7 Oncelik Matrisi (Ne Ilk Yapilmali?)

```
YUKSEK ETKI + DUSUK EFOR (ILKONCE YAP):
├── Chronos-Bolt zero-shot (6 saat, aninda tahmin)
├── LightGBM baseline (8 saat, hizli sonuc)
├── Triple Barrier labeling (8 saat, kalite artisi)
├── Windows CUDA setup (4 saat, GPU acilir)
└── Feather data format (4 saat, 10x hiz)

YUKSEK ETKI + YUKSEK EFOR (PLANLA):
├── Walk-forward validation (10 saat, overfitting onleme)
├── Feature pipeline 100+ (12 saat, tum modellerin temeli)
├── FinRL PPO agent (12 saat, otonom trading)
├── Chronos fine-tune (8 saat, dogruluk artisi)
└── Sentiment model (10 saat, alpha kaynagi)

DUSUK ETKI + DUSUK EFOR (FIRSATTA YAP):
├── Entropy features (4 saat)
├── CUSUM filter (4 saat)
└── Plot annotations (4 saat)

DUSUK ETKI + YUKSEK EFOR (SONRA YAP):
├── Black-Litterman (8 saat)
├── NautilusTrader Rust core (20+ saat)
└── Strategy marketplace (15+ saat)
```

---

---

## 26. ARGUS: Institutional-Grade Multi-Regime Trading System Architecture

> **Classification:** Core System Blueprint  
> **Author Role:** Senior Quant Architect + Hedge Fund CTO  
> **Design Philosophy:** Survival → Consistency → Scalability  
> **Regime Coverage:** Bull, Bear, Sideways, Chop, High Vol, Low Liquidity, News Shock, Crash, Recovery  
> **Single Rule:** Capital preservation is non-negotiable. Everything else is optimization.

---

### 26.1 Full System Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                        ARGUS MASTER ARCHITECTURE                           ║
║                   Institutional-Grade Trading System                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │                    LAYER 0: DATA PIPELINE                          │    ║
║  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │    ║
║  │  │  OHLCV   │ │ Funding  │ │  Open    │ │ Orderbook│ │ Senti-  │  │    ║
║  │  │  Multi-  │ │  Rate    │ │ Interest │ │  L2/L3   │ │  ment   │  │    ║
║  │  │ Timeframe│ │  Stream  │ │  Stream  │ │  Depth   │ │  Feed   │  │    ║
║  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬─────┘  │    ║
║  │       └──────────┬──┴───────────┬┴────────────┴───────────┘        │    ║
║  │                  ▼              ▼                                   │    ║
║  │  ┌───────────────────────────────────────────────────────────────┐  │    ║
║  │  │              FEATURE ENGINEERING ENGINE                       │  │    ║
║  │  │  Technical(100+) │ Microstructure │ Cross-Asset │ Derived     │  │    ║
║  │  │  RSI,MACD,BB,ATR │ Spread,Imbal.  │ Corr,Beta   │ FracDiff   │  │    ║
║  │  └───────────────────────────┬───────────────────────────────────┘  │    ║
║  └──────────────────────────────┼──────────────────────────────────────┘    ║
║                                 ▼                                          ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │              LAYER 1: REGIME DETECTION ENGINE (RDE)                │    ║
║  │                                                                    │    ║
║  │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │    ║
║  │   │   HMM    │  │Volatility│  │  Trend   │  │   Micro-        │  │    ║
║  │   │ Gaussian │  │Structure │  │ Filters  │  │   structure     │  │    ║
║  │   │ 8-state  │  │ GARCH    │  │ ADX+MA   │  │   Volume Prof.  │  │    ║
║  │   └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘  │    ║
║  │        └──────────┬───┴────────────┬┘                │           │    ║
║  │                   ▼                ▼                  ▼           │    ║
║  │           ┌─────────────────────────────────────────────┐        │    ║
║  │           │         REGIME CONSENSUS MODULE             │        │    ║
║  │           │  Weighted vote → regime + confidence        │        │    ║
║  │           │  Output: {regime, confidence, stability}    │        │    ║
║  │           └───────────────────┬─────────────────────────┘        │    ║
║  └───────────────────────────────┼──────────────────────────────────┘    ║
║                                  ▼                                       ║
║  ┌───────────────────────────────────────────────────────────────────┐    ║
║  │              LAYER 2: STRATEGY COUNCIL SYSTEM (SCS)               │    ║
║  │                                                                   │    ║
║  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │    ║
║  │  │  ORION   │ │ AEGEAN   │ │  ATLAS   │ │  HERMES  │ │ HELIOS │  │    ║
║  │  │  Trend   │ │ Mean-Rev │ │ Macro/   │ │ Senti-   │ │ Scalp/ │  │    ║
║  │  │  Engine  │ │  Engine  │ │  Risk    │ │  ment    │ │ Micro  │  │    ║
║  │  │          │ │          │ │  Engine  │ │  Engine  │ │ Engine │  │    ║
║  │  │ Breakout │ │ Range    │ │ Risk-On/ │ │ News NLP │ │ Spread │  │    ║
║  │  │ Momentum │ │ VWAP Rev │ │ Risk-Off │ │ Social   │ │ Liq.   │  │    ║
║  │  │ Trend FL │ │ Stat Arb │ │ Correl.  │ │ Orderfl. │ │ Fund.  │  │    ║
║  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘  │    ║
║  │       │             │            │             │           │       │    ║
║  │       ▼             ▼            ▼             ▼           ▼       │    ║
║  │  {bias, confidence, risk_score, expected_return} x 5 engines      │    ║
║  └───────────────────────────┬───────────────────────────────────────┘    ║
║                              ▼                                            ║
║  ┌───────────────────────────────────────────────────────────────────┐    ║
║  │              LAYER 3: META DECISION ENGINE (MDE)                  │    ║
║  │                                                                   │    ║
║  │  Inputs:                      Processing:                         │    ║
║  │  ├─ Regime state             ├─ Dynamic engine weighting          │    ║
║  │  ├─ 5x engine outputs       ├─ Correlation penalty               │    ║
║  │  ├─ Portfolio state          ├─ Drawdown adjustment               │    ║
║  │  ├─ Drawdown state          ├─ Confidence thresholding            │    ║
║  │  ├─ Market stress index     ├─ Position sizing (Kelly+CVaR)       │    ║
║  │  └─ Recent performance      └─ Regime-conditional leverage        │    ║
║  │                                                                   │    ║
║  │  Output: {action, position_size, leverage, stop_loss, confidence} │    ║
║  └───────────────────────────┬───────────────────────────────────────┘    ║
║                              ▼                                            ║
║  ┌───────────────────────────────────────────────────────────────────┐    ║
║  │              LAYER 4: RISK & SURVIVAL LAYER (RSL)                 │    ║
║  │                                                                   │    ║
║  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐  │    ║
║  │  │ Daily Loss  │ │  Drawdown   │ │  Vol-Adj    │ │   Kill     │  │    ║
║  │  │    Cap      │ │   Guard     │ │   Sizing    │ │  Switch    │  │    ║
║  │  │  -2% hard   │ │  -5% warn   │ │  ATR-based  │ │  -8% halt  │  │    ║
║  │  │  -3% halt   │ │  -8% halt   │ │  regime-adj │ │  24h cool  │  │    ║
║  │  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘  │    ║
║  │                                                                   │    ║
║  │  RSL has VETO POWER over MDE. No trade passes without RSL OK.     │    ║
║  └───────────────────────────┬───────────────────────────────────────┘    ║
║                              ▼                                            ║
║  ┌───────────────────────────────────────────────────────────────────┐    ║
║  │              LAYER 5: EXECUTION ENGINE                            │    ║
║  │                                                                   │    ║
║  │  Smart Order Router → Slippage Control → Fill Monitoring          │    ║
║  │  Partial fills → Retry logic → Exchange failover                  │    ║
║  └───────────────────────────┬───────────────────────────────────────┘    ║
║                              ▼                                            ║
║  ┌───────────────────────────────────────────────────────────────────┐    ║
║  │              LAYER 6: LEARNING & EVOLUTION LAYER (LEL)            │    ║
║  │                                                                   │    ║
║  │  State→Action→Result→Regime logging                               │    ║
║  │  Strategy decay detection │ Performance attribution               │    ║
║  │  Feature importance drift │ Auto-pruning │ RL-ready dataset       │    ║
║  └───────────────────────────────────────────────────────────────────┘    ║
║                                                                          ║
║  ┌───────────────────────────────────────────────────────────────────┐    ║
║  │              CROSS-CUTTING: BACKTEST & VALIDATION (BVS)           │    ║
║  │                                                                   │    ║
║  │  Walk-Forward │ Monte Carlo │ Slippage Sim │ Fee Model │ Regime   │    ║
║  │  Analysis     │ Permutation │ Realistic    │ Tiered    │ Stress   │    ║
║  └───────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

### 26.2 Module Responsibilities

#### 26.2.1 LAYER 0: Data Pipeline

**Responsibility:** Ingest, normalize, cache, and distribute all market data to downstream consumers.

| Component | Source | Frequency | Storage | Criticality |
|-----------|--------|-----------|---------|-------------|
| **OHLCV Multi-TF** | Binance/Bybit WS | 1s,1m,5m,15m,1h,4h,1d | Parquet + Redis | CRITICAL |
| **Funding Rate** | Exchange REST/WS | 8h (real-time stream) | TimescaleDB | HIGH |
| **Open Interest** | Exchange REST | 5m polling | TimescaleDB | HIGH |
| **Orderbook L2** | Exchange WS | 100ms snapshots | Redis (ring buffer) | MEDIUM |
| **Sentiment Feed** | CryptoPanic, Twitter, Reddit | 1m-15m | PostgreSQL | MEDIUM |
| **On-Chain** | Glassnode, CoinGecko | 1h | PostgreSQL | LOW (Phase 2) |

**Feature Engineering Engine:**

| Feature Category | Count | Examples | Compute |
|-----------------|-------|---------|---------|
| **Trend** | 15 | ADX, Aroon, SuperTrend, Linear Reg Slope, Parabolic SAR | CPU |
| **Momentum** | 12 | RSI, MACD, Stochastic, Williams %R, CCI, ROC, MFI | CPU |
| **Volatility** | 10 | ATR, Bollinger Width, Keltner Width, Historical Vol, Parkinson | CPU |
| **Volume** | 10 | OBV, VWAP, Volume Profile, A/D Line, CMF, VPFR | CPU |
| **Microstructure** | 8 | Bid-Ask Spread, Order Imbalance, Trade Flow Imbalance, Kyle Lambda | CPU |
| **Cross-Asset** | 8 | BTC Dominance, BTC-ETH Corr, DXY proxy, Gold Corr | CPU |
| **Derived (ML)** | 15 | Fractional Diff, Entropy, CUSUM Events, Rolling IC | CPU |
| **Chronos Output** | 6 | Price forecast, Vol forecast, Regime prob, Confidence intervals | GPU |
| **Funding/OI** | 8 | Funding Rate, OI Change, OI-weighted direction, Liquidation est. | CPU |
| **Sentiment** | 8 | News score, Social volume, Fear-Greed proxy, Whale alert | CPU |
| **TOTAL** | **100+** | | |

**Data Contract:**

```python
@dataclass
class MarketSnapshot:
    timestamp: datetime
    symbol: str
    ohlcv: dict[str, pd.DataFrame]    # keyed by timeframe
    features: pd.Series               # 100+ computed features
    orderbook: OrderbookState
    funding_rate: float
    open_interest: float
    sentiment_score: float
    
    def validate(self) -> bool:
        """No NaN in critical fields. Timestamp monotonic. Price > 0."""
        ...
```

#### 26.2.2 LAYER 1: Regime Detection Engine (RDE)

**Responsibility:** Classify the current market regime with confidence and stability scores. The RDE is the brain's compass -- every other module depends on its output.

**8 Regime States:**

| # | Regime | Definition | Key Indicators |
|---|--------|------------|----------------|
| 0 | **TRENDING_BULL** | Sustained upward movement with increasing participation | ADX>25, price>MA200, higher highs, rising OBV |
| 1 | **TRENDING_BEAR** | Sustained downward movement with selling pressure | ADX>25, price<MA200, lower lows, declining OBV |
| 2 | **RANGING** | Price oscillating within defined support/resistance | ADX<20, BB width narrowing, mean-reverting |
| 3 | **CHOP** | Erratic, directionless movement with false signals | ADX<15, high whipsaw rate, low serial correlation |
| 4 | **VOL_EXPANSION** | Rapid increase in volatility, direction uncertain | ATR spike >2x 20d avg, BB expansion, VIX proxy up |
| 5 | **VOL_COMPRESSION** | Decreasing volatility, breakout imminent | ATR at 30d low, BB squeeze, decreasing volume |
| 6 | **CRASH_PANIC** | Violent downward movement >10% in 24h | Price drop >10%/24h, vol >3x normal, liquidation cascade |
| 7 | **RECOVERY** | Post-crash stabilization and rebound | Price >10% off bottom, decreasing vol, volume returning |

**Detection Sub-Modules:**

**A) Hidden Markov Model (HMM) - Primary Classifier**

```python
class RegimeHMM:
    """
    Gaussian HMM with 8 hidden states.
    Observations: [log_return, realized_vol, volume_ratio, adx, spread]
    Transition matrix learned from 2+ years of data.
    Re-fitted weekly with expanding window.
    """
    n_states: int = 8
    n_features: int = 5
    covariance_type: str = "full"
    min_obs_for_transition: int = 16  # 16 candles (16h on 1h TF) before confirming
    
    def fit(self, observations: np.ndarray) -> None: ...
    def predict_proba(self, observations: np.ndarray) -> np.ndarray: ...
    def get_regime(self) -> RegimeOutput: ...
```

**B) Volatility Structure Analyzer**

```python
class VolatilityStructure:
    """
    GARCH(1,1) for conditional volatility.
    Parkinson/Garman-Klass for realized vol.
    Vol-of-vol for regime stability.
    ATR ratio (short/long) for expansion/compression detection.
    """
    def classify(self) -> str:
        atr_ratio = atr_5 / atr_20
        if atr_ratio > 1.5:   return "VOL_EXPANSION"
        if atr_ratio < 0.6:   return "VOL_COMPRESSION"
        return "NORMAL"
```

**C) Trend Filter Bank**

```python
class TrendFilterBank:
    """
    Multi-timeframe trend consensus.
    ADX + DI+/DI- for trend strength + direction.
    MA cross system (20/50/200) for trend phase.
    Linear regression slope for trend velocity.
    """
    def classify(self) -> str:
        if adx > 25 and di_plus > di_minus and price > ma200:
            return "TRENDING_BULL"
        if adx > 25 and di_minus > di_plus and price < ma200:
            return "TRENDING_BEAR"
        if adx < 15:
            return "CHOP"
        return "RANGING"
```

**D) Market Microstructure Analyzer**

```python
class MicrostructureAnalyzer:
    """
    Orderbook imbalance for directional pressure.
    Spread analysis for liquidity state.
    Trade size distribution for institutional activity.
    Volume profile for support/resistance.
    """
    def detect_crash(self) -> bool:
        return (
            price_change_24h < -0.10 and
            vol_ratio > 3.0 and
            liquidation_estimate > threshold
        )
```

**Regime Consensus Module:**

```python
class RegimeConsensus:
    """
    Weighted vote across all 4 sub-modules.
    Weights adjusted based on recent accuracy.
    Hysteresis: regime change requires N consecutive
    agreements to prevent whipsawing.
    """
    WEIGHTS = {
        "hmm": 0.35,
        "volatility": 0.25, 
        "trend": 0.25,
        "microstructure": 0.15
    }
    CONFIRMATION_CANDLES = 4   # Must agree for 4 consecutive periods
    MIN_CONFIDENCE = 0.60      # Below this → regime = UNCERTAIN
    
    def compute(self) -> RegimeOutput:
        votes = {
            "hmm": self.hmm.get_regime(),
            "volatility": self.vol.classify(),
            "trend": self.trend.classify(),
            "micro": self.micro.classify()
        }
        # Weighted probability aggregation
        regime_probs = weighted_aggregate(votes, self.WEIGHTS)
        top_regime = argmax(regime_probs)
        confidence = regime_probs[top_regime]
        
        # Hysteresis check
        if top_regime != self.current_regime:
            self.transition_counter += 1
            if self.transition_counter < self.CONFIRMATION_CANDLES:
                return RegimeOutput(
                    regime=self.current_regime,  # Keep old regime
                    confidence=confidence * 0.8,  # Reduce confidence
                    stability=0.3                 # Flag low stability
                )
            else:
                self.current_regime = top_regime
                self.transition_counter = 0
        
        stability = 1.0 - regime_entropy(regime_probs)
        
        return RegimeOutput(
            regime=top_regime,
            confidence=round(confidence, 3),
            stability=round(stability, 3)
        )
```

**Output Contract:**

```json
{
    "regime": "TRENDING_BULL",
    "confidence": 0.82,
    "stability": 0.75,
    "secondary_regime": "VOL_EXPANSION",
    "secondary_confidence": 0.15,
    "transition_risk": 0.12,
    "timestamp": "2026-02-09T14:00:00Z"
}
```

#### 26.2.3 LAYER 2: Strategy Council System (SCS)

**Responsibility:** 5 independent strategy engines, each a specialist in a domain. They operate in parallel, each outputting a directional bias, confidence, risk score, and expected return. No engine knows what the others are doing. No collusion. Pure independent signal generation.

**ENGINE 1: ORION (Trend Engine)**

| Sub-Strategy | Logic | Best Regime | Worst Regime |
|-------------|-------|-------------|--------------|
| **Breakout** | Price breaks N-period high/low with volume confirmation | VOL_COMPRESSION → TRENDING | CHOP |
| **Trend Following** | EMA cross + ADX filter + ATR trailing stop | TRENDING_BULL, TRENDING_BEAR | RANGING, CHOP |
| **Momentum** | RSI + MACD + ROC alignment with volume | TRENDING + VOL_EXPANSION | CHOP |

```python
class OrionEngine:
    """Trend-following specialist. Goes loud in trends, silent in chop."""
    
    def generate_signal(self, snapshot: MarketSnapshot, regime: RegimeOutput) -> EngineSignal:
        # Suppress in chop/ranging -- Orion knows it bleeds there
        if regime.regime in ("CHOP", "RANGING") and regime.confidence > 0.7:
            return EngineSignal(bias="neutral", confidence=0.1, risk_score=0.8, expected_return=0.0)
        
        breakout_signal = self._breakout(snapshot)
        trend_signal = self._trend_follow(snapshot)
        momentum_signal = self._momentum(snapshot)
        
        # Internal consensus
        combined = self._weighted_combine([breakout_signal, trend_signal, momentum_signal],
                                          weights=[0.3, 0.4, 0.3])
        return combined
    
    def _breakout(self, s): ...    # Donchian channel + volume spike
    def _trend_follow(self, s): ... # EMA(21/55) cross + ADX>25 + ATR trail
    def _momentum(self, s): ...    # RSI(14) + MACD(12,26,9) alignment
```

**ENGINE 2: AEGEAN (Mean Reversion Engine)**

| Sub-Strategy | Logic | Best Regime | Worst Regime |
|-------------|-------|-------------|--------------|
| **Range Trading** | Bollinger Band bounces + RSI oversold/overbought | RANGING | TRENDING |
| **VWAP Reversion** | Price deviation from VWAP + mean revert expectation | RANGING, mild CHOP | CRASH |
| **Statistical Edges** | Z-score extremes on price ratios, funding rate arb | RANGING, VOL_COMPRESSION | TRENDING |

```python
class AegeanEngine:
    """Mean-reversion specialist. Feeds on ranges, starves in trends."""
    
    def generate_signal(self, snapshot: MarketSnapshot, regime: RegimeOutput) -> EngineSignal:
        # Suppress in strong trends -- mean reversion is suicide in trends
        if regime.regime in ("TRENDING_BULL", "TRENDING_BEAR") and regime.confidence > 0.7:
            return EngineSignal(bias="neutral", confidence=0.1, risk_score=0.9, expected_return=0.0)
        
        range_signal = self._range_trade(snapshot)
        vwap_signal = self._vwap_reversion(snapshot)
        stat_signal = self._statistical_edge(snapshot)
        
        combined = self._weighted_combine([range_signal, vwap_signal, stat_signal],
                                          weights=[0.4, 0.35, 0.25])
        return combined
    
    def _range_trade(self, s): ...     # BB(20,2) + RSI(14) extremes
    def _vwap_reversion(self, s): ...  # Distance from VWAP + volume profile
    def _statistical_edge(self, s): ... # Z-score + funding rate premium
```

**ENGINE 3: ATLAS (Macro / Risk Engine)**

| Sub-Strategy | Logic | Best Regime | Worst Regime |
|-------------|-------|-------------|--------------|
| **Risk-On/Risk-Off** | DXY, yields, BTC dominance, correlation regime | ALL | None (always relevant) |
| **Correlation Mgmt** | Cross-asset correlation shifts, contagion detection | VOL_EXPANSION, CRASH | VOL_COMPRESSION |
| **Macro Overlay** | Fed/ECB events, CPI, rate decisions impact | ALL | None |

```python
class AtlasEngine:
    """The adult in the room. Doesn't trade -- it governs risk appetite."""
    
    def generate_signal(self, snapshot: MarketSnapshot, regime: RegimeOutput) -> EngineSignal:
        risk_state = self._risk_on_off(snapshot)       # RISK_ON | RISK_OFF | NEUTRAL
        correlation = self._correlation_risk(snapshot)   # 0.0 (uncorrelated) to 1.0 (contagion)
        macro_bias = self._macro_overlay(snapshot)       # -1 (bearish) to +1 (bullish)
        
        # Atlas biases the portfolio, doesn't generate direct trades
        if risk_state == "RISK_OFF":
            return EngineSignal(bias="short", confidence=0.7, risk_score=0.2, expected_return=-0.01)
        elif risk_state == "RISK_ON" and macro_bias > 0.3:
            return EngineSignal(bias="long", confidence=0.6, risk_score=0.4, expected_return=0.01)
        else:
            return EngineSignal(bias="neutral", confidence=0.5, risk_score=0.5, expected_return=0.0)
```

**ENGINE 4: HERMES (Sentiment Engine)**

| Sub-Strategy | Logic | Best Regime | Worst Regime |
|-------------|-------|-------------|--------------|
| **News NLP** | DistilBERT on crypto news, event classification | NEWS_SHOCK, CRASH | RANGING (noise) |
| **Social Volume** | Reddit/Twitter mention velocity + sentiment delta | VOL_EXPANSION | CHOP |
| **Orderflow Proxy** | Large trade detection, whale movement inference | ALL | None |

```python
class HermesEngine:
    """The ear on the ground. Listens to what the crowd is doing."""
    
    def generate_signal(self, snapshot: MarketSnapshot, regime: RegimeOutput) -> EngineSignal:
        news_sentiment = self._news_nlp(snapshot)          # -1 to +1
        social_momentum = self._social_volume(snapshot)     # -1 to +1
        flow_signal = self._orderflow_proxy(snapshot)       # -1 to +1
        
        # Hermes confidence is lower by design -- sentiment is noisy
        composite = 0.4 * news_sentiment + 0.3 * social_momentum + 0.3 * flow_signal
        confidence = min(abs(composite) * 1.2, 0.7)  # Capped at 0.7 -- never fully trust sentiment
        
        bias = "long" if composite > 0.15 else "short" if composite < -0.15 else "neutral"
        return EngineSignal(bias=bias, confidence=confidence, risk_score=0.6, expected_return=composite*0.005)
```

**ENGINE 5: HELIOS (Scalping / Microstructure Engine)**

| Sub-Strategy | Logic | Best Regime | Worst Regime |
|-------------|-------|-------------|--------------|
| **Spread Capture** | Bid-ask spread widening → provide liquidity | RANGING, VOL_COMPRESSION | CRASH |
| **Liquidity Gaps** | Detect orderbook thin zones → short-term moves | VOL_EXPANSION | CHOP |
| **Funding Arbitrage** | Funding rate extremes → basis trade | ALL (when funding extreme) | None |

```python
class HeliosEngine:
    """The scalpel. Makes many small cuts. High frequency, low size."""
    
    def generate_signal(self, snapshot: MarketSnapshot, regime: RegimeOutput) -> EngineSignal:
        spread_opp = self._spread_analysis(snapshot)
        liquidity_gap = self._liquidity_gap(snapshot)
        funding_arb = self._funding_arbitrage(snapshot)
        
        # Helios operates only when edge is clear and short-lived
        if regime.regime == "CRASH_PANIC":
            return EngineSignal(bias="neutral", confidence=0.0, risk_score=1.0, expected_return=0.0)
        
        best_opp = max([spread_opp, liquidity_gap, funding_arb], key=lambda x: x.expected_return)
        return best_opp
```

**Engine Output Contract:**

```json
{
    "engine": "ORION",
    "timestamp": "2026-02-09T14:00:00Z",
    "bias": "long",
    "confidence": 0.78,
    "risk_score": 0.35,
    "expected_return": 0.012,
    "sub_signals": {
        "breakout": {"bias": "long", "confidence": 0.85},
        "trend_follow": {"bias": "long", "confidence": 0.80},
        "momentum": {"bias": "long", "confidence": 0.65}
    },
    "regime_suitability": 0.90
}
```

#### 26.2.4 LAYER 3: Meta Decision Engine (MDE)

**Responsibility:** The Supreme Commander. Receives 5 engine signals + regime state + portfolio state. Produces the final actionable decision. The only module allowed to issue trade orders.

**MDE Core Algorithm (Pseudocode):**

```python
class MetaDecisionEngine:
    """
    THE decision maker. No other module can trade.
    MDE is regime-aware, drawdown-aware, correlation-aware.
    It weights, filters, sizes, and decides.
    """
    
    # Base engine weights -- adjusted dynamically
    BASE_WEIGHTS = {
        "ORION":  0.25,
        "AEGEAN": 0.20,
        "ATLAS":  0.20,
        "HERMES": 0.15,
        "HELIOS": 0.20
    }
    
    # Regime-specific weight overrides
    REGIME_WEIGHTS = {
        "TRENDING_BULL": {"ORION": 0.40, "AEGEAN": 0.05, "ATLAS": 0.20, "HERMES": 0.15, "HELIOS": 0.20},
        "TRENDING_BEAR": {"ORION": 0.35, "AEGEAN": 0.05, "ATLAS": 0.25, "HERMES": 0.15, "HELIOS": 0.20},
        "RANGING":       {"ORION": 0.10, "AEGEAN": 0.35, "ATLAS": 0.15, "HERMES": 0.15, "HELIOS": 0.25},
        "CHOP":          {"ORION": 0.05, "AEGEAN": 0.20, "ATLAS": 0.30, "HERMES": 0.15, "HELIOS": 0.30},
        "VOL_EXPANSION": {"ORION": 0.25, "AEGEAN": 0.10, "ATLAS": 0.30, "HERMES": 0.20, "HELIOS": 0.15},
        "VOL_COMPRESSION":{"ORION": 0.30, "AEGEAN": 0.25, "ATLAS": 0.15, "HERMES": 0.10, "HELIOS": 0.20},
        "CRASH_PANIC":   {"ORION": 0.05, "AEGEAN": 0.00, "ATLAS": 0.60, "HERMES": 0.30, "HELIOS": 0.05},
        "RECOVERY":      {"ORION": 0.35, "AEGEAN": 0.15, "ATLAS": 0.20, "HERMES": 0.15, "HELIOS": 0.15}
    }
    
    # Confidence gates
    MIN_CONFIDENCE_TO_TRADE = 0.55
    MIN_CONFIDENCE_TO_ADD   = 0.70
    MIN_ENGINES_AGREEING    = 2    # At least 2 engines must agree on direction
    
    def decide(self,
               regime: RegimeOutput,
               engine_signals: dict[str, EngineSignal],
               portfolio: PortfolioState,
               risk_state: RiskState) -> Decision:
        
        # ──── STEP 1: Get regime-adjusted weights ────
        weights = self.REGIME_WEIGHTS.get(regime.regime, self.BASE_WEIGHTS).copy()
        
        # ──── STEP 2: Performance-adjusted weights ────
        # Suppress engines that have been losing recently
        for engine_name, signal in engine_signals.items():
            recent_perf = self.performance_tracker.get_30d_sharpe(engine_name)
            if recent_perf < -0.5:
                weights[engine_name] *= 0.3    # Suppress bad performer
            elif recent_perf > 1.0:
                weights[engine_name] *= 1.2    # Boost good performer
        
        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
        
        # ──── STEP 3: Compute weighted consensus ────
        weighted_bias = 0.0       # -1.0 (max short) to +1.0 (max long)
        weighted_confidence = 0.0
        weighted_risk = 0.0
        weighted_er = 0.0
        
        for engine_name, signal in engine_signals.items():
            w = weights[engine_name]
            bias_num = {"long": 1.0, "neutral": 0.0, "short": -1.0}[signal.bias]
            
            weighted_bias += w * bias_num * signal.confidence
            weighted_confidence += w * signal.confidence
            weighted_risk += w * signal.risk_score
            weighted_er += w * signal.expected_return
        
        # ──── STEP 4: Count agreeing engines ────
        direction = "long" if weighted_bias > 0 else "short" if weighted_bias < 0 else "neutral"
        n_agreeing = sum(1 for s in engine_signals.values() 
                        if s.bias == direction and s.confidence > 0.3)
        
        # ──── STEP 5: Confidence gate ────
        if weighted_confidence < self.MIN_CONFIDENCE_TO_TRADE:
            return Decision(action="hold", position_size=0, leverage=1.0,
                          stop_loss=None, confidence=weighted_confidence,
                          reason="Below confidence threshold")
        
        if n_agreeing < self.MIN_ENGINES_AGREEING:
            return Decision(action="hold", position_size=0, leverage=1.0,
                          stop_loss=None, confidence=weighted_confidence,
                          reason=f"Only {n_agreeing} engines agree, need {self.MIN_ENGINES_AGREEING}")
        
        # ──── STEP 6: Correlation penalty ────
        # If multiple engines are correlated, reduce effective confidence
        corr_penalty = self._compute_correlation_penalty(engine_signals)
        adjusted_confidence = weighted_confidence * (1.0 - corr_penalty)
        
        # ──── STEP 7: Drawdown adjustment ────
        dd_multiplier = 1.0
        if risk_state.current_drawdown > 0.03:     # -3% DD
            dd_multiplier = 0.5                      # Half size
        if risk_state.current_drawdown > 0.05:     # -5% DD
            dd_multiplier = 0.25                     # Quarter size
        if risk_state.current_drawdown > 0.08:     # -8% DD
            return Decision(action="reduce", position_size=0, leverage=1.0,
                          stop_loss=None, confidence=1.0,
                          reason="KILL SWITCH: Drawdown exceeds 8%")
        
        # ──── STEP 8: Position sizing (Modified Kelly) ────
        kelly_fraction = self._kelly_criterion(
            win_rate=self.performance_tracker.get_win_rate(),
            avg_win=self.performance_tracker.get_avg_win(),
            avg_loss=self.performance_tracker.get_avg_loss()
        )
        # Half-Kelly for safety, capped at 15% of portfolio
        position_pct = min(kelly_fraction * 0.5, 0.15) * dd_multiplier
        
        # ──── STEP 9: Regime-conditional leverage ────
        max_leverage = {
            "TRENDING_BULL": 3.0,
            "TRENDING_BEAR": 2.0,
            "RANGING": 2.0,
            "CHOP": 1.0,         # NO leverage in chop
            "VOL_EXPANSION": 1.5,
            "VOL_COMPRESSION": 2.5,
            "CRASH_PANIC": 1.0,  # NO leverage in crash
            "RECOVERY": 2.0
        }
        leverage = min(
            1.0 + (adjusted_confidence - 0.5) * 2.0,  # Scale with confidence
            max_leverage.get(regime.regime, 1.0)
        )
        leverage = max(leverage, 1.0)  # Never below 1x
        
        # ──── STEP 10: Stop loss calculation ────
        atr = engine_signals["ORION"].snapshot_atr if hasattr(engine_signals["ORION"], 'snapshot_atr') else 0.02
        stop_loss_pct = max(atr * 1.5, 0.01)   # ATR-based, minimum 1%
        stop_loss_pct = min(stop_loss_pct, 0.05) # Maximum 5%
        
        # ──── STEP 11: Final decision ────
        if abs(weighted_bias) > 0.3 and adjusted_confidence > self.MIN_CONFIDENCE_TO_TRADE:
            action = "buy" if weighted_bias > 0 else "sell"
        elif portfolio.has_position and abs(weighted_bias) < 0.1:
            action = "reduce"  # Weak signal + existing position → trim
        else:
            action = "hold"
        
        return Decision(
            action=action,
            position_size=round(position_pct, 4),
            leverage=round(leverage, 2),
            stop_loss=round(stop_loss_pct, 4),
            confidence=round(adjusted_confidence, 3),
            reason=f"Regime={regime.regime}, Bias={weighted_bias:.2f}, "
                   f"Engines={n_agreeing}/{len(engine_signals)}, DD_mult={dd_multiplier}"
        )
    
    def _kelly_criterion(self, win_rate, avg_win, avg_loss):
        """f* = (p*b - q) / b where b = avg_win/avg_loss"""
        if avg_loss == 0: return 0.01
        b = avg_win / abs(avg_loss)
        q = 1 - win_rate
        f = (win_rate * b - q) / b
        return max(f, 0.01)  # Never negative, minimum 1%
    
    def _compute_correlation_penalty(self, signals):
        """If 3+ engines give identical signals, they might be seeing the same thing."""
        biases = [s.bias for s in signals.values() if s.confidence > 0.3]
        if len(biases) == 0: return 0.0
        most_common = max(set(biases), key=biases.count)
        agreement_ratio = biases.count(most_common) / len(biases)
        # Penalty kicks in when >80% agree (might be correlated, not independent)
        if agreement_ratio > 0.8:
            return 0.15  # 15% penalty for possible correlation
        return 0.0
```

**MDE Decision Output Contract:**

```json
{
    "action": "buy",
    "position_size": 0.08,
    "leverage": 2.0,
    "stop_loss": 0.025,
    "confidence": 0.72,
    "reason": "Regime=TRENDING_BULL, Bias=0.65, Engines=4/5, DD_mult=1.0",
    "timestamp": "2026-02-09T14:00:00Z",
    "engine_weights_used": {
        "ORION": 0.40, "AEGEAN": 0.05, "ATLAS": 0.20, "HERMES": 0.15, "HELIOS": 0.20
    }
}
```

#### 26.2.5 LAYER 4: Risk & Survival Layer (RSL)

**Responsibility:** The last line of defense. RSL has **VETO POWER** over all MDE decisions. No trade executes without RSL approval. RSL can forcibly close positions, reduce exposure, or halt the entire system.

**RSL Operates on 5 Independent Risk Checks:**

```
Trade Decision (from MDE)
        │
        ▼
┌───────────────────┐
│  CHECK 1:         │──FAIL──► BLOCK TRADE
│  Daily Loss Cap   │
│  -2% soft / -3%   │
│  hard             │
└───────┬───────────┘
        │ PASS
        ▼
┌───────────────────┐
│  CHECK 2:         │──FAIL──► CLOSE ALL + HALT 24h
│  Max Drawdown     │
│  -5% warn / -8%   │
│  kill             │
└───────┬───────────┘
        │ PASS
        ▼
┌───────────────────┐
│  CHECK 3:         │──FAIL──► REDUCE SIZE
│  Vol-Adjusted     │
│  Sizing           │
│  position < f(ATR)│
└───────┬───────────┘
        │ PASS
        ▼
┌───────────────────┐
│  CHECK 4:         │──FAIL──► BLOCK TRADE
│  Cooldown         │
│  After loss streak│
│  3+ losses → wait │
└───────┬───────────┘
        │ PASS
        ▼
┌───────────────────┐
│  CHECK 5:         │──FAIL──► BLOCK TRADE
│  Correlation      │
│  Max 0.7 between  │
│  concurrent pos.  │
└───────┬───────────┘
        │ PASS
        ▼
    EXECUTE TRADE
```

**RSL Rules Table:**

| Rule | Trigger | Action | Duration | Override |
|------|---------|--------|----------|----------|
| **Daily Loss Cap (Soft)** | PnL today < -2% | New positions blocked, existing OK | Until 00:00 UTC | Manual only |
| **Daily Loss Cap (Hard)** | PnL today < -3% | Close 50% of positions | Until 00:00 UTC | Manual only |
| **Drawdown Warning** | DD from peak > -5% | Position sizes halved | Until DD recovers to -3% | None |
| **Drawdown Kill Switch** | DD from peak > -8% | ALL positions closed. System halted. | 24 hours minimum | Manual review required |
| **Vol Spike Guard** | ATR > 2.5x 20d avg | Max position = 50% of normal | Until ATR normalizes | None |
| **Cooldown (Losses)** | 3 consecutive losses | No new trades | 4 hours | None |
| **Cooldown (Kill)** | After kill switch | No new trades | 24 hours | Manual only |
| **Correlation Guard** | Position corr > 0.7 | Block correlated trade | Per trade | None |
| **Single Position Cap** | Any position > 15% portfolio | Block or trim | Per trade | None |
| **Daily Trade Cap** | > 20 trades/day | Block new trades | Until 00:00 UTC | None |
| **Slippage Guard** | Slippage > 0.5% | Pause + alert | 30 minutes | None |
| **Exchange Failure** | API timeout > 10s | Cancel pending orders | Until resolved | None |

**RSL Pseudocode:**

```python
class RiskSurvivalLayer:
    DAILY_LOSS_SOFT = -0.02
    DAILY_LOSS_HARD = -0.03
    DD_WARNING = -0.05
    DD_KILL = -0.08
    MAX_CONSECUTIVE_LOSSES = 3
    MAX_POSITION_PCT = 0.15
    MAX_DAILY_TRADES = 20
    COOLDOWN_HOURS = 4
    KILL_COOLDOWN_HOURS = 24
    MAX_CORRELATION = 0.7
    
    def approve(self, decision: Decision, portfolio: PortfolioState) -> RiskVerdict:
        # Check 1: Daily loss
        if portfolio.daily_pnl_pct < self.DAILY_LOSS_HARD:
            self._force_reduce(portfolio, 0.5)
            return RiskVerdict(approved=False, reason="Daily hard loss cap hit")
        if portfolio.daily_pnl_pct < self.DAILY_LOSS_SOFT:
            if decision.action in ("buy", "sell"):
                return RiskVerdict(approved=False, reason="Daily soft loss cap hit")
        
        # Check 2: Drawdown
        if portfolio.drawdown < self.DD_KILL:
            self._kill_switch(portfolio)
            return RiskVerdict(approved=False, reason="KILL SWITCH ACTIVATED")
        if portfolio.drawdown < self.DD_WARNING:
            decision.position_size *= 0.5
        
        # Check 3: Vol-adjusted sizing
        if portfolio.current_atr_ratio > 2.5:
            decision.position_size *= 0.5
        
        # Check 4: Cooldown
        if portfolio.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
            if not self._cooldown_elapsed(self.COOLDOWN_HOURS):
                return RiskVerdict(approved=False, reason="Loss streak cooldown")
        
        # Check 5: Correlation
        if decision.action in ("buy", "sell"):
            for existing_pos in portfolio.positions:
                corr = self._compute_correlation(decision.symbol, existing_pos.symbol)
                if corr > self.MAX_CORRELATION:
                    return RiskVerdict(approved=False, 
                                     reason=f"Correlated with {existing_pos.symbol}: {corr:.2f}")
        
        # Check 6: Position size cap
        if decision.position_size > self.MAX_POSITION_PCT:
            decision.position_size = self.MAX_POSITION_PCT
        
        # Check 7: Daily trade count
        if portfolio.trades_today >= self.MAX_DAILY_TRADES:
            return RiskVerdict(approved=False, reason="Daily trade limit reached")
        
        return RiskVerdict(approved=True, adjusted_decision=decision)
    
    def _kill_switch(self, portfolio):
        """EMERGENCY: Close everything. Alert owner. Halt system."""
        for position in portfolio.positions:
            self.executor.market_close(position)
        self.alerter.send_critical("KILL SWITCH ACTIVATED. All positions closed.")
        self.system.halt(duration_hours=self.KILL_COOLDOWN_HOURS)
```

#### 26.2.6 LAYER 5: Execution Engine

**Responsibility:** Convert approved decisions into actual exchange orders. Handle partial fills, retries, slippage monitoring, and exchange failover.

| Component | Responsibility |
|-----------|---------------|
| **Smart Order Router** | Choose best exchange based on liquidity, fees, latency |
| **Order Type Selector** | Limit vs Market based on urgency and spread |
| **Slippage Monitor** | Track expected vs actual fill price |
| **Partial Fill Handler** | Retry or cancel remaining after timeout |
| **Exchange Failover** | If primary down → route to secondary |
| **Position Reconciler** | Verify local state matches exchange state every 60s |

#### 26.2.7 LAYER 6: Learning & Evolution Layer (LEL)

**Responsibility:** Continuous improvement without rewriting code. Detect what's working, what's decaying, what should be pruned.

**LEL Data Store (Every Trade):**

```json
{
    "trade_id": "T-20260209-0042",
    "timestamp_entry": "2026-02-09T14:00:00Z",
    "timestamp_exit": "2026-02-09T18:30:00Z",
    "regime_at_entry": "TRENDING_BULL",
    "regime_at_exit": "TRENDING_BULL",
    "engine_signals": { ... },
    "mde_decision": { ... },
    "rsl_adjustments": { ... },
    "entry_price": 98500.0,
    "exit_price": 99200.0,
    "pnl_pct": 0.0071,
    "slippage": 0.0002,
    "fees": 0.0004,
    "net_pnl_pct": 0.0065,
    "duration_minutes": 270,
    "features_snapshot": { ... }
}
```

**LEL Continuous Tasks:**

| Task | Frequency | Logic |
|------|-----------|-------|
| **Strategy Decay Detection** | Weekly | Rolling 30d Sharpe per engine. Alert if Sharpe drops below 0.5 for 2+ weeks |
| **Performance Attribution** | Daily | Which engine contributed most to PnL? Update engine credibility scores |
| **Feature Importance Drift** | Weekly | Re-run MDI/MDA. If top features change >30%, flag for investigation |
| **Auto-Pruning** | Monthly | If an engine's 60d Sharpe < 0 → weight drops to 0.05 (minimum) |
| **Regime Accuracy Audit** | Weekly | How accurate was RDE? Compare predicted vs realized regime |
| **RL Dataset Build** | Continuous | Append (state, action, reward, next_state) for future RL training |

---

### 26.3 Complete Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW DIAGRAM                            │
└──────────────────────────────────────────────────────────────────────┘

EXTERNAL SOURCES                    INTERNAL PIPELINE
================                    ==================

Binance WS ─────┐
Bybit WS ───────┤                  ┌──────────────────┐
CryptoPanic ────┼───► Ingest ────► │ Raw Data Store    │
Twitter API ────┤    Layer         │ (Redis + Parquet) │
Glassnode ──────┘                  └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │ Feature Engine    │
                                   │ 100+ features     │
                                   │ Multi-timeframe   │
                                   └────────┬─────────┘
                                            │
                                   ┌────────▼─────────┐
                              ┌────│ MarketSnapshot    │────┐
                              │    │ (immutable obj)   │    │
                              │    └──────────────────┘    │
                              │                            │
                              ▼                            ▼
                     ┌─────────────────┐         ┌─────────────────────┐
                     │      RDE        │         │    5x ENGINES       │
                     │ Regime Detection│         │ (receive snapshot   │
                     └────────┬────────┘         │  + regime output)   │
                              │                  └──────────┬──────────┘
                              │                             │
                              │    ┌─────────────────┐      │
                              └───►│       MDE       │◄─────┘
                                   │ Meta Decision   │
                                   │ Engine          │
                                   └────────┬────────┘
                                            │
                                   ┌────────▼────────┐
                                   │      RSL        │
                                   │ Risk Survival   │──── VETO / APPROVE
                                   └────────┬────────┘
                                            │
                                   ┌────────▼────────┐
                                   │   Execution     │
                                   │   Engine        │───► Exchange API
                                   └────────┬────────┘
                                            │
                                   ┌────────▼────────┐
                                   │      LEL        │
                                   │ Learning Layer  │───► Trade DB
                                   └─────────────────┘       │
                                                             ▼
                                                    ┌─────────────────┐
                                                    │   Dashboard     │
                                                    │   + Telegram    │
                                                    │   + Alerts      │
                                                    └─────────────────┘
```

**Timing Constraints:**

| Stage | Max Latency | Notes |
|-------|-------------|-------|
| Data Ingest → Feature Compute | < 500ms | Critical path |
| Regime Detection | < 200ms | Cached HMM, no re-fit during live |
| 5x Engine Signal Generation | < 1000ms (parallel) | All engines fire in parallel |
| MDE Decision | < 100ms | Pure computation |
| RSL Check | < 50ms | Simple rule checks |
| Order Placement | < 500ms | Exchange dependent |
| **Total Decision Latency** | **< 2.5 seconds** | From candle close to order sent |

---

### 26.4 Folder Structure

```
argus-terminal/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
│
├── config/
│   ├── base.yaml                  # Default configuration
│   ├── production.yaml            # Production overrides
│   ├── paper.yaml                 # Paper trading config
│   ├── backtest.yaml              # Backtest config
│   └── regimes.yaml               # Regime thresholds
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                      # Core framework
│   │   ├── __init__.py
│   │   ├── types.py               # MarketSnapshot, Decision, EngineSignal dataclasses
│   │   ├── config.py              # Configuration loader
│   │   ├── events.py              # Event bus (pub/sub)
│   │   ├── clock.py               # System clock (live/backtest aware)
│   │   └── exceptions.py          # Custom exceptions
│   │
│   ├── data/                      # LAYER 0: Data Pipeline
│   │   ├── __init__.py
│   │   ├── ingest/
│   │   │   ├── binance_ws.py      # Binance WebSocket connector
│   │   │   ├── bybit_ws.py        # Bybit WebSocket connector
│   │   │   ├── funding.py         # Funding rate ingestion
│   │   │   ├── orderbook.py       # L2 orderbook snapshots
│   │   │   └── sentiment.py       # News/social sentiment feed
│   │   ├── features/
│   │   │   ├── technical.py       # RSI, MACD, BB, ATR, etc.
│   │   │   ├── microstructure.py  # Spread, imbalance, flow
│   │   │   ├── cross_asset.py     # Correlations, dominance
│   │   │   ├── derived.py         # Fractional diff, entropy, CUSUM
│   │   │   └── chronos_features.py # Chronos model outputs as features
│   │   ├── store/
│   │   │   ├── parquet_store.py   # OHLCV Parquet read/write
│   │   │   ├── redis_cache.py     # Real-time cache layer
│   │   │   └── timescale.py       # TimescaleDB for time series
│   │   └── snapshot.py            # MarketSnapshot builder
│   │
│   ├── regime/                    # LAYER 1: Regime Detection Engine
│   │   ├── __init__.py
│   │   ├── hmm.py                 # Hidden Markov Model classifier
│   │   ├── volatility.py          # GARCH + ATR structure
│   │   ├── trend_filter.py        # ADX + MA filter bank
│   │   ├── microstructure.py      # Volume profile + orderbook analysis
│   │   └── consensus.py           # Weighted vote + hysteresis
│   │
│   ├── engines/                   # LAYER 2: Strategy Council System
│   │   ├── __init__.py
│   │   ├── base.py                # AbstractEngine base class
│   │   ├── orion/                 # Trend Engine
│   │   │   ├── __init__.py
│   │   │   ├── breakout.py
│   │   │   ├── trend_follow.py
│   │   │   ├── momentum.py
│   │   │   └── engine.py          # OrionEngine orchestrator
│   │   ├── aegean/                # Mean Reversion Engine
│   │   │   ├── __init__.py
│   │   │   ├── range_trade.py
│   │   │   ├── vwap_reversion.py
│   │   │   ├── statistical.py
│   │   │   └── engine.py
│   │   ├── atlas/                 # Macro / Risk Engine
│   │   │   ├── __init__.py
│   │   │   ├── risk_regime.py
│   │   │   ├── correlation.py
│   │   │   ├── macro_overlay.py
│   │   │   └── engine.py
│   │   ├── hermes/                # Sentiment Engine
│   │   │   ├── __init__.py
│   │   │   ├── news_nlp.py
│   │   │   ├── social_volume.py
│   │   │   ├── orderflow.py
│   │   │   └── engine.py
│   │   └── helios/                # Scalping / Microstructure Engine
│   │       ├── __init__.py
│   │       ├── spread.py
│   │       ├── liquidity_gap.py
│   │       ├── funding_arb.py
│   │       └── engine.py
│   │
│   ├── mde/                       # LAYER 3: Meta Decision Engine
│   │   ├── __init__.py
│   │   ├── decision_engine.py     # Core MDE logic
│   │   ├── weighting.py           # Dynamic weight computation
│   │   ├── sizing.py              # Kelly criterion + position sizing
│   │   └── correlation.py         # Cross-engine correlation analysis
│   │
│   ├── risk/                      # LAYER 4: Risk & Survival Layer
│   │   ├── __init__.py
│   │   ├── rsl.py                 # Main RSL orchestrator
│   │   ├── daily_cap.py           # Daily loss cap logic
│   │   ├── drawdown.py            # Drawdown monitoring + kill switch
│   │   ├── vol_guard.py           # Volatility-adjusted sizing
│   │   ├── cooldown.py            # Loss streak cooldown
│   │   ├── correlation_guard.py   # Position correlation check
│   │   └── kill_switch.py         # Emergency halt
│   │
│   ├── execution/                 # LAYER 5: Execution Engine
│   │   ├── __init__.py
│   │   ├── executor.py            # Main execution orchestrator
│   │   ├── order_router.py        # Smart order routing
│   │   ├── slippage.py            # Slippage monitoring
│   │   └── reconciler.py          # Position reconciliation
│   │
│   ├── learning/                  # LAYER 6: Learning & Evolution
│   │   ├── __init__.py
│   │   ├── trade_logger.py        # State→Action→Result logging
│   │   ├── decay_detector.py      # Strategy decay detection
│   │   ├── attribution.py         # Performance attribution
│   │   ├── feature_drift.py       # Feature importance monitoring
│   │   └── pruner.py              # Auto-pruning logic
│   │
│   ├── ml/                        # ML Models
│   │   ├── __init__.py
│   │   ├── chronos/
│   │   │   ├── predictor.py       # Chronos-Bolt inference
│   │   │   └── fine_tune.py       # LoRA fine-tuning
│   │   ├── lightgbm_model.py      # LightGBM alpha model
│   │   ├── lstm_model.py          # LSTM/GRU sequence model
│   │   ├── sentiment_model.py     # DistilBERT sentiment
│   │   ├── meta_labeler.py        # Meta-labeling model
│   │   └── training/
│   │       ├── walk_forward.py    # Walk-forward validation
│   │       ├── triple_barrier.py  # Triple barrier labeling
│   │       └── feature_eng.py     # Fractional diff, entropy
│   │
│   ├── backtest/                  # Backtest & Validation System
│   │   ├── __init__.py
│   │   ├── backtester.py          # Main backtest engine
│   │   ├── walk_forward.py        # Walk-forward analysis
│   │   ├── monte_carlo.py         # Monte Carlo permutation
│   │   ├── slippage_sim.py        # Realistic slippage model
│   │   ├── fee_model.py           # Tiered fee model
│   │   └── regime_stress.py       # Regime-specific stress tests
│   │
│   └── interface/                 # User Interface
│       ├── __init__.py
│       ├── telegram_bot.py        # Telegram control bot
│       ├── dashboard.py           # Web dashboard
│       └── alerts.py              # Alert management
│
├── tests/
│   ├── unit/
│   │   ├── test_regime.py
│   │   ├── test_engines.py
│   │   ├── test_mde.py
│   │   ├── test_rsl.py
│   │   └── test_features.py
│   ├── integration/
│   │   ├── test_pipeline.py
│   │   ├── test_backtest.py
│   │   └── test_execution.py
│   └── stress/
│       ├── test_crash_scenario.py
│       ├── test_regime_transition.py
│       └── test_multi_engine_failure.py
│
├── scripts/
│   ├── run_live.py                # Start live trading
│   ├── run_paper.py               # Start paper trading
│   ├── run_backtest.py            # Run backtest
│   ├── train_models.py            # Train ML models
│   ├── verify_gpu.py              # GPU verification
│   └── migrate_data.py            # Data migration tool
│
├── data/
│   ├── ohlcv/                     # Historical OHLCV (Parquet)
│   ├── models/                    # Trained model artifacts
│   ├── backtest_results/          # Backtest output
│   └── trade_logs/                # Trade log database
│
└── Docs/
    ├── FUTURE_VISION.md           # This document
    ├── ARGUS_MASTER_PLAN.md
    └── ...
```

---

### 26.5 Development Roadmap (12 Weeks)

#### Week 1-2: Foundation Layer

| Task | Deliverable | Hours |
|------|------------|-------|
| Project scaffold + config system | `config/`, `src/core/` | 8 |
| Data ingest: Binance WS OHLCV + funding | `src/data/ingest/` | 12 |
| Feature engineering (50 core indicators) | `src/data/features/` | 16 |
| MarketSnapshot builder + data contracts | `src/data/snapshot.py` | 6 |
| Parquet store + Redis cache | `src/data/store/` | 8 |
| Unit tests for data layer | `tests/unit/` | 6 |
| **Week 1-2 Total** | | **56h** |

#### Week 3-4: Regime Detection + First 2 Engines

| Task | Deliverable | Hours |
|------|------------|-------|
| HMM regime classifier (8-state) | `src/regime/hmm.py` | 12 |
| Volatility structure (GARCH + ATR) | `src/regime/volatility.py` | 8 |
| Trend filter bank (ADX + MA) | `src/regime/trend_filter.py` | 6 |
| Regime consensus + hysteresis | `src/regime/consensus.py` | 8 |
| ORION engine (breakout + trend + momentum) | `src/engines/orion/` | 16 |
| AEGEAN engine (range + VWAP + stat) | `src/engines/aegean/` | 14 |
| Backtest engine v1 (basic) | `src/backtest/backtester.py` | 10 |
| **Week 3-4 Total** | | **74h** |

#### Week 5-6: Remaining Engines + MDE

| Task | Deliverable | Hours |
|------|------------|-------|
| ATLAS engine (risk-on/off + correlation) | `src/engines/atlas/` | 12 |
| HERMES engine (sentiment + social + flow) | `src/engines/hermes/` | 14 |
| HELIOS engine (spread + liquidity + funding) | `src/engines/helios/` | 12 |
| MDE core (weighting + sizing + decision) | `src/mde/` | 16 |
| Engine-to-MDE integration test | `tests/integration/` | 8 |
| **Week 5-6 Total** | | **62h** |

#### Week 7-8: Risk Layer + Execution

| Task | Deliverable | Hours |
|------|------------|-------|
| RSL: daily cap + drawdown + kill switch | `src/risk/` | 16 |
| RSL: vol guard + cooldown + correlation | `src/risk/` | 10 |
| Execution engine + order routing | `src/execution/` | 14 |
| Position reconciliation | `src/execution/reconciler.py` | 6 |
| Slippage + fee model for backtest | `src/backtest/slippage_sim.py` | 8 |
| Walk-forward analysis | `src/backtest/walk_forward.py` | 10 |
| **Week 7-8 Total** | | **64h** |

#### Week 9-10: ML Integration + Chronos

| Task | Deliverable | Hours |
|------|------------|-------|
| LightGBM baseline + Triple Barrier | `src/ml/` | 14 |
| Chronos-Bolt zero-shot integration | `src/ml/chronos/` | 8 |
| LSTM/GRU model | `src/ml/lstm_model.py` | 10 |
| Meta-labeling model | `src/ml/meta_labeler.py` | 8 |
| Feature importance + drift monitor | `src/learning/` | 6 |
| ML → Engine integration | Connect ML outputs to engines | 8 |
| **Week 9-10 Total** | | **54h** |

#### Week 11-12: Production Hardening

| Task | Deliverable | Hours |
|------|------------|-------|
| Telegram bot (status, force close, alerts) | `src/interface/telegram_bot.py` | 10 |
| Dashboard (basic web UI) | `src/interface/dashboard.py` | 12 |
| Monte Carlo + regime stress tests | `src/backtest/` | 8 |
| LEL: trade logging + decay detection | `src/learning/` | 8 |
| Paper trading full system test (72h) | Live paper test | 12 |
| Bug fixes + edge cases | Throughout | 10 |
| **Week 11-12 Total** | | **60h** |

#### Summary:

| Phase | Weeks | Hours | Deliverable |
|-------|-------|-------|-------------|
| Foundation | 1-2 | 56h | Data pipeline, features, storage |
| Core Engines | 3-4 | 74h | RDE + Orion + Aegean + basic backtest |
| Full Council | 5-6 | 62h | Atlas + Hermes + Helios + MDE |
| Risk + Exec | 7-8 | 64h | RSL + Execution + walk-forward |
| ML + AI | 9-10 | 54h | LightGBM + Chronos + LSTM + meta-label |
| Hardening | 11-12 | 60h | Telegram, dashboard, stress tests, paper |
| **TOTAL** | **12** | **370h** | **Full system paper-trade ready** |

**Required pace:** ~31 hours/week (achievable with focused 4-5h/day)

---

### 26.6 Failure Scenarios + Protections

| # | Failure Scenario | Impact | Detection | Protection | Recovery |
|---|-----------------|--------|-----------|------------|----------|
| 1 | **RDE misclassifies regime** | Engines get wrong weights, wrong strategy active | LEL tracks regime accuracy weekly; compare predicted vs realized | Hysteresis prevents rapid switching; MDE requires 2+ engines agreeing; RSL caps max loss | Weekly HMM refit; increase CONFIRMATION_CANDLES |
| 2 | **Single engine goes rogue** (generates extreme signals) | Potential large loss if MDE trusts it | MDE checks: signal confidence capped at 0.95; single engine max weight 0.40; RSL daily loss cap | No single engine can override MDE; RSL has veto; max position 15% | Auto-prune engine weight to 0.05; alert for manual review |
| 3 | **Multiple engines fail simultaneously** | MDE gets no usable signals | MDE checks min_engines_agreeing=2; if <2, action=hold | System goes to HOLD; no new positions; RSL monitors existing | Alert owner; manual investigation; restart engines |
| 4 | **Black swan crash (>20% in 1 hour)** | Massive drawdown if positioned | RSL crash detection: price drop >10%/24h; vol >3x; liquidation cascade | Kill switch activates at -8% DD; CRASH_PANIC regime → Atlas weight 0.60 (max defensive); 90% cash | 24h cooldown; gradual re-entry; DCA in recovery regime |
| 5 | **Exchange API goes down** | Can't execute orders or close positions | Heartbeat monitoring; API timeout >10s; WebSocket disconnect detection | Failover to secondary exchange; cancel pending orders; local position tracking | Queue orders; retry with exponential backoff; manual alert |
| 6 | **Overfitting in ML models** | Models give false confidence, bleed in live | Walk-forward validation; out-of-sample Sharpe; compare paper vs backtest | Reject any strategy where backtest Sharpe > 2x live Sharpe; automatic model rollback | Retrain with larger window; reduce features; add regularization |
| 7 | **Liquidity crisis** | Can't exit positions at expected price | Spread monitoring; orderbook depth tracking; slippage > 0.5% triggers alert | Reduce position sizes in low-liquidity regime; limit order preference; max slippage check | Switch to higher-liquidity pairs; reduce overall exposure |
| 8 | **Data feed corruption** | Wrong features → wrong signals → wrong trades | Data validation: no NaN in critical fields; price > 0; timestamp monotonic; sanity checks | MarketSnapshot.validate() before any processing; stale data timeout (5 min) | Fallback to REST API polling; alert; use last known good snapshot |
| 9 | **Funding rate manipulation** | Helios funding arb generates false signals | Cross-reference multiple exchanges; historical funding percentile check | Funding signal capped at 0.3 contribution weight; RSL daily cap protects downside | Reduce Helios weight; switch to longer-term funding average |
| 10 | **Strategy decay** (alpha dies) | Gradual bleeding, death by 1000 cuts | LEL weekly Sharpe tracking per engine; 30d rolling < 0 for 2+ weeks → flag | Auto-reduce engine weight; MDE suppresses bad performers | Retrain/redesign strategy; replace with new engine; research new alpha |
| 11 | **Power failure / system crash** | Open positions unmanaged | PM2 auto-restart; exchange-side stop-loss orders (set at entry) | All positions have exchange-side SL; PM2 restarts within 30s | System resumes; reconcile positions; verify SL orders still active |
| 12 | **Correlation blow-up** (all positions move together) | Amplified drawdown | RSL correlation guard (max 0.7); MDE correlation penalty | Block correlated trades; if portfolio correlation > 0.8 → reduce all sizes by 50% | Close most correlated position; diversify across uncorrelated assets |

**Critical Design Principle:**

```
┌───────────────────────────────────────────────────────┐
│                                                       │
│   ARGUS IS DESIGNED TO SURVIVE ITS OWN FAILURES.     │
│                                                       │
│   • If RDE is wrong → MDE still requires consensus   │
│   • If 1 engine fails → 4 others still operate       │
│   • If MDE is aggressive → RSL has veto power        │
│   • If RSL misses something → exchange SL is backup  │
│   • If exchange is down → failover is ready           │
│   • If power fails → PM2 restarts in 30s             │
│   • If all else fails → kill switch at -8%           │
│                                                       │
│   NO SINGLE POINT OF FAILURE.                         │
│                                                       │
└───────────────────────────────────────────────────────┘
```

---

### 26.7 Backtest & Validation System (BVS) Requirements

**No strategy enters paper trading without passing ALL of these gates:**

| Gate | Test | Pass Criteria | Reject Criteria |
|------|------|--------------|-----------------|
| **G1: Walk-Forward** | 5-fold time series split, train 90d/test 30d | OOS Sharpe > 0.8 in 4/5 folds | Any fold Sharpe < 0 |
| **G2: Monte Carlo** | 1000 path permutations of trade order | 95th percentile max DD < 15% | Median DD > 10% |
| **G3: Slippage Stress** | Add 2x estimated slippage to all trades | Still profitable (PF > 1.2) | PF drops below 1.0 |
| **G4: Fee Stress** | Use maximum fee tier (0.1% maker+taker) | Still profitable (PF > 1.1) | PF drops below 1.0 |
| **G5: Regime Stress** | Test in worst regime for that engine | Loss < 5% over 30d | Loss > 10% in worst regime |
| **G6: Crash Test** | Simulate 2020 March, 2022 LUNA, 2022 FTX | Max DD < 12% | Max DD > 20% |
| **G7: Correlation** | Check signal correlation with existing engines | Correlation < 0.5 with all existing | Correlation > 0.7 with any |

---

### 26.8 Engineering Principles Summary

| Principle | Implementation |
|-----------|---------------|
| **No single point of failure** | 5 independent engines; RSL veto; exchange SL backup; PM2 restart |
| **Explainability** | Every decision logged with full reason chain; feature importance tracked |
| **Determinism + Adaptivity** | Deterministic core logic; adaptive weights via LEL; no randomness in production |
| **Capital-first mindset** | RSL has absolute veto; kill switch at -8%; daily loss caps; cooldowns |
| **Auditability** | Every trade: state→action→result→regime stored; weekly performance reports |
| **No hype** | All strategies must pass 7-gate BVS; OOS validation required; no backtest-only claims |
| **Deployable systems** | Every module has defined contract, test suite, and monitoring; no theoretical designs |

---

### 26.9 System Performance Targets (Post-12 Week Build)

| Metric | Target | Minimum Acceptable | Measurement Period |
|--------|--------|-------------------|--------------------|
| **Annual Return** | 60-100% | 30% | Rolling 12 months |
| **Sharpe Ratio** | > 1.5 | > 1.0 | Rolling 6 months |
| **Sortino Ratio** | > 2.0 | > 1.5 | Rolling 6 months |
| **Max Drawdown** | < 8% | < 12% | All time |
| **Win Rate** | > 55% | > 50% | Rolling 3 months |
| **Profit Factor** | > 1.8 | > 1.3 | Rolling 3 months |
| **Regime Detection Accuracy** | > 75% | > 65% | Weekly audit |
| **System Uptime** | 99.5% | 99.0% | Monthly |
| **Decision Latency** | < 2.5s | < 5s | Per candle |
| **Bull Market Alpha** | > BTC B&H | Positive | Per bull regime period |
| **Bear Market Return** | > 0% | > -5% | Per bear regime period |
| **Crash Survival** | DD < 10% | DD < 15% | Per crash event |
| **Chop Bleed** | < -1%/month | < -2%/month | Per chop regime period |

---

---

## 27. HOSTILE AUDIT: ARGUS v1.0 Critical Review & v2.0 Redesign

> **Review Authority:** CIO + Quant Research Director + System Auditor  
> **Review Date:** 2026-02-09  
> **Review Stance:** Adversarial. Assume external investor capital at risk.  
> **Verdict on v1.0:** Architecturally ambitious. Practically undeployable without major revision.  
> **Core Problem:** The system is over-engineered in complexity and under-engineered in depth. It has the skeleton of a hedge fund but the muscles of a retail bot.

---

### 27.1 SECTION A: Top 10 Critical Weaknesses (Ranked by Kill Potential)

**#1: RESOURCE DELUSION — 5 engines, 1 developer**

This is the single most dangerous flaw. A solo developer building 5 independent strategy engines will produce 5 shallow implementations, each with surface-level logic and untested edge cases. Renaissance has 300+ PhDs and runs fewer independent strategies than we've sketched.

- **Reality:** Each engine needs 200-400 hours of research, coding, backtesting, and regime-specific tuning. Orion alone (breakout + trend + momentum) is three strategies pretending to be one.
- **Fix:** Cut to 2 engines for v2.0. Master them. Add engines only after each one proves live profitability for 90+ days.

**#2: FALSE INDEPENDENCE — All engines consume the same data**

The architecture claims 5 "independent" engines. They are not independent. Every engine reads the same OHLCV data, the same features, and the same regime output. When BTC drops 10%, all engines see the same thing. The "independence" that would protect us through diversification does not exist.

- **The correlation penalty of 15% is cosmetic.** True correlation during stress events approaches 1.0 across all price-derived signals.
- **Fix:** True independence requires different data domains: price, flow, sentiment, on-chain, macro. Each engine must have at least one data source the others do not share.

**#3: HMM REGIME DETECTION IS A RESEARCH TRAP**

The 8-state Gaussian HMM looks elegant on paper. In practice:
- HMMs assume observations are generated by the hidden state. Markets don't work like this — regimes are emergent, not generative.
- 8 states with 5 features means fitting 8x5 means + 8x5x5 covariance matrices + 8x8 transition matrix = **288 parameters** from noisy, non-stationary financial data.
- Weekly refitting with expanding window will slowly overfit to the most recent regime, guaranteeing poor performance during the next regime transition.
- **The 4-candle hysteresis is arbitrary.** Why 4? Why not 2 or 12? No mathematical basis provided.

- **Fix:** Replace HMM with simpler, more robust approach: rule-based regime classification with 4 states (not 8), backed by a lightweight ML model (LightGBM on vol features) as a confirming secondary signal. 4 states: TRENDING, RANGING, VOLATILE, CRISIS. That's it. Anything more is false precision.

**#4: KELLY CRITERION WITH BAD INPUTS**

The MDE uses Kelly criterion for position sizing. Kelly requires accurate estimates of win_rate, avg_win, and avg_loss. In the first 6 months of operation, we will have:
- < 200 trades (probably < 100)
- Win rate estimate with standard error of ±5-8%
- avg_win/avg_loss ratio with massive variance

Half-Kelly on garbage inputs is still garbage. A 55% win rate ± 7% means Kelly could be sizing for anywhere between 48% (net loser) and 62% (great system). The position sizes will be erratic and unreliable.

- **Fix:** Use fixed fractional sizing (1-2% risk per trade) for the first 12 months. Transition to Kelly only after 500+ trades with stable statistics. This is how every surviving fund starts.

**#5: HERMES (SENTIMENT ENGINE) IS A LIABILITY, NOT AN ASSET**

Sentiment analysis on crypto social media is one of the most researched and least profitable edges in retail quant. Problems:
- No labeled training data for crypto-specific sentiment.
- DistilBERT fine-tuned on what? We have no dataset.
- Twitter/Reddit sentiment has near-zero predictive power beyond 15 minutes. By the time we process it, the move is done.
- Building an NLP pipeline is a 6-month project, not a 10-hour task.
- The 0.15 weight in MDE means even if it works perfectly, it contributes almost nothing.

- **Fix:** Remove Hermes entirely from v2.0. Replace with simple, high-signal inputs: CryptoPanic fear/greed score (free API), funding rate extremes (already available), and liquidation cascade detection (available from exchange data). These are quantifiable, not NLP-dependent.

**#6: BACKTEST VALIDATION IS NECESSARY BUT DECEPTIVE**

The 7-gate BVS looks rigorous. It is not sufficient. Problems:
- Walk-forward analysis on 2-3 years of crypto data is testing on a single market cycle. This is like testing a weather model on one season.
- Monte Carlo permutation of trade order assumes trades are independent. They are not — regime clustering means trades are auto-correlated.
- Slippage simulation at 2x estimated is arbitrary. During real stress events, slippage can be 10-50x normal.
- **The most critical test is missing:** out-of-distribution performance. What happens when the market does something it has never done before? Every significant loss in fund history comes from this scenario.

- **Fix:** Add: (1) Synthetic regime generation — artificially create regimes the system has never seen; (2) Adversarial testing — intentionally feed the system adversarial inputs; (3) Minimum 5+ years of data including 2020 crash, 2021 bull, 2022 bear, 2023 recovery; (4) Exchange outage simulation.

**#7: THE MDE WEIGHTED VOTING IS NAIVE CONSENSUS**

The MDE takes 5 engine signals, applies regime-specific weights, and produces a weighted average. This is a freshman-level ensemble. Problems:
- Weighted average destroys edge cases. If Orion screams "SELL at 0.95 confidence" but Aegean says "hold at 0.3", the average dilutes the strong signal.
- The weight tables are hand-designed, not learned. CRASH_PANIC gives Atlas 0.60 weight — why? What if Atlas's risk-on/off model is wrong during the crash?
- No concept of signal freshness. A signal from 4 hours ago is weighted the same as one from 30 seconds ago.
- No concept of conviction scaling — the difference between "barely long" and "screaming long" is collapsed into a single bias number.

- **Fix:** Replace weighted average with a hierarchical decision system: (1) RSL decides if we CAN trade; (2) Regime decides WHERE we are; (3) The single best-performing engine for this regime decides WHAT to do; (4) Atlas modifies sizing. Not consensus. Command chain.

**#8: NO TRANSACTION COST MODEL IN SIGNAL GENERATION**

Transaction costs (fees + spread + slippage + market impact) are treated as a backtest afterthought. In reality, transaction costs are the #1 killer of strategies that look good on paper.

- On Binance futures, round-trip cost is ~0.08-0.12% (maker/taker + spread).
- A strategy targeting 0.5% per trade needs to overcome 0.1% costs = 20% drag.
- Helios (scalping) targeting spread capture will be eaten alive by its own fees.
- **No signal should be generated without subtracting expected transaction costs from expected return first.**

- **Fix:** Every engine's expected_return must be NET of estimated transaction costs. If net expected return < 0.1%, the signal is noise, not alpha. Kill it at the source.

**#9: 12-WEEK TIMELINE IS FANTASY**

370 hours to build an institutional-grade trading system. Let me list what actually takes 370 hours:
- Reliable Binance WebSocket connection with reconnection logic: 40h
- Feature engineering pipeline with 100+ features, all tested: 80h
- One properly backtested and validated trading strategy: 100h
- Risk management system with kill switch: 40h
- That's 260h and we haven't even built the regime detector, MDE, execution engine, or any ML models.

- **Fix:** Honest timeline: 6 months for MVP (2 engines + regime + risk + basic execution). 12 months for production. 18 months before considering external capital. Plan for reality, not aspiration.

**#10: NO CONCEPT OF CAPACITY AND MARKET IMPACT**

The system assumes it can enter and exit positions without moving the market. At $100-$1000 AUM, this is true. At $100K, still mostly true. At $1M+? Depending on the pair, our orders ARE the market.

- No model for how our own orders affect price.
- No concept of optimal execution (TWAP, VWAP, iceberg orders).
- No measurement of realized market impact vs estimated.

- **Fix for now:** Not critical at current AUM. But build the measurement infrastructure from day 1 so we have data when scaling becomes relevant.

---

### 27.2 SECTION B: Missing Components

| # | Missing Component | Why It's Critical | Priority |
|---|-------------------|------------------|----------|
| 1 | **Funding Rate / Basis Engine** | Most reliable and measurable edge in crypto. Funding rate extremes predict mean-reversion with high accuracy. Currently buried inside Helios. Should be standalone. | P0 |
| 2 | **Inventory/Position Management Module** | System has no model of its own positions beyond basic tracking. Needs: time-in-position decay, unrealized PnL monitoring, partial take-profit ladder, position aging alerts. | P0 |
| 3 | **Cost Model as First-Class Citizen** | Transaction costs embedded in every signal, not bolted on in backtest. Fee tier tracking, spread estimation, slippage prediction model. | P0 |
| 4 | **Data Quality Monitor** | No validation that incoming data is correct. Exchanges send bad candles, duplicate timestamps, missing data. One corrupted candle → bad features → bad signal → bad trade. | P0 |
| 5 | **Regime Transition Model** | RDE classifies current regime but doesn't model transition probabilities. We need: what's the probability of moving FROM current regime TO each other regime? This changes risk budget. | P1 |
| 6 | **Alpha Decay Model** | No measurement of how fast a signal's edge is eroding. Every alpha decays. We need: rolling IC, rolling hit rate, regime-conditional decay rate. | P1 |
| 7 | **Synthetic Data Generator** | Cannot test rare events (crashes, flash crashes, exchange failures) without generating synthetic scenarios. Need: parametric scenario generation, historical splicing, adversarial sequences. | P1 |
| 8 | **Order Management System (OMS)** | No concept of pending order state, order lifecycle, amendment logic, or partial fill management. The current "executor" is a function call, not a system. | P1 |
| 9 | **Reconciliation Engine** | Exchange state and local state WILL diverge. Need: continuous reconciliation, discrepancy alerting, auto-correction logic, manual override interface. | P1 |
| 10 | **Audit Trail / Compliance Log** | Every decision, override, and error must be immutably logged with millisecond timestamps. Not for regulation (yet) — for debugging and post-mortem analysis. | P1 |
| 11 | **Configuration Versioning** | When parameters change, which trades were under which config? Need: config hashing, version tagging, parameter drift tracking. | P2 |
| 12 | **Graceful Degradation Framework** | What happens when a component dies? System needs: health checks per module, fallback behaviors defined per failure type, automatic escalation. | P1 |

---

### 27.3 SECTION C: Engine Redesign — v2.0 Proposal

#### Current Engines: Verdict

| Engine | Verdict | Reasoning |
|--------|---------|-----------|
| **Orion (Trend)** | KEEP but SPLIT | Contains 3 strategies pretending to be 1 engine. Breakout ≠ trend-following ≠ momentum. |
| **Aegean (Mean-Rev)** | KEEP but NARROW | VWAP reversion and statistical arb are fundamentally different strategies. Pick one. |
| **Atlas (Macro/Risk)** | REDESIGN | It's not an engine — it's a risk overlay. Stop pretending it generates trade signals. Make it what it is: a risk governor. |
| **Hermes (Sentiment)** | REMOVE | NLP sentiment is a research project, not a production signal. Zero proven edge. Resource drain. |
| **Helios (Scalp/Micro)** | REMOVE, extract funding | Scalping requires sub-second latency on co-located infrastructure. We have a laptop on WiFi. Funding rate arbitrage should be standalone. |

#### v2.0 Engine Architecture: 3 Engines + 2 Overlays

**PRINCIPLE:** Better to have 2 deep engines than 5 shallow ones.

**ENGINE 1: TITAN (Trend/Momentum Engine) — replaces Orion**

```
Purpose: Capture directional moves when the market is trending.
Active in: TRENDING regime only. Silent otherwise.
Sub-strategies:
  A) Trend Follow: EMA cross (21/55) + ADX>25 + ATR trailing stop
  B) Momentum Breakout: Donchian(20) breakout + volume confirmation + ATR filter
Signal quality gate: Only fires when ADX > 25 AND regime = TRENDING AND volume > 1.5x avg
Kill condition: 3 consecutive stops hit → go silent for 24h
Unique data: Multi-timeframe alignment (1h signal, 4h confirmation, 1d direction)
```

**ENGINE 2: NAUTILUS (Mean-Reversion/Range Engine) — replaces Aegean**

```
Purpose: Capture mean-reversion in ranging markets.
Active in: RANGING regime only. Silent otherwise.
Sub-strategies:
  A) Bollinger Reversion: Price touches BB(20,2) outer band + RSI extreme + volume decline
  B) Funding Rate Mean-Reversion: Funding rate > 95th percentile → fade the crowd
Signal quality gate: Only fires when ADX < 20 AND regime = RANGING AND spread < 0.05%
Kill condition: Price breaks range (closes outside BB by >1 ATR) → immediate exit + go silent
Unique data: Orderbook depth ratio, funding rate percentile, historical range boundaries
```

**ENGINE 3: PHOENIX (Carry/Basis Engine) — NEW, extracted from Helios**

```
Purpose: Capture funding rate and basis trade opportunities.
Active in: ALL regimes (carry is regime-independent).
Strategy:
  A) Funding Rate Harvest: When perpetual funding rate is extreme (>0.05%/8h or <-0.03%/8h),
     take the opposite side. Position sized by funding magnitude.
  B) Spot-Perp Basis: When basis between spot and perpetual deviates >0.3%,
     arb the convergence.
Signal quality gate: Funding must be extreme for 2+ consecutive periods (16h confirmation)
Kill condition: Basis diverges further instead of converging → cut at 0.5% adverse move
Unique data: Cross-exchange funding comparison, historical funding percentiles, OI concentration
```

**OVERLAY 1: ATLAS (Risk Governor) — redesigned from engine to overlay**

```
Purpose: NOT a trade signal generator. A risk multiplier/reducer.
Function: Modifies position sizes and leverage limits based on macro risk state.
Inputs: BTC dominance trend, total market cap momentum, DXY proxy, VIX proxy,
        cross-asset correlation regime, stablecoin market cap flow
Output: risk_multiplier (0.0 to 1.5)
  - RISK_ON (multiplier 1.0-1.5): Crypto market cap rising, DXY falling, low correlation
  - RISK_NEUTRAL (multiplier 0.7-1.0): Mixed signals
  - RISK_OFF (multiplier 0.2-0.5): Correlation spiking, DXY rising, market cap declining
  - CRISIS (multiplier 0.0): Extreme stress indicators → no new positions allowed
Application: Every engine's position_size *= atlas_risk_multiplier
```

**OVERLAY 2: SENTINEL (Data Quality + Anomaly Detection) — NEW**

```
Purpose: Detect data anomalies, exchange issues, and market microstructure warnings
        BEFORE they corrupt signals.
Monitors:
  - Data staleness (no new candle for >2x expected interval)
  - Price anomalies (>3 sigma move in 1 candle without volume confirmation)
  - Spread blowout (>5x normal spread → liquidity crisis)
  - Exchange latency spike (API response >2s)
  - Orderbook depth collapse (<30% of normal depth within 5% of mid)
  - Funding rate flash spike (>10x normal in 1 period)
Output: data_quality_score (0.0 to 1.0)
  - If score < 0.7 → reduce all engine confidence by 30%
  - If score < 0.4 → halt all new trades until resolved
  - If score < 0.2 → EMERGENCY: close all positions, alert owner
```

#### Engine Interaction Model (v2.0):

```
MarketSnapshot
      │
      ├───► SENTINEL (data quality check)
      │         │
      │         ▼ data_quality_score
      │
      ├───► REGIME DETECTOR (4-state, not 8)
      │         │
      │         ▼ regime + confidence
      │
      ├───► TITAN ──────────┐
      │     (only if TRENDING) │
      │                        │
      ├───► NAUTILUS ──────────┼───► SELECTOR (pick active engine)
      │     (only if RANGING)  │         │
      │                        │         ▼
      ├───► PHOENIX ───────────┘    Best signal for current regime
      │     (always active)              │
      │                                  ▼
      └───► ATLAS ──────────────► risk_multiplier
                                         │
                                         ▼
                                    POSITION SIZER
                                    (fixed fractional, NOT Kelly)
                                         │
                                         ▼
                                       RSL
                                    (veto/approve)
                                         │
                                         ▼
                                    EXECUTION
```

**KEY CHANGE:** No voting. No weighted consensus. One engine leads per regime. Atlas modifies size. RSL approves or kills. Command chain, not committee.

---

### 27.4 SECTION D: Improved Feature Set

#### Problems with Current Feature Set

1. **100+ features is a red flag.** Most will be noise. The curse of dimensionality means more features = more overfitting unless we have millions of training samples (we don't).
2. **Features are generic TA indicators.** RSI, MACD, BB — these are in every retail bot. They contain no alpha that isn't already priced in.
3. **No features from the unique properties of crypto markets:** funding rates, liquidation cascades, stablecoin flows, miner behavior, exchange reserves.
4. **No concept of feature decay.** A feature that worked 6 months ago may be arbitraged away.

#### v2.0 Feature Architecture: Quality Over Quantity

**TIER 1: Core Features (Always Computed, High Signal) — 25 features**

| # | Feature | Category | Rationale |
|---|---------|----------|-----------|
| 1 | **ATR(14) / Price** | Volatility | Normalized volatility, regime-defining |
| 2 | **ATR(5) / ATR(20)** | Volatility | Vol expansion/compression ratio |
| 3 | **Realized Vol (20d annualized)** | Volatility | Absolute vol level |
| 4 | **Parkinson Vol** | Volatility | Uses high-low range, more efficient estimator |
| 5 | **ADX(14)** | Trend | Trend strength, regime-defining |
| 6 | **Price vs MA(200)** | Trend | Bull/bear regime separator |
| 7 | **EMA(21) vs EMA(55)** | Trend | Trend direction and crossover |
| 8 | **Linear Regression Slope (20)** | Trend | Trend velocity |
| 9 | **RSI(14)** | Momentum | Overbought/oversold, mean-rev input |
| 10 | **BB %B (20,2)** | Momentum | Position within Bollinger Band |
| 11 | **BB Width (20,2)** | Volatility | Squeeze detection |
| 12 | **Volume / MA(20 volume)** | Volume | Relative volume (participation) |
| 13 | **OBV slope (10)** | Volume | Accumulation/distribution trend |
| 14 | **VWAP deviation %** | Microstructure | Distance from fair value |
| 15 | **Bid-Ask Spread (normalized)** | Microstructure | Liquidity state |
| 16 | **Orderbook Imbalance** | Microstructure | (bid_depth - ask_depth) / total |
| 17 | **Funding Rate (raw)** | Crypto-native | Crowding indicator |
| 18 | **Funding Rate Percentile (30d)** | Crypto-native | How extreme is current funding |
| 19 | **OI Change % (4h)** | Crypto-native | New money entering/leaving |
| 20 | **Liquidation Estimate** | Crypto-native | Cascade risk |
| 21 | **BTC Dominance Delta (24h)** | Cross-asset | Risk appetite indicator |
| 22 | **BTC-ETH Correlation (30d rolling)** | Cross-asset | Correlation regime |
| 23 | **Stablecoin Market Cap Delta** | Cross-asset | Money flow in/out of crypto |
| 24 | **Return Serial Correlation (20)** | Statistical | Trending vs mean-reverting |
| 25 | **Hurst Exponent (100)** | Statistical | Persistence vs anti-persistence |

**TIER 2: Derived / ML Features (Computed Periodically) — 15 features**

| # | Feature | Category | Compute |
|---|---------|----------|---------|
| 26 | **Chronos Price Forecast (24h median)** | ML | GPU, hourly |
| 27 | **Chronos Confidence Width (90-10 quantile)** | ML | GPU, hourly |
| 28 | **Chronos Vol Forecast** | ML | GPU, 4-hourly |
| 29 | **LightGBM Direction Prediction** | ML | CPU, per candle |
| 30 | **LightGBM Prediction Confidence** | ML | CPU, per candle |
| 31 | **Meta-Label: Trade Quality Score** | ML | CPU, per signal |
| 32 | **Fractional Differentiation of Price** | Derived | CPU, per candle |
| 33 | **Shannon Entropy (returns, 50)** | Derived | CPU, per candle |
| 34 | **CUSUM Event Flag** | Derived | CPU, per candle |
| 35 | **Regime Probability (TRENDING)** | Regime | CPU, per candle |
| 36 | **Regime Probability (RANGING)** | Regime | CPU, per candle |
| 37 | **Regime Probability (VOLATILE)** | Regime | CPU, per candle |
| 38 | **Regime Probability (CRISIS)** | Regime | CPU, per candle |
| 39 | **Rolling IC of top features (30d)** | Meta | CPU, daily |
| 40 | **Feature Importance Rank Shift** | Meta | CPU, weekly |

**TIER 3: Structural / Positioning Features (Research Phase) — 10 features**

| # | Feature | Category | Availability |
|---|---------|----------|-------------|
| 41 | **Exchange Net Flow (BTC)** | On-chain | Glassnode/CryptoQuant |
| 42 | **Miner Outflow** | On-chain | Glassnode |
| 43 | **MVRV Z-Score** | On-chain | Glassnode |
| 44 | **Realized Price / Market Price** | On-chain | CoinGecko |
| 45 | **Term Structure (funding curve)** | Positioning | Exchange quarterly futures |
| 46 | **Put/Call Ratio (BTC options)** | Positioning | Deribit |
| 47 | **Max Pain (BTC options)** | Positioning | Deribit |
| 48 | **Implied Vol vs Realized Vol** | Vol surface | Deribit |
| 49 | **Dollar Strength (DXY proxy)** | Macro | FRED / Yahoo Finance |
| 50 | **US 10Y yield delta** | Macro | FRED |

**TOTAL: 50 features. Not 100+.**

**Rule: Every feature must justify its existence with IC > 0.02 over 6+ months of OOS data, or it is removed. Feature court is held monthly.**

---

### 27.5 SECTION E: Regime Detection v2.0 — Redesign

#### Problems with v1.0 RDE

1. **8 states is false precision.** With 1h candles and 2 years of data (~17,000 obs), fitting an 8-state HMM is statistically irresponsible. Rule of thumb: need 1000+ observations per state per feature. We have 2,125 per state. Barely sufficient for 5 features. Will overfit.
2. **HMM assumptions are wrong for markets.** HMM assumes: (a) observations depend only on current state, (b) transitions are Markov (memoryless). Markets have long memory, momentum, and path-dependency. HMM cannot model this.
3. **No concept of "uncertain" regime.** The system must classify into one of 8 states. What if the market is genuinely ambiguous? Forcing a classification introduces false confidence.
4. **Hysteresis is a band-aid.** The 4-candle hysteresis delays the correct classification without preventing the incorrect one. During genuine regime transitions, 4 candles = 4 hours of lag while running the wrong strategy.

#### v2.0 Regime Detection: Pragmatic + Robust

**4 States (not 8):**

| State | Definition | Detection | Confidence Required |
|-------|------------|-----------|-------------------|
| **TRENDING** | Directional movement with strength | ADX(14) > 25 AND price directionally aligned with MA(50) for 20+ candles | 3 of 4 indicators agree |
| **RANGING** | Bounded oscillation | ADX(14) < 20 AND price within BB(20,2) for 20+ candles AND Hurst < 0.4 | 3 of 4 indicators agree |
| **VOLATILE** | High volatility, direction uncertain | ATR(5)/ATR(20) > 1.8 OR realized vol > 2x 60d median | Any 1 indicator sufficient |
| **CRISIS** | Extreme stress, capital preservation mode | Price drop >8% in 24h OR vol >3x 60d median OR liquidation cascade detected | Any 1 indicator sufficient |

**Why 4 not 8:**
- TRENDING covers both bull and bear (direction handled by the engine, not the regime)
- VOL_COMPRESSION is not a tradeable regime — it's a "wait for breakout" state, which TRENDING already handles
- RECOVERY is just early TRENDING after CRISIS
- CHOP is RANGING with lower ADX — no different strategy needed

**Detection Method: Rule-Based Primary + LightGBM Secondary**

```python
class RegimeDetectorV2:
    """
    Primary: Deterministic rules (fast, explainable, no overfit)
    Secondary: LightGBM classifier (learned, higher accuracy, retrained monthly)
    Agreement required for high-confidence classification.
    """
    
    def detect(self, features: pd.Series) -> RegimeOutput:
        # ── FAST PATH: Crisis detection (no delay, no consensus needed) ──
        if features['price_change_24h'] < -0.08:
            return RegimeOutput(regime="CRISIS", confidence=0.95, stability=0.1)
        if features['atr_ratio_5_20'] > 3.0:
            return RegimeOutput(regime="CRISIS", confidence=0.90, stability=0.1)
        if features['liquidation_estimate'] > self.LIQUIDATION_THRESHOLD:
            return RegimeOutput(regime="CRISIS", confidence=0.85, stability=0.2)
        
        # ── PRIMARY: Rule-based classification ──
        rule_regime = self._rule_based(features)
        
        # ── SECONDARY: LightGBM confirmation ──
        ml_probs = self.lgbm_model.predict_proba(features)
        ml_regime = max(ml_probs, key=ml_probs.get)
        ml_confidence = ml_probs[ml_regime]
        
        # ── AGREEMENT CHECK ──
        if rule_regime == ml_regime:
            confidence = min(0.95, ml_confidence * 1.1)  # Boost for agreement
            stability = 0.8
        else:
            # Disagreement: use rule-based (more robust), lower confidence
            confidence = min(ml_confidence, 0.6)  # Cap at 0.6
            stability = 0.4
        
        # ── TRANSITION GUARD ──
        if rule_regime != self.current_regime:
            self.pending_transition = rule_regime
            self.transition_count += 1
            if self.transition_count < 3:  # 3 candles confirmation
                return RegimeOutput(
                    regime=self.current_regime,
                    confidence=confidence * 0.7,
                    stability=0.3,
                    pending_transition=rule_regime
                )
            else:
                self.current_regime = rule_regime
                self.transition_count = 0
        else:
            self.transition_count = 0
        
        return RegimeOutput(
            regime=self.current_regime,
            confidence=round(confidence, 3),
            stability=round(stability, 3)
        )
    
    def _rule_based(self, f):
        # VOLATILE takes precedence over TRENDING/RANGING
        if f['atr_ratio_5_20'] > 1.8 or f['realized_vol'] > 2 * f['realized_vol_60d_median']:
            return "VOLATILE"
        if f['adx'] > 25 and abs(f['lr_slope_20']) > 0.001:
            return "TRENDING"
        if f['adx'] < 20 and f['hurst'] < 0.45:
            return "RANGING"
        # Ambiguous zone: default to RANGING (safer — smaller positions)
        return "RANGING"
```

**Key improvements over v1.0:**
- Crisis detection is instant (no hysteresis — when the house is on fire, don't wait to confirm)
- Rule-based primary = no overfitting, fully explainable
- LightGBM secondary = captures non-linear patterns rules miss
- Agreement required = high confidence only when both methods agree
- Ambiguity defaults to RANGING = conservative default

---

### 27.6 SECTION F: MDE v2.0 — Command Chain, Not Committee

#### Why Voting Fails

Voting works in elections. It fails in trading. Why:
- The market rewards conviction, not compromise
- Averaging a strong sell with a weak buy produces a meaningless "slight sell"
- Committee decisions are always late
- Accountability is diffused — nobody owns the trade

#### v2.0: Regime-Gated Engine Selection

```python
class MetaDecisionEngineV2:
    """
    NOT a voting system. A routing system.
    Regime determines which engine has command authority.
    Only 1 engine leads at a time.
    Atlas modifies, RSL approves, Sentinel monitors.
    """
    
    REGIME_TO_LEAD_ENGINE = {
        "TRENDING": "TITAN",
        "RANGING":  "NAUTILUS",
        "VOLATILE": "PHOENIX",    # Carry trade is most robust in high vol
        "CRISIS":   None          # No engine leads in crisis. Capital preservation only.
    }
    
    def decide(self, regime, engine_signals, portfolio, risk_state):
        
        # ── CRISIS OVERRIDE: No trading. Period. ──
        if regime.regime == "CRISIS":
            if portfolio.has_positions:
                return Decision(action="close_all", reason="CRISIS regime active")
            return Decision(action="hold", reason="CRISIS regime — no new positions")
        
        # ── GET LEAD ENGINE ──
        lead_engine_name = self.REGIME_TO_LEAD_ENGINE[regime.regime]
        lead_signal = engine_signals[lead_engine_name]
        
        # ── PHOENIX ALWAYS ACTIVE (carry trades are regime-independent) ──
        phoenix_signal = engine_signals.get("PHOENIX")
        
        # ── SIGNAL QUALITY GATE ──
        if lead_signal.confidence < 0.50:
            # Lead engine doesn't have conviction. Don't trade.
            # Check if Phoenix has a carry opportunity
            if phoenix_signal and phoenix_signal.confidence > 0.60:
                lead_signal = phoenix_signal
                lead_engine_name = "PHOENIX"
            else:
                return Decision(action="hold", reason=f"{lead_engine_name} confidence too low: {lead_signal.confidence}")
        
        # ── NET EXPECTED RETURN GATE ──
        estimated_cost = self._estimate_transaction_cost(portfolio)
        net_return = lead_signal.expected_return - estimated_cost
        if net_return < 0.001:  # Less than 0.1% net expected return
            return Decision(action="hold", reason=f"Net return after costs too low: {net_return:.4f}")
        
        # ── ATLAS RISK MULTIPLIER ──
        atlas_multiplier = self.atlas_overlay.get_risk_multiplier()
        
        # ── SENTINEL DATA QUALITY CHECK ──
        sentinel_score = self.sentinel.get_quality_score()
        if sentinel_score < 0.4:
            return Decision(action="hold", reason=f"Data quality too low: {sentinel_score}")
        
        # ── POSITION SIZING: Fixed Fractional ──
        base_risk_pct = 0.02  # 2% risk per trade
        
        # Adjustments:
        size_multiplier = 1.0
        size_multiplier *= atlas_multiplier                      # Macro risk adjustment
        size_multiplier *= min(sentinel_score, 1.0)              # Data quality adjustment
        size_multiplier *= min(regime.confidence, 1.0)           # Regime confidence adjustment
        size_multiplier *= self._drawdown_multiplier(risk_state)  # DD adjustment
        
        position_risk_pct = base_risk_pct * size_multiplier
        position_risk_pct = min(position_risk_pct, 0.03)  # HARD CAP: never risk >3% per trade
        position_risk_pct = max(position_risk_pct, 0.005) # FLOOR: minimum 0.5% if trading
        
        # ── STOP LOSS: ATR-based ──
        atr = lead_signal.atr if hasattr(lead_signal, 'atr') else 0.02
        stop_distance = max(atr * 2.0, 0.01)   # 2x ATR, minimum 1%
        stop_distance = min(stop_distance, 0.05) # Maximum 5%
        
        position_size = position_risk_pct / stop_distance  # Risk-based sizing
        position_size = min(position_size, 0.15)            # Max 15% of portfolio
        
        # ── LEVERAGE: Conservative ──
        max_leverage = {"TRENDING": 2.0, "RANGING": 1.5, "VOLATILE": 1.0, "CRISIS": 1.0}
        leverage = min(1.0 + (lead_signal.confidence - 0.5), max_leverage[regime.regime])
        leverage = max(leverage, 1.0)
        
        return Decision(
            action=lead_signal.bias,  # "long" or "short"
            position_size=round(position_size, 4),
            leverage=round(leverage, 2),
            stop_loss=round(stop_distance, 4),
            confidence=round(lead_signal.confidence * regime.confidence, 3),
            reason=f"Lead={lead_engine_name}, Regime={regime.regime}, "
                   f"Atlas={atlas_multiplier:.2f}, Sentinel={sentinel_score:.2f}",
            engine=lead_engine_name
        )
    
    def _drawdown_multiplier(self, risk_state):
        dd = abs(risk_state.current_drawdown)
        if dd < 0.02: return 1.0     # <2% DD: full speed
        if dd < 0.04: return 0.5     # 2-4% DD: half speed
        if dd < 0.06: return 0.25    # 4-6% DD: quarter speed
        return 0.0                    # >6% DD: no new trades
    
    def _estimate_transaction_cost(self, portfolio):
        """Estimate round-trip cost including spread, fees, slippage."""
        base_fee = 0.0008   # 0.08% round-trip (maker+taker)
        est_spread = 0.0003  # 0.03% typical spread
        est_slippage = 0.0002 # 0.02% estimated slippage
        return base_fee + est_spread + est_slippage  # ~0.13% total
```

---

### 27.7 SECTION G: RSL v2.0 — Risk Layer Hardening

#### New Risk Rules

| # | Rule | v1.0 | v2.0 Change | Rationale |
|---|------|------|-------------|-----------|
| 1 | Daily Loss Cap | -2%/-3% | **-1.5%/-2.5%** | With $100-$1000 AUM, even -2% is -$20. Tighten early, loosen with proven track record. |
| 2 | Max Drawdown | -8% kill | **-6% kill** | -8% from $100 = $8 lost. But at $10K, it's $800. Tighter DD preserves compounding. |
| 3 | Regime-aware limits | None | **CRISIS regime = 0% new exposure** | Don't just reduce size in crisis. Eliminate new risk entirely. |
| 4 | Correlation guard | 0.7 threshold | **0.6 threshold + regime adjustment** | In stress, correlations spike to 0.9+. Must block before stress. |
| 5 | Time-of-day filter | None | **No new trades 15min before/after funding** | Funding rate settlement causes predictable volatility spikes |
| 6 | Weekend filter | None | **Reduce max position 50% on weekends** | Lower liquidity, wider spreads, fewer participants |
| 7 | News event filter | None | **No new trades 30min before major scheduled events** | CPI, FOMC, etc. create unpredictable gaps |
| 8 | Profit protection | None | **Trail portfolio-level stop: if up >5% from low, trail at 50% of gain** | Lock in profits, don't give back winners |
| 9 | Single-trade max loss | None | **Any single trade loss > 3% of portfolio = immediate close + 4h cooldown** | One bad trade should not be a catastrophe |
| 10 | Equity curve monitoring | None | **If equity curve crosses below 20d MA → reduce all sizes by 50%** | Trade the system like a stock: cut when it's declining |

#### Kill Switch v2.0 Protocol

```
LEVEL 0: NORMAL OPERATION
  All systems go. Engines active. Full position sizing.

LEVEL 1: CAUTION (DD > 2% OR daily loss > 1%)
  ├── Position sizes reduced to 75%
  ├── Max leverage capped at 1.5x
  ├── Alert sent to Telegram
  └── Log escalation reason

LEVEL 2: DEFENSIVE (DD > 4% OR daily loss > 1.5% OR 3 consecutive losses)
  ├── Position sizes reduced to 40%
  ├── No new positions allowed
  ├── Max leverage 1.0x (no leverage)
  ├── Only PHOENIX (carry) trades allowed
  ├── Alert sent to Telegram (URGENT)
  └── Manual review recommended

LEVEL 3: HALT (DD > 6% OR daily loss > 2.5% OR CRISIS regime + positions)
  ├── ALL positions closed at market
  ├── System halted for 24 hours MINIMUM
  ├── Owner must manually restart
  ├── Full post-mortem required before restart
  ├── CRITICAL alert to all channels
  └── Parameters reviewed before any new trade

LEVEL 4: LOCKDOWN (DD > 10% - should never reach this)
  ├── System halted INDEFINITELY
  ├── No automated restart possible
  ├── Full strategy audit required
  ├── Consider: is the system fundamentally broken?
  └── Manual trading only until root cause identified
```

---

### 27.8 SECTION H: Execution v2.0

#### Current Execution: Problems

1. No order type intelligence — everything is market orders
2. No concept of urgency-based execution
3. No measurement of execution quality
4. No handling of exchange rate limits

#### v2.0 Execution Architecture

| Urgency Level | When | Order Type | Max Slippage | Timeout |
|--------------|------|-----------|-------------|---------|
| **EMERGENCY** | Kill switch, stop loss | Market order | Unlimited (just get out) | Immediate |
| **HIGH** | Strong signal (conf > 0.8) | Aggressive limit (mid + 1 tick) | 0.1% | 30 seconds, then market |
| **NORMAL** | Standard signal | Limit at mid | 0.05% | 60 seconds, then cancel |
| **LOW** | Carry trade, rebalance | Passive limit (best bid/ask) | 0.03% | 5 minutes, then cancel |

**Execution Quality Metrics (tracked per trade):**

| Metric | Definition | Target |
|--------|-----------|--------|
| **Implementation Shortfall** | Actual fill vs decision price | < 0.05% |
| **Slippage** | Fill vs mid at order time | < 0.03% avg |
| **Fill Rate** | Filled / Attempted | > 85% for limit orders |
| **Time to Fill** | Order sent → fully filled | < 30s for HIGH urgency |
| **Cost vs TWAP** | Our cost vs theoretical TWAP | Within 0.02% |

---

### 27.9 SECTION I: Learning System v2.0 — Guarding Against Self-Deception

#### Overfitting Risks in Current LEL

1. **Auto-pruning creates survivorship bias.** If we prune strategies that underperform, we only keep strategies that happened to work recently. This is not the same as strategies that will work going forward.
2. **Feature importance drift → parameter instability.** Reacting to weekly feature importance changes creates a system that is always chasing yesterday's edge.
3. **RL-ready dataset → RL danger.** Reinforcement learning on financial data has near-zero successful production deployments in crypto. The state space is too large, reward is too sparse, and non-stationarity breaks RL's core assumptions.
4. **Performance attribution without causation.** Saying "Orion contributed +2% this month" doesn't mean Orion will contribute next month. Correlation ≠ causation applies to our own system's analysis.

#### v2.0 Learning System: Conservative Evolution

```
RESEARCH PIPELINE (monthly cadence):

  1. MEASURE (weekly)
     ├── Rolling 30d Sharpe per engine
     ├── Rolling IC per feature (top 25)
     ├── Regime accuracy vs realized
     ├── Execution quality metrics
     └── Cost analysis

  2. DIAGNOSE (bi-weekly)
     ├── Is performance decline due to:
     │   ├── A) Regime change → temporary, wait it out
     │   ├── B) Alpha decay → permanent, need new signal
     │   ├── C) Implementation bug → fix immediately
     │   └── D) Bad luck → statistically normal variance
     └── Decision: wait / investigate / fix / replace

  3. EVOLVE (monthly, ONLY if evidence is overwhelming)
     ├── Parameter changes: requires 90d OOS evidence
     ├── Feature changes: requires IC test + walk-forward
     ├── Engine changes: requires 6+ month research cycle
     └── ALL changes go through paper trading first (30d minimum)

  4. RECORD (continuous)
     ├── Every decision logged immutably
     ├── Config version tagged to every trade
     ├── Monthly performance review document
     └── Quarterly strategy review meeting (even if solo)
```

**Evolution Rules:**
- No parameter change without 90d OOS evidence
- No new feature without IC > 0.02 for 6+ months OOS
- No new engine without 6 months of paper trading
- No removal of engine without 3+ months of underperformance AND identified root cause
- All changes paper-traded for 30d before live deployment
- **The system's default behavior is: change nothing.** The burden of proof is on the proposed change, not on the status quo.

---

### 27.10 SECTION J: Kill Scenarios — How ARGUS Dies

| # | Scenario | How It Kills Us | Current Protection | Fix |
|---|----------|----------------|-------------------|-----|
| 1 | **Regime detector stuck in wrong state** | TITAN runs in RANGING market, bleeds through repeated stops | 4-candle hysteresis (too slow) | v2.0: Rule-based primary + ML secondary. If they disagree, default to RANGING (conservative). Max 3 candle delay. Separate CRISIS instant-detection. |
| 2 | **Flash crash + exchange API down simultaneously** | Can't close positions during 30% drop | Exchange-side stop-loss (unreliable during exchange overload) | Pre-set OCO orders on exchange at all times. Positions without exchange-side SL are forbidden. Secondary exchange account for emergency exits. |
| 3 | **Slow bleed in chop (death by 1000 cuts)** | -0.3% per day, no single loss triggers kill switch, but DD accumulates | Daily loss cap at -2% (chop losses are often -0.5% to -1%, below radar) | Equity curve MA filter: if equity < MA(20d), system goes DEFENSIVE (Level 2). Detects slow decay that daily caps miss. |
| 4 | **Correlated crash across all held positions** | BTC and ETH drop together, portfolio drops 2x expected | Correlation guard at 0.7 | Stress-test correlation: measure tail correlation (not Pearson — use lower-tail dependence coefficient). Reject positions where tail correlation > 0.5. Limit total crypto exposure to 80% of portfolio; 20% always in stablecoin. |
| 5 | **ML model silently degrades** | LightGBM accuracy drops from 58% to 51% over 3 months, nobody notices | LEL weekly Sharpe tracking | Hard circuit breaker: if any ML model's rolling 30d accuracy < 52%, disable its signal immediately. Automatic fallback to rules-only mode. |
| 6 | **Stablecoin depeg event** | USDT depegs to $0.95, our "safe" stablecoin position loses 5% | Nothing in current design | Diversify across USDT + USDC + DAI. Max 50% in any single stablecoin. Monitor stablecoin peg continuously. If any stable drops below $0.99, exit immediately. |
| 7 | **Regulatory black swan** | Country bans crypto trading, exchange freezes accounts | Nothing | Geographic exchange diversification. Never >70% of capital on one exchange. Decentralized exchange fallback (DEX) for emergency exits. |
| 8 | **Data poisoning** | Exchange sends manipulated candle data (wash trading, fake volume) | Basic data validation (price > 0, no NaN) | Cross-exchange data validation: compare candle from Binance vs Bybit vs CoinGecko. If >1% divergence, flag data as unreliable and halt signals until resolved. |
| 9 | **Strategy crowding** | Everyone runs the same strategies (EMA cross, BB bounce), alpha goes to zero | Feature importance drift tracking (too slow) | Monthly alpha decay measurement: if rolling OOS IC drops below 0.01, the feature/signal is considered dead. Research new signals proactively, don't wait for death. |
| 10 | **Developer error (the real #1 risk)** | Bug in position sizing → 10x intended size. Bug in stop loss → no stop. Bug in regime → wrong engine. | Unit tests + integration tests | Mandatory: (1) Shadow mode for all new code (run parallel with no real orders for 48h); (2) Position size hard cap in exchange API wrapper (physical limit, not logical); (3) Pre-trade validation: max order size check, max leverage check, max daily trades check, all at the exchange API layer, not in strategy code. |

---

### 27.11 SECTION K: Organizational Design (If This Were a Real Fund)

Even as a solo developer, thinking in terms of organizational roles creates discipline:

#### Roles (All Performed by Founder, But Wearing Different Hats)

| Role | Responsibility | When to Wear This Hat |
|------|---------------|----------------------|
| **Portfolio Manager** | Final approval on risk limits, new engine deployment, capital allocation | Weekly review meeting (yes, with yourself) |
| **Quant Researcher** | Strategy design, feature research, backtesting, validation | Dedicated research blocks (NOT during trading hours) |
| **Risk Manager** | Monitor RSL, review kill scenarios, audit drawdowns | Daily: 10-minute risk review at 00:00 UTC |
| **Engineer** | Code, test, deploy, debug, infrastructure | Dedicated dev blocks |
| **Auditor** | Monthly: review all decisions, check for biases, validate performance claims | Monthly review (hostile self-review) |

#### Approval Pipeline (Self-Governance)

```
NEW IDEA
    │
    ▼
RESEARCH (Quant hat)
    │ Write hypothesis, backtest, walk-forward
    │ Minimum 40 hours research before any code
    ▼
REVIEW (Auditor hat)
    │ Challenge assumptions. Try to break it.
    │ Ask: "Would I bet someone else's money on this?"
    ▼
PAPER TRADE (Engineer hat)
    │ 30 days minimum paper trading
    │ Compare paper vs backtest: if gap > 30%, reject
    ▼
RISK APPROVAL (Risk Manager hat)
    │ Does it fit within risk budget?
    │ What's the worst case?
    │ What kills this strategy?
    ▼
DEPLOY (PM hat)
    │ Start at 25% of target allocation
    │ Scale up over 3 months if results hold
    ▼
MONITOR (All hats)
    │ Weekly performance review
    │ Monthly strategy court
    │ Quarterly full audit
```

---

### 27.12 SECTION L: v2.0 Development Roadmap (Realistic Timeline)

**Principle: Build less, build deeper, validate harder.**

#### Phase 1: Foundation (Month 1-2, ~120 hours)

| Week | Deliverable | Hours | Gate |
|------|------------|-------|------|
| 1-2 | Data pipeline: Binance WS + feature engine (25 Tier 1 features) | 40 | Data flowing, features validated |
| 3-4 | Regime Detector v2.0 (rule-based + LightGBM) | 30 | Accuracy >70% on historical data |
| 5-6 | RSL v2.0 (all rules + kill switch levels) | 20 | Stress tested with synthetic scenarios |
| 7-8 | Backtest engine + walk-forward framework | 30 | Can run any strategy through full validation |
| **Phase 1 Total** | | **120h** | System can detect regime and manage risk, but not trade |

#### Phase 2: First Engine — TITAN (Month 3-4, ~100 hours)

| Week | Deliverable | Hours | Gate |
|------|------------|-------|------|
| 9-10 | TITAN engine: trend follow + momentum breakout | 30 | Signals generate correctly |
| 11-12 | TITAN backtesting: walk-forward, Monte Carlo, regime stress | 30 | Passes 7-gate BVS |
| 13-14 | MDE v2.0 (single-engine routing) + execution engine | 20 | End-to-end paper trade works |
| 15-16 | Paper trading: TITAN only, 30 days minimum | 20 | Paper Sharpe > 0.8, DD < 5% |
| **Phase 2 Total** | | **100h** | One profitable, validated engine in paper trading |

#### Phase 3: Second Engine — NAUTILUS (Month 5-6, ~80 hours)

| Week | Deliverable | Hours | Gate |
|------|------------|-------|------|
| 17-18 | NAUTILUS engine: BB reversion + funding rate MR | 25 | Signals generate correctly |
| 19-20 | NAUTILUS backtesting + regime stress tests | 25 | Passes 7-gate BVS |
| 21-22 | Dual-engine paper trading (TITAN + NAUTILUS, 30 days) | 15 | Combined Sharpe > 1.0 |
| 23-24 | Telegram bot + basic monitoring dashboard | 15 | Can monitor and control remotely |
| **Phase 3 Total** | | **80h** | Two engines, regime-gated, paper-traded |

#### Phase 4: ML Integration + Carry Engine (Month 7-9, ~120 hours)

| Week | Deliverable | Hours | Gate |
|------|------------|-------|------|
| 25-28 | LightGBM direction model + Triple Barrier labels | 30 | OOS accuracy > 55% |
| 29-32 | Chronos-Bolt integration (zero-shot + fine-tune) | 25 | MAPE < 5% on 1h forecasts |
| 33-34 | PHOENIX carry engine | 20 | Funding arb profitable in backtest |
| 35-36 | Atlas overlay + Sentinel overlay | 20 | Risk adjustment working in paper |
| 37-38 | Full system paper trade (all 3 engines + overlays, 30 days) | 25 | System Sharpe > 1.0, DD < 4% |
| **Phase 4 Total** | | **120h** | Full system paper-trade ready |

#### Phase 5: Live Deployment (Month 10-12, ~80 hours)

| Week | Deliverable | Hours | Gate |
|------|------------|-------|------|
| 39-40 | Micro-live: $10-$20 capital, real trades | 20 | No bugs, execution quality OK |
| 41-44 | Gradual scale: $20 → $50 → $100 | 20 | Live Sharpe > 0.6, DD < 5% |
| 45-48 | LEL v2.0: performance tracking, alpha decay, monthly review | 20 | System self-monitors correctly |
| 49-52 | Hardening: edge cases, stress tests, documentation | 20 | Production-ready |
| **Phase 5 Total** | | **80h** | Live trading with proven track record |

#### Timeline Summary

| Phase | Duration | Hours | Milestone |
|-------|----------|-------|-----------|
| Foundation | Month 1-2 | 120h | Infrastructure + Regime + Risk |
| Engine 1 (TITAN) | Month 3-4 | 100h | First profitable engine |
| Engine 2 (NAUTILUS) | Month 5-6 | 80h | Two-engine system |
| ML + Engine 3 (PHOENIX) | Month 7-9 | 120h | Full ML-enhanced system |
| Live Deployment | Month 10-12 | 80h | Real money trading |
| **TOTAL** | **12 months** | **500h** | **Production-grade system** |

**Pace:** ~10 hours/week. Sustainable. No burnout. No shortcuts.

**v1.0 claimed 370h in 12 weeks. v2.0 allocates 500h over 12 months. The difference is honesty.**

---

### 27.13 SECTION M: Architecture v2.0 — Simplified Blueprint

```
╔═══════════════════════════════════════════════════════════════════╗
║                    ARGUS v2.0 ARCHITECTURE                       ║
║              "Fewer components. Deeper execution."               ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  ┌──────────────────────────────────────────────────────────┐     ║
║  │              DATA PIPELINE + SENTINEL                    │     ║
║  │  OHLCV + Funding + OI + Orderbook → 50 Features          │     ║
║  │  Sentinel: data quality monitoring + anomaly detection    │     ║
║  │  Output: MarketSnapshot (validated, timestamped)          │     ║
║  └──────────────────────┬───────────────────────────────────┘     ║
║                         ▼                                         ║
║  ┌──────────────────────────────────────────────────────────┐     ║
║  │           REGIME DETECTOR v2.0 (4 states)                │     ║
║  │  Rules (primary) + LightGBM (secondary)                  │     ║
║  │  CRISIS detection: instant, no delay                     │     ║
║  │  Output: {regime, confidence, stability}                 │     ║
║  └──────────────────────┬───────────────────────────────────┘     ║
║                         │                                         ║
║           ┌─────────────┼──────────────┐                         ║
║           ▼             ▼              ▼                         ║
║  ┌──────────────┐ ┌───────────┐ ┌────────────┐                  ║
║  │    TITAN     │ │ NAUTILUS  │ │  PHOENIX   │                  ║
║  │   (Trend)    │ │ (Mean-Rev)│ │  (Carry)   │                  ║
║  │              │ │           │ │            │                  ║
║  │  TRENDING    │ │ RANGING   │ │ ALL regimes│                  ║
║  │  regime only │ │ regime    │ │ (always on)│                  ║
║  └──────┬───────┘ └─────┬─────┘ └─────┬──────┘                  ║
║         └───────────────┼─────────────┘                          ║
║                         ▼                                         ║
║  ┌──────────────────────────────────────────────────────────┐     ║
║  │               MDE v2.0 (Routing, NOT voting)             │     ║
║  │  1. Regime selects lead engine                           │     ║
║  │  2. Lead engine provides signal                          │     ║
║  │  3. ATLAS overlay adjusts sizing                         │     ║
║  │  4. Fixed fractional sizing (NOT Kelly)                  │     ║
║  │  5. Transaction cost gate (net return > 0.1%)            │     ║
║  └──────────────────────┬───────────────────────────────────┘     ║
║                         ▼                                         ║
║  ┌──────────────────────────────────────────────────────────┐     ║
║  │           RSL v2.0 (4-Level Kill Switch)                 │     ║
║  │  L0: Normal → L1: Caution → L2: Defensive → L3: Halt    │     ║
║  │  Equity curve MA filter (slow bleed detection)           │     ║
║  │  VETO POWER remains absolute                             │     ║
║  └──────────────────────┬───────────────────────────────────┘     ║
║                         ▼                                         ║
║  ┌──────────────────────────────────────────────────────────┐     ║
║  │              EXECUTION v2.0                              │     ║
║  │  4 urgency levels (EMERGENCY/HIGH/NORMAL/LOW)            │     ║
║  │  Exchange-side SL mandatory for all positions            │     ║
║  │  Execution quality tracking per trade                    │     ║
║  └──────────────────────┬───────────────────────────────────┘     ║
║                         ▼                                         ║
║  ┌──────────────────────────────────────────────────────────┐     ║
║  │              LEL v2.0 (Conservative Evolution)           │     ║
║  │  Monthly research cadence (NOT weekly)                   │     ║
║  │  90d OOS evidence required for any change                │     ║
║  │  Default behavior: change nothing                        │     ║
║  └──────────────────────────────────────────────────────────┘     ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝

COMPONENT COUNT:
  v1.0: 5 engines + 8-state HMM + voting MDE + Kelly sizing = 14+ moving parts
  v2.0: 3 engines + 4-state RDE + routing MDE + fixed sizing = 8 moving parts

LESS COMPLEXITY. MORE ROBUSTNESS. DEEPER EXECUTION.
```

---

### 27.14 Final Verdict

| Aspect | v1.0 Grade | v2.0 Target | Assessment |
|--------|-----------|-------------|------------|
| **Architecture** | B- | A- | Over-engineered → right-sized |
| **Strategy Depth** | D | B+ | 5 shallow → 3 deep |
| **Risk Management** | B | A | Good foundation → hardened |
| **Regime Detection** | C | B+ | Academic → pragmatic |
| **Execution** | D | B | Absent → basic institutional |
| **Timeline Realism** | F | B+ | Fantasy → honest |
| **ML Integration** | C+ | B | Ambitious → achievable |
| **Overfitting Protection** | C | A- | Inadequate → paranoid |
| **Capital Preservation** | B | A | Good intent → enforced |
| **Survivability** | C+ | A- | Hope-based → evidence-based |

**Bottom line:** v1.0 is the system a quant student designs. v2.0 is the system a quant who has lost money designs. The difference is pain. We're injecting the pain upfront through hostile review instead of learning it through real losses.

**The single most important sentence in this entire document:**

> Build less. Validate more. Trade small. Survive first. Everything else is optimization.

---

---

## 28. ARGUS v2.0 — Consolidated Technical Specification

> **Purpose:** This is the FINAL, AUTHORITATIVE specification for ARGUS v2.0.  
> **Rule:** If any previous section contradicts this section, THIS SECTION WINS.  
> **Audience:** The developer building this system. Every line is implementation-ready.

---

### 28.1 System Identity

```
Name:           ARGUS v2.0
Type:           Multi-regime algorithmic crypto trading system
Deployment:     Windows laptop (i7-11800H, 32GB RAM, RTX A3000M 6GB)
Runtime:        24/7 autonomous with human oversight
Capital:        $100 initial → scale to $100K+ over 4 years
Markets:        Crypto perpetual futures (Binance primary, Bybit secondary)
Pairs (v2.0):   BTCUSDT, ETHUSDT (add more only after 6 months profitability)
Timeframe:      1h primary, 4h confirmation, 1d direction
Language:       Python 3.11+
Framework:      asyncio + ccxt + pandas + PyTorch + LightGBM
```

### 28.2 Component Inventory (What Gets Built)

| # | Component | Type | Priority | Build Phase |
|---|-----------|------|----------|-------------|
| 1 | **Data Pipeline** | Infrastructure | P0 | Phase 1 |
| 2 | **Feature Engine (50 features)** | Infrastructure | P0 | Phase 1 |
| 3 | **Sentinel (Data Quality Monitor)** | Overlay | P0 | Phase 1 |
| 4 | **Regime Detector v2.0 (4-state)** | Core | P0 | Phase 1 |
| 5 | **RSL v2.0 (4-level kill switch)** | Core | P0 | Phase 1 |
| 6 | **Backtest Engine + Walk-Forward** | Validation | P0 | Phase 1 |
| 7 | **TITAN Engine (Trend/Momentum)** | Strategy | P0 | Phase 2 |
| 8 | **MDE v2.0 (Routing)** | Core | P0 | Phase 2 |
| 9 | **Execution Engine v2.0** | Infrastructure | P0 | Phase 2 |
| 10 | **NAUTILUS Engine (Mean-Reversion)** | Strategy | P1 | Phase 3 |
| 11 | **Telegram Bot** | Interface | P1 | Phase 3 |
| 12 | **PHOENIX Engine (Carry/Basis)** | Strategy | P1 | Phase 4 |
| 13 | **Atlas Overlay (Risk Governor)** | Overlay | P1 | Phase 4 |
| 14 | **LightGBM Direction Model** | ML | P1 | Phase 4 |
| 15 | **Chronos-Bolt Forecaster** | ML | P1 | Phase 4 |
| 16 | **Meta-Labeler** | ML | P2 | Phase 4 |
| 17 | **LEL v2.0 (Learning)** | Analytics | P2 | Phase 5 |
| 18 | **Dashboard** | Interface | P2 | Phase 5 |

**Total components: 18. Not 50. Not 30. Eighteen.**

### 28.3 Data Pipeline — Final Spec

#### 28.3.1 Data Sources

| Source | Protocol | Data | Frequency | Fallback |
|--------|----------|------|-----------|----------|
| **Binance Futures** | WebSocket | OHLCV (1m,5m,15m,1h,4h,1d) | Real-time | REST poll 5s |
| **Binance Futures** | WebSocket | Mark Price + Funding Rate | Real-time | REST poll 60s |
| **Binance Futures** | REST | Open Interest | 5m poll | 15m poll |
| **Binance Futures** | WebSocket | Orderbook L2 (top 20) | 100ms | REST poll 1s |
| **Binance Futures** | REST | Liquidation data | 1m poll | Estimate from OI delta |
| **Bybit** | REST | OHLCV + Funding (cross-validation) | 5m poll | None (optional) |
| **CoinGecko** | REST | BTC dominance, total market cap | 5m poll | None (cache last) |
| **CryptoPanic** | REST | Fear/Greed score | 15m poll | None (use last known) |

#### 28.3.2 Storage Architecture

```
HOT STORE (Redis) — last 24h, <1ms access
├── Current candles (all timeframes)
├── Current orderbook snapshot
├── Current funding rate
├── Current feature vector (50 features)
├── Current regime state
└── Current portfolio state

WARM STORE (Parquet files) — all history, <100ms access
├── OHLCV by symbol by timeframe (partitioned by month)
├── Funding rate history
├── Open interest history
└── Feature history (computed and cached)

COLD STORE (SQLite/PostgreSQL) — trade logs, immutable
├── Trade log (every trade ever taken)
├── Decision log (every MDE decision)
├── Risk log (every RSL check)
├── Regime log (every regime change)
└── Error log (every error/exception)
```

#### 28.3.3 Data Validation (Sentinel)

```python
class Sentinel:
    """Runs BEFORE any data reaches engines. Non-negotiable."""
    
    CHECKS = [
        ("price_positive",    lambda s: s.close > 0),
        ("price_reasonable",  lambda s: 0.7 < s.close/s.prev_close < 1.3),  # No 30%+ gaps without flag
        ("volume_present",    lambda s: s.volume > 0),
        ("timestamp_fresh",   lambda s: (now() - s.timestamp).seconds < 120),  # Max 2 min stale
        ("spread_reasonable", lambda s: s.spread / s.close < 0.005),  # Max 0.5% spread
        ("no_nan",            lambda s: not any_nan(s.features)),
    ]
    
    def validate(self, snapshot) -> float:
        """Returns quality score 0.0-1.0"""
        passed = sum(1 for name, check in self.CHECKS if check(snapshot))
        score = passed / len(self.CHECKS)
        
        if score < 0.7:
            self.alert("DATA_QUALITY_WARNING", score=score)
        if score < 0.4:
            self.alert("DATA_QUALITY_CRITICAL", score=score)
        
        return score
```

### 28.4 Feature Engine — Final Spec (50 Features)

#### 28.4.1 Computation Contract

```python
@dataclass(frozen=True)
class FeatureVector:
    """Immutable. Computed once per candle close. All 50 values populated."""
    timestamp: datetime
    symbol: str
    
    # ── Volatility (6) ──
    atr_14: float              # ATR(14) absolute
    atr_14_pct: float          # ATR(14) / close (normalized)
    atr_ratio_5_20: float      # ATR(5) / ATR(20) — expansion/compression
    realized_vol_20d: float    # 20-day annualized realized volatility
    parkinson_vol: float       # Parkinson high-low volatility estimator
    bb_width: float            # Bollinger Band width (20,2)
    
    # ── Trend (6) ──
    adx_14: float              # ADX(14) — trend strength
    price_vs_ma200: float      # (close - MA200) / MA200
    ema_21_vs_55: float        # (EMA21 - EMA55) / EMA55
    lr_slope_20: float         # Linear regression slope of close over 20 periods
    supertrend_dir: int        # SuperTrend direction: +1 / -1
    aroon_osc: float           # Aroon oscillator (-100 to +100)
    
    # ── Momentum (5) ──
    rsi_14: float              # RSI(14) — 0 to 100
    bb_pct_b: float            # Bollinger %B — 0 to 1 (can exceed)
    roc_10: float              # Rate of change (10)
    willr_14: float            # Williams %R (-100 to 0)
    cci_20: float              # Commodity Channel Index (20)
    
    # ── Volume (5) ──
    volume_ratio: float        # volume / SMA(volume, 20)
    obv_slope_10: float        # OBV linear reg slope over 10 periods
    vwap_dev_pct: float        # (close - VWAP) / VWAP
    cmf_20: float              # Chaikin Money Flow (20)
    volume_delta: float        # buy_vol - sell_vol (estimated from candle)
    
    # ── Microstructure (5) ──
    spread_pct: float          # bid-ask spread / mid
    orderbook_imbalance: float # (bid_depth - ask_depth) / total @ 0.5%
    trade_flow_imbalance: float # net buy volume / total volume (1h rolling)
    depth_ratio: float         # bid depth / ask depth within 1% of mid
    large_trade_ratio: float   # large trades (>$10K) volume / total volume
    
    # ── Crypto-Native (7) ──
    funding_rate: float        # raw perpetual funding rate
    funding_pctile_30d: float  # percentile rank over 30 days
    oi_change_4h_pct: float    # open interest % change over 4 hours
    oi_change_24h_pct: float   # open interest % change over 24 hours
    liquidation_est: float     # estimated liquidation volume (normalized)
    long_short_ratio: float    # long/short account ratio (if available)
    basis_pct: float           # (perp_price - spot_price) / spot_price
    
    # ── Cross-Asset (4) ──
    btc_dominance_delta_24h: float  # BTC.D change over 24h
    btc_eth_corr_30d: float         # rolling 30d correlation BTC-ETH
    total_mcap_momentum: float      # total crypto market cap 7d momentum
    stablecoin_flow: float          # USDT+USDC market cap 24h delta (normalized)
    
    # ── Statistical (4) ──
    return_autocorr_20: float  # serial correlation of returns (20 period)
    hurst_exponent: float      # Hurst exponent (100 period) — persistence measure
    entropy_50: float          # Shannon entropy of return distribution (50 period)
    frac_diff_price: float     # Fractionally differentiated close (d=0.35)
    
    # ── ML Output (8) — computed by ML models, None if models not yet active ──
    chronos_forecast_1h: Optional[float]      # Chronos median 1h forecast
    chronos_confidence_width: Optional[float]  # Chronos 90-10 quantile range
    lgbm_direction: Optional[int]             # -1, 0, +1 prediction
    lgbm_confidence: Optional[float]          # prediction probability
    meta_label_score: Optional[float]         # trade quality score 0-1
    regime_prob_trending: Optional[float]     # P(trending)
    regime_prob_ranging: Optional[float]      # P(ranging)
    regime_prob_volatile: Optional[float]     # P(volatile)
```

#### 28.4.2 Feature Computation Timing

```
Candle Close (1h) ─── t=0
    │
    ├── Tier 1: Technical features (40 features) ──── t+200ms (CPU, pandas/numpy)
    │
    ├── Tier 2: Microstructure features (5 features) ── t+100ms (Redis read)
    │
    ├── Tier 3: Crypto-native features (7 features) ── t+300ms (REST API calls)
    │
    ├── Tier 4: ML features (8 features) ──── t+1500ms (GPU inference)
    │
    └── FeatureVector complete ──── t+2000ms MAXIMUM
        │
        ├── Sentinel validation ──── t+2050ms
        │
        └── Ready for Regime Detector + Engines ──── t+2100ms
```

### 28.5 Regime Detector v2.0 — Final Spec

#### 28.5.1 State Machine

```
                    ┌──────────────┐
            ┌──────►│   TRENDING   │◄──────┐
            │       │  ADX>25      │       │
            │       └──────┬───────┘       │
            │              │               │
   (ADX drops    (Vol spike)    (ADX rises)
    below 20)          │               │
            │              ▼               │
            │       ┌──────────────┐       │
            ├──────►│   VOLATILE   │◄──────┤
            │       │  ATR ratio   │       │
            │       │  >1.8        │       │
            │       └──────┬───────┘       │
            │              │               │
            │      (extreme             (vol 
            │       stress)             subsides)
            │              │               │
            ▼              ▼               │
     ┌──────────────┐  ┌──────────────┐    │
     │   RANGING    │  │   CRISIS     │────┘
     │  ADX<20      │  │  drop>8%/24h │  (recovery = TRENDING entry)
     │  Hurst<0.45  │  │  vol>3x norm │
     └──────────────┘  └──────────────┘
           │                    │
           └────────────────────┘
              (extreme event)
```

#### 28.5.2 Transition Rules

| From | To | Trigger | Confirmation | Delay |
|------|-----|---------|-------------|-------|
| ANY | **CRISIS** | price_change_24h < -8% OR atr_ratio > 3.0 OR liquidation_cascade | **NONE** (instant) | 0 candles |
| CRISIS | TRENDING | Price >5% off bottom, vol declining, 48h elapsed | Rule + ML agree | 3 candles |
| CRISIS | RANGING | Vol normalizing, price stable, 48h elapsed | Rule + ML agree | 3 candles |
| TRENDING | RANGING | ADX drops below 20 for 3 candles, Hurst < 0.45 | Rule + ML agree | 3 candles |
| TRENDING | VOLATILE | ATR ratio > 1.8, direction unclear | Rule sufficient | 2 candles |
| RANGING | TRENDING | ADX rises above 25, LR slope significant | Rule + ML agree | 3 candles |
| RANGING | VOLATILE | ATR ratio > 1.8 | Rule sufficient | 2 candles |
| VOLATILE | TRENDING | Vol subsiding, ADX > 25, direction clear | Rule + ML agree | 3 candles |
| VOLATILE | RANGING | Vol subsiding, ADX < 20 | Rule + ML agree | 3 candles |

**Key design: CRISIS entry is INSTANT. Everything else requires confirmation. Asymmetric — fast into defense, slow out of defense.**

#### 28.5.3 Regime Output Contract

```python
@dataclass(frozen=True)
class RegimeState:
    regime: str                    # "TRENDING" | "RANGING" | "VOLATILE" | "CRISIS"
    confidence: float              # 0.0 - 1.0
    stability: float               # 0.0 - 1.0 (how long in this regime)
    direction: Optional[int]       # +1 (bull) / -1 (bear) / None (non-directional)
    pending_transition: Optional[str]  # If transition brewing, what regime might come next
    candles_in_regime: int         # How many candles since regime started
    rule_regime: str               # What rules say (for debugging)
    ml_regime: str                 # What ML says (for debugging)
    timestamp: datetime
```

### 28.6 Engine Specifications — Final

#### 28.6.1 TITAN (Trend/Momentum Engine)

```python
class TitanEngine:
    """
    ONLY active when regime = TRENDING.
    Two sub-strategies with internal vote.
    Conservative by default. Aggressive only on high conviction.
    """
    
    # ── Configuration ──
    ACTIVE_REGIMES = ["TRENDING"]
    MIN_ADX = 25
    MIN_CONFIDENCE_TO_SIGNAL = 0.55
    MAX_CONCURRENT_POSITIONS = 2   # per pair
    
    # ── Sub-Strategy A: Trend Follow ──
    TREND_EMA_FAST = 21
    TREND_EMA_SLOW = 55
    TREND_ADX_MIN = 25
    TREND_ATR_TRAIL_MULT = 2.5    # trailing stop at 2.5x ATR
    TREND_MIN_VOLUME_RATIO = 1.0  # volume must be >= average
    
    # ── Sub-Strategy B: Momentum Breakout ──
    BREAKOUT_DONCHIAN = 20         # 20-period Donchian channel
    BREAKOUT_VOLUME_SPIKE = 1.5    # volume must be 1.5x average on break
    BREAKOUT_ATR_FILTER = 0.005    # ATR/price must be > 0.5% (enough volatility)
    BREAKOUT_CONFIRMATION_CANDLES = 2  # close above/below for 2 candles
    
    def generate_signal(self, snapshot: MarketSnapshot, 
                        regime: RegimeState, 
                        features: FeatureVector) -> Optional[EngineSignal]:
        
        # ── Gate: Only operate in TRENDING regime ──
        if regime.regime not in self.ACTIVE_REGIMES:
            return None  # Return None, not neutral. Titan is OFF.
        
        if features.adx_14 < self.MIN_ADX:
            return None  # ADX must confirm trend
        
        # ── Sub-Strategy A: Trend Follow ──
        trend_signal = self._trend_follow(features, regime)
        
        # ── Sub-Strategy B: Breakout ──
        breakout_signal = self._breakout(features, regime)
        
        # ── Internal Selection: Pick the STRONGER signal ──
        signals = [s for s in [trend_signal, breakout_signal] if s is not None]
        if not signals:
            return None
        
        best = max(signals, key=lambda s: s.confidence)
        
        if best.confidence < self.MIN_CONFIDENCE_TO_SIGNAL:
            return None
        
        return best
    
    def _trend_follow(self, f: FeatureVector, regime: RegimeState) -> Optional[EngineSignal]:
        """EMA cross + ADX + volume + ATR trailing stop."""
        
        ema_cross = f.ema_21_vs_55  # positive = bullish, negative = bearish
        direction = regime.direction  # +1 or -1
        
        if direction is None:
            return None
        
        # Long signal: EMA21 > EMA55, ADX > 25, price > MA200, volume OK
        if direction == 1 and ema_cross > 0 and f.price_vs_ma200 > 0 and f.volume_ratio >= self.TREND_MIN_VOLUME_RATIO:
            confidence = min(0.95, 0.5 + (f.adx_14 - 25) / 50 + abs(ema_cross) * 2)
            stop_distance = f.atr_14_pct * self.TREND_ATR_TRAIL_MULT
            expected_return = f.atr_14_pct * 3.0  # Target 3x ATR
            return EngineSignal(
                engine="TITAN", sub_strategy="trend_follow",
                bias="long", confidence=confidence,
                stop_distance=stop_distance, expected_return=expected_return,
                atr=f.atr_14_pct
            )
        
        # Short signal: mirror logic
        if direction == -1 and ema_cross < 0 and f.price_vs_ma200 < 0 and f.volume_ratio >= self.TREND_MIN_VOLUME_RATIO:
            confidence = min(0.95, 0.5 + (f.adx_14 - 25) / 50 + abs(ema_cross) * 2)
            stop_distance = f.atr_14_pct * self.TREND_ATR_TRAIL_MULT
            expected_return = f.atr_14_pct * 3.0
            return EngineSignal(
                engine="TITAN", sub_strategy="trend_follow",
                bias="short", confidence=confidence,
                stop_distance=stop_distance, expected_return=expected_return,
                atr=f.atr_14_pct
            )
        
        return None
    
    def _breakout(self, f: FeatureVector, regime: RegimeState) -> Optional[EngineSignal]:
        """Donchian breakout with volume confirmation."""
        # Implementation: price breaks 20-period high/low
        # with volume > 1.5x average
        # Confirmation: 2 consecutive candle closes beyond channel
        # Stop: opposite Donchian band or 2x ATR, whichever is tighter
        ...
```

#### 28.6.2 NAUTILUS (Mean-Reversion Engine)

```python
class NautilusEngine:
    """
    ONLY active when regime = RANGING.
    Fades extremes. Targets mean. Tight stops.
    The anti-TITAN: profits when TITAN would bleed.
    """
    
    # ── Configuration ──
    ACTIVE_REGIMES = ["RANGING"]
    MAX_ADX = 22              # ADX must be LOW for mean reversion
    MIN_CONFIDENCE = 0.55
    
    # ── Sub-Strategy A: Bollinger Reversion ──
    BB_PERIOD = 20
    BB_STD = 2.0
    BB_ENTRY_THRESHOLD = 0.05  # %B < 0.05 (oversold) or > 0.95 (overbought)
    BB_RSI_OVERSOLD = 30
    BB_RSI_OVERBOUGHT = 70
    BB_STOP_MULT = 1.0         # Stop at 1x ATR beyond entry
    BB_TARGET = "mid"          # Target: middle Bollinger Band
    
    # ── Sub-Strategy B: Funding Rate Mean-Reversion ──
    FUNDING_EXTREME_PCTILE = 90     # Funding > 90th percentile = extreme long crowding
    FUNDING_EXTREME_NEG_PCTILE = 10 # Funding < 10th percentile = extreme short crowding
    FUNDING_HOLD_PERIODS = 8         # Hold for 8 funding periods (64 hours)
    FUNDING_STOP_PCT = 0.03          # 3% stop (wide — funding trades need room)
    
    def generate_signal(self, snapshot, regime, features):
        if regime.regime not in self.ACTIVE_REGIMES:
            return None
        
        if features.adx_14 > self.MAX_ADX:
            return None  # Too trendy for mean reversion
        
        bb_signal = self._bollinger_reversion(features)
        funding_signal = self._funding_reversion(features)
        
        signals = [s for s in [bb_signal, funding_signal] if s is not None]
        if not signals:
            return None
        
        return max(signals, key=lambda s: s.confidence)
    
    def _bollinger_reversion(self, f):
        """Buy at lower BB + RSI oversold. Sell at upper BB + RSI overbought."""
        
        if f.bb_pct_b < self.BB_ENTRY_THRESHOLD and f.rsi_14 < self.BB_RSI_OVERSOLD:
            # Oversold: go long, target middle band
            confidence = min(0.90, 0.5 + (self.BB_RSI_OVERSOLD - f.rsi_14) / 60 + (0.05 - f.bb_pct_b) * 5)
            return EngineSignal(
                engine="NAUTILUS", sub_strategy="bb_reversion",
                bias="long", confidence=confidence,
                stop_distance=f.atr_14_pct * self.BB_STOP_MULT,
                expected_return=abs(f.vwap_dev_pct) * 0.5,  # Target: half the deviation back
                atr=f.atr_14_pct
            )
        
        if f.bb_pct_b > (1 - self.BB_ENTRY_THRESHOLD) and f.rsi_14 > self.BB_RSI_OVERBOUGHT:
            confidence = min(0.90, 0.5 + (f.rsi_14 - self.BB_RSI_OVERBOUGHT) / 60 + (f.bb_pct_b - 0.95) * 5)
            return EngineSignal(
                engine="NAUTILUS", sub_strategy="bb_reversion",
                bias="short", confidence=confidence,
                stop_distance=f.atr_14_pct * self.BB_STOP_MULT,
                expected_return=abs(f.vwap_dev_pct) * 0.5,
                atr=f.atr_14_pct
            )
        
        return None
    
    def _funding_reversion(self, f):
        """When funding rate is extreme, fade the crowd."""
        
        if f.funding_pctile_30d > self.FUNDING_EXTREME_PCTILE:
            # Extreme longs → short (crowd will pay us to hold)
            confidence = min(0.85, 0.5 + (f.funding_pctile_30d - 90) / 20)
            return EngineSignal(
                engine="NAUTILUS", sub_strategy="funding_reversion",
                bias="short", confidence=confidence,
                stop_distance=self.FUNDING_STOP_PCT,
                expected_return=abs(f.funding_rate) * self.FUNDING_HOLD_PERIODS,
                atr=f.atr_14_pct
            )
        
        if f.funding_pctile_30d < self.FUNDING_EXTREME_NEG_PCTILE:
            confidence = min(0.85, 0.5 + (10 - f.funding_pctile_30d) / 20)
            return EngineSignal(
                engine="NAUTILUS", sub_strategy="funding_reversion",
                bias="long", confidence=confidence,
                stop_distance=self.FUNDING_STOP_PCT,
                expected_return=abs(f.funding_rate) * self.FUNDING_HOLD_PERIODS,
                atr=f.atr_14_pct
            )
        
        return None
```

#### 28.6.3 PHOENIX (Carry/Basis Engine)

```python
class PhoenixEngine:
    """
    Active in ALL regimes (carry is regime-independent).
    Low frequency. High conviction. Funding rate is the most
    measurable and reliable edge in crypto markets.
    
    Core idea: When the crowd pays extreme funding, be the counterparty.
    When basis between spot and perp deviates, arb the convergence.
    """
    
    ACTIVE_REGIMES = ["TRENDING", "RANGING", "VOLATILE"]  # NOT CRISIS
    
    # ── Funding Harvest ──
    FUNDING_ENTRY_PCTILE = 95    # Only enter at 95th percentile (very extreme)
    FUNDING_EXIT_PCTILE = 60     # Exit when funding normalizes
    FUNDING_MIN_RATE = 0.0003    # Minimum 0.03%/8h funding to bother
    
    # ── Basis Trade ──
    BASIS_ENTRY_THRESHOLD = 0.003  # 0.3% spot-perp basis to enter
    BASIS_EXIT_THRESHOLD = 0.0005  # Exit when basis converges to 0.05%
    
    def generate_signal(self, snapshot, regime, features):
        if regime.regime == "CRISIS":
            return None
        
        funding = self._funding_harvest(features)
        basis = self._basis_trade(features)
        
        signals = [s for s in [funding, basis] if s is not None]
        if not signals:
            return None
        
        return max(signals, key=lambda s: s.expected_return)
    
    def _funding_harvest(self, f):
        """Collect funding from overcrowded side."""
        if f.funding_pctile_30d >= self.FUNDING_ENTRY_PCTILE and abs(f.funding_rate) > self.FUNDING_MIN_RATE:
            bias = "short" if f.funding_rate > 0 else "long"
            # Expected return = funding collected over holding period
            expected_return = abs(f.funding_rate) * 3  # 3 funding periods (24h)
            confidence = min(0.80, 0.55 + (f.funding_pctile_30d - 95) / 10)
            return EngineSignal(
                engine="PHOENIX", sub_strategy="funding_harvest",
                bias=bias, confidence=confidence,
                stop_distance=0.025,  # 2.5% stop (wider — carry trade needs room)
                expected_return=expected_return,
                atr=f.atr_14_pct
            )
        return None
    
    def _basis_trade(self, f):
        """Arb spot-perp basis divergence."""
        if abs(f.basis_pct) > self.BASIS_ENTRY_THRESHOLD:
            bias = "short" if f.basis_pct > 0 else "long"  # fade the premium
            expected_return = abs(f.basis_pct) * 0.6  # expect 60% convergence
            confidence = min(0.75, 0.5 + abs(f.basis_pct) * 50)
            return EngineSignal(
                engine="PHOENIX", sub_strategy="basis_trade",
                bias=bias, confidence=confidence,
                stop_distance=0.03,  # 3% stop
                expected_return=expected_return,
                atr=f.atr_14_pct
            )
        return None
```

#### 28.6.4 Engine Signal Contract

```python
@dataclass(frozen=True)
class EngineSignal:
    engine: str              # "TITAN" | "NAUTILUS" | "PHOENIX"
    sub_strategy: str        # "trend_follow" | "breakout" | "bb_reversion" | etc.
    bias: str                # "long" | "short"
    confidence: float        # 0.0 - 1.0
    stop_distance: float     # as fraction of price (e.g., 0.02 = 2%)
    expected_return: float   # NET of estimated costs, as fraction
    atr: float               # current ATR/price for sizing reference
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def net_expected_return(self, cost=0.0013):
        """Expected return minus estimated round-trip cost (default 0.13%)."""
        return self.expected_return - cost
    
    def reward_risk_ratio(self):
        """Expected return / stop distance."""
        if self.stop_distance == 0: return 0
        return self.expected_return / self.stop_distance
```

### 28.7 MDE v2.0 — Final Spec

```python
class MetaDecisionEngineV2:
    
    ENGINE_ROUTING = {
        "TRENDING": "TITAN",
        "RANGING":  "NAUTILUS",
        "VOLATILE": "PHOENIX",
        "CRISIS":   None  # No engine. Capital preservation only.
    }
    
    MIN_CONFIDENCE = 0.55
    MIN_NET_RETURN = 0.001        # 0.1% minimum net expected return
    MIN_REWARD_RISK = 1.5         # Minimum reward/risk ratio
    BASE_RISK_PER_TRADE = 0.02    # 2% risk per trade
    MAX_RISK_PER_TRADE = 0.03     # 3% absolute maximum
    MAX_POSITION_PCT = 0.15       # 15% max of portfolio in one position
    ESTIMATED_COST = 0.0013       # 0.13% round-trip cost
    
    def decide(self, regime, engines, portfolio, risk_state, sentinel_score, atlas_mult):
        
        # ── GATE 0: Data quality ──
        if sentinel_score < 0.4:
            return Decision(action="hold", reason="Data quality critical")
        
        # ── GATE 1: Crisis = no new trades ──
        if regime.regime == "CRISIS":
            if portfolio.has_positions:
                return Decision(action="close_all", reason="CRISIS active")
            return Decision(action="hold", reason="CRISIS — capital preservation")
        
        # ── GATE 2: RSL level check ──
        rsl_level = risk_state.current_level
        if rsl_level >= 3:
            return Decision(action="hold", reason=f"RSL Level {rsl_level} — halted")
        if rsl_level >= 2:
            # Only PHOENIX allowed at Level 2
            lead_engine = "PHOENIX"
        else:
            lead_engine = self.ENGINE_ROUTING[regime.regime]
        
        # ── GATE 3: Get signal ──
        signal = engines[lead_engine].signal
        
        # Check if PHOENIX has a better opportunity (always-on cross-check)
        phoenix_signal = engines.get("PHOENIX", {}).get("signal")
        if signal is None and phoenix_signal is not None:
            signal = phoenix_signal
            lead_engine = "PHOENIX"
        
        if signal is None:
            return Decision(action="hold", reason=f"{lead_engine} has no signal")
        
        # ── GATE 4: Confidence ──
        if signal.confidence < self.MIN_CONFIDENCE:
            return Decision(action="hold", reason=f"Confidence {signal.confidence} < {self.MIN_CONFIDENCE}")
        
        # ── GATE 5: Net expected return ──
        net_return = signal.net_expected_return(self.ESTIMATED_COST)
        if net_return < self.MIN_NET_RETURN:
            return Decision(action="hold", reason=f"Net return {net_return:.4f} < {self.MIN_NET_RETURN}")
        
        # ── GATE 6: Reward/Risk ratio ──
        rr = signal.reward_risk_ratio()
        if rr < self.MIN_REWARD_RISK:
            return Decision(action="hold", reason=f"R:R {rr:.2f} < {self.MIN_REWARD_RISK}")
        
        # ── SIZING ──
        risk_pct = self.BASE_RISK_PER_TRADE
        
        # Adjustments (multiplicative)
        risk_pct *= atlas_mult                                    # Macro risk
        risk_pct *= min(sentinel_score, 1.0)                     # Data quality
        risk_pct *= min(regime.confidence, 1.0)                  # Regime confidence
        risk_pct *= self._drawdown_mult(risk_state.drawdown)     # DD adjustment
        risk_pct *= (0.5 if rsl_level == 1 else 1.0)            # RSL caution
        
        risk_pct = min(risk_pct, self.MAX_RISK_PER_TRADE)
        risk_pct = max(risk_pct, 0.005)  # Floor: 0.5%
        
        position_size = risk_pct / signal.stop_distance
        position_size = min(position_size, self.MAX_POSITION_PCT)
        
        # ── LEVERAGE ──
        max_lev = {"TRENDING": 2.0, "RANGING": 1.5, "VOLATILE": 1.0}
        leverage = min(1.0 + (signal.confidence - 0.5), max_lev.get(regime.regime, 1.0))
        
        return Decision(
            action=signal.bias,
            position_size=round(position_size, 4),
            leverage=round(max(leverage, 1.0), 2),
            stop_loss=round(signal.stop_distance, 4),
            take_profit=round(signal.expected_return, 4),
            confidence=round(signal.confidence * regime.confidence, 3),
            engine=lead_engine,
            reason=f"Engine={lead_engine}, Regime={regime.regime}({regime.confidence:.2f}), "
                   f"R:R={rr:.1f}, Atlas={atlas_mult:.2f}, Sentinel={sentinel_score:.2f}"
        )
    
    def _drawdown_mult(self, dd):
        dd = abs(dd)
        if dd < 0.02: return 1.0
        if dd < 0.04: return 0.5
        if dd < 0.06: return 0.25
        return 0.0
```

### 28.8 RSL v2.0 — Final Spec

#### 28.8.1 Risk Levels

```python
class RiskLevel(Enum):
    NORMAL   = 0   # Full operation
    CAUTION  = 1   # Reduced sizing, alerts
    DEFENSIVE = 2  # Minimal operation, carry only
    HALT     = 3   # All closed, system stopped
    LOCKDOWN = 4   # Indefinite halt, manual only

class RSLv2:
    
    LEVEL_TRIGGERS = {
        # NORMAL → CAUTION
        1: [
            ("drawdown > 2%",          lambda s: abs(s.drawdown) > 0.02),
            ("daily_loss > 1%",        lambda s: s.daily_pnl < -0.01),
            ("2 consecutive losses",   lambda s: s.consecutive_losses >= 2),
        ],
        # CAUTION → DEFENSIVE
        2: [
            ("drawdown > 4%",          lambda s: abs(s.drawdown) > 0.04),
            ("daily_loss > 1.5%",      lambda s: s.daily_pnl < -0.015),
            ("3 consecutive losses",   lambda s: s.consecutive_losses >= 3),
            ("equity < MA(20d)",       lambda s: s.equity < s.equity_ma_20d),
        ],
        # DEFENSIVE → HALT
        3: [
            ("drawdown > 6%",          lambda s: abs(s.drawdown) > 0.06),
            ("daily_loss > 2.5%",      lambda s: s.daily_pnl < -0.025),
            ("CRISIS regime + positions", lambda s: s.regime == "CRISIS" and s.has_positions),
        ],
        # HALT → LOCKDOWN
        4: [
            ("drawdown > 10%",         lambda s: abs(s.drawdown) > 0.10),
        ],
    }
    
    LEVEL_ACTIONS = {
        0: "Full operation. All engines active.",
        1: "Position sizes reduced to 75%. Max leverage 1.5x. Alert sent.",
        2: "No new trades except PHOENIX carry. Max leverage 1.0x. Existing positions kept with tighter stops.",
        3: "ALL positions closed at market. System halted 24h minimum. Manual restart required.",
        4: "System halted INDEFINITELY. Full audit required. No automated restart.",
    }
    
    RECOVERY_CONDITIONS = {
        # To go from Level X back to Level X-1:
        1: "DD recovers to <1.5%. Must hold for 4h.",
        2: "DD recovers to <3%. Must hold for 12h. No losses in last 6 trades.",
        3: "Manual restart only. Post-mortem document required.",
        4: "Manual restart only. Full strategy audit completed.",
    }
```

#### 28.8.2 Pre-Trade Checks (per trade)

```python
def pre_trade_check(self, decision, portfolio):
    checks = [
        # Check 1: Position size sanity
        (decision.position_size <= 0.15,
         f"Position size {decision.position_size} exceeds 15% cap"),
        
        # Check 2: Leverage sanity
        (decision.leverage <= 3.0,
         f"Leverage {decision.leverage} exceeds 3x cap"),
        
        # Check 3: Daily trade count
        (portfolio.trades_today < 15,
         f"Daily trade count {portfolio.trades_today} exceeds 15"),
        
        # Check 4: Not within 15min of funding settlement
        (not self._near_funding_settlement(),
         "Too close to funding settlement"),
        
        # Check 5: Weekend position reduction
        (not self._is_weekend() or decision.position_size <= portfolio.max_weekend_size,
         "Weekend position limit exceeded"),
        
        # Check 6: Correlation with existing positions
        (self._correlation_ok(decision, portfolio),
         "Too correlated with existing positions"),
        
        # Check 7: Stop loss present
        (decision.stop_loss > 0,
         "No stop loss defined"),
        
        # Check 8: Stop loss not too wide
        (decision.stop_loss <= 0.05,
         f"Stop loss {decision.stop_loss} exceeds 5% maximum"),
    ]
    
    for passed, reason in checks:
        if not passed:
            return RiskVerdict(approved=False, reason=reason)
    
    return RiskVerdict(approved=True)
```

### 28.9 Execution v2.0 — Final Spec

```python
class ExecutionEngine:
    """
    Rule #1: Every position MUST have an exchange-side stop loss.
    Rule #2: If exchange-side SL fails to place, position is NOT opened.
    Rule #3: Position reconciliation runs every 60 seconds.
    """
    
    URGENCY_CONFIG = {
        "EMERGENCY": {"order_type": "market", "max_slippage": None, "timeout_s": 0},
        "HIGH":      {"order_type": "limit", "offset": 0.001, "timeout_s": 30, "fallback": "market"},
        "NORMAL":    {"order_type": "limit", "offset": 0.0, "timeout_s": 60, "fallback": "cancel"},
        "LOW":       {"order_type": "limit", "offset": -0.0005, "timeout_s": 300, "fallback": "cancel"},
    }
    
    async def execute(self, decision: Decision, urgency: str = "NORMAL"):
        config = self.URGENCY_CONFIG[urgency]
        
        # Step 1: Calculate order parameters
        order_params = self._build_order(decision, config)
        
        # Step 2: Place entry order
        entry_result = await self.exchange.place_order(order_params)
        
        if not entry_result.filled:
            if config.get("fallback") == "market":
                entry_result = await self.exchange.place_market_order(order_params)
            else:
                return ExecutionResult(success=False, reason="Order not filled, cancelled")
        
        # Step 3: IMMEDIATELY place exchange-side stop loss
        sl_result = await self.exchange.place_stop_loss(
            symbol=decision.symbol,
            side="sell" if decision.action == "long" else "buy",
            stop_price=entry_result.fill_price * (1 - decision.stop_loss if decision.action == "long" 
                                                    else 1 + decision.stop_loss),
            quantity=entry_result.filled_quantity
        )
        
        if not sl_result.success:
            # CRITICAL: SL failed. Close position immediately.
            await self.exchange.place_market_order(close_params)
            self.alert("CRITICAL: Stop loss placement failed. Position closed.")
            return ExecutionResult(success=False, reason="SL placement failed")
        
        # Step 4: Log execution quality
        self._log_execution_quality(decision, entry_result, sl_result)
        
        return ExecutionResult(
            success=True,
            fill_price=entry_result.fill_price,
            slippage=entry_result.slippage,
            sl_order_id=sl_result.order_id
        )
    
    async def reconcile(self):
        """Run every 60s. Compare local state vs exchange state."""
        local_positions = self.portfolio.get_all_positions()
        exchange_positions = await self.exchange.get_positions()
        
        for pos in local_positions:
            exchange_pos = exchange_positions.get(pos.symbol)
            if exchange_pos is None:
                self.alert(f"DISCREPANCY: {pos.symbol} exists locally but not on exchange")
                self.portfolio.remove(pos)
            elif abs(exchange_pos.size - pos.size) > 0.01:
                self.alert(f"SIZE MISMATCH: {pos.symbol} local={pos.size} exchange={exchange_pos.size}")
                self.portfolio.update(pos.symbol, size=exchange_pos.size)
```

---

## 29. Phase 1 Sprint Board — Month 1-2 (120 Hours)

### 29.1 Sprint 1 (Week 1-2): Data Pipeline

| # | Task | Acceptance Criteria | Hours | Status |
|---|------|-------------------|-------|--------|
| 1.1 | **Project scaffold** | pyproject.toml, src/ structure, config/, tests/ | 3 | ⬜ |
| 1.2 | **Config system** | YAML loading, env vars, paper/live/backtest modes | 3 | ⬜ |
| 1.3 | **Core types** | FeatureVector, RegimeState, EngineSignal, Decision dataclasses | 4 | ⬜ |
| 1.4 | **Binance WS connector** | Connects, reconnects, receives OHLCV for BTC+ETH, 1m+1h+4h | 12 | ⬜ |
| 1.5 | **Funding + OI ingest** | Funding rate + OI polling every 5m, stored | 4 | ⬜ |
| 1.6 | **Parquet store** | Write/read OHLCV by symbol/timeframe, partitioned by month | 6 | ⬜ |
| 1.7 | **Redis cache** | Current candle, features, regime in Redis, <1ms read | 4 | ⬜ |
| 1.8 | **Historical data download** | Download 2+ years BTC+ETH 1h candles for backtesting | 4 | ⬜ |
| | **Sprint 1 Total** | | **40** | |

**Sprint 1 Gate:** `pytest tests/unit/test_data.py` passes. Can stream live data and read historical.

### 29.2 Sprint 2 (Week 3-4): Features + Regime

| # | Task | Acceptance Criteria | Hours | Status |
|---|------|-------------------|-------|--------|
| 2.1 | **Technical features (25)** | All Tier 1 non-ML features computed from OHLCV | 12 | ⬜ |
| 2.2 | **Microstructure features (5)** | Spread, imbalance, flow from orderbook data | 4 | ⬜ |
| 2.3 | **Crypto-native features (7)** | Funding percentile, OI change, liquidation est, basis | 6 | ⬜ |
| 2.4 | **Feature validation** | All 37 features: no NaN, correct range, backtested values match | 4 | ⬜ |
| 2.5 | **Sentinel data quality monitor** | 6 checks, quality score, alerts on degradation | 4 | ⬜ |
| 2.6 | **Regime Detector v2.0 (rules)** | Rule-based 4-state classification, tested on 2y BTC data | 8 | ⬜ |
| 2.7 | **Regime Detector (LightGBM)** | Train on labeled regime data, >70% accuracy OOS | 8 | ⬜ |
| 2.8 | **Regime consensus + transition** | Rule + ML agreement, CRISIS instant, 3-candle confirm others | 4 | ⬜ |
| | **Sprint 2 Total** | | **50** | |

**Sprint 2 Gate:** Feature pipeline produces validated FeatureVector every candle. Regime detector classifies 2+ years of BTC data with >70% accuracy when compared to manually labeled regimes.

### 29.3 Sprint 3 (Week 5-6): Risk + Backtest Framework

| # | Task | Acceptance Criteria | Hours | Status |
|---|------|-------------------|-------|--------|
| 3.1 | **RSL v2.0 core** | 4-level system, all triggers, all recovery conditions | 8 | ⬜ |
| 3.2 | **Pre-trade checks** | All 8 checks implemented and unit tested | 4 | ⬜ |
| 3.3 | **Kill switch** | Level 3 + Level 4 tested with synthetic scenarios | 3 | ⬜ |
| 3.4 | **Backtest engine** | Can replay historical data through feature→regime→signal→risk pipeline | 10 | ⬜ |
| 3.5 | **Walk-forward framework** | 5-fold time-series split, OOS metrics per fold | 5 | ⬜ |
| 3.6 | **Backtest metrics** | Sharpe, Sortino, MaxDD, Win Rate, PF, Calmar computed correctly | 3 | ⬜ |
| 3.7 | **Decision + Risk logging** | Every backtest decision logged to SQLite with full context | 3 | ⬜ |
| | **Sprint 3 Total** | | **36** | |

**Sprint 3 Gate:** Can run a dummy strategy through full backtest pipeline. RSL correctly triggers at all levels in synthetic stress scenarios. Walk-forward produces 5 OOS metric sets.

### 29.4 Phase 1 Summary

| Sprint | Weeks | Hours | Deliverable |
|--------|-------|-------|-------------|
| Sprint 1 | 1-2 | 40 | Data pipeline live + historical |
| Sprint 2 | 3-4 | 50 | 37 features + Regime detector |
| Sprint 3 | 5-6 | 36 | RSL + Backtest framework |
| **Total Phase 1** | **6 weeks** | **126h** | **Foundation complete, ready for engines** |

**AFTER Phase 1, the system can:**
- Stream live market data
- Compute 37+ validated features per candle
- Classify market regime in real-time
- Monitor data quality (Sentinel)
- Run any strategy through rigorous backtesting
- Enforce 4-level risk management
- Log every decision immutably

**AFTER Phase 1, the system CANNOT:**
- Generate trade signals (no engines yet)
- Execute trades (no execution engine yet)
- Use ML models (no training yet)

**This is intentional. The foundation must be rock-solid before any trading logic is added.**

---

## 30. Data Contracts & Interface Definitions

### 30.1 Inter-Module Communication

```
Every module communicates through TYPED, IMMUTABLE data objects.
No module reaches into another module's internals.
No global state. No shared mutable state.
```

#### 30.1.1 Master Data Flow Contract

```python
# ── Pipeline produces ──
MarketSnapshot → FeatureVector → Sentinel validates

# ── Regime consumes features, produces ──
FeatureVector → RegimeDetector → RegimeState

# ── Engines consume features + regime, produce ──
(FeatureVector, RegimeState) → Engine → Optional[EngineSignal]

# ── MDE consumes everything, produces ──
(RegimeState, dict[str, EngineSignal], PortfolioState, RiskState, 
 float, float) → MDE → Decision

# ── RSL validates decision ──
(Decision, PortfolioState) → RSL → RiskVerdict

# ── Execution acts on approved decision ──
Decision (approved) → ExecutionEngine → ExecutionResult

# ── LEL logs everything ──
(Decision, ExecutionResult, RegimeState, FeatureVector) → LEL → TradeRecord
```

#### 30.1.2 All Data Objects

```python
# ── Core Types ──

@dataclass(frozen=True)
class Decision:
    action: str           # "long" | "short" | "hold" | "close_all" | "reduce"
    position_size: float  # fraction of portfolio (0.0 - 0.15)
    leverage: float       # 1.0 - 3.0
    stop_loss: float      # fraction of price
    take_profit: float    # fraction of price
    confidence: float     # 0.0 - 1.0
    engine: Optional[str] # which engine decided
    reason: str           # human-readable explanation
    timestamp: datetime
    
@dataclass(frozen=True)
class RiskVerdict:
    approved: bool
    reason: str
    adjusted_decision: Optional[Decision] = None  # If RSL modified sizing
    risk_level: int = 0   # Current RSL level (0-4)
    
@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    order_id: Optional[str]
    fill_price: Optional[float]
    fill_quantity: Optional[float]
    slippage: Optional[float]
    fees: Optional[float]
    sl_order_id: Optional[str]
    reason: str
    timestamp: datetime

@dataclass(frozen=True)
class PortfolioState:
    total_equity: float
    available_balance: float
    positions: list       # list of Position objects
    has_positions: bool
    daily_pnl: float
    daily_pnl_pct: float
    drawdown: float       # current drawdown from peak
    peak_equity: float
    trades_today: int
    consecutive_losses: int
    equity_ma_20d: float
    timestamp: datetime

@dataclass(frozen=True)
class Position:
    symbol: str
    side: str              # "long" | "short"
    size: float            # in base currency
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    sl_price: float
    tp_price: Optional[float]
    entry_time: datetime
    duration_hours: float
    exchange_sl_order_id: str  # MUST exist

@dataclass(frozen=True)
class TradeRecord:
    trade_id: str
    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    fees: float
    slippage: float
    net_pnl_pct: float
    regime_at_entry: str
    regime_at_exit: str
    engine: str
    sub_strategy: str
    confidence_at_entry: float
    stop_distance: float
    duration_hours: float
    features_at_entry: dict  # snapshot of key features
    reason_entry: str
    reason_exit: str         # "stop_loss" | "take_profit" | "signal_reversal" | "manual" | "kill_switch"
```

### 30.2 Event System

```python
class EventBus:
    """
    Pub/Sub for system events. All modules can subscribe.
    Events are logged immutably.
    """
    
    EVENTS = [
        "candle_close",          # New candle closed → trigger feature compute
        "features_ready",        # Features computed → trigger regime + engines
        "regime_changed",        # Regime transition detected
        "signal_generated",      # Engine produced a signal
        "decision_made",         # MDE produced a decision
        "risk_verdict",          # RSL approved/rejected
        "order_placed",          # Order sent to exchange
        "order_filled",          # Order filled
        "position_opened",       # New position
        "position_closed",       # Position closed
        "stop_loss_hit",         # SL triggered
        "risk_level_changed",    # RSL level escalated/de-escalated
        "kill_switch_activated", # Emergency halt
        "data_quality_warning",  # Sentinel flagged issue
        "error",                 # Any error
        "alert",                 # Any alert requiring human attention
    ]
```

---

## 31. Mathematical Foundations — Formulas, Thresholds, Justifications

### 31.1 Position Sizing (Fixed Fractional — NOT Kelly)

**Formula:**

```
position_size = risk_per_trade / stop_distance

Where:
  risk_per_trade = base_risk × atlas_mult × sentinel × regime_conf × dd_mult × rsl_mult
  
  base_risk = 0.02 (2% of equity)
  
  atlas_mult = [0.0, 1.5] based on macro risk state
  sentinel = [0.0, 1.0] based on data quality
  regime_conf = [0.0, 1.0] from regime detector
  dd_mult = {DD<2%: 1.0, DD<4%: 0.5, DD<6%: 0.25, DD>6%: 0.0}
  rsl_mult = {Level 0: 1.0, Level 1: 0.5, Level 2+: 0.0 for new trades}
  
  stop_distance = engine's calculated stop (ATR-based, min 1%, max 5%)

Constraints:
  risk_per_trade ∈ [0.005, 0.03]    (0.5% minimum, 3% maximum)
  position_size ∈ [0.0, 0.15]       (0% to 15% of portfolio)
```

**Why NOT Kelly:**

```
Kelly optimal fraction: f* = (p × b - q) / b
  Where p = win rate, b = avg_win/avg_loss, q = 1-p

Problem: With < 500 trades, estimation error in p is ±5-8%.
If true p = 0.55 but estimated p = 0.48 (within error margin):
  Kelly says: DON'T TRADE (negative f*)
If true p = 0.55 but estimated p = 0.62:
  Kelly says: OVERSIZE (f* too large)

Fixed fractional at 2% base risk:
  - Survives 50 consecutive losses before losing 64% (never happens)
  - At $100 AUM: risking $2 per trade → even 10 losses = -$20 (survivable)
  - At $10K AUM: risking $200 per trade → scaled appropriately

Transition to Kelly: ONLY after 500+ trades AND win rate standard error < 3%
  (requires win rate estimated from 500+ samples: SE = sqrt(p(1-p)/n) ≈ 0.022)
```

### 31.2 Stop Loss Calculation

```
stop_distance = max(ATR(14) × multiplier, min_stop)
stop_distance = min(stop_distance, max_stop)

Where:
  multiplier = {
    TITAN trend_follow: 2.5  (trending → wider stops to avoid noise)
    TITAN breakout: 2.0      (breakout → tighter, momentum should carry)
    NAUTILUS bb_reversion: 1.0 (mean-rev → tight stops, wrong if range breaks)
    NAUTILUS funding: 3.0    (funding → wide, carry trades need room)
    PHOENIX funding: 2.5     (carry → wide)
    PHOENIX basis: 3.0       (basis → widest, convergence takes time)
  }
  
  min_stop = 0.01 (1% — below this, noise will stop us out)
  max_stop = 0.05 (5% — above this, risk per trade becomes unmanageable)
```

### 31.3 Regime Detection Thresholds — With Justification

| Threshold | Value | Mathematical Basis |
|-----------|-------|--------------------|
| **ADX trending threshold** | 25 | Industry standard. ADX creator (Wilder) defined >25 as "trending". Backtested on BTC 2020-2025: ADX>25 captures 85%+ of major moves. |
| **ADX ranging threshold** | 20 | Below 20, mean-reversion strategies outperform trend-following by 2:1 in BTC backtests. |
| **ATR ratio for volatility** | 1.8 | ATR(5)/ATR(20) > 1.8 means short-term vol is nearly 2x long-term. Statistically, this is >95th percentile of ATR ratio distribution in BTC. |
| **Hurst < 0.45 for ranging** | 0.45 | H=0.5 is random walk. H<0.5 is mean-reverting. 0.45 gives buffer. Computed on rolling 100 periods using rescaled range method. |
| **Crisis: -8% in 24h** | 8% | BTC drops >8% in 24h approximately 10-15 times per year. This captures genuine crashes without triggering on normal volatility. Checked against 2020-2025 data. |
| **Confirmation candles** | 3 | Balances speed vs accuracy. 1 candle = too many false transitions. 5 candles = too slow. 3 candles on 1h TF = 3 hour delay, acceptable for non-crisis transitions. |
| **Funding extreme (95th pctile)** | 95% | By definition, funding is at this level 5% of the time. These are the extreme crowding events where mean-reversion has highest edge. |
| **BB entry (%B < 0.05)** | 0.05 | Price at lower BB = %B ≈ 0. Requiring <0.05 means price is AT or BELOW lower band. Combined with RSI<30, this captures genuine oversold + mean-rev setups. |

### 31.4 Risk Thresholds — With Justification

| Threshold | Value | Justification |
|-----------|-------|---------------|
| **Daily loss soft cap** | -1.5% | At $100 AUM = $1.50 loss. At $10K = $150. Conservative enough to prevent ruin. -2% daily is common in institutional (we're tighter because of lower AUM and less diversification). |
| **Daily loss hard cap** | -2.5% | Emergency level. If we lose 2.5% in a day, something is either very wrong or market is doing something extreme. Either way, stop. |
| **DD kill switch** | -6% | Recovery math: -6% requires +6.4% to recover. -10% requires +11.1%. -20% requires +25%. We want to keep recovery manageable. At -6%, we can recover in 1-2 good weeks. At -10%, it takes a month+. |
| **Max position 15%** | 15% | With 2 pairs (BTC+ETH), max total exposure = 30%. This prevents catastrophic single-position loss. Even if stop fails and we lose 2x stop distance, max loss = 15% × 10% = 1.5% of portfolio. |
| **Max leverage 2.0** | 2.0 | With 6% DD kill switch and 2x leverage, a 3% adverse move at full size = 6% loss = kill switch. This is the maximum leverage where our kill switch math still works. At 3x, a 2% move would trigger kill switch. |
| **Cooldown 3 losses** | 3 | 3 consecutive losses at 2% risk each = -6% → exactly at kill switch. Cooldown kicks in to prevent reaching kill switch. After 3 losses, system pauses to re-evaluate. |
| **Equity curve MA(20d)** | 20d | 20 trading days ≈ 1 month. If equity is below its 1-month moving average, the system is in drawdown phase. Reducing size here prevents deeper drawdowns. Similar to "trend following the equity curve" — a well-studied risk management technique. |

### 31.5 Expected Performance Model

```
Assumptions (conservative):
  Win rate: 52% (barely above random — realistic for first 6 months)
  Avg win: 2.5% (on the position, not portfolio)
  Avg loss: 1.8% (stopped out at ~2x ATR average)
  Avg position size: 8% of portfolio
  Trades per week: 3-5
  
Portfolio-level per trade:
  Avg portfolio win: 8% × 2.5% = +0.20%
  Avg portfolio loss: 8% × 1.8% = -0.14%
  
  Expected value per trade = 0.52 × 0.20% - 0.48 × 0.14% = +0.0368%
  
  Weekly (4 trades): +0.147%
  Monthly (16 trades): +0.589%
  Annual (192 trades): +7.3% (conservative baseline)

If win rate improves to 55% with ML:
  EV per trade = 0.55 × 0.20% - 0.45 × 0.14% = +0.047%
  Annual: +9.4%
  
If Sharpe improves to 1.5 (target):
  With 10% annualized vol → 15% annual return
  With 15% annualized vol → 22.5% annual return
  
IMPORTANT: These are CONSERVATIVE estimates. Target is higher but plan for reality.
At $100 AUM, even 50% annual = $50. We need both % return AND capital growth.
```

---

---

## SECTION 32: ARGUS CHIEF ARCHITECT DESIGN PACKAGE (v1.0)

```
============================================================================
  ARGUS CHIEF ARCHITECT DESIGN PACKAGE
  Role: Chief Architect (Opus)
  Purpose: Final authoritative design — consolidates and SUPERSEDES all
           previous architectural decisions where conflicts exist.
  Scope: 9 deliverables (32A-32I) + 5 additional requirements
  Rule: THIS SECTION IS THE SOURCE OF TRUTH for implementation.
        If Section 28 says X and Section 32 says Y, Section 32 wins.
============================================================================
```

---

### 32A: ONE-PAGE SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARGUS ALL-WEATHER FUND MANAGEMENT SYSTEM                  │
│                        Chief Architect Design v1.0                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────── LAYER 0: DATA ──────────────────────────┐     │
│  │                                                                     │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │     │
│  │  │ Binance  │  │ Bybit    │  │CoinGecko │  │ CryptoPanic      │   │     │
│  │  │ WS+REST  │  │ REST     │  │ REST     │  │ REST             │   │     │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │     │
│  │       │              │              │                 │             │     │
│  │       └──────────────┴──────────────┴─────────────────┘             │     │
│  │                              │                                      │     │
│  │                    ┌─────────▼──────────┐                           │     │
│  │                    │    SENTINEL        │ ◄── Data Quality Gate     │     │
│  │                    │ (6 health checks)  │     score: 0.0-1.0       │     │
│  │                    └─────────┬──────────┘                           │     │
│  │                              │ (validated data)                     │     │
│  │                    ┌─────────▼──────────┐                           │     │
│  │                    │   SNAPSHOT BUILDER  │ ◄── MarketSnapshot       │     │
│  │                    │ (50 features + OB)  │     + FeatureVector      │     │
│  │                    └─────────┬──────────┘                           │     │
│  └──────────────────────────────┼──────────────────────────────────────┘     │
│                                 │                                            │
│  ┌──────────────────────────────▼─────────────────────────────────────┐     │
│  │                    LAYER 1: REGIME DETECTION                        │     │
│  │                                                                     │     │
│  │  ┌────────────┐  ┌──────────────┐  ┌──────────────┐               │     │
│  │  │ Rule-Based │  │ Volatility   │  │ Microstructure│               │     │
│  │  │ (ADX/Hurst)│  │ Classifier   │  │ Classifier   │               │     │
│  │  └──────┬─────┘  └──────┬───────┘  └──────┬───────┘               │     │
│  │         └───────────────┼──────────────────┘                       │     │
│  │                  ┌──────▼───────┐                                   │     │
│  │                  │  CONSENSUS   │ ◄── 3-of-4 rule                  │     │
│  │                  │              │     Output: RegimeState           │     │
│  │                  └──────┬───────┘     (TRENDING|RANGING|            │     │
│  │                         │              VOLATILE|CRISIS)             │     │
│  └─────────────────────────┼──────────────────────────────────────────┘     │
│                             │                                                │
│  ┌──────────────────────────▼─────────────────────────────────────────┐     │
│  │                    LAYER 2: ENGINE PORTFOLIO                        │     │
│  │                                                                     │     │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐              │     │
│  │  │   TITAN     │  │  NAUTILUS    │  │   PHOENIX   │              │     │
│  │  │ Trend/Mom   │  │ Mean-Rev    │  │  Carry/Basis│              │     │
│  │  │             │  │             │  │             │              │     │
│  │  │ Active:     │  │ Active:     │  │ Active:     │              │     │
│  │  │ TRENDING    │  │ RANGING     │  │ ALL except  │              │     │
│  │  │ only        │  │ only        │  │ CRISIS      │              │     │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │     │
│  │         │                │                 │                      │     │
│  │         └────────────────┼─────────────────┘                      │     │
│  │                   ┌──────▼───────┐                                 │     │
│  │                   │  ATLAS       │ ◄── Risk Multiplier Overlay    │     │
│  │                   │  (0.0-1.5)   │     Macro/Cross-Asset          │     │
│  │                   └──────┬───────┘                                 │     │
│  └──────────────────────────┼──────────────────────────────────────────┘     │
│                              │                                               │
│  ┌───────────────────────────▼────────────────────────────────────────┐     │
│  │                    LAYER 3: MDE (ROUTING)                          │     │
│  │                                                                     │     │
│  │  GATE 0: Sentinel score ── GATE 1: Crisis check ──                │     │
│  │  GATE 2: RSL level ── GATE 3: Get signal from lead engine ──      │     │
│  │  GATE 4: Confidence ── GATE 5: Net return ── GATE 6: R:R ──      │     │
│  │  ── SIZING (fixed fractional, 2% base) ──► Decision               │     │
│  └───────────────────────────┬────────────────────────────────────────┘     │
│                               │                                              │
│  ┌────────────────────────────▼───────────────────────────────────────┐     │
│  │                    LAYER 4: RISK (RSL)                             │     │
│  │                                                                     │     │
│  │  8 Pre-Trade Checks ── Position Limits ── Drawdown Monitor ──     │     │
│  │  Kill Switch (5 levels: NORMAL→CAUTION→DEFENSIVE→HALT→LOCKDOWN)   │     │
│  │  ── Output: RiskVerdict (approved/rejected/adjusted)               │     │
│  └────────────────────────────┬───────────────────────────────────────┘     │
│                                │                                             │
│  ┌─────────────────────────────▼──────────────────────────────────────┐     │
│  │                    LAYER 5: EXECUTION                              │     │
│  │                                                                     │     │
│  │  Order Router ── 4 Urgency Levels ── Exchange-Side SL (MANDATORY)  │     │
│  │  ── Slippage Monitor ── Fill Reconciler                            │     │
│  └─────────────────────────────┬──────────────────────────────────────┘     │
│                                 │                                            │
│  ┌──────────────────────────────▼─────────────────────────────────────┐     │
│  │                    LAYER 6: TELEMETRY + LEARNING                   │     │
│  │                                                                     │     │
│  │  ┌───────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐  │     │
│  │  │Trade      │  │Feature     │  │Performance │  │Decay        │  │     │
│  │  │Logger     │  │Drift       │  │Attribution │  │Detector     │  │     │
│  │  └───────────┘  └────────────┘  └────────────┘  └─────────────┘  │     │
│  └──────────────────────────────┬─────────────────────────────────────┘     │
│                                  │                                           │
│  ┌───────────────────────────────▼────────────────────────────────────┐     │
│  │                    LAYER 7: OPS + INTERFACE                        │     │
│  │                                                                     │     │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐ │     │
│  │  │ Supervisor │  │ Dashboard  │  │ Telegram   │  │ Health      │ │     │
│  │  │ (watchdog) │  │ (Streamlit)│  │ Bot        │  │ Endpoints   │ │     │
│  │  └────────────┘  └────────────┘  └────────────┘  └─────────────┘ │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    RESEARCH NODE (OFFLINE)                         │     │
│  │                                                                     │     │
│  │  GPU Training ── Walk-Forward ── Hyperparameter Search ──          │     │
│  │  Model Registry ── Deployment Gate ── Artifact Signing             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

DATA FLOW (simplified):
  Exchange → Sentinel → Snapshot → Regime → Engine(s) → MDE → RSL → Executor
       ↓                                                           ↓
  Telemetry ◄──────────────────────────────────────────────────────┘
       ↓
  Dashboard / Telegram / Health API
```

**Key Invariant:** Data flows DOWN through layers. No layer may call upward.
The only exception: Kill Switch (Layer 4) can halt Execution (Layer 5) directly.

**Codex TODO:**
- [ ] Create `src/core/layers.py` with layer enum and dependency validation
- [ ] Implement layer boundary checks in `__init__.py` of each module
- [ ] Create architecture validation test: no import from lower layer to upper layer

---

### 32B: MODULE BOUNDARIES + AUTHORITATIVE FILE TREE

**Reconciliation Note:** Section 28 contains a folder structure from the v1.0 era that still references
Orion/Aegean/Atlas(engine)/Hermes/Helios. Section 27 reduced engines to TITAN/NAUTILUS/PHOENIX + 
ATLAS(overlay)/SENTINEL(overlay). **This section provides the AUTHORITATIVE v2.0 folder structure.**

```
argus-terminal/
├── README.md
├── pyproject.toml                     # uv/pip, Python 3.11+
├── requirements.txt                   # pinned versions
├── requirements-research.txt          # GPU/ML dependencies (Research Node only)
├── .env.example
├── .gitignore
├── Makefile                           # lint, test, type-check, build shortcuts
│
├── config/
│   ├── base.yaml                      # shared defaults
│   ├── production.yaml                # live trading overrides
│   ├── paper.yaml                     # paper trading overrides
│   ├── backtest.yaml                  # backtest overrides
│   ├── regimes.yaml                   # regime thresholds (ADX, Hurst, ATR ratio)
│   ├── engines.yaml                   # per-engine parameters (TITAN, NAUTILUS, PHOENIX)
│   ├── risk.yaml                      # RSL thresholds, kill switch triggers, pre-trade checks
│   └── telemetry.yaml                 # event types, destinations, sampling rates
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                          # SHARED KERNEL (no business logic)
│   │   ├── __init__.py
│   │   ├── types.py                   # ALL frozen dataclasses (FeatureVector, RegimeState,
│   │   │                              #   EngineSignal, Decision, RiskVerdict, ExecutionResult,
│   │   │                              #   PortfolioState, Position, TradeRecord, MarketSnapshot)
│   │   ├── config.py                  # YAML loader, typed config objects, env overlay
│   │   ├── events.py                  # EventBus (pub/sub), 17 event types
│   │   ├── clock.py                   # Unified clock (live=real, backtest=simulated)
│   │   ├── exceptions.py             # Custom exceptions (DataStale, SentinelHalt, etc.)
│   │   └── constants.py              # Magic numbers with docstrings
│   │
│   ├── data/                          # LAYER 0: DATA PIPELINE
│   │   ├── __init__.py
│   │   ├── ingest/
│   │   │   ├── __init__.py
│   │   │   ├── binance_ws.py         # WebSocket: OHLCV, mark price, funding, orderbook
│   │   │   ├── binance_rest.py       # REST fallback: OI, liquidations, historical
│   │   │   ├── bybit_rest.py         # Cross-validation source
│   │   │   ├── coingecko.py          # BTC dominance, total market cap
│   │   │   └── fear_greed.py         # CryptoPanic fear/greed
│   │   ├── sentinel/                  # SENTINEL OVERLAY (data quality gate)
│   │   │   ├── __init__.py
│   │   │   ├── validator.py          # 6 health checks, outputs data_quality_score
│   │   │   └── anomaly.py            # Statistical anomaly flags
│   │   ├── features/
│   │   │   ├── __init__.py
│   │   │   ├── technical.py          # Volatility(6) + Trend(6) + Momentum(5) features
│   │   │   ├── volume.py             # Volume(5) features
│   │   │   ├── microstructure.py     # Microstructure(5) features
│   │   │   ├── crypto_native.py      # Crypto-Native(7) features
│   │   │   ├── cross_asset.py        # Cross-Asset(4) features
│   │   │   ├── statistical.py        # Statistical(4) features
│   │   │   └── ml_features.py        # ML Output(8) -- wraps model inference
│   │   ├── store/
│   │   │   ├── __init__.py
│   │   │   ├── parquet_store.py      # Warm storage: daily parquet files
│   │   │   └── sqlite_store.py       # Trade logs, metadata (simpler than TimescaleDB)
│   │   └── snapshot.py               # Assembles MarketSnapshot + FeatureVector
│   │
│   ├── regime/                        # LAYER 1: REGIME DETECTION
│   │   ├── __init__.py
│   │   ├── rule_based.py             # ADX + Hurst + ATR ratio + price/MA alignment
│   │   ├── volatility_classifier.py  # Realized vol vs median, ATR ratio
│   │   ├── microstructure_cls.py     # Spread + depth + flow based regime hints
│   │   ├── consensus.py              # 3-of-4 vote, hysteresis, confirmation window
│   │   └── state_machine.py          # Regime state machine with transition rules (32D)
│   │
│   ├── engines/                       # LAYER 2: ENGINE PORTFOLIO
│   │   ├── __init__.py
│   │   ├── base.py                   # AbstractEngine: generate_signal(snapshot, regime) -> Optional[EngineSignal]
│   │   ├── titan/                    # TREND/MOMENTUM ENGINE
│   │   │   ├── __init__.py
│   │   │   ├── engine.py             # TitanEngine(AbstractEngine)
│   │   │   ├── trend_follow.py       # EMA cross + ADX + ATR trailing
│   │   │   └── breakout.py           # Donchian breakout + volume + confirmation
│   │   ├── nautilus/                 # MEAN-REVERSION ENGINE
│   │   │   ├── __init__.py
│   │   │   ├── engine.py             # NautilusEngine(AbstractEngine)
│   │   │   ├── bb_reversion.py       # Bollinger Band reversion + RSI
│   │   │   └── funding_reversion.py  # Funding rate mean-reversion
│   │   ├── phoenix/                  # CARRY/BASIS ENGINE
│   │   │   ├── __init__.py
│   │   │   ├── engine.py             # PhoenixEngine(AbstractEngine)
│   │   │   ├── funding_harvest.py    # Funding rate carry
│   │   │   └── basis_trade.py        # Spot-perp basis arbitrage
│   │   └── atlas/                    # ATLAS OVERLAY (risk multiplier)
│   │       ├── __init__.py
│   │       └── risk_overlay.py       # Macro signals -> risk_multiplier [0.0, 1.5]
│   │
│   ├── mde/                           # LAYER 3: META-DECISION ENGINE (ROUTING)
│   │   ├── __init__.py
│   │   ├── router.py                 # Regime -> lead engine selection + signal dispatch
│   │   ├── gates.py                  # 7 sequential gates (Gate 0-6)
│   │   └── sizing.py                 # Fixed fractional position sizing
│   │
│   ├── risk/                          # LAYER 4: RISK SAFETY LAYER (RSL)
│   │   ├── __init__.py
│   │   ├── rsl.py                    # RSL controller: level management, transitions
│   │   ├── pre_trade.py              # 8 pre-trade checks -> pass/fail
│   │   ├── drawdown.py               # DD tracking, peak equity, MA(20d)
│   │   ├── kill_switch.py            # 5-level kill switch state machine
│   │   └── cooldown.py               # Post-loss cooldown logic
│   │
│   ├── execution/                     # LAYER 5: EXECUTION
│   │   ├── __init__.py
│   │   ├── executor.py               # Main executor: Decision -> exchange orders
│   │   ├── order_router.py           # Urgency-based order type selection
│   │   ├── sl_manager.py             # Exchange-side stop loss placement + verification
│   │   └── reconciler.py             # Fill verification, position vs exchange state
│   │
│   ├── telemetry/                     # LAYER 6: TELEMETRY + LEARNING
│   │   ├── __init__.py
│   │   ├── trade_logger.py           # TradeRecord persistence
│   │   ├── event_logger.py           # All telemetry events (10+ schemas per 32F)
│   │   ├── attribution.py            # Per-engine, per-strategy P&L attribution
│   │   ├── drift_detector.py         # Feature distribution drift monitoring
│   │   └── decay_detector.py         # Strategy performance decay detection
│   │
│   ├── ops/                           # LAYER 7: OPS + SUPERVISION
│   │   ├── __init__.py
│   │   ├── supervisor.py             # Watchdog process, heartbeat, restart logic
│   │   ├── health.py                 # Health check HTTP endpoint
│   │   └── alerts.py                 # Alert routing (Telegram, log, email)
│   │
│   ├── interface/                     # LAYER 7: USER INTERFACE
│   │   ├── __init__.py
│   │   ├── telegram_bot.py           # Commands: /status, /stop, /pnl, /regime
│   │   └── dashboard.py              # Streamlit dashboard (optional, Phase 3+)
│   │
│   ├── ml/                            # RESEARCH NODE (offline, not in live path)
│   │   ├── __init__.py
│   │   ├── chronos/
│   │   │   ├── predictor.py          # Inference wrapper for Chronos-Bolt
│   │   │   └── fine_tune.py          # LoRA fine-tuning pipeline
│   │   ├── lgbm_model.py             # LightGBM direction classifier
│   │   ├── meta_labeler.py           # Triple-barrier meta-labeling
│   │   ├── model_registry.py         # Artifact versioning, metadata, acceptance gate
│   │   └── training/
│   │       ├── walk_forward.py       # Walk-forward cross-validation
│   │       ├── feature_eng.py        # Feature engineering pipeline
│   │       └── hyperopt.py           # Optuna-based hyperparameter search
│   │
│   ├── backtest/                      # BACKTEST ENGINE
│   │   ├── __init__.py
│   │   ├── backtester.py             # Event-driven backtester (uses same pipeline)
│   │   ├── walk_forward.py           # Walk-forward validation harness
│   │   ├── monte_carlo.py            # Monte Carlo permutation tests
│   │   ├── fee_model.py              # Realistic fee + slippage model
│   │   └── regime_stress.py          # Per-regime stress testing
│   │
│   └── main.py                        # Entry point: argparse, mode selection, startup
│
├── tests/
│   ├── conftest.py                    # Shared fixtures (sample data, mock exchange)
│   ├── unit/
│   │   ├── test_types.py             # Dataclass validation
│   │   ├── test_sentinel.py          # Sentinel scoring
│   │   ├── test_features.py          # Feature computation correctness
│   │   ├── test_regime.py            # Regime detection logic
│   │   ├── test_titan.py             # TITAN signal generation
│   │   ├── test_nautilus.py          # NAUTILUS signal generation
│   │   ├── test_phoenix.py           # PHOENIX signal generation
│   │   ├── test_atlas.py             # ATLAS risk multiplier
│   │   ├── test_mde.py               # MDE routing + gates
│   │   ├── test_sizing.py            # Position sizing math
│   │   ├── test_rsl.py               # RSL level transitions
│   │   ├── test_kill_switch.py       # Kill switch state machine
│   │   └── test_pre_trade.py         # Pre-trade checks
│   ├── integration/
│   │   ├── test_pipeline.py          # Full data->decision pipeline
│   │   ├── test_execution.py         # Order placement (mock exchange)
│   │   └── test_telemetry.py         # Event logging verification
│   └── stress/
│       ├── test_crash_scenario.py    # Simulated crash handling
│       └── test_regime_transition.py # Rapid regime flipping
│
├── scripts/
│   ├── run_live.py                    # python scripts/run_live.py --config production
│   ├── run_paper.py                   # python scripts/run_paper.py --config paper
│   ├── run_backtest.py               # python scripts/run_backtest.py --config backtest
│   ├── verify_gpu.py                 # GPU/CUDA verification
│   ├── train_models.py               # ML training orchestrator
│   └── promote_model.py             # Model promotion from Research -> Production
│
├── data/
│   ├── ohlcv/                         # Parquet files
│   ├── models/                        # Trained model artifacts
│   ├── backtest_results/
│   └── trade_logs/
│
└── Docs/
    └── FUTURE_VISION.md               # This document
```

**Module Boundary Contracts:**

| Module | Responsibility | Inputs | Outputs | Invariants |
|--------|---------------|--------|---------|------------|
| `data.ingest` | Raw data acquisition | Exchange APIs | Raw OHLCV, OB, funding | Must reconnect within 30s on failure |
| `data.sentinel` | Data quality scoring | Raw data streams | `data_quality_score: float` | Score < 0.4 halts all trading |
| `data.features` | Feature computation | Raw data | `FeatureVector` (50 fields) | All features computed < 2000ms |
| `data.snapshot` | Snapshot assembly | Features + OB + state | `MarketSnapshot` | Snapshot is immutable once created |
| `regime` | Market state classification | `FeatureVector` | `RegimeState` | Transition requires confirmation window |
| `engines.titan` | Trend/momentum signals | Snapshot + RegimeState | `Optional[EngineSignal]` | Only fires when regime=TRENDING |
| `engines.nautilus` | Mean-reversion signals | Snapshot + RegimeState | `Optional[EngineSignal]` | Only fires when regime=RANGING |
| `engines.phoenix` | Carry/basis signals | Snapshot + RegimeState | `Optional[EngineSignal]` | Fires in ALL except CRISIS |
| `engines.atlas` | Risk multiplier | Snapshot + RegimeState | `risk_multiplier: float` | Output in [0.0, 1.5] always |
| `mde` | Signal routing + sizing | Signals + Regime + RSL state | `Decision` | Exactly one lead engine per regime |
| `risk` | Risk gate + kill switch | `Decision` + `PortfolioState` | `RiskVerdict` | Can ONLY reject or reduce, never amplify |
| `execution` | Order management | `Decision` (approved) | `ExecutionResult` | Exchange-side SL MUST exist before confirming |
| `telemetry` | Event logging + analysis | All layer events | Persisted events + alerts | Every decision is logged, no exceptions |
| `ops` | Process supervision | Health checks | Restart/alert actions | Heartbeat failure = alert within 60s |
| `ml` | Offline model training | Historical data | Model artifacts + metadata | Never runs in live trading process |

**Codex TODO:**
- [ ] Create all directories and `__init__.py` files per this tree
- [ ] Implement `src/core/types.py` with all 10 frozen dataclasses from Section 30
- [ ] Implement `src/core/config.py` with YAML loading for all config files
- [ ] Implement `src/core/events.py` with EventBus and 17 event types
- [ ] Create `config/` YAML files with defaults from Section 28/31
- [ ] Write `tests/unit/test_types.py` to validate all dataclass constraints

---

### 32C: DECISION PIPELINE — END-TO-END LIFECYCLE

Every trading decision follows this exact pipeline. No shortcuts, no bypasses.

```
STEP 1: DATA ACQUISITION (Layer 0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Trigger: New 1h candle close (primary), or 5m/15m for sub-signals
  
  1a. binance_ws delivers: OHLCV, mark_price, funding_rate, orderbook_l2
  1b. binance_rest polls: open_interest (5m), liquidations (1m)
  1c. bybit_rest polls: cross-validation OHLCV + funding (5m)
  1d. coingecko polls: BTC dominance, total market cap (5m)
  1e. fear_greed polls: Fear/Greed index (15m)
  
  Output: Raw data buffers (in-memory ring buffers + parquet persistence)
  Latency budget: < 500ms from candle close

STEP 2: SENTINEL VALIDATION (Layer 0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: Raw data buffers
  
  Check 1: Data staleness — any source > 2x expected interval?
  Check 2: Price anomaly — price move > 3 sigma without volume confirmation?
  Check 3: Spread blowout — spread > 5x normal?
  Check 4: Exchange latency — response time > 2s?
  Check 5: Orderbook depth — depth < 30% normal within 5% of mid?
  Check 6: Funding flash spike — funding > 10x normal?
  
  Output: data_quality_score (0.0-1.0)
  
  DECISION POINT:
    score >= 0.7  → proceed normally
    score 0.4-0.7 → proceed with 30% confidence reduction on all engines
    score < 0.4   → HALT: no new trades, emit sentinel_halt event
    score < 0.2   → EMERGENCY: close all positions, alert owner
  
  Latency budget: < 100ms

STEP 3: SNAPSHOT BUILD (Layer 0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: Validated data + historical buffers
  
  3a. Compute 50 features (FeatureVector)
      - Volatility(6), Trend(6), Momentum(5), Volume(5)
      - Microstructure(5), Crypto-Native(7), Cross-Asset(4), Statistical(4)
      - ML Output(8) — only if models are deployed and warm
  3b. Assemble MarketSnapshot:
      - timestamp, symbol, features, orderbook_summary,
        portfolio_state, sentinel_score
  3c. Snapshot is FROZEN (immutable) — all subsequent layers use this exact snapshot
  
  Output: MarketSnapshot (frozen)
  Latency budget: < 2000ms (feature computation is the bottleneck)

STEP 4: REGIME DETECTION (Layer 1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: MarketSnapshot.features
  
  4a. Rule-based classifier:
      - ADX(14) > 25 → TRENDING vote
      - ADX(14) < 20 AND Hurst < 0.45 → RANGING vote
      - ATR(5)/ATR(20) > 1.8 → VOLATILE vote
      - Price drop > 8%/24h OR vol > 3x 60d median → CRISIS vote
  4b. Volatility classifier:
      - Realized vol vs 60-day distribution percentile
  4c. Microstructure classifier:
      - Spread + depth + flow patterns
  4d. (Future) ML classifier:
      - regime_prob_* from FeatureVector
  
  4e. CONSENSUS: 3-of-4 agreement required for TRENDING/RANGING
      - VOLATILE: any 1 indicator sufficient
      - CRISIS: any 1 indicator sufficient (safety bias)
  
  4f. STATE MACHINE (see 32D):
      - Apply hysteresis: must hold for confirmation_window candles
      - Check transition rules
      - Update candles_in_regime counter
  
  Output: RegimeState (frozen)
  Latency budget: < 200ms

STEP 5: ENGINE SIGNAL GENERATION (Layer 2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: MarketSnapshot + RegimeState
  
  5a. ATLAS overlay computes risk_multiplier:
      - Analyze BTC dominance, total mcap momentum, stablecoin flows
      - Output: risk_multiplier ∈ [0.0, 1.5]
      - If multiplier == 0.0 → CRISIS overlay, skip engines
  
  5b. Route to LEAD ENGINE based on regime:
      TRENDING → TITAN
      RANGING  → NAUTILUS
      VOLATILE → PHOENIX
      CRISIS   → None (no engine leads)
  
  5c. Lead engine generates signal:
      - Evaluates sub-strategies
      - Picks strongest sub-strategy signal
      - Applies MIN_CONFIDENCE = 0.55 gate
      - If no signal passes gate → return None
  
  5d. PHOENIX always runs as fallback (except CRISIS):
      - If lead engine returned None, PHOENIX signal is used
      - If lead engine returned signal, PHOENIX is ignored
  
  Output: Optional[EngineSignal]
  Latency budget: < 500ms per engine

STEP 6: MDE ROUTING + GATES (Layer 3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: Optional[EngineSignal] + RegimeState + PortfolioState + sentinel_score + rsl_level
  
  Sequential gate evaluation (MUST pass ALL):
  
  GATE 0: sentinel_score < 0.4 → HOLD ("Data quality critical")
  GATE 1: regime == CRISIS → CLOSE_ALL (if positions) or HOLD
  GATE 2: rsl_level >= 3 → HOLD; rsl_level >= 2 → only PHOENIX allowed
  GATE 3: signal is None → HOLD ("No valid signal")
  GATE 4: signal.confidence < 0.55 → HOLD ("Low confidence")
  GATE 5: signal.net_expected_return < 0.001 → HOLD ("Insufficient edge")
  GATE 6: signal.reward_risk_ratio < 1.5 → HOLD ("Bad R:R")
  
  ALL GATES PASSED → compute position size:
  
  risk_per_trade = 0.02 × atlas_mult × sentinel × regime_conf × dd_mult × rsl_mult
  risk_per_trade = clamp(risk_per_trade, 0.005, 0.03)
  position_size  = risk_per_trade / signal.stop_distance
  position_size  = clamp(position_size, 0.0, 0.15)
  leverage       = min(position_size / available_margin_pct, MAX_LEVERAGE)
  
  Output: Decision (frozen)
  Latency budget: < 100ms

STEP 7: RISK VERIFICATION (Layer 4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: Decision + PortfolioState
  
  8 pre-trade checks (ALL must pass):
    ✓ position_size <= 0.15
    ✓ leverage <= MAX_LEVERAGE (2.0 in Year 1)
    ✓ trades_today < 15
    ✓ not within 15min of funding settlement
    ✓ weekend limit respected (if applicable)
    ✓ correlation with existing positions OK
    ✓ stop_loss > 0
    ✓ stop_loss <= 0.05
  
  Kill switch check:
    Level 0 → full go
    Level 1 → reduce size to 75%
    Level 2 → reduce size to 40%, only PHOENIX
    Level 3+ → reject
  
  Output: RiskVerdict (approved: bool, adjusted_decision: Optional[Decision])
  Latency budget: < 50ms

STEP 8: EXECUTION (Layer 5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: Approved Decision
  
  8a. Select urgency level:
      EMERGENCY: kill switch trigger → market order
      HIGH: confidence > 0.8 → aggressive limit (mid + 1 tick)
      NORMAL: standard → limit at mid
      LOW: carry trade → passive limit (best bid/ask)
  
  8b. Place entry order
  8c. Wait for fill (with timeout per urgency)
  8d. On fill: IMMEDIATELY place exchange-side stop loss
      *** SL MUST be confirmed on exchange before proceeding ***
  8e. Place take profit order (if applicable)
  8f. Reconcile: verify position matches expected state
  
  Output: ExecutionResult (frozen)
  Latency budget: < 5s total (including SL confirmation)

STEP 9: TELEMETRY + AUDIT (Layer 6)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: All outputs from Steps 1-8
  
  Events emitted (see 32F for full schemas):
    - regime_snapshot (every candle)
    - signal_generated (when engine produces signal)
    - decision_made (MDE output, including HOLD decisions)
    - risk_check (RSL verdict)
    - order_submitted (to exchange)
    - order_filled (confirmed)
    - order_rejected (failed)
    - heartbeat (every 60s)
  
  All events include: timestamp, run_id, inputs_hash (SHA256 of snapshot)
  
  Output: Persisted events + alerts (if needed)

STEP 10: POST-TRADE EVALUATION (Layer 6, async)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Runs asynchronously after trade lifecycle:
  
  10a. Update PortfolioState (equity, DD, P&L)
  10b. Update RSL level (check if level should change)
  10c. Update consecutive loss counter
  10d. Attribution: which engine/strategy generated this P&L?
  10e. Feature drift check: are input distributions shifting?
  10f. Decay check: is this strategy's recent performance degrading?
  10g. If daily close: generate daily_report event
  
  Output: Updated state + potential alerts
```

**Total Pipeline Latency Budget:** < 10 seconds from candle close to order placed.

**Critical Path:** Snapshot Build (2000ms) → Regime (200ms) → Engine (500ms) → MDE (100ms) → RSL (50ms) → Execution (5000ms) = ~7.85s

**Codex TODO:**
- [ ] Implement `src/main.py` with the 10-step pipeline as the main loop
- [ ] Create `src/core/pipeline.py` with a `PipelineOrchestrator` class that enforces step ordering
- [ ] Add latency tracking to every step (emit latency_ms in telemetry)
- [ ] Write integration test `tests/integration/test_pipeline.py` that runs full pipeline with mock data
- [ ] Implement circuit breaker: if any step exceeds 2x its latency budget, emit alert

---

### 32D: REGIME STATE MACHINE v3.0

**Reconciliation:** Section 27.5 defined 4 states (TRENDING, RANGING, VOLATILE, CRISIS) with basic
transitions. Section 28 added confirmation candles. This section provides the COMPLETE state machine
with full transition rules, hysteresis, crash handling, and recovery.

```
                    ┌──────────────────────────────┐
                    │         STATE MACHINE         │
                    │                                │
                    │   ┌────────────────────────┐  │
    ┌───────────────┼──►│      TRENDING          │  │
    │               │   │                        │  │
    │               │   │  Lead: TITAN           │  │
    │               │   │  ADX>25, price aligned │  │
    │   ┌───────────┼───┤  with MA(50) 20+ bars  │  │
    │   │           │   └──────────┬─────────────┘  │
    │   │           │              │                  │
    │   │           │   ┌──────────▼─────────────┐  │
    │   │   ┌───────┼──►│      RANGING           │  │
    │   │   │       │   │                        │  │
    │   │   │       │   │  Lead: NAUTILUS        │  │
    │   │   │       │   │  ADX<20, Hurst<0.45    │  │
    │   │   │   ┌───┼───┤  BB(20,2) 20+ bars     │  │
    │   │   │   │   │   └──────────┬─────────────┘  │
    │   │   │   │   │              │                  │
    │   │   │   │   │   ┌──────────▼─────────────┐  │
    │   ├───┼───┼───┼──►│      VOLATILE          │  │
    │   │   │   │   │   │                        │  │
    │   │   │   │   │   │  Lead: PHOENIX         │  │
    │   │   │   │   │   │  ATR(5)/ATR(20)>1.8    │  │
    │   │   │   │   │   │  OR vol>2x 60d median  │  │
    │   │   │   │   │   └──────────┬─────────────┘  │
    │   │   │   │   │              │                  │
    │   │   │   │   │   ┌──────────▼─────────────┐  │
    │   │   │   │   │   │      CRISIS            │  │
    │   │   │   │   └───┤                        │  │
    │   │   │   │       │  Lead: None            │  │
    │   │   │   │       │  Drop>8%/24h OR        │  │
    │   │   │   └───────┤  vol>3x 60d OR         │  │
    │   │   │           │  liquidation cascade    │  │
    │   │   └───────────┤                        │  │
    │   └───────────────┤  (any state can enter)  │  │
    └───────────────────┘                        │  │
                    │   └────────────────────────┘  │
                    └──────────────────────────────┘
```

**Transition Rules:**

| From | To | Trigger | Confirmation | Hysteresis |
|------|----|---------|-------------|------------|
| TRENDING → RANGING | ADX drops < 20 AND Hurst < 0.45 | 3 consecutive 1h candles | Must be in TRENDING for 6+ candles |
| TRENDING → VOLATILE | ATR ratio > 1.8 | 2 consecutive 1h candles | None — safety override |
| TRENDING → CRISIS | Crisis trigger (any) | IMMEDIATE — no confirmation | None — emergency |
| RANGING → TRENDING | ADX rises > 25 AND directional alignment | 3 consecutive 1h candles | Must be in RANGING for 6+ candles |
| RANGING → VOLATILE | ATR ratio > 1.8 | 2 consecutive 1h candles | None — safety override |
| RANGING → CRISIS | Crisis trigger (any) | IMMEDIATE | None — emergency |
| VOLATILE → TRENDING | ADX > 25 AND ATR ratio < 1.5 | 5 consecutive 1h candles | Must be in VOLATILE for 4+ candles |
| VOLATILE → RANGING | ADX < 20 AND ATR ratio < 1.5 AND Hurst < 0.45 | 5 consecutive 1h candles | Must be in VOLATILE for 4+ candles |
| VOLATILE → CRISIS | Crisis trigger (any) | IMMEDIATE | None — emergency |
| CRISIS → VOLATILE | Crisis conditions ease BUT vol still elevated | 12 consecutive 1h candles | Manual override can accelerate (6 candles) |
| CRISIS → TRENDING | NOT ALLOWED directly — must pass through VOLATILE first | — | — |
| CRISIS → RANGING | NOT ALLOWED directly — must pass through VOLATILE first | — | — |

**Key Design Decisions:**

1. **Asymmetric entry/exit for CRISIS:**
   - Entry: IMMEDIATE (any 1 indicator, no confirmation) — safety bias
   - Exit: SLOW (12 candles = 12 hours minimum) — prevent premature re-entry
   - CRISIS can ONLY exit to VOLATILE (gradual re-entry)

2. **Hysteresis prevents flapping:**
   - Minimum candles_in_regime before allowing transition (except CRISIS entry)
   - Confirmation window: multiple candles must agree before transition executes
   - `pending_transition` field tracks in-progress transitions

3. **Confirmation window mechanics:**
   ```
   on each candle:
     if transition_condition_met:
       if pending_transition is None:
         pending_transition = target_regime
         confirmation_counter = 1
       elif pending_transition == target_regime:
         confirmation_counter += 1
         if confirmation_counter >= required_confirmations:
           execute_transition()
       else:
         # Different transition detected — reset
         pending_transition = target_regime
         confirmation_counter = 1
     else:
       pending_transition = None
       confirmation_counter = 0
   ```

4. **CRISIS detection specifics:**
   ```
   def is_crisis(snapshot: MarketSnapshot) -> bool:
       """Any ONE of these triggers CRISIS immediately."""
       f = snapshot.features
       
       # Trigger 1: Price crash
       price_drop_24h = (current_price - price_24h_ago) / price_24h_ago
       if price_drop_24h < -0.08:  # -8%
           return True
       
       # Trigger 2: Extreme volatility
       if f.realized_vol_20d > 3 * vol_60d_median:
           return True
       
       # Trigger 3: Liquidation cascade
       if f.liquidation_est > liquidation_99th_percentile:
           return True
       
       # Trigger 4: Depth collapse (exchange stress)
       if f.depth_ratio < 0.3:  # <30% normal depth
           return True
       
       return False
   ```

5. **Recovery from CRISIS (gradual re-entry):**
   ```
   Phase 1 (CRISIS): 
     - All positions closed
     - No new trades
     - Monitor only
     - Duration: minimum 12h (12 candles on 1h)
   
   Phase 2 (VOLATILE, post-crisis):
     - PHOENIX only (carry/basis)
     - Position sizes at 25% of normal
     - ATLAS multiplier capped at 0.5
     - Duration: minimum 4h (4 candles)
     - If crisis re-triggers → back to Phase 1
   
   Phase 3 (Normal operations resume):
     - Full engine routing based on regime
     - Position sizes gradually increase:
       Candle 1-4 in new regime: 50% size
       Candle 5-12: 75% size
       Candle 13+: 100% size
   ```

**State Machine Implementation:**

```python
@dataclass(frozen=True)
class RegimeTransition:
    from_regime: str
    to_regime: str
    trigger: str           # human-readable trigger description
    confirmation: int      # number of candles required
    min_candles_in_current: int  # minimum candles before transition allowed
    
TRANSITIONS = [
    RegimeTransition("TRENDING", "RANGING", "ADX<20 AND Hurst<0.45", 3, 6),
    RegimeTransition("TRENDING", "VOLATILE", "ATR_ratio>1.8", 2, 0),
    RegimeTransition("TRENDING", "CRISIS", "crisis_trigger", 0, 0),
    RegimeTransition("RANGING", "TRENDING", "ADX>25 AND directional", 3, 6),
    RegimeTransition("RANGING", "VOLATILE", "ATR_ratio>1.8", 2, 0),
    RegimeTransition("RANGING", "CRISIS", "crisis_trigger", 0, 0),
    RegimeTransition("VOLATILE", "TRENDING", "ADX>25 AND ATR_ratio<1.5", 5, 4),
    RegimeTransition("VOLATILE", "RANGING", "ADX<20 AND ATR_ratio<1.5 AND Hurst<0.45", 5, 4),
    RegimeTransition("VOLATILE", "CRISIS", "crisis_trigger", 0, 0),
    RegimeTransition("CRISIS", "VOLATILE", "crisis_eased AND vol_elevated", 12, 0),
    # CRISIS -> TRENDING: NOT ALLOWED (must go through VOLATILE)
    # CRISIS -> RANGING: NOT ALLOWED (must go through VOLATILE)
]
```

**Failure Modes:**
- **Rapid oscillation between TRENDING/RANGING:** Prevented by 6-candle minimum + 3-candle confirmation = minimum 9 candles (9h) between flips
- **CRISIS entry on flash wick:** Acceptable — false CRISIS costs 12h of no trading, which is far cheaper than being exposed during a real crash
- **Stuck in CRISIS:** Manual override available via Telegram `/force_regime VOLATILE` — requires 2-factor confirmation
- **Regime detection lag:** 3-candle confirmation = 3h maximum delay. Acceptable for 1h timeframe trading. CRISIS has zero delay.

**Codex TODO:**
- [ ] Implement `src/regime/state_machine.py` with RegimeStateMachine class
- [ ] Implement all transition rules from the TRANSITIONS table
- [ ] Implement confirmation window logic with pending_transition tracking
- [ ] Implement is_crisis() function with all 4 triggers
- [ ] Implement gradual recovery (Phase 1 → Phase 2 → Phase 3)
- [ ] Write `tests/unit/test_regime.py` covering: all valid transitions, blocked transitions (CRISIS→TRENDING), hysteresis, confirmation windows, rapid oscillation prevention
- [ ] Write `tests/stress/test_regime_transition.py` with Monte Carlo regime flip scenarios

**Status:** FUTURE_VISION.md v8.0 - Chief Architect Design Package (Batch 1: 32A-32D)  
**Son Guncelleme:** 2026-02-10  
**Toplam Bolum:** 33 (Section 0-32, Section 32 in progress)  
**Document End**

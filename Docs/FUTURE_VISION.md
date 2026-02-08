# Argus Future Vision & Reference Integration

**Created:** 2026-02-07  
**Status:** COMPLETE - Full Strategic Blueprint (2026-02-08)  
**Timeline:** Year 2+ (2026-2030)  
**Sections:** 18 (Year-1 Summary + Year-2 Vision + Reference Repos + Growth Strategy + 24/7 Ops + Gate System + Risk + Strategies)

---

## 1. Year-1 Roadmap Summary ✅

| Phase | Dönem | Focus | Tasks |
|-------|-------|-------|-------|
| P20 | Month 1-2 | Engine Enhancement | 7 tasks (34h) |
| P21 | Month 2-3 | Infrastructure | 4 tasks (17h) |
| P22 | Month 3-6 | Advanced Features | 4 tasks (32h) |
| P23 | Month 6-9 | Production Ready | 4 tasks (16h) |
| P24 | Month 9-12 | Scale & Expansion | 4 tasks (32h) |

**Total Year-1:** 23 tasks, ~131 saat

## 1.1 Execution Sync (As of 2026-02-08 09:10 UTC)

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

## 2. Year 2+ Vision (After 12 Months)

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

## 3. Reference Repositories & Integration Plan

### 3.1 When to Use Reference Repos

| Repo | Use Case | Integration Phase |
|------|----------|-------------------|
| **freqtrade** | Strategy backtesting, indicator lib | P20-ENH1 (Orion indicators) |
| **jesse** | Event-driven architecture patterns | P21-001 (Walk-forward) |
| **hummingbot** | Exchange connectors, market making | P24-001 (Multi-exchange) |
| **zipline-reloaded** | Pipeline API, factor model | P24-003 (ML signals) |
| **vectorbt** | Vectorized backtesting | P21-002 (Determinism) |

### 3.2 Specific Integration Points

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

### 3.3 Reference Repo Study Schedule

| Week | Task | Repos to Study |
|------|------|----------------|
| P20 Start | Indicator validation | freqtrade |
| P21 Start | Backtest architecture | jesse, vectorbt |
| P22 Start | Portfolio patterns | zipline-reloaded |
| P24 Start | Exchange connectors | hummingbot |

---

## 4. Technology Roadmap

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

## 5. Scaling Milestones

| AUM | Infrastructure | Team Size |
|-----|----------------|-----------|
| $10K | Single Mac, paper trading | 1 (you) |
| $100K | VPS + testnet validation | 1-2 |
| $500K | Dedicated server, monitoring | 2-3 |
| $1M | Multi-region, redundancy | 3-5 |
| $10M | Full ops team, compliance | 5-10 |

---

## 6. Risk Evolution

| Phase | Max Position | Leverage | Daily Loss Limit |
|-------|--------------|----------|------------------|
| Paper (now) | 100% | 1x | None |
| Pilot ($1K) | 20% | 1x | 3% |
| Small ($10K) | 15% | 1x | 2% |
| Medium ($100K) | 10% | 1-2x | 1.5% |
| Large ($1M+) | 5% | 1-3x | 1% |

---

## 7. Next Actions (Post Year-1)

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

## 8. 24/7 Otonom Calisma Mimarisi

### 8.1 Temel Felsefe

Kripto piyasasi 7/24 acik. Gece 03:00'te gelen likidation cascade'i kacirmak, en kolay parayi kacirmak demek. Sistem **insanin uyudugu saatlerde bile** tam otomatik calismali.

### 8.2 Hibrit Altyapi: Beast + Soldier

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

### 8.3 Process Yonetimi

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

### 8.4 Gece Autopilot Dongusu

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

### 8.5 Monitoring & Alert Stack

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

### 8.6 Uptime Hedefleri

| Faz | Hedef Uptime | RTO |
|-----|-------------|-----|
| Paper | >= 99.0% | 1 dk (auto-restart) |
| Micro-live | >= 99.5% | 1 dk |
| Live | >= 99.7% | 30 sn |
| Scale | >= 99.9% | 15 sn (multi-region) |

---

## 9. 3 Haneden 6-7 Haneye: Sermaye Buyume Yol Haritasi

### 9.1 Matematiksel Gerceklik

$100'dan $100,000'e = **1000x** buyume. Tek lineer strateji ile kisa surede imkansiz (yikim riski olmadan).

**Kazanma Formulu:**
```
Buyume = (Edge x Frekans) - (Risk + Maliyet)
```

- **Edge** = Strateji kalitesi (pozitif beklenti)
- **Frekans** = Islem sayisi (bilesik getiri hizi)
- **Risk** = Drawdown kontrolu (hayatta kalma)
- **Maliyet** = Fee + slippage + latency

### 9.2 Buyume Fazlari

| Faz | Sermaye | Odak | Stratejiler | Risk/Trade | Tahmini Sure |
|-----|---------|------|-------------|------------|-------------|
| **Micro** | $100 - $1,000 | Agresif buyume, yuksek frekans | Hydra Scalp + Titan DCA | 2% | 6 ay |
| **Base** | $1,000 - $10,000 | Stabilite, trend ekleme | + Orion Trend | 1.5% | 12 ay |
| **Acceleration** | $10,000 - $50,000 | Diversifikasyon | + Phoenix Revert + Argo Arb | 1% | 18 ay |
| **6-Figure** | $50,000 - $100,000+ | Sermaye koruma | Portfolio balancing + DeFi yield | 0.5-1% | 24 ay |

### 9.3 Era Bazli Detay (4 Yillik Bakis)

| Era | Donem | Sermaye | Mod | Kaynak |
|-----|-------|---------|-----|--------|
| Era 0: Foundation | 2026 H1 | $30 - $500 | Paper + backtest | Kisisel birikim |
| Era 1: Proof | 2026 H2 | $500 - $2,000 | Paper 24/7 | Birikim + kucuk getiri |
| Era 2: Pilot | 2027 | $2,000 - $10,000 | Kucuk canli | Getiri + birikim |
| Era 3: Scale | 2028 | $10,000 - $50,000 | Multi-strateji | Bilesik getiri |
| Era 4: Professional | 2029 | $50,000 - $250,000 | Kurumsal ops | Bilesik + (dis sermaye?) |
| Era 5: Maturity | 2030+ | $250,000+ | Otonom makine | Bilesik getiri |

### 9.4 Sermaye Kurallari (Degismez)

1. **Kaybedebileceginizi risk edin.** Ilk $10K birikim + is gelirinizden, sistem getirisinden degil.
2. **Bilesikleyin, cekmeyin.** $50K'ye kadar tum getirileri yeniden yatirin.
3. **Kovalamak yok.** Sistem %10 dususteyse, "kurtarmak" icin ekstra para eklemeyin.
4. **Yavas olceklendirin.** Pozisyon artisi yalniz 3+ ay pozitif performanstan sonra.
5. **Ayristirin.** Trading sermayesi != Acil durum fonu != Yasam giderleri.

### 9.5 Bilesik Getiri Projeksiyonu (Baslangic: $100)

| Aylik Getiri | 12 Ay Sonrasi | 24 Ay Sonrasi | 36 Ay Sonrasi | 48 Ay Sonrasi |
|-------------|---------------|---------------|---------------|---------------|
| %3 | $143 | $203 | $289 | $411 |
| %5 | $180 | $323 | $580 | $1,040 |
| %8 | $252 | $634 | $1,594 | $4,010 |
| %10 | $314 | $985 | $3,091 | $9,700 |
| %15 | $535 | $2,862 | $15,308 | $81,871 |

> **Not:** Saf bilesik getiri hesabidir. Gercekte drawdown, fee, slippage ve disi birikim eklenince tablo degisir. Ancak %8-10 tutarli aylik getiri ile $100K'ya 3-4 yilda ulasmak matematiksel olarak mumkun.

### 9.6 "Senior Quant" Direktifleri

1. **Fee ile savasmayin.** Kucuk hesapta taker fee oldurucu. **Her zaman Limit Order (Post-Only)** kullanin (acil cikislar haric).
2. **Execution = Alpha.** Slippage de bir fee'dir. TWAP ve Chase-Limit mantigi implement edin.
3. **Veri = Edge.** Herkesin fiyat verisi var. **Orderbook Imbalance** ve **Liquidation Cascade** verisini alin.
4. **Korelasyon = Gizli Risk.** BTC ve ETH %90 korelasyondaysa, her ikisinin pozisyonunu yariya dusurun.

---

## 10. Strateji Portfolyosu ("Futbol Takimi")

### 10.1 Neden Tek Strateji Yetmez

Tek bir yildiz oyuncuya guvenmeyin. Bir takim kurun. Her piyasa kosulunda en az bir strateji kazanc saglayacak sekilde diversifiye edin.

### 10.2 Strateji Envanteri

| Strateji | Rejim Uygunlugu | Hedef | Timeframe | Mevcut Durum |
|----------|-----------------|-------|-----------|-------------|
| **Orion Trend** | Bull/Bear Trend | Buyuk hareketleri yakala (haftalik) | 1h-4h | Mevcut (Refine) |
| **Phoenix Revert** | High Vol Choppy | Wichleri fade et | 15m-1h | Mevcut (Refine) |
| **Hydra Scalp** | Low Vol Calm | 5-15m kucuk scalplar | 5m-15m | YENI |
| **Argo Arbitrage** | Any | Risksiz spread / funding farming | Tick-level | YENI |
| **Titan HODL** | Bull Trend | Akilli DCA (sadece dip alim) | 1d | YENI |
| **TopHunter Short** | Bear/Chop | Yapisal kirilim sonrasi short | 1h | Paper-Only |

### 10.3 Rejim-Strateji Matrisi

```
Rejim = BULL_TREND  ->  Orion (Long) + Titan DCA       -> Phoenix OFF, Hydra LOW
Rejim = BEAR_TREND  ->  Orion (Short) + TopHunter       -> Titan OFF, Hydra LOW
Rejim = HIGH_VOL    ->  Phoenix + Grid                   -> Orion OFF (trend'de oldurur)
Rejim = LOW_VOL     ->  Hydra Scalp + Argo Funding      -> Orion BEKLE, Phoenix BEKLE
```

### 10.4 Strateji Lifecycle

```
FIKIR -> HIPOTEZ -> BACKTEST -> WALK-FORWARD -> PAPER -> LIVE -> MONITOR -> EMEKLILIK
```

**Gate Metrikleri:**
- Backtest Gate: Profit Factor > 1.2, Sharpe > 0.5
- Walk-Forward Gate: %60+ pencerede pozitif beklenti
- Paper Gate: Paper sonuclari backtest'in %20'si icinde
- Emeklilik Tetikleyicileri: 30 gun DD > threshold VEYA 60 gun PF < 1.0

### 10.5 Portfolyo Kurallari

| Kural | Limit |
|-------|-------|
| Maks strateji sayisi | 10 |
| Min strateji sayisi | 2 |
| Maks tek strateji alokasyonu | %30 |
| Maks stratejiler arasi korelasyon | 0.5 |
| Maks alokasyon icin gereken track record | 6 ay |

---

## 11. Market Rejim Motoru ("Hava Istasyonu")

### 11.1 Neden Gerekli

Tek bir strateji tum hava kosullarinda kazanamaz. "Hava Istasyonu" (Rejim Dedektoru) stratejileri otomatik degistirir.

### 11.2 Rejim Siniflandirmasi

Her 4 saatte bir piyasa durumunu 4 kovaya siniflandir:

| Rejim | HV Rank | ADX | Funding | Aktif Strateji |
|-------|---------|-----|---------|----------------|
| **BULL_TREND** | Any | > 25 | > 0 | Orion (Long), Titan |
| **BEAR_TREND** | Any | > 25 | < 0 | Orion (Short), TopHunter |
| **HIGH_VOL_CHOP** | > 80 percentile | < 25 | Any | Phoenix, Grid |
| **LOW_VOL_CALM** | < 40 percentile | < 20 | Any | Hydra, Argo |

### 11.3 Girdiler

| Girdi | Kaynak | Kullanim |
|-------|--------|----------|
| VIX Proxy | Crypto HV (24h rolling) | Volatilite seviyesi |
| ADX(14) | Fiyat verisi | Trend gucu |
| Avg Funding Rate (3d) | Binance/Bybit API | Piyasa sentiment |
| Long/Short Ratio | Exchange API | Kalabalik pozisyon |
| On-Chain Inflow | Glassnode / CryptoQuant | Balina hareketi |
| Market Breadth | CoinGecko (% coins > MA200) | Genel piyasa sagligi |

### 11.4 Contract Tasarimi

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

## 12. 7 Motor Kripto Adaptasyonu

### 12.1 Motor Envanteri ve Kapsam

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

### 12.2 ATLAS-C: On-Chain Fundamental Analiz

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

### 12.3 AETHER-C: Kripto Makro Ortam

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

### 12.4 HERMES-C: Kripto Haber Sentiment

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

### 12.5 CHIRON: Ogrenme Motoru (Phase 2)

**On Kosul:** 50+ tamamlanmis trade ile telemetri (decisions.csv, trades.csv)
**Mevcut Durum:** Telemetri mevcut, ogrenme dongusu henuz yok

**Contract Tasarimi:** `argus_py/learning/chiron.py` (PLANLI)

- Her rejim icin en iyi agirlik setini bulma
- Objective: maximize Sharpe, minimize DD
- Trade sonuclarina gore motor agirliklarini optimize etme

### 12.6 Kripto Council Agirliklari (Onerilen)

```
Technical (Orion-C):  45%   # Fiyat aksiyonu kripto'da baskin
On-Chain (Atlas-C):   25%   # Fundamentaller daha az onemli
Macro (Aether-C):     20%   # Makro donguleri onemli
Sentiment (Hermes-C): 10%   # Gurultu/sinyal orani dusuk
```

### 12.7 Implementasyon Takvimi

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

## 13. Paper -> Micro-Live -> Live Gate Sistemi

### 13.1 Gate Felsefesi

Hicbir asamaya kanitlanmadan gecilemez. Her gate'in sayisal gecis kriteri var.

### 13.2 Gate A: Paper -> Micro-Live

| Metrik | Gecis Esigi | Basarisizlik | Kaynak |
|--------|-------------|-------------|--------|
| Max Drawdown | <= %6.0 (30 gun rolling) | > %6.0 | heartbeat.json, weekly_audit |
| Uptime | >= %99.0 | < %99.0 | status.log |
| Slippage | median <= 6 bps, p95 <= 12 bps | Ust sinir asilirsa | trades.csv |
| Hata Orani | <= %0.20 bar basina | > %0.20 | rejects.csv |
| Trade Sayisi | >= 200 gecerli paper trade | < 200 | trades.csv |
| Drift | <= 10 bps median | > 10 bps | signal_audit |

**Promosyon Kurali:** Tum metrikler **2 ardisik haftalik review'da** gecmeli.

### 13.3 Gate B: Micro-Live -> Live

| Metrik | Gecis Esigi | Basarisizlik | Kaynak |
|--------|-------------|-------------|--------|
| Max Drawdown | <= %4.0 (45 gun rolling) | > %4.0 | broker equity |
| Uptime | >= %99.5 | < %99.5 | heartbeat |
| Slippage Delta | median <= +4 bps, p95 <= +10 bps | Ust sinir | model vs live fills |
| Hata Orani | <= %0.10 kritik hata/bar | > %0.10 | rejects/errors |
| Trade Sayisi | >= 100 micro-live fill | < 100 | micro-live trades.csv |
| Drift | paper vs micro-live <= %15 relative | > %15 | paired-run drift |

**Promosyon Kurali:** Tum metrikler pass + kill-switch hicbir zaman `HARD/HALT`'da 1 cycle'dan fazla kalmamis olmali.

### 13.4 Gate C: Live Scale-Up (Stage-1 -> Stage-2)

| Metrik | Gecis Esigi | Kaynak |
|--------|-------------|--------|
| 90 gun Max DD | <= %5.0 | live equity curve |
| Calisma Stabilitesi | >= %99.7 | heartbeat + supervisor |
| Slippage Stabilitesi | p95 <= 12 bps | fills vs model |
| Incident Rate | 0 cozulmemis kritik incident | incident log |
| Trade Throughput | >= 250 fill / 90 gun | trades.csv |
| Drift Stabilitesi | aylik trend artmayan | aylik drift paketi |

### 13.5 Stage Progression Timeline

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

### 13.6 Risk Profili Progresyonu

| Parametre | Paper | Micro-Live | Live S1 | Live S2 |
|-----------|-------|-----------|---------|---------|
| `dailyLossCap` | %3.0 | %2.0 | %1.5 | %1.0 |
| `maxRiskPerTrade` | %1.0 | %0.50 | %0.35 | %0.25 |
| `maxConcurrentPos` | 3 | 2 | 2 | 3 |
| `minCashReserve` | %10 | %20 | %25 | %20 |

---

## 14. Risk Yonetimi: "Iron Risk" Detay

### 14.1 Iron Risk Felsefesi

> "Hayatta kalma > Kar. %50 kaybedersen, sifira donmek icin %100 kazanman lazim."

Risk yonetimi sistemin **cekirdegine** kodlanir. Bypass edilemez.

### 14.2 5 Katmanli Risk Hiyerarsisi

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

### 14.3 Pozisyon Boyutlandirma Formulu

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

### 14.4 Korelasyon Kontrol

- BTC-ETH korelasyonu > 0.7 ise: her iki pozisyonu `(1 - corr/2)` ile carp
- Ornek: corr = 0.9 -> scale = 0.55 -> her pozisyon neredeyse yariya iner
- Amac: Birbirine bagli varliklarda cift risk almamak

### 14.5 Kill-Switch Protokolu

| Tetikleyici | Level | Aksiyon |
|-------------|-------|---------|
| Gunluk kayip > %3 | `SOFT` | Yeni giris durdur, mevcut pozisyonlar devam |
| Gunluk kayip > %5 | `HARD` | Tum yeni islemler durdur |
| Toplam DD > %10 | `HALT` | Tum pozisyonlari kapat, 24 saat sogurum |
| 5 ardisik kayip | `SOFT` | 30 dk yeni giris yok |
| Sistem hatasi | `HARD` | Alert + inceleme bekle |
| Manuel tetik | `HALT` | Tam durdurma, manuel restart gerekir |

### 14.6 Kill-Switch Sonrasi Recovery

1. `SOFT` recovery: Otomatik, sonraki bar'da normal devam
2. `HARD` recovery: 12 saat paper-only zorunlu
3. `HALT` recovery: Manuel restart + incident raporu zorunlu

### 14.7 Cooldown Kurallari

| Kural | Deger |
|-------|-------|
| Loss streak cooldown | 3 ardisik kayip -> 30 dk pause |
| Yuksek volatilite cooldown | Slippage p95 esik asarsa -> 15 dk pause |
| Post-kill-switch cooldown | HARD'dan recovery -> 12 saat paper-only |
| SOFT selective mode | Yalniz yuksek conviction giris, %25-40 normal boyut |

---

## 15. Alpha Factory & Arastirma Pipeline'i

### 15.1 Surec

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

### 15.2 Factor Lab

Her hafta 100+ sinyal adayini test eden otomatik pipeline:

- Girdiler: Teknik (RSI, MACD, BB, Stoch, ADX, OBV), On-chain (NVT, MVRV, Exchange Reserve), Sentiment (Fear & Greed, LLM Score), Microstructure (OBI, Volume Delta), Cross-asset (BTC Dominance, DXY, SPY corr)
- Degerlendirme: IC (Information Coefficient) hesapla, IC > 0.05 olanlari promote et
- Hit Rate: Faktor yonu ile gelecek getiri yonunun eslestigi oran

### 15.3 Walk-Forward Optimizer

```
Her Pazar:
1. Son 6 ayin verisinde parametreleri optimize et
2. Son 2 haftalik (gorunmeyen) veride test et
3. Verimli ise -> config.yaml'i guncelle
4. Verimli degilse -> mevcut config'i koru
```

### 15.4 Arastirma Ritmi

| Frekans | Aktivite |
|---------|----------|
| Gunluk | Telemetri inceleme, anomali taramasi |
| Haftalik | Performans review, factor screening |
| Aylik | Strateji retrospektifi, yeni hipotez |
| Ceyreklik | Mimari review, teknik borc degerlendirmesi |

### 15.5 GPU-Hizlandirilmis Feature Engineering

Beast'in RTX A3000M'i ile:
- 100+ teknik indikatoru 5 yillik 1m veri uzerinde saniyeler icinde hesapla (cuDF / RAPIDS)
- XGBoost/LightGBM modellerini GPU'da egit
- Lokal LLM (Ollama Mistral/Llama3) ile zero-cost sentiment analizi
- 16 paralel multiprocessing ile optimize_hydra.py tipi grid search

---

## 16. 4 Yillik Master Plan Ozeti (2026-2030)

### 16.1 Era 0: Foundation (2026 H1)
- **Sermaye:** $30 -> $500
- **Mod:** Paper + backtest
- **Basari:** 12M walk-forward pozitif beklenti, DD < %15, 30 gun kesintisiz calisma
- **Yapma:** Canli para yatirma, getiri optimize etme

### 16.2 Era 1: Proof (2026 H2)
- **Sermaye:** $500 -> $2,000
- **Mod:** Paper 24/7 (gercek zamanli veri ile)
- **Basari:** 6 ay kesintisiz paper, Sharpe > 0.5, DD < %12
- **Aktivite:** Haftalik performans review, aylik strateji retrospektifi

### 16.3 Era 2: Pilot (2027)
- **Sermaye:** $2,000 -> $10,000
- **Mod:** Kucuk canli + paper genisleme
- **Basari:** 12 ay canli (blow-up yok), pozitif getiri, DD < %10, ikinci varlik sinifi
- **Risk:** Trade basina maks %1, gunluk %5 hard stop

### 16.4 Era 3: Scale (2028)
- **Sermaye:** $10,000 -> $50,000
- **Mod:** Multi-strateji, multi-asset
- **Basari:** 3+ strateji pozitif, Portfolio Sharpe > 0.8, DD < %8
- **Yeni:** Strateji alokasyon motoru, rejim tespiti cross-asset, ML feedback loop v1

### 16.5 Era 4: Professional (2029)
- **Sermaye:** $50,000 -> $250,000
- **Mod:** Kurumsal seviye operasyon
- **Basari:** 3+ yillik denetlenebilir track record, DD < %6, Uptime > %99.5
- **Degerlendir:** Dis sermaye (arkadaslar/aile), yasal yapi, sigorta

### 16.6 Era 5: Maturity (2030+)
- **Sermaye:** $250,000+
- **Mod:** Otonom bilesik makine
- **Karakter:** Minimal mudahale, arastirma pipeline'indan yeni stratejiler, basarisiz stratejiler otomatik emekli, operator rolu gozlem

### 16.7 Her Gun Sorun: "Sistem bugun hayatta kaldi mi?"

```
Evet -> Bilesikle.
Hayir -> Nedenini ogren.
Tum oyun bu.
```

---

## 17. Basarisizlik Modlari ve Onleme Cercevesi

### 17.1 Argus Nasil Olur?

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

### 17.2 Onleme Cercevesi

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

### 17.3 Incident Drill (3 Ayda Bir)

**Prosedur:**
1. Anomali simule et (stale heartbeat / error spike)
2. Alert'in ateslendigini dogrula
3. Triage: `soak_status.sh` + `status_reader.py`
4. Containment: Kill-switch seviyesini dogrula
5. Recovery: Restart + heartbeat dogrulama
6. Postmortem: Incident template + kok neden + aksiyon

---

## 18. Hydra / Argo / Titan: Yeni Strateji Planlari

### 18.1 HYDRA SCALP: Dusuk Volatilite Scalper

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

### 18.2 ARGO ARBITRAGE: Funding Rate Farmer

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

### 18.3 TITAN DCA: Akilli Ortalama Maliyet

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

### 18.4 Yeni Strateji Implementasyon Takvimi

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
| P0 | Rejim Motoru (Section 11) | 10 saat | Veri API'leri |
| P0 | Paper 24/7 Stabilite (Section 8) | 8 saat | PM2 + monitoring |
| P1 | Orion Enhancement (7 motor, Section 12) | 6 saat | Mevcut kod |
| P1 | Gate A Metrik Altyapisi (Section 13) | 6 saat | Telemetri |
| P1 | Iron Risk Kernel (Section 14) | 8 saat | Kill-switch mevcut |
| P2 | Hydra Scalp Stratejisi (Section 18) | 15 saat | P0 rejim motoru |
| P2 | Aether-C Macro (Section 12) | 8 saat | API entegrasyonu |
| P2 | Titan DCA (Section 18) | 8 saat | P0 rejim motoru |
| P3 | Hermes-C Sentiment (Section 12) | 6 saat | RSS + LLM |
| P3 | Atlas-C On-Chain (Section 12) | 8 saat | Glassnode/CoinGecko |
| P3 | Argo Arbitrage (Section 18) | 20 saat | Multi-exchange |
| P4 | Chiron Learning (Section 12) | 10 saat | 50+ trade |
| P4 | Factor Lab Automasyonu (Section 15) | 12 saat | Feature store |

**Toplam Tahmini Efor:** ~125 saat (~3 ay part-time, hafta 10 saat)

---

**Status:** FUTURE_VISION.md v2.0 - Tum bolumler tamamlandi  
**Son Guncelleme:** 2026-02-08  
**Document End**

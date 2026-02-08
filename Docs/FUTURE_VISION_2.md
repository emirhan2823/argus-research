# Argus Future Vision & Reference Integration

**Created:** 2026-02-07  
**Status:** Strategic Planning + Execution Sync Applied (2026-02-08 09:10 UTC)  
**Timeline:** Year 2+

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

---

# PHASE 25: Advanced Trading (Year 2 Q1)

---

## P25-001: Options Trading Module

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 20 hours

### Objective
Hedging spot positions with BTC/ETH options (Deribit via API).
Focus on buying protective puts or selling covered calls.

### Contract

**File:** `argus_py/options/manager.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Optional
from datetime import date

@dataclass
class OptionContract:
    symbol: str
    expiry: date
    strike: float
    type: str  # CALL | PUT
    greek_delta: float
    implied_vol: float

class OptionsManager:
    """
    Manages option positions for hedging.
    """
    def __init__(self, connector):
        self.connector = connector
    
    async def hedge_spot_position(self, symbol: str, quantity: float):
        """
        Buy put options to hedge a long spot position.
        Target delta: -0.3 to -0.5
        """
        chain = await self.connector.get_option_chain(symbol)
        puts = [o for o in chain if o.type == 'PUT']
        
        # Select best hedge
        best_put = self._select_hedge_option(puts)
        if best_put:
            await self.connector.place_order(best_put.symbol, 'BUY', quantity)
    
    def _select_hedge_option(self, puts: List[OptionContract]) -> Optional[OptionContract]:
        # Logic: OTM put, 30-day expiry, delta ~ -0.3
        return puts[0] if puts else None
```

### Files to Create
1. `argus_py/options/__init__.py`
2. `argus_py/options/manager.py` (200 lines)
3. `argus_py/options/greeks.py` (Black-Scholes calc)
4. `tests/unit/test_options.py`

---

## P25-002: Arbitrage Engine

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 15 hours

### Objective
Capture price differences between exchanges (e.g., Binance vs Bybit).

### Contract

**File:** `argus_py/arbitrage/scanner.py` (NEW)

```python
import asyncio
from typing import Dict, Tuple

class ArbitrageScanner:
    def __init__(self, exchanges: Dict[str, ExchangeConnector]):
        self.exchanges = exchanges
    
    async def scan_spread(self, symbol: str) -> Tuple[str, str, float]:
        """
        Find best spread for a symbol.
        Returns: (buy_exchange, sell_exchange, spread_pct)
        """
        prices = {}
        for name, ex in self.exchanges.items():
            ticker = await ex.get_ticker(symbol)
            prices[name] = ticker
        
        # Calculate max spread
        # ... logic
        return ("binance", "bybit", 0.5)

    async def execute_arb(self, symbol: str, qty: float):
        buy_ex, sell_ex, spread = await self.scan_spread(symbol)
        if spread > 0.2:  # Min threshold
            await asyncio.gather(
                self.exchanges[buy_ex].place_market_order(symbol, 'BUY', qty),
                self.exchanges[sell_ex].place_market_order(symbol, 'SELL', qty)
            )
```

### Files to Create
1. `argus_py/arbitrage/__init__.py`
2. `argus_py/arbitrage/scanner.py` (150 lines)
3. `tests/unit/test_arbitrage.py`

---

## P25-003: Grid Trading Bot

**Assign to:** Codex  
**Priority:** P3  
**Estimated:** 10 hours

### Objective
Automated grid trading for sideways markets.

### Contract

**File:** `argus_py/strategies/grid.py` (NEW)

```python
from dataclasses import dataclass
from typing import List

@dataclass
class GridLevel:
    price: float
    order_id: Optional[str] = None
    filled: bool = False

class GridStrategy:
    def __init__(self, lower: float, upper: float, grids: int):
        self.levels = [
            GridLevel(lower + i * (upper - lower) / grids)
            for i in range(grids + 1)
        ]
    
    def on_tick(self, price: float):
        # Update grid logic
        # Buy low, sell high within range
        pass
```

### Files to Create
1. `argus_py/strategies/grid.py` (150 lines)
2. `tests/unit/test_grid.py`

---

# PHASE 26: AI/ML Evolution (Year 2 Q2)

---

## P26-001: Reinforcement Learning Pilot

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 40 hours

### Objective
Implement Q-Learning agent for trade execution optimization.
Uses OpenAI Gym interface.

### Contract

**File:** `argus_py/ml/rl_agent.py` (NEW)

```python
import gym
import numpy as np
from gym import spaces

class ArgusTradingEnv(gym.Env):
    """
    OpenAI Gym environment for trading.
    """
    def __init__(self, df):
        super(ArgusTradingEnv, self).__init__()
        self.df = df
        self.action_space = spaces.Discrete(3)  # HOLD, BUY, SELL
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(10, 6), dtype=np.float32
        )
    
    def step(self, action):
        # Execute action, calculate reward
        # Reward = PnL change
        pass

    def reset(self):
        # Reset state
        pass
```

### Training Script
**File:** `Scripts/train_rl.py`
```python
from stable_baselines3 import PPO
from argus_py.ml.rl_agent import ArgusTradingEnv

env = ArgusTradingEnv(data)
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=100000)
model.save("models/ppo_trader")
```

### Files to Create
1. `argus_py/ml/rl_agent.py` (200 lines)
2. `Scripts/train_rl.py`
3. `tests/unit/test_rl.py`

---

## P26-002: Sentiment NLP v2 (LLM)

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 20 hours

### Objective
Integrate local LLM (Llama 3 / Mistral) via Ollama for news sentiment analysis.
Replaces keyword-based Hermes-C engine.

### Contract

**File:** `argus_py/models/hermes/llm_sentiment.py` (NEW)

```python
import httpx
from dataclasses import dataclass

@dataclass
class SentimentResult:
    score: float  # -1.0 to 1.0
    summary: str
    entities: List[str]

class LLMSentimentEngine:
    def __init__(self, model_url="http://localhost:11434"):
        self.model_url = model_url
    
    async def analyze(self, text: str) -> SentimentResult:
        prompt = f"""
        Analyze the following financial news for crypto sentiment.
        Output CSV: score (-1 to 1), summary, entities.
        
        News: {text}
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.model_url}/api/generate",
                json={"model": "llama3", "prompt": prompt, "stream": False}
            )
            # Parse response
            # ...
            return SentimentResult(0.8, "Bullish adoption", ["BTC", "BlackRock"])
```

### Files to Create
1. `argus_py/models/hermes/llm_sentiment.py` (100 lines)
2. `tests/unit/test_llm_sentiment.py`

---

---

# PHASE 27: Ecosystem Expansion (Year 2 Q3)

---

## P27-001: DeFi Integration (Uniswap/Aave)

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 30 hours

### Objective
Trade on DEXs (Uniswap V3) and lend on Aave for yield.
Requires Web3.py and local node or Infura.

### Contract

**File:** `argus_py/defi/connector.py` (NEW)

```python
from web3 import Web3
from typing import Dict

class DeFiConnector:
    def __init__(self, node_url: str, private_key: str):
        self.w3 = Web3(Web3.HTTPProvider(node_url))
        self.account = self.w3.eth.account.from_key(private_key)
    
    async def swap_uniswap_v3(self, token_in: str, token_out: str, amount: int):
        # Build transaction for SwapRouter
        # Sign and send
        pass
    
    async def supply_aave_v3(self, asset: str, amount: int):
        # Aave Pool supply
        pass
```

### Files to Create
1. `argus_py/defi/connector.py` (150 lines)
2. `argus_py/defi/uniswap.py` (router logic)
3. `tests/unit/test_defi.py`

---

## P27-002: On-Chain Analytics

**Assign to:** Codex  
**Priority:** P2  
**Estimated:** 15 hours

### Objective
Track whale movements and exchange inflows as signals.

### Contract

**File:** `argus_py/onchain/whale_alert.py` (NEW)

```python
class WhaleMonitor:
    def __init__(self, connector):
        self.connector = connector
    
    async def check_large_transfers(self, min_value_usd=10_000_000):
        # Scan latest blocks for >$10M transfers
        # Filter for Exchange wallets
        pass
```

### Files to Create
1. `argus_py/onchain/whale_alert.py` (100 lines)
2. `tests/unit/test_onchain.py`

---

# PHASE 28: Enterprise Features (Year 2 Q4)

---

## P28-001: Multi-Tenant SaaS Architecture

**Assign to:** Codex  
**Priority:** P1  
**Estimated:** 60 hours

### Objective
Isolate user state to allow multiple users on one instance.
Database schema migration to include `user_id` and `organization_id`.

### Contract

**File:** `argus_py/core/context.py` (MODIFY)

```python
from contextvars import ContextVar
from dataclasses import dataclass

@dataclass
class UserContext:
    user_id: str
    org_id: str
    permissions: List[str]

current_user = ContextVar("current_user")

class TenancyMiddleware:
    async def __call__(self, scope, receive, send):
        # Extract JWT, set current_user
        # Enforce data isolation in DB queries
        pass
```

### Files to Modify
1. `argus_py/core/context.py`
2. `argus_py/models/*.py` (add user_id)
3. `Scripts/migrate_saas.py`

---

## P28-002: Regulatory Reporting (MiFID II)

**Assign to:** Sonnet  
**Priority:** P2  
**Estimated:** 20 hours

### Objective
Standardized reporting for EU/US compliance.
Transaction reporting, best execution analysis.

### Contract

**File:** `argus_py/reporting/mifid.py` (NEW)

```python
class MifidReporter:
    def generate_transaction_report(self, date):
        # Fields: LEI, ISIN, Price, Qty, Venue, Timestamp
        # Format: ISO 20022 XML
        pass
```

### Files to Create
1. `argus_py/reporting/mifid.py` (150 lines)
2. `tests/unit/test_mifid.py`

---

**Document End**

# ARGUS 1-Year Technical Roadmap

**2026 Sprint-by-Sprint Execution Plan**

**Start Date:** 2026-02-07  
**End Date:** 2027-02-07  
**Cadence:** 2-week sprints (26 sprints total)

---

# Inspired By: Open Source Quant Excellence

Bu roadmap'te aşağıdaki açık kaynak projelerden ilham alınmıştır:

| Repo | Alınacak Özellik |
|------|------------------|
| **microsoft/qlib** | AI/ML pipeline, factor analysis, alpha engine |
| **QuantConnect/LEAN** | Multi-asset engine, event-driven architecture |
| **freqtrade/freqtrade** | Strategy optimization, hyperopt, Telegram bot |
| **nautechsystems/nautilus_trader** | High-performance event loop, order management |
| **Ashutosh0x/QuantHedgeFund** | MLflow experiment tracking, IB integration |
| **goldmansachs/gs-quant** | Risk analytics, portfolio construction |
| **AI4Finance/FinRL** | Reinforcement learning, DRL agents |
| **erdewit/Backtesting.py** | Interactive visualization, optimizer |
| **stefan-jansen/machine-learning-for-trading** | ML features, alpha factors |
| **OpenBB-finance/OpenBBTerminal** | Research terminal, data aggregation |

---

# Q1 2026: Foundation Sprint (Sprint 1-6)

## Sprint 1-2 (Feb 7 - Mar 6): Data Infrastructure

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Cache sistemi production-grade | 12M veri hatasız yüklenir | `feat: robust-cache-layer` |
| Data quality checks | Her dosyada checksum, gap detection | `feat: data-validation` |
| Multi-source ingestion | Binance + yfinance (US equity) | `feat: yfinance-adapter` |

### Yeni Feature'lar (Qlib'den ilham)
```
data/
├── quality/
│   ├── gap_detector.py      # Eksik veri tespiti
│   ├── outlier_filter.py    # Spike removal
│   └── checksum.py          # Data integrity
├── providers/
│   ├── binance.py           # Mevcut
│   ├── yfinance.py          # YENİ: US equity
│   └── ccxt_universal.py    # YENİ: Çoklu exchange
```

### Kabul Kriterleri
- [ ] 12M BTC veri gap-free
- [ ] SPY, QQQ, AAPL günlük veri indirilir
- [ ] Data quality report otomatik üretilir

---

## Sprint 3-4 (Mar 7 - Apr 3): Event-Driven Engine

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Event bus implementasyonu | Pub/sub pattern çalışır | `feat: event-bus` |
| Handler ayrımı | Data → Signal → Risk → Execution | `refactor: event-handlers` |
| Replay mode | Historical events sıralı oynatılır | `feat: event-replay` |

### Yeni Feature'lar (LEAN + Nautilus'tan ilham)
```
core/
├── events/
│   ├── bus.py               # Central event dispatcher
│   ├── types.py             # MarketEvent, SignalEvent, OrderEvent
│   └── replay.py            # Historical replay for testing
├── handlers/
│   ├── market_handler.py    # Bar updates
│   ├── signal_handler.py    # Strategy signals
│   ├── risk_handler.py      # Risk gate decisions
│   └── execution_handler.py # Order management
```

### Kabul Kriterleri
- [ ] Event bus unit testleri geçer
- [ ] Backtest event replay ile çalışır
- [ ] Handlers loosely coupled

---

## Sprint 5-6 (Apr 4 - May 1): Feature Store v1

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Feature hesaplama pipeline | 50+ teknik indicator | `feat: feature-pipeline` |
| Parquet storage | Hızlı read/write | `feat: parquet-store` |
| Warmup management | Indicator warmup explicit | `feat: warmup-manager` |

### Yeni Feature'lar (Qlib + MLflow'dan ilham)
```
features/
├── indicators/
│   ├── momentum.py          # RSI, MACD, ROC, Williams
│   ├── trend.py             # ADX, Aroon, Parabolic SAR
│   ├── volatility.py        # ATR, Bollinger, Keltner
│   ├── volume.py            # OBV, VWAP, MFI
│   └── custom.py            # Argus-specific features
├── store/
│   ├── feature_store.py     # Parquet-based storage
│   ├── registry.py          # Feature metadata
│   └── versioning.py        # Feature version tracking
├── compute/
│   └── pipeline.py          # Batch feature computation
```

### Feature List (50+)
| Kategori | Features |
|----------|----------|
| Momentum | RSI(14), RSI(7), MACD, Signal, Histogram, ROC(10), ROC(20), Williams%R, Stochastic K/D |
| Trend | ADX, +DI, -DI, Aroon Up/Down, Parabolic SAR, SuperTrend, Ichimoku (5 line) |
| Volatility | ATR(14), ATR(7), Bollinger Bands (3), Keltner (3), Donchian (3), True Range |
| Volume | OBV, VWAP, Volume SMA ratio, MFI, Accumulation/Distribution |
| Price | SMA(20,50,200), EMA(12,26), Pivot Points, Fibonacci levels |
| Custom | MRIE score, Regime label, Entry quality, Conviction score |

### Kabul Kriterleri
- [ ] 50 feature hesaplanır
- [ ] Parquet dosyaları üretilir
- [ ] Feature registry metadata tutar

---

# Q2 2026: Strategy Engine (Sprint 7-13)

## Sprint 7-8 (May 2 - May 29): Strategy Framework

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Strategy interface | Abstract base class | `feat: strategy-interface` |
| Strategy registry | Discovery + lifecycle | `feat: strategy-registry` |
| Config-driven params | YAML config per strategy | `feat: strategy-config` |

### Yeni Feature'lar (Freqtrade + QSTrader'dan ilham)
```
strategy/
├── base.py                  # AbstractStrategy
├── registry.py              # Strategy discovery
├── config.py                # YAML loader
├── lifecycle.py             # DRAFT→ACTIVE→RETIRED
├── builtin/
│   ├── aegean/              # Momentum strategy
│   │   ├── strategy.py
│   │   └── config.yaml
│   ├── orion/               # Confirmation strategy
│   │   ├── strategy.py
│   │   └── config.yaml
│   └── mrie/                # Regime strategy
│       ├── strategy.py
│       └── config.yaml
```

### Strategy Interface (Clean Design)
```python
class AbstractStrategy(ABC):
    name: str
    version: str
    required_features: List[str]
    
    @abstractmethod
    def generate_signal(self, features: Dict) -> Signal:
        pass
    
    @abstractmethod
    def calculate_conviction(self, features: Dict) -> float:
        pass
    
    def get_config(self) -> StrategyConfig:
        pass
```

---

## Sprint 9-10 (May 30 - Jun 26): Alpha Engine

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Alpha factor library | 20+ alpha factors | `feat: alpha-factors` |
| Factor combination | Weighted ensemble | `feat: alpha-ensemble` |
| Factor analysis | IC, IR, turnover | `feat: factor-analysis` |

### Alpha Factors (101 Alphas'tan ilham)
```python
# Örnek alpha factors
class AlphaFactors:
    @staticmethod
    def momentum_12_1(prices):
        """12-month momentum, skip recent month"""
        return prices.pct_change(252).shift(21)
    
    @staticmethod
    def mean_reversion_5d(prices):
        """5-day mean reversion"""
        return -prices.pct_change(5)
    
    @staticmethod
    def volume_surprise(volume):
        """Volume vs 20-day average"""
        return volume / volume.rolling(20).mean() - 1
    
    @staticmethod
    def price_range_position(high, low, close):
        """Where is close in day's range"""
        return (close - low) / (high - low)
```

### Kabul Kriterleri
- [ ] 20 alpha factor implementasyonu
- [ ] Factor correlation matrix
- [ ] IC (Information Coefficient) hesaplanır

---

## Sprint 11-12 (Jun 27 - Jul 24): Council v2

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Multi-strategy voting | Weighted consensus | `feat: council-v2` |
| Regime-aware weighting | Weights by market state | `feat: regime-weights` |
| Conflict resolution | Clear rules for disagreement | `feat: conflict-resolver` |

### Council Architecture
```
council/
├── aggregator.py            # Vote collection
├── weighting/
│   ├── equal.py             # Simple average
│   ├── performance.py       # Weight by recent performance
│   ├── regime.py            # Weight by regime fit
│   └── adaptive.py          # ML-learned weights
├── resolver.py              # Conflict handling
├── verdict.py               # Final decision types
```

---

## Sprint 13 (Jul 25 - Aug 7): Walk-Forward v2

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Anchored walk-forward | Expanding window option | `feat: anchored-wf` |
| Combinatorial purging | Prevent leakage | `feat: purged-cv` |
| Automatic reports | HTML + PDF output | `feat: wf-reports` |

### Walk-Forward Modes
| Mode | Description |
|------|-------------|
| Rolling | Fixed window slides forward |
| Anchored | Start fixed, end expands |
| Purged | Gap between train/test |
| Combinatorial | Multiple test paths |

---

# Q3 2026: Risk & Execution (Sprint 14-19)

## Sprint 14-15 (Aug 8 - Sep 4): Portfolio Risk Engine

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Portfolio VaR | Daily VaR calculation | `feat: portfolio-var` |
| Correlation monitor | Real-time correlation | `feat: correlation-monitor` |
| Sector exposure | Asset class limits | `feat: sector-limits` |

### Risk Metrics (gs-quant'tan ilham)
```
risk/
├── portfolio/
│   ├── var.py               # Value at Risk
│   ├── cvar.py              # Conditional VaR
│   ├── sharpe.py            # Real-time Sharpe
│   ├── sortino.py           # Downside risk
│   └── max_dd.py            # Max drawdown tracker
├── correlation/
│   ├── rolling.py           # Rolling correlation
│   ├── regime.py            # Correlation by regime
│   └── alerts.py            # Correlation spike alerts
├── exposure/
│   ├── sector.py            # Sector allocation
│   ├── asset_class.py       # Asset class limits
│   └── concentration.py     # Position concentration
```

---

## Sprint 16-17 (Sep 5 - Oct 2): Execution Engine

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Order management | Full lifecycle tracking | `feat: order-manager` |
| Slippage model | Realistic cost modeling | `feat: slippage-model` |
| Bracket orders | TP/SL as single unit | `feat: bracket-orders` |

### Order States
```
PENDING → SUBMITTED → PARTIAL → FILLED
                   ↘ REJECTED
                   ↘ CANCELLED
```

### Execution Features
```
execution/
├── order_manager.py         # Order lifecycle
├── position_tracker.py      # Position state
├── slippage/
│   ├── fixed.py             # Fixed pct model
│   ├── volume.py            # Volume-based
│   └── spread.py            # Bid-ask spread
├── broker/
│   ├── base.py              # Abstract broker
│   ├── paper.py             # Paper trading
│   └── ccxt.py              # Live crypto (ccxt)
```

---

## Sprint 18-19 (Oct 3 - Oct 30): Kill-Switch & Observability

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Multi-level kill-switch | SOFT/HARD/HALT | `feat: kill-switch-v2` |
| Health dashboard | Real-time metrics | `feat: health-dashboard` |
| Alert system | Telegram/Discord/Email | `feat: alerts` |

### Alert Channels (Freqtrade'den ilham)
```
ops/
├── kill_switch/
│   ├── controller.py        # Main controller
│   ├── triggers.py          # Trigger conditions
│   └── actions.py           # Response actions
├── health/
│   ├── checks.py            # Health check functions
│   ├── dashboard.py         # Metrics dashboard
│   └── exporter.py          # Prometheus metrics
├── alerts/
│   ├── telegram.py          # Telegram bot
│   ├── discord.py           # Discord webhook
│   ├── email.py             # Email alerts
│   └── router.py            # Alert routing
```

---

# Q4 2026: ML & Automation (Sprint 20-26)

## Sprint 20-21 (Oct 31 - Nov 27): Experiment Tracking

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| MLflow integration | Experiment logging | `feat: mlflow-tracking` |
| Hyperparameter store | Config versioning | `feat: hyperparam-store` |
| Run comparison | Side-by-side analysis | `feat: run-comparison` |

### MLflow Setup (QuantHedgeFund'dan ilham)
```
ml/
├── tracking/
│   ├── experiment.py        # Experiment wrapper
│   ├── run.py               # Run logger
│   └── comparison.py        # Run comparison
├── artifacts/
│   ├── models.py            # Model storage
│   ├── features.py          # Feature artifacts
│   └── reports.py           # Report artifacts
```

---

## Sprint 22-23 (Nov 28 - Dec 25): ML Models v1

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Classification models | Direction prediction | `feat: direction-models` |
| Regression models | Return prediction | `feat: return-models` |
| Ensemble methods | Model combination | `feat: ensemble-models` |

### Model Zoo (Qlib'den ilham)
```
ml/
├── models/
│   ├── linear/
│   │   ├── ridge.py
│   │   └── lasso.py
│   ├── tree/
│   │   ├── random_forest.py
│   │   ├── gradient_boost.py
│   │   └── catboost.py
│   ├── neural/
│   │   ├── mlp.py
│   │   └── lstm.py (Q1 2027)
│   └── ensemble/
│       ├── voting.py
│       └── stacking.py
├── evaluation/
│   ├── metrics.py           # ML metrics
│   ├── cross_val.py         # CV strategies
│   └── backtest_val.py      # Trading metrics
```

### Model Comparison Table
| Model | Complexity | Interpretability | Speed |
|-------|------------|------------------|-------|
| Ridge | Low | High | Fast |
| Random Forest | Medium | Medium | Fast |
| GradientBoost | Medium | Low | Medium |
| CatBoost | Medium | Low | Medium |
| MLP | High | Low | Slow |
| LSTM | High | Low | Slow |

---

## Sprint 24-25 (Dec 26 - Jan 22, 2027): RL Exploration

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Trading environment | Gym-compatible env | `feat: trading-env` |
| DQN agent | Basic RL agent | `feat: dqn-agent` |
| Reward shaping | Risk-adjusted rewards | `feat: reward-shaping` |

### RL Architecture (FinRL'den ilham)
```
ml/
├── rl/
│   ├── environments/
│   │   ├── trading_env.py   # Gym environment
│   │   ├── multi_asset.py   # Portfolio env
│   │   └── risk_aware.py    # Risk-constrained
│   ├── agents/
│   │   ├── dqn.py           # Deep Q-Network
│   │   ├── ppo.py           # PPO (advanced)
│   │   └── a2c.py           # A2C (advanced)
│   ├── rewards/
│   │   ├── simple.py        # Raw PnL
│   │   ├── sharpe.py        # Sharpe-based
│   │   └── sortino.py       # Sortino-based
```

---

## Sprint 26 (Jan 23 - Feb 6, 2027): Year-End Consolidation

### Hedefler
| Hedef | Ölçüt | Commit |
|-------|-------|--------|
| Full system test | End-to-end validation | `test: e2e-suite` |
| Documentation | Complete docs | `docs: full-docs` |
| Performance audit | Bottleneck analysis | `perf: optimization` |

---

# Feature Wishlist: Edge/Engine/Model Ideas

## 🎯 Edge Ideas (Alpha Sources)

| Feature | Kaynak | Zorluk | Potansiyel |
|---------|--------|--------|------------|
| **Sentiment Analysis** | Twitter/Reddit | Orta | Yüksek |
| **Order Flow Imbalance** | Exchange data | Yüksek | Yüksek |
| **Funding Rate Arbitrage** | Crypto perps | Düşük | Orta |
| **Cross-Exchange Spreads** | Multiple CEX | Orta | Orta |
| **On-Chain Metrics** | Blockchain data | Yüksek | Yüksek |
| **Options Flow** | Options data | Yüksek | Yüksek |
| **Insider Trading Signals** | SEC filings | Düşük | Orta |
| **Macro Regime Detection** | Fed, economic data | Orta | Yüksek |

## 🔧 Engine Ideas (System Capabilities)

| Feature | Açıklama | Öncelik |
|---------|----------|---------|
| **Multi-Timeframe Sync** | 1m, 5m, 1h, 1d aynı anda | S1 |
| **Tick Data Support** | Sub-minute granularity | S2 |
| **Live Orderbook** | Real-time L2 data | S2 |
| **Portfolio Rebalancing** | Automated allocation | S1 |
| **Tax-Loss Harvesting** | Tax optimization | S3 |
| **Fractional Shares** | Small capital support | S1 |
| **Multi-Broker** | Redundancy | S2 |
| **Backtester GPU** | CUDA acceleration | S3 |

## 🧠 Model Ideas (ML/Intelligence)

| Model | Use Case | Complexity |
|-------|----------|------------|
| **LightGBM Ranker** | Cross-sectional stock ranking | Orta |
| **Transformer** | Sequence prediction | Yüksek |
| **Graph Neural Network** | Asset relationship | Yüksek |
| **Bayesian Optimization** | Hyperparameter tuning | Orta |
| **Thompson Sampling** | Strategy allocation | Düşük |
| **GARCH** | Volatility forecasting | Düşük |
| **Hidden Markov Model** | Regime detection | Orta |
| **Attention Mechanism** | Feature importance | Yüksek |

## 🏗️ System Ideas (Infrastructure)

| Feature | Açıklama | Kaynak |
|---------|----------|--------|
| **Docker Deployment** | Containerized system | DevOps |
| **Kubernetes** | Scaled deployment | DevOps |
| **Redis Cache** | Real-time data cache | QuantHedgeFund |
| **PostgreSQL + TimescaleDB** | Time-series DB | Nautilus |
| **Apache Kafka** | Event streaming | LEAN |
| **Grafana Dashboards** | Monitoring | Standard |
| **Jupyter Integration** | Research notebooks | Qlib |
| **REST API** | External integration | Freqtrade |

---

# GitHub Repo Reference Library

## Tier 1: Çalış, Öğren, Entegre Et

| Repo | Stars | Neden |
|------|-------|-------|
| `microsoft/qlib` | 15k+ | En iyi ML-quant pipeline |
| `QuantConnect/LEAN` | 9k+ | Profesyonel event-driven architecture |
| `freqtrade/freqtrade` | 28k+ | Production-ready crypto bot |
| `nautechsystems/nautilus_trader` | 2k+ | High-performance trading |
| `stefan-jansen/machine-learning-for-trading` | 13k+ | ML features + book |

## Tier 2: İnspire Ol, Feature Al

| Repo | Alınacak Feature |
|------|------------------|
| `AI4Finance/FinRL` | Trading gym environments, DRL agents |
| `goldmansachs/gs-quant` | Risk analytics design |
| `erdewit/Backtesting.py` | Interactive visualization |
| `OpenBB-finance/OpenBBTerminal` | CLI design, data aggregation |
| `Ashutosh0x/QuantHedgeFund` | MLflow integration pattern |

## Tier 3: Referans

| Repo | Kullanım |
|------|----------|
| `quantopian/zipline` | Event-driven architecture reference |
| `jadchaar/sec-edgar-downloader` | SEC filing data |
| `ccxt/ccxt` | Multi-exchange crypto API |
| `ranaroussi/yfinance` | Yahoo Finance data |
| `twopirllc/pandas-ta` | Technical indicators |

---

# Yıllık Özet

| Çeyrek | Odak | Anahtar Çıktı |
|--------|------|---------------|
| Q1 | Data + Events | Feature Store, Event Bus |
| Q2 | Strategy | Alpha Engine, Council v2 |
| Q3 | Risk + Execution | Portfolio Risk, Kill-Switch |
| Q4 | ML | Models, Experiment Tracking |

## Commit Sayısı Hedefi

| Kategori | Hedef |
|----------|-------|
| feat: | 50+ |
| refactor: | 20+ |
| test: | 30+ |
| docs: | 15+ |
| fix: | 40+ |
| **Toplam** | **150+ commits** |

## Yıl Sonu Success Metric

```
12 ay paper trading + backtest data ile:
- Sharpe > 0.8
- Max DD < 12%
- Win rate > 45%
- Profit factor > 1.3
- System uptime > 99%
```

Bu metriklere ulaşılırsa: **LIVE TRADING READY**

---

**Document Version:** 1.0  
**Author:** Founder + AI Architect  
**Next Review:** Her sprint sonunda

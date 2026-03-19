# Argus Python: Implementation Roadmap

This roadmap defines the step-by-step execution plan to build the Argus Python System from zero to feature parity and beyond.

## Phase P0: Foundation & Setup
**Goal**: Clean repo state, validated environment.
- [ ] Initialize `argus-python/` root directory.
- [ ] Define standard project layout:
  - `src/argus/`
  - `tests/`
  - `scripts/`
  - `data/` (symlinked or ignored)
- [ ] Setup `pyproject.toml` (or `requirements.txt`) with minimal deps (pandas, numpy, polars (opt), pytest).
- [ ] Configure `logging` module to match Argus Swift format.

## Phase P1: Core Engine & Data
**Goal**: A deterministic loop that loads data and iterates.
- [ ] **CSV Loader**:
  - Implement robust CSV parsing (pandas/polars).
  - Ensure column type safety (float64 for prices).
  - Unit Tests: Test gaps, missing columns, simple files.
- [ ] **Candle Model**:
  - Define `Bar` / `Candle` dataclass/struct.
  - Implement `DataFeed` class (iterator).
- [ ] **Engine Skeleton**:
  - Create `BacktestEngine` class.
  - Implement the main loop: `for event in feed: ...`.
  - Validate timestamps match CSV exactly.

## Phase P2: Aegean Indicator Port
**Goal**: Reproduce the "Aegean" signal logic 1:1.
- [ ] **Indicators Module**:
  - Implement EMA (Exponential Moving Average).
  - Implement Linear Regression Slope.
  - Implement Channel/Zone logic.
- [ ] **Aegean Strategy**:
  - Combine indicators into `AegeanStrategy` class.
  - Implement `compute(history) -> Signal`.
  - **Parity Check**: Feed same CSV to Python and Swift, assert same values for Slope, Pos, and Zone.

## Phase P3: Broker & Portfolio
**Goal**: Handle money, orders, and positions.
- [ ] **PaperBroker**:
  - Implement `Account` state (Balance, Equity).
  - Implement `Order` types (Market, Limit placeholders).
  - Implement `Position` tracking (AvgPrice, Size, PnL).
- [ ] **Bracket Logic**:
  - Implement local SL/TP monitoring.
  - Trigger exits when price hits SL/TP levels inside the loop.
- [ ] **Reporting**:
  - Generate "Trade Log" (entry time, price, exit time, price, pnl).

## Phase P4: Risk Engine (The Guardian)
**Goal**: Safety constraints and low-balance survival.
- [ ] **Risk Manager**:
  - Implement Daily Loss Limit check.
  - Implement Max Drawdown check.
  - Implement Consecutive Loss cooldown.
- [ ] **Sizing & Constraints**:
  - **Low Bal Fix**: Port the dynamic `minNotional` logic ($1.0 vs $5.0).
  - Implement standard position sizing (% of equity).
- [ ] **Integration**: Connect Risk manager to Strategy entries.

## Phase P5: Exits & Advanced Management
**Goal**: Maximize trade value.
- [ ] **Trailing Stop**: Implement ATR-based or structure-based trailing.
- [ ] **Time Stop**: Exit if trade stagnant for N bars.
- [ ] **Opposite Signal**: Flip position if strategy reverses hard.

## Phase P6: Testing & Parity
**Goal**: Prove it works.
- [ ] **Integration Test**: Run full backtest on BTCUSDT.
- [ ] **Comparison**: Compare `run_30.log` (Swift) vs Python output.
- [ ] **CI/CD**: Setup basic GitHub Actions (optional but recommended).

## Phase P7+: Future Expansion (Post-MVP)
- [ ] **Vote Engine**: Multi-strategy (Orion/Atlas) weighted voting.
- [ ] **Optimization**: Hyperparameter grid search.
- [ ] **C Acceleration**: Optimize hot loops (indicators/backtest) in C.
- [ ] **Live Bridge**: CCXT or Direct API integration.

---

**Execution Rule**: Do not proceed to next phase until current phase tests pass.

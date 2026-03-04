# ARGUS v2.5 — Institutional Risk Management Architecture

> **Version**: 2.5.1 · **Date**: 2026-02-27 · **Status**: LIVE (Paper Trading)

---

## 1. The Core Philosophy

### The Problem: "Right Signal, Wrong Execution"

ARGUS signal engines (AEGEAN, POSEIDON, TITAN) were already producing accurate directional predictions. The real-world failure mode was never the signal — it was the execution.

**The 65k → 63k → 66k Scenario:**

```
Signal fires LONG at $65,000 (confidence: 0.78)
├── Old system: 100% position size, stop at $64,000 (1.5% stop)
├── Price dips to $63,000 → STOPPED OUT (-1.5%)
└── Price pumps to $66,000 → Correct signal, zero profit
```

The system was entering with 100% of its risk budget at a single price point with a tight stop-loss. In crypto markets, liquidation wicks routinely sweep 1-3% before continuing in the predicted direction. A correct signal was being punished by rigid execution.

### The Solution: Asymmetric, Flexible Entry

The fix was not to widen stops (which increases risk) or reduce confidence thresholds (which reduces signal quality). The fix was to **restructure how capital is deployed**:

```
Signal fires LONG at $65,000 (confidence: 0.78)
├── New system: 30% scout entry at $65,000
├── Price dips to $63,700 → REINFORCE: add 70% at better price
├── Average entry: ~$64,090 (improved)
├── Stop at $63,000 → still intact (wider effective stop from avg entry)
├── Break-even lock snaps SL to $64,220 at +1× ATR
└── Price pumps to $66,000 → Full position, profit captured
```

Three self-contained modules implement this:

| Module | File | Purpose |
|--------|------|---------|
| Scale-In Orchestrator | [scale_in_orchestrator.py](file:///e:/argus/argus-terminal/src/risk/scale_in_orchestrator.py) | Multi-layer position entry (30/70 split) |
| Dynamic Leverage Calibrator | [leverage_calibrator.py](file:///e:/argus/argus-terminal/src/risk/leverage_calibrator.py) | Fixed-risk leverage tied to stop distance |
| Break-Even Lock | [breakeven_lock.py](file:///e:/argus/argus-terminal/src/risk/breakeven_lock.py) | ATR-based SL snap to avg entry + fees |
| Market Structure | [market_structure.py](file:///e:/argus/argus-terminal/src/features/market_structure.py) | SL Shield (hide behind support) + TP Magnet (take before resistance) |

---

## 2. Scale-In Orchestrator (DCA)

**Source**: `src/risk/scale_in_orchestrator.py`

### 2.1 Design Principle

Never fire 100% of the risk budget on the first signal. Instead, deploy capital in layers:

- **Layer 0 — Scout Entry (30%)**: Establish initial exposure on a NORMAL-confidence signal.
- **Layer 1+ — Reinforcement (70%)**: Add remaining capital when price improves or signal strengthens to STRONG.

This is not dollar-cost-averaging in the retail sense. It is institutional-grade pyramiding where each layer requires **explicit justification** (price improvement, signal confirmation, or both).

### 2.2 Configuration

```python
@dataclass(frozen=True)
class ScaleInConfig:
    enabled: bool = True
    scout_pct: float = 0.30              # 30% on NORMAL signal
    reinforcement_pct: float = 0.70      # 70% on STRONG / price-improved
    max_layers: int = 3                  # Maximum pyramid layers
    min_price_improvement_pct: float = 0.01  # 1% price must improve
    cooldown_minutes: int = 15           # Min gap between layers
    max_avg_entry_deviation_pct: float = 0.05  # 5% max avg entry drift
```

### 2.3 Entry Rules

| Condition | Scout (Layer 0) | Reinforcement (Layer 1+) |
|-----------|:---:|:---:|
| Signal present | ✅ Required | ✅ Required |
| Price improved ≥ 1% | — | ✅ Required |
| Cooldown elapsed (15 min) | — | ✅ Required |
| Risk budget remaining | ✅ Checked | ✅ Checked |
| Max layers not reached | ✅ Checked | ✅ Checked |
| Avg entry deviation ≤ 5% | — | ✅ Checked |

### 2.4 Signal Strength Scaling

The scout allocation adjusts based on signal confidence:

| Signal Strength | Confidence | Scout Size | Reinforcement Size |
|:---:|:---:|:---:|:---:|
| `NORMAL` | < 0.80 | 30% of budget | 35% (half reinforcement) |
| `STRONG` | ≥ 0.80 | 50% of budget | 70% (full reinforcement) |

This means high-conviction signals get more aggressive initial deployment while still reserving capital for reinforcement.

### 2.5 Weighted Average Entry

After each layer, the average entry price is recalculated:

```
avg_entry = Σ(price_i × qty_i) / Σ(qty_i)
```

This is critical because the **break-even lock** and **leverage calibrator** both operate on the average entry, not individual layer entries.

### 2.6 Position Lifecycle

```
pending → scout (Layer 0 filled)
       → reinforced (Layer 1 filled, budget < 95%)
       → full (budget ≥ 95% consumed)
```

### 2.7 Database Persistence

Scale-in layers are persisted to the `pyramid_layers` table with columns:

| Column | Type | Purpose |
|--------|------|---------|
| `risk_budget` | REAL | Total risk allocated to this position |
| `risk_used` | REAL | Cumulative risk consumed by this layer |
| `avg_entry_after` | REAL | Weighted avg entry after this layer |
| `signal_strength` | TEXT | NORMAL / STRONG / VERY_STRONG |

---

## 3. Dynamic Leverage Calibrator

**Source**: `src/risk/leverage_calibrator.py`

### 3.1 Design Principle

Leverage is **not a risk parameter**. It is a **mathematical consequence** of two fixed inputs:

1. **Fixed equity risk** (e.g., 2% of account per trade)
2. **Stop-loss distance** (determined by ATR and market volatility)

The calibrator computes leverage dynamically so that every trade risks exactly the same dollar amount, regardless of how tight or wide the stop is.

### 3.2 The Math

```
risk_usd = equity × risk_pct                          # CONSTANT
notional = risk_usd / stop_distance_pct               # Position size
leverage = notional / equity                           # Derived
```

### 3.3 Practical Examples

Given: **$10,000 equity**, **2% risk** ($200 max loss per trade)

| Stop Distance | Leverage | Notional | Risk at Stop | Note |
|:---:|:---:|:---:|:---:|:---|
| 0.5% | 4.0x | $40,000 | $200 | Tight stop, sniper entry |
| 1.0% | 2.0x | $20,000 | $200 | Standard |
| 2.0% | 1.0x | $10,000 | $200 | Wide stop, conservative |
| 0.2% | 10.0x | $100,000 | $200 | Mean-reversion sniper |
| 3.0% | 1.0x (floor) | $10,000 | $300* | Floored — actual risk < budget |

> \* When leverage floors at 1.0x, the actual loss at stop is less than the 2% budget. Capital is preserved.

### 3.4 Why the Pydantic Cap Was Raised to 20.0

The old `Decision.leverage` field had a hard cap of `le=3.0`. This was a blunt safety measure from before the calibrator existed.

With the calibrator in place, a 10x leverage trade with a 0.2% stop is **mathematically identical in risk** to a 2x trade with a 1% stop. Both risk exactly $200 on a $10,000 account. The safety now comes from the **calibration math**, not arbitrary caps.

The cap was raised to `le=20.0` to allow the calibrator full range for tight-stop sniper entries.

### 3.5 Configuration

```python
@dataclass(frozen=True)
class LeverageCalibrationConfig:
    enabled: bool = True
    max_leverage: float = 20.0       # Hard ceiling
    min_leverage: float = 1.0        # Floor
    risk_pct: float = 0.02           # 2% equity risk per trade
    safety_margin: float = 0.95      # 95% of theoretical (absorbs slippage)
```

### 3.6 Safety Margin

The `safety_margin=0.95` multiplier reduces the theoretical notional by 5% to absorb:
- Order book slippage
- Funding rate costs
- Execution latency between signal and fill

---

## 4. Fee-Adjusted Break-Even Lock

**Source**: `src/risk/breakeven_lock.py`

### 4.1 Design Principle

Once price moves **1× ATR** in our favor from the average entry, snap the stop-loss to **break-even + round-trip fees**. This creates a mathematically risk-free position.

### 4.2 Why ATR, Not R-Multiples?

The existing DRM `TrailingRules` uses R-multiples (relative to stop distance). The break-even lock uses **ATR** (absolute volatility) because:

| Aspect | R-Multiple (DRM) | ATR (Break-Even Lock) |
|--------|:-:|:-:|
| Reference point | Initial stop distance | Market volatility |
| Entry awareness | Single entry only | Scale-in avg entry |
| Fee accounting | None | Round-trip fees included |
| Purpose | Trailing profit lock | **Risk elimination** |

### 4.3 The Fee Offset

A "break-even" that doesn't account for fees is actually a small loss. The lock includes fees:

```
Long BE  = avg_entry × (1 + 2 × fee_pct)    # Entry + exit fees
Short BE = avg_entry × (1 - 2 × fee_pct)
```

With BingX fees (0.1% per side):

| Entry Price | Naive BE | True BE (with fees) | Hidden Loss Avoided |
|:---:|:---:|:---:|:---:|
| $65,000 | $65,000 | $65,130 | $130 |
| $40,000 | $40,000 | $40,080 | $80 |
| $100,000 | $100,000 | $100,200 | $200 |

### 4.4 Trigger Mechanism

```
Long:  IF current_price ≥ avg_entry + (trigger_atr_multiple × ATR)
       THEN SL = max(current_SL, BE_price)    # never regresses

Short: IF current_price ≤ avg_entry - (trigger_atr_multiple × ATR)
       THEN SL = min(current_SL, BE_price)    # never regresses
```

### 4.5 Non-Regression Guarantee

The break-even lock **never moves the stop-loss against the trade**:
- If SL is already above BE (for longs), it stays at the higher level
- If SL is already below BE (for shorts), it stays at the lower level

This means the DRM trailing stop and break-even lock work together: BE lock sets the floor, DRM trailing ratchets above it.

### 4.6 Configuration

```python
@dataclass(frozen=True)
class BreakevenConfig:
    enabled: bool = True
    trigger_atr_multiple: float = 1.0    # Snap at 1× ATR profit
    include_fees: bool = True
    default_fee_pct: float = 0.001       # 0.1% per side
```

---

## 5. Market Structure — SL Shield & TP Magnet

**Source**: `src/features/market_structure.py`

### 5.1 Design Principle

ATR measures volatility but has no "market memory". It cannot see that a support wall at $63,800 makes a stop at $63,500 vulnerable to liquidity hunts, or that resistance at $66,800 will reject price before our TP at $67,000 fills.

Market structure adds that memory by detecting recent **Swing Highs** (Resistance) and **Swing Lows** (Support), then adjusting SL/TP placement relative to these structural levels.

### 5.2 Non-Repainting Swing Detection

A Swing Low at index `i` is confirmed when:

```
lows[i] == min(lows[i-N : i+N+1])   AND   lows[i] < max(lows[i-N : i+N+1])
```

**Non-repainting guarantee**: The last valid center index is `len(data) - 1 - N`. The right-side window must fully close before a pivot is declared. No future data is ever used.

### 5.3 Level Clustering

Nearby levels (within 0.3%) are merged into clusters with boosted `strength`. This prevents noise from multiple touches near the same price from creating redundant levels.

### 5.4 SL Shield

Hides the stop-loss behind structural support/resistance:

| Side | Mechanism |
|------|-----------|
| Long | Find support between (SL, entry) → push SL just below it |
| Short | Find resistance between (entry, SL) → push SL just above it |

The SL moves **behind the wall**, gaining structural protection. A max tightening limit prevents excessive stop reduction.

### 5.5 TP Magnet

Pulls take-profit to just before structural walls:

| Side | Mechanism |
|------|-----------|
| Long | Resistance in last 20% of TP range → pull TP below it |
| Short | Support in last 20% of TP range → pull TP above it |

This ensures fills before rejection, rather than placing a TP beyond an impenetrable wall.

### 5.6 Configuration

```python
@dataclass(frozen=True)
class MarketStructureConfig:
    enabled: bool = False              # Feature flag: OFF by default
    swing_window: int = 5              # N bars left + N bars right
    max_levels: int = 5                # Top 5 nearest per side
    cluster_tolerance_pct: float = 0.003  # 0.3% merge threshold
    min_age_bars: int = 3              # Ignore very recent pivots
```

---

## 6. Pipeline Integration

### 6.1 Execution Flow (Modified Steps)

```
Signal → Step 8: Sizing ──────────────────────┐
         │                                     │
         ├── compute_growth_size()             │
         ├── IF scale_in.enabled:              │
         │   └── initial_position_size_pct()   │  ← Scale-In: reduces to 30%
         │                                     │
         └── Step 8.1: DRM ───────────────────┤
             │                                 │
             ├── compute_risk_decision()       │
             ├── IF leverage_cal.enabled:      │
             │   └── calibrate_leverage()      │  ← LevCal: ties to stop distance
             ├── IF market_structure.enabled:  │
             │   └── adjust_sl_tp()            │  ← SL Shield + TP Magnet
             │                                 │
             └── Step 9: Execute ─────────────┘

Position Open → Each Cycle:
         │
         ├── _apply_drm_trailing_stops()
         │   ├── IF breakeven.enabled:
         │   │   └── check_breakeven_trigger() ← BE Lock: snaps SL first
         │   └── drm_apply_trailing()          ← DRM trailing: ratchets above
         │
         └── Continue...
```

### 6.2 Order of Operations

The break-even lock executes **before** the DRM trailing stop in each cycle. This ensures:

1. BE lock sets the floor (entry + fees)
2. DRM trailing only moves the stop higher (profit locking)
3. Neither can regress the stop backwards

---

## 7. Feature Flags

All three modules are controlled via configuration objects in `ArgusPipeline.__init__`:

```python
# Active configuration (paper trading)
self._scale_in_config = ScaleInConfig(enabled=True)
self._leverage_cal_config = LeverageCalibrationConfig(
    enabled=True, risk_pct=0.02, max_leverage=20.0
)
self._breakeven_config = BreakevenConfig(
    enabled=True, trigger_atr_multiple=1.0
)
```

To disable any module without code changes, set `enabled=False`. The pipeline will bypass the module entirely and fall back to pre-v2.5 behavior:

| Config | `enabled=False` Behavior |
|--------|--------------------------|
| ScaleInConfig | Full 100% position on first signal |
| LeverageCalibrationConfig | DRM leverage used as-is |
| BreakevenConfig | Only DRM trailing stops apply |
| MarketStructureConfig | ATR-based SL/TP used as-is |

---

## 8. Test Coverage

```
100 tests passed in 0.45s

├── test_market_structure.py         24 tests
│   ├── Swing detection (V-pattern, inverted-V, flat, edge cases)
│   ├── Non-repainting proof (last N bars never signal)
│   ├── Clustering (merge/separate/triple, strength summing)
│   ├── Builder (disabled passthrough, age filter, max levels, sorting)
│   ├── SL Shield (long behind support, short behind resistance, bounds)
│   └── TP Magnet (pull before resistance, zone boundary, dual adjustment)
│
├── test_scale_in_orchestrator.py    23 tests
├── test_leverage_calibrator.py      15 tests
├── test_breakeven_lock.py           14 tests
└── test_dynamic_risk_manager.py     24 tests (REGRESSION — zero breakage)
```

---

## 9. File Manifest

| File | Status | Lines | Purpose |
|------|:------:|------:|---------|
| `src/features/market_structure.py` | NEW | 330 | Swing detection + SL Shield + TP Magnet |
| `src/risk/scale_in_orchestrator.py` | NEW | 270 | DCA orchestrator |
| `src/risk/leverage_calibrator.py` | NEW | 175 | Dynamic leverage |
| `src/risk/breakeven_lock.py` | NEW | 165 | BE lock |
| `src/core/types.py` | MOD | 1 line | leverage cap 3.0→20.0 |
| `src/main.py` | MOD | ~90 lines | Pipeline wiring (Steps 8, 8.2, 8.3, BE lock) |
| `src/v25/db/migrations.py` | MOD | 15 lines | pyramid_layers +4 cols |
| `tests/features/test_market_structure.py` | NEW | 420 | 24 tests |
| `tests/risk/test_scale_in_orchestrator.py` | NEW | 250 | 23 tests |
| `tests/risk/test_leverage_calibrator.py` | NEW | 175 | 15 tests |
| `tests/risk/test_breakeven_lock.py` | NEW | 210 | 14 tests |

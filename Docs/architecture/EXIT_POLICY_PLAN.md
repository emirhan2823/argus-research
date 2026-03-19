# ARGUS — Trailing Stop + Dynamic Exit Layer

## Context

Backtest analizi 1319 trade üzerinden 0 golden pattern buldu — WR hiçbir zaman %50'yi aşmıyor.
Temel neden: main.py backtest yolu **sadece SL hit vs 60m time_exit** destekliyor.
Trailing stop, breakeven lock, engine-aware time-stop hiç yok.
`backtest_simulator.py`'de zaten tam exit logic var ama war_backtest_lab tarafından kullanılmıyor.

**Hedef**: İki paralel exit sistemini birleştirmek için **shared exit policy modülü** oluştur,
main.py backtest yoluna trailing stop + BE lock + engine-aware time stop ekle.

---

## Problem: İki Paralel Exit Sistemi

| | System A: `backtest_simulator.py` | System B: `src/main.py` |
| --- | --- | --- |
| Kullanıldığı yer | Standalone simulator | war_backtest_lab |
| Exit logic | BE lock → trailing → SL/TP → time_stop | SL check only → time_exit |
| Trailing stop | POSEIDON engine, 1% trail | YOK |
| Breakeven lock | 1.5×ATR trigger | YOK |
| Time stop | Engine-aware candle count | Hold minutes (60m fixed) |
| Exit reasons | sl, tp, trailing, be_stop, time_stop | stop_loss_hit, time_exit_backtest_sim |

---

## Approach: Option C — Shared Exit Policy Module

Neden diğerleri değil:

- **A (inline patch)**: İki yerde aynı logic = maintenance drift
- **B (import SimulatedPosition)**: Çok fazla dummy field gerekir (tp_price, size_usd)
- **C (shared module)**: Pure function, zero state, her iki sistem kullanabilir

---

## Revisions (User-Approved)

### R1: Canonical Exit Reason Strings

Persisted `reason_exit` değerleri (standardize):

- `"stop_loss_hit"` — initial SL hit (BE lock engage olmamış)
- `"breakeven_stop_hit"` — SL hit while BE lock engaged
- `"trailing_stop_hit"` — SL hit after trailing ratchet tightened SL beyond initial
- `"time_stop_hit"` — engine max_hold_candles reached, exit at close
- `"time_exit_backtest_sim"` — outer bound close, nothing else hit

Eski DB'lerde "sl", "be_stop" gibi değerler korunur (backward compat).

### R2: ATR Semantics — atr_pct Only

- `atr_pct` = ATR / price (fraction). Tutarlılık: `atr_distance = entry_price * atr_pct * be_trigger_atr_mult`
- `atr_pct == 0` veya missing → BE lock **disabled** (candle-based ATR fallback YOK v1'de)
- Trailing stop ATR'ye bağlı değil (sadece trail_pct), dolayısıyla ATR eksikliği trailing'i etkilemez

### R3: Lookahead-Safe Candle Evaluation Order

Her candle için sıralama (backtest_simulator.py ile birebir):

```
a) candle_age += 1
b) BE lock check using CLOSE only (not high/low)
c) Trailing ratchet using CLOSE only (not high/low)
d) SL wick hit check using LOW (long) / HIGH (short)
e) Time-stop if candle_age >= max_hold_candles → exit at CLOSE
```

Son candle ve exit yok → `"time_exit_backtest_sim"` at last candle CLOSE.

### R4: Engine Config — Safe Defaults

```python
DEFAULT_EXIT_CONFIG = EngineExitConfig(
    trailing_enabled=False, be_lock_enabled=True,
    be_trigger_atr_mult=1.5, max_hold_candles=16
)
ENGINE_EXIT_CONFIGS.get(engine, DEFAULT_EXIT_CONFIG)  # ASLA KeyError
```

v1'de trailing sadece POSEIDON'da aktif. TITAN+verified_trend sonraki iterasyon.

### R5: Candle Slicing Guardrails

- `_forward_history` candles: `["timestamp", "high", "low", "close"]` gerekli kolonlar
- Eksik kolon → fallback to old SL-only scan + time_exit (graceful degradation)
- Debug log: `"exit_eval | symbol=%s candles=%d first=%s last=%s"` (off-by-one catch)

### R6: Naming — `be_buffer_pct`

`be_fee_pct` → `be_buffer_pct` (fees+slippage buffer, default 0.001)

### R7: Ek Testler

- `test_unknown_engine_uses_default_config`
- `test_empty_candles_returns_none`
- Parity tests: POSEIDON long/short + HYDRA short + AEGEAN long vs simulator
- Float tolerance for exit_price (`pytest.approx`)

---

## Implementation Plan

### Faz 1: Shared Exit Module (`src/backtest/exit_policy.py`) — YENİ

```python
@dataclass(frozen=True)
class EngineExitConfig:
    trailing_enabled: bool = False
    trail_pct: float = 0.01          # 1% trailing distance
    be_lock_enabled: bool = True
    be_trigger_atr_mult: float = 1.5  # BE lock after 1.5×ATR move
    be_buffer_pct: float = 0.001     # buffer for BE price (R6)
    max_hold_candles: int = 16       # time-stop candle limit

ENGINE_EXIT_CONFIGS: dict[str, EngineExitConfig] = {
    "HYDRA":    EngineExitConfig(trailing_enabled=False, max_hold_candles=6),
    "NAUTILUS": EngineExitConfig(trailing_enabled=False, max_hold_candles=12),
    "AEGEAN":   EngineExitConfig(trailing_enabled=False, max_hold_candles=8),
    "POSEIDON": EngineExitConfig(trailing_enabled=True, trail_pct=0.01, max_hold_candles=24),
    "TITAN":    EngineExitConfig(trailing_enabled=False, max_hold_candles=16),
}
DEFAULT_EXIT_CONFIG = EngineExitConfig()  # trailing=False, max=16

@dataclass
class ExitResult:
    exit_price: float
    exit_time: datetime
    exit_reason: str          # R1 canonical strings
    exit_candle_index: int
    final_sl: float
    be_locked: bool
    candles_evaluated: int    # R5 debug metric

def get_engine_exit_config(engine: str) -> EngineExitConfig:
    return ENGINE_EXIT_CONFIGS.get(engine, DEFAULT_EXIT_CONFIG)  # R4

def evaluate_exit_bar_by_bar(
    *, candles: list[dict],   # [{timestamp, high, low, close}, ...]
    side: str,                # "long" | "short"
    entry_price: float,
    initial_stop_price: float,
    atr_pct: float,           # R2: 0 → BE disabled
    config: EngineExitConfig,
) -> ExitResult | None:
    """Bar-by-bar exit evaluation. R3 ordering per candle."""
    # Returns None if candles empty
```

### Faz 2: main.py Backtest Entegrasyonu

**2A: `_check_backtest_stop_hit` → `_evaluate_backtest_exit`** (satır 2189-2235)

```python
def _evaluate_backtest_exit(self, *, symbol, side, entry_price, stop_distance,
                             entry_time, exit_time, engine, atr_pct=0.0
) -> tuple[float | None, datetime | None, str]:
```

- `_forward_history`'den candle'ları al (entry_time..exit_time)
- Kolon kontrolü: `["timestamp", "high", "low", "close"]` yoksa → old SL-only (R5)
- `get_engine_exit_config(engine)` ile config al (R4)
- `atr_pct == 0` → BE lock disabled (R2)
- `evaluate_exit_bar_by_bar()` çağır
- Debug log: candle count + first/last timestamp (R5)
- 3-tuple dön: (exit_price, exit_time, exit_reason)

**2B: ATR'yi call site'a ekle** (satır ~3688)

```python
gate_results = rec.get("gate_results", {})
features_snap = (gate_results.get("features_snapshot", {})
                 if isinstance(gate_results, dict) else {})
atr_pct = float(features_snap.get("atr_14_pct", 0.0) or 0.0)
```

**2C: Caller güncelle** (satır ~3852)

```python
_exit_px, _exit_time, _exit_reason = pipeline._evaluate_backtest_exit(
    symbol=symbol, side=action, entry_price=entry_price,
    stop_distance=stop_distance, entry_time=entry_time,
    exit_time=exit_time, engine=engine, atr_pct=atr_pct,
)
if _exit_px is not None and _exit_time is not None:
    exit_price = float(_exit_px)
    exit_time = _exit_time
# _exit_reason already set (canonical R1 string)
```

### Faz 3: Testler

**`tests/backtest/test_exit_policy.py`** (14+ test):

| Test | Açıklama |
| --- | --- |
| `test_sl_hit_basic_long` | SL hit on wick, correct price+time |
| `test_sl_hit_basic_short` | Short side SL check |
| `test_no_exit_returns_time_exit` | Candle'lar SL'ye ulaşmaz → time_exit at close |
| `test_breakeven_lock_triggers` | 1.5×ATR move → SL snaps to entry+buffer |
| `test_trailing_ratchets_long` | POSEIDON, price rises 3%, trail locks below peak |
| `test_trailing_ratchets_short` | Short trailing |
| `test_trailing_disabled_non_trailing_engine` | NAUTILUS → trailing never engages |
| `test_be_lock_then_trailing` | BE lock first, then trailing ratchets further |
| `test_candle_age_time_stop` | 25 candles, max=24 → time_stop_hit at candle 24 |
| `test_empty_candles_returns_none` | No candles → None |
| `test_atr_zero_disables_be_lock` | atr_pct=0 → BE lock never triggers (R2) |
| `test_unknown_engine_uses_default` | Unknown engine → DEFAULT_EXIT_CONFIG (R4/R7) |
| `test_backward_compat_all_disabled` | All disabled → old SL-only behavior |
| `test_canonical_exit_reasons` | Verify exact reason strings (R1) |

**`tests/backtest/test_exit_consistency.py`** (4+ parameterized tests):

- 20 candle sequence → run through both SimulatedPosition + evaluate_exit_bar_by_bar
- Assert same exit_reason, exit_price (pytest.approx), exit_candle_index
- Params: POSEIDON long, POSEIDON short, HYDRA short, AEGEAN long (R7)

---

## Dosya Listesi

| Dosya | İşlem | Faz |
| --- | --- | --- |
| `src/backtest/exit_policy.py` | YENİ — shared exit evaluation | 1 |
| `src/main.py` (satır 2189-2235) | MODIFY — `_evaluate_backtest_exit` | 2A |
| `src/main.py` (satır ~3688) | MODIFY — atr_pct extraction | 2B |
| `src/main.py` (satır ~3852) | MODIFY — caller 3-tuple return | 2C |
| `tests/backtest/test_exit_policy.py` | YENİ — 14 unit test | 3 |
| `tests/backtest/test_exit_consistency.py` | YENİ — parity tests | 3 |

## Referans Dosyalar (read-only)

| Dosya | Neden |
| --- | --- |
| `src/backtest/backtest_simulator.py:67-196` | SimulatedPosition — BE lock, trailing logic |
| `src/backtest/backtest_simulator.py:397-502` | on_candle() — evaluation order (R3 reference) |
| `src/backtest/backtest_simulator.py:27-38` | ENGINE_MAX_AGE, TRAILING_ENGINES constants |

## Doğrulama

1. `python -m pytest tests/backtest/test_exit_policy.py -v` → 14 test geçmeli
2. `python -m pytest tests/backtest/test_exit_consistency.py -v` → 4 parameterized test geçmeli
3. Luna crash backtest → trailing_stop_hit, breakeven_stop_hit, time_stop_hit exit reason'ları
4. Analysis pipeline → yeni exit reason'lar ANALYSIS_SUMMARY.md'de görülmeli
5. `python -m pytest tests/ -x -q` → mevcut 1327+ test kırılmamalı

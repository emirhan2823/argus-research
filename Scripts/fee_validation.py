"""ARGUS v2.5 - Crypto Fee Mode Validation Run (A/B/C comparison).

Run A: Baseline (crypto_fee_mode=False)
Run B: Fee-Aware v1 (crypto_fee_mode=True, default thresholds)
Run C: Fee-Aware v1 + HYDRA strict (tighter thresholds for HYDRA)

All runs use identical BTCUSDT 15m data and MR signal generation.
Measures POST-FEE performance with taker_fee=3bps per side.

Usage:
    python Scripts/fee_validation.py

Output: reports/fee_validation/FEE_VALIDATION_SUMMARY.md
"""

from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.exit_policy import (
    EngineExitConfig,
    evaluate_exit_bar_by_bar,
    REASON_STOP_LOSS,
    REASON_TIME_EXIT,
)

# ---------------------------------------------------------------
# Config
# ---------------------------------------------------------------
PARQUET_ROOT = Path("data/binance")
SYMBOL = "BTCUSDT"
TF = "15m"
MONTHS = ["2025-11", "2025-12", "2026-01", "2026-02"]

TAKER_FEE_BPS = 3.0
SLIPPAGE_BPS = 1.0
LEVERAGE = 5.0
INITIAL_BALANCE = 10_000.0

# MR signal generation thresholds
RSI_OB = 70  # overbought
RSI_OS = 30  # oversold
BB_UPPER_THRESHOLD = 0.85  # %B above -> short
BB_LOWER_THRESHOLD = 0.15  # %B below -> long
MIN_CANDLE_GAP = 6  # min 1.5h gap between signals

# Trade parameters
SL_ATR_MULT = 2.0  # ATR x 2.0 stop (POSEIDON default)
TP_RR_BASE = 2.0   # base RR target

HOLD_CANDLES = 12  # 3h on 15m TF (POSEIDON default)

MR_EXIT_CONFIG = EngineExitConfig(
    trailing_enabled=False, be_lock_enabled=False, max_hold_candles=HOLD_CANDLES,
)

OUTPUT_DIR = Path("reports/fee_validation")


# ---------------------------------------------------------------
# Run Configs
# ---------------------------------------------------------------

@dataclass
class RunConfig:
    name: str
    label: str
    crypto_fee_mode: bool = False
    taker_fee_bps: float = 3.0
    min_rr: float = 1.5       # standard gate 7
    min_tp_pct: float = 0.001  # standard gate 6
    min_edge: float = -999.0   # disabled
    tq_min_grade: str = "C"    # standard: C with high conf allowed
    tq_high_conf_exception: bool = True
    grade_a_size_mult: float = 1.0
    grade_b_size_mult: float = 1.0
    mr_max_adx: float = 99.0     # disabled
    mr_max_atr_pctl: float = 1.0  # disabled
    hydra_min_tp: float = 0.001   # same as global
    hydra_min_rr: float = 1.5     # same as global
    engine_filter: str = "ALL"    # POSEIDON, HYDRA, NAUTILUS, or ALL


RUN_A = RunConfig(
    name="A_baseline",
    label="A) Baseline (fee-aware OFF)",
    crypto_fee_mode=False,
)

RUN_B = RunConfig(
    name="B_fee_mode",
    label="B) Fee-Aware v1",
    crypto_fee_mode=True,
    min_rr=2.0,
    min_tp_pct=0.01,
    min_edge=0.0,
    tq_min_grade="B",
    tq_high_conf_exception=False,
    grade_a_size_mult=1.25,
    grade_b_size_mult=1.10,
    mr_max_adx=30.0,         # BTC median ADX ~31 -> 30 filters trending half
    mr_max_atr_pctl=0.70,    # aligned with mr_strict_atr_threshold
)

RUN_C = RunConfig(
    name="C_fee_strict",
    label="C) Fee-Aware + HYDRA Strict",
    crypto_fee_mode=True,
    min_rr=2.0,
    min_tp_pct=0.01,
    min_edge=0.0,
    tq_min_grade="B",
    tq_high_conf_exception=False,
    grade_a_size_mult=1.25,
    grade_b_size_mult=1.10,
    mr_max_adx=30.0,
    mr_max_atr_pctl=0.70,
    hydra_min_tp=0.012,
    hydra_min_rr=2.2,
)


# ---------------------------------------------------------------
# Data Loading + Indicators
# ---------------------------------------------------------------

def _load_15m_data() -> pd.DataFrame:
    """Load all 15m BTCUSDT parquets and compute indicators."""
    frames = []
    for m in MONTHS:
        p = PARQUET_ROOT / SYMBOL / TF / f"{m}.parquet"
        if not p.exists():
            print(f"  [WARN] Missing: {p}")
            continue
        frames.append(pd.read_parquet(p))

    if not frames:
        raise FileNotFoundError("No 15m parquet data found")

    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # ATR
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr_14"] = tr.ewm(span=14, adjust=False).mean()
    df["atr_pct"] = df["atr_14"] / df["close"]

    # ATR percentile (rolling 100 bars)
    df["atr_pctl"] = df["atr_14"].rolling(100, min_periods=20).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    )

    # ADX
    df["adx"] = _compute_adx(df)

    # ADX rising 3 bars
    df["adx_rising_3"] = (
        (df["adx"] > df["adx"].shift(1)) &
        (df["adx"].shift(1) > df["adx"].shift(2)) &
        (df["adx"].shift(2) > df["adx"].shift(3))
    )

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
    rs = gain / (loss + 1e-10)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # Bollinger %B
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    df["bb_pct_b"] = (close - bb_lower) / (bb_upper - bb_lower + 1e-10)

    # Volume ratio
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean().clip(lower=1)

    # EMA for trend context
    df["ema_21"] = close.ewm(span=21, adjust=False).mean()
    df["ema_55"] = close.ewm(span=55, adjust=False).mean()

    df = df.dropna().reset_index(drop=True)
    return df


def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
    return dx.ewm(span=period, adjust=False).mean()


# ---------------------------------------------------------------
# Signal Generation (MR Consortium-style)
# ---------------------------------------------------------------

@dataclass
class RawSignal:
    idx: int
    timestamp: datetime
    side: str           # long | short
    engine: str         # POSEIDON | HYDRA | NAUTILUS
    confidence: float
    entry_price: float
    atr_pct: float
    atr_pctl: float
    adx: float
    adx_rising_3: bool
    rsi: float
    bb_pct_b: float
    vol_ratio: float
    sl_pct: float       # stop distance as pct of price
    tp_pct: float       # take profit distance as pct of price
    rr: float           # reward/risk ratio
    tq_grade: str = ""  # trade quality grade (computed later)
    tq_score: float = 0.0


def _generate_mr_signals(df: pd.DataFrame) -> list[RawSignal]:
    """Generate POSEIDON/HYDRA/NAUTILUS MR signals from indicator extremes.

    Each engine scans independently with its own cooldown tracker.
    POSEIDON: BB %B + RSI confluence (primary MR)
    HYDRA: RSI extreme only (aggressive MR)
    NAUTILUS: BB + RSI + volume confirmation (conservative MR)
    """
    signals: list[RawSignal] = []
    last_idx_by_engine = {"POSEIDON": -99, "HYDRA": -99, "NAUTILUS": -99}

    for i in range(60, len(df) - HOLD_CANDLES - 2):
        row = df.iloc[i]
        rsi = float(row["rsi_14"])
        bb = float(row["bb_pct_b"])
        adx = float(row["adx"])
        atr_pct = float(row["atr_pct"])
        atr_pctl = float(row.get("atr_pctl", 0.5))
        adx_rising = bool(row.get("adx_rising_3", False))
        vol_ratio = float(row["vol_ratio"])
        price = float(row["close"])

        if np.isnan(atr_pctl):
            atr_pctl = 0.5

        # ----- POSEIDON: BB + RSI confluence -----
        if i - last_idx_by_engine["POSEIDON"] >= MIN_CANDLE_GAP:
            poseidon_long = bb < BB_LOWER_THRESHOLD and rsi < RSI_OS + 5
            poseidon_short = bb > BB_UPPER_THRESHOLD and rsi > RSI_OB - 5
            if poseidon_long or poseidon_short:
                side = "long" if poseidon_long else "short"
                if side == "long":
                    bb_strength = max(0, (BB_LOWER_THRESHOLD - bb) / BB_LOWER_THRESHOLD)
                    rsi_strength = max(0, (RSI_OS + 5 - rsi) / (RSI_OS + 5))
                else:
                    bb_strength = max(0, (bb - BB_UPPER_THRESHOLD) / (1 - BB_UPPER_THRESHOLD))
                    rsi_strength = max(0, (rsi - RSI_OB + 5) / (100 - RSI_OB + 5))

                conf = 0.55 + 0.15 * bb_strength + 0.10 * rsi_strength
                if vol_ratio >= 1.3:
                    conf += 0.03

                sl_pct = atr_pct * SL_ATR_MULT
                tp_pct = sl_pct * TP_RR_BASE
                rr = tp_pct / max(sl_pct, 1e-9)

                signals.append(RawSignal(
                    idx=i, timestamp=row["timestamp"].to_pydatetime(),
                    side=side, engine="POSEIDON", confidence=min(conf, 0.95),
                    entry_price=price, atr_pct=atr_pct, atr_pctl=atr_pctl,
                    adx=adx, adx_rising_3=adx_rising, rsi=rsi, bb_pct_b=bb,
                    vol_ratio=vol_ratio, sl_pct=sl_pct, tp_pct=tp_pct, rr=rr,
                ))
                last_idx_by_engine["POSEIDON"] = i

        # ----- HYDRA: RSI extreme only (more aggressive) -----
        if i - last_idx_by_engine["HYDRA"] >= MIN_CANDLE_GAP:
            hydra_long = rsi < RSI_OS
            hydra_short = rsi > RSI_OB
            if hydra_long or hydra_short:
                side = "long" if hydra_long else "short"
                conf = 0.55 + 0.10 * abs(rsi - 50) / 50
                sl_pct = atr_pct * SL_ATR_MULT * 0.8  # tighter SL
                tp_pct = sl_pct * TP_RR_BASE
                rr = tp_pct / max(sl_pct, 1e-9)

                signals.append(RawSignal(
                    idx=i, timestamp=row["timestamp"].to_pydatetime(),
                    side=side, engine="HYDRA", confidence=min(conf, 0.85),
                    entry_price=price, atr_pct=atr_pct, atr_pctl=atr_pctl,
                    adx=adx, adx_rising_3=adx_rising, rsi=rsi, bb_pct_b=bb,
                    vol_ratio=vol_ratio, sl_pct=sl_pct, tp_pct=tp_pct, rr=rr,
                ))
                last_idx_by_engine["HYDRA"] = i

        # ----- NAUTILUS: conservative — BB + RSI + volume -----
        if i - last_idx_by_engine["NAUTILUS"] >= MIN_CANDLE_GAP:
            naut_long = bb < 0.12 and rsi < RSI_OS + 3 and vol_ratio >= 1.1
            naut_short = bb > 0.88 and rsi > RSI_OB - 3 and vol_ratio >= 1.1
            if naut_long or naut_short:
                side = "long" if naut_long else "short"
                conf = 0.65 + 0.08 * (vol_ratio - 1.0)
                sl_pct = atr_pct * SL_ATR_MULT * 1.2  # wider SL
                tp_pct = sl_pct * TP_RR_BASE * 1.1
                rr = tp_pct / max(sl_pct, 1e-9)

                signals.append(RawSignal(
                    idx=i, timestamp=row["timestamp"].to_pydatetime(),
                    side=side, engine="NAUTILUS", confidence=min(conf, 0.90),
                    entry_price=price, atr_pct=atr_pct, atr_pctl=atr_pctl,
                    adx=adx, adx_rising_3=adx_rising, rsi=rsi, bb_pct_b=bb,
                    vol_ratio=vol_ratio, sl_pct=sl_pct, tp_pct=tp_pct, rr=rr,
                ))
                last_idx_by_engine["NAUTILUS"] = i

    # Sort by timestamp
    signals.sort(key=lambda s: s.timestamp)
    return signals


# ---------------------------------------------------------------
# Trade Quality Grading (simplified)
# ---------------------------------------------------------------

def _compute_tq_grade(sig: RawSignal) -> tuple[str, float]:
    """Simplified trade quality composite score -> A/B/C/D grade."""
    # Signal quality: RSI extreme distance
    sq = min(1.0, abs(sig.rsi - 50) / 50)

    # Precision: BB extreme distance
    if sig.side == "long":
        prec = min(1.0, max(0, (0.5 - sig.bb_pct_b)) * 2)
    else:
        prec = min(1.0, max(0, (sig.bb_pct_b - 0.5)) * 2)

    # Confluence: how many indicators agree
    confluence = 0.5
    if sig.engine == "NAUTILUS":
        confluence = 0.80  # all 3 aligned
    elif sig.engine == "POSEIDON":
        confluence = 0.70  # BB + RSI
    else:
        confluence = 0.50  # RSI only

    # Volume confirmation
    vol_bonus = min(0.15, max(0, sig.vol_ratio - 1.0) * 0.15)
    confluence += vol_bonus

    # Regime alignment: MR works best when ADX low
    regime_align = max(0, min(1.0, (40 - sig.adx) / 30))

    # RR normalized
    rr_norm = min(1.0, sig.rr / 4.0)

    composite = (
        sq * 0.20
        + prec * 0.15
        + confluence * 0.30
        + regime_align * 0.15
        + min(1.0, sig.confidence) * 0.10
        + rr_norm * 0.10
    )
    composite = max(0.0, min(1.0, composite))

    if composite >= 0.80:
        grade = "A"
    elif composite >= 0.65:
        grade = "B"
    elif composite >= 0.50:
        grade = "C"
    else:
        grade = "D"

    return grade, composite


# ---------------------------------------------------------------
# Gate Filtering
# ---------------------------------------------------------------

@dataclass
class GateRejectInfo:
    reason: str
    signal: RawSignal


def _apply_gates(
    signals: list[RawSignal],
    cfg: RunConfig,
) -> tuple[list[RawSignal], list[GateRejectInfo]]:
    """Apply gate filters per run config. Returns (passed, rejected)."""
    passed: list[RawSignal] = []
    rejected: list[GateRejectInfo] = []

    for sig in signals:
        # Assign TQ grade
        grade, score = _compute_tq_grade(sig)
        sig.tq_grade = grade
        sig.tq_score = score

        # -- MR regime filter (crypto mode: disable MR when ADX high) --
        if cfg.crypto_fee_mode:
            if sig.adx > cfg.mr_max_adx:
                rejected.append(GateRejectInfo(f"regime_adx_{sig.adx:.1f}_gt_{cfg.mr_max_adx}", sig))
                continue
            if sig.atr_pctl > cfg.mr_max_atr_pctl:
                rejected.append(GateRejectInfo(f"regime_atr_pctl_{sig.atr_pctl:.2f}", sig))
                continue

        # -- Standard Gate 5: confidence --
        if sig.confidence < 0.55:
            rejected.append(GateRejectInfo("confidence_below_0.55", sig))
            continue

        # -- Standard Gate 7: reward/risk --
        if sig.rr < 1.5:
            rejected.append(GateRejectInfo(f"rr_{sig.rr:.2f}_below_1.5", sig))
            continue

        # -- Gate 7.5: crypto fee-adjusted expectancy --
        if cfg.crypto_fee_mode:
            taker_fee_pct = cfg.taker_fee_bps / 10_000.0
            sl_pct = max(sig.sl_pct, 1e-9)
            win_prob = max(0.0, min(1.0, sig.confidence))

            fee_adjusted_edge = (
                sig.rr * win_prob
                - (1.0 - win_prob)
                - (2.0 * taker_fee_pct / sl_pct)
            )

            if fee_adjusted_edge <= cfg.min_edge:
                rejected.append(GateRejectInfo(
                    f"fee_edge_negative_{fee_adjusted_edge:.4f}", sig))
                continue

            # Engine-specific overrides for Run C
            _min_rr = cfg.min_rr
            _min_tp = cfg.min_tp_pct
            if sig.engine == "HYDRA":
                _min_rr = max(cfg.min_rr, cfg.hydra_min_rr)
                _min_tp = max(cfg.min_tp_pct, cfg.hydra_min_tp)

            if sig.rr < _min_rr:
                rejected.append(GateRejectInfo(
                    f"crypto_min_rr_{sig.rr:.2f}_lt_{_min_rr}", sig))
                continue

            if sig.tp_pct < _min_tp:
                rejected.append(GateRejectInfo(
                    f"crypto_min_tp_{sig.tp_pct:.4f}_lt_{_min_tp}", sig))
                continue

        # -- Trade Quality gate --
        if cfg.crypto_fee_mode:
            # Crypto: only A/B pass
            if grade not in ("A", "B"):
                rejected.append(GateRejectInfo(
                    f"tq_grade_{grade}_reject_crypto", sig))
                continue
        else:
            # Standard: D rejected, C needs high conf
            if grade == "D":
                rejected.append(GateRejectInfo("tq_grade_D_reject", sig))
                continue
            if grade == "C" and sig.confidence < 0.85:
                rejected.append(GateRejectInfo(
                    f"tq_grade_C_low_conf_{sig.confidence:.2f}", sig))
                continue

        passed.append(sig)

    return passed, rejected


# ---------------------------------------------------------------
# Trade Simulation
# ---------------------------------------------------------------

@dataclass
class TradeResult:
    signal: RawSignal
    exit_price: float
    exit_reason: str
    hold_candles: int
    gross_pnl_pct: float  # before fees
    net_pnl_pct: float    # after fees
    fee_cost_pct: float   # round-trip fee as pct of notional
    size_mult: float = 1.0


@dataclass
class RunResult:
    config: RunConfig
    total_signals: int
    passed_signals: int
    trades: list[TradeResult]
    rejected: list[GateRejectInfo]


def _simulate_trades(
    passed: list[RawSignal],
    df: pd.DataFrame,
    cfg: RunConfig,
) -> list[TradeResult]:
    """Simulate trades with SL/TP/time-stop bar-by-bar evaluation."""
    results: list[TradeResult] = []
    fee_pct = (TAKER_FEE_BPS + SLIPPAGE_BPS) / 10_000.0  # per side

    for sig in passed:
        idx = sig.idx
        entry = sig.entry_price
        side = sig.side

        if side == "long":
            sl_price = entry * (1 - sig.sl_pct)
            tp_price = entry * (1 + sig.tp_pct)
        else:
            sl_price = entry * (1 + sig.sl_pct)
            tp_price = entry * (1 - sig.tp_pct)

        window = df.iloc[idx + 1: idx + 1 + HOLD_CANDLES + 2]
        if len(window) < 2:
            continue

        # Bar-by-bar with SL + TP + time-stop
        exit_price = entry
        exit_reason = "time_exit"
        hold_candles = 0

        for j, (_, row) in enumerate(window.iterrows()):
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            hold_candles = j + 1

            # SL check (conservative: SL wins over TP on same candle)
            sl_hit = (low <= sl_price) if side == "long" else (high >= sl_price)
            tp_hit = (high >= tp_price) if side == "long" else (low <= tp_price)

            if sl_hit:
                exit_price = sl_price
                exit_reason = "stop_loss"
                break
            if tp_hit:
                exit_price = tp_price
                exit_reason = "take_profit"
                break
            if hold_candles >= HOLD_CANDLES:
                exit_price = close
                exit_reason = "time_stop"
                break

        if side == "long":
            gross = (exit_price - entry) / entry * LEVERAGE
        else:
            gross = (entry - exit_price) / entry * LEVERAGE

        round_trip_fee = 2 * fee_pct * LEVERAGE
        net = gross - round_trip_fee

        # Size multiplier for crypto fee mode
        size_mult = 1.0
        if cfg.crypto_fee_mode:
            if sig.tq_grade == "A":
                size_mult = cfg.grade_a_size_mult
            elif sig.tq_grade == "B":
                size_mult = cfg.grade_b_size_mult

        results.append(TradeResult(
            signal=sig,
            exit_price=exit_price,
            exit_reason=exit_reason,
            hold_candles=hold_candles,
            gross_pnl_pct=gross,
            net_pnl_pct=net,
            fee_cost_pct=round_trip_fee,
            size_mult=size_mult,
        ))

    return results


# ---------------------------------------------------------------
# Metrics Computation
# ---------------------------------------------------------------

@dataclass
class Metrics:
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    net_pnl_pct: float = 0.0
    gross_pnl_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_rr: float = 0.0
    avg_tp_pct: float = 0.0
    avg_sl_pct: float = 0.0
    avg_hold_candles: float = 0.0
    avg_hold_minutes: float = 0.0
    avg_fee_cost: float = 0.0
    gross_expectancy: float = 0.0
    net_expectancy: float = 0.0
    exit_reasons: dict = field(default_factory=dict)
    engine_breakdown: dict = field(default_factory=dict)


def _compute_metrics(trades: list[TradeResult]) -> Metrics:
    if not trades:
        return Metrics()

    wins = [t for t in trades if t.net_pnl_pct > 0]
    losses = [t for t in trades if t.net_pnl_pct <= 0]
    wr = len(wins) / len(trades)

    # Size-weighted PnL
    total_net = sum(t.net_pnl_pct * t.size_mult for t in trades)
    total_gross = sum(t.gross_pnl_pct * t.size_mult for t in trades)

    gross_profit = sum(t.net_pnl_pct * t.size_mult for t in wins)
    gross_loss = abs(sum(t.net_pnl_pct * t.size_mult for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for t in trades:
        equity *= (1 + t.net_pnl_pct * t.size_mult)
        peak = max(peak, equity)
        dd = (equity / peak) - 1.0
        max_dd = min(max_dd, dd)

    # Averages
    avg_rr = statistics.mean([t.signal.rr for t in trades])
    avg_tp = statistics.mean([t.signal.tp_pct for t in trades])
    avg_sl = statistics.mean([t.signal.sl_pct for t in trades])
    avg_hold = statistics.mean([t.hold_candles for t in trades])
    avg_fee = statistics.mean([t.fee_cost_pct for t in trades])

    gross_exp = statistics.mean([t.gross_pnl_pct for t in trades])
    net_exp = statistics.mean([t.net_pnl_pct for t in trades])

    # Exit reasons
    exit_reasons: dict[str, int] = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    # Engine breakdown
    by_engine: dict[str, list[TradeResult]] = {}
    for t in trades:
        by_engine.setdefault(t.signal.engine, []).append(t)

    engine_bd: dict[str, dict] = {}
    for eng, eng_trades in sorted(by_engine.items()):
        e_wins = [t for t in eng_trades if t.net_pnl_pct > 0]
        e_losses = [t for t in eng_trades if t.net_pnl_pct <= 0]
        e_gp = sum(t.net_pnl_pct * t.size_mult for t in e_wins)
        e_gl = abs(sum(t.net_pnl_pct * t.size_mult for t in e_losses))
        e_pf = e_gp / e_gl if e_gl > 0 else float("inf")
        e_net = sum(t.net_pnl_pct * t.size_mult for t in eng_trades)
        e_rr = statistics.mean([t.signal.rr for t in eng_trades])

        engine_bd[eng] = {
            "trades": len(eng_trades),
            "pf": round(e_pf, 3),
            "net_pnl": round(e_net * 100, 2),
            "avg_rr": round(e_rr, 2),
            "wr": round(len(e_wins) / len(eng_trades) * 100, 1) if eng_trades else 0,
        }

    return Metrics(
        total_trades=len(trades),
        win_rate=round(wr * 100, 1),
        profit_factor=round(pf, 3),
        net_pnl_pct=round(total_net * 100, 2),
        gross_pnl_pct=round(total_gross * 100, 2),
        max_drawdown_pct=round(max_dd * 100, 2),
        avg_rr=round(avg_rr, 2),
        avg_tp_pct=round(avg_tp * 100, 3),
        avg_sl_pct=round(avg_sl * 100, 3),
        avg_hold_candles=round(avg_hold, 1),
        avg_hold_minutes=round(avg_hold * 15, 0),
        avg_fee_cost=round(avg_fee * 10000, 2),
        gross_expectancy=round(gross_exp * 10000, 2),
        net_expectancy=round(net_exp * 10000, 2),
        exit_reasons=exit_reasons,
        engine_breakdown=engine_bd,
    )


# ---------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------

def _gate_reject_summary(rejected: list[GateRejectInfo]) -> dict[str, int]:
    """Count rejects by reason category."""
    cats: dict[str, int] = {}
    for r in rejected:
        reason = r.reason
        if "fee_edge" in reason:
            key = "edge<=0"
        elif "min_rr" in reason:
            key = "min_rr"
        elif "min_tp" in reason:
            key = "min_tp"
        elif "tq_grade" in reason:
            key = "grade_rejected"
        elif "regime_adx" in reason:
            key = "regime_adx_high"
        elif "regime_atr" in reason:
            key = "regime_atr_high"
        elif "confidence" in reason:
            key = "confidence_low"
        elif "rr_" in reason:
            key = "base_rr_low"
        else:
            key = reason
        cats[key] = cats.get(key, 0) + 1
    return cats


def _generate_report(
    runs: list[RunResult],
    total_raw_signals: int,
) -> str:
    """Generate comparative markdown report."""
    lines: list[str] = []
    L = lines.append

    L("# ARGUS v2.5 - Crypto Fee Mode Validation Report")
    L("")
    L(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    L(f"Dataset: {SYMBOL} {TF} | {MONTHS[0]} to {MONTHS[-1]}")
    L(f"Leverage: {LEVERAGE}x | Fee: {TAKER_FEE_BPS} bps/side + {SLIPPAGE_BPS} bps slippage")
    L(f"Total raw MR signals generated: {total_raw_signals}")
    L("")

    # Config diff
    L("## Config Diff")
    L("")
    L("| Parameter | A) Baseline | B) Fee-Aware | C) HYDRA Strict |")
    L("|---|---|---|---|")
    L(f"| crypto_fee_mode | False | True | True |")
    L(f"| min_rr | 1.5 | 2.0 | 2.0 (HYDRA: 2.2) |")
    L(f"| min_tp_pct | 0.1% | 1.0% | 1.0% (HYDRA: 1.2%) |")
    L(f"| min_edge | OFF | >=0 | >=0 |")
    L(f"| tq_min_grade | C (w/ conf) | B | B |")
    L(f"| size_boost A/B | 1.0/1.0 | 1.25/1.10 | 1.25/1.10 |")
    L(f"| mr_max_adx | OFF | {runs[1].config.mr_max_adx} | {runs[2].config.mr_max_adx} |")
    L(f"| mr_max_atr_pctl | OFF | {runs[1].config.mr_max_atr_pctl} | {runs[2].config.mr_max_atr_pctl} |")
    L("")

    # TABLE 1: Global Metrics
    metrics_list = [_compute_metrics(r.trades) for r in runs]

    L("## TABLE 1 -- Global Metrics")
    L("")
    L("| Run | Trades | PF | Net PnL % | MaxDD % | Avg RR | Avg Hold (min) | WR % |")
    L("|---|---|---|---|---|---|---|---|")
    for run, m in zip(runs, metrics_list):
        L(f"| {run.config.label} | {m.total_trades} | {m.profit_factor} | "
          f"{m.net_pnl_pct:+.2f}% | {m.max_drawdown_pct:.2f}% | "
          f"{m.avg_rr} | {m.avg_hold_minutes:.0f} | {m.win_rate}% |")
    L("")

    # TABLE 2: Engine Breakdown
    L("## TABLE 2 -- Engine Breakdown")
    L("")
    L("| Run | Engine | Trades | PF | Net PnL % | Avg RR | WR % |")
    L("|---|---|---|---|---|---|---|")
    for run, m in zip(runs, metrics_list):
        for eng, ed in m.engine_breakdown.items():
            L(f"| {run.config.name} | {eng} | {ed['trades']} | {ed['pf']} | "
              f"{ed['net_pnl']:+.2f}% | {ed['avg_rr']} | {ed['wr']}% |")
    L("")

    # TABLE 3: Gate Impact
    L("## TABLE 3 -- Gate Impact (Fee Mode Runs)")
    L("")
    L("| Reason | B) Count | B) % | C) Count | C) % |")
    L("|---|---|---|---|---|")

    reject_b = _gate_reject_summary(runs[1].rejected) if len(runs) > 1 else {}
    reject_c = _gate_reject_summary(runs[2].rejected) if len(runs) > 2 else {}
    all_reasons = sorted(set(list(reject_b.keys()) + list(reject_c.keys())))
    total_b = runs[1].total_signals if len(runs) > 1 else 1
    total_c = runs[2].total_signals if len(runs) > 2 else 1

    for reason in all_reasons:
        b_cnt = reject_b.get(reason, 0)
        c_cnt = reject_c.get(reason, 0)
        b_pct = b_cnt / total_b * 100
        c_pct = c_cnt / total_c * 100
        L(f"| {reason} | {b_cnt} | {b_pct:.1f}% | {c_cnt} | {c_pct:.1f}% |")
    L("")

    # TABLE 4: Fee Efficiency
    L("## TABLE 4 -- Fee Efficiency")
    L("")
    L("| Run | Gross Expect (bps) | Fee Cost/Trade (bps) | Net Expect (bps) |")
    L("|---|---|---|---|")
    for run, m in zip(runs, metrics_list):
        L(f"| {run.config.label} | {m.gross_expectancy:+.2f} | {m.avg_fee_cost:.2f} | {m.net_expectancy:+.2f} |")
    L("")

    # Exit Reason Distribution
    L("## Exit Reason Distribution")
    L("")
    L("| Run | SL | TP | Time Stop | Time Exit | Other |")
    L("|---|---|---|---|---|---|")
    for run, m in zip(runs, metrics_list):
        er = m.exit_reasons
        sl = er.get("stop_loss", 0)
        tp = er.get("take_profit", 0)
        ts_ = er.get("time_stop", 0)
        te_ = er.get("time_exit", 0)
        known = {"stop_loss", "take_profit", "time_stop", "time_exit"}
        other = sum(v for k, v in er.items() if k not in known)
        L(f"| {run.config.name} | {sl} | {tp} | {ts_} | {te_} | {other} |")
    L("")

    # Signal Pass Rates
    L("## Signal Filter Rates")
    L("")
    L("| Run | Raw Signals | Passed | Pass Rate |")
    L("|---|---|---|---|")
    for run in runs:
        rate = run.passed_signals / run.total_signals * 100 if run.total_signals > 0 else 0
        L(f"| {run.config.name} | {run.total_signals} | {run.passed_signals} | {rate:.1f}% |")
    L("")

    # TQ Grade Distribution of executed trades
    L("## Trade Quality Grade Distribution (Executed)")
    L("")
    L("| Run | Grade A | Grade B | Grade C | Grade D |")
    L("|---|---|---|---|---|")
    for run in runs:
        grades = {"A": 0, "B": 0, "C": 0, "D": 0}
        for t in run.trades:
            grades[t.signal.tq_grade] = grades.get(t.signal.tq_grade, 0) + 1
        L(f"| {run.config.name} | {grades['A']} | {grades['B']} | {grades['C']} | {grades['D']} |")
    L("")

    # CONCLUSION
    L("## Conclusion")
    L("")

    if len(metrics_list) >= 2:
        m_a, m_b = metrics_list[0], metrics_list[1]

        if m_b.profit_factor > m_a.profit_factor and m_b.net_pnl_pct > m_a.net_pnl_pct:
            verdict = "FEE MODE SUCCESSFUL"
            emoji_line = "Fee Mode improves both PF and Net PnL."
        elif m_b.total_trades < m_a.total_trades and m_b.profit_factor > m_a.profit_factor:
            verdict = "FEE MODE IMPROVES QUALITY"
            emoji_line = "Trade count dropped but PF improved -> higher quality filtering."
        elif m_b.total_trades < m_a.total_trades and m_b.net_expectancy > m_a.net_expectancy:
            verdict = "FEE MODE IMPROVES QUALITY"
            emoji_line = "Trade count dropped but per-trade expectancy improved."
        else:
            verdict = "FEE MODE OVER-RESTRICTIVE -- THRESHOLD TUNING NEEDED"
            emoji_line = "Fee mode did not improve performance. Consider relaxing thresholds."

        L(f"**Verdict: {verdict}**")
        L("")
        L(f"{emoji_line}")
        L("")
        L(f"- Baseline: {m_a.total_trades} trades, PF={m_a.profit_factor}, Net={m_a.net_pnl_pct:+.2f}%")
        L(f"- Fee Mode: {m_b.total_trades} trades, PF={m_b.profit_factor}, Net={m_b.net_pnl_pct:+.2f}%")
        L(f"- Trade reduction: {m_a.total_trades - m_b.total_trades} trades ({(1 - m_b.total_trades/max(m_a.total_trades,1))*100:.0f}%)")
        L(f"- Net expectancy delta: {m_b.net_expectancy - m_a.net_expectancy:+.2f} bps/trade")

        if len(metrics_list) >= 3:
            m_c = metrics_list[2]
            L("")
            L(f"- HYDRA Strict: {m_c.total_trades} trades, PF={m_c.profit_factor}, Net={m_c.net_pnl_pct:+.2f}%")
            hydra_b = m_b.engine_breakdown.get("HYDRA", {})
            hydra_c = m_c.engine_breakdown.get("HYDRA", {})
            if hydra_b and hydra_c:
                L(f"- HYDRA trades: B={hydra_b.get('trades',0)} -> C={hydra_c.get('trades',0)}")
                L(f"- HYDRA PF: B={hydra_b.get('pf',0)} -> C={hydra_c.get('pf',0)}")

        L("")
        L("### Next Tuning Vector")
        L("")
        if m_b.total_trades < 20:
            L("- Relax min_rr from 2.0 to 1.8 to allow more trades")
            L("- Consider lowering mr_max_adx from 22 to 25")
        elif m_b.profit_factor < 1.0:
            L("- Tighten min_edge threshold above 0")
            L("- Consider raising min_rr to 2.2 for all engines")
        else:
            L("- Current thresholds look reasonable")
            L("- Monitor HYDRA vs NAUTILUS PF split for engine-specific tuning")
            L("- Consider testing on ETHUSDT for cross-asset validation")

    return "\n".join(lines)


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  ARGUS v2.5 -- CRYPTO FEE MODE VALIDATION")
    print("=" * 60)

    print(f"\nLoading {SYMBOL} {TF} data...")
    df = _load_15m_data()
    print(f"  -> {len(df)} candles ({df.iloc[0].timestamp} to {df.iloc[-1].timestamp})")

    print("\nGenerating MR signals...")
    all_signals = _generate_mr_signals(df)
    print(f"  -> {len(all_signals)} raw signals generated")

    by_engine: dict[str, int] = {}
    for s in all_signals:
        by_engine[s.engine] = by_engine.get(s.engine, 0) + 1
    for eng, cnt in sorted(by_engine.items()):
        print(f"     {eng}: {cnt}")

    runs_cfg = [RUN_A, RUN_B, RUN_C]
    results: list[RunResult] = []

    for cfg in runs_cfg:
        print(f"\n{'='*50}")
        print(f"  RUN: {cfg.label}")
        print(f"{'='*50}")

        passed, rejected = _apply_gates(all_signals, cfg)
        print(f"  Signals passed gates: {len(passed)} / {len(all_signals)} ({len(passed)/len(all_signals)*100:.1f}%)")

        if rejected:
            reject_cats = _gate_reject_summary(rejected)
            for reason, cnt in sorted(reject_cats.items(), key=lambda x: -x[1]):
                print(f"    Rejected [{reason}]: {cnt}")

        trades = _simulate_trades(passed, df, cfg)
        print(f"  Simulated trades: {len(trades)}")

        m = _compute_metrics(trades)
        print(f"  PF={m.profit_factor} | Net={m.net_pnl_pct:+.2f}% | WR={m.win_rate}% | MaxDD={m.max_drawdown_pct:.2f}%")
        print(f"  Gross expect={m.gross_expectancy:+.2f}bps | Net expect={m.net_expectancy:+.2f}bps")

        for eng, ed in m.engine_breakdown.items():
            print(f"    {eng}: {ed['trades']}t PF={ed['pf']} Net={ed['net_pnl']:+.2f}%")

        results.append(RunResult(
            config=cfg,
            total_signals=len(all_signals),
            passed_signals=len(passed),
            trades=trades,
            rejected=rejected,
        ))

    # Generate report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = _generate_report(results, len(all_signals))
    report_path = OUTPUT_DIR / "FEE_VALIDATION_SUMMARY.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved: {report_path}")

    print("\n" + "=" * 60)
    print("  VALIDATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()

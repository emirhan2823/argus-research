"""Lightweight TITAN bottleneck diagnostic.

Loads BTC/ETH 1h candle data, computes features via FeatureBuilder,
feeds to TitanEngine, and reports per-condition rejection counts.

Bypasses full ArgusPipeline for speed.

Usage:
    python Scripts/titan_bottleneck_diag.py
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.constants import REGIME_TRENDING
from src.core.types import FeatureVector, RegimeState
from src.engines.titan.engine import TitanEngine


def load_candles(symbol: str, year: int = 2024) -> pd.DataFrame:
    """Load 1h candles from replay parquets."""
    path = Path(f"data/binance/{symbol}/1h/{year}.parquet")
    if not path.exists():
        raise FileNotFoundError(f"No parquet at {path}")
    df = pd.read_parquet(path)
    # Ensure standard column names
    cols = df.columns.str.lower()
    df.columns = cols
    # Rename if needed
    for old, new in [("open_time", "timestamp"), ("quote_volume", "quote_vol")]:
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute indicators TITAN needs from OHLCV."""
    c = df["close"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    v = df["volume"].values.astype(float)

    n = len(c)

    # --- ADX (14) ---
    adx = np.full(n, np.nan)
    if n > 15:
        up_move = np.diff(h)
        down_move = -np.diff(l)
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
        period = 14
        alpha = 1.0 / period
        atr_s = np.zeros(n - 1)
        plus_s = np.zeros(n - 1)
        minus_s = np.zeros(n - 1)
        atr_s[0] = tr[0]
        plus_s[0] = plus_dm[0]
        minus_s[0] = minus_dm[0]
        for i in range(1, n - 1):
            atr_s[i] = atr_s[i - 1] * (1 - alpha) + tr[i] * alpha
            plus_s[i] = plus_s[i - 1] * (1 - alpha) + plus_dm[i] * alpha
            minus_s[i] = minus_s[i - 1] * (1 - alpha) + minus_dm[i] * alpha
        plus_di = np.where(atr_s > 0, 100 * plus_s / atr_s, 0)
        minus_di = np.where(atr_s > 0, 100 * minus_s / atr_s, 0)
        di_sum = plus_di + minus_di
        dx = np.where(di_sum > 0, 100 * np.abs(plus_di - minus_di) / di_sum, 0)
        adx_vals = np.zeros(n - 1)
        adx_vals[period - 1] = np.mean(dx[:period]) if period <= len(dx) else 0
        for i in range(period, n - 1):
            adx_vals[i] = adx_vals[i - 1] * (1 - alpha) + dx[i] * alpha
        adx[1:] = adx_vals

    # --- EMA 21 vs 55 ---
    ema21 = _ema(c, 21)
    ema55 = _ema(c, 55)
    ema_diff = ema21 - ema55

    # --- MA200 ---
    ma200 = np.full(n, np.nan)
    if n >= 200:
        for i in range(199, n):
            ma200[i] = np.mean(c[i - 199 : i + 1])
    price_vs_ma200 = np.where(~np.isnan(ma200), c - ma200, 0)

    # --- RSI 14 ---
    rsi = np.full(n, 50.0)
    if n > 15:
        delta = np.diff(c)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = np.zeros(n - 1)
        avg_loss = np.zeros(n - 1)
        avg_gain[13] = np.mean(gain[:14])
        avg_loss[13] = np.mean(loss[:14])
        for i in range(14, n - 1):
            avg_gain[i] = (avg_gain[i - 1] * 13 + gain[i]) / 14
            avg_loss[i] = (avg_loss[i - 1] * 13 + loss[i]) / 14
        rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100)
        rsi_vals = 100 - 100 / (1 + rs)
        rsi[1:] = rsi_vals

    # --- ATR 14 ---
    atr = np.full(n, np.nan)
    if n > 1:
        tr_arr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
        atr_vals = np.zeros(n - 1)
        atr_vals[0] = tr_arr[0]
        for i in range(1, n - 1):
            atr_vals[i] = atr_vals[i - 1] * (13 / 14) + tr_arr[i] * (1 / 14)
        atr[1:] = atr_vals

    # --- ATR percentile (100-bar rolling) ---
    atr_pctl = np.full(n, np.nan)
    window = 100
    for i in range(window, n):
        subset = atr[i - window + 1 : i + 1]
        valid = subset[~np.isnan(subset)]
        if len(valid) > 1:
            atr_pctl[i] = np.sum(valid < atr[i]) / len(valid)

    # --- Volume ratio (current / 20-period SMA) ---
    vol_ratio = np.full(n, 1.0)
    if n >= 20:
        vol_sma = np.convolve(v, np.ones(20) / 20, mode="full")[:n]
        vol_sma[:19] = np.nan
        valid_mask = vol_sma > 0
        vol_ratio[valid_mask] = v[valid_mask] / vol_sma[valid_mask]

    # --- BB %B ---
    bb_pct_b = np.full(n, 0.5)
    if n >= 20:
        sma20 = np.convolve(c, np.ones(20) / 20, mode="full")[:n]
        sma20[:19] = np.nan
        for i in range(19, n):
            std = np.std(c[i - 19 : i + 1])
            if std > 0:
                upper = sma20[i] + 2 * std
                lower = sma20[i] - 2 * std
                bb_pct_b[i] = (c[i] - lower) / (upper - lower)

    df = df.copy()
    df["adx_14"] = adx
    df["ema_21_vs_55"] = ema_diff
    df["price_vs_ma200"] = price_vs_ma200
    df["rsi_14"] = rsi
    df["atr_14"] = atr
    df["atr_pctl"] = atr_pctl
    df["volume_ratio"] = vol_ratio
    df["bb_pct_b"] = bb_pct_b
    return df


def _ema(arr, span):
    result = np.full_like(arr, np.nan, dtype=float)
    alpha = 2 / (span + 1)
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = result[i - 1] * (1 - alpha) + arr[i] * alpha
    return result


def run_diagnostic(symbol: str, year: int = 2024, vol_threshold: float = 0.8, adx_rising_bars: int = 3):
    """Run TITAN diagnostic for a single symbol."""
    print(f"\n{'=' * 70}")
    print(f"  TITAN BOTTLENECK DIAGNOSTIC: {symbol} ({year})")
    print(f"  min_volume_expansion = {vol_threshold}, adx_rising_bars = {adx_rising_bars}")
    print(f"{'=' * 70}")

    df = load_candles(symbol, year)
    df = compute_indicators(df)
    print(f"  Loaded {len(df)} candles")

    # Show indicator distributions
    valid_adx = df["adx_14"].dropna()
    valid_atr_pctl = df["atr_pctl"].dropna()
    valid_vol = df["volume_ratio"].dropna()
    print(f"\n  INDICATOR DISTRIBUTIONS:")
    print(f"    ADX:      min={valid_adx.min():.1f}  mean={valid_adx.mean():.1f}  max={valid_adx.max():.1f}")
    print(f"    ATR pctl: min={valid_atr_pctl.min():.3f}  mean={valid_atr_pctl.mean():.3f}  max={valid_atr_pctl.max():.3f}")
    print(f"    Vol ratio:min={valid_vol.min():.2f}  mean={valid_vol.mean():.2f}  max={valid_vol.max():.2f}")

    # Create TitanEngine
    titan = TitanEngine(min_volume_expansion=vol_threshold, adx_rising_bars=adx_rising_bars)

    # Simulate regime (always TRENDING for diagnostic)
    regime = RegimeState(
        regime=REGIME_TRENDING,
        confidence=0.8,
        stability=0.7,
        direction=1,
        candles_in_regime=100,
        rule_regime=REGIME_TRENDING,
        ml_regime=REGIME_TRENDING,
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    # Walk through candles (need 200+ warmup for MA200)
    warmup = 250
    signals_found = 0
    cycles_run = 0

    for i in range(warmup, len(df)):
        row = df.iloc[i]
        # Skip rows with NaN in critical indicators
        if pd.isna(row["adx_14"]) or pd.isna(row["atr_14"]):
            continue

        # Feed candle history to TITAN
        start_idx = max(0, i - 499)
        hist_slice = df.iloc[start_idx : i + 1]
        titan.feed_candles(
            symbol=symbol,
            highs=list(hist_slice["high"].astype(float)),
            lows=list(hist_slice["low"].astype(float)),
            closes=list(hist_slice["close"].astype(float)),
        )

        # Build minimal FeatureVector
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
        fv = FeatureVector(
            timestamp=ts,
            symbol=symbol,
            asset_class="crypto",
            atr_14=float(row["atr_14"]),
            atr_14_pct=float(row["atr_14"] / row["close"]) if row["close"] > 0 else 0.0,
            atr_ratio_5_20=1.0,
            realized_vol_20d=0.01,
            parkinson_vol=0.01,
            bb_width=0.02,
            adx_14=float(row["adx_14"]),
            price_vs_ma200=float(row["price_vs_ma200"]),
            ema_21_vs_55=float(row["ema_21_vs_55"]),
            lr_slope_20=0.0,
            supertrend_dir=1 if row["ema_21_vs_55"] > 0 else -1,
            aroon_osc=0.0,
            rsi_14=float(row["rsi_14"]),
            bb_pct_b=float(row["bb_pct_b"]),
            roc_10=0.0,
            willr_14=-50.0,
            cci_20=0.0,
            volume_ratio=float(row["volume_ratio"]),
            obv_slope_10=0.0,
            vwap_dev_pct=0.0,
            cmf_20=0.0,
            volume_delta=0.0,
            atr_pctl=float(row["atr_pctl"]) if not pd.isna(row["atr_pctl"]) else None,
            spread_pct=0.001,
            return_autocorr_20=0.0,
            hurst_exponent=0.5,
            entropy_50=1.0,
            frac_diff_price=0.0,
        )

        sig = titan.generate_signal(regime=regime, features=fv)
        if sig is not None:
            signals_found += 1
        cycles_run += 1

    # Report
    d = titan._diag
    total_calls = d["cont_long_calls"] + d["cont_short_calls"]

    print(f"\n  CYCLES RUN: {cycles_run}")
    print(f"  Regime rejects:   {d['regime_reject']}  (should be 0, we force TRENDING)")
    print(f"  History rejects:  {d['history_reject']}")

    print(f"\n  --- CONTINUATION LONG ({d['cont_long_calls']} calls) ---")
    stages_long = ["adx", "adx_rising", "ema", "ma200", "structure", "atr_pctl", "volume"]
    for s in stages_long:
        cnt = d[f"cont_long_fail_{s}"]
        pct = cnt / d["cont_long_calls"] * 100 if d["cont_long_calls"] > 0 else 0
        bar = "#" * int(pct / 2)
        print(f"    fail_{s:15s}: {cnt:>6}  ({pct:5.1f}%)  {bar}")
    print(f"    PASS:              {d['cont_long_pass']:>6}")

    print(f"\n  --- CONTINUATION SHORT ({d['cont_short_calls']} calls) ---")
    for s in stages_long:
        cnt = d[f"cont_short_fail_{s}"]
        pct = cnt / d["cont_short_calls"] * 100 if d["cont_short_calls"] > 0 else 0
        bar = "#" * int(pct / 2)
        print(f"    fail_{s:15s}: {cnt:>6}  ({pct:5.1f}%)  {bar}")
    print(f"    PASS:              {d['cont_short_pass']:>6}")

    print(f"\n  --- PULLBACK + SIGNAL ---")
    print(f"    Pullback fail:     {d['pullback_fail']:>6}")
    print(f"    Pullback pass:     {d['pullback_pass']:>6}")
    print(f"    SIGNAL PRODUCED:   {d['signal_produced']:>6}")

    # Cumulative funnel
    print(f"\n  --- FUNNEL SUMMARY (LONG) ---")
    remaining = d["cont_long_calls"]
    for s in stages_long:
        fail = d[f"cont_long_fail_{s}"]
        remaining -= fail
        print(f"    After {s:15s}: {remaining:>6} remain  (lost {fail})")

    print(f"\n  --- FUNNEL SUMMARY (SHORT) ---")
    remaining = d["cont_short_calls"]
    for s in stages_long:
        fail = d[f"cont_short_fail_{s}"]
        remaining -= fail
        print(f"    After {s:15s}: {remaining:>6} remain  (lost {fail})")

    return d


def main():
    print("TITAN BOTTLENECK DIAGNOSTIC")
    print("All cycles forced to TRENDING regime (bypass regime classifier)")
    print("This isolates TITAN's internal condition chain\n")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--adx-rising", type=int, default=3, help="adx_rising_bars value")
    parser.add_argument("--vol", type=float, default=0.8, help="min_volume_expansion value")
    args = parser.parse_args()

    results = {}
    for sym in ["BTCUSDT", "ETHUSDT"]:
        try:
            results[sym] = run_diagnostic(sym, 2024, vol_threshold=args.vol, adx_rising_bars=args.adx_rising)
        except Exception as e:
            print(f"\n  ERROR for {sym}: {e}")
            import traceback
            traceback.print_exc()

    # Combined summary
    if results:
        print(f"\n{'=' * 70}")
        print(f"  COMBINED BOTTLENECK RANKING")
        print(f"{'=' * 70}")
        stages = ["adx", "adx_rising", "ema", "ma200", "structure", "atr_pctl", "volume"]
        for bias_label, prefix in [("LONG", "cont_long"), ("SHORT", "cont_short")]:
            print(f"\n  {bias_label}:")
            totals = {}
            total_calls = sum(r[f"{prefix}_calls"] for r in results.values())
            for s in stages:
                key = f"{prefix}_fail_{s}"
                total = sum(r[key] for r in results.values())
                totals[s] = total
            # Sort by count descending
            ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
            for rank, (stage, count) in enumerate(ranked, 1):
                pct = count / total_calls * 100 if total_calls > 0 else 0
                bar = "#" * int(pct / 2)
                print(f"    #{rank} {stage:15s}: {count:>6}  ({pct:5.1f}%)  {bar}")
            total_pass = sum(r[f"{prefix}_pass"] for r in results.values())
            print(f"    PASS:              {total_pass:>6}")


if __name__ == "__main__":
    main()

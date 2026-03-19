"""TITAN Rejection Waterfall Diagnostic.

Runs TITAN engine directly on historical data (bypassing pipeline orchestrator)
to count exactly where signals get rejected at each stage of the funnel.

Usage:
    python Scripts/titan_rejection_diagnostic.py --start 2022-05-01 --end 2022-07-31
    python Scripts/titan_rejection_diagnostic.py --start 2024-01-01 --end 2024-12-31
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.replay_loader import ReplayLoader
from src.engines.titan.engine import TitanEngine
from src.core.types import FeatureVector, RegimeState
from src.regime.rule_based import RuleBasedInput, RuleBasedRegimeClassifier


def _build_features_from_ohlcv(df: pd.DataFrame, idx: int) -> dict | None:
    """Build a minimal feature dict from OHLCV at position idx."""
    if idx < 200:
        return None

    window = df.iloc[max(0, idx - 260):idx + 1]
    if len(window) < 200:
        return None

    closes = window["close"].values
    highs = window["high"].values
    lows = window["low"].values
    volumes = window["volume"].values

    # Basic indicators
    close = closes[-1]

    # EMA
    ema_21 = pd.Series(closes).ewm(span=21, adjust=False).mean().iloc[-1]
    ema_55 = pd.Series(closes).ewm(span=55, adjust=False).mean().iloc[-1]
    ma_200 = pd.Series(closes).rolling(200).mean().iloc[-1]

    ema_21_vs_55 = (ema_21 - ema_55) / ema_55 if ema_55 > 0 else 0
    price_vs_ma200 = (close - ma_200) / ma_200 if ma_200 > 0 else 0

    # ADX (simplified)
    tr_series = []
    for i in range(1, len(closes)):
        h = highs[i]
        l = lows[i]
        pc = closes[i - 1]
        tr_series.append(max(h - l, abs(h - pc), abs(l - pc)))

    if len(tr_series) < 14:
        return None

    atr_14 = pd.Series(tr_series).rolling(14).mean().iloc[-1]
    atr_pct = atr_14 / close if close > 0 else 0

    # ADX calculation (Wilder's smoothing)
    plus_dm = []
    minus_dm = []
    for i in range(1, len(highs)):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)

    if len(plus_dm) < 14:
        return None

    tr_s = pd.Series(tr_series)
    pdm_s = pd.Series(plus_dm)
    mdm_s = pd.Series(minus_dm)

    atr_smooth = tr_s.ewm(span=14, adjust=False).mean()
    pdm_smooth = pdm_s.ewm(span=14, adjust=False).mean()
    mdm_smooth = mdm_s.ewm(span=14, adjust=False).mean()

    pdi = 100 * pdm_smooth / atr_smooth.replace(0, 1e-10)
    mdi = 100 * mdm_smooth / atr_smooth.replace(0, 1e-10)
    dx = 100 * abs(pdi - mdi) / (pdi + mdi).replace(0, 1e-10)
    adx = dx.ewm(span=14, adjust=False).mean()
    adx_14 = float(adx.iloc[-1])

    # RSI
    deltas = pd.Series(closes).diff()
    gains = deltas.clip(lower=0)
    losses = (-deltas.clip(upper=0))
    avg_gain = gains.ewm(span=14, adjust=False).mean().iloc[-1]
    avg_loss = losses.ewm(span=14, adjust=False).mean().iloc[-1]
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi_14 = 100 - 100 / (1 + rs)

    # Volume ratio
    vol_sma = pd.Series(volumes).rolling(20).mean().iloc[-1]
    vol_ratio = volumes[-1] / vol_sma if vol_sma > 0 else 1.0

    # BB %B
    sma_20 = pd.Series(closes).rolling(20).mean().iloc[-1]
    std_20 = pd.Series(closes).rolling(20).std().iloc[-1]
    bb_upper = sma_20 + 2 * std_20
    bb_lower = sma_20 - 2 * std_20
    bb_pct_b = (close - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

    # ATR percentile
    atr_series = pd.Series(tr_series).rolling(14).mean()
    atr_pctl = float((atr_series < atr_14).sum() / len(atr_series))

    # Hurst (simplified)
    log_returns = pd.Series(closes).pct_change().dropna()
    if len(log_returns) > 20:
        rs_vals = []
        for n in [20, 50, 100]:
            if len(log_returns) >= n:
                chunk = log_returns.iloc[-n:]
                mean_r = chunk.mean()
                dev = chunk.cumsum() - chunk.cumsum().mean()
                r_range = dev.max() - dev.min()
                s = chunk.std()
                if s > 0:
                    rs_vals.append(r_range / s)
        hurst = 0.5  # default
        if len(rs_vals) >= 2:
            import numpy as np
            ns = [20, 50, 100][:len(rs_vals)]
            try:
                coeffs = np.polyfit(np.log(ns), np.log(rs_vals), 1)
                hurst = float(coeffs[0])
            except Exception:
                pass
    else:
        hurst = 0.5

    return {
        "close": close,
        "ema_21": ema_21,
        "ema_55": ema_55,
        "ma_200": ma_200,
        "ema_21_vs_55": ema_21_vs_55,
        "price_vs_ma200": price_vs_ma200,
        "adx_14": adx_14,
        "rsi_14": rsi_14,
        "atr_14": atr_14,
        "atr_pct": atr_pct,
        "atr_pctl": atr_pctl,
        "volume_ratio": vol_ratio,
        "bb_pct_b": bb_pct_b,
        "hurst": hurst,
        "highs": list(highs[-500:]),
        "lows": list(lows[-500:]),
        "closes": list(closes[-500:]),
    }


def _classify_regime(feat: dict) -> str:
    """Simple regime classification matching the rule-based classifier."""
    adx = feat["adx_14"]
    hurst = feat["hurst"]
    atr_ratio = feat.get("atr_pct", 0) / 0.01 if feat.get("atr_pct", 0) > 0 else 0

    if atr_ratio > 1.4:
        return "VOLATILE"
    if adx >= 32 and hurst >= 0.58:
        return "TRENDING"
    if adx < 32 and hurst < 0.50:
        return "RANGING"
    return "RANGING"  # default


def run_diagnostic(
    symbol: str,
    start: str,
    end: str,
    timeframe: str = "1h",
) -> dict:
    """Run TITAN through historical data and collect rejection stats."""
    loader = ReplayLoader(root="data/binance")

    # Load and resample to target timeframe
    df_15m = loader.load_ohlcv(symbol, "15m", start, end)
    if df_15m.empty:
        return {"error": f"No data for {symbol} {start}-{end}"}

    # Resample to 1h
    if timeframe == "1h":
        df_15m = df_15m.set_index("timestamp")
        df = df_15m.resample("1h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum",
        }).dropna().reset_index()
    else:
        df = df_15m

    print(f"  Data: {len(df)} candles ({df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]})")

    # Create TITAN engine
    engine = TitanEngine()

    # Counters
    stats = defaultdict(int)
    stats["total_candles"] = len(df)

    # Stage counters
    regime_counts = defaultdict(int)

    for idx in range(200, len(df)):
        feat = _build_features_from_ohlcv(df, idx)
        if feat is None:
            stats["feature_build_fail"] += 1
            continue

        stats["features_built"] += 1

        regime = _classify_regime(feat)
        regime_counts[regime] += 1

        # Stage 1: Regime gate
        if regime != "TRENDING":
            stats["fail_regime_not_trending"] += 1
            continue

        stats["pass_regime_trending"] += 1

        # Feed candles
        engine.feed_candles(
            symbol=symbol,
            highs=feat["highs"],
            lows=feat["lows"],
            closes=feat["closes"],
        )

        # Reset diag for this call
        before_diag = dict(engine._diag)

        # Create mock FeatureVector-like object
        class MockFV:
            pass

        fv = MockFV()
        fv.symbol = symbol
        fv.asset_class = "crypto"
        fv.adx_14 = feat["adx_14"]
        fv.ema_21_vs_55 = feat["ema_21_vs_55"]
        fv.price_vs_ma200 = feat["price_vs_ma200"]
        fv.atr_14 = feat["atr_14"]
        fv.atr_pctl = feat["atr_pctl"]
        fv.volume_ratio = feat["volume_ratio"]
        fv.bb_pct_b = feat["bb_pct_b"]
        fv.rsi_14 = feat["rsi_14"]
        fv.atr_14_pct = feat["atr_pct"]

        class MockRegime:
            pass

        regime_obj = MockRegime()
        regime_obj.regime = regime

        signal = engine.generate_signal(regime=regime_obj, features=fv)

        # Collect diag diffs
        after_diag = engine._diag
        for key in after_diag:
            diff = after_diag[key] - before_diag.get(key, 0)
            if diff > 0:
                stats[f"diag_{key}"] += diff

        if signal is not None:
            stats["signal_produced"] += 1
            stats[f"signal_{signal.bias}"] += 1
            stats[f"signal_{signal.sub_strategy}"] += 1
            print(f"    SIGNAL at {df.iloc[idx]['timestamp']}: {signal.sub_strategy} {signal.bias} conf={signal.confidence:.3f}")
        else:
            stats["signal_none_after_trending"] += 1

    # Summary
    stats["regime_distribution"] = dict(regime_counts)

    return dict(stats)


def main():
    parser = argparse.ArgumentParser(description="TITAN Rejection Waterfall Diagnostic")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--timeframe", default="1h")
    args = parser.parse_args()

    scenarios = [
        (args.symbol, args.start, args.end),
    ]

    for symbol, start, end in scenarios:
        print(f"\n{'=' * 80}")
        print(f"TITAN REJECTION WATERFALL: {symbol} {start} -> {end}")
        print(f"{'=' * 80}")

        stats = run_diagnostic(symbol, start, end, args.timeframe)

        if "error" in stats:
            print(f"  ERROR: {stats['error']}")
            continue

        total = stats.get("features_built", 0)
        trending = stats.get("pass_regime_trending", 0)
        not_trending = stats.get("fail_regime_not_trending", 0)
        signals = stats.get("signal_produced", 0)

        print(f"\n  REGIME DISTRIBUTION:")
        for regime, count in sorted(stats.get("regime_distribution", {}).items()):
            pct = count / total * 100 if total > 0 else 0
            print(f"    {regime:>12}: {count:>6} ({pct:.1f}%)")

        print(f"\n  FUNNEL:")
        print(f"    Total candles:          {stats.get('total_candles', 0):>6}")
        print(f"    Features built:         {total:>6}")
        print(f"    Regime = TRENDING:      {trending:>6} ({trending / total * 100:.1f}%)" if total > 0 else "")
        print(f"    Regime != TRENDING:     {not_trending:>6} ({not_trending / total * 100:.1f}%)" if total > 0 else "")

        print(f"\n  CONTINUATION FUNNEL (Long):")
        cl = stats.get("diag_cont_long_calls", 0)
        print(f"    Calls:                  {cl:>6}")
        print(f"    Fail ADX < min_adx:     {stats.get('diag_cont_long_fail_adx', 0):>6}")
        print(f"    Fail ADX not rising:    {stats.get('diag_cont_long_fail_adx_rising', 0):>6}")
        print(f"    Fail EMA21 < EMA55:     {stats.get('diag_cont_long_fail_ema', 0):>6}")
        print(f"    Fail Price < MA200:     {stats.get('diag_cont_long_fail_ma200', 0):>6}")
        print(f"    Fail HH/HL structure:   {stats.get('diag_cont_long_fail_structure', 0):>6}")
        print(f"    Fail ATR percentile:    {stats.get('diag_cont_long_fail_atr_pctl', 0):>6}")
        print(f"    Fail Volume:            {stats.get('diag_cont_long_fail_volume', 0):>6}")
        print(f"    PASS:                   {stats.get('diag_cont_long_pass', 0):>6}")

        print(f"\n  CONTINUATION FUNNEL (Short):")
        cs = stats.get("diag_cont_short_calls", 0)
        print(f"    Calls:                  {cs:>6}")
        print(f"    Fail ADX < min_adx:     {stats.get('diag_cont_short_fail_adx', 0):>6}")
        print(f"    Fail ADX not rising:    {stats.get('diag_cont_short_fail_adx_rising', 0):>6}")
        print(f"    Fail EMA21 > EMA55:     {stats.get('diag_cont_short_fail_ema', 0):>6}")
        print(f"    Fail Price > MA200:     {stats.get('diag_cont_short_fail_ma200', 0):>6}")
        print(f"    Fail LL/LH structure:   {stats.get('diag_cont_short_fail_structure', 0):>6}")
        print(f"    Fail ATR percentile:    {stats.get('diag_cont_short_fail_atr_pctl', 0):>6}")
        print(f"    Fail Volume:            {stats.get('diag_cont_short_fail_volume', 0):>6}")
        print(f"    PASS:                   {stats.get('diag_cont_short_pass', 0):>6}")

        print(f"\n  PULLBACK:")
        print(f"    Fail:                   {stats.get('diag_pullback_fail', 0):>6}")
        print(f"    Pass:                   {stats.get('diag_pullback_pass', 0):>6}")

        print(f"\n  RESULT:")
        print(f"    Signals produced:       {signals:>6}")
        print(f"    Signal long:            {stats.get('signal_long', 0):>6}")
        print(f"    Signal short:           {stats.get('signal_short', 0):>6}")


if __name__ == "__main__":
    main()

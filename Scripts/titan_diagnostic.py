"""Diagnose why TITAN never fires: check entry conditions against actual feature data.

Usage:
    python Scripts/titan_diagnostic.py <run_dir>
"""

import argparse
import json
import sqlite3
from pathlib import Path


def load_features(run_dir: Path) -> list[dict]:
    """Load features_snapshot from executed/rejected decisions."""
    features = []
    db_paths = sorted(run_dir.glob("*/war_backtest_lab_v25.db"))

    for db_path in db_paths:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT symbol, timestamp, gate_results_json FROM decisions "
                "WHERE gate_results_json IS NOT NULL AND gate_results_json != '{}'"
            ).fetchall()
            for r in rows:
                try:
                    gr = json.loads(r["gate_results_json"])
                    fs = gr.get("features_snapshot")
                    if fs and "adx_14" in fs:
                        fs["_symbol"] = r["symbol"]
                        fs["_timestamp"] = r["timestamp"]
                        features.append(fs)
                except (json.JSONDecodeError, KeyError):
                    pass
        except Exception as e:
            print(f"  Error: {db_path}: {e}")
        finally:
            conn.close()
    return features


def analyze_titan_funnel(features: list[dict], symbol: str | None = None):
    """Check how many feature snapshots pass each TITAN condition."""

    if symbol:
        features = [f for f in features if f.get("_symbol") == symbol]

    label = symbol or "ALL"
    n = len(features)
    if n == 0:
        print(f"  No features for {label}")
        return

    print(f"\n{'=' * 70}")
    print(f"  TITAN DIAGNOSTIC: {label} ({n} cycles)")
    print(f"{'=' * 70}")

    # Check regime classification
    trending = [f for f in features if f.get("regime") == "TRENDING"]
    ranging = [f for f in features if f.get("regime") == "RANGING"]
    volatile = [f for f in features if f.get("regime") == "VOLATILE"]
    print(f"\n  REGIME DISTRIBUTION:")
    print(f"    TRENDING: {len(trending)} ({len(trending)/n*100:.1f}%)")
    print(f"    RANGING:  {len(ranging)} ({len(ranging)/n*100:.1f}%)")
    print(f"    VOLATILE: {len(volatile)} ({len(volatile)/n*100:.1f}%)")
    print(f"    Other:    {n - len(trending) - len(ranging) - len(volatile)}")

    # Only TRENDING cycles matter for TITAN
    tf = trending
    tn = len(tf)
    if tn == 0:
        print(f"\n  No TRENDING cycles - TITAN gate 1 blocks everything")
        return

    print(f"\n  === REVERSAL CONDITIONS (in {tn} TRENDING cycles) ===")

    # REVERSAL SHORT: RSI > 70 + BB%B > 0.95
    rsi_high = [f for f in tf if f.get("rsi_14", 0) > 70]
    bb_high = [f for f in tf if f.get("bb_pct_b", 0) > 0.95]
    rsi_and_bb_high = [f for f in tf if f.get("rsi_14", 0) > 70 and f.get("bb_pct_b", 0) > 0.95]
    print(f"    SHORT Exhaustion:")
    print(f"      RSI > 70:           {len(rsi_high):>5} ({len(rsi_high)/tn*100:.1f}%)")
    print(f"      BB%B > 0.95:        {len(bb_high):>5} ({len(bb_high)/tn*100:.1f}%)")
    print(f"      BOTH (RSI+BB):      {len(rsi_and_bb_high):>5} ({len(rsi_and_bb_high)/tn*100:.1f}%)")

    # REVERSAL LONG: RSI < 30 + BB%B < 0.05
    rsi_low = [f for f in tf if f.get("rsi_14", 0) < 30]
    bb_low = [f for f in tf if f.get("bb_pct_b", 0) < 0.05]
    rsi_and_bb_low = [f for f in tf if f.get("rsi_14", 0) < 30 and f.get("bb_pct_b", 0) < 0.05]
    print(f"    LONG Exhaustion:")
    print(f"      RSI < 30:           {len(rsi_low):>5} ({len(rsi_low)/tn*100:.1f}%)")
    print(f"      BB%B < 0.05:        {len(bb_low):>5} ({len(bb_low)/tn*100:.1f}%)")
    print(f"      BOTH (RSI+BB):      {len(rsi_and_bb_low):>5} ({len(rsi_and_bb_low)/tn*100:.1f}%)")

    # Total exhaustion (either direction)
    any_exhaust = [f for f in tf if
                   (f.get("rsi_14", 0) > 70 and f.get("bb_pct_b", 0) > 0.95) or
                   (f.get("rsi_14", 0) < 30 and f.get("bb_pct_b", 0) < 0.05)]
    print(f"    ANY Exhaustion:       {len(any_exhaust):>5} ({len(any_exhaust)/tn*100:.1f}%)")

    # But TITAN also does lookback over last 20 bars for RSI, so more may pass
    # We can't check lookback from single-snapshot data

    print(f"\n  === CONTINUATION CONDITIONS (in {tn} TRENDING cycles) ===")

    # ADX >= 22
    adx_pass = [f for f in tf if f.get("adx_14", 0) >= 22]
    print(f"    ADX >= 22:            {len(adx_pass):>5} ({len(adx_pass)/tn*100:.1f}%)")

    # ADX rising (we can't check this from snapshot, but note it)
    print(f"    ADX rising 3 bars:    ????? (need candle history, not in snapshot)")

    # EMA21 > EMA55 (for long)
    ema_long = [f for f in tf if f.get("ema_21_vs_55", 0) > 0]
    ema_short = [f for f in tf if f.get("ema_21_vs_55", 0) < 0]
    print(f"    EMA21 > EMA55 (long): {len(ema_long):>5} ({len(ema_long)/tn*100:.1f}%)")
    print(f"    EMA21 < EMA55 (short):{len(ema_short):>5} ({len(ema_short)/tn*100:.1f}%)")

    # Price vs MA200
    above_ma200 = [f for f in tf if f.get("price_vs_ma200", 0) > 0]
    below_ma200 = [f for f in tf if f.get("price_vs_ma200", 0) < 0]
    print(f"    Price > MA200 (long): {len(above_ma200):>5} ({len(above_ma200)/tn*100:.1f}%)")
    print(f"    Price < MA200 (short):{len(below_ma200):>5} ({len(below_ma200)/tn*100:.1f}%)")

    # EMA + MA200 aligned (long)
    long_aligned = [f for f in tf if f.get("ema_21_vs_55", 0) > 0 and f.get("price_vs_ma200", 0) > 0]
    short_aligned = [f for f in tf if f.get("ema_21_vs_55", 0) < 0 and f.get("price_vs_ma200", 0) < 0]
    print(f"    Long aligned (EMA+MA200): {len(long_aligned):>5} ({len(long_aligned)/tn*100:.1f}%)")
    print(f"    Short aligned (EMA+MA200):{len(short_aligned):>5} ({len(short_aligned)/tn*100:.1f}%)")

    # Volume >= 1.2
    vol_12 = [f for f in tf if f.get("volume_ratio", 0) >= 1.2]
    vol_15 = [f for f in tf if f.get("volume_ratio", 0) >= 1.5]
    print(f"    Volume >= 1.2:        {len(vol_12):>5} ({len(vol_12)/tn*100:.1f}%)")
    print(f"    Volume >= 1.5:        {len(vol_15):>5} ({len(vol_15)/tn*100:.1f}%)")

    # Combined CONTINUATION LONG conditions (what we can check)
    cont_long_checkable = [f for f in tf if
                           f.get("adx_14", 0) >= 22 and
                           f.get("ema_21_vs_55", 0) > 0 and
                           f.get("price_vs_ma200", 0) > 0 and
                           f.get("volume_ratio", 0) >= 1.2]
    cont_short_checkable = [f for f in tf if
                            f.get("adx_14", 0) >= 22 and
                            f.get("ema_21_vs_55", 0) < 0 and
                            f.get("price_vs_ma200", 0) < 0 and
                            f.get("volume_ratio", 0) >= 1.2]
    print(f"\n    CONT LONG (ADX+EMA+MA200+Vol): {len(cont_long_checkable):>5} ({len(cont_long_checkable)/tn*100:.1f}%)")
    print(f"    CONT SHORT (ADX+EMA+MA200+Vol):{len(cont_short_checkable):>5} ({len(cont_short_checkable)/tn*100:.1f}%)")
    print(f"    (Still need: ADX rising, HH/HL structure, ATR pctl >= 0.55, pullback)")

    # ATR percentile (if available in feature pack)
    # Check feature_pack_v0 for atr_pctl
    atr_pctl_vals = []
    for f in tf:
        fp = f.get("feature_pack_v0", {})
        if isinstance(fp, dict) and "atr_pctl" in fp:
            atr_pctl_vals.append(fp["atr_pctl"])
    if atr_pctl_vals:
        above_055 = sum(1 for v in atr_pctl_vals if v >= 0.55)
        print(f"    ATR pctl >= 0.55:     {above_055:>5} ({above_055/len(atr_pctl_vals)*100:.1f}%)")

    # Summary
    print(f"\n  === SUMMARY ===")
    print(f"  Exhaustion events (REVERSAL gate): {len(any_exhaust)}/{tn} = {len(any_exhaust)/tn*100:.1f}%")
    print(f"  Checkable CONT LONG passes:        {len(cont_long_checkable)}/{tn} = {len(cont_long_checkable)/tn*100:.1f}%")
    print(f"  Checkable CONT SHORT passes:       {len(cont_short_checkable)}/{tn} = {len(cont_short_checkable)/tn*100:.1f}%")
    print(f"  Uncheckable conditions: ADX rising 3 bars, HH/HL structure, ATR pctl, pullback candle")
    print(f"  These uncheckable conditions further reduce the passing rate")

    # Distribution of key indicators
    print(f"\n  === KEY INDICATOR DISTRIBUTIONS (TRENDING cycles) ===")
    rsi_vals = [f.get("rsi_14", 50) for f in tf]
    adx_vals = [f.get("adx_14", 0) for f in tf]
    bb_vals = [f.get("bb_pct_b", 0.5) for f in tf]
    vol_vals = [f.get("volume_ratio", 1.0) for f in tf]
    print(f"    RSI:    min={min(rsi_vals):.1f}  max={max(rsi_vals):.1f}  mean={sum(rsi_vals)/len(rsi_vals):.1f}")
    print(f"    ADX:    min={min(adx_vals):.1f}  max={max(adx_vals):.1f}  mean={sum(adx_vals)/len(adx_vals):.1f}")
    print(f"    BB%B:   min={min(bb_vals):.3f}  max={max(bb_vals):.3f}  mean={sum(bb_vals)/len(bb_vals):.3f}")
    print(f"    VolRat: min={min(vol_vals):.2f}  max={max(vol_vals):.2f}  mean={sum(vol_vals)/len(vol_vals):.2f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", help="Path to orion_on run directory")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    print(f"Loading features from {run_dir}...")
    features = load_features(run_dir)
    print(f"Loaded {len(features)} feature snapshots")

    # All symbols
    analyze_titan_funnel(features)

    # Per-symbol
    symbols = sorted(set(f.get("_symbol", "?") for f in features))
    for sym in symbols:
        analyze_titan_funnel(features, symbol=sym)


if __name__ == "__main__":
    main()

"""Run pipeline in-process and dump TITAN diagnostic counters.

Usage:
    python Scripts/titan_funnel_live.py
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import ArgusPipeline  # noqa: E402


def main():
    run_dir = Path("runs/titan_diag_temp")
    run_dir.mkdir(parents=True, exist_ok=True)
    db_path = run_dir / "diag.db"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))

    print("Initializing pipeline...")
    pipeline = ArgusPipeline(
        mode="backtest",
        assets=["crypto"],
        data_mode="replay",
        replay_now=None,
        forward_sim=True,
        v25_conn=conn,
        risk_profile="relaxed",
        symbols_override={"crypto": ["BTCUSDT", "ETHUSDT"]},
    )

    titan = pipeline.titan_engine
    print(f"TITAN min_volume_expansion: {titan.min_volume_expansion}")
    print(f"TITAN min_adx: {titan.min_adx}")
    print(f"TITAN min_atr_pctl: {titan.min_atr_pctl}")

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    max_cycles = 744  # 1 month of 1h candles

    print(f"\nRunning {max_cycles} cycles from {start.date()}...")

    for cycle in range(max_cycles):
        now = start + timedelta(hours=cycle)
        try:
            pipeline.run_once(now=now)
        except Exception as e:
            if cycle < 3:
                print(f"  Cycle {cycle}: {type(e).__name__}: {e}")

        if (cycle + 1) % 100 == 0:
            sig = titan._diag.get("signal_produced", 0)
            print(f"  Cycle {cycle + 1}/{max_cycles} -- TITAN signals so far: {sig}")

    print(f"\n{'=' * 60}")
    print(f"TITAN DIAGNOSTIC COUNTERS")
    print(f"{'=' * 60}")

    total_calls = titan._diag.get("cont_long_calls", 0) + titan._diag.get("cont_short_calls", 0)
    print(f"\n  Total generate_signal() calls reaching TRENDING: "
          f"{total_calls + titan._diag.get('regime_reject', 0) + titan._diag.get('history_reject', 0)}")
    print(f"  Regime rejects (not TRENDING):  {titan._diag.get('regime_reject', 0)}")
    print(f"  History rejects (<50 bars):      {titan._diag.get('history_reject', 0)}")

    print(f"\n  --- CONTINUATION LONG ({titan._diag.get('cont_long_calls', 0)} attempts) ---")
    for stage in ["adx", "adx_rising", "ema", "ma200", "structure", "atr_pctl", "volume"]:
        key = f"cont_long_fail_{stage}"
        print(f"    fail_{stage:15s}: {titan._diag.get(key, 0):>5}")
    print(f"    PASS:                  {titan._diag.get('cont_long_pass', 0):>5}")

    print(f"\n  --- CONTINUATION SHORT ({titan._diag.get('cont_short_calls', 0)} attempts) ---")
    for stage in ["adx", "adx_rising", "ema", "ma200", "structure", "atr_pctl", "volume"]:
        key = f"cont_short_fail_{stage}"
        print(f"    fail_{stage:15s}: {titan._diag.get(key, 0):>5}")
    print(f"    PASS:                  {titan._diag.get('cont_short_pass', 0):>5}")

    print(f"\n  --- PULLBACK + SIGNAL ---")
    print(f"    Pullback fail:         {titan._diag.get('pullback_fail', 0):>5}")
    print(f"    Pullback pass:         {titan._diag.get('pullback_pass', 0):>5}")
    print(f"    SIGNAL PRODUCED:       {titan._diag.get('signal_produced', 0):>5}")

    print(f"\n{'=' * 60}")

    conn.close()


if __name__ == "__main__":
    main()

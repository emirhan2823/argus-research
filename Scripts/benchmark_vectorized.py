#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

import numpy as np

from argus_py.lab.vectorized import run_iterative_backtest, run_vectorized_backtest



def build_dataset(size: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.00005, 0.008, size)
    prices = 100.0 * np.cumprod(1.0 + rets)
    raw = rng.normal(0.0, 1.0, size)
    signal = np.where(raw > 0.2, 1.0, np.where(raw < -0.2, -1.0, 0.0))
    return prices, signal



def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark iterative vs vectorized backtest")
    parser.add_argument("--bars", type=int, default=300_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    prices, signal = build_dataset(args.bars, args.seed)

    t0 = time.perf_counter()
    iter_res = run_iterative_backtest(prices, signal)
    t1 = time.perf_counter()

    vec_res = run_vectorized_backtest(prices, signal)
    t2 = time.perf_counter()

    iterative_s = t1 - t0
    vectorized_s = t2 - t1
    speedup = iterative_s / vectorized_s if vectorized_s > 0 else float("inf")

    print(f"bars={args.bars}")
    print(f"iterative_seconds={iterative_s:.6f}")
    print(f"vectorized_seconds={vectorized_s:.6f}")
    print(f"speedup={speedup:.2f}x")
    print(f"iter_total_return={iter_res.total_return:.8f}")
    print(f"vec_total_return={vec_res.total_return:.8f}")
    print(f"equity_match={np.allclose(iter_res.equity_curve, vec_res.equity_curve, atol=1e-10)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

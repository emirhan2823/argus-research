from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np

from .signal_model import MLFeatures


def _as_array(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        raise ValueError("Input series cannot be empty")
    return arr


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1.0)
    out = np.empty_like(values, dtype=float)
    out[0] = values[0]
    for idx in range(1, len(values)):
        out[idx] = alpha * values[idx] + (1.0 - alpha) * out[idx - 1]
    return out


def compute_rsi(close: Sequence[float], period: int = 14) -> float:
    prices = _as_array(close)
    if len(prices) <= period:
        return 50.0

    delta = np.diff(prices)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)

    avg_gain = gains[-period:].mean()
    avg_loss = losses[-period:].mean()

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def compute_macd_hist(close: Sequence[float]) -> float:
    prices = _as_array(close)
    ema_12 = _ema(prices, 12)
    ema_26 = _ema(prices, 26)
    macd = ema_12 - ema_26
    signal = _ema(macd, 9)
    hist = macd - signal
    return float(hist[-1])


def compute_bb_position(close: Sequence[float], window: int = 20, std_factor: float = 2.0) -> float:
    prices = _as_array(close)
    if len(prices) < window:
        return 0.5

    win = prices[-window:]
    mean = float(win.mean())
    std = float(win.std(ddof=0))
    upper = mean + std_factor * std
    lower = mean - std_factor * std
    if upper <= lower:
        return 0.5

    position = (float(prices[-1]) - lower) / (upper - lower)
    return float(np.clip(position, 0.0, 1.0))


def compute_atr_pct(high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int = 14) -> float:
    highs = _as_array(high)
    lows = _as_array(low)
    closes = _as_array(close)

    size = min(len(highs), len(lows), len(closes))
    highs = highs[-size:]
    lows = lows[-size:]
    closes = closes[-size:]

    prev_close = np.roll(closes, 1)
    prev_close[0] = closes[0]

    true_range = np.maximum(highs - lows, np.maximum(np.abs(highs - prev_close), np.abs(lows - prev_close)))
    lookback = true_range[-period:] if len(true_range) >= period else true_range
    atr = float(np.mean(lookback))
    last_close = float(closes[-1])
    if last_close <= 0:
        return 0.0
    return float((atr / last_close) * 100.0)


def compute_volume_ratio(volume: Sequence[float], window: int = 20) -> float:
    vols = _as_array(volume)
    if len(vols) < 2:
        return 1.0

    tail = vols[-window:] if len(vols) >= window else vols
    if len(tail) < 2:
        return 1.0

    baseline = float(np.mean(tail[:-1]))
    if baseline <= 0:
        return 1.0
    return float(vols[-1] / baseline)


def extract_features(
    close: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    volume: Sequence[float],
    *,
    fear_greed: float = 50.0,
    funding_rate: float = 0.0,
) -> MLFeatures:
    return MLFeatures(
        rsi_14=compute_rsi(close, period=14),
        macd_hist=compute_macd_hist(close),
        bb_position=compute_bb_position(close, window=20),
        atr_pct=compute_atr_pct(high, low, close, period=14),
        volume_ratio=compute_volume_ratio(volume, window=20),
        fear_greed=float(fear_greed),
        funding_rate=float(funding_rate),
    )


def features_to_array(features: MLFeatures) -> np.ndarray:
    return np.array(
        [
            features.rsi_14,
            features.macd_hist,
            features.bb_position,
            features.atr_pct,
            features.volume_ratio,
            features.fear_greed,
            features.funding_rate,
        ],
        dtype=float,
    )


def feature_matrix(rows: Sequence[MLFeatures]) -> np.ndarray:
    if not rows:
        return np.empty((0, 7), dtype=float)
    return np.vstack([features_to_array(item) for item in rows])

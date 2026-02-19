"""Fallback feature builder that does not require pandas_ta.

This builder is used on Python 3.11 environments where ``pandas_ta`` cannot
be installed.  It computes a minimal but complete FeatureVector using only
pandas/numpy + lightweight indicator helpers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.core.types import FeatureVector
from src.data.features.cross_asset import compute_cross_asset_features
from src.data.features.crypto_native import compute_crypto_native_features
from src.data.features.microstructure import compute_microstructure_features
from src.data.features.ml_features import compute_ml_features
from src.data.features.sentiment import compute_sentiment_features
from src.data.features.statistical import compute_statistical_features
from src.indicators.basic_indicators import (
    atr,
    bollinger,
    ema,
    log_returns,
    returns,
    rolling_vol,
    rsi,
    sma,
    zscore,
)

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeatureBuildResult:
    feature_vector: Optional[FeatureVector]
    tier1_nan_count: int
    tier2_nan_count: int
    tier3_nan_count: int
    sentinel_penalty: float
    halted: bool
    nan_fields: tuple[str, ...]


def _last(series: pd.Series, default: float = 0.0) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return float(default)
    return float(s.iloc[-1])


def _safe_ratio(num: float, den: float, default: float = 0.0) -> float:
    if den == 0 or not np.isfinite(den):
        return float(default)
    out = num / den
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _adx_wilder(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    c = pd.to_numeric(close, errors="coerce")
    w = max(1, int(window))

    up_move = h.diff()
    down_move = -l.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0.0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0.0), 0.0)

    tr = pd.concat(
        [
            (h - l),
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr_w = tr.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()
    plus_di = 100.0 * (plus_dm.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean() / atr_w.replace(0.0, np.nan))
    minus_di = 100.0 * (minus_dm.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean() / atr_w.replace(0.0, np.nan))
    dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)).fillna(0.0)
    return dx.ewm(alpha=1.0 / w, adjust=False, min_periods=w).mean()


def _aroon_osc(high: pd.Series, low: pd.Series, window: int = 14) -> float:
    w = max(2, int(window))
    h = pd.to_numeric(high, errors="coerce").dropna().tail(w)
    l = pd.to_numeric(low, errors="coerce").dropna().tail(w)
    if len(h) < 2 or len(l) < 2:
        return 0.0

    periods_since_high = (len(h) - 1) - int(np.argmax(h.values))
    periods_since_low = (len(l) - 1) - int(np.argmin(l.values))
    aroon_up = 100.0 * (w - periods_since_high) / w
    aroon_down = 100.0 * (w - periods_since_low) / w
    return float(aroon_up - aroon_down)


class BasicFeatureBuilder:
    """Feature builder fallback for environments without pandas_ta."""

    def build(
        self,
        df: pd.DataFrame,
        symbol: str,
        asset_class: str,
        timestamp: datetime,
        # Microstructure inputs
        spread_pct: float = 0.0,
        orderbook_imbalance: Optional[float] = None,
        trade_flow_imbalance: Optional[float] = None,
        depth_ratio: Optional[float] = None,
        large_trade_ratio: Optional[float] = None,
        # Crypto-native inputs
        funding_rate: Optional[float] = None,
        funding_pctile_30d: Optional[float] = None,
        oi_change_4h_pct: Optional[float] = None,
        oi_change_24h_pct: Optional[float] = None,
        liquidation_est: Optional[float] = None,
        long_short_ratio: Optional[float] = None,
        basis_pct: Optional[float] = None,
        # Cross-asset inputs
        btc_dominance_delta_24h: Optional[float] = None,
        btc_eth_corr_30d: Optional[float] = None,
        total_mcap_momentum: Optional[float] = None,
        stablecoin_flow: Optional[float] = None,
        # Sentiment inputs
        hermes_sentiment_score: Optional[float] = None,
        hermes_sentiment_confidence: Optional[float] = None,
        hermes_urgency: Optional[str] = None,
        # ML inputs
        chronos_forecast_1h: Optional[float] = None,
        chronos_confidence_width: Optional[float] = None,
        lgbm_direction: Optional[int] = None,
        lgbm_confidence: Optional[float] = None,
        meta_label_score: Optional[float] = None,
        regime_prob_trending: Optional[float] = None,
        regime_prob_ranging: Optional[float] = None,
        regime_prob_volatile: Optional[float] = None,
    ) -> FeatureBuildResult:
        try:
            frame = df.copy()
            for col in ("open", "high", "low", "close", "volume"):
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
            frame = frame.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)
            if frame.empty:
                return FeatureBuildResult(None, 1, 0, 0, 1.0, True, ("ohlcv_empty",))

            o = frame["open"]
            h = frame["high"]
            l = frame["low"]
            c = frame["close"]
            v = frame["volume"]

            last_close = _last(c, 1.0)
            last_close = max(last_close, 1e-6)

            # --- Minimal indicator set (required by request) ---
            ret = returns(c)
            lret = log_returns(c)
            vol20_s = rolling_vol(lret, 20)
            rsi14_s = rsi(c, 14)
            atr14_s = atr(h, l, c, 14)
            atr5_s = atr(h, l, c, 5)
            atr20_s = atr(h, l, c, 20)
            ema_fast = ema(c, 21)
            ema_slow = ema(c, 55)
            bb_mid, bb_upper, bb_lower = bollinger(c, 20, 2.0)
            zc = zscore(c, 20)

            # --- Volatility ---
            atr_14 = _last(atr14_s, last_close * 0.005)
            atr_14_pct = _safe_ratio(atr_14, last_close, 0.005)
            atr_ratio_5_20 = _safe_ratio(_last(atr5_s, atr_14), _last(atr20_s, atr_14), 1.0)
            realized_vol_20d = float(_last(vol20_s, 0.01) * np.sqrt(365.0))

            hl = np.log((h.tail(20).replace(0.0, np.nan)) / (l.tail(20).replace(0.0, np.nan))).dropna()
            if len(hl) >= 2:
                parkinson_vol = float(np.sqrt((1.0 / (4.0 * len(hl) * np.log(2.0))) * float((hl**2).sum())))
            else:
                parkinson_vol = 0.0

            bbm = _last(bb_mid, last_close)
            bbu = _last(bb_upper, last_close)
            bbl = _last(bb_lower, last_close)
            bb_width = _safe_ratio((bbu - bbl), bbm, 0.0)

            # --- Trend ---
            adx_14 = _last(_adx_wilder(h, l, c, 14), 20.0)
            ma200 = _last(sma(c, 200), _last(sma(c, max(5, min(200, len(c)))), last_close))
            price_vs_ma200 = _safe_ratio(last_close, ma200, 1.0) - 1.0

            e_fast = _last(ema_fast, last_close)
            e_slow = _last(ema_slow, last_close)
            ema_21_vs_55 = _safe_ratio(e_fast, e_slow, 1.0) - 1.0

            y = c.tail(min(20, len(c))).to_numpy(dtype=float)
            if len(y) >= 2:
                x = np.arange(len(y), dtype=float)
                lr_slope_20 = _safe_ratio(float(np.polyfit(x, y, 1)[0]), last_close, 0.0)
            else:
                lr_slope_20 = 0.0

            supertrend_dir = 1 if last_close >= e_fast else -1
            aroon_osc = _aroon_osc(h, l, 14)

            # --- Momentum ---
            rsi_14 = float(np.clip(_last(rsi14_s, 50.0), 0.0, 100.0))
            bb_denom = max(bbu - bbl, 1e-9)
            bb_pct_b = float(np.clip((last_close - bbl) / bb_denom, 0.0, 1.0))
            roc_10 = float(_last(ret * 100.0, 0.0))

            h14 = _last(h.rolling(14, min_periods=1).max(), last_close)
            l14 = _last(l.rolling(14, min_periods=1).min(), last_close)
            wr_denom = max(h14 - l14, 1e-9)
            willr_14 = float(-100.0 * (h14 - last_close) / wr_denom)

            tp = (h + l + c) / 3.0
            tp_ma20 = sma(tp, 20)
            tp_mad20 = tp.rolling(20, min_periods=20).apply(
                lambda x: float(np.mean(np.abs(x - np.mean(x)))), raw=True,
            )
            cci_series = (tp - tp_ma20) / (0.015 * tp_mad20.replace(0.0, np.nan))
            cci_20 = _last(cci_series, _last(zc, 0.0) * 100.0)

            # --- Volume ---
            vol_ma20 = _last(sma(v, 20), _last(v, 1.0))
            volume_ratio = _safe_ratio(_last(v, 1.0), vol_ma20, 1.0)

            direction = np.sign(c.diff().fillna(0.0))
            obv = (direction * v).fillna(0.0).cumsum()
            obv_tail = obv.tail(min(10, len(obv))).to_numpy(dtype=float)
            if len(obv_tail) >= 2:
                obv_slope = float(np.polyfit(np.arange(len(obv_tail), dtype=float), obv_tail, 1)[0])
                obv_scale = float(np.mean(np.abs(obv_tail)))
                obv_slope_10 = _safe_ratio(obv_slope, obv_scale, 0.0)
            else:
                obv_slope_10 = 0.0

            cum_tpv = (tp * v).cumsum()
            cum_vol = v.cumsum().replace(0.0, np.nan)
            vwap = cum_tpv / cum_vol
            vwap_dev_pct = _safe_ratio((last_close - _last(vwap, last_close)), _last(vwap, last_close), 0.0)

            mfm = ((c - l) - (h - c)) / (h - l).replace(0.0, np.nan)
            mfv = mfm.fillna(0.0) * v
            cmf20_series = mfv.rolling(20, min_periods=1).sum() / v.rolling(20, min_periods=1).sum().replace(0.0, np.nan)
            cmf_20 = _last(cmf20_series, 0.0)

            buy_vol = v.where(c >= o, 0.0)
            sell_vol = v.where(c < o, 0.0)
            total20 = float(v.rolling(20, min_periods=1).sum().iloc[-1]) if not v.empty else 0.0
            if total20 > 0:
                net_delta = float(buy_vol.rolling(20, min_periods=1).sum().iloc[-1] - sell_vol.rolling(20, min_periods=1).sum().iloc[-1])
                volume_delta = net_delta / total20
            else:
                volume_delta = 0.0

            # --- Statistical ---
            stat = compute_statistical_features(frame)
            return_autocorr_20 = float(stat.get("return_autocorr_20") if stat.get("return_autocorr_20") is not None else 0.0)
            hurst_exponent = float(stat.get("hurst_exponent") if stat.get("hurst_exponent") is not None else 0.5)
            entropy_50 = float(stat.get("entropy_50") if stat.get("entropy_50") is not None else 1.0)
            frac_diff_price = float(stat.get("frac_diff_price") if stat.get("frac_diff_price") is not None else 0.0)

            micro = compute_microstructure_features(
                spread_pct=max(float(spread_pct), 0.0005),
                orderbook_imbalance=orderbook_imbalance,
                trade_flow_imbalance=trade_flow_imbalance,
                depth_ratio=depth_ratio,
                large_trade_ratio=large_trade_ratio,
            )
            crypto = compute_crypto_native_features(
                asset_class=asset_class,
                funding_rate=funding_rate,
                funding_pctile_30d=funding_pctile_30d,
                oi_change_4h_pct=oi_change_4h_pct,
                oi_change_24h_pct=oi_change_24h_pct,
                liquidation_est=liquidation_est,
                long_short_ratio=long_short_ratio,
                basis_pct=basis_pct,
            )
            cross = compute_cross_asset_features(
                btc_dominance_delta_24h=btc_dominance_delta_24h,
                btc_eth_corr_30d=btc_eth_corr_30d,
                total_mcap_momentum=total_mcap_momentum,
                stablecoin_flow=stablecoin_flow,
            )
            sent = compute_sentiment_features(
                hermes_sentiment_score=hermes_sentiment_score,
                hermes_sentiment_confidence=hermes_sentiment_confidence,
                hermes_urgency=hermes_urgency,
            )
            ml = compute_ml_features(
                chronos_forecast_1h=chronos_forecast_1h,
                chronos_confidence_width=chronos_confidence_width,
                lgbm_direction=lgbm_direction,
                lgbm_confidence=lgbm_confidence,
                meta_label_score=meta_label_score,
                regime_prob_trending=regime_prob_trending,
                regime_prob_ranging=regime_prob_ranging,
                regime_prob_volatile=regime_prob_volatile,
            )

            fv = FeatureVector(
                timestamp=timestamp,
                symbol=symbol,
                asset_class=asset_class,
                atr_14=float(atr_14),
                atr_14_pct=float(max(1e-6, atr_14_pct)),
                atr_ratio_5_20=float(atr_ratio_5_20),
                realized_vol_20d=float(realized_vol_20d),
                parkinson_vol=float(parkinson_vol),
                bb_width=float(bb_width),
                adx_14=float(adx_14),
                price_vs_ma200=float(price_vs_ma200),
                ema_21_vs_55=float(ema_21_vs_55),
                lr_slope_20=float(lr_slope_20),
                supertrend_dir=int(supertrend_dir),
                aroon_osc=float(aroon_osc),
                rsi_14=float(rsi_14),
                bb_pct_b=float(bb_pct_b),
                roc_10=float(roc_10),
                willr_14=float(willr_14),
                cci_20=float(cci_20),
                volume_ratio=float(volume_ratio),
                obv_slope_10=float(obv_slope_10),
                vwap_dev_pct=float(vwap_dev_pct),
                cmf_20=float(cmf_20),
                volume_delta=float(volume_delta),
                spread_pct=float(micro["spread_pct"] if micro["spread_pct"] is not None else 0.0005),
                orderbook_imbalance=micro["orderbook_imbalance"],
                trade_flow_imbalance=micro["trade_flow_imbalance"],
                depth_ratio=micro["depth_ratio"],
                large_trade_ratio=micro["large_trade_ratio"],
                funding_rate=crypto["funding_rate"],
                funding_pctile_30d=crypto["funding_pctile_30d"],
                oi_change_4h_pct=crypto["oi_change_4h_pct"],
                oi_change_24h_pct=crypto["oi_change_24h_pct"],
                liquidation_est=crypto["liquidation_est"],
                long_short_ratio=crypto["long_short_ratio"],
                basis_pct=crypto["basis_pct"],
                btc_dominance_delta_24h=cross["btc_dominance_delta_24h"],
                btc_eth_corr_30d=cross["btc_eth_corr_30d"],
                total_mcap_momentum=cross["total_mcap_momentum"],
                stablecoin_flow=cross["stablecoin_flow"],
                return_autocorr_20=float(return_autocorr_20),
                hurst_exponent=float(hurst_exponent),
                entropy_50=float(entropy_50),
                frac_diff_price=float(frac_diff_price),
                hermes_sentiment_score=sent["hermes_sentiment_score"],
                hermes_sentiment_confidence=sent["hermes_sentiment_confidence"],
                hermes_urgency=sent["hermes_urgency"],
                chronos_forecast_1h=ml["chronos_forecast_1h"],
                chronos_confidence_width=ml["chronos_confidence_width"],
                lgbm_direction=ml["lgbm_direction"],
                lgbm_confidence=ml["lgbm_confidence"],
                meta_label_score=ml["meta_label_score"],
                regime_prob_trending=ml["regime_prob_trending"],
                regime_prob_ranging=ml["regime_prob_ranging"],
                regime_prob_volatile=ml["regime_prob_volatile"],
            )

            return FeatureBuildResult(
                feature_vector=fv,
                tier1_nan_count=0,
                tier2_nan_count=0,
                tier3_nan_count=0,
                sentinel_penalty=0.0,
                halted=False,
                nan_fields=(),
            )
        except Exception:
            LOG.exception("basic feature build failed")
            return FeatureBuildResult(
                feature_vector=None,
                tier1_nan_count=1,
                tier2_nan_count=0,
                tier3_nan_count=0,
                sentinel_penalty=1.0,
                halted=True,
                nan_fields=("basic_builder_error",),
            )

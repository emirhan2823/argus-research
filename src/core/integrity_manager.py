import polars as pl
import numpy as np
import ccxt.async_support as ccxt
import asyncio
from typing import Optional, List, Dict, Any

class IntegrityManager:
    """
    Ensures Data Integrity through Cross-Exchange Validation, Outlier Detection, and Gap Analysis.
    """

    def __init__(self):
        pass

    async def fetch_binance_comparison(self, symbol: str, timeframe: str, start_time: int, limit: int = 1000) -> pl.DataFrame:
        """
        Fetches comparison data from Binance (The 'Gold Standard' for liquidity).
        """
        # Convert symbol format: "XAU/USDT:USDT" -> "XAU/USDT" for Binance Spot/Futures
        # Ideally check if Binance supports the specific pair.
        # Assuming standard format "BASE/QUOTE"
        binance_symbol = symbol.split(":")[0]

        exchange = ccxt.binance()
        try:
            ohlcv = await exchange.fetch_ohlcv(binance_symbol, timeframe, since=start_time, limit=limit)
            if not ohlcv:
                return pl.DataFrame()

            df = pl.DataFrame(ohlcv, schema=["timestamp", "open", "high", "low", "close", "volume"], orient="row")
            return df
        except Exception as e:
            print(f"Binance Fetch Error: {e}")
            return pl.DataFrame()
        finally:
            await exchange.close()

    def check_cross_exchange_integrity(self, primary_df: pl.DataFrame, secondary_df: pl.DataFrame, tolerance_pct: float = 0.3) -> Dict[str, Any]:
        """
        Compares primary (BingX) vs secondary (Binance) data.
        Returns a report of deviations exceeding tolerance.
        """
        if primary_df.is_empty() or secondary_df.is_empty():
            return {"status": "SKIPPED", "reason": "Empty Data"}

        # Align timestamps (Join)
        # Assuming timestamps are milliseconds
        joined = primary_df.join(secondary_df, on="timestamp", how="inner", suffix="_binance")

        # Calculate Deviation
        # Deviation = abs(Close_BingX - Close_Binance) / Close_Binance
        deviation = (
            (pl.col("close") - pl.col("close_binance")).abs() / pl.col("close_binance")
        ) * 100.0

        # Filter exceeding tolerance
        anomalies = joined.filter(deviation > tolerance_pct)

        # Calculate max deviation (execute expression)
        max_dev = joined.select(deviation.max()).item() if joined.height > 0 else 0.0

        report = {
            "status": "PASS" if anomalies.height == 0 else "FAIL",
            "total_rows": joined.height,
            "anomaly_count": anomalies.height,
            "max_deviation": max_dev,
            "anomalies": anomalies.select(["timestamp", "close", "close_binance"]).to_dicts()
        }

        return report

    def detect_and_flag_outliers(self, df: pl.DataFrame, z_threshold: float = 4.0, window: int = 100) -> pl.DataFrame:
        """
        Detects statistical outliers using Rolling Z-Score.
        Flags rows as 'is_outlier'.
        """
        if df.is_empty():
            return df

        # Rolling Mean & Std
        # We use 'close' price for outlier detection
        rolling_stats = df.select([
            pl.col("close").rolling_mean(window).alias("mean"),
            pl.col("close").rolling_std(window).alias("std")
        ])

        # Calculate Z-Score
        # Z = (Value - Mean) / Std
        # We need to join rolling stats back to df or perform computation in context
        # Polars makes this easier with window functions or expressions

        # Note: rolling_mean in Polars aligns with the window end usually.

        df_with_z = df.with_columns([
            (
                (pl.col("close") - pl.col("close").rolling_mean(window)) /
                (pl.col("close").rolling_std(window) + 1e-9)
            ).alias("z_score")
        ])

        # Flag Outliers
        df_flagged = df_with_z.with_columns([
            (pl.col("z_score").abs() > z_threshold).alias("is_outlier")
        ])

        # Return dataframe with flag
        return df_flagged

    def analyze_gaps(self, df: pl.DataFrame, expected_interval_ms: int = 60000) -> List[Dict[str, Any]]:
        """
        Detects discontinuities in timestamps.
        """
        if df.is_empty():
            return []

        # Calculate Time Delta
        # Shift timestamp by 1 to compare with previous
        # delta = ts[i] - ts[i-1]

        df_gaps = df.sort("timestamp").with_columns([
            (pl.col("timestamp") - pl.col("timestamp").shift(1)).alias("delta")
        ])

        # Filter gaps larger than expected interval (with small buffer for jitter)
        # Using 1.5x interval as threshold to avoid flagging minor jitter
        threshold = expected_interval_ms * 1.5

        gaps = df_gaps.filter(pl.col("delta") > threshold)

        report = []
        for row in gaps.select(["timestamp", "delta"]).to_dicts():
            report.append({
                "gap_end_time": row["timestamp"],
                "gap_duration_ms": row["delta"],
                "missing_candles": int(row["delta"] / expected_interval_ms) - 1
            })

        return report

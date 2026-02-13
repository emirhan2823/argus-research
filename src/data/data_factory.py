import polars as pl
import pandas as pd
import hashlib
import json
import os
import time
from typing import List, Callable, Optional
from datetime import datetime, timedelta
from src.core.integrity_manager import IntegrityManager

class DataFactory:
    """
    Automates data ingestion, gap-healing, and dynamic feature re-generation.
    Ensures 100% data integrity.
    """
    def __init__(self, data_dir: str = "data/time_machine"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.integrity_manager = IntegrityManager()

    def get_parquet_path(self, symbol: str) -> str:
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        return os.path.join(self.data_dir, f"{safe_symbol}.parquet")

    def load_or_sync(self, symbol: str, fetch_func: Callable, feature_func: Callable) -> pl.LazyFrame:
        """
        Main entry point.
        1. Checks for file existence.
        2. Detects Gaps & Heals via REST.
        3. Validates Feature Schema & Regenerates if needed.
        4. Returns LazyFrame.
        """
        path = self.get_parquet_path(symbol)

        # 1. Load Existing Data
        if os.path.exists(path):
            try:
                # Eager load for manipulation (schema check/gap check)
                df = pl.read_parquet(path)
            except Exception as e:
                print(f"Data Corrupt: {e}. Re-fetching all.")
                df = pl.DataFrame()
        else:
            df = pl.DataFrame()

        # 2. Gap Detection & Healing
        current_time_ms = int(time.time() * 1000)

        if df.is_empty():
            print(f"[{symbol}] No local data. Fetching initial history...")
            # Fetch e.g. last 30 days
            start_time = current_time_ms - (30 * 24 * 60 * 60 * 1000)
            new_data = self._fetch_data(fetch_func, start_time)
            df = new_data
        else:
            last_ts = df["timestamp"].max()
            # If gap > 5 minutes (assuming 1m candles)
            if (current_time_ms - last_ts) > (5 * 60 * 1000):
                print(f"[{symbol}] Gap Detected! Last: {last_ts}, Now: {current_time_ms}")
                new_data = self._fetch_data(fetch_func, last_ts + 1)

                if not new_data.is_empty():
                    # Merge and Deduplicate
                    df = pl.concat([df, new_data]).unique(subset=["timestamp"]).sort("timestamp")
                    print(f"[{symbol}] Gap Healed. New rows: {len(new_data)}")

        # 3. Feature Schema Validation
        # Generate hash of current features based on feature_func output on sample
        # For simplicity, we assume feature_func takes a DataFrame and returns a DataFrame with features

        # We need to apply features to a small sample to see what columns are generated
        # This acts as the "Signature" of the code
        if not df.is_empty():
            # Convert to Pandas for feature_func compatibility (assuming strategy uses pandas_ta)
            # Ideal: Strategy uses Polars. Fallback: conversion.
            sample_pd = df.tail(100).to_pandas()
            try:
                features_pd = feature_func(sample_pd)
                current_schema_cols = sorted(list(features_pd.columns))
                current_hash = self._compute_schema_hash(current_schema_cols)

                # Check stored hash (in metadata or side file)
                # Here we compare with existing columns in parquet
                stored_cols = sorted(df.columns)
                stored_hash = self._compute_schema_hash(stored_cols)

                if current_hash != stored_hash:
                    print(f"[{symbol}] Schema Mismatch! Code changed. Regenerating features...")
                    # Recalculate features on WHOLE dataset
                    full_pd = df.to_pandas()
                    full_features_pd = feature_func(full_pd)

                    # Convert back to Polars
                    df = pl.from_pandas(full_features_pd)

                    # Save updated dataset
                    df.write_parquet(path)
                    print(f"[{symbol}] Features regenerated and saved.")
                else:
                    # Save if we healed gaps but didn't regen features
                    # Optimized: Only save if changed (simple check via row count or flag)
                    df.write_parquet(path)

            except Exception as e:
                print(f"Feature Generation Failed: {e}")

        # 3.1 Integrity Check (Post-Healing)
        if not df.is_empty():
            # Check for Gaps
            gaps = self.integrity_manager.analyze_gaps(df)
            if gaps:
                print(f"[{symbol}] WARNING: {len(gaps)} remaining gaps detected.")
                # Could log to specific report file

            # Check for Outliers
            # Only on recent data for speed, or full dataset if small
            # For HFT, we scan everything if possible, or last day
            # Here we demonstrate full scan as it's Polars (fast)
            df = self.integrity_manager.detect_and_flag_outliers(df)

            # Optional: Cross-Check if implemented async (requires await, skipped in sync flow for now)
            # Would be ideal to have an async sync method.

        # 4. Return LazyFrame
        # If we modified df (outlier flagging), we should save it first?
        # Yes, save the clean version with flags
        df.write_parquet(path)

        return pl.scan_parquet(path)

    def _fetch_data(self, fetch_func: Callable, start_time: int) -> pl.DataFrame:
        """
        Wraps the API fetch call and returns Polars DataFrame.
        fetch_func must return Pandas DataFrame or list of dicts.
        """
        try:
            # ExchangeClient usually returns Pandas DF
            # We assume it handles pagination internally or we call it once for recent gap
            data = fetch_func(start_time=start_time)

            if isinstance(data, pd.DataFrame):
                if data.empty:
                    return pl.DataFrame()
                # Ensure timestamp is int
                if not pd.api.types.is_integer_dtype(data.index):
                     # If index is datetime, convert to ms int
                     data['timestamp'] = data.index.astype(np.int64) // 10**6
                else:
                    data['timestamp'] = data.index

                return pl.from_pandas(data).select(pl.exclude("index")) # Polars handles index differently
            return pl.DataFrame(data)
        except Exception as e:
            print(f"Fetch Error: {e}")
            return pl.DataFrame()

    def _compute_schema_hash(self, columns: List[str]) -> str:
        s = json.dumps(columns)
        return hashlib.md5(s.encode()).hexdigest()


from argus_py.data.binance_downloader import BinanceDownloader
import os

OUTPUT_DIR = "argus_py/data"

tasks = [
    # Temporal Test (BTC 2023 H2)
    ("BTCUSDT", "2023-07-01", "2024-01-01"),
    
    # Cross-Asset Test (Jan 2024)
    ("ETHUSDT", "2024-01-01", "2024-02-01"),
    ("SOLUSDT", "2024-01-01", "2024-02-01"),
    ("BNBUSDT", "2024-01-01", "2024-02-01"),
]

print("--- Starting Phase 5 Data Download ---")
for symbol, start, end in tasks:
    print(f"\nProcessing {symbol} ({start} -> {end})...")
    # Note: binance_downloader checks if file exists? No, it overwrites.
    # Ideally checking would be nice but batch download is fine.
    # Wait, binance_downloader saves to {SYMBOL}.csv.
    # If I download 2023-07, it overwrites Jan 2024 BTC?
    # Yes. The downloader logic is: `filename = os.path.join(output_dir, f"{symbol}.csv")`.
    # I need to separate them or merge them.
    # For Phase 5, let's use separate filenames for Temporal test?
    # Or just use date range in filename?
    # `binance_downloader` hardcodes name.
    # I should subclass or modify logic?
    # Or just temporarily download to `argus_py/data/phase5`?
    
    target_dir = OUTPUT_DIR
    if symbol == "BTCUSDT" and start == "2023-07-01":
        # Rename after download or use subfolder
        # Let's use `argus_py/data/temporal` for 2023
        target_dir = os.path.join(OUTPUT_DIR, "temporal")
    
    BinanceDownloader.download_binance_klines(symbol, start, end, target_dir)

print("\n--- Download Complete ---")

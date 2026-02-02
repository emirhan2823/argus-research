import requests
import csv
import os
import time
from datetime import datetime

class BinanceDownloader:
    BASE_URL = "https://api.binance.com/api/v3/klines"
    
    @staticmethod
    def date_to_ms(d_str: str) -> int:
        """Converts YYYY-MM-DD to milliseconds timestamp."""
        try:
            return int(time.mktime(datetime.strptime(d_str, "%Y-%m-%d").timetuple()) * 1000)
        except Exception as e:
            print(f"Invalid date format: {d_str}. Use YYYY-MM-DD.")
            raise e

    @staticmethod
    def download_binance_klines(symbol: str, start_date: str, end_date: str, output_dir: str, interval: str = "1m"):
        symbol = symbol.upper()
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"{symbol}.csv")
        
        start_ms = BinanceDownloader.date_to_ms(start_date)
        end_ms = BinanceDownloader.date_to_ms(end_date)
        
        print(f"--- Downloading {symbol} from Binance ---")
        print(f"Range: {start_date} -> {end_date} ({start_ms} -> {end_ms})")
        print(f"Output: {filename}")
        
        all_candles = []
        current_start = start_ms
        page = 0
        limit = 1000
        max_pages = 5000  # Guard against infinite loops
        
        while True:
            if page >= max_pages:
                print(f"WARNING: Max pages ({max_pages}) reached. Stopping download.")
                break

            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_ms,
                "limit": limit
            }
            
            # Retry logic: 3 attempts (1s, 2s, 4s)
            attempts = 0
            success = False
            response = None
            
            while attempts < 3:
                try:
                    response = requests.get(BinanceDownloader.BASE_URL, params=params, timeout=10)
                    if response.status_code == 200:
                        success = True
                        break
                    elif response.status_code == 429:
                        print("Rate limit hit. Waiting 60s...")
                        time.sleep(60)
                        # Don't increment attempts for rate limit, just retry loop or continue outer?
                        # Standard retry logic usually counts it or handles separately.
                        # Prompt says "Retry: network hatasında 3 kez dene".
                        # Let's count rate limit as a hard wait and retry.
                    else:
                        print(f"Error {response.status_code}: {response.text}")
                except Exception as e:
                    print(f"Network error: {e}")
                
                attempts += 1
                wait_time = 2 ** (attempts - 1) # 1, 2, 4
                print(f"Retrying in {wait_time}s... (Attempt {attempts}/3)")
                time.sleep(wait_time)
            
            if not success:
                print("Failed to fetch data after retries. Aborting.")
                break
                
            data = response.json()
            if not data:
                break
                
            # [Open time, Open, High, Low, Close, Volume, Close time, ...]
            # We want: timestamp(s), open, high, low, close, volume
            
            for k in data:
                ts = k[0] # ms
                o, h, l, c, v = k[1], k[2], k[3], k[4], k[5]
                all_candles.append([ts, o, h, l, c, v])
            
            last_time = data[-1][0] # ms
            
            page += 1
            print(f"[Page {page}] Bars: {len(all_candles)} | Last: {datetime.fromtimestamp(last_time/1000.0)}")
            
            # Setup next loop
            current_start = last_time + 1
            
            if current_start >= end_ms:
                break
                
            # Small nice sleep for API
            time.sleep(0.1)

        # Save to CSV
        if all_candles:
            print(f"Saving {len(all_candles)} bars to {filename}...")
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
                writer.writerows(all_candles)
            print("Download Complete.")
            return True
        else:
            print("No data downloaded.")
            return False

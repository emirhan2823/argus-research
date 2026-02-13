# ARGUS v2.5: Zero-Bias Backtest Engine Architecture

**Role:** Lead Quant Researcher (Ex-HFT/Data Integrity Specialist)
**Objective:** Engineer a "Perfect Simulation" environment for ARGUS v2.5.
**Philosophy:** "Garbage In, Garbage Out" (GIGO) prevention -> "Survival First".

---

## 1. Micro-Volatility & Pressure (GARCH + OBI in Backtest)

### 1.1. Point-in-Time GARCH(1,1) (Volatility Guard)

**What:**
Backtest sırasında, *her bir bar* için GARCH modelini sadece *o ana kadar olan* veriyle eğitip, bir sonraki barın volatilitesini tahmin eden "Rolling Window" yapısı. Gelecek veriyi asla görmemeli (No Look-ahead).

**Why:**
Çoğu amatör backtest, GARCH modelini tüm veri setine (ör. 2020-2023) eğitip, sonra geçmişe dönük tahmin üretir. Bu "In-Sample" hatasıdır ve canlıda çalışmaz. Bizim modelimiz, T anında sadece T-1000...T arasındaki veriyi görebilir.

**How:**
`arch` kütüphanesini `polars` ile entegre ederek "Expanding Window" veya "Rolling Window" uygulayacağız.

**Python Implementation (Rolling Forecast):**

```python
import polars as pl
from arch import arch_model
import numpy as np

def rolling_garch_forecast(series: pl.Series, window_size: int = 1000) -> pl.Series:
    """
    Simulates real-time GARCH forecasting.
    Optimized: Re-fits model every N bars (e.g., daily) to save compute,
    but forecasts strictly 1-step ahead.
    """
    values = series.to_numpy()
    forecasts = np.full(len(series), np.nan)

    # Iterate through time (simulating live trading)
    # Re-fit every 24 bars (approx daily for hourly data) for speed
    # In HFT, we might re-fit every bar, but Python overhead makes that slow.
    refit_step = 24

    for i in range(window_size, len(values), 1):
        train_data = values[i-window_size : i] # Explicitly T-Window to T-1

        # Re-fit model only occasionally to optimize speed
        if i % refit_step == 0 or i == window_size:
            # Scale returns for convergence
            am = arch_model(train_data * 100, vol='Garch', p=1, q=1, dist='Normal')
            res = am.fit(disp='off', show_warning=False)
            params = res.params

        # Manual Forecast using fixed params for intermediate steps
        # This is valid because GARCH params don't change drastically intraday
        # Sigma^2_t = omega + alpha * resid^2_{t-1} + beta * sigma^2_{t-1}
        # (Simplified logic: arch library 'forecast' method handles this best)

        # Ideally, use the fitted model to forecast T+1
        # Here we just use the last fitted model for the next 'refit_step' bars
        # For strict accuracy, fit every bar. For 32GB RAM/Speed trade-off:
        if i % refit_step == 0:
             f = res.forecast(horizon=1)
             # Store annualized vol
             forecasts[i] = np.sqrt(f.variance.iloc[-1, 0]) * np.sqrt(365) / 100
        else:
             # Fill forward last known forecast (or implement simple GARCH update equation)
             forecasts[i] = forecasts[i-1]

    return pl.Series("garch_vol", forecasts)
```

### 1.2. Order Book Imbalance (OBI) Veto

**What:**
Geçmiş L2 (Level 2) Order Book verilerini (Bid/Ask Snapshot) kullanarak OBI hesaplayan ve SQS sinyallerini geçmişe dönük filtreleyen yapı.

**Why:**
OHLCV verisinde "görünmeyen" likidite tuzaklarını backtest'te simüle etmek zorundayız. Gerçek hayatta emriniz OBI yüzünden gerçekleşmeyebilir veya kötü fiyattan gerçekleşebilir.

**How:**
L2 verileri genellikle çok büyüktür (TB seviyesi). Polars kullanarak bunları "Lazy Frame" olarak işleyeceğiz.

```python
def calculate_historical_obi(l2_data: pl.LazyFrame) -> pl.LazyFrame:
    """
    Calculates OBI from historical L2 snapshots.
    l2_data columns: [ts, bid_vol_0..9, ask_vol_0..9]
    """
    return l2_data.with_columns([
        (
            (pl.col("bid_vol_sum") - pl.col("ask_vol_sum")) /
            (pl.col("bid_vol_sum") + pl.col("ask_vol_sum"))
        ).alias("obi_value")
    ])
```

---

## 2. Anti-GIGO Backtest Engine (Perfect Simulation)

### 2.1. Look-ahead Bias Prevention (DataLock)

**What:**
Veri setini oluştururken "gelecek" sütunlarını (ör. `close.shift(-1)`) hesaplama aşamasında kilitli tutan, sadece "Execution" aşamasında açan bir boru hattı (Pipeline).

**Why:**
`Target` (etiket) oluştururken `shift(-1)` kullanırız. Eğer bu sütun yanlışlıkla `Feature` (girdi) olarak modele girerse, model %99 başarı gösterir ama hatalıdır.

**How:**
`DataLock` sınıfı, ham veriyi alır ve ikiye ayırır: `Features` (T anında bilinenler) ve `Targets` (Sadece eğitim/değerlendirme için).

```python
class DataLock:
    def __init__(self, df: pl.DataFrame):
        self.raw = df

    def get_features_at(self, timestamp):
        """
        Returns only data available strictly BEFORE or AT timestamp.
        Enforces a 'knowledge barrier'.
        """
        return self.raw.filter(pl.col("ts") <= timestamp).select(
            pl.exclude("future_close", "target_label")
        )
```

### 2.2. Purged Walk-Forward Validation

**What:**
Zaman serisi validasyonunda eğitim ve test setleri arasına "tampon bölge" (Embargo) koyma.

**Why:**
Finansal verilerde otokorelasyon (serial correlation) vardır. T anındaki işlem, T+1 anındaki sonucu etkiler. Eğer eğitim seti T'de bitip test seti T+1'de başlarsa, model "kopya çeker". Ayrıca işlem bitiş süreleri (ör. 1 saat) sızıntı yaratır.

**How:**
`PurgedKFold` mantığını uygulayacağız.

```python
def generate_purged_folds(timestamps, n_folds=5, embargo_pct=0.01):
    """
    Generates indices for Train/Test splits with Purging & Embargo.
    """
    indices = np.arange(len(timestamps))
    fold_size = len(timestamps) // n_folds
    embargo_size = int(len(timestamps) * embargo_pct)

    for i in range(n_folds):
        # Test segment definition
        test_start = i * fold_size
        test_end = (i + 1) * fold_size

        # Purge: Remove data immediately preceding test set
        # Embargo: Remove data immediately following test set (if training on future)

        # Train indices: All indices EXCEPT [test_start - purge : test_end + embargo]
        train_indices = indices[
            (indices < test_start - embargo_size) |
            (indices > test_end + embargo_size)
        ]

        test_indices = indices[test_start:test_end]

        yield train_indices, test_indices
```

### 2.3. Realistic Slippage & Execution Simulator

**What:**
Sadece "Close" fiyatından işlem yapıldığını varsaymak yerine, "Order Book Depth" verisine göre *Ağırlıklı Ortalama Gerçekleşme Fiyatı* (VWAP of Fill) hesaplamak.

**Why:**
Büyük pozisyon açıyorsan (ör. 10x kaldıraç), tahtadaki ilk kademeyi süpürürsün (Market Impact). Slippage, kârın yarısını yiyebilir.

**How:**
L2 Snapshot verisindeki derinliği simüle edeceğiz. L2 verisi yoksa, volatiliteye dayalı sentetik bir slippage modeli kullanacağız.

```python
def calculate_execution_price(
    side: str,
    size: float,
    l2_snapshot: dict,
    base_slippage_bps: float = 5.0
) -> float:
    """
    Simulates walking the order book to fill 'size'.
    """
    remaining_size = size
    total_cost = 0.0

    book_side = l2_snapshot['asks'] if side == 'buy' else l2_snapshot['bids']

    # Walk the book
    for price, qty in book_side:
        fill_qty = min(remaining_size, qty)
        total_cost += fill_qty * price
        remaining_size -= fill_qty

        if remaining_size <= 0:
            break

    avg_price = total_cost / size

    # Add fixed fee/slippage component if book is thin or unavailable
    if remaining_size > 0:
        # Penalize explicitly for lack of liquidity
        penalty = base_slippage_bps * 1e-4 * avg_price * (remaining_size / size)
        avg_price += penalty if side == 'buy' else -penalty

    return avg_price
```

---

## 3. Memory-Efficient Execution (Polars & LazyFrames)

### What
Veriyi RAM'e yüklemeden (Eager Loading), işlem planını oluşturup sadece ihtiyaç duyulan parçaları belleğe alan (Lazy Execution) kütüphane: **Polars**.

### Why
32GB RAM iyidir ancak L2 (Order Book) verileri veya 1 dakikalık OHLCV verileri (yıllarca) belleği hızla doldurur (`pandas` yaklaşık 3-4x RAM tüketir). Polars ise Rust tabanlıdır, veriyi sıkıştırır ve RAM kullanımını minimize eder.

### How
Tüm veri boru hattını (pipeline) `pl.LazyFrame` üzerine kuracağız.

```python
import polars as pl

def load_data_lazy(parquet_path: str) -> pl.LazyFrame:
    """
    Creates a LazyFrame scan plan. No data is loaded into RAM yet.
    """
    return pl.scan_parquet(parquet_path)

def process_pipeline(lazy_df: pl.LazyFrame) -> pl.DataFrame:
    """
    Constructs the computation graph.
    """
    q = (
        lazy_df
        .sort("ts")
        .with_columns([
            pl.col("close").pct_change().alias("returns"),
            # Add technicals using polars expressions
            (pl.col("high") - pl.col("low")).rolling_mean(14).alias("atr_14")
        ])
        .filter(pl.col("atr_14") > 0.001) # Filter low vol
    )

    # EXECUTE: Only now is data loaded and processed in chunks.
    # Streaming mode allows processing datasets larger than RAM.
    return q.collect(streaming=True)
```

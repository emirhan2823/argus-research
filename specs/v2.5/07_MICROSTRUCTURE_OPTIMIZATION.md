# ARGUS v2.5: Volatility & Microstructure Optimization

**Role:** Senior Quant Developer (Citadel/Jump Trading)
**Objective:** Enhance Leverage Engine with GARCH(1,1) Volatility Forecasting & Order Book Imbalance (OBI).
**Philosophy:** "Survival First" (Preemptive Defense).

---

## 1. GARCH(1,1) Volatility Forecasting

### What
**Generalized Autoregressive Conditional Heteroskedasticity (GARCH).**
Standart sapmanın (volatilitenin) sabit olmadığı, zamanla değiştiği ve "kümeler" (clusters) halinde geldiği gerçeğini modelleyen istatistiksel bir yöntemdir. Basit hareketli ortalamaların (EWMA) aksine, volatilite şoklarının ne kadar kalıcı olacağını (persistence) tahmin eder.

### Why
Finansal piyasalarda volatilite "bulaşıcıdır". Büyük bir fiyat hareketi genellikle başka büyük hareketleri tetikler (Volatility Clustering).
*   **EWMA (Eski):** Volatilite arttıktan *sonra* tepki verir (Lagging).
*   **GARCH (Yeni):** Volatilite şokunun *devam edip etmeyeceğini* olasılıksal olarak tahmin eder. Eğer model "patlama" (explosion) öngörüyorsa, sistem daha kriz başlamadan kaldıracı düşürür. Bu, "Survival First" için kritik bir **erken uyarı sistemidir.**

### How
`arch` kütüphanesini kullanarak GARCH(1,1) modelini kuracağız.

**Python Implementation (Optimized for Multi-Threading):**

```python
import numpy as np
import pandas as pd
from arch import arch_model

def fit_garch_forecast(returns: pd.Series, horizon: int = 1) -> float:
    """
    Fits a GARCH(1,1) model to historical returns and forecasts the next period's volatility.

    Args:
        returns: Percentage returns (e.g., 100 * (p_t / p_t-1 - 1))
        horizon: Forecast horizon (default 1 step ahead)

    Returns:
        forecast_vol: Predicted annualized volatility (sigma)
    """
    # 1. Scale Returns (Critical for Convergence)
    # GARCH models optimizer works best when returns are scaled (e.g. percentages)
    scaled_returns = returns * 100.0

    # 2. Define Model (Constant Mean, GARCH Volatility)
    # vol='Garch', p=1, q=1 is the standard robust configuration.
    model = arch_model(scaled_returns, vol='Garch', p=1, q=1, mean='Constant', dist='Normal')

    # 3. Fit Model (Suppress Output)
    # options={'maxiter': 100} to prevent infinite loops in production
    res = model.fit(disp='off', show_warning=False, options={'maxiter': 100})

    # 4. Forecast Next Step Variance
    forecast = res.forecast(horizon=horizon)
    next_var = forecast.variance.iloc[-1, 0]

    # 5. Convert to Annualized Volatility
    # sqrt(variance) = daily_sigma
    # daily_sigma / 100 = unscaled_daily_sigma
    # unscaled_daily_sigma * sqrt(365) = annualized_sigma
    next_sigma_daily = np.sqrt(next_var) / 100.0
    next_sigma_ann = next_sigma_daily * np.sqrt(365)

    return next_sigma_ann

def volatility_guard(current_leverage: float, forecast_vol: float, vol_threshold: float = 0.40) -> float:
    """
    Volatility Guard: Proactively cuts leverage if forecasted vol exceeds threshold.
    """
    if forecast_vol > vol_threshold:
        # High Volatility Regime Detected!
        # Apply exponential decay to leverage.
        # If forecast is 50%, scalar might be 0.5. If 80%, scalar 0.1.

        excess_vol = forecast_vol - vol_threshold
        penalty = np.exp(-5.0 * excess_vol) # Aggressive dampener

        return current_leverage * penalty

    return current_leverage
```

---

## 2. Order Book Pressure (OBP) Scalar

### What
**Microstructure Analysis (Market Depth).**
Borsa "Limit Order Book" (L2 Data) verisindeki Alıcı (Bid) ve Satıcı (Ask) emirlerinin hacimsel dengesizliğini (Imbalance) ölçer.

### Why
Fiyat grafiği (OHLCV) gerçekleşmiş işlemleri gösterir (Geçmiş). Emir defteri ise gerçekleşmeyi bekleyen niyeti gösterir (Gelecek).
*   **Bull Trap:** Fiyat yükseliyor ama Ask tarafında devasa satış emirleri (Iceberg/Wall) bekliyorsa, yükseliş sahtedir.
*   **Survival First:** Eğer long işlem açmak üzeresiniz ama OBI (Order Book Imbalance) şiddetli şekilde negatifse (-0.8), piyasa yapıcılar (Market Makers) fiyatı aşağı itmeye hazırlanıyordur. Bu işlemi iptal etmek sermayeyi korur.

### How
`Volume Imbalance` formülünü kullanarak bir `Scalar` (0.0 ile 1.0 arası) üreteceğiz.

**Python Implementation (Vectorized):**

```python
def calculate_obi_scalar(
    bids: pd.DataFrame,
    asks: pd.DataFrame,
    trade_direction: str,
    depth_level: int = 10
) -> float:
    """
    Calculates Order Book Imbalance (OBI) Scalar.
    Returns:
        1.0: Supportive Order Book (Safe to trade)
        0.5: Neutral / Slight Pressure (Reduce size)
        0.0: Extreme Opposing Pressure (VETO trade)
    """

    # 1. Aggregated Volume (Top N Levels)
    # Using 'quantity' or 'volume' column from L2 snapshot
    bid_vol = bids.iloc[:depth_level]['quantity'].sum()
    ask_vol = asks.iloc[:depth_level]['quantity'].sum()

    # 2. Calculate Imbalance (-1.0 to +1.0)
    # +1.0 means Only Bids (Strong Support)
    # -1.0 means Only Asks (Strong Resistance)
    imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol + 1e-9)

    # 3. Determine Pressure relative to Trade Direction
    pressure_scalar = 1.0

    if trade_direction == "LONG":
        if imbalance > 0:
            # Book supports Long (More Bids)
            pressure_scalar = 1.0
        elif imbalance < -0.3:
            # Moderate Sell Pressure -> Reduce Leverage
            pressure_scalar = 0.5
        elif imbalance < -0.6:
            # Extreme Sell Pressure (Wall) -> VETO
            pressure_scalar = 0.0

    elif trade_direction == "SHORT":
        if imbalance < 0:
            # Book supports Short (More Asks)
            pressure_scalar = 1.0
        elif imbalance > 0.3:
            # Moderate Buy Pressure
            pressure_scalar = 0.5
        elif imbalance > 0.6:
            # Extreme Buy Pressure (Wall)
            pressure_scalar = 0.0

    return pressure_scalar
```

---

## 3. Integration & Efficiency (Multiprocessing)

### What
GARCH(1,1) modelinin `fit()` fonksiyonu iteratif bir optimizasyon sürecidir ve CPU yoğundur. Eğer bunu ana ticaret döngüsü (Main Loop) içinde senkron (bloklayarak) çalıştırırsanız, `Low-Latency` yapınız çöker. Ticaret botunuz donar ve fiyat değişimlerini kaçırır.

### Why
i7-11800H işlemcinizin 16 Thread'i var. Ana döngü tek bir çekirdekte (Core 0) çalışırken, ağır matematiksel işleri (GARCH Fitting) diğer çekirdeklere (Core 1-15) yıkmalıyız.

### How
Python `concurrent.futures.ProcessPoolExecutor` kullanarak GARCH hesaplamasını "Sidecar" (Yan Sepet) mantığıyla asenkron çalıştıracağız.

**Architecture:**

```python
import concurrent.futures
import time

class MicrostructureEngine:
    def __init__(self):
        # Executor Pool (Persistent)
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=2)
        self.latest_vol_forecast = 0.0
        self.is_calculating = False

    def update_volatility_async(self, returns_data):
        """
        Non-blocking call to update volatility forecast.
        """
        if self.is_calculating:
            return # Skip if already busy

        self.is_calculating = True

        # Submit task to separate process
        future = self.executor.submit(fit_garch_forecast, returns_data)

        # Add callback to update state when done
        future.add_done_callback(self._on_vol_update)

    def _on_vol_update(self, future):
        try:
            self.latest_vol_forecast = future.result()
        except Exception as e:
            print(f"GARCH Fit Error: {e}")
        finally:
            self.is_calculating = False

    def get_safe_leverage(self, current_leverage):
        """
        Main Loop calls this. It's instant (O(1)) because it reads cached value.
        """
        return volatility_guard(current_leverage, self.latest_vol_forecast)

# Usage in Main Loop
# engine = MicrostructureEngine()
# while True:
#     price = get_price()
#     engine.update_volatility_async(recent_returns) # Offloads heavy math
#
#     safe_lev = engine.get_safe_leverage(target_lev) # Instant
#     execute_trade(..., leverage=safe_lev)
```

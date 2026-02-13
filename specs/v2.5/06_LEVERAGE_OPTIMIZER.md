# ARGUS v2.5: Dynamic Leverage Scaling (DLS) & Risk Engine

**Role:** Quantitative Strategist (Ex-Bridgewater/Two Sigma)
**Objective:** Engineer a 10x Growth Engine via Volatility Targeting & Regime Adaptation.
**Philosophy:** "Survival First" -> "Thrive Second".

---

## 1. Volatility Targeting (Vol-Target)

### What
Portföyün maruz kaldığı günlük fiyat dalgalanmasını (Daily Dollar Volatility) sabitleyen bir mekanizmadır. Amacımız, piyasa sakinleştiğinde (Low Vol) kaldıraç kullanarak getiriyi artırmak, piyasa çalkalandığında (High Vol) ise pozisyonu küçülterek riski sabitlemektir.

### Why
Standart "sabit lot" veya "sermaye yüzdesi" (%1 Risk) yöntemleri, piyasa volatilitesi arttığında portföyü devasa risklere sokar. Bridgewater'ın "All Weather" fonunun temel prensibi budur: Risk Parity. Volatilite düştüğünde getiri elde etmek için kaldıraç şarttır; volatilite fırladığında hayatta kalmak için küçülmek şarttır.

### How
Volatiliteyi ölçmek için GARCH(1,1) veya basitçe Exponentially Weighted Moving Average (EWMA) kullanacağız.

**Python Implementation (Vectorized):**

```python
import numpy as np
import pandas as pd

def calculate_vol_target_leverage(
    prices: pd.Series,
    target_vol_ann: float = 0.20,  # Hedef Yıllık Volatilite %20
    lookback: int = 21
) -> pd.Series:
    """
    Calculates the leverage required to maintain a constant volatility target.
    """
    # 1. Calculate Daily Returns
    returns = prices.pct_change()

    # 2. Estimate Realized Volatility (EWMA for speed/reactivity)
    # Span=21 corresponds to ~1 month center of mass
    daily_vol_est = returns.ewm(span=lookback).std()

    # 3. Annualize Volatility (Crypto/Forex 24/7 -> sqrt(365), Stocks -> sqrt(252))
    ann_vol_est = daily_vol_est * np.sqrt(365)

    # 4. Calculate Leverage Factor
    # If Market Vol is 10% and Target is 20%, Leverage = 2.0x
    # If Market Vol is 40% and Target is 20%, Leverage = 0.5x
    leverage_factor = target_vol_ann / ann_vol_est

    # 5. Cap Leverage (Survival First) - e.g., Max 4x
    leverage_factor = leverage_factor.clip(upper=4.0)

    return leverage_factor.fillna(0.0)
```

---

## 2. Regime-Adaptive Leverage (HMM Integration)

### What
Piyasanın gizli durumuna (Hidden State) göre kaldıraç katsayısını dinamik olarak ayarlayan bir "vites kutusu" (gearbox).

### Why
Her piyasa rejimi kaldıraç için uygun değildir.
*   **Bull/Low-Vol:** Kaldıraç dostudur. Trend güçlü, gürültü az.
*   **Bear/High-Vol:** Yüksek risk içerir. Kaldıraç düşürülmeli veya Short ağırlıklı olmalı.
*   **Chop/Mean-Reverting:** Kaldıraç ölümcüldür. Testere (whipsaw) piyasasında kaldıraç sermayeyi eritir.

### How
Hidden Markov Model (HMM) çıktısını bir çarpan (scalar multiplier) vektörüne dönüştüreceğiz.

**Transition Logic:**

| State | Description | Volatility | Trend | Leverage Scalar |
| :--- | :--- | :--- | :--- | :--- |
| **0** | **Bull Run** | Low | Positive | **1.0x (Base)** |
| **1** | **Correction** | Medium | Negative | **0.5x (Defensive)** |
| **2** | **Chaos/Chop** | High | Flat | **0.0x (Cash)** |

**Python Implementation:**

```python
def apply_regime_scalar(leverage_series: pd.Series, hmm_states: pd.Series) -> pd.Series:
    """
    Adjusts leverage based on HMM Market Regime.
    State 0: Bull (1.0x)
    State 1: Bear (0.5x)
    State 2: Chop (0.0x - Sleep Mode)
    """
    # Define Scalar Map
    regime_map = {
        0: 1.0,
        1: 0.5,
        2: 0.0
    }

    # Map states to scalars
    scalars = hmm_states.map(regime_map)

    # Apply to base leverage
    adjusted_leverage = leverage_series * scalars

    return adjusted_leverage
```

---

## 3. Drawdown-Based De-leveraging (Circuit Breaker)

### What
Sermaye eridikçe (Drawdown arttıkça), izin verilen maksimum kaldıracı lineer olmayan bir şekilde (Non-linear decay) azaltan bir güvenlik mekanizması.

### Why
"Martingale" (zararda pozisyon büyütme) stratejisi iflasın garantisidir. Profesyonel fon yönetimi tam tersini yapar: **Anti-Martingale**. Kazandıkça risk artırılır, kaybettikçe risk azaltılır. Bu, "Survival First" felsefesinin matematiksel karşılığıdır. %10 kayıp %11 kazançla telafi edilir, ancak %50 kayıp %100 kazanç gerektirir. Çukur derinleşmeden frene basılmalıdır.

### How
Sigmoid veya Quadratic bir "Ceza Fonksiyonu" (Penalty Function) kullanacağız.

**Formula:**
$$ Cap_t = MaxLev \times (1 - (\frac{CurrentDD}{MaxDD})^2) $$

**Python Implementation:**

```python
def calculate_drawdown_cap(
    current_equity: float,
    peak_equity: float,
    max_tolerable_dd: float = 0.15, # %15 Max DD Limit
    max_base_leverage: float = 5.0
) -> float:
    """
    Calculates the maximum allowed leverage based on current drawdown.
    Non-linear penalty: As DD approaches Limit, Leverage goes to 0 rapidly.
    """
    # 1. Calculate Current Drawdown
    dd_pct = (peak_equity - current_equity) / peak_equity
    dd_pct = max(0.0, dd_pct)

    # 2. Check Hard Stop
    if dd_pct >= max_tolerable_dd:
        return 0.0 # Circuit Breaker Tripped!

    # 3. Calculate Penalty Factor (Quadratic Decay)
    # If DD is 0%, Penalty is 0. Factor is 1.0.
    # If DD is 7.5% (Half), Penalty is (0.5)^2 = 0.25. Factor is 0.75.
    # If DD is 15% (Max), Penalty is (1.0)^2 = 1.0. Factor is 0.0.
    penalty_ratio = (dd_pct / max_tolerable_dd) ** 2
    safety_factor = 1.0 - penalty_ratio

    # 4. Adjust Cap
    adjusted_cap = max_base_leverage * safety_factor

    return adjusted_cap
```

---

## 4. Kelly-Leverage Fusion (The Synthesis)

### What
Kelly Kriteri (Teorik Optimal) ile Borsa Kaldıracı (Pratik Sınır) ve Volatilite Hedeflemesi (Risk Yönetimi) arasındaki nihai sentez.

### Why
Kelly Kriteri genellikle aşırı kaldıraç önerir (ör. %50 sermaye riski). Bunu "Half-Kelly" veya "Quarter-Kelly" olarak yumuşatmak standarttır. Ancak biz bunu statik bir çarpanla değil, HMM ve Volatilite verisiyle dinamik olarak yapacağız.

### How
Nihai Pozisyon Büyüklüğü şu 3 faktörün en küçüğü (minimumu) olacaktır:
1.  **Kelly Size:** Reflector'dan gelen kazanma olasılığına dayalı büyüklük.
2.  **Vol-Target Size:** Hedef volatiliteye (ör. günlük %1) ulaşmak için gereken büyüklük.
3.  **Drawdown Cap:** Sermaye kaybına dayalı maksimum kaldıraç sınırı.

**Final Algorithm:**

```python
def calculate_final_position_size(
    account_equity: float,
    kelly_fraction: float,       # From Reflector (e.g., 0.10)
    vol_target_lev: float,       # From Vol-Target (e.g., 2.5x)
    regime_scalar: float,        # From HMM (e.g., 1.0 or 0.0)
    dd_leverage_cap: float       # From Drawdown (e.g., 4.2x)
) -> dict:

    # 1. Apply Regime Scalar to Base Kelly
    # If Chop, Kelly becomes 0.
    adjusted_kelly_lev = kelly_fraction * regime_scalar * 5.0 # Assuming 5x is implied max for "Full Kelly" mapping

    # 2. Determine Limiting Factor (The Constraint)
    # We take the MINIMUM of all safety constraints.
    target_leverage = min(
        adjusted_kelly_lev,  # Performance Driver
        vol_target_lev,      # Stability Driver
        dd_leverage_cap      # Survival Driver
    )

    # 3. Calculate Final Notional Value
    position_notional_usd = account_equity * target_leverage

    return {
        "leverage": target_leverage,
        "size_usd": position_notional_usd,
        "is_safe": target_leverage > 0.1
    }
```

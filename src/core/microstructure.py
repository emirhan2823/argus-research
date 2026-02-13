import numpy as np
import pandas as pd
from arch import arch_model
import concurrent.futures

def fit_garch_forecast(returns: pd.Series, horizon: int = 1) -> float:
    """
    Fits a GARCH(1,1) model to historical returns and forecasts the next period's volatility.

    Args:
        returns: Percentage returns (e.g., 100 * (p_t / p_t-1 - 1))
        horizon: Forecast horizon (default 1 step ahead)

    Returns:
        forecast_vol: Predicted annualized volatility (sigma)
    """
    try:
        # 1. Scale Returns (Critical for Convergence)
        scaled_returns = returns * 100.0

        # 2. Define Model (Constant Mean, GARCH Volatility)
        # vol='Garch', p=1, q=1 is the standard robust configuration.
        model = arch_model(scaled_returns, vol='Garch', p=1, q=1, mean='Constant', dist='Normal')

        # 3. Fit Model
        # options={'maxiter': 100} to prevent infinite loops in production
        res = model.fit(disp='off', show_warning=False, options={'maxiter': 100})

        # 4. Forecast Next Step Variance
        forecast = res.forecast(horizon=horizon)
        next_var = forecast.variance.iloc[-1, 0]

        # 5. Convert to Annualized Volatility
        next_sigma_daily = np.sqrt(next_var) / 100.0
        next_sigma_ann = next_sigma_daily * np.sqrt(365)

        return next_sigma_ann
    except Exception as e:
        print(f"GARCH Fit Error: {e}")
        return 0.20 # Fallback to 20% vol

def volatility_guard(current_leverage: float, forecast_vol: float, vol_threshold: float = 0.40) -> float:
    """
    Volatility Guard: Proactively cuts leverage if forecasted vol exceeds threshold.
    """
    if forecast_vol > vol_threshold:
        excess_vol = forecast_vol - vol_threshold
        penalty = np.exp(-5.0 * excess_vol) # Aggressive dampener
        return current_leverage * penalty

    return current_leverage

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
    if bids.empty or asks.empty:
        return 1.0 # No data, assume neutral

    try:
        # 1. Aggregated Volume (Top N Levels)
        # Assuming input DF has a 'quantity' column
        bid_vol = bids.iloc[:depth_level]['quantity'].sum()
        ask_vol = asks.iloc[:depth_level]['quantity'].sum()

        # 2. Calculate Imbalance (-1.0 to +1.0)
        imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol + 1e-9)

        # 3. Determine Pressure relative to Trade Direction
        pressure_scalar = 1.0

        if trade_direction == "LONG":
            if imbalance > 0:
                pressure_scalar = 1.0
            elif imbalance < -0.3:
                pressure_scalar = 0.5
            elif imbalance < -0.6:
                pressure_scalar = 0.0

        elif trade_direction == "SHORT":
            if imbalance < 0:
                pressure_scalar = 1.0
            elif imbalance > 0.6:
                pressure_scalar = 0.0
            elif imbalance > 0.3:
                pressure_scalar = 0.5

        return pressure_scalar
    except Exception as e:
        print(f"OBI Calculation Error: {e}")
        return 1.0

class MicrostructureEngine:
    def __init__(self):
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=2)
        self.latest_vol_forecast = 0.20 # Default 20%
        self.is_calculating = False

    def update_volatility_async(self, returns_data: pd.Series):
        """
        Non-blocking call to update volatility forecast.
        """
        if self.is_calculating:
            return

        self.is_calculating = True
        future = self.executor.submit(fit_garch_forecast, returns_data)
        future.add_done_callback(self._on_vol_update)

    def _on_vol_update(self, future):
        try:
            self.latest_vol_forecast = future.result()
        except Exception as e:
            print(f"Async GARCH Error: {e}")
        finally:
            self.is_calculating = False

    def get_safe_leverage(self, current_leverage: float) -> float:
        return volatility_guard(current_leverage, self.latest_vol_forecast)

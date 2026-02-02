# Argus Live Trading Playbook

## ⚠️ WARNING: READ BEFORE EXECUTION ⚠️
Live trading involves real financial risk. This system tries to be safe, but software bugs, exchange outages, and market anomalies happen.
**NEVER TRADE MONEY YOU CANNOT AFFORD TO LOSE.**

## 1. Safety Checklist (The "Pre-Flight")
Before running with `--mode live`:
1.  [ ] **Run Dry-Run First**: `python3 argus_py/runner/live_cli.py --mode dry_run ...` for at least 6 hours.
2.  [ ] **Check Logs**: Ensure `runs/live/live_decisions.csv` shows rational output.
3.  [ ] **Verify Config**: check `--max_daily_loss_pct` (Default 2%).
4.  [ ] **Fund Safety**: Move only allocated risk capital to the trading sub-account. Do not keep life savings in the active trading wallet.
5.  [ ] **Environment**: Ensure reliable internet and power (VPS recommended).

## 2. Command Reference

### Dry Run (Safe Default)
```bash
python3 argus_py/runner/live_cli.py \
  --exchange bingx \
  --symbol BTCUSDT \
  --profile BALANCED \
  --mode dry_run
```

### LIVE (Danger Zone)
```bash
export BINGX_API_KEY="your_key"
export BINGX_SECRET="your_secret"

python3 argus_py/runner/live_cli.py \
  --exchange bingx \
  --symbol BTCUSDT \
  --profile DEFENSIVE \
  --mode live \
  --i_understand_live_trading yes
```

## 3. Kill Switches (Automatic)
The bot will **STOP TRADING** if:
*   **Daily Loss > 2%** (Configurable).
*   **Max Drawdown > 5%**.
*   **Consecutive Losses >= 3**.

**Manual Kill**: Press `Ctrl+C`. The bot handles graceful shutdown but always check exchange UI to confirm no hanging orders.

## 4. Troubleshooting
*   **"No candles yielded"**: Check internet connection or API limits.
*   **"Signature Warning"**: Verify API Key/Secret. Check system clock sync.
*   **"Order Failed"**: Check `Min Notional` (usually 5 USDT) or Available Balance.

## 5. Idempotency & State
*   State is saved to `runs/live/live_state.json`.
*   If bot crashes, restart it. It will load `live_state.json` to resume Daily PnL tracking.
*   **Reset**: To clear state (e.g. new day), delete `live_state.json`.

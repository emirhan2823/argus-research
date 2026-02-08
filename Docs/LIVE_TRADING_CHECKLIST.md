# Live Trading Checklist

Before enabling live trading, ensure all items below are completed:

1. `testnet=True` verified working
2. `max_order_value` set to acceptable loss
3. `max_daily_volume` set to daily risk budget
4. `require_confirmation=True` for initial testing
5. Kill-switch integration verified
6. API keys have trade permission only (no withdraw)
7. IP whitelist configured on Binance
8. Testnet paper run for 7+ days without issues

Use `argus_py/broker/safety.py` for programmatic validation of critical config fields.

## Planned Risk Policy Note (Do Not Forget)

- Current behavior: when daily max loss is hit, new trades are blocked for the day.
- Planned enhancement before small-live rollout:
  - If risk level is `SOFT`, allow only selective entries with strict filters.
  - Entry filter: high-conviction setup only (council/score threshold raised).
  - Position size: reduced (target 25-40% of normal size).
  - Cooldown: enforce minimum bars/time between SOFT entries.
- Reason: keep protection active while reducing "missed opportunity" side effect.

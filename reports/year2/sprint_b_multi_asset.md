# Sprint B - Multi-Asset Expansion Layer

## Scope
Implemented Year-2 Sprint B deliverables for a MODE=v2-only multi-asset routing layer while preserving legacy behavior.

## Delivered Components

### 1) Unified Asset Router
- Added `argus_py/asset_router.py`
- Provides a single abstraction that routes market/order/position operations by `asset_class`
- Includes backend failure containment:
  - adapter exceptions do not crash caller
  - optional fallback path
  - structured route snapshot and telemetry tags

### 2) Standardized Adapter Interfaces
- Added `argus_py/adapters/contracts.py`
- Interfaces/contracts:
  - `MarketAdapter`
  - `OrderAdapter`
  - `PositionAdapter`
- Added request/response contracts:
  - `MarketRequest`
  - `OrderRequest`
  - `OrderResult`
  - `PositionSnapshot`

### 3) Pluggable Backends
- Added `argus_py/adapters/crypto_adapter.py`
  - market: Binance klines
  - order/position: existing paper broker bridge
- Added `argus_py/adapters/stock_sim_adapter.py`
  - deterministic paper market simulator
  - order/position: existing paper broker bridge
- Added `argus_py/adapters/defi_sim_adapter.py`
  - deterministic paper market simulator (higher-vol profile)
  - order/position: existing paper broker bridge

### 4) Runtime Wiring (MODE=v2 only)
- Updated `Scripts/paper_daemon.py`
  - new args: `--asset-class crypto|stock|defi`, `--venue-id`
  - initializes `AssetRouter` only when `--mode v2`
  - routes kline fetch via selected backend in v2
  - legacy mode path unchanged

## Telemetry and Metrics
- Added/propagated required telemetry tags:
  - `asset_class`
  - `venue_id`
- Updated:
  - `Scripts/paper_daemon.py` metrics + heartbeat payloads
  - decision/reject/trade JSONL payloads
  - `argus_py/telemetry/schema.py` to include structured asset tags
  - `argus_py/runner/v2_runtime.py` metric tags and payload visibility

## Reliability Guarantees
- One backend failure does not crash engine:
  - router catches backend errors and returns safe outputs
  - daemon remains running with non-throwing fetch path

## Tests Added
- `tests/unit/test_asset_router.py`
  - routing defaults
  - deterministic stock/defi simulation
  - backend failure safety
  - order/position interface wiring
- `tests/integration/test_sprint_b_multi_asset.py`
  - MODE=v2 + stock/defi end-to-end daemon flow
  - asset telemetry tags in metrics + decision JSONL
  - backend failure non-crash integration path

## Verification
- Full test suite:
  - `venv/bin/pytest -q`
  - Result: `265 passed`

## CLI Examples

```bash
# Crypto (existing backend)
venv/bin/python Scripts/paper_daemon.py \
  --mode v2 \
  --asset-class crypto \
  --venue-id binance_spot_paper \
  --strategy council \
  --run_dir runs/year2/paper_main
```

```bash
# Stock (deterministic simulator)
venv/bin/python Scripts/paper_daemon.py \
  --mode v2 \
  --asset-class stock \
  --venue-id auto \
  --strategy council \
  --run_dir runs/year2/paper_main_stock
```

```bash
# DeFi (deterministic simulator)
venv/bin/python Scripts/paper_daemon.py \
  --mode v2 \
  --asset-class defi \
  --venue-id auto \
  --strategy council \
  --run_dir runs/year2/paper_main_defi
```

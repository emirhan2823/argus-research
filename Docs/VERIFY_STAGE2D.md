# Verify Stage-2D (Resilience + Notifications + Multi-symbol)

## 1) Create / activate isolated Python 3.12 venv

```powershell
py -3.12 -m venv .venv312
.venv312\Scripts\Activate.ps1
python -V
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 2) Run unit and integration (offline) tests

```powershell
pytest -q
pytest -q tests/unit/test_exchange_client_resilience.py
pytest -q tests/unit/test_telegram_notifier.py
pytest -q tests/unit/test_symbol_universe.py
pytest -q tests/integration/test_live_data.py::test_live_data_path_uses_exchange_client_and_cache_for_multiple_symbols
```

## 3) Paper one-cycle sanity (live-data, multi-symbol)

```powershell
python -m src.main --mode paper --assets crypto --v25 --live-data --orion --symbols BTCUSDT,ETHUSDT --max-cycles 1
```

## 4) Paper 24h supervisor mode

```powershell
python -m src.main --mode paper --assets crypto --v25 --live-data --orion --paper-24h --daily-loss-cap-pct 0.1 --max-trades-per-day 10
```

## 5) Enable Telegram alerts (optional)

```powershell
set TELEGRAM_BOT_TOKEN=YOUR_TOKEN
set TELEGRAM_CHAT_ID=YOUR_CHAT_ID
python -m src.main --mode paper --assets crypto --v25 --live-data --orion --telegram-signals --telegram-min-confidence 0.60 --symbols BTCUSDT,ETHUSDT --max-cycles 1
```

## 6) Online tests (explicit opt-in)

```powershell
set RUN_ONLINE_TESTS=1
pytest -q tests/integration/test_live_data.py::test_binance_live_data_multi_symbol_smoke
pytest -q tests/integration/test_live_data.py::test_binance_live_data_handles_disconnect_gracefully
```

## 7) Quick SQLite checks (notifications + runtime outputs)

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'runs/v25/argus_v25.db'); cur=c.cursor(); print('decisions',cur.execute('select count(*) from decisions').fetchone()[0]); print('trades',cur.execute('select count(*) from trades').fetchone()[0]); print('telegram_notifications',cur.execute('select count(*) from telegram_notifications').fetchone()[0]); print('symbol_dist',cur.execute('select symbol,count(*) from decisions group by symbol order by count(*) desc limit 15').fetchall()); c.close()"
```

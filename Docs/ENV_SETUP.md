# Environment Setup (Python 3.12, Isolated)

This project supports running in an isolated Python 3.12 virtual environment without modifying system Python or PATH.

## Windows PowerShell (safe, local-only)

```powershell
py -3.12 -m venv .venv312
.venv312\Scripts\Activate.ps1
python -V  # 3.12.x
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Expected Python output should be `3.12.x`.

## Notes on pandas-ta / feature builder fallback

- `pandas_ta` is optional in this repository.
- If `pandas_ta` is not installed, ARGUS automatically uses `BasicFeatureBuilder` and remains functional.
- `requirements.txt` installs core runtime deps (including `pyarrow` for parquet-based replay/historical tests).
- Optional technical-indicator acceleration can be installed manually:

```powershell
pip install pandas_ta
```

If installation fails on your platform/version, continue with fallback mode.

## Run tests in .venv312

```powershell
.venv312\Scripts\Activate.ps1
pytest -q
```

## Running paper/live with venv312

```powershell
python -m src.main --mode paper --assets crypto --v25 --live-data --orion --symbols BTCUSDT,ETHUSDT --max-cycles 1
```

```powershell
python -m src.main --mode live --assets crypto --v25 --live-data --orion --symbols BTCUSDT,ETHUSDT --max-cycles 1
```

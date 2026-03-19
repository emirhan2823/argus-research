@echo off
REM ============================================================
REM  ARGUS Historical Data Downloader - Windows Launcher
REM ============================================================
REM
REM  Downloads Binance OHLCV data into month-partitioned Parquet.
REM  Can be run from any directory.
REM
REM  Usage:
REM    download_data.bat --symbol BTCUSDT --interval 1m --start 2024-01-01 --end 2024-03-01
REM    download_data.bat --symbol ETHUSDT --interval 1h --days 30
REM    download_data.bat --all --interval 1m --days 90
REM    download_data.bat --info
REM    download_data.bat --info BTCUSDT
REM    download_data.bat --verify BTCUSDT --interval 1m
REM
REM  Output: data\binance\{SYMBOL}\{interval}\{YYYY-MM}.parquet
REM ============================================================

cd /d "%~dp0"

REM --- Find Python ---
if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
) else if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

REM --- Pre-flight: verify imports ---
%PYTHON% -c "from src.data.binance_downloader import BinanceDownloader; print('[OK] Imports verified')" 2>nul
if errorlevel 1 (
    echo [ERROR] Import check failed. Make sure you have dependencies installed:
    echo   %PYTHON% -m pip install -r requirements.txt
    pause
    exit /b 1
)

REM --- Run ---
%PYTHON% Scripts\download_historical.py %*

if errorlevel 1 (
    echo.
    echo [ERROR] Download failed. Check logs above.
    pause
    exit /b 1
)

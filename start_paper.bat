@echo off
REM ============================================================
REM  ARGUS v2 Paper Trading Daemon - Windows Launcher
REM ============================================================
REM
REM  Usage:
REM    start_paper.bat              (default: crypto, 60s interval)
REM    start_paper.bat --assets crypto,us_equity --interval 30
REM
REM  Requirements:
REM    1. Python 3.10+ with venv at .\venv\
REM    2. pip install -r requirements.txt
REM    3. Ollama NOT required (unused in v2 pipeline)
REM    4. No API keys needed for paper mode
REM
REM  Stop: Press Ctrl+C (graceful shutdown)
REM  Logs: runs\paper_v2\paper_v2_daemon.log
REM  Heartbeat: runs\paper_v2\heartbeat.json
REM ============================================================

cd /d "%~dp0"

REM --- Create output directories ---
if not exist "runs\paper_v2" mkdir "runs\paper_v2"
if not exist "runs\v25" mkdir "runs\v25"

REM --- Check Python ---
if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
) else if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo ============================================================
echo  ARGUS v2 Paper Trading Daemon
echo ============================================================
echo  Python: %PYTHON%
echo  Time:   %date% %time%
echo.

REM --- Install deps check ---
%PYTHON% -c "import pandas_ta" 2>nul
if errorlevel 1 (
    echo [WARN] pandas_ta not found. Installing dependencies...
    %PYTHON% -m pip install -r requirements.txt --quiet
    echo.
)

REM --- Pre-flight: quick import check ---
%PYTHON% -c "from src.main import ArgusPipeline; print('[OK] Pipeline imports successful')"
if errorlevel 1 (
    echo [ERROR] Pipeline import failed. Check logs.
    pause
    exit /b 1
)

echo.
echo Starting daemon... (Ctrl+C to stop)
echo.

REM --- Run the daemon ---
%PYTHON% Scripts\paper_v2_daemon.py --mode paper --assets crypto --interval 60 --v25 --v25-db runs\v25\argus_v25.db --run-dir runs\paper_v2 %*

echo.
echo Daemon stopped.
pause

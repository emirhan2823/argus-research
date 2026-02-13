@echo off
REM ARGUS v2.5 Generation 0 Trigger Script (Windows)

echo [ARGUS] Creating Virtual Environment...
py -3.12 -m venv .venv

echo [ARGUS] Activating Environment...
call .venv\Scripts\activate

echo [ARGUS] Upgrading pip...
python -m pip install --upgrade pip setuptools wheel

echo [ARGUS] Installing Dependencies...
pip install -r requirements.txt
pip install -e .

echo [ARGUS] Triggering Generation 0 Evolution...
python scripts/execute_gen0.py

echo [ARGUS] Done.
pause

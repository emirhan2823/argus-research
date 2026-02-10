# Windows Sprint-B Runbook (ARGUS)

Bu runbook, Sprint-B (multi-asset router + simulated backends) akisini Windows makinede `E:\` diskini kullanarak calistirmak ve dogrulamak icindir.

## 1) Prerequisites

- Windows 10/11
- PowerShell 5.1+ veya PowerShell 7+
- Python `3.11.9` (veya 3.11.x) kurulu
- `git` kurulu
- Internet erisimi (`crypto` testinde Binance klines cekilir)
- Yeterli disk alani: tum runtime ve run klasorleri `E:\argus\` altina yazilir

## 2) One-Time Setup

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\windows_setup.ps1 -RootPath "E:\argus"
```

Bu komut:
- `E:\argus\runs\year2\paper_main_crypto`
- `E:\argus\runs\year2\paper_main_stock`
- `E:\argus\runs\year2\paper_main_defi`
- `venv` olusturma + dependency kurulumu

## 3) Clone / Update

### Clone (ilk kurulum)

```powershell
cd E:\
mkdir argus -Force
git clone <REPO_URL> E:\argus\argus-terminal
cd E:\argus\argus-terminal
```

### Update (mevcut repo)

```powershell
cd E:\argus\argus-terminal
git fetch --all --prune
git pull --ff-only
```

Ardindan setup tekrar:

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\windows_setup.ps1 -RootPath "E:\argus"
```

## 4) Venv + Install Deps

`windows_setup.ps1` bunu zaten yapar. Elle yapmak istersen:

```powershell
cd E:\argus\argus-terminal
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 5) Run Pytest

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\windows_doctor.ps1 -RootPath "E:\argus"
```

Bu komut:
- setup kontrolu + venv/deps
- `pytest -q`
- sonucu `reports/year2/windows_sprint_b_validation.md` dosyasina append eder

## 6) Run Sprint-B (Paper Daemon, MODE=v2)

### Crypto

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\windows_run_sprint_b.ps1 -RootPath "E:\argus" -AssetClass crypto
```

### Stock (simulated)

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\windows_run_sprint_b.ps1 -RootPath "E:\argus" -AssetClass stock
```

### DeFi (simulated)

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\windows_run_sprint_b.ps1 -RootPath "E:\argus" -AssetClass defi
```

Varsayilan olarak her run ~3 dakika devam eder (`-DurationSec 180`).

## 7) Soak Control (Manual)

### Start

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\windows_soak_start.ps1 -RootPath "E:\argus" -AssetClass crypto
```

### Status

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\windows_soak_status.ps1 -RootPath "E:\argus" -AssetClass crypto
```

### Stop

```powershell
powershell -ExecutionPolicy Bypass -File Scripts\windows_soak_stop.ps1 -RootPath "E:\argus" -AssetClass crypto
```

## 8) Nightly Eval (Manual, MODE=v2)

Asset bazli run klasoru icin:

```powershell
cd E:\argus\argus-terminal
.\venv\Scripts\python.exe Scripts\nightly_eval.py --mode v2 --run_dir E:\argus\runs\year2\paper_main_crypto --reports_dir reports\year2\windows\crypto
.\venv\Scripts\python.exe Scripts\nightly_eval.py --mode v2 --run_dir E:\argus\runs\year2\paper_main_stock  --reports_dir reports\year2\windows\stock
.\venv\Scripts\python.exe Scripts\nightly_eval.py --mode v2 --run_dir E:\argus\runs\year2\paper_main_defi   --reports_dir reports\year2\windows\defi
```

## 9) Logs / Runs on E:

- Repo: `E:\argus\argus-terminal`
- Run roots:
  - `E:\argus\runs\year2\paper_main_crypto`
  - `E:\argus\runs\year2\paper_main_stock`
  - `E:\argus\runs\year2\paper_main_defi`
- Runtime artifacts:
  - `daemon.pid`
  - `daemon.log`
  - `daemon.err.log`
  - `heartbeat.json`
  - `metrics.json`
  - `decisions.csv|jsonl`
  - `rejects.csv|jsonl`
  - `trades.csv|jsonl`

## 10) Deterministic Verification Procedure

Asagidaki sira ile calis:

1. `windows_doctor.ps1`
2. `windows_run_sprint_b.ps1 -AssetClass crypto`
3. `windows_run_sprint_b.ps1 -AssetClass stock`
4. `windows_run_sprint_b.ps1 -AssetClass defi`

Her adim sonucunu su dosyada topla:

- `E:\argus\argus-terminal\reports\year2\windows_sprint_b_validation.md`

PASS kriteri:
- doctor `pytest -q` basarili
- her asset class icin daemon start/status/stop akisi basarili
- heartbeat+metrics olusmus
- `nightly_eval.py` `--mode v2` basarili


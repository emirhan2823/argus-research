
import subprocess
import os
import shutil
import sys

TASKS = [
    {
        "name": "Adx35_Exp80_S1_Normal_OUT",
        "cmd": [
            "python3", "-u", "-m", "argus_py.runner.cli",
            "--mode", "backtest",
            "--symbol", "BTCUSDT",
            "--data_dir", "argus_py/data/cache",
            "--start_date", "2024-02-01",
            "--end_date", "2024-03-01",
            "--fee_bps", "4.0",
            "--slippage_bps", "2.0",
            "--spread_bps", "1.0", 
            "--min_adx", "35",
            "--max_exp_move_bps", "80",
            "--quiet"
        ]
    },
    {
        "name": "Adx35_Exp80_S1_Stress_OUT",
        "cmd": [
            "python3", "-u", "-m", "argus_py.runner.cli",
            "--mode", "backtest",
            "--symbol", "BTCUSDT",
            "--data_dir", "argus_py/data/cache",
            "--start_date", "2024-02-01",
            "--end_date", "2024-03-01",
            "--fee_bps", "8.0",
            "--slippage_bps", "4.0",
            "--spread_bps", "2.0",
            "--min_adx", "35",
            "--max_exp_move_bps", "80", 
            "--quiet"
        ]
    }
]

def run_task(t):
    print(f"Running {t['name']}...")
    try:
        proc = subprocess.run(t["cmd"], check=True, capture_output=True, text=True)
        out = proc.stdout + "\n" + proc.stderr
        
        # Parse dir
        run_dir = None
        for line in out.splitlines():
            if "Logging run to:" in line:
                run_dir = line.split("Logging run to:")[1].strip()
                break
        
        if run_dir and os.path.isdir(run_dir):
            target = os.path.join("runs/phase18_robustness", t["name"])
            if os.path.exists(target): shutil.rmtree(target)
            shutil.move(run_dir, target)
            
            # Save log
            with open(os.path.join(target, "stdout.log"), "w") as f:
                f.write(out)
                
            print(f"SUCCESS: Moved to {target}")
        else:
            print(f"FAIL: Run dir not found. Out:\n{out[-500:]}")

    except subprocess.CalledProcessError as e:
        print(f"CRASH {t['name']}: {e.stderr}")

if __name__ == "__main__":
    for t in TASKS:
        run_task(t)

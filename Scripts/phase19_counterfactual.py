
import sys
import json
import pandas as pd
import numpy as np
import requests
import time
from pathlib import Path
from datetime import datetime

# --- CONFIG ---
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from Scripts.phase19_eval_config import HORIZONS, COST_MODEL, GATES
from datetime import timedelta

TWIN_ROOT = REPO_ROOT / "runs/phase19_twin"
LAB_DIR = TWIN_ROOT / "lab"
LAB_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = LAB_DIR / "counterfactual_labels.csv"
SUMMARY_FILE = LAB_DIR / "reject_audit_summary.md"

def fetch_klines(symbol="BTCUSDT", interval="1m", limit=1500):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data, columns=["open_time", "open", "high", "low", "close", "vol", "close_time", "qav", "n", "tbb", "tbq", "ign"])
        df["ts"] = df["open_time"].apply(lambda x: int(x)/1000.0)
        df["close"] = df["close"].astype(float)
        return df.set_index("ts")
    except Exception as e:
        print(f"Error fetching klines: {e}")
        return pd.DataFrame()

def load_decisions(daemon_id, n=1000):
    # Load last n records
    path = TWIN_ROOT / daemon_id / "decisions.jsonl"
    if not path.exists(): return pd.DataFrame()
    
    records = []
    try:
        with open(path, "r") as f:
            for line in f:
                 records.append(json.loads(line))
        # Keep internal logic simple, assume sorted logs for now or small enough 
        # For production use proper efficient tail if files get huge
    except: pass
    
    if not records: return pd.DataFrame()
    df = pd.DataFrame(records)
    df["ts_align"] = df["bar_ts_iso"].apply(lambda x: datetime.fromisoformat(x).timestamp() if x else 0)
    return df.set_index("ts_align")

def calculate_net_ret(entry, exit, side):
    gross = (exit - entry)/entry if side == "LONG" else (entry - exit)/entry
    costs = (COST_MODEL['fee_bps'] + COST_MODEL['slippage_bps'] + COST_MODEL['spread_bps']) * 2 / 10000.0
    return (gross - costs) * 100.0 # Return in %

def evaluate():
    print("Locked & Loaded Phase 19.7 Counterfactual Lab")
    df_strict = load_decisions("STRICT")
    df_soft = load_decisions("SOFT")
    
    if df_strict.empty or df_soft.empty:
        print("Waiting for logs...")
        return

    common_idx = df_strict.index.intersection(df_soft.index)
    pricing = fetch_klines() # ensure coverage? 
    # If using live data fetching, might miss older decision points if not in last 1500 bars
    # Assuming this runs frequently enough or logs are recent

    results = []
    missing_reasons_count = 0
    
    for ts in common_idx:
        row_s = df_strict.loc[ts]
        row_soft = df_soft.loc[ts]
        
        # Divergence: STRICT BLOCK vs SOFT GO
        if row_s["decision"] == "BLOCK" and row_soft["decision"] == "GO":
            # This is a REJECT to Audit
            symbol = row_s["symbol"]
            gate = "OTHER"
            
            # Attribute Gate
            raw_reason = row_s.get("block_reason_primary")
            reason = ""
            
            # Paranoid Check
            if raw_reason is None:
                reason = ""
                missing_reasons_count += 1
            elif isinstance(raw_reason, float) and np.isnan(raw_reason):
                reason = ""
                missing_reasons_count += 1
            elif pd.isna(raw_reason):
                reason = ""
                missing_reasons_count += 1
            else:
                reason = str(raw_reason)

            if "MIN_ADX" in reason: gate = "MIN_ADX"
            elif "ROUTER" in reason: gate = "ROUTER_DEFENSE"
            elif "MAX_EXP" in reason: gate = "MAX_EXP"
            
            # Shadow Outcomes
            entry_price = pricing.loc[ts]["close"] if ts in pricing.index else 0
            if entry_price == 0: continue
            
            eval_row = {
                "ts_iso": row_s["ts_iso"],
                "symbol": symbol,
                "strict_decision": "BLOCK",
                "soft_decision": "GO",
                "strict_gate_reason": gate,
                "strict_gate_detail": reason,
                "price_entry": entry_price
            }
            
            for h in HORIZONS:
                target_mm = ts + (h * 60)
                # find closest price
                slice_df = pricing[pricing.index >= target_mm]
                if not slice_df.empty:
                    exit_price = slice_df.iloc[0]["close"]
                    net_ret = calculate_net_ret(entry_price, exit_price, row_soft["direction"])
                    
                    eval_row[f"price_exit_h{h}"] = exit_price
                    eval_row[f"ret_h{h}_net"] = net_ret
                    
                    # Label: Correct if we rejected a Loss (NetRet <= 0)
                    # Incorrect if we rejected a Win (NetRet > 0)
                    is_correct = 1 if net_ret <= 0 else 0
                    eval_row[f"label_reject_correct_h{h}"] = is_correct
                    
                    # Shadow PnL: What we missed (if incorrect) or saved (if correct)
                    # Use NetRet directly as proxy
                    eval_row[f"shadow_pnl_h{h}"] = net_ret 
                else:
                    eval_row[f"ret_h{h}_net"] = None
                    
            results.append(eval_row)

    if missing_reasons_count > 0:
        print(f"Sanity: Fixed {missing_reasons_count} rows with None/NaN reasons.")

    if not results:
        print("No divergences found yet.")
        return

    df_out = pd.DataFrame(results)
    df_out.to_csv(OUT_CSV, index=False)
    print(f"Exported {len(df_out)} labels to {OUT_CSV}")
    
    generate_summary(df_out)

def generate_summary(df):
    md = f"# Reject Audit Summary\nGenerated: {datetime.now()}\n\n"
    
    # Accuracy Table (H15)
    if "label_reject_correct_h15" in df.columns:
        md += "## Reject Accuracy (H15)\n"
        # Group by Gate
        # Avoid float formatting issues
        try:
            grp = df.groupby("strict_gate_reason").agg(
                count=("ts_iso", "count"),
                accuracy=("label_reject_correct_h15", "mean"),
                avg_shadow_pnl=("shadow_pnl_h15", "mean")
            )
            try:
                md += grp.to_markdown() + "\n\n"
            except ImportError:
                md += grp.to_string() + "\n\n"
        except Exception as e:
            md += f"Error generating table: {e}\n"

    # Worst Rejects
    if "shadow_pnl_h15" in df.columns:
        md += "## Top Missed Opportunities (Worst Rejects H15)\n"
        # We want largest Positive Shadow PnL (meaning we rejected a massive gain)
        worst = df.sort_values("shadow_pnl_h15", ascending=False).head(10)
        cols = ["ts_iso", "symbol", "strict_gate_reason", "shadow_pnl_h15"]
        try:
            md += worst[cols].to_markdown(index=False)
        except ImportError:
            md += worst[cols].to_string(index=False)
        
    with open(SUMMARY_FILE, "w") as f:
        f.write(md)

if __name__ == "__main__":
    evaluate()



import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
# --- CONFIG ---
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

# Delayed import to ensure sys.path is ready
from Scripts.phase19_eval_config import GATES

TWIN_ROOT = REPO_ROOT / "runs/phase19_twin"
LAB_DIR = TWIN_ROOT / "lab"
INPUT_CSV = LAB_DIR / "counterfactual_labels.csv"
OUTPUT_MD = LAB_DIR / "tuning_proposals.md"

def analyze():
    print("Generating Tuning Proposals...")
    if not INPUT_CSV.exists():
        print("No counterfactual labels found. Skipping.")
        return

    df = pd.read_csv(INPUT_CSV)
    if df.empty:
        print("Label dataset empty.")
        return

    # Filter for H15 horizon for tuning logic (Scalp focus)
    target_pnl = "shadow_pnl_h15"
    if target_pnl not in df.columns:
        print("H15 PnL missing.")
        return

    md = f"# Tuning Proposals (Phase 19.7)\nGenerated: {datetime.now()}\n\n"
    md += "Analysis based on Counterfactual Lab (H15 Horizon).\n\n"

    # --- VARIANT A: Dynamic MIN_ADX ---
    # Hypothesis: Use lower ADX in RANGE regimes?
    # Filter: Gate=MIN_ADX
    df_adx = df[df["strict_gate_reason"] == "MIN_ADX"]
    if not df_adx.empty:
        missed_opps = df_adx[df_adx[target_pnl] > 0]
        total_missed_pnl = missed_opps[target_pnl].sum()
        count = len(df_adx)
        missed_count = len(missed_opps)
        
        md += "## Variant A: Dynamic MIN_ADX\n"
        md += f"- **Current Impact**: {count} trades blocked by MIN_ADX.\n"
        md += f"- **Missed Opportunities**: {missed_count} ({missed_count/count:.1%} of blocks).\n"
        md += f"- **Total Missed PnL**: {total_missed_pnl:.2f}%\n\n"
        
        if total_missed_pnl > 5.0:
            md += "✅ **PROPOSAL**: Consider lowering MIN_ADX to 30 or 28.\n"
            md += "Significant value left on table.\n"
        else:
            md += "❌ **PROPOSAL**: Keep MIN_ADX at 35.\n"
            md += "Cost of safety is low.\n"
        md += "\n"

    # --- VARIANT B: Router Micro-Risk ---
    # Filter: Gate=ROUTER_DEFENSE
    df_router = df[df["strict_gate_reason"] == "ROUTER_DEFENSE"]
    if not df_router.empty:
        missed_pnl = df_router[df_router[target_pnl] > 0][target_pnl].sum()
        
        md += "## Variant B: Router Micro-Risk\n"
        md += f"- **Blocked by Router**: {len(df_router)}\n"
        md += f"- **Missed PnL**: {missed_pnl:.2f}%\n\n"
        
        if missed_pnl > 2.0:
             md += "⚠️ **PROPOSAL**: Allow Micro-Risk (0.2x) in Defense Mode.\n"
        else:
             md += "✅ **PROPOSAL**: Zero-Risk Policy is efficient.\n"
        md += "\n"

    # --- VARIANT C: MaxExp Flexibility ---
    df_exp = df[df["strict_gate_reason"] == "MAX_EXP"]
    if not df_exp.empty:
        missed_pnl = df_exp[df_exp[target_pnl] > 0][target_pnl].sum()
        md += "## Variant C: MaxExp Flexibility\n"
        md += f"- **Blocked by MaxExp**: {len(df_exp)}\n"
        md += f"- **Missed PnL**: {missed_pnl:.2f}%\n"
        md += "Suggest analyzing volatility percentile.\n\n"

    with open(OUTPUT_MD, "w") as f:
        f.write(md)
    
    print(f"Propsoals written to {OUTPUT_MD}")

if __name__ == "__main__":
    analyze()

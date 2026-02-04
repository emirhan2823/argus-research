#!/usr/bin/env python3
import os
import sys
import pandas as pd
import argparse

def generate_surface(grid_dir):
    print(f"Generating Surface Map for: {grid_dir}")
    
    summary_md = []
    summary_md.append("# Phase 17 Sensitivity Surface Analysis")
    summary_md.append(f"**Run Directory**: `{grid_dir}`\n")
    
    windows = ["INSAMPLE", "OUTSAMPLE"]
    dfs = {}
    
    for w in windows:
        csv_path = os.path.join(grid_dir, f"grid_summary_{w}.csv")
        if not os.path.exists(csv_path):
            print(f"Warning: {w} CSV not found at {csv_path}")
            continue
            
        df = pd.read_csv(csv_path)
        dfs[w] = df
        
        summary_md.append(f"## Window: {w}")
        summary_md.append(f"**Points Run**: {len(df)}")
        
        # 1. Pivot Table (Return %)
        # Filter for OK rows only for surface maps
        ok_df = df[df.get("status", "OK") == "OK"]
        fail_df = df[df.get("status", "OK") != "OK"]
        
        if not fail_df.empty:
            summary_md.append(f"**Failures Detected**: {len(fail_df)} points failed.")
            # Summarize reasons
            if "error_reason" in fail_df.columns:
                reasons = fail_df["error_reason"].value_counts().to_dict()
                summary_md.append("Failure Reasons:")
                for r, c in reasons.items():
                    summary_md.append(f"- {r}: {c}")
            summary_md.append("")

        # Helper to piv and save
        def save_pivot(val_col, fname):
            try:
                # Fill na with 0 just for pivot visualization or leave empty
                pivot = ok_df.pivot(index="min_adx", columns="max_exp_move_bps", values=val_col)
                p_path = os.path.join(grid_dir, fname)
                pivot.to_csv(p_path)
                return os.path.basename(p_path)
            except Exception as e:
                return f"Error: {e}"

        map_ret = save_pivot("return_pct", f"surface_return_{w}.csv")
        map_trd = save_pivot("trades", f"surface_trades_{w}.csv")
        map_wr  = save_pivot("wr_pct", f"surface_wr_{w}.csv")
        
        summary_md.append(f"- **Return Map**: [{map_ret}]({map_ret})")
        summary_md.append(f"- **Trades Map**: [{map_trd}]({map_trd})")
        summary_md.append(f"- **WinRate Map**: [{map_wr}]({map_wr})")

        # 2. Top 5 Configs (Sort by return_pct, handling NaNs)
        valid_df = ok_df.dropna(subset=["return_pct"])
        top5 = valid_df.sort_values(by="return_pct", ascending=False).head(5)
        
        summary_md.append("### Top 5 Configs")
        summary_md.append("| Rank | Config | Return% | PnL | Trades | WR% |")
        summary_md.append("|---|---|---|---|---|---|")
        
        for i, (idx, row) in enumerate(top5.iterrows()):
            summary_md.append(f"| {i+1} | `{row['combo']}` | {row['return_pct']:.2f}% | {row['net_pnl']:.2f} | {row['trades']} | {row['wr_pct']:.1f}% |")
        summary_md.append("")
        
        # 3. Sensitivity / Diversity
        fingerprints = df['scenario_fingerprint'].nunique()
        summary_md.append(f"**Diversity**: {fingerprints} unique signatures out of {len(df)} runs.")
        summary_md.append("")

    # 4. Stability Analysis (Join In vs Out)
    if "INSAMPLE" in dfs and "OUTSAMPLE" in dfs:
        summary_md.append("## Stability Analysis (In vs Out)")
        # Use dropna to ensure we only compare valid runs
        in_df = dfs["INSAMPLE"].dropna(subset=["return_pct"]).set_index("combo")[["return_pct", "net_pnl", "trades"]]
        out_df = dfs["OUTSAMPLE"].dropna(subset=["return_pct"]).set_index("combo")[["return_pct", "net_pnl", "trades"]]
        
        joined = in_df.join(out_df, lsuffix="_in", rsuffix="_out", how="inner")
        
        # Criteria: Positive in BOTH
        stable = joined[(joined["return_pct_in"] > 0) & (joined["return_pct_out"] > 0)].copy()
        summary_md.append(f"**Stable Configs** (Positive in BOTH): {len(stable)}")
        
        if not stable.empty:
            summary_md.append("| Config | Return(In) | Return(Out) | Total Return |")
            summary_md.append("|---|---|---|---|")
            stable["total_ret"] = stable["return_pct_in"] + stable["return_pct_out"]
            stable = stable.sort_values(by="total_ret", ascending=False)
            
            for combo, row in stable.head(10).iterrows():
                summary_md.append(f"| `{combo}` | {row['return_pct_in']:.2f}% | {row['return_pct_out']:.2f}% | {row['total_ret']:.2f}% |")
        else:
            summary_md.append("No config was positive in both windows.")
    else:
        summary_md.append("## Stability Analysis\nSkipped: Requires both INSAMPLE and OUTSAMPLE results.")

    # Save MD
    md_path = os.path.join(grid_dir, "phase17_surface_summary.md")
    with open(md_path, 'w') as f:
        f.write("\n".join(summary_md))
    
    print(f"Summary Report generated: {md_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("grid_dir", help="Path to grid run directory (e.g. runs/phase17_grid_...)")
    args = parser.parse_args()
    
    if not os.path.isdir(args.grid_dir):
        print("Invalid directory")
        sys.exit(1)
        
    generate_surface(args.grid_dir)

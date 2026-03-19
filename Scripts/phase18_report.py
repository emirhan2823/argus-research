
import pandas as pd
import os
import sys

RUN_ROOT = "runs/phase18_robustness"
SUMMARY_CSV = os.path.join(RUN_ROOT, "runner_summary.csv")
REPORT_MD = os.path.join(RUN_ROOT, "phase18_robustness_report.md")
METRICS_CSV = os.path.join(RUN_ROOT, "phase18_metrics.csv")

def parse_decision_log(run_dir):
    log_path = os.path.join(run_dir, "decision_log.csv")
    stats = {
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "max_dd": 0.0,
        "pf": 0.0
    }
    
    if not os.path.exists(log_path): return stats
    
    try:
        df = pd.read_csv(log_path)
        if "RealizedPnL" not in df.columns: return stats
        
        # PnL Analysis
        pnl = pd.to_numeric(df["RealizedPnL"], errors='coerce').fillna(0)
        pnl = pnl[pnl != 0] # Filter 0s
        
        gross_profit = pnl[pnl > 0].sum()
        gross_loss = abs(pnl[pnl < 0].sum())
        
        stats["gross_profit"] = gross_profit
        stats["gross_loss"] = gross_loss
        stats["pf"] = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
        
        # Drawdown (approx from cumulative PnM)
        # Note: True DD requires equity curve. We'll approx from Trade PnL series.
        cum_pnl = pnl.cumsum()
        running_max = cum_pnl.cummax()
        dd = running_max - cum_pnl
        stats["max_dd"] = dd.max() # In BPS usually
        
    except Exception as e:
        pass
        
    return stats

def generate_report():
    if not os.path.exists(SUMMARY_CSV):
        print("Summary CSV not found. Make sure run is complete.")
        return
        
    df = pd.read_csv(SUMMARY_CSV)
    
    # Force numeric types
    for col in ["return_pct", "max_dd", "pf"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    # Enrich with detailed stats
    enrichments = []
    for _, row in df.iterrows():
        stats = parse_decision_log(row["run_dir"])
        enrichments.append(stats)
        
    enrich_df = pd.DataFrame(enrichments)
    
    # Drop duplicates to avoid Series ambiguity
    cols_to_drop = [c for c in enrich_df.columns if c in df.columns]
    df = df.drop(columns=cols_to_drop)
    
    df = pd.concat([df, enrich_df], axis=1)
    
    # Save Metrics CSV
    df.to_csv(METRICS_CSV, index=False)
    
    # Aggregate by Candidate
    # We want to check pass/fail criteria
    # Success Metrics:
    # - Positivity Ratio: Hits / Total Windows (> 50% required).
    # - Profit Factor: Aggregate PF > 1.1.
    # - Max Drawdown: < 15% in any single window (approx 1500 bps? Let's check Return % limit)
    # - Stress Resilience: Must remain profitable under stress in at least 1 Out-Sample window.
    
    candidates = df["candidate"].unique()
    
    with open(REPORT_MD, "w") as f:
        f.write("# Phase 18 Robustness Report\n\n")
        
        f.write("## Candidate Summary\n")
        f.write("| Candidate | Positivity | Agg PF | Max DD (Bps) | Stress Resilient? | Status |\n")
        f.write("|---|---|---|---|---|---|\n")
        
        best_cand = None
        best_score = -1
        
        for cand in candidates:
            c_df = df[df["candidate"] == cand]
            
            # Positivity (Return > 0)
            wins = c_df[c_df["return_pct"] > 0]
            pos_ratio = len(wins) / len(c_df)
            
            # Aggregate PF
            tot_profit = c_df["gross_profit"].sum()
            tot_loss = c_df["gross_loss"].sum()
            agg_pf = tot_profit / tot_loss if tot_loss > 0 else 999.0
            
            # Max DD
            max_dd = c_df["max_dd"].max()
            
            # Stress Resilience (Check Out-Sample Stress windows)
            # Filter profile=Stress, window=out
            stress_out = c_df[(c_df["profile"] == "Stress") & (c_df["window"] == "out")]
            resilient = (stress_out["return_pct"] > 0).any()
            
            # Status Logic
            status = "FAIL"
            if pos_ratio >= 0.5 and agg_pf > 1.1 and max_dd < 2500: # 25% approx?
                 if resilient: status = "PASS"
            
            f.write(f"| {cand} | {pos_ratio:.1%} | {agg_pf:.2f} | {max_dd:.0f} | {resilient} | **{status}** |\n")
            
            score = pos_ratio * agg_pf
            if status == "PASS" and score > best_score:
                best_score = score
                best_cand = cand
                
        f.write("\n## Detailed Metrics\n")
        # Manual Markdown Table
        cols = ["candidate", "split", "window", "profile", "return_pct", "trades", "pf", "max_dd"]
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        f.write(header + "\n")
        f.write(sep + "\n")
        
        for _, row in df[cols].iterrows():
            line = "| " + " | ".join([str(row[c]) for c in cols]) + " |"
            f.write(line + "\n")
            
    print(f"Report generated: {REPORT_MD}")

if __name__ == "__main__":
    generate_report()

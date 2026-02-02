import os
import json
import csv
import pandas as pd
from typing import Dict, Any

def generate_report(run_dir: str):
    """
    Generates a generic markdown report for the run.
    """
    report_path = os.path.join(run_dir, "report.md")
    
    try:
        # Load Config
        config = {}
        config_path = os.path.join(run_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)

        # Load Summary
        summary = {}
        summary_path = os.path.join(run_dir, "summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, 'r') as f:
                summary = json.load(f)

        # Start Report
        lines = []
        lines.append(f"# Argus Run Report")
        lines.append(f"**Run ID:** `{os.path.basename(run_dir)}`")
        lines.append(f"**Symbol:** {config.get('symbol', 'N/A')} | **Mode:** {config.get('mode', 'N/A')}")
        lines.append("")

        # 0. Data Summary
        if 'data_summary' in summary:
             ds = summary['data_summary']
             lines.append("## Data Summary")
             lines.append(f"**Bars:** {ds.get('bars', 0)} | **From:** {ds.get('start_date', 'N/A')} | **To:** {ds.get('end_date', 'N/A')}")
             lines.append(f"**Price Range:** {ds.get('min_price', 0):.2f} - {ds.get('max_price', 0):.2f}")
             lines.append("")
             
        # 1. Performance Summary
        lines.append("## Performance Summary")
        if summary:
            lines.append("| Metric | Value |")
            lines.append("|---|---|")
            lines.append(f"| Total Return | {summary.get('total_return_pct', 0):.2f}% |")
            lines.append(f"| Max Drawdown | {summary.get('max_drawdown_pct', 0):.2f}% |")
            lines.append(f"| Final Equity | ${summary.get('final_equity', 0):.2f} |")
            lines.append(f"| Total Trades | {summary.get('total_trades', 0)} |")
            lines.append(f"| Win Rate | {summary.get('win_rate', 0)*100:.1f}% |")
            lines.append(f"| Profit Factor | {summary.get('profit_factor', 0):.2f} |")
        else:
            lines.append("_No summary.json found._")
        lines.append("")

        # 2. Charts
        lines.append("## Visualization")
        lines.append("![Equity Curve](equity.png)")
        lines.append("![Drawdown Curve](drawdown.png)")
        lines.append("")

        # 3. Parameters
        lines.append("## Parameters")
        lines.append("| Param | Value |")
        lines.append("|---|---|")
        lines.append(f"| Fee (bps) | {config.get('fee_bps', 'N/A')} |")
        lines.append(f"| Slippage (bps) | {config.get('slippage_bps', 'N/A')} |")
        lines.append(f"| Spread (bps) | {config.get('spread_bps', 'N/A')} |")
        lines.append(f"| Use Bid/Ask | {config.get('use_bid_ask', False)} |")
        lines.append(f"| Max Risk Cap | {config.get('max_risk_per_trade_pct', 'N/A')}% |")
        lines.append(f"| Liq Margin | {config.get('liq_safety_margin_pct', 'N/A')}% |")
        lines.append("")
        
        # 3b. Configuration JSON
        lines.append("<details>")
        lines.append("<summary>Full Config JSON</summary>")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(config, indent=2))
        lines.append("```")
        lines.append("</details>")
        lines.append("")
        
        # 3c. Trade Analysis (Histogram & Top/Bottom)
        trades_path = os.path.join(run_dir, "trades.csv")
        if os.path.exists(trades_path):
             try:
                 df_t = pd.read_csv(trades_path)
                 # Filter for CLOSE events
                 commits = df_t[df_t['Event'] == 'CLOSE']
                 if not commits.empty and 'PnL' in commits.columns:
                     pnl_vals = commits['PnL'].sort_values()
                     
                     # Top 5 Winners
                     lines.append("### Top Winners")
                     lines.append(commits.nlargest(5, 'PnL')[['Timestamp', 'Symbol', 'Side', 'PnL', 'Comm']].to_markdown(index=False))
                     lines.append("")
                     
                     # Top 5 Losers
                     lines.append("### Top Losers")
                     lines.append(commits.nsmallest(5, 'PnL')[['Timestamp', 'Symbol', 'Side', 'PnL', 'Comm']].to_markdown(index=False))
                     lines.append("")
                     
                     # ASCII Histogram
                     lines.append("### PnL Distribution")
                     lines.append("```text")
                     # Simple bucket logic
                     min_p = pnl_vals.min()
                     max_p = pnl_vals.max()
                     count = len(pnl_vals)
                     if count > 0 and max_p > min_p:
                         bins = 10
                         step = (max_p - min_p) / bins
                         for i in range(bins):
                             lo = min_p + i*step
                             hi = min_p + (i+1)*step
                             c = ((pnl_vals >= lo) & (pnl_vals < hi)).sum()
                             # Last bin includes max
                             if i == bins-1: c += (pnl_vals >= hi).sum()
                             
                             bar = "#" * c
                             lines.append(f"{lo:8.2f} .. {hi:8.2f} : {c:3d} | {bar}")
                     else:
                         lines.append("Not enough variance for histogram.")
                     lines.append("```")
                     lines.append("")
             except Exception as e:
                 lines.append(f"_Analysis Error: {e}_")


        # 4. Signal Stats (from Decision Log)
        decision_log_path = os.path.join(run_dir, "decision_log.csv")
        if os.path.exists(decision_log_path):
            lines.append("## Signal Analysis")
            try:
                df = pd.read_csv(decision_log_path)
                
                # Block Reasons
                if 'BlockReason' in df.columns:
                    block_counts = df['BlockReason'].value_counts()
                    lines.append("### Block Reasons")
                    lines.append("| Reason | Count |")
                    lines.append("|---|---|")
                    for reason, count in block_counts.items():
                        lines.append(f"| {reason} | {count} |")
                    lines.append("")
                
                # Conviction Stats
                if 'Conviction' in df.columns:
                    avg_conv = df['Conviction'].mean()
                    max_conv = df['Conviction'].max()
                    lines.append(f"**Avg Conviction:** {avg_conv:.2f} | **Max Conviction:** {max_conv:.2f}")

                # Monitoring Hooks (Daily Report)
                if 'OrionADX' in df.columns:
                    avg_adx = df['OrionADX'].mean()
                    max_adx = df['OrionADX'].max()
                    lines.append(f"**Avg ADX:** {avg_adx:.1f} | **Max ADX:** {max_adx:.1f}")

                if 'Regime' in df.columns:
                    regime_counts = df['Regime'].value_counts()
                    total_ticks = len(df)
                    if total_ticks > 0:
                        lines.append(f"**Regime Dist:** Trend: {regime_counts.get('TREND', 0)/total_ticks*100:.1f}% | Chop: {regime_counts.get('CHOP', 0)/total_ticks*100:.1f}%")


            except Exception as e:
                lines.append(f"_Error analyzing decision log: {e}_")
        lines.append("")

        # 5. Last 10 Trades
        trades_path = os.path.join(run_dir, "trades.csv")
        if os.path.exists(trades_path):
            lines.append("## Last 10 Trades")
            try:
                trades_df = pd.read_csv(trades_path)
                # Filter for CLOSE events or just show raw
                # Let's show last 10 raw fills
                tail = trades_df.tail(10)
                # Convert to markdown table
                lines.append(tail.to_markdown(index=False))
            except Exception as e:
                lines.append(f"_Error reading trades: {e}_")
        lines.append("")

        # Write Report
        with open(report_path, 'w') as f:
            f.write("\n".join(lines))
        
        print(f"Report generated: {report_path}")

    except Exception as e:
        print(f"Failed to generate report: {e}")

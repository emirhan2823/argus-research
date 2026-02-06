import os
import sys
import pandas as pd
import glob
import json

def analyze_pack(pack_dir):
    print(f"Analyzing pack: {pack_dir}")
    report_path = os.path.join(pack_dir, "diagnostics.md")
    
    # Check scenarios
    scenarios = sorted([d for d in os.listdir(pack_dir) if os.path.isdir(os.path.join(pack_dir, d))])
    
    lines = []
    lines.append(f"| # Pack Diagnostics: {os.path.basename(pack_dir)}")
    lines.append("| Scenario | Net PnL | Grs PnL | Fees | SlipCost | Trades (Ev) | WR% | AvgHold | Sc(p95) | RejCost | Exp/Cost (r) | Exit |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    
    for sc in scenarios:
        sc_dir = os.path.join(pack_dir, sc)
        trades_path = os.path.join(sc_dir, "trades.csv")
        config_path = os.path.join(sc_dir, "config.json")
        
        if not os.path.exists(trades_path):
            continue
            
        try:
            df = pd.read_csv(trades_path)
            # Filter Closed Trades
            closed = df[df['Event'] == 'CLOSE']
            
            # Load Config for cost est
            cfg = {}
            if os.path.exists(config_path):
                with open(config_path) as f: cfg = json.load(f)
                
            spread_bps = cfg.get("spread_bps", 1.0)
            slip_bps = cfg.get("slippage_bps", 2.0)
            
            # Metrics
            net_pnl = closed['PnL'].sum() if not closed.empty else 0.0
            fees = closed['Comm'].sum()
            
            # Note: In PaperBroker, Net = Gross - Comm. So Gross = Net + Comm.
            # But wait, did we verify this?
            # Broker: `gross = (price - entry) * qty`. `net = gross - comm`.
            # Yes.
            # But `Comm` in trades.csv is only EXIT comm.
            # Entry comm is lost in history unless we sum OPEN events too?
            # Broker logic: `trades.append(TradeFill(..., "OPEN", ..., comm, ...))`
            # So `df['Comm'].sum()` sums BOTH Open and Close commissions if we look at ALL rows.
            # Let's check if we filtered for CLOSE only?
            # If we filter CLOSE, we only get Exit comms.
            # But the 'Net' in CLOSE row *includes* entry comm deduction?
            # `net = gross - comm - (pos.entry_price * pos.quantity * 0.001)` (old code)
            # `net = gross - comm` (new code).
            # Wait, in new code step 487/488:
            # `net = gross - comm`.
            # Where `gross` is raw price diff.
            # So `Net` in CLOSE row is PnL of that specific EXIT transaction?
            # No, usually "Trade PnL" implies the whole round trip.
            # The previous code had: `net = gross - comm - (pos.entry_price * pos.quantity * 0.001)`.
            # My edit removed the entry comm deduction from `net` calc?
            # Let's check `_close_position` in `paper.py` again.
            
            # Re-verifying logic in Diagnostics:
            # Total Net PnL of the account = Final Equity - Start Equity.
            # Sum of `PnL` column in `trades.csv` (CLOSE rows) should ideally match this?
            # If my `Net` calc is just `ExitGross - ExitComm`, then I am missing EntryComm.
            # So Total PnL = Sum(Net on Close) - Sum(Comm on Open).
            
            # Let's calculate from TOTAL `Comm` column (Open + Close).
            all_comm = df['Comm'].sum()
            
            # Gross PnL from Price Diff (Theoretical)
            # We can reconstruct it:
            # For each CLOSE:
            # Quantity * (ExitPrice - EntryPrice) * SideMultiplier
            # But we don't have EntryPrice in CLOSE row easily (unless we track it).
            # We can approximate: Net PnL + All Fees?
            # Validating: NetPnL (Account) = Gross - Fees.
            # So Gross = NetPnL + Fees.
            
            # Let's use Account Equity change as Truth for Net PnL.
            # Or use `summary.json` 'total_return_pct'.
            
            # Let's calculate:
            # Net PnL = Sum(PnL column in CLOSE) ?? -> Likely inaccurate if I messed up the calc.
            # Let's use `Sum(Net)` from CLOSE rows calculating `(Exit-Entry)*Qty - Comms`.
            # I suspect my `paper.py` update might have simplistic `Net` calc.
            # I will trust `all_comm` as Total Fees.
            # And `Gross` = `Net_Account_Change` + `all_comm`.
            
            
            # (Original Slippage Cost block deleted)

            # Stats
            count = len(closed)
            wins = len(closed[closed['PnL'] > 0]) # Note: PnL here depends on faulty calc?
            # Actually just trust the PnL column for Win/Loss classification.
            wr = (wins / count * 100) if count > 0 else 0
            
            gross_win = closed[closed['PnL'] > 0]['PnL'].sum()
            gross_loss = abs(closed[closed['PnL'] <= 0]['PnL'].sum())
            pf = (gross_win / gross_loss) if gross_loss > 0 else 0
            
            # Hold time
            # Timestamp diff? We need OPEN timestamps.
            # This is hard without linking rows.
            # Approximation: `bars_held` is not in CSV.
            # Skip avg hold for now or mock it 0.
            
            # Reasons
            # Reason format: "SELL_TP", "BUY_SL"
            reasons = closed['Event'].apply(lambda x: x.split('_')[-1] if '_' in x else x)
            r_counts = reasons.value_counts().to_dict()
            # Robust Column Mapping
            cols = df.columns
            # 1. Qty
            qty_col = next((c for c in ["Qty","qty","Quantity","quantity","QTY"] if c in cols), None)
            # 2. Comm
            comm_col = next((c for c in ["Comm","comm","Commission","commission","FEE","fee"] if c in cols), None)
            # 3. PnL 
            pnl_col = next((c for c in ["PnL","pnl","RealizedPnL","realized_pnl"] if c in cols), None)
            
            if not qty_col or not comm_col or not pnl_col:
                lines.append(f"| {sc} | Error | Missing Cols: {qty_col}/{comm_col}/{pnl_col} | | | | | | | |")
                continue
                
            # Filter Closed Trades
            # Closed trades usually identified by Event="CLOSE" or side containing "EOS/TP/SL"
            # If Event col exists use it
            if 'Event' in cols:
                closed = df[df['Event'] == 'CLOSE']
            else:
                # Heuristic: Side contains _EOS, _TP, _SL
                closed = df[df['Side'].str.contains('_EOS|_TP|_SL', na=False)]

            
            # Load Config for cost est or check columns
            cfg = {}
            if os.path.exists(config_path):
                with open(config_path) as f: cfg = json.load(f)
                
            spread_bps = cfg.get("spread_bps", 1.0)
            slip_bps = cfg.get("slippage_bps", 2.0)
            
            # Metrics
            net_pnl = closed[pnl_col].sum() if not closed.empty else 0.0
            
            # Fee logic: Sum ALL commissions (Open+Close) because Close row usually only has Exit Fee
            # Assuming dataframe contains all fills (Open and Close)
            all_comm = df[comm_col].sum() if not df.empty else 0.0
            
            # Calculate Gross PnL (Account view)
            # Net Account PnL = Sum(Net PnL on Closes) ? 
            # If PaperBroker NetPnL = (Gross - ExitFee), then we are missing EntryFee deduction from PnL?
            # Actually PaperBroker deducts EntryFee from Balance on Open.
            # And calculates NetPnL on Close as (Gross - ExitFee - EntryFee)?
            # No, looking at code: `net = gross - comm`. (Only exit fee).
            # So `closed['PnL'].sum()` is Gross - ExitFees.
            # Total Account Change = Sum(NetPnL) - Sum(EntryFees).
            # Total Fees = Sum(EntryFees) + Sum(ExitFees) = `all_comm`.
            # So Real Net PnL = Sum(NetPnL_in_row) - Sum(EntryFees).
            # This is confusing. Let's look at Equity or Balance change.
            # We don't have equity history here easily.
            # Let's approximate:
            # Grs PnL = NetPnL + ExitFees.
            # Real Net = Grs PnL - AllFees.
            
            exit_fees = closed[comm_col].sum() if not closed.empty else 0.0
            gross_pnl = net_pnl + exit_fees
            real_net_pnl = gross_pnl - all_comm
            
            # Slippage Cost Calculation
            # Method A: Real "FillPrice" vs "MarkPrice" columns
            # Method B: Estimate if cols missing
            
            # Est Slippage Cost
            # Method A: Real "FillPrice" vs "MarkPrice" columns
            # Method B: Estimate if cols missing
            
            slip_cost = 0.0
            if 'FillPrice' in cols and 'MarkPrice' in cols:
                # Calculate for ALL rows (Entry and Exit)
                # Cost = abs(Fill - Mark) * Qty
                # Ensure Qty is absolute
                df['slip_delta'] = (df['FillPrice'] - df['MarkPrice']).abs() * df[qty_col].abs()
                slip_cost = df['slip_delta'].sum()
            else:
                # Estimate
                total_vol = (df['Price'] * df[qty_col]).sum()
                use_bid_ask = cfg.get('use_bid_ask', False)
                est_bps = slip_bps + (spread_bps if use_bid_ask else 0)
                slip_cost = total_vol * (est_bps / 10000.0)
            
            est_slip_cost = slip_cost

            
            # Stats
            count = closed['PositionId'].nunique() if 'PositionId' in cols else len(closed)
            events_count = len(df)
            
            wins = len(closed[closed[pnl_col] > 0]) 
            wr = (wins / count * 100) if count > 0 else 0
            
            gross_win = closed[closed[pnl_col] > 0][pnl_col].sum()
            gross_loss = abs(closed[closed[pnl_col] <= 0][pnl_col].sum())
            pf = (gross_win / gross_loss) if gross_loss > 0 else 0
            
            # Hold time (Avg minutes)
            avg_hold_m = 0
            if 'PositionId' in cols and count > 0:
                # Group by PosID
                # Find min timestamp (open) and max timestamp (close)
                # Assuming Timestamp is seconds
                gr = df.groupby('PositionId')['Timestamp'].agg(['min','max'])
                durations = gr['max'] - gr['min']
                avg_hold_m = (durations.mean() / 60.0)
            
            # Reasons
            # Reason format: "SELL_TP", "BUY_SL"
            # If Event is "CLOSE", look at Side or extra data
            # Broker logs Side="SELL_TP" in trades.csv?
            # Yes: `f"{close_side}_{reason}"` is passed as `side`.
            # Wait, `TradeFill` has `side` and `event`.
            # `TradeFill(..., side=f"{close_side}_{reason}", ..., event="CLOSE")`
            # So `Side` column contains "SELL_TP".
            
            reasons_series = closed['Side'].apply(lambda x: x.split('_')[-1] if '_' in x else x)
            r_counts = reasons_series.value_counts().to_dict()
            r_str = ", ".join([f"{k}:{v}" for k,v in r_counts.items()])
            
            # Load Score Stats (Handle Legacy and New Structure)
            stats_path = os.path.join(sc_dir, "score_stats.json")
            sc_p95 = "-"
            sc_p99 = "-"
            if os.path.exists(stats_path):
                with open(stats_path) as f:
                    try:
                        sdata = json.load(f)
                        # Check for new structure "calibration_source"
                        if "calibration_source" in sdata:
                            src = sdata["calibration_source"]
                            nested = sdata.get(src, {})
                            if nested.get("count", 0) > 0:
                                sc_p95 = f"{nested.get('p95', 0):.1f}"
                                sc_p99 = f"{nested.get('p99', 0):.1f}"
                        # Legacy/Direct keys
                        elif sdata.get("count", 0) > 0:
                            sc_p95 = f"{sdata.get('p95', 0):.1f}"
                            sc_p99 = f"{sdata.get('p99', 0):.1f}"
                    except: pass

            # Load Rejects
            rejects_path = os.path.join(sc_dir, "rejects.csv")
            rej_cost_count = 0
            if os.path.exists(rejects_path):
                 try:
                     df_rej = pd.read_csv(rejects_path)
                     if 'Reason' in df_rej.columns:
                         rej_cost_count = len(df_rej[df_rej['Reason'] == 'REJECT_EDGE_COST'])
                 except: pass

            # Load Explanations for E/C Ratio
            exp_path = os.path.join(sc_dir, "homerun_explain.csv")
            dec_path = os.path.join(sc_dir, "decision_log.csv")
            
            ec_mean = 0.0
            avg_exp = 0.0
            avg_cost = 0.0
            
            # Source 1: HomeRun Explain
            if os.path.exists(exp_path):
                 try:
                     df_exp = pd.read_csv(exp_path)
                     if 'expected_move_bps' in df_exp.columns:
                         # Cost = fee + slip + spread
                         cost = df_exp['fee_bps'] + df_exp['slip_bps'] + df_exp['spread_bps'] if 'fee_bps' in df_exp.columns else cfg.get('fee_bps', 4)+cfg.get('slippage_bps',2)+cfg.get('spread_bps',1)
                         
                         df_exp['ec'] = df_exp['expected_move_bps'] / cost
                         ec_mean = df_exp['ec'].mean()
                         avg_exp = df_exp['expected_move_bps'].mean()
                         avg_cost = cost.mean()
                 except: pass

            # Source 2: Decision Log fallback
            if ec_mean == 0.0 and os.path.exists(dec_path):
                 try:
                     df_dec = pd.read_csv(dec_path)
                     if 'ExpMove' in df_dec.columns and not df_dec.empty:
                         # Filter for Trades using OPEN timestamps
                         # df has Trades
                         if 'Timestamp' in df.columns:
                             # Use Timestamps from Executed OPEN trades
                             exec_ts = df[df['Event'] == 'OPEN']['Timestamp'].tolist() if 'Event' in df.columns else df['Timestamp'].tolist()
                             
                             # Filter Decision Log
                             # Use approx match or exact? CLi uses exact timestamp.
                             rel = df_dec[df_dec['Timestamp'].isin(exec_ts)].copy()
                             
                             if not rel.empty:
                                 avg_exp = rel['ExpMove'].mean()
                                 if 'Cost' in rel.columns and rel['Cost'].sum() > 0:
                                     avg_cost = rel['Cost'].mean()
                                 else:
                                     avg_cost = float(slip_bps + spread_bps + 4.0) # approx fallback
                                     
                                 if avg_cost > 0:
                                     # Cal E/C
                                     if 'Cost' in rel.columns and rel['Cost'].sum() > 0:
                                         rel['ec'] = rel['ExpMove'] / rel['Cost']
                                         ec_mean = rel['ec'].mean()
                                     else:
                                         ec_mean = avg_exp / avg_cost
                 except: pass

            lines.append(f"| {sc} | {real_net_pnl:.2f} | {gross_pnl:.2f} | {all_comm:.2f} | {est_slip_cost:.2f} | {count} ({events_count}) | {wr:.1f} | {avg_hold_m:.0f} | {sc_p95} | {rej_cost_count} | {avg_exp:.1f}/{avg_cost:.1f} (r={ec_mean:.1f}) | {r_str} |")
            
        except Exception as e:
            lines.append(f"| {sc} | Error | {e} | | | | | | | |")
            
    with open(report_path, 'w') as f:
        f.write("\n".join(lines))
        
        # --- Top Winners Section (New) ---
        f.write("\n\n## Top Winners (PnL)\n")
        f.write("| Scenario | Timestamp | Side | PnL | Price | Duration (m) |\n")
        f.write("|---|---|---|---|---|---|\n")
        
        winners = []
        for sc in scenarios:
            sc_dir = os.path.join(pack_dir, sc)
            tp = os.path.join(sc_dir, "trades.csv")
            if os.path.exists(tp):
                try:
                    d = pd.read_csv(tp)
                    # Filter closes
                    cl = d[d['Event'] == 'CLOSE'] if 'Event' in d.columns else d[d['Side'].str.contains('_EOS|_TP|_SL', na=False)]
                    if not cl.empty:
                        # Ensure 'PnL' exists (robustness)
                        p_col = next((c for c in cl.columns if c.lower() in ['pnl','realizedpnl']), None)
                        if p_col:
                             w_df = cl[cl[p_col] > 0].copy()
                             for _, w in w_df.iterrows():
                                 winners.append({
                                     "sc": sc,
                                     "ts": w['Timestamp'],
                                     "side": w['Side'],
                                     "pnl": w[p_col],
                                     "price": w['Price']
                                 })
                except: pass
        
        winners.sort(key=lambda x: x['pnl'], reverse=True)
        for w in winners[:10]:
            f.write(f"| {w['sc']} | {w['ts']} | {w['side']} | {w['pnl']:.2f} | {w['price']:.2f} | - |\n")

        # --- HomeRun Traces ---
        f.write("\n\n## HomeRun Trade Explanations (Top 10 High Score)\n")
        f.write("| Timestamp | Score | Thresh | Regime | Slope | ADX | Dir | ExpMove |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        
        all_explanations = []
        for sc in scenarios:
             sc_dir = os.path.join(pack_dir, sc)
             exp_path = os.path.join(sc_dir, "homerun_explain.csv")
             if os.path.exists(exp_path):
                 try:
                     exps = pd.read_csv(exp_path)
                     for _, row in exps.iterrows():
                         all_explanations.append(row.to_dict())
                 except: pass
        
        all_explanations.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        for exp in all_explanations[:10]:
            ts = exp.get('dt', exp.get('timestamp'))
            sc = exp.get('score', 0)
            th = exp.get('threshold', 0)
            rg = exp.get('regime', '-')
            sl = exp.get('slope_net', 0)
            adx = exp.get('adx', 0)
            dr = exp.get('direction', '-')
            em = exp.get('expected_move_bps', 0)
            f.write(f"| {ts} | {sc:.1f} | {th:.1f} | {rg} | {sl:.1f} | {adx:.1f} | {dr} | {em:.1f} |\n")


        # --- Blocked Trades Section (Robust Regex) ---
        f.write("\n\n## Top Blocked Trades (Cost Filter Rejects)\n")
        f.write("| Scenario | Timestamp | Score | ExpMove | Cost | Safety |\n")
        f.write("|---|---|---|---|---|---|\n")
        
        blocked_list = []
        import re
        # Pattern: Exp:{val} ... Cost:{val}*{val}
        # Example: "Exp:22.0 (Sl:18/ATR:12) < Cost:10.0*2.0"
        pat = re.compile(r"Exp:([\d\.]+).*Cost:([\d\.]+)\*([\d\.]+)")
        
        for sc in scenarios:
             sc_dir = os.path.join(pack_dir, sc)
             rp = os.path.join(sc_dir, "rejects.csv")
             if os.path.exists(rp):
                 try:
                     dr = pd.read_csv(rp)
                     dr.columns = [c.capitalize() for c in dr.columns]
                     if 'Reason' in dr.columns:
                         costs = dr[dr['Reason'] == "REJECT_EDGE_COST"]
                         for _, row in costs.iterrows():
                             try:
                                 det = row['Details']
                                 m = pat.search(det)
                                 exp_v = 0
                                 cost_v = 0
                                 safe_v = 0
                                 if m:
                                     exp_v = float(m.group(1))
                                     cost_v = float(m.group(2))
                                     safe_v = float(m.group(3))
                                 
                                 score_v = float(row['Meta']) if pd.notnull(row['Meta']) else 0.0
                                 
                                 blocked_list.append({
                                     "sc": sc,
                                     "ts": row['Timestamp'],
                                     "score": score_v,
                                     "exp": exp_v,
                                     "cost": cost_v,
                                     "safe": safe_v
                                 })
                             except: pass
                 except: pass

        blocked_list.sort(key=lambda x: x['score'], reverse=True)
        for b in blocked_list[:10]:
             f.write(f"| {b['sc']} | {b['ts']} | {b['score']:.1f} | {b['exp']:.1f} | {b['cost']:.1f} | {b['safe']:.1f} |\n")


        # --- Phase 14: Variant Fingerprinting & Gate Breakdown ---
        f.write("\n## Scenario Fingerprints & Gate Attribution\n")
        f.write("| Scenario | Trades | GoSignals | TradeHash | GoHash | Gate: MIN_ADX | Gate: COST | Gate: VOL_TRAP | Gate: MAX_EXP | Other |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")

        import hashlib
        
        for sc in scenarios:
            sc_dir = os.path.join(pack_dir, sc)
            tp = os.path.join(sc_dir, "trades.csv")
            dl = os.path.join(sc_dir, "decision_log.csv")
            
            t_count = 0
            go_count = 0
            t_hash = "N/A"
            g_hash = "N/A"
            gate_counts = {"MIN_ADX":0, "COST":0, "VOL_TRAP":0, "MAX_EXP":0, "Other":0}
            
            if os.path.exists(dl):
                try:
                     df_d = pd.read_csv(dl)
                     # GO Hash
                     gos = df_d[df_d['Decision'] == 'GO']
                     go_count = len(gos)
                     if go_count > 0:
                         # Sort by TS
                         gos = gos.sort_values('Timestamp')
                         # Create signature string
                         sig = "".join([f"{r['Timestamp']}{r['Direction']}" for _, r in gos.iterrows()])
                         g_hash = hashlib.sha1(sig.encode()).hexdigest()[:8]
                         
                     # Gate Breakdown
                     blocks = df_d[df_d['Decision'] == 'BLOCK']
                     if not blocks.empty and 'BlockedReason' in blocks.columns:
                         counts = blocks['BlockedReason'].value_counts()
                         for reason, count in counts.items():
                             if reason in gate_counts:
                                 gate_counts[reason] = count
                             else:
                                 gate_counts["Other"] += count
                except: pass

            if os.path.exists(tp):
                try:
                    df_t = pd.read_csv(tp)
                    # Trade Hash (Completed Trades)
                    # Filter OPEN events
                    opens = df_t[df_t['Event'] == 'OPEN']
                    t_count = len(opens)
                    if t_count > 0:
                        opens = opens.sort_values('Timestamp')
                        # Sig: Ts + Dir + Price(Int)
                        sig = "".join([f"{r['Timestamp']}{r['Side']}{int(r['Price'])}" for _, r in opens.iterrows()])
                        t_hash = hashlib.sha1(sig.encode()).hexdigest()[:8]
                except: pass
                
            f.write(f"| {sc} | {t_count} | {go_count} | {t_hash} | {g_hash} | {gate_counts['MIN_ADX']} | {gate_counts['COST']} | {gate_counts['VOL_TRAP']} | {gate_counts['MAX_EXP']} | {gate_counts['Other']} |\n")

        f.write("\n")

        # --- Phase C.3: Calibration Dump & Reliability ---
        f.write("\n## ExpMove Calibration & Reliability (Binning & Correlation)\n")
        f.write("| Metric | Pearson (Linear) | Spearman (Rank) | Notes |\n")
        f.write("|---|---|---|---|\n")

        all_calibration_rows = []
        
        for sc in scenarios:
            sc_dir = os.path.join(pack_dir, sc)
            tp = os.path.join(sc_dir, "trades.csv")
            dl = os.path.join(sc_dir, "decision_log.csv")
            
            if os.path.exists(tp) and os.path.exists(dl):
                sc_rows = []
                try:
                    df_t = pd.read_csv(tp)
                    df_d = pd.read_csv(dl)
                    
                    if 'ExpMove' not in df_d.columns: continue
                    
                    # Merge logic (Entry)
                    entries = df_t[df_t['Event'] == 'OPEN'].copy()
                    entries['ts_int'] = entries['Timestamp'].astype(int)
                    df_d['ts_int'] = df_d['Timestamp'].astype(int)
                    merged = pd.merge(entries, df_d, on='ts_int', suffixes=('_t', '_d'))
                    
                    if not merged.empty:
                        # Map Exit Prices
                        exits = df_t[df_t['Event'] == 'CLOSE'].copy()
                        pid_map = {row['PositionId']: row for _, row in exits.iterrows()}
                        
                        for _, row in merged.iterrows():
                            pid = row['PositionId']
                            if pid in pid_map:
                                exit_row = pid_map[pid]
                                exit_price = exit_row['Price']
                                entry_price = row['Price']
                                exp_move = row['ExpMove']
                                cost_est = row['Cost'] if 'Cost' in row else 7.0
                                
                                # Regime/Score meta
                                score = row.get('Score', 0.0) # Not easily avail? We have 'Votes' string? 
                                # Actually we don't have raw Score column in decision log unless we parse?
                                # We have 'AegeanSlope', 'OrionADX'.
                                slope = row.get('AegeanSlope', 0.0)
                                adx = row.get('OrionADX', 0.0)
                                regime = row.get('Regime', 'N/A')
                                
                                # Direction
                                d_str = row['Direction'] # Decision Log Direction
                                direction = 1 if d_str == 'BUY' else -1
                                
                                # Sanity Check w/ Trade Side
                                t_side = row['Side'] # Trade Side (OPEN)
                                # If OPEN BUY -> Dir 1. If OPEN SELL -> Dir -1.
                                t_dir = 1 if t_side == 'BUY' else -1
                                if t_dir != direction: continue # Mismatch?
                                
                                # Realized Calc
                                realized_bps = ((exit_price - entry_price) / entry_price) * 10000.0 * direction
                                net_bps = realized_bps - cost_est
                                
                                row_data = {
                                    "Scenario": sc,
                                    "PositionId": pid,
                                    "EntryTs": row['Timestamp_t'],
                                    "ExitTs": exit_row['Timestamp'],
                                    "Direction": d_str,
                                    "EntryPrice": entry_price,
                                    "ExitPrice": exit_price,
                                    "ExpMove": exp_move,
                                    "Cost": cost_est,
                                    "Realized": realized_bps,
                                    "Net": net_bps,
                                    "Slope": slope,
                                    "ADX": adx,
                                    "Regime": regime,
                                    "ShiftScore": row.get('ShiftScore', 0.0),
                                    "ModeSuggest": row.get('ModeSuggest', 'N/A'),
                                    "ModeFinal": row.get('ModeFinal', 'N/A'),
                                    "Policy": row.get('Policy', 'N/A')
                                }
                                sc_rows.append(row_data)
                                all_calibration_rows.append(row_data)
                        
                        # DUMP SCENARIO SPECIFIC
                        if sc_rows:
                            sc_dump_path = os.path.join(sc_dir, "calibration_dump.csv")
                            pd.DataFrame(sc_rows).to_csv(sc_dump_path, index=False)
                            print(f"  [OK] {sc}: Generated {len(sc_rows)} calibration rows.")

                except Exception as e:
                     f.write(f"<!-- Error processing {sc}: {str(e)} -->\n")

        # 1. Dump CSV
        if all_calibration_rows:
            dump_df = pd.DataFrame(all_calibration_rows)
            dump_path = os.path.join(pack_dir, "calibration_dump.csv")
            dump_df.to_csv(dump_path, index=False)
            print(f"Dumped calibration data to {dump_path}")
            
            # 2. Correlations
            corr_p_real = dump_df['ExpMove'].corr(dump_df['Realized'], method='pearson')
            corr_p_net = dump_df['ExpMove'].corr(dump_df['Net'], method='pearson')
            
            try:
                corr_s_real = dump_df['ExpMove'].corr(dump_df['Realized'], method='spearman')
                s_real_str = f"{corr_s_real:.2f}"
            except:
                s_real_str = "N/A"
                
            try:
                corr_s_net = dump_df['ExpMove'].corr(dump_df['Net'], method='spearman')
                s_net_str = f"{corr_s_net:.2f}"
            except:
                s_net_str = "N/A"
            
            f.write(f"| Exp vs Realized | {corr_p_real:.2f} | {s_real_str} | Ground Truth |\n")
            f.write(f"| Exp vs Net | {corr_p_net:.2f} | {s_net_str} | After Cost |\n\n")
            
            # 3. Reliability Bins
            f.write("### Reliability (Monotonicity Check)\n")
            f.write("| Bin (ExpMove) | Count | AvgExp | AvgRealized | HitRate (>Cost) |\n")
            f.write("|---|---|---|---|---|\n")
            
            try:
                # QCut into bins (e.g. 5)
                # If too few data points, qcut fails.
                if len(dump_df) >= 5:
                    dump_df['Bin'] = pd.qcut(dump_df['ExpMove'], q=5, duplicates='drop')
                    # Group by Bin
                    grouped = dump_df.groupby('Bin', observed=True)
                    stats = grouped.agg({
                        'ExpMove': ['count', 'mean'],
                        'Realized': 'mean',
                        'Cost': 'mean' # to compare hitrate
                    })
                    
                    # HitRate manually
                    # Function to calc hitrate per group
                    # Function to calc hitrate per group
                    def calc_hr(g):
                        if len(g) == 0: return 0.0
                        return (len(g[g['Realized'] > g['Cost']]) / len(g)) * 100.0
                        
                    # Fix FutureWarning by excluding grouping keys
                    hitrates = grouped.apply(calc_hr, include_groups=False)
                    
                    # Iterate and Write
                    # stats.index is Interval
                    for interval, row in stats.iterrows():
                        count = int(row[('ExpMove', 'count')])
                        avg_exp = row[('ExpMove', 'mean')]
                        avg_real = row['Realized']['mean']
                        # Safe access if interval missing
                        hr = hitrates.get(interval, 0.0)
                        
                        f.write(f"| {interval} | {count} | {avg_exp:.1f} | {avg_real:.1f} | {hr:.1f}% |\n")
                else:
                    f.write("| All | " + str(len(dump_df)) + " | - | - | - |\n")
            except Exception as e:
                f.write(f"| Error Binning | {str(e)} | - | - | - |\n")

        else:
            f.write("No calibration data found.\n")

        # --- Cost Verification Fix ---
        f.write("\n\n## Cost Model Verification (Detailed)\n")
        f.write("| Scenario | Est Cost (Fee/Slip/Spread) | Actual (Fee/Slip) | Error (Est-Act) | Act Slip Bps |\n")
        f.write("|---|---|---|---|---|\n")
        
        for sc in scenarios:
             sc_dir = os.path.join(pack_dir, sc)
             tp = os.path.join(sc_dir, "trades.csv")
             cfg_p = os.path.join(sc_dir, "config.json")
             
             if os.path.exists(tp):
                 try:
                     df = pd.read_csv(tp)
                     
                     # Est Default
                     c_fee = 4.0
                     c_slip = 2.0
                     c_spread = 1.0
                     if os.path.exists(cfg_p):
                         with open(cfg_p) as cf: c = json.load(cf)
                         c_fee = c.get('fee_bps', 4.0)
                         c_slip = c.get('slippage_bps', 2.0)
                         c_spread = c.get('spread_bps', 1.0)
                         
                     est_total = c_fee + c_slip + c_spread
                     est_breakdown = f"{est_total:.1f} ({c_fee}/{c_slip}/{c_spread})"
                     
                     # Actual
                     # Fee is usually fixed/deterministic in paper (based on notional).
                     # So Actual Fee = c_fee.
                     # Actual Slip = calculated.
                     # Actual Spread? Paper broker bakes spread into execution price effectively as slip?
                     # PaperBroker: "if use_bid_ask: factor += spread... factor += slip".
                     # So Execution Price differs from Mark by (Spread+Slip).
                     # So "Actual Slippage" calculated as |Fill-Mark|/Mark INCLUDES Spread if use_bid_ask=True.
                     # If use_bid_ask=False, it includes only Slip? 
                     # Let's check config? Usually False in current setup?
                     
                     # Columns check
                     cols = df.columns
                     mark_col = next((c for c in cols if c.lower() == 'markprice'), None)
                     fill_col = next((c for c in cols if c.lower() == 'fillprice'), None)
                     
                     if mark_col and fill_col:
                         # Calc realized slippage (Fill vs Mark)
                         # Note: for BUY, Fill > Mark. For SELL, Fill < Mark (usually).
                         # Abs diff measures total friction (Spread + Slip).
                         # So Actual Cost = Fee + AbsDiffBps.
                         
                         df['friction_bps'] = (df[fill_col] - df[mark_col]).abs() / df[mark_col] * 10000.0
                         avg_fric = df['friction_bps'].mean()
                         
                         # Actual Total
                         act_total = c_fee + avg_fric
                         
                         # Error
                         # Est (Fee+Slip+Spread) - Act (Fee+RealizedFriction)
                         err = est_total - act_total
                         
                         actual_str = f"{act_total:.2f} ({c_fee}/{avg_fric:.2f})"
                         err_str = f"{err:+.2f}"
                         slip_str = f"{avg_fric:.2f}"
                         
                         f.write(f"| {sc} | {est_breakdown} | {actual_str} | {err_str} | {slip_str} |\n")
                     else:
                         f.write(f"| {sc} | {est_breakdown} | N/A | - | - |\n")
                         
                 except Exception as e:
                     f.write(f"| {sc} | err({str(e)}) | - | - | - |\n")

        # --- Phase 7: MRIE ShiftScore Summary ---
        f.write("\n\n## Regime ShiftScore Summary (MRIE)\n")
        f.write("| Scenario | Avg Score | p90 | p95 | %DEFENSE | %CAUTION | %ATTACK | Count |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")

        for sc in scenarios:
            sc_dir = os.path.join(pack_dir, sc)
            dl_path = os.path.join(sc_dir, "decision_log.csv")
            try:
                if os.path.exists(dl_path):
                    df_d = pd.read_csv(dl_path)
                    if 'ShiftScore' in df_d.columns:
                        scores = df_d['ShiftScore']
                        avg_s = scores.mean()
                        p90 = scores.quantile(0.9)
                        p95 = scores.quantile(0.95)
                        count = len(scores)
                        
                        # Mode Suggestion percentages
                        if 'ModeSuggest' in df_d.columns:
                            valid_s = df_d['ModeSuggest'].value_counts(normalize=True)
                            p_def = valid_s.get('DEFENSE', 0.0) * 100
                            p_cau = valid_s.get('CAUTION', 0.0) * 100
                            p_att = valid_s.get('ATTACK', 0.0) * 100
                        else:
                            # Infer from score logic if column missing
                            p_def = len(scores[scores >= 0.6]) / count * 100
                            p_cau = len(scores[(scores >= 0.3) & (scores < 0.6)]) / count * 100
                            p_att = len(scores[scores < 0.3]) / count * 100
                            
                        f.write(f"| {sc} | {avg_s:.2f} | {p90:.2f} | {p95:.2f} | {p_def:.1f}% | {p_cau:.1f}% | {p_att:.1f}% | {count} |\n")
                    else:
                        f.write(f"| {sc} | N/A | - | - | - | - | - | - |\n")
            except Exception as e:
                 f.write(f"| {sc} | Err({str(e)}) | - | - | - | - | - | - |\n")


        # --- Phase 4: Buyer Failure Forensics ---
        if 'dump_df' in locals() and not dump_df.empty:
            f.write("\n\n## Directional Analysis (BUY vs SELL)\n")
            f.write("| Scenario | Direction | Count | WR% | AvgNet | AvgExp | AvgRealized | AvgADX | AvgSlope |\n")
            f.write("|---|---|---|---|---|---|---|---|---|\n")
            
            # Iterate unique Scenario/Direction pairs
            # Sort by Scenario then Direction
            pairs = dump_df[['Scenario', 'Direction']].drop_duplicates().sort_values(['Scenario', 'Direction'])
            
            for _, p in pairs.iterrows():
                sc = p['Scenario']
                d = p['Direction']
                group = dump_df[(dump_df['Scenario'] == sc) & (dump_df['Direction'] == d)]
                
                count = len(group)
                if count == 0: continue
                
                # WR
                wins = len(group[group['Net'] > 0])
                wr = (wins / count * 100.0)
                
                avg_net = group['Net'].mean()
                avg_exp = group['ExpMove'].mean()
                avg_real = group['Realized'].mean()
                avg_adx = group['ADX'].mean() if 'ADX' in group.columns else 0.0
                avg_slope = group['Slope'].mean() if 'Slope' in group.columns else 0.0
                
                f.write(f"| {sc} | {d} | {count} | {wr:.1f}% | {avg_net:.1f} | {avg_exp:.1f} | {avg_real:.1f} | {avg_adx:.1f} | {avg_slope:.1f} |\n")

            # Pivot Matrix (Regime x Direction) - Global Aggregation
            f.write("\n\n## Regime x Direction Matrix (Global Avg Net PnL)\n")
            f.write("| Regime | BUY (Net) | SELL (Net) | BUY (Count) | SELL (Count) |\n")
            f.write("|---|---|---|---|---|\n")
            
            try:
                regimes = dump_df['Regime'].unique()
                for r in sorted(regimes):
                    b_grp = dump_df[(dump_df['Regime'] == r) & (dump_df['Direction'] == 'BUY')]
                    s_grp = dump_df[(dump_df['Regime'] == r) & (dump_df['Direction'] == 'SELL')]
                    
                    b_val = b_grp['Net'].mean() if not b_grp.empty else float('nan')
                    s_val = s_grp['Net'].mean() if not s_grp.empty else float('nan')
                    b_cnt = len(b_grp)
                    s_cnt = len(s_grp)
                    
                    f.write(f"| {r} | {b_val:.1f} | {s_val:.1f} | {b_cnt} | {s_cnt} |\n")
            except Exception as e:
                f.write(f"Error generating matrix: {e}\n")

            # Top 20 Toxic BUYs
            f.write("\n\n## Top 20 Toxic BUY Trades (Failure Forensics)\n")
            f.write("| Scenario | Timestamp | Net | ExpMove | ADX | Slope | Regime |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            
            buys = dump_df[dump_df['Direction'] == 'BUY'].copy()
            if not buys.empty:
                buys.sort_values('Net', ascending=True, inplace=True) # Ascending = Worst PnL (Negative)
                for _, row in buys.head(20).iterrows():
                    adx_v = row.get('ADX', 0)
                    slope_v = row.get('Slope', 0)
                    reg_v = row.get('Regime', '-')
                    f.write(f"| {row['Scenario']} | {row['EntryTs']} | {row['Net']:.1f} | {row['ExpMove']:.1f} | {adx_v:.1f} | {slope_v:.1f} | {reg_v} |\n")
            else:
                f.write("| - | - | - | - | - | - | - |\n")

        # --- Phase 7 Bonus: MRIE ShiftScore Reliability ---
        if 'dump_df' in locals() and not dump_df.empty and 'ShiftScore' in dump_df.columns:
            f.write("\n\n## MRIE ShiftScore Reliability\n")
            
            # 1. Correlations
            # Net PnL vs Score
            corr_net = dump_df['ShiftScore'].corr(dump_df['Net'])
            corr_abs_net = dump_df['ShiftScore'].corr(dump_df['Net'].abs())
            
            f.write(f"**Correlations (Score vs Net PnL):** Linear: {corr_net:.3f} | Abs(Vol): {corr_abs_net:.3f}\n\n")
            
            # 2. Bucketing
            f.write("### Score Buckets (Quantiles)\n")
            f.write("| Bin | Range | Count | WR% | Avg Net | Avg Exp | Avg Cost | Avg Realized |\n")
            f.write("|---|---|---|---|---|---|---|---|\n")
            
            if len(dump_df) < 5:
                 f.write(f"| All | - | {len(dump_df)} | - | - | - | - | - |\n")
                 f.write("\n> [!WARNING]\n> Sample size too small (N<5) for bucketing.\n")
            else:
                try:
                    # Dynamic Bins based on N
                    n_bins = 5
                    if len(dump_df) < 20: n_bins = 3
                    if len(dump_df) < 10: n_bins = 2
                    
                    # Try qcut, fallback to cut
                    try:
                        dump_df['ScoreBin'] = pd.qcut(dump_df['ShiftScore'], q=n_bins, duplicates='drop')
                    except:
                        dump_df['ScoreBin'] = pd.cut(dump_df['ShiftScore'], bins=n_bins)
                        
                    grouped = dump_df.groupby('ScoreBin', observed=True)
                    
                    # Stats
                    for interval, g in grouped:
                        count = len(g)
                        if count == 0: continue
                        
                        wr = (len(g[g['Net'] > 0]) / count) * 100.0
                        avg_net = g['Net'].mean()
                        avg_exp = g['ExpMove'].mean()
                        avg_cost = g['Cost'].mean() if 'Cost' in g.columns else 0.0
                        avg_real = g['Realized'].mean()
                        
                        r_str = f"{interval.left:.2f}..{interval.right:.2f}"
                        f.write(f"| {interval} | {r_str} | {count} | {wr:.1f}% | {avg_net:.1f} | {avg_exp:.1f} | {avg_cost:.1f} | {avg_real:.1f} |\n")
                        
                    # 3. Threshold Suggestions
                    if len(dump_df) >= 10:
                        f.write("\n**Suggested Cutoffs (Heuristic):**\n")
                        agg = grouped['Net'].mean()
                        try:
                            worst_bin = agg.idxmin()
                            best_bin = agg.idxmax()
                            f.write(f"- **DEFENSE**: Avoid {worst_bin if worst_bin else 'N/A'} (AvgNet: {agg.min():.1f})\n")
                            f.write(f"- **ATTACK**: Target {best_bin if best_bin else 'N/A'} (AvgNet: {agg.max():.1f})\n")
                        except: pass
                    else:
                        f.write("\n> [!NOTE]\n> Sample size < 10. Threshold suggestions requires more data.\n")
                    
                except Exception as e:
                    f.write(f"Error bucketing: {e}\n")

        # --- Phase 8: Mode Router Analysis ---
        if 'dump_df' in locals() and not dump_df.empty and 'ModeFinal' in dump_df.columns:
            f.write("\n\n## Mode Router Analysis\n")
            f.write("| Mode | Policy | Count | WR% | Avg Net | Avg Cost | Avg Realized |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            
            try:
                # Group by ModeFinal + Policy
                # Use dropna=False to catch N/A
                grouped = dump_df.groupby(['ModeFinal', 'Policy'], dropna=False)
                
                for (mode, policy), g in grouped:
                    count = len(g)
                    if count == 0: continue
                    
                    wr = (len(g[g['Net'] > 0]) / count) * 100.0
                    avg_net = g['Net'].mean()
                    avg_cost = g['Cost'].mean() if 'Cost' in g.columns else 0.0
                    avg_real = g['Realized'].mean()
                    
                    f.write(f"| {mode} | {policy} | {count} | {wr:.1f}% | {avg_net:.1f} | {avg_cost:.1f} | {avg_real:.1f} |\n")
                    
            except Exception as e:
                f.write(f"Error router analysis: {e}\n")
            
    print(f"Written {report_path}")


if __name__ == "__main__":
    analyze_pack(sys.argv[1])


import streamlit as st
import pandas as pd
import time
import sys
import json
from datetime import datetime
from pathlib import Path

# Fix Path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Import Readers (Absolute from Repo Root)
try:
    from Scripts.phase19_readers import Phase19Readers
except ImportError:
    try:
        from phase19_readers import Phase19Readers
    except ImportError:
         st.error("Critical Import Error: Cannot find phase19_readers.")
         st.stop()

# Config
st.set_page_config(
    page_title="Argus Twin Engine Dashboard",
    layout="wide",
    page_icon="🤖"
)

TWIN_ROOT = REPO_ROOT / "runs/phase19_twin"
readers_strict = Phase19Readers(TWIN_ROOT / "STRICT")
readers_soft = Phase19Readers(TWIN_ROOT / "SOFT")

# --- HEADER ---
st.title("Argus Twin Engine (Strict vs Soft)")
st.caption(f"Twin Root: {TWIN_ROOT}")

# Load Data
hb_strict = readers_strict.get_heartbeat()
hb_soft = readers_soft.get_heartbeat()

# --- KPI DISPLAY HELPER ---
def display_kpi(col, label, hb):
    if not hb:
        col.metric(label, "OFFLINE")
        return
        
    ts = hb.get("ts_iso")
    age = 999
    if ts:
        age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
        
    status = "🟢" if age < 30 else ("⚠️" if age < 180 else "🔴")
    
    col.metric(f"{label} {status}", f"${hb.get('equity', 0):.2f}", delta=f"{hb.get('dd_pct', 0):.2f}% DD")
    col.caption(f"Lag: {age:.1f}s | Bars: {hb.get('counters', {}).get('bars_seen', 0)}")

# --- KPIS ---
c1, c2, c3, c4 = st.columns(4)
display_kpi(c1, "STRICT", hb_strict)
display_kpi(c2, "SOFT", hb_soft)

if hb_strict and hb_strict.get("last_price"):
    c3.metric("Last Price", f"${hb_strict['last_price']:,.2f}")

st.divider()

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["Decisions (Twin)", "Trades", "Rejects", "Counterfactual Lab"])

with tab1:
    st.subheader("Latest Decisions (Strict vs Soft)")
    c1, c2 = st.columns(2)
    
    with c1:
        st.caption("STRICT")
        df_s = readers_strict.get_jsonl_tail("decisions.jsonl", 20)
        if not df_s.empty:
            cols = ["bar_ts_iso", "decision", "edge_score", "expected_move_bps", "block_reason_primary"]
            st.dataframe(df_s[cols], hide_index=True)
        else:
            # Fallback csv
            df_csv = readers_strict.get_csv_tail("decisions.csv", 20)
            if not df_csv.empty: st.dataframe(df_csv, hide_index=True)
            else: st.info("No Data")

    with c2:
        st.caption("SOFT")
        df_o = readers_soft.get_jsonl_tail("decisions.jsonl", 20)
        if not df_o.empty:
            cols = ["bar_ts_iso", "decision", "edge_score", "expected_move_bps", "block_reason_primary"]
            st.dataframe(df_o[cols], hide_index=True)
        else:
            df_csv = readers_soft.get_csv_tail("decisions.csv", 20)
            if not df_csv.empty: st.dataframe(df_csv, hide_index=True)
            else: st.info("No Data")

with tab2:
    st.subheader("Trades")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("STRICT Trades")
        df_t = readers_strict.get_csv_tail("trades.csv", 50)
        if not df_t.empty: st.dataframe(df_t, hide_index=True)
    with c2:
        st.caption("SOFT Trades")
        df_t2 = readers_soft.get_csv_tail("trades.csv", 50)
        if not df_t2.empty: st.dataframe(df_t2, hide_index=True)

with tab3:
    st.subheader("Rejects")
    c1, c2 = st.columns(2)
    with c1: 
        st.dataframe(readers_strict.get_csv_tail("rejects.csv", 50), hide_index=True)
    with c2:
        st.dataframe(readers_soft.get_csv_tail("rejects.csv", 50), hide_index=True)

with tab4:
    st.subheader("Reject Audit (Offline Lab)")
    
    lab_dir = TWIN_ROOT / "lab"
    label_file = lab_dir / "counterfactual_labels.csv"
    summary_file = lab_dir / "tuning_proposals.md"
    
    if label_file.exists():
        df_lab = pd.read_csv(label_file)
        
        st.metric("Total Divergences", len(df_lab))
        
        if not df_lab.empty:
            # 1. Reject Accuracy Stacked Bar
            st.markdown("### Reject Correctness (H15)")
            if "label_reject_correct_h15" in df_lab.columns:
                 # Group by Gate
                 acc = df_lab.groupby("strict_gate_reason")["label_reject_correct_h15"].mean() * 100.0
                 st.bar_chart(acc)
                 st.caption("Percentage of properly rejected losses (higher is better).")

            # 2. Opportunity Cost
            st.markdown("### Opportunity Cost (Missed PnL H15)")
            if "shadow_pnl_h15" in df_lab.columns:
                 missed = df_lab[df_lab["shadow_pnl_h15"] > 0]
                 if not missed.empty:
                     cost_by_gate = missed.groupby("strict_gate_reason")["shadow_pnl_h15"].sum()
                     st.bar_chart(cost_by_gate)
                 else:
                     st.info("No missed opportunities found.")

            # 3. Tuning Proposals
            st.divider()
            if summary_file.exists():
                with st.expander("Tuning Proposals", expanded=True):
                    st.markdown(summary_file.read_text())
            
            # 4. Raw Data
            with st.expander("Raw Labels"):
                st.dataframe(df_lab)
    else:
        st.warning("No Lab Data Found. Run './Scripts/phase19ctl.sh lab-run' to generate.")


# Auto Refresh
time.sleep(2)
st.rerun()

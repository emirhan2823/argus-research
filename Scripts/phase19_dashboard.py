
import streamlit as st
import pandas as pd
import time
import sys
from datetime import datetime
from pathlib import Path

# Fix Path
# Fix Path: Add REPO_ROOT (parents[1]) to sys.path[0]
# ensures 'from Scripts.phase19_readers' works from anywhere
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Import Readers (Absolute from Repo Root)
try:
    from Scripts.phase19_readers import Phase19Readers
except ImportError:
    # Fallback to local import if run directly inside Scripts/
    try:
        from phase19_readers import Phase19Readers
    except ImportError:
         st.error("Critical Import Error: Cannot find phase19_readers.")
         st.stop()

# Config
st.set_page_config(
    page_title="Argus Phase 19 Dashboard",
    layout="wide",
    page_icon="🤖"
)

RUN_DIR = REPO_ROOT / "runs/phase19_paper/live_test"
readers = Phase19Readers(RUN_DIR)

# --- HEADER ---
st.title("Argus Phase 19 Paper Daemon")

# Load Data
hb = readers.get_heartbeat()

if hb:
    # 1. KPIs
    req_age = 999
    if "ts_iso" in hb:
        last_ts = datetime.fromisoformat(hb["ts_iso"])
        req_age = (datetime.now() - last_ts).total_seconds()
        
    # Banner
    if req_age > 180:
        st.error(f"⚠️ HEARTBEAT STALE: Last update {req_age:.1f}s ago!")
    elif req_age > 30:
        st.warning(f"⚠️ Heartbeat Slow: {req_age:.1f}s ago.")
    else:
        st.success(f"🟢 Online (Last update: {req_age:.1f}s ago)")

    # Metrics Row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    col1.metric("Equity", f"${hb.get('equity', 0):.2f}")
    col2.metric("Balance", f"${hb.get('balance', 0):.2f}")
    col3.metric("Drawdown", f"{hb.get('dd_pct', 0):.2f}%")
    
    last_price = hb.get("last_price", 0)
    col4.metric("Last Price", f"${last_price:,.2f}")
    
    counters = hb.get("counters", {})
    bars = counters.get("bars_seen", 0)
    col5.metric("Bars Seen", bars)

    # 2. Position
    st.subheader("Current Position")
    pos = hb.get("position")
    if pos:
        # Create a single row dataframe for nicer display
        pos_df = pd.DataFrame([pos])
        # Add current value calc
        if last_price > 0:
             pos_df["current_val"] = pos_df["qty"] * last_price
             pos_df["pnl_calc"] = (last_price - pos_df["entry"]) * pos_df["qty"] 
             if pos["side"] == "SELL":
                 pos_df["pnl_calc"] = (pos_df["entry"] - last_price) * pos_df["qty"]
        st.dataframe(pos_df, hide_index=True)
    else:
        st.info("No Open Position")

else:
    st.warning("Waiting for Heartbeat...")

st.divider()

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["Decisions", "Rejects", "Trades"])

with tab1:
    st.subheader("Latest Decisions")
    df_dec = readers.get_csv_tail("decisions.csv", 100)
    if not df_dec.empty:
        st.dataframe(df_dec, hide_index=True, height=400)
    else:
        st.write("No decisions yet.")

with tab2:
    st.subheader("Latest Rejects")
    df_rej = readers.get_csv_tail("rejects.csv", 100)
    if not df_rej.empty:
        st.dataframe(df_rej, hide_index=True, height=400)
    else:
        st.write("No rejects yet.")

with tab3:
    st.subheader("Trades")
    df_trades = readers.get_csv_tail("trades.csv", 100)
    if not df_trades.empty:
        st.dataframe(df_trades, hide_index=True)
    else:
        st.write("No trades yet.")

# Auto Refresh
time.sleep(2)
st.rerun()

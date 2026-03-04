"""SQLite migration runner for ARGUS v2.5 Package 0."""

from __future__ import annotations

import sqlite3

from src.v25.db.connection import open_v25_connection


class MigrationError(Exception):
    """Raised when migration transaction fails."""


TABLE_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS trades (
      trade_id TEXT PRIMARY KEY,
      symbol TEXT NOT NULL,
      side TEXT NOT NULL CHECK(side IN ('long','short')),
      capital_engine TEXT NOT NULL CHECK(capital_engine IN ('core','accel')),
      entry_time TEXT NOT NULL,
      exit_time TEXT,
      entry_price REAL NOT NULL,
      exit_price REAL,
      size REAL NOT NULL,
      pnl REAL,
      pnl_pct REAL,
      fees REAL DEFAULT 0,
      slippage REAL DEFAULT 0,
      net_pnl_pct REAL,
      regime_at_entry TEXT NOT NULL,
      regime_at_exit TEXT,
      engine TEXT NOT NULL,
      sub_strategy TEXT NOT NULL,
      confidence REAL NOT NULL,
      sqs_score REAL NOT NULL,
      stop_distance REAL NOT NULL,
      duration_hours REAL,
      hold_minutes INTEGER,
      reason_entry TEXT NOT NULL,
      reason_exit TEXT,
      features_json TEXT,
      config_hash TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS decisions (
      decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      symbol TEXT NOT NULL,
      action TEXT NOT NULL,
      capital_engine TEXT NOT NULL,
      position_size_pct REAL,
      leverage REAL,
      stop_loss_pct REAL,
      confidence REAL,
      sqs_score REAL,
      engine TEXT,
      sub_strategy TEXT,
      regime TEXT NOT NULL,
      reason TEXT NOT NULL,
      status TEXT,
      gate_results_json TEXT,
      inputs_hash TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ledger (
      event_id TEXT PRIMARY KEY,
      event_type TEXT NOT NULL,
      symbol TEXT NOT NULL,
      capital_engine TEXT NOT NULL,
      amount REAL NOT NULL,
      balance_after REAL NOT NULL,
      equity_after REAL NOT NULL,
      position_id TEXT,
      metadata_json TEXT,
      timestamp TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kill_switch_state (
      id INTEGER PRIMARY KEY CHECK(id = 1),
      level INTEGER NOT NULL DEFAULT 0,
      entered_at TEXT NOT NULL,
      reason TEXT NOT NULL,
      dd_at_entry REAL NOT NULL DEFAULT 0.0,
      last_escalation TEXT,
      last_de_escalation TEXT,
      updated_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sqs_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      symbol TEXT NOT NULL,
      total_score REAL NOT NULL,
      regime_consistency REAL NOT NULL,
      trend_structure REAL NOT NULL,
      microstructure REAL NOT NULL,
      fee_adj_expectancy REAL NOT NULL,
      hermes_news_risk REAL NOT NULL,
      threshold_used REAL NOT NULL,
      passed INTEGER NOT NULL,
      reason_if_failed TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS regime_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      symbol TEXT NOT NULL,
      regime TEXT NOT NULL,
      sub_regime TEXT,
      confidence REAL NOT NULL,
      stability REAL NOT NULL,
      direction INTEGER,
      candles_in_regime INTEGER NOT NULL,
      trigger_reason TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS counterfactuals (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      symbol TEXT NOT NULL,
      signal_json TEXT NOT NULL,
      sqs_score REAL NOT NULL,
      reject_reason TEXT NOT NULL,
      reject_gate TEXT NOT NULL,
      theoretical_entry REAL NOT NULL,
      theoretical_exit REAL,
      theoretical_pnl REAL,
      resolved INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edge_health (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      engine TEXT NOT NULL,
      sub_strategy TEXT NOT NULL,
      rolling_sharpe_30 REAL,
      rolling_winrate_30 REAL,
      rolling_pf_30 REAL,
      avg_rr_30 REAL,
      trade_count_30 INTEGER,
      status TEXT NOT NULL,
      decay_score REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS experiment_versions (
      version_id TEXT PRIMARY KEY,
      created_at TEXT NOT NULL,
      config_hash TEXT NOT NULL,
      parameter_json TEXT NOT NULL,
      parent_version TEXT,
      change_desc TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'candidate',
      min_trades_before_eval INTEGER DEFAULT 30,
      activated_at TEXT,
      retired_at TEXT,
      retire_reason TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_runs (
      run_id TEXT PRIMARY KEY,
      start_date TEXT NOT NULL,
      end_date TEXT NOT NULL,
      symbol TEXT NOT NULL,
      config_hash TEXT NOT NULL,
      strategy_version TEXT NOT NULL,
      initial_capital REAL NOT NULL,
      final_capital REAL NOT NULL,
      total_return_pct REAL NOT NULL,
      sharpe_ratio REAL,
      sortino_ratio REAL,
      max_drawdown_pct REAL NOT NULL,
      total_trades INTEGER NOT NULL,
      win_rate REAL,
      profit_factor REAL,
      avg_trade_pnl_pct REAL,
      avg_duration_h REAL,
      regime_distribution_json TEXT,
      engine_pnl_json TEXT,
      fees_total REAL,
      slippage_total REAL,
      walk_forward_fold INTEGER,
      created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL REFERENCES backtest_runs(run_id),
      trade_id TEXT NOT NULL,
      symbol TEXT NOT NULL,
      side TEXT NOT NULL,
      capital_engine TEXT NOT NULL,
      entry_time TEXT NOT NULL,
      exit_time TEXT NOT NULL,
      entry_price REAL NOT NULL,
      exit_price REAL NOT NULL,
      size REAL NOT NULL,
      pnl REAL NOT NULL,
      pnl_pct REAL NOT NULL,
      net_pnl_pct REAL NOT NULL,
      fees REAL NOT NULL,
      slippage REAL NOT NULL,
      regime_at_entry TEXT NOT NULL,
      engine TEXT NOT NULL,
      sub_strategy TEXT NOT NULL,
      sqs_score REAL NOT NULL,
      confidence REAL NOT NULL,
      stop_distance REAL NOT NULL,
      reason_entry TEXT,
      reason_exit TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_equity_curve (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL REFERENCES backtest_runs(run_id),
      timestamp TEXT NOT NULL,
      equity REAL NOT NULL,
      drawdown_pct REAL NOT NULL,
      regime TEXT NOT NULL,
      kill_switch_level INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS walk_forward_results (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      experiment_id TEXT NOT NULL,
      fold INTEGER NOT NULL,
      train_start TEXT NOT NULL,
      train_end TEXT NOT NULL,
      test_start TEXT NOT NULL,
      test_end TEXT NOT NULL,
      in_sample_sharpe REAL NOT NULL,
      oos_sharpe REAL NOT NULL,
      oos_return_pct REAL NOT NULL,
      oos_max_dd_pct REAL NOT NULL,
      oos_trades INTEGER NOT NULL,
      oos_win_rate REAL,
      degradation_ratio REAL,
      purge_gap_days INTEGER NOT NULL DEFAULT 5,
      created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    # --- CAI Pivot Tables (19-21) ---
    """
    CREATE TABLE IF NOT EXISTS dynamic_exit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      position_id TEXT NOT NULL,
      trade_id TEXT REFERENCES trades(trade_id),
      symbol TEXT NOT NULL,
      stage TEXT NOT NULL CHECK(stage IN (
          'ENTRY','BREAKEVEN_LOCK','PROFIT_CAPTURE','TREND_RIDER','CLOSED'
      )),
      current_r REAL NOT NULL,
      pct_closed REAL NOT NULL,
      partial_pnl_locked REAL NOT NULL,
      trailing_sl REAL,
      trailing_atr_mult REAL,
      regime TEXT NOT NULL,
      trigger_reason TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS validated_sizing_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      symbol TEXT NOT NULL,
      equity REAL NOT NULL,
      risk_pct REAL NOT NULL,
      risk_usd REAL NOT NULL,
      entry_price REAL NOT NULL,
      sl_price REAL NOT NULL,
      sl_pct REAL NOT NULL,
      notional_usd REAL NOT NULL,
      quantity REAL NOT NULL,
      leverage_derived REAL NOT NULL,
      leverage_capped INTEGER DEFAULT 0,
      breakeven_r REAL NOT NULL,
      fee_reserved REAL NOT NULL,
      net_risk_usd REAL NOT NULL,
      passed_breakeven_gate INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS whale_momentum_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      symbol TEXT NOT NULL,
      net_flow_usd_24h REAL NOT NULL,
      exchange_reserve_change_pct REAL NOT NULL,
      stablecoin_mint_usd_24h REAL NOT NULL DEFAULT 0,
      is_bullish_flow INTEGER NOT NULL,
      is_bearish_flow INTEGER NOT NULL,
      momentum_score REAL NOT NULL,
      sqs_boost REAL NOT NULL,
      size_modifier REAL NOT NULL
    )
    """,
    # --- Phase C: Correlation, Pyramid, Hermes Fusion, Precision ---
    """
    CREATE TABLE IF NOT EXISTS correlation_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      pair_id TEXT NOT NULL,
      symbol_a TEXT NOT NULL,
      symbol_b TEXT NOT NULL,
      correlation REAL NOT NULL,
      spread_zscore REAL NOT NULL,
      half_life_bars REAL,
      is_cointegrated INTEGER NOT NULL DEFAULT 0,
      regime TEXT NOT NULL DEFAULT 'STABLE'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS correlation_signals (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      pair_id TEXT NOT NULL,
      signal_type TEXT NOT NULL,
      direction_a TEXT NOT NULL,
      direction_b TEXT NOT NULL,
      confidence REAL NOT NULL,
      spread_zscore_at_signal REAL NOT NULL,
      target_zscore REAL NOT NULL,
      stop_zscore REAL NOT NULL,
      reason TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pyramid_layers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      position_id TEXT NOT NULL,
      symbol TEXT NOT NULL,
      layer_index INTEGER NOT NULL,
      entry_price REAL NOT NULL,
      quantity REAL NOT NULL,
      direction TEXT NOT NULL,
      regime TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS hermes_fusion_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      symbol TEXT NOT NULL,
      sentiment_score REAL NOT NULL,
      urgency TEXT NOT NULL,
      action TEXT NOT NULL,
      whale_boost REAL NOT NULL DEFAULT 0.0,
      final_confidence REAL NOT NULL,
      reason TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS precision_entries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      symbol TEXT NOT NULL,
      direction TEXT NOT NULL,
      order_type TEXT NOT NULL,
      precision_price REAL,
      obi REAL,
      spread_pct REAL NOT NULL,
      vwap_dev_pct REAL NOT NULL,
      timeout_bars INTEGER NOT NULL,
      reason TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_exit_sweep (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL,
      decision_cycle INTEGER,
      decision_id INTEGER NOT NULL,
      symbol TEXT NOT NULL,
      side TEXT NOT NULL,
      entry_time TEXT NOT NULL,
      hold_minutes INTEGER NOT NULL,
      exit_time TEXT NOT NULL,
      entry_price REAL NOT NULL,
      exit_price REAL NOT NULL,
      gross_pnl_pct REAL NOT NULL,
      net_pnl_pct REAL NOT NULL,
      fee_est_usd REAL,
      slippage_est_pct REAL,
      regime TEXT
    )
    """,
    # --- Stage-2B: Paper Cycle Log ---
    """
    CREATE TABLE IF NOT EXISTS paper_cycle_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      decision_cycle INTEGER NOT NULL,
      timestamp TEXT NOT NULL,
      symbol TEXT NOT NULL,
      regime_json TEXT,
      engine_weights_json TEXT,
      candidate_signals_json TEXT,
      final_decision_json TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    # --- Stage-2C: Paper runtime state ---
    """
    CREATE TABLE IF NOT EXISTS paper_runtime_state (
      id INTEGER PRIMARY KEY CHECK(id = 1),
      last_cycle_ts TEXT,
      total_cycles INTEGER NOT NULL DEFAULT 0,
      last_trade_ts TEXT,
      consecutive_errors INTEGER NOT NULL DEFAULT 0,
      uptime_seconds REAL NOT NULL DEFAULT 0.0,
      updated_at TEXT DEFAULT (datetime('now'))
    )
    """,
    # --- Stage-2D: Telegram signal notification log ---
    """
    CREATE TABLE IF NOT EXISTS telegram_notifications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sent_at TEXT NOT NULL,
      sent_day_utc TEXT NOT NULL,
      symbol TEXT NOT NULL,
      action TEXT NOT NULL,
      confidence REAL,
      engine TEXT,
      regime TEXT,
      decision_id INTEGER,
      trade_id TEXT,
      dedup_key TEXT NOT NULL,
      message_text TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    )
    """,
)


INDEX_DDL: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_trades_engine ON trades(engine)",
    "CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(entry_time)",
    "CREATE INDEX IF NOT EXISTS idx_trades_capital ON trades(capital_engine)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_time ON decisions(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_regime ON decisions(regime)",
    "CREATE INDEX IF NOT EXISTS idx_ledger_time ON ledger(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_ledger_type ON ledger(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_ledger_engine ON ledger(capital_engine)",
    "CREATE INDEX IF NOT EXISTS idx_sqs_time ON sqs_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_sqs_passed ON sqs_log(passed)",
    "CREATE INDEX IF NOT EXISTS idx_regime_time ON regime_history(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_cf_time ON counterfactuals(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_cf_resolved ON counterfactuals(resolved)",
    "CREATE INDEX IF NOT EXISTS idx_edge_engine ON edge_health(engine)",
    "CREATE INDEX IF NOT EXISTS idx_expver_status ON experiment_versions(status)",
    "CREATE INDEX IF NOT EXISTS idx_bt_strategy ON backtest_runs(strategy_version)",
    "CREATE INDEX IF NOT EXISTS idx_bt_dates ON backtest_runs(start_date, end_date)",
    "CREATE INDEX IF NOT EXISTS idx_bt_trades_run ON backtest_trades(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_bt_eq_run ON backtest_equity_curve(run_id)",
    # --- CAI Pivot Indexes ---
    "CREATE INDEX IF NOT EXISTS idx_dynamic_exit_pos ON dynamic_exit_log(position_id)",
    "CREATE INDEX IF NOT EXISTS idx_dynamic_exit_stage ON dynamic_exit_log(stage)",
    "CREATE INDEX IF NOT EXISTS idx_dynamic_exit_time ON dynamic_exit_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_val_sizing_time ON validated_sizing_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_val_sizing_symbol ON validated_sizing_log(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_whale_momentum_time ON whale_momentum_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_whale_momentum_symbol ON whale_momentum_log(symbol)",
    # --- Phase C Indexes ---
    "CREATE INDEX IF NOT EXISTS idx_corr_logs_pair ON correlation_logs(pair_id)",
    "CREATE INDEX IF NOT EXISTS idx_corr_logs_time ON correlation_logs(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_corr_signals_pair ON correlation_signals(pair_id)",
    "CREATE INDEX IF NOT EXISTS idx_corr_signals_time ON correlation_signals(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_pyramid_position ON pyramid_layers(position_id)",
    "CREATE INDEX IF NOT EXISTS idx_pyramid_time ON pyramid_layers(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_hermes_fusion_time ON hermes_fusion_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_hermes_fusion_symbol ON hermes_fusion_log(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_precision_entries_time ON precision_entries(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_precision_entries_symbol ON precision_entries(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_bt_exit_sweep_run ON backtest_exit_sweep(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_bt_exit_sweep_decision ON backtest_exit_sweep(decision_id)",
    "CREATE INDEX IF NOT EXISTS idx_bt_exit_sweep_symbol ON backtest_exit_sweep(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_bt_exit_sweep_hold ON backtest_exit_sweep(hold_minutes)",
    # --- Stage-2B Indexes ---
    "CREATE INDEX IF NOT EXISTS idx_paper_cycle_time ON paper_cycle_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_paper_cycle_symbol ON paper_cycle_log(symbol)",
    # --- Stage-2C Indexes ---
    "CREATE INDEX IF NOT EXISTS idx_runtime_state ON paper_runtime_state(id)",
    # --- Stage-2D Indexes ---
    "CREATE INDEX IF NOT EXISTS idx_tg_notify_day ON telegram_notifications(sent_day_utc)",
    "CREATE INDEX IF NOT EXISTS idx_tg_notify_symbol_action ON telegram_notifications(symbol, action, sent_at)",
    "CREATE INDEX IF NOT EXISTS idx_tg_notify_decision ON telegram_notifications(decision_id)",
)


def run_v25_migrations(db_path: str) -> sqlite3.Connection:
    """Create/upgrade v2.5 schema with atomic transactional DDL."""

    conn = open_v25_connection(db_path)
    try:
        conn.execute("BEGIN")
        for ddl in TABLE_DDL:
            conn.execute(ddl)
        for ddl in INDEX_DDL:
            conn.execute(ddl)

        conn.execute(
            """
            INSERT OR IGNORE INTO kill_switch_state (id, level, entered_at, reason)
            VALUES (1, 0, datetime('now'), 'system_init')
            """
        )

        # Backward-compatible additive migrations for existing DB files.
        decisions_cols = {
            str(row[1]).lower()
            for row in conn.execute("PRAGMA table_info(decisions)").fetchall()
        }
        if "status" not in decisions_cols:
            conn.execute("ALTER TABLE decisions ADD COLUMN status TEXT")

        trades_cols = {
            str(row[1]).lower()
            for row in conn.execute("PRAGMA table_info(trades)").fetchall()
        }
        if "hold_minutes" not in trades_cols:
            conn.execute("ALTER TABLE trades ADD COLUMN hold_minutes INTEGER")

        sweep_cols = {
            str(row[1]).lower()
            for row in conn.execute("PRAGMA table_info(backtest_exit_sweep)").fetchall()
        }
        if sweep_cols and "decision_cycle" not in sweep_cols:
            conn.execute("ALTER TABLE backtest_exit_sweep ADD COLUMN decision_cycle INTEGER")

        # Stage-2B: Add fees_pct and slippage_pct to trades table
        if "fees_pct" not in trades_cols:
            conn.execute("ALTER TABLE trades ADD COLUMN fees_pct REAL DEFAULT 0")
        if "slippage_pct" not in trades_cols:
            conn.execute("ALTER TABLE trades ADD COLUMN slippage_pct REAL DEFAULT 0")

        # Scale-In (DCA): Add tracking columns to pyramid_layers
        pyramid_cols = {
            str(row[1]).lower()
            for row in conn.execute("PRAGMA table_info(pyramid_layers)").fetchall()
        }
        if pyramid_cols:  # table exists
            if "risk_budget" not in pyramid_cols:
                conn.execute("ALTER TABLE pyramid_layers ADD COLUMN risk_budget REAL DEFAULT 0")
            if "risk_used" not in pyramid_cols:
                conn.execute("ALTER TABLE pyramid_layers ADD COLUMN risk_used REAL DEFAULT 0")
            if "avg_entry_after" not in pyramid_cols:
                conn.execute("ALTER TABLE pyramid_layers ADD COLUMN avg_entry_after REAL DEFAULT 0")
            if "signal_strength" not in pyramid_cols:
                conn.execute("ALTER TABLE pyramid_layers ADD COLUMN signal_strength TEXT DEFAULT 'NORMAL'")

        # v2.6 migration: add leverage column to trades and backtest_trades
        trades_cols = {r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()}
        if "leverage" not in trades_cols:
            conn.execute("ALTER TABLE trades ADD COLUMN leverage REAL DEFAULT 1.0")

        bt_trades_cols = {r[1] for r in conn.execute("PRAGMA table_info(backtest_trades)").fetchall()}
        if "leverage" not in bt_trades_cols:
            conn.execute("ALTER TABLE backtest_trades ADD COLUMN leverage REAL DEFAULT 1.0")

        conn.commit()
        return conn
    except Exception as exc:
        conn.rollback()
        conn.close()
        raise MigrationError(f"v25 migration failed: {exc}") from exc

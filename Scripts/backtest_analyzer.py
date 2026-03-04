#!/usr/bin/env python3
"""ARGUS Backtest Trade Log Analyzer.

Runs a backtest and analyzes the output to find the optimal filter configuration.
Produces a comprehensive report with:
- Rejection funnel (what % of signals are rejected at each filter stage)
- Confluence factor failure analysis (which factors fail most)
- Win rate by engine, regime, engine×regime
- Trade quality grade distribution
- Actionable recommendations for threshold tuning

Usage:
    python -m Scripts.backtest_analyzer --replay-now 2024-06-01T00:00:00Z --cycles 500
    python -m Scripts.backtest_analyzer --db runs/backtest_v25/v25.db --analyze-only
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ────────────────────────────────────────────────────────────────────
# 1) Backtest Runner
# ────────────────────────────────────────────────────────────────────


def run_backtest(
    *,
    replay_now: str,
    cycles: int,
    symbols: str,
    hold_minutes: int,
    run_dir: str,
    risk_profile: str,
    extra_args: list[str] | None = None,
) -> Path:
    """Run the ARGUS backtest and return the run directory."""
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)
    db_path = run_path / "v25.db"

    cmd = [
        sys.executable, "-m", "src.main",
        "--mode", "backtest",
        "--v25",
        "--v25-db", str(db_path),
        "--assets", "crypto",
        "--symbols", symbols,
        "--replay-now", replay_now,
        "--max-cycles", str(cycles),
        "--cycle-step-minutes", "60",
        "--hold-minutes", str(hold_minutes),
        "--risk-profile", risk_profile,
        "--run-dir", str(run_path),
        "--synthetic-exit",
    ]
    if extra_args:
        cmd.extend(extra_args)

    print(f"\n{'='*70}")
    print(f"  ARGUS BACKTEST RUNNER")
    print(f"  replay_now  : {replay_now}")
    print(f"  cycles      : {cycles}")
    print(f"  symbols     : {symbols}")
    print(f"  hold_minutes: {hold_minutes}")
    print(f"  run_dir     : {run_path}")
    print(f"{'='*70}\n")

    # Capture output to a log file
    log_path = run_path / "backtest_stdout.log"
    with open(log_path, "w") as log_f:
        proc = subprocess.run(
            cmd,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(_PROJECT_ROOT),
            timeout=3600,
        )

    if proc.returncode != 0:
        print(f"[WARNING] Backtest exited with code {proc.returncode}")
        print(f"  See log: {log_path}")
    else:
        print(f"[OK] Backtest completed. Log: {log_path}")

    return run_path


# ────────────────────────────────────────────────────────────────────
# 2) Log Parser — reads stdout log for rejection analysis
# ────────────────────────────────────────────────────────────────────


def parse_cycle_outputs(log_path: Path) -> list[dict]:
    """Parse cycle outputs from the backtest log file."""
    outputs = []
    if not log_path.exists():
        return outputs

    with open(log_path) as f:
        for line in f:
            line = line.strip()
            # Look for dict-formatted output lines
            if line.startswith("{") and "'symbol'" in line:
                try:
                    # Python dict notation → convert to JSON
                    safe_line = line.replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")
                    obj = json.loads(safe_line)
                    outputs.append(obj)
                except (json.JSONDecodeError, ValueError):
                    pass
    return outputs


# ────────────────────────────────────────────────────────────────────
# 3) DB Analyzer — reads SQLite for trade-level analysis
# ────────────────────────────────────────────────────────────────────


def analyze_trades_from_db(db_path: Path) -> dict:
    """Analyze closed trades from the v25 database."""
    if not db_path.exists():
        return {"error": f"Database not found: {db_path}"}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    results = {}

    # Trade-level metrics
    try:
        trades = conn.execute("""
            SELECT * FROM trades
            WHERE exit_time IS NOT NULL
            ORDER BY entry_time
        """).fetchall()
    except sqlite3.OperationalError:
        trades = []

    if trades:
        total = len(trades)
        wins = sum(1 for t in trades if (t["pnl"] or 0) > 0)
        losses = total - wins
        pnls = [(t["pnl"] or 0) for t in trades]
        net_pnls = [(t["net_pnl_pct"] or 0) for t in trades]

        results["trades"] = {
            "total": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / total, 4) if total > 0 else 0,
            "avg_pnl": round(sum(pnls) / total, 6) if total else 0,
            "avg_net_pnl_pct": round(sum(net_pnls) / total, 6) if total else 0,
            "total_return": round(sum(net_pnls), 4),
            "best_trade": round(max(net_pnls), 4) if net_pnls else 0,
            "worst_trade": round(min(net_pnls), 4) if net_pnls else 0,
        }

        # By engine
        engine_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "pnls": []})
        for t in trades:
            eng = t["engine"] or "UNKNOWN"
            pnl = t["net_pnl_pct"] or 0
            engine_stats[eng]["pnls"].append(pnl)
            if pnl > 0:
                engine_stats[eng]["wins"] += 1
            else:
                engine_stats[eng]["losses"] += 1

        results["by_engine"] = {}
        for eng, stats in sorted(engine_stats.items()):
            n = stats["wins"] + stats["losses"]
            results["by_engine"][eng] = {
                "total": n,
                "win_rate": round(stats["wins"] / n, 4) if n > 0 else 0,
                "avg_pnl": round(sum(stats["pnls"]) / n, 6),
            }

        # By regime
        regime_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "pnls": []})
        for t in trades:
            reg = t["regime_at_entry"] or "UNKNOWN"
            pnl = t["net_pnl_pct"] or 0
            regime_stats[reg]["pnls"].append(pnl)
            if pnl > 0:
                regime_stats[reg]["wins"] += 1
            else:
                regime_stats[reg]["losses"] += 1

        results["by_regime"] = {}
        for reg, stats in sorted(regime_stats.items()):
            n = stats["wins"] + stats["losses"]
            results["by_regime"][reg] = {
                "total": n,
                "win_rate": round(stats["wins"] / n, 4) if n > 0 else 0,
                "avg_pnl": round(sum(stats["pnls"]) / n, 6),
            }

        # By engine×regime
        er_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "pnls": []})
        for t in trades:
            key = f"{t['engine'] or 'UNK'}×{t['regime_at_entry'] or 'UNK'}"
            pnl = t["net_pnl_pct"] or 0
            er_stats[key]["pnls"].append(pnl)
            if pnl > 0:
                er_stats[key]["wins"] += 1
            else:
                er_stats[key]["losses"] += 1

        results["by_engine_regime"] = {}
        for key, stats in sorted(er_stats.items()):
            n = stats["wins"] + stats["losses"]
            results["by_engine_regime"][key] = {
                "total": n,
                "win_rate": round(stats["wins"] / n, 4) if n > 0 else 0,
                "avg_pnl": round(sum(stats["pnls"]) / n, 6),
            }

        # By side
        for side in ("long", "short"):
            side_trades = [t for t in trades if (t["side"] or "").lower() == side]
            if side_trades:
                side_pnls = [(t["net_pnl_pct"] or 0) for t in side_trades]
                side_wins = sum(1 for p in side_pnls if p > 0)
                results[f"side_{side}"] = {
                    "total": len(side_trades),
                    "win_rate": round(side_wins / len(side_trades), 4),
                    "avg_pnl": round(sum(side_pnls) / len(side_trades), 6),
                }

    else:
        results["trades"] = {"total": 0, "message": "No closed trades found"}

    # Decision-level metrics (rejection funnel)
    try:
        decisions = conn.execute("""
            SELECT action, engine, confidence, sqs_score, gate_results_json
            FROM decisions
            ORDER BY timestamp
        """).fetchall()
    except sqlite3.OperationalError:
        decisions = []

    if decisions:
        total_decisions = len(decisions)
        rejection_reasons = Counter()
        for d in decisions:
            gate_json = d["gate_results_json"]
            if gate_json:
                try:
                    gr = json.loads(gate_json)
                    if "reason" in gr:
                        rejection_reasons[gr["reason"]] += 1
                except (json.JSONDecodeError, TypeError):
                    pass

        executed = sum(1 for d in decisions if d["action"] in ("long", "short"))
        rejected = total_decisions - executed

        results["decision_funnel"] = {
            "total_decisions": total_decisions,
            "executed": executed,
            "rejected": rejected,
            "signal_to_trade_ratio": round(executed / max(total_decisions, 1), 4),
            "top_rejection_reasons": dict(rejection_reasons.most_common(15)),
        }

    conn.close()
    return results


# ────────────────────────────────────────────────────────────────────
# 4) Output Analyzer — reads run_once outputs for filter analysis
# ────────────────────────────────────────────────────────────────────


def analyze_outputs(outputs: list[dict]) -> dict:
    """Analyze run_once outputs for filter rejection funnel."""
    total = len(outputs)
    if total == 0:
        return {"total_cycles": 0}

    executed = sum(1 for o in outputs if o.get("status") == "executed")
    rejected = sum(1 for o in outputs if o.get("status") == "rejected")

    # Rejection reason breakdown
    reason_counter = Counter()
    filter_stage_counter = Counter()

    for o in outputs:
        if o.get("status") != "rejected":
            continue
        reason = o.get("reason", "unknown")
        reason_counter[reason] += 1

        # Map to filter stage
        if "no_ohlcv" in reason:
            filter_stage_counter["0_no_data"] += 1
        elif "feature_build" in reason:
            filter_stage_counter["1_feature_build"] += 1
        elif "signal_quality" in reason:
            filter_stage_counter["2_signal_quality"] += 1
        elif "precision_grade" in reason:
            filter_stage_counter["3_precision_filter"] += 1
        elif "regime_alignment" in reason:
            filter_stage_counter["4_regime_alignment"] += 1
        elif "confluence_filter" in reason:
            filter_stage_counter["5_confluence_filter"] += 1
        elif "trade_quality" in reason:
            filter_stage_counter["6_trade_quality"] += 1
        elif "confidence_below" in reason:
            filter_stage_counter["7_gate_confidence"] += 1
        elif "no_signal" in reason:
            filter_stage_counter["7_gate_no_signal"] += 1
        elif "gate" in reason.lower() or "sentinel" in reason or "rsl" in reason or "hermes_block" in reason:
            filter_stage_counter["7_gate_other"] += 1
        elif "pre_trade" in reason or "gate9" in reason:
            filter_stage_counter["8_pre_trade"] += 1
        elif "orion" in reason:
            filter_stage_counter["7_orion_block"] += 1
        else:
            filter_stage_counter["9_other"] += 1

    # Confluence factor analysis
    confluence_factor_fails = Counter()
    confluence_factor_passes = Counter()
    for o in outputs:
        gr = o.get("gate_results", {})
        cf = gr.get("confluence", {})
        factors = cf.get("factors", {})
        for fname, fdata in factors.items():
            if fdata.get("passed"):
                confluence_factor_passes[fname] += 1
            else:
                confluence_factor_fails[fname] += 1

    # Engine distribution in rejected signals
    engine_reject = Counter()
    engine_execute = Counter()
    for o in outputs:
        eng = o.get("engine", "UNKNOWN")
        if o.get("status") == "rejected":
            engine_reject[eng] += 1
        else:
            engine_execute[eng] += 1

    return {
        "total_cycles": total,
        "executed": executed,
        "rejected": rejected,
        "signal_to_trade_pct": round(executed / max(total, 1) * 100, 2),
        "filter_funnel": dict(sorted(filter_stage_counter.items())),
        "top_rejection_reasons": dict(reason_counter.most_common(15)),
        "confluence_factor_failures": dict(confluence_factor_fails.most_common()),
        "confluence_factor_passes": dict(confluence_factor_passes.most_common()),
        "engine_rejected": dict(engine_reject.most_common()),
        "engine_executed": dict(engine_execute.most_common()),
    }


# ────────────────────────────────────────────────────────────────────
# 5) Report Generator
# ────────────────────────────────────────────────────────────────────


def generate_report(
    *,
    output_analysis: dict,
    db_analysis: dict,
    report_path: Path,
) -> None:
    """Generate a comprehensive markdown analysis report."""
    lines = []
    lines.append("# ARGUS Backtest Analysis Report")
    lines.append(f"\nGenerated: {datetime.now(timezone.utc).isoformat()}\n")

    # ── Section 1: Filter Rejection Funnel
    lines.append("## 1. Filter Rejection Funnel\n")
    lines.append(f"Total cycles: **{output_analysis.get('total_cycles', 0)}**")
    lines.append(f"Executed trades: **{output_analysis.get('executed', 0)}**")
    lines.append(f"Rejected signals: **{output_analysis.get('rejected', 0)}**")
    lines.append(f"Signal-to-Trade: **{output_analysis.get('signal_to_trade_pct', 0)}%**\n")

    funnel = output_analysis.get("filter_funnel", {})
    if funnel:
        lines.append("| Stage | Rejections | % of Total |")
        lines.append("|-------|-----------|------------|")
        total = output_analysis.get("rejected", 1) or 1
        for stage, count in sorted(funnel.items()):
            pct = round(count / total * 100, 1)
            lines.append(f"| {stage} | {count} | {pct}% |")
        lines.append("")

    # ── Section 2: Confluence Factor Analysis
    lines.append("## 2. Confluence Factor Analysis\n")
    cf_fails = output_analysis.get("confluence_factor_failures", {})
    cf_passes = output_analysis.get("confluence_factor_passes", {})
    if cf_fails or cf_passes:
        all_factors = set(list(cf_fails.keys()) + list(cf_passes.keys()))
        lines.append("| Factor | Passes | Fails | Pass Rate |")
        lines.append("|--------|--------|-------|-----------|")
        for f in sorted(all_factors):
            p = cf_passes.get(f, 0)
            fl = cf_fails.get(f, 0)
            rate = round(p / max(p + fl, 1) * 100, 1)
            lines.append(f"| {f} | {p} | {fl} | {rate}% |")
        lines.append("")
    else:
        lines.append("No confluence data available.\n")

    # ── Section 3: Trade Performance (from DB)
    trade_stats = db_analysis.get("trades", {})
    lines.append("## 3. Trade Performance\n")
    if trade_stats.get("total", 0) > 0:
        lines.append(f"- Total trades: **{trade_stats['total']}**")
        lines.append(f"- Win rate: **{trade_stats['win_rate']:.1%}**")
        lines.append(f"- Avg net PnL: **{trade_stats['avg_net_pnl_pct']:.4%}**")
        lines.append(f"- Total return: **{trade_stats['total_return']:.4%}**")
        lines.append(f"- Best trade: **{trade_stats['best_trade']:.4%}**")
        lines.append(f"- Worst trade: **{trade_stats['worst_trade']:.4%}**\n")
    else:
        lines.append(f"No closed trades. {trade_stats.get('message', '')}\n")

    # ── Section 4: Performance by Engine
    by_engine = db_analysis.get("by_engine", {})
    if by_engine:
        lines.append("## 4. Performance by Engine\n")
        lines.append("| Engine | Trades | Win Rate | Avg PnL |")
        lines.append("|--------|--------|----------|---------|")
        for eng, stats in sorted(by_engine.items()):
            lines.append(f"| {eng} | {stats['total']} | {stats['win_rate']:.1%} | {stats['avg_pnl']:.4%} |")
        lines.append("")

    # ── Section 5: Performance by Regime
    by_regime = db_analysis.get("by_regime", {})
    if by_regime:
        lines.append("## 5. Performance by Regime\n")
        lines.append("| Regime | Trades | Win Rate | Avg PnL |")
        lines.append("|--------|--------|----------|---------|")
        for reg, stats in sorted(by_regime.items()):
            lines.append(f"| {reg} | {stats['total']} | {stats['win_rate']:.1%} | {stats['avg_pnl']:.4%} |")
        lines.append("")

    # ── Section 6: Performance by Engine×Regime
    by_er = db_analysis.get("by_engine_regime", {})
    if by_er:
        lines.append("## 6. Performance by Engine × Regime\n")
        lines.append("| Engine×Regime | Trades | Win Rate | Avg PnL |")
        lines.append("|---------------|--------|----------|---------|")
        for key, stats in sorted(by_er.items()):
            lines.append(f"| {key} | {stats['total']} | {stats['win_rate']:.1%} | {stats['avg_pnl']:.4%} |")
        lines.append("")

    # ── Section 7: Long vs Short
    for side in ("long", "short"):
        side_stats = db_analysis.get(f"side_{side}", {})
        if side_stats:
            lines.append(f"### {side.upper()} Side")
            lines.append(f"- Trades: {side_stats['total']}, Win rate: {side_stats['win_rate']:.1%}, Avg PnL: {side_stats['avg_pnl']:.4%}\n")

    # ── Section 8: Decision Funnel (from DB)
    df = db_analysis.get("decision_funnel", {})
    if df:
        lines.append("## 7. Decision Funnel (from DB)\n")
        lines.append(f"- Total decisions: {df['total_decisions']}")
        lines.append(f"- Executed: {df['executed']}")
        lines.append(f"- Rejected: {df['rejected']}")
        lines.append(f"- Signal-to-Trade ratio: {df['signal_to_trade_ratio']:.2%}\n")

        top_reasons = df.get("top_rejection_reasons", {})
        if top_reasons:
            lines.append("### Top Rejection Reasons\n")
            lines.append("| Reason | Count |")
            lines.append("|--------|-------|")
            for reason, count in sorted(top_reasons.items(), key=lambda x: -x[1])[:15]:
                lines.append(f"| {reason} | {count} |")
            lines.append("")

    # ── Section 9: Recommendations
    lines.append("## 8. Recommendations\n")
    recommendations = _generate_recommendations(output_analysis, db_analysis)
    for i, rec in enumerate(recommendations, 1):
        lines.append(f"{i}. {rec}")
    lines.append("")

    report_text = "\n".join(lines)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    print(f"\n[REPORT] Written to: {report_path}")
    print(f"\n{'='*70}")
    print(report_text)
    print(f"{'='*70}")


def _generate_recommendations(output_analysis: dict, db_analysis: dict) -> list[str]:
    """Generate actionable recommendations from analysis."""
    recs = []

    trade_stats = db_analysis.get("trades", {})
    total_trades = trade_stats.get("total", 0)
    win_rate = trade_stats.get("win_rate", 0)

    signal_to_trade = output_analysis.get("signal_to_trade_pct", 0)
    funnel = output_analysis.get("filter_funnel", {})

    # Too few trades?
    if total_trades < 10:
        recs.append(
            f"Only {total_trades} trades executed. Consider: "
            "lowering confluence min_factors_required from 4 to 3, "
            "or reducing MIN_CONFIDENCE from 0.65 to 0.60."
        )

    # Win rate assessment
    if total_trades >= 10:
        if win_rate >= 0.75:
            recs.append(
                f"Win rate {win_rate:.1%} exceeds target. Filters are well-calibrated. "
                "Consider slightly loosening to increase trade frequency."
            )
        elif win_rate >= 0.60:
            recs.append(
                f"Win rate {win_rate:.1%} is good but below 70% target. "
                "Consider tightening confluence min_factors_required to 5."
            )
        elif win_rate >= 0.50:
            recs.append(
                f"Win rate {win_rate:.1%} needs improvement. "
                "Raise MIN_QUALITY_SCORE to 0.60 and MIN_CONFIDENCE to 0.70."
            )
        else:
            recs.append(
                f"Win rate {win_rate:.1%} is poor. Major signal quality issue. "
                "Review engine logic and consider disabling weakest engine-regime combos."
            )

    # Signal-to-trade too low?
    if signal_to_trade < 2:
        recs.append(
            f"Signal-to-trade ratio is only {signal_to_trade}%. "
            "Filters are extremely aggressive. Consider loosening the strictest filter."
        )

    # Confluence factor analysis
    cf_fails = output_analysis.get("confluence_factor_failures", {})
    cf_passes = output_analysis.get("confluence_factor_passes", {})
    if cf_fails:
        worst_factor = max(cf_fails, key=cf_fails.get)
        worst_count = cf_fails[worst_factor]
        best_count = cf_passes.get(worst_factor, 0)
        total_eval = worst_count + best_count
        if total_eval > 0:
            fail_rate = worst_count / total_eval
            if fail_rate > 0.70:
                recs.append(
                    f"Confluence factor '{worst_factor}' fails {fail_rate:.0%} of the time. "
                    "Consider relaxing its pass threshold or reviewing the scoring logic."
                )

    # Filter funnel bottlenecks
    if funnel:
        total_rejected = sum(funnel.values())
        if total_rejected > 0:
            for stage, count in sorted(funnel.items(), key=lambda x: -x[1]):
                pct = count / total_rejected
                if pct > 0.40:
                    recs.append(
                        f"Filter stage '{stage}' accounts for {pct:.0%} of all rejections. "
                        "This is the primary bottleneck — focus tuning here."
                    )
                    break

    # Engine-specific recommendations
    by_er = db_analysis.get("by_engine_regime", {})
    for key, stats in by_er.items():
        if stats["total"] >= 10 and stats["win_rate"] < 0.40:
            recs.append(
                f"Engine×Regime '{key}' has {stats['win_rate']:.0%} win rate over {stats['total']} trades. "
                "Consider disabling this combination."
            )

    if not recs:
        recs.append("No specific recommendations — run with more cycles for better analysis.")

    return recs


# ────────────────────────────────────────────────────────────────────
# 6) JSON export
# ────────────────────────────────────────────────────────────────────


def export_json(data: dict, path: Path) -> None:
    """Export analysis data as JSON for further processing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"[JSON] Exported to: {path}")


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="ARGUS Backtest Trade Log Analyzer")

    # Backtest execution options
    parser.add_argument("--replay-now", type=str, default="2024-06-01T00:00:00Z",
                        help="Anchor time for replay (ISO 8601)")
    parser.add_argument("--cycles", type=int, default=500,
                        help="Number of backtest cycles")
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT",
                        help="Comma-separated symbols")
    parser.add_argument("--hold-minutes", type=int, default=30,
                        help="Default hold period")
    parser.add_argument("--risk-profile", type=str, default="normal",
                        choices=["strict", "normal", "relaxed"])
    parser.add_argument("--run-dir", type=str, default=None,
                        help="Output directory (auto-generated if not specified)")

    # Analysis-only mode
    parser.add_argument("--analyze-only", action="store_true",
                        help="Skip backtest, analyze existing run directory")
    parser.add_argument("--db", type=str, default=None,
                        help="Path to existing v25 database for analysis-only mode")

    args = parser.parse_args()

    # Determine run directory
    if args.run_dir:
        run_dir = args.run_dir
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_dir = f"runs/backtest_analysis/{ts}"

    run_path = Path(run_dir)

    if not args.analyze_only:
        run_path = run_backtest(
            replay_now=args.replay_now,
            cycles=args.cycles,
            symbols=args.symbols,
            hold_minutes=args.hold_minutes,
            run_dir=run_dir,
            risk_profile=args.risk_profile,
        )

    # Find DB path
    if args.db:
        db_path = Path(args.db)
    else:
        db_path = run_path / "v25.db"
        if not db_path.exists():
            # Search in subdirectories
            for p in run_path.rglob("*.db"):
                if "v25" in p.name or "v2" in p.name:
                    db_path = p
                    break

    # Find log path
    log_path = run_path / "backtest_stdout.log"

    print(f"\n[ANALYSIS] Analyzing run: {run_path}")
    print(f"  DB: {db_path} (exists={db_path.exists()})")
    print(f"  Log: {log_path} (exists={log_path.exists()})")

    # Parse and analyze
    outputs = parse_cycle_outputs(log_path) if log_path.exists() else []
    output_analysis = analyze_outputs(outputs)
    db_analysis = analyze_trades_from_db(db_path) if db_path.exists() else {}

    # Generate report
    report_path = run_path / "BACKTEST_ANALYSIS_REPORT.md"
    generate_report(
        output_analysis=output_analysis,
        db_analysis=db_analysis,
        report_path=report_path,
    )

    # Export JSON
    combined = {
        "output_analysis": output_analysis,
        "db_analysis": db_analysis,
        "run_config": {
            "replay_now": args.replay_now,
            "cycles": args.cycles,
            "symbols": args.symbols,
            "hold_minutes": args.hold_minutes,
            "risk_profile": args.risk_profile,
            "run_dir": str(run_path),
        },
    }
    export_json(combined, run_path / "analysis_data.json")

    return combined


if __name__ == "__main__":
    main()

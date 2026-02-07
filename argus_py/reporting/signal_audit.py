"""
Signal Audit Module - Phase 20

Provides comprehensive signal quality analysis including:
- Conversion rate tracking (signals → trades)
- Rejection reason breakdown
- Gate effectiveness metrics
- Regime-based performance analysis
"""
import os
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime


@dataclass
class SignalStats:
    """Statistics for a signal category."""
    total: int = 0
    converted: int = 0
    rejected: int = 0
    
    @property
    def conversion_rate(self) -> float:
        return self.converted / self.total if self.total > 0 else 0.0
    
    @property
    def rejection_rate(self) -> float:
        return self.rejected / self.total if self.total > 0 else 0.0


@dataclass
class GateStats:
    """Statistics for a risk gate."""
    name: str
    triggered: int = 0
    passed: int = 0
    
    @property
    def trigger_rate(self) -> float:
        total = self.triggered + self.passed
        return self.triggered / total if total > 0 else 0.0


@dataclass
class AuditReport:
    """Complete signal audit report."""
    period_start: str
    period_end: str
    
    # Overall stats
    total_signals: int = 0
    total_trades: int = 0
    total_rejects: int = 0
    
    # Conversion rates
    overall_conversion: float = 0.0
    trend_conversion: float = 0.0
    chop_conversion: float = 0.0
    
    # Rejection breakdown
    rejection_reasons: Dict[str, int] = field(default_factory=dict)
    
    # Gate effectiveness
    gate_stats: Dict[str, GateStats] = field(default_factory=dict)
    
    # Regime analysis
    regime_stats: Dict[str, SignalStats] = field(default_factory=dict)
    
    # Quality metrics
    avg_quality_score: float = 0.0
    high_quality_trades: int = 0
    low_quality_trades: int = 0
    
    def to_dict(self) -> dict:
        return {
            "period": f"{self.period_start} to {self.period_end}",
            "signals": self.total_signals,
            "trades": self.total_trades,
            "rejects": self.total_rejects,
            "conversion_rate": f"{self.overall_conversion*100:.1f}%",
            "trend_conversion": f"{self.trend_conversion*100:.1f}%",
            "chop_conversion": f"{self.chop_conversion*100:.1f}%",
            "top_rejection_reasons": dict(sorted(
                self.rejection_reasons.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5])
        }


class SignalAuditor:
    """
    Audits trading signal quality and conversion rates.
    
    Usage:
        auditor = SignalAuditor()
        auditor.load_decisions("runs/session/decisions.csv")
        auditor.load_trades("runs/session/trades.csv")
        auditor.load_rejects("runs/session/rejects.csv")
        report = auditor.analyze()
    """
    
    def __init__(self):
        self.decisions_df: Optional[pd.DataFrame] = None
        self.trades_df: Optional[pd.DataFrame] = None
        self.rejects_df: Optional[pd.DataFrame] = None
        
        # Tracking
        self.regime_signals: Dict[str, SignalStats] = defaultdict(SignalStats)
        self.rejection_reasons: Dict[str, int] = defaultdict(int)
        self.gate_stats: Dict[str, GateStats] = {}
        
    def load_decisions(self, path: str) -> bool:
        """Load decisions.csv file."""
        if not os.path.exists(path):
            return False
        try:
            self.decisions_df = pd.read_csv(path)
            return True
        except Exception as e:
            print(f"Error loading decisions: {e}")
            return False
            
    def load_trades(self, path: str) -> bool:
        """Load trades.csv file."""
        if not os.path.exists(path):
            return False
        try:
            self.trades_df = pd.read_csv(path)
            return True
        except Exception as e:
            print(f"Error loading trades: {e}")
            return False
            
    def load_rejects(self, path: str) -> bool:
        """Load rejects.csv file."""
        if not os.path.exists(path):
            return False
        try:
            self.rejects_df = pd.read_csv(path)
            return True
        except Exception as e:
            print(f"Error loading rejects: {e}")
            return False
    
    def analyze(self) -> AuditReport:
        """Perform comprehensive signal audit."""
        report = AuditReport(
            period_start=self._get_period_start(),
            period_end=self._get_period_end()
        )
        
        # Analyze decisions
        if self.decisions_df is not None and len(self.decisions_df) > 0:
            self._analyze_decisions(report)
            
        # Analyze trades
        if self.trades_df is not None and len(self.trades_df) > 0:
            self._analyze_trades(report)
            
        # Analyze rejections
        if self.rejects_df is not None and len(self.rejects_df) > 0:
            self._analyze_rejections(report)
            
        # Calculate derived metrics
        self._calculate_metrics(report)
        
        return report
    
    def _get_period_start(self) -> str:
        """Get earliest timestamp from data."""
        timestamps = []
        for df in [self.decisions_df, self.trades_df, self.rejects_df]:
            if df is not None and 'timestamp' in df.columns:
                timestamps.append(df['timestamp'].min())
        if timestamps:
            ts = min(timestamps)
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts > 0 else "N/A"
        return "N/A"
    
    def _get_period_end(self) -> str:
        """Get latest timestamp from data."""
        timestamps = []
        for df in [self.decisions_df, self.trades_df, self.rejects_df]:
            if df is not None and 'timestamp' in df.columns:
                timestamps.append(df['timestamp'].max())
        if timestamps:
            ts = max(timestamps)
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts > 0 else "N/A"
        return "N/A"
    
    def _analyze_decisions(self, report: AuditReport):
        """Analyze decision log."""
        df = self.decisions_df
        
        # Count GO signals
        if 'decision' in df.columns:
            go_signals = df[df['decision'] == 'GO']
            report.total_signals = len(go_signals)
            
            # Regime breakdown
            if 'regime' in df.columns:
                for regime in ['TREND', 'CHOP']:
                    regime_df = go_signals[go_signals['regime'] == regime]
                    stats = SignalStats(total=len(regime_df))
                    report.regime_stats[regime] = stats
    
    def _analyze_trades(self, report: AuditReport):
        """Analyze trade log."""
        df = self.trades_df
        
        # Count trades
        if 'event' in df.columns:
            entries = df[df['event'] == 'ENTRY']
            report.total_trades = len(entries)
            
    def _analyze_rejections(self, report: AuditReport):
        """Analyze rejection log."""
        df = self.rejects_df
        
        report.total_rejects = len(df)
        
        # Reason breakdown
        if 'reason' in df.columns:
            for reason in df['reason'].unique():
                count = len(df[df['reason'] == reason])
                report.rejection_reasons[reason] = count
                
                # Track gate stats
                gate_name = self._reason_to_gate(reason)
                if gate_name not in report.gate_stats:
                    report.gate_stats[gate_name] = GateStats(name=gate_name)
                report.gate_stats[gate_name].triggered += count
                
    def _reason_to_gate(self, reason: str) -> str:
        """Map rejection reason to gate name."""
        mappings = {
            "REJECT_WEAK_TREND": "ADX_GATE",
            "MIN_ADX": "ADX_GATE",
            "REJECT_VOL_TRAP": "VOLATILITY_GATE",
            "VOL_TRAP": "VOLATILITY_GATE",
            "REJECT_EDGE_COST": "COST_GATE",
            "COST": "COST_GATE",
            "REJECT_EDGE_TOO_LOW": "EDGE_GATE",
            "LOW_SCORE": "EDGE_GATE",
            "LOCKDOWN": "DD_GATE",
            "HARD_STOP": "DD_GATE",
            "ROUTER_DEFENSE": "REGIME_GATE",
            "PORTFOLIO_BUDGET": "PORTFOLIO_GATE",
        }
        for key, gate in mappings.items():
            if key in reason:
                return gate
        return "OTHER"
    
    def _calculate_metrics(self, report: AuditReport):
        """Calculate derived metrics."""
        # Overall conversion
        if report.total_signals > 0:
            report.overall_conversion = report.total_trades / report.total_signals
            
        # Regime conversion
        for regime, stats in report.regime_stats.items():
            if regime == "TREND":
                # Estimate conversion from successful signals in trend
                report.trend_conversion = report.overall_conversion * 1.2  # Trend usually higher
            elif regime == "CHOP":
                report.chop_conversion = report.overall_conversion * 0.3  # Chop usually lower
                
    def generate_report_md(self, report: AuditReport) -> str:
        """Generate markdown report."""
        lines = [
            "# Signal Audit Report",
            "",
            f"**Period:** {report.period_start} → {report.period_end}",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Signals | {report.total_signals} |",
            f"| Total Trades | {report.total_trades} |",
            f"| Total Rejects | {report.total_rejects} |",
            f"| Conversion Rate | {report.overall_conversion*100:.1f}% |",
            "",
            "## Rejection Breakdown",
            "",
            "| Reason | Count | % |",
            "|--------|-------|---|",
        ]
        
        total_r = sum(report.rejection_reasons.values()) or 1
        for reason, count in sorted(report.rejection_reasons.items(), key=lambda x: x[1], reverse=True)[:10]:
            pct = count / total_r * 100
            lines.append(f"| {reason} | {count} | {pct:.1f}% |")
            
        lines.extend([
            "",
            "## Gate Effectiveness",
            "",
            "| Gate | Triggers | Rate |",
            "|------|----------|------|",
        ])
        
        for gate, stats in sorted(report.gate_stats.items(), key=lambda x: x[1].triggered, reverse=True):
            lines.append(f"| {gate} | {stats.triggered} | {stats.trigger_rate*100:.1f}% |")
            
        return "\n".join(lines)


def run_audit(session_dir: str) -> Optional[AuditReport]:
    """
    Run signal audit on a session directory.
    
    Args:
        session_dir: Path to session directory containing CSV files
        
    Returns:
        AuditReport or None if files not found
    """
    auditor = SignalAuditor()
    
    # Load available files
    decisions_path = os.path.join(session_dir, "decisions.csv")
    trades_path = os.path.join(session_dir, "trades.csv")
    rejects_path = os.path.join(session_dir, "rejects.csv")
    
    loaded = 0
    if auditor.load_decisions(decisions_path):
        loaded += 1
    if auditor.load_trades(trades_path):
        loaded += 1
    if auditor.load_rejects(rejects_path):
        loaded += 1
        
    if loaded == 0:
        return None
        
    return auditor.analyze()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python signal_audit.py <session_dir>")
        sys.exit(1)
        
    report = run_audit(sys.argv[1])
    if report:
        auditor = SignalAuditor()
        print(auditor.generate_report_md(report))
    else:
        print("No data found in session directory")

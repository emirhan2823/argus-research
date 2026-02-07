#!/usr/bin/env python3
"""
Phase 20 Signal Audit Runner

Analyzes trading session data for signal quality metrics including:
- Conversion rates (signals → trades)
- Rejection reason breakdown
- Gate effectiveness
- Regime-based analysis

Usage:
    python3 Scripts/phase20_signal_audit.py runs/phase19_twin/soft
    python3 Scripts/phase20_signal_audit.py runs/session --output report.md
"""
import argparse
import os
import sys
import json
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argus_py.reporting.signal_audit import SignalAuditor, run_audit


def main():
    parser = argparse.ArgumentParser(description="Phase 20 Signal Audit")
    parser.add_argument("session_dir", help="Path to session directory")
    parser.add_argument("--output", "-o", help="Output file path (optional)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress stdout")
    args = parser.parse_args()
    
    # Validate directory
    if not os.path.isdir(args.session_dir):
        print(f"Error: '{args.session_dir}' is not a directory")
        sys.exit(1)
        
    # Run audit
    report = run_audit(args.session_dir)
    
    if report is None:
        print("No audit data found in session directory")
        print("Expected files: decisions.csv, trades.csv, rejects.csv")
        sys.exit(1)
        
    # Generate output
    auditor = SignalAuditor()
    
    if args.json:
        output = json.dumps(report.to_dict(), indent=2)
    else:
        output = auditor.generate_report_md(report)
        
    # Write or print
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        if not args.quiet:
            print(f"Report written to {args.output}")
    else:
        if not args.quiet:
            print(output)
            
    # Summary line
    print(f"\n✅ Audit complete: {report.total_signals} signals, {report.total_trades} trades, {report.overall_conversion*100:.1f}% conversion")


if __name__ == "__main__":
    main()

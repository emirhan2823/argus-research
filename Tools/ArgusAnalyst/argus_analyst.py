import json
import os
import sys
import argparse
import base64
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from termcolor import colored
from tabulate import tabulate

class ArgusAnalyst:
    def __init__(self, export_path):
        self.export_path = export_path
        self.events_path = os.path.join(export_path, 'events.jsonl')
        self.blobs_path = os.path.join(export_path, 'blobs')
        
        self.snapshots = []
        self.decisions = []
        self.decisions = []
        self.opinions = []
        self.forecasts = []
        
    def load_data(self):
        print(colored(f"📂 Loading data from: {self.export_path}", "cyan"))
        
        if not os.path.exists(self.events_path):
            print(colored("❌ events.jsonl not found!", "red"))
            return False
            
        with open(self.events_path, 'r') as f:
            for line in f:
                try:
                    event = json.loads(line)
                    etype = event.get('type')
                    payload = event.get('payload', {})
                    
                    if etype == 'DataSnapshotEvent':
                        self.snapshots.append(payload)
                    elif etype == 'DecisionEvent':
                        self.decisions.append(payload)
                    elif etype == 'ModuleOpinionEvent':
                        self.opinions.append(payload)
                    elif etype == 'ForecastEvent':
                        self.forecasts.append(payload)
                except Exception as e:
                    print(colored(f"⚠️ Error parsing line: {e}", "yellow"))
                    
        print(colored(f"✅ Loaded {len(self.snapshots)} snapshots, {len(self.decisions)} decisions, {len(self.opinions)} opinions, {len(self.forecasts)} forecasts.", "green"))
        return True

    def analyze_decisions(self):
        if not self.decisions:
            print("No decisions to analyze.")
            return

        df = pd.DataFrame(self.decisions)
        
        print("\n" + colored("📊 Decision Distribution", "blue", attrs=['bold']))
        if 'action' in df.columns:
            print(tabulate(df['action'].value_counts().reset_index(), headers=['Action', 'Count'], tablefmt='pretty'))
        
        print("\n" + colored("🕒 Decision Timeline", "blue", attrs=['bold']))
        # In V0, timestamp might be missing in payload directly, need to check structure
        # Assuming we can grab it from filename or order. 
        # Actually Event wrapper has timestamp. But here we load payload.
        # Let's fix parser to include wrapper timestamp if needed.
        
        # For now, just listing last 5
        if not df.empty:
            print(tabulate(df.tail(5)[['symbol', 'action']], headers=['Symbol', 'Action'], tablefmt='pretty'))

    def analyze_forecasts(self):
        if not self.forecasts:
            print(colored("\nNo forecasts found to analyze.", "yellow"))
            return

        df = pd.DataFrame(self.forecasts)
        print("\n" + colored("🔮 Forecast Analysis (Prometheus)", "cyan", attrs=['bold']))
        
        # Summary by Confidence
        print("Average Confidence Score: {:.1f}%".format(df['confidence_score'].mean()))
        
        # Last 5 Forecasts
        cols = ['symbol', 'current_price', 'predicted_price_5d', 'confidence_score']
        print(tabulate(df.tail(5)[cols], headers=['Symbol', 'Now', 'Pred(5d)', 'Conf%'], tablefmt='pretty'))

    def audit_linkage(self):
        print("\n" + colored("🔗 Quality Assurance (Data Linkage)", "magenta", attrs=['bold']))
        linked_count = 0
        total_decisions = len(self.decisions)
        
        for d in self.decisions:
            blobs = d.get('input_blobs', [])
            is_valid = False
            for b in blobs:
                h = b.get('hash_id')
                # Check if this hash exists in snapshots
                # Use a set for O(1) in production
                if any(s['snapshot_id'] == h for s in self.snapshots):
                    is_valid = True
                    break
            
            if is_valid:
                linked_count += 1
                
        print(f"Decisions with Valid Data Linkage: {linked_count}/{total_decisions}")
        if total_decisions > 0:
            pct = (linked_count / total_decisions) * 100
            color = "green" if pct == 100 else "red"
            print(colored(f"Integrity Score: {pct:.1f}%", color))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Argus Black Box Analyst')
    parser.add_argument('path', help='Path to unzipped export folder')
    args = parser.parse_args()
    
    analyst = ArgusAnalyst(args.path)
    if analyst.load_data():
        analyst.analyze_decisions()
        analyst.analyze_forecasts()
        analyst.audit_linkage()

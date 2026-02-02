import os
import pandas as pd
import matplotlib.pyplot as plt

def generate_plots(run_dir: str):
    """
    Reads metrics.csv from run_dir and generates equity.png and drawdown.png.
    """
    metrics_path = os.path.join(run_dir, "metrics.csv")
    if not os.path.exists(metrics_path):
        print(f"No metrics.csv found in {run_dir}")
        return

    try:
        df = pd.read_csv(metrics_path)
        
        # Ensure we have data
        if df.empty:
            print("metrics.csv is empty")
            return

        # Plot Equity
        plt.figure(figsize=(10, 6))
        plt.plot(df['Bar'], df['Equity'], label='Equity', color='blue')
        plt.title('Equity Curve')
        plt.xlabel('Bar')
        plt.ylabel('Equity ($)')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.savefig(os.path.join(run_dir, "equity.png"))
        plt.close()

        # Calculate Drawdown if not explicitly in metrics, but metrics usually has Equity.
        # metrics.csv cols: Bar, Timestamp, Equity, Balance, UnrealizedPnL, PositionQty, Type
        
        # Calculate DD curve
        equity = df['Equity']
        running_max = equity.cummax()
        drawdown = (equity - running_max) / running_max
        
        # Plot Drawdown
        plt.figure(figsize=(10, 6))
        plt.plot(df['Bar'], drawdown, label='Drawdown', color='red')
        plt.fill_between(df['Bar'], drawdown, 0, color='red', alpha=0.1)
        plt.title('Drawdown Curve')
        plt.xlabel('Bar')
        plt.ylabel('Drawdown %')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.savefig(os.path.join(run_dir, "drawdown.png"))
        plt.close()
        
        print(f"Plots saved to {run_dir}")

    except Exception as e:
        print(f"Error generating plots: {e}")

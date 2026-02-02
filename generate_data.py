import csv
import time

# Generated sine wave like data for > 50 bars to trigger Aegean
# Price around 40k. 
base_time = 1704067200000
price = 40000.0
data = []

# Create an uptrend then downtrend
for i in range(6000):
    ts = base_time + (i * 60000)
    
    # Simple uptrend for first 60 bars
    if i < 60:
        price += 50 
    else:
        price -= 50
        
    op = price
    hi = price + 20
    lo = price - 20
    cl = price + 10 # Bullish closes mostly
    vol = 100
    
    data.append([ts, op, hi, lo, cl, vol])
    
with open("argus_py/data/sample.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp","open","high","low","close","volume"])
    writer.writerows(data)

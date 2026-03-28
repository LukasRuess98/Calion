"""
Check what variables are available in the model
and verify they're being exported
"""

import pandas as pd
from pathlib import Path

print("="*70)
print("CSV DATA COMPLETENESS CHECK")
print("="*70)

csv_path = Path("outputs/runs/thermal_network_results/unified_timeseries.csv")

if csv_path.exists():
    df = pd.read_csv(csv_path, sep=';')
    
    print(f"\nActual columns in exported CSV: {len(df.columns)}")
    for col in df.columns:
        print(f"  - {col}")
    
    # Check first few rows
    print("\nFirst 5 rows:")
    print(df.head())
    
    # === Analysis ===
    print("\n" + "="*70)
    print("DATA ANALYSIS")
    print("="*70)
    
    if 'heat_demand_MW' in df.columns:
        d = df['heat_demand_MW']
        print(f"\n✓ Heat Demand Data:")
        print(f"  - Values range: {d.min():.2f} to {d.max():.2f} MW")
        print(f"  - Annual energy: {(d.sum()/1000):.2f} GWh")
        print(f"  - Average: {d.mean():.2f} MW")
        print(f"  - Non-zero hours: {(d > 0).sum()} / {len(d)}")
    
    print("\n⚠️  NOTE: CSV only has 2 columns (timestep + heat_demand)")
    print("Expected 8+ columns based on code (Q_boiler, Q_hp, P_buy, etc.)")
    print("\nPossible reasons:")
    print("  1. Variables don't exist in copperplate model (expected)")
    print("  2. Variables exist but are None/uninitialized")
    print("  3. Need to run with networked config (level2, level3)")
    
else:
    print("CSV file not found!")

#!/usr/bin/env python3
"""
ENERGIS INFEASIBILITY DIAGNOSTICS - PHASE 1
Demand vs Capacity Analysis
"""

import pandas as pd

df = pd.read_csv('data/Import_Data.csv')

print("=" * 60)
print("ENERGIS INFEASIBILITY DIAGNOSTICS - PHASE 1")
print("=" * 60)

print("\n[1] DEMAND ANALYSE")
print("-" * 60)
max_demand = df['waermebedarf_MWth'].max()
min_demand = df['waermebedarf_MWth'].min()
mean_demand = df['waermebedarf_MWth'].mean()
std_demand = df['waermebedarf_MWth'].std()

print(f"Max demand:  {max_demand:.2f} MW")
print(f"Min demand:  {min_demand:.2f} MW")
print(f"Mean demand: {mean_demand:.2f} MW")
print(f"Std demand:  {std_demand:.2f} MW")

print("\n[2] CAPACITY CHECK")
print("-" * 60)
boiler_cap = 150  # MW
hp_cap = 80       # MW
total_cap = boiler_cap + hp_cap
margin_abs = total_cap - max_demand
margin_pct = 100 * margin_abs / total_cap

print(f"Boiler capacity:     {boiler_cap} MW")
print(f"HP capacity:         {hp_cap} MW")
print(f"Total supply:        {total_cap} MW")
print(f"Peak demand:         {max_demand:.2f} MW")
print(f"Reserve margin:      {margin_abs:.2f} MW ({margin_pct:.1f}%)")

if margin_abs < 0:
    print("\n❌ CRITICAL: DEMAND > CAPACITY (INFEASIBLE PER SE)")
else:
    print("\n✅ Capacity check PASSED")

print("\n[3] TIME-SERIES STATISTICS")
print("-" * 60)
print(f"Total timesteps: {len(df)}")
print(f"Date range: {df['Datum'].min()} to {df['Datum'].max()}")
print(f"Missing values: {df['waermebedarf_MWth'].isna().sum()}")

print("\n[4] DEMAND PERCENTILE DISTRIBUTION")
print("-" * 60)
for p in [10, 25, 50, 75, 90, 95]:
    val = df['waermebedarf_MWth'].quantile(p/100)
    print(f"P{p:2d}: {val:.2f} MW")

print("\n" + "=" * 60)
print("DIAGNOSIS RESULT")
print("=" * 60)
if margin_pct > 20:
    print("✅ PASS: Ausreichende Kapazität vorhanden (>20% Reserve)")
    print("→ Weiter zu PHASE 2: Config-Validierung")
elif margin_pct > 0:
    print("⚠️  WARNING: Reserve < 20%, aber noch OK")
    print("→ Weiter zu PHASE 2: Config-Validierung")
else:
    print("❌ FAIL: Nicht genug Kapazität!")
    print("→ Erhöhe Boiler/HP Kapazitäten in Config")

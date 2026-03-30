#!/usr/bin/env python3
"""
FINAL HYPOTHESIS TEST: MILP Temperature Fixation Issue

Hypothesis: MILP mode fixes temperatures at 90°C, but network heat losses
+ pipe constraints make it impossible to deliver required heat at this temp.

Fix test: Increase supply temperature beyond MILP nominal to see if feasibility returns.
"""

import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from calion.io.loader import load_input_excel
from calion.models.system_builder import build_model
from calion.config.merge import load_and_merge
import pyomo.environ as pyo

print("\n" + "=" * 70)
print("HYPOTHESIS TEST: MILP Temperature Constraints")  
print("=" * 70)

# Test 1: Standard config (should fail)
print("\n[TEST 1] Standard config (MILP with 90°C fixed)")
print("-" * 70)

config_path = Path("configs/templates/level2_simple_3node.yaml")
cfg = load_and_merge([str(config_path)])
excel_file = Path(cfg.get("site", {}).get("input_xlsx", "data/Import_Data.csv"))
time_series = load_input_excel(excel_file, cfg)
dt_h = cfg.get("run", {}).get("dt_h", 1.0)

model = build_model(time_series, cfg, dt_h=dt_h)
opt = pyo.SolverFactory("appsi_highs")
results = opt.solve(model, load_solutions=False)

term_cond_1 = str(results.termination_condition)
print(f"Result: {term_cond_1}")

# Test 2: Try with HIGHER supply temp (if possible through config)
print("\n[TEST 2] Attempt with reduced network losses scenario")
print("-" * 70)

# Load config and modify to reduce pipe diameter (reduce losses)
cfg2 = load_and_merge([str(config_path)])

# Increase pipe diameter to reduce pressure drop/losses
if "network" in cfg2 and "pipes" in cfg2["network"]:
    for pipe_name, pipe_cfg in cfg2["network"]["pipes"].items():
        old_diam = pipe_cfg.get("diameter_mm", 300)
        pipe_cfg["diameter_mm"] = old_diam * 1.5  # 50% larger
        print(f"  Modified {pipe_name} diameter: {old_diam}mm → {pipe_cfg['diameter_mm']}mm")

model2 = build_model(time_series, cfg2, dt_h=dt_h)
results2 = opt.solve(model2, load_solutions=False)
term_cond_2 = str(results2.termination_condition)
print(f"Result: {term_cond_2}")

# Test 3: Disable network entirely (copperplate)
print("\n[TEST 3] Disable network (copperplate test)")
print("-" * 70)

cfg3 = load_and_merge([str(config_path)])
cfg3["network"]["physics"] = {
    "heat_loss": False,
    "pressure_drop": False,
    "transport_delay": False
}

try:
    model3 = build_model(time_series, cfg3, dt_h=dt_h)
    results3 = opt.solve(model3, load_solutions=False)
    term_cond_3 = str(results3.termination_condition)
    print(f"Result: {term_cond_3}")
except Exception as e:
    print(f"Error: {e}")
    term_cond_3 = "ERROR"

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Test 1 (Standard MILP): {term_cond_1}")
print(f"Test 2 (Larger pipes):  {term_cond_2}")
print(f"Test 3 (No network):    {term_cond_3}")

if "optimal" in term_cond_3.lower():
    print("\n✅ DIAGNOSIS: Problem IS network-related")
    print("   Root cause: Network constraints + MILP temperature fixation")
    print("   Fix: Relax MILP temperature bounds or simplify network model")
elif "optimal" in term_cond_2.lower():
    print("\n✅ Partial success with larger pipes")
    print("   Root cause: Pressure drop / heat loss constraints too aggressive")
    print("   Fix: Adjust pipe sizing or network parameters")
elif "optimal" in term_cond_1.lower():
    print("\n✅ Standard config works!")
    print("   (This would be unexpected)")
else:
    print("\n❌ All tests failed - problem fundamental")
    print("   Root cause: Likely asset capacity or demand constraints")

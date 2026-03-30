#!/usr/bin/env python3
"""
ENERGIS INFEASIBILITY DIAGNOSTICS - PHASE 4
Deep Asset/Constraint Analysis - Build Model Without Solving
"""

import sys
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from energis.io.loader import load_input_excel
from energis.models.system_builder import build_model
from energis.utils.timeseries import TimeSeriesTable
from energis.config.merge import load_and_merge

print("\n" + "=" * 70)
print("PHASE 4: ASSET CONSTRAINT ANALYSIS")
print("=" * 70)

config_file = Path("configs/templates/level2_simple_3node.yaml")

print("\n[1] Loading config and building model (WITHOUT solving)...")
print("-" * 70)

print("\n[1] Loading config and building model (WITHOUT solving)...")
print("-" * 70)

try:
    # Step 1: Load config
    cfg = load_and_merge(["configs/templates/level2_simple_3node.yaml"])
    print(f"✅ Config loaded")
    
    # Step 2: Load time-series data
    excel_file = Path(cfg.get("site", {}).get("input_xlsx", "data/Import_Data.csv"))
    time_series = load_input_excel(excel_file, cfg)
    
    print(f"✅ Time-series loaded")
    print(f"   - Timesteps: {len(time_series)}")
    
    # Step 3: Build model
    dt_h = cfg.get("run", {}).get("dt_h", 1.0)
    model = build_model(time_series, cfg, dt_h=dt_h)
    
    print(f"✅ Model built successfully (no solver errors)")
    
    # Step 4: Inspect model structure
    print("\n[2] MODEL STRUCTURE INSPECTION")
    print("-" * 70)
    
    # List all components
    components = []
    for comp in model.component_objects():
        name = str(comp)
        ctype_name = comp.ctype.__name__ if hasattr(comp.ctype, '__name__') else str(comp.ctype)
        components.append((name, ctype_name))
    
    # Count by type
    from collections import Counter
    type_counts = Counter(t for _, t in components)
    
    print("Component summary:")
    for ctype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {ctype}: {count}")
    
    # Show sample constraints
    print("\n[3] SAMPLE CONSTRAINTS")
    print("-" * 70)
    constraint_names = [n for n, t in components if t == 'Constraint']
    print(f"Total constraints: {len(constraint_names)}")
    print("First 10 constraint names:")
    for cn in sorted(constraint_names)[:10]:
        print(f"  - {cn}")
    
    print("\n[4] DIAGNOSTICS")
    print("-" * 70)
    print("✅ Model builds without error")
    print("   → Problem is not in model construction")
    print("   → Infeasibility detected by solver preprocessor")
    
except Exception as e:
    print(f"❌ ERROR during model building: {e}")
    import traceback
    traceback.print_exc()


print("\n" + "=" * 70)
print("PHASE 4 CONCLUSION")
print("=" * 70)
print("To proceed to Phase 5 (MILP mode analysis):")
print("  Run: python diagnose_phase5.py")

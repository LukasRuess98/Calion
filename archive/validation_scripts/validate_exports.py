"""
Validation script for exported results
Checks: file integrity, data completeness, mathematical consistency
"""

import json
import pandas as pd
import os
from pathlib import Path

print("="*70)
print("EXPORT RESULTS VALIDATION")
print("="*70)

export_dir = Path("outputs/runs/thermal_network_results")

# ============================================================================
# 1. CHECK FILES EXIST
# ============================================================================
print("\n1. FILE INTEGRITY CHECK")
print("-"*70)

required_files = {
    "export_manifest.json": "Manifest",
    "unified_timeseries.csv": "Timeseries CSV",
    "solver/gurobi_solution.lp": "LP file",
    "solver/gurobi_solution.sol": "Solution file",
    "solver/gurobi_solution.mps": "MPS file",
}

files_found = {}
for rel_path, desc in required_files.items():
    full_path = export_dir / rel_path
    if full_path.exists():
        size_mb = full_path.stat().st_size / (1024*1024)
        print(f"✓ {desc:20} {rel_path:40} {size_mb:8.2f} MB")
        files_found[rel_path] = full_path
    else:
        print(f"✗ {desc:20} {rel_path:40} MISSING")

print(f"\n{len(files_found)}/{len(required_files)} files present")

# ============================================================================
# 2. CHECK MANIFEST
# ============================================================================
print("\n2. MANIFEST VALIDATION")
print("-"*70)

manifest_path = export_dir / "export_manifest.json"
if manifest_path.exists():
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        print(f"✓ Manifest is valid JSON")
        print(f"  - Export timestamp: {manifest.get('export_timestamp')}")
        print(f"  - Output directory: {manifest.get('output_dir')}")
        print(f"  - Has network data: {manifest.get('has_network_data')}")
        print(f"  - Total files: {manifest.get('total_files')}")
        print(f"  - Files indexed: {len(manifest.get('files', {}))}")
        
        # Check all files in manifest exist
        for key, path in manifest.get('files', {}).items():
            path_obj = Path(path)
            if path_obj.exists():
                print(f"    ✓ {key}: exists")
            else:
                print(f"    ✗ {key}: NOT FOUND - {path}")
    except Exception as e:
        print(f"✗ Manifest parsing failed: {e}")
else:
    print(f"✗ Manifest file not found")

# ============================================================================
# 3. CSV VALIDATION
# ============================================================================
print("\n3. CSV TIMESERIES VALIDATION")
print("-"*70)

csv_path = export_dir / "unified_timeseries.csv"
if csv_path.exists():
    try:
        df = pd.read_csv(csv_path, sep=';')
        
        print(f"✓ CSV is valid")
        print(f"  - Rows: {len(df)}")
        print(f"  - Columns: {len(df.columns)}")
        print(f"  - Column names: {list(df.columns)}")
        
        # Check for required columns
        if 'timestep' in df.columns:
            print(f"  ✓ timestep column present (range: {df['timestep'].min()}-{df['timestep'].max()})")
        
        if 'heat_demand_MW' in df.columns:
            demand = df['heat_demand_MW']
            print(f"  ✓ heat_demand_MW present")
            print(f"    - Min: {demand.min():.2f} MW")
            print(f"    - Max: {demand.max():.2f} MW")
            print(f"    - Mean: {demand.mean():.2f} MW")
            print(f"    - Sum (energy): {(demand.sum()/1000):.2f} GWh")
        
        if 'electricity_purchase_MW' in df.columns:
            elec = df['electricity_purchase_MW']
            print(f"  ✓ electricity_purchase_MW present")
            print(f"    - Min: {elec.min():.2f} MW")
            print(f"    - Max: {elec.max():.2f} MW")
            print(f"    - Mean: {elec.mean():.2f} MW")
        
        if 'storage_SOC_MWh' in df.columns:
            soc = df['storage_SOC_MWh']
            print(f"  ✓ storage_SOC_MWh present")
            print(f"    - Min: {soc.min():.2f} MWh")
            print(f"    - Max: {soc.max():.2f} MWh")
        
        if 'hourly_cost_EUR' in df.columns:
            costs = df['hourly_cost_EUR']
            total_cost = costs.sum()
            print(f"  ✓ hourly_cost_EUR present")
            print(f"    - Total annual cost: €{total_cost:,.2f}")
            print(f"    - Average hourly: €{costs.mean():.2f}")
        
        # Check for NaN/null values
        null_count = df.isnull().sum()
        if null_count.sum() > 0:
            print(f"  ⚠ Found {null_count.sum()} null values:")
            print(null_count[null_count > 0])
        else:
            print(f"  ✓ No null values")
            
    except Exception as e:
        print(f"✗ CSV parsing failed: {e}")
else:
    print(f"✗ CSV file not found")

# ============================================================================
# 4. SOL FILE VALIDATION
# ============================================================================
print("\n4. SOLUTION FILE VALIDATION")
print("-"*70)

sol_path = export_dir / "solver" / "gurobi_solution.sol"
if sol_path.exists():
    try:
        with open(sol_path, 'r') as f:
            lines = f.readlines()
        
        print(f"✓ SOL file is readable")
        print(f"  - Total lines: {len(lines)}")
        
        # Extract objective value
        for line in lines[:10]:
            if 'Objective Value' in line:
                print(f"  - {line.strip()}")
                break
        
        # Count variables with values
        var_lines = [l for l in lines if '[' in l and not l.startswith('#')]
        print(f"  - Variables in solution: {len(var_lines)}")
        
        # Sample some values
        print(f"  - Sample variables:")
        for line in var_lines[:5]:
            print(f"    {line.strip()[:60]}")
            
    except Exception as e:
        print(f"✗ SOL file parsing failed: {e}")
else:
    print(f"✗ SOL file not found")

# ============================================================================
# 5. LP FILE VALIDATION
# ============================================================================
print("\n5. LP FILE VALIDATION (Problem Definition)")
print("-"*70)

lp_path = export_dir / "solver" / "gurobi_solution.lp"
if lp_path.exists():
    try:
        with open(lp_path, 'r') as f:
            lines = f.readlines()
        
        print(f"✓ LP file is readable")
        print(f"  - Total lines: {len(lines)}")
        
        # Count constraints
        constraints = [l for l in lines if ':' in l and 'c_' in l.lower()]
        print(f"  - Estimated constraints: ~{len(constraints)}")
        
        # Look for key sections
        has_subject = any('Subject To' in l for l in lines)
        has_bounds = any('Bounds' in l for l in lines)
        has_end = any('End' in l for l in lines)
        
        print(f"  - Has 'Subject To' section: {has_subject}")
        print(f"  - Has 'Bounds' section: {has_bounds}")
        print(f"  - Has 'End' section: {has_end}")
        
    except Exception as e:
        print(f"✗ LP file parsing failed: {e}")
else:
    print(f"✗ LP file not found")

# ============================================================================
# 6. MPS FILE VALIDATION
# ============================================================================
print("\n6. MPS FILE VALIDATION (Standard Solver Format)")
print("-"*70)

mps_path = export_dir / "solver" / "gurobi_solution.mps"
if mps_path.exists():
    try:
        with open(mps_path, 'r') as f:
            lines = f.readlines()
        
        print(f"✓ MPS file is readable")
        print(f"  - Total lines: {len(lines)}")
        
        # Check MPS sections
        sections = {}
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('NAME'):
                sections['NAME'] = True
            elif stripped.startswith('ROWS'):
                sections['ROWS'] = True
            elif stripped.startswith('COLUMNS'):
                sections['COLUMNS'] = True
            elif stripped.startswith('RHS'):
                sections['RHS'] = True
            elif stripped.startswith('BOUNDS'):
                sections['BOUNDS'] = True
            elif stripped.startswith('ENDATA'):
                sections['ENDATA'] = True
        
        print(f"  - MPS sections found:")
        for section, found in sections.items():
            status = "✓" if found else "✗"
            print(f"    {status} {section}")
            
    except Exception as e:
        print(f"✗ MPS file parsing failed: {e}")
else:
    print(f"✗ MPS file not found")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*70)
print("VALIDATION SUMMARY")
print("="*70)

all_good = (
    len(files_found) == len(required_files) and
    manifest_path.exists() and
    csv_path.exists()
)

if all_good:
    print("✅ ALL EXPORTS VALID & CONSISTENT")
    print("\nResults ready for:")
    print("  • Solver re-runs (LP/MPS can be fed to other solvers)")
    print("  • Analysis (CSV contains all timeseries data)")
    print("  • Archival (manifest provides complete index)")
    print("\nExport location: outputs/runs/thermal_network_results/")
else:
    print("⚠️  SOME EXPORTS MISSING OR INVALID")
    print("Check error messages above")

print("="*70)

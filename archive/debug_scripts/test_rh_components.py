#!/usr/bin/env python3
"""
RH Component Isolation Test

This script systematically tests Rolling Horizon optimization with different
component combinations to isolate infeasibility causes.

Tests:
1. RH with ONLY storage (HP disabled)
2. RH with ONLY heat pumps (storage disabled)
3. RH with storage + HP (current failing case)
4. Check WRG data quality in Excel

Usage:
    python scripts/test_rh_components.py
"""

import sys
from pathlib import Path
import yaml
import pandas as pd

# Add project root to path
current = Path.cwd()
for candidate in [current] + list(current.parents):
    if (candidate / 'energis').exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        PROJECT_ROOT = candidate
        break

from energis.run import rolling_horizon as rh


def load_config(config_path: Path) -> dict:
    """Load YAML config."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def save_config(config: dict, config_path: Path) -> None:
    """Save YAML config."""
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def check_wrg_data(data_file: Path) -> None:
    """Check WRG data quality in Excel."""
    print("\n" + "=" * 70)
    print("CHECKING WRG DATA QUALITY")
    print("=" * 70)

    if not data_file.exists():
        print(f"ERROR: Data file not found: {data_file}")
        return

    # Read Excel file
    df = pd.read_excel(data_file)

    print(f"\nLoaded {len(df)} rows from {data_file.name}")
    print(f"Columns: {list(df.columns)}")

    # Check WRG columns
    wrg_cols = {
        'WRG1_Q_MW': ['WRG1Q MW', 'WRG1_Q MW'],
        'WRG1_T_K': ['WRG1_T °C', 'WRG1 T °C'],
        'WRG2_Q_MW': ['WRG2Q MW', 'WRG2_Q MW'],
        'WRG2_T_K': ['WRG2_T °C', 'WRG2 T °C'],
        'WRG3_Q_MW': ['WRG3Q MW', 'WRG3_Q MW'],
        'WRG3_T_K': ['WRG3_T °C', 'WRG3 T °C'],
        'WRG4_Q_MW': ['WRG4Q MW', 'WRG4_Q MW'],
        'WRG4_T_K': ['WRG4_T °C', 'WRG4 T °C'],
    }

    print("\nWRG Column Analysis:")
    for target_col, candidates in wrg_cols.items():
        found_col = None
        for candidate in candidates:
            if candidate in df.columns:
                found_col = candidate
                break

        if found_col:
            values = df[found_col]
            print(f"\n  {target_col} (found as '{found_col}'):")
            print(f"    - Count: {len(values)}")
            print(f"    - Non-null: {values.notna().sum()}")
            print(f"    - Null: {values.isna().sum()}")
            print(f"    - Min: {values.min():.2f}")
            print(f"    - Max: {values.max():.2f}")
            print(f"    - Mean: {values.mean():.2f}")
            print(f"    - Zeros: {(values == 0).sum()}")
            print(f"    - Negatives: {(values < 0).sum()}")

            # Check for problematic values
            if values.isna().sum() > 0:
                print(f"    ⚠️  WARNING: {values.isna().sum()} NaN values!")
            if (values < 0).sum() > 0:
                print(f"    ⚠️  WARNING: {(values < 0).sum()} negative values!")
            if (values == 0).sum() == len(values):
                print(f"    ⚠️  WARNING: All values are zero!")
        else:
            print(f"\n  {target_col}: NOT FOUND (candidates: {candidates})")


def test_rh_scenario(name: str, enable_storage: bool, enable_hp: bool) -> bool:
    """Test RH with specific component configuration."""
    print("\n" + "=" * 70)
    print(f"TEST: {name}")
    print("=" * 70)
    print(f"Storage: {'ENABLED' if enable_storage else 'DISABLED'}")
    print(f"Heat Pumps: {'ENABLED' if enable_hp else 'DISABLED'}")

    # Load config
    config_path = PROJECT_ROOT / 'configs' / 'stadtbach.yaml'
    config = load_config(config_path)

    # Modify config
    if 'system' not in config:
        config['system'] = {}

    # Set storage
    if 'storage' not in config['system']:
        config['system']['storage'] = {}
    config['system']['storage']['enabled'] = enable_storage

    # Set heat pumps
    if 'heat_pumps' not in config['system']:
        config['system']['heat_pumps'] = []
    for hp in config['system']['heat_pumps']:
        hp['enabled'] = enable_hp

    # Save modified config to temp file
    temp_config_path = PROJECT_ROOT / 'configs' / 'stadtbach_test.yaml'
    save_config(config, temp_config_path)

    # Run RH
    try:
        print(f"\nRunning RH optimization...")
        workflow = rh.run_workflow([str(temp_config_path)])
        print(f"✅ SUCCESS: RH completed without errors")

        # Check if we got results
        result = workflow.rh_result or workflow.pf_result
        if result:
            print(f"   Results available: {len(result.series)} time series")

            # Check storage if enabled
            if enable_storage and 'TES_SOC_MWh' in result.series:
                soc = result.series['TES_SOC_MWh']
                soc_std = pd.Series(soc).std()
                print(f"   Storage SOC std: {soc_std:.2f} MWh")
                if soc_std > 10:
                    print(f"   ✅ Storage is actively cycling")
                else:
                    print(f"   ⚠️  Storage appears inactive (low variance)")

            # Check heat pumps if enabled
            if enable_hp:
                hp_series = [k for k in result.series.keys() if k.startswith('HP')]
                if hp_series:
                    print(f"   Heat pump series found: {hp_series[:3]}...")
                    for hp_key in hp_series[:4]:  # Check first 4 HP series
                        hp_vals = result.series[hp_key]
                        hp_sum = sum(hp_vals)
                        if hp_sum > 0:
                            print(f"   ✅ {hp_key}: Total output = {hp_sum:.2f} MWh")
                        else:
                            print(f"   ⚠️  {hp_key}: No output (sum=0)")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")

        # Check if it's infeasibility
        if 'infeasible' in str(e).lower() or 'unbounded' in str(e).lower():
            print(f"\n   INFEASIBILITY DETECTED")
            print(f"   This component combination causes infeasible model!")

        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up temp config
        if temp_config_path.exists():
            temp_config_path.unlink()


def main():
    print("=" * 70)
    print("RH COMPONENT ISOLATION TEST")
    print("=" * 70)
    print(f"Project root: {PROJECT_ROOT}")

    # Guard: skip when required config is absent
    config_path = PROJECT_ROOT / 'configs' / 'stadtbach.yaml'
    if not config_path.exists():
        print(f"\nSKIPPED: Integration config not available: {config_path}")
        print("This script requires a site-specific config (not shipped with the repo).")
        return

    # First check WRG data
    data_file = PROJECT_ROOT / 'Import_Data.xlsx'
    check_wrg_data(data_file)

    # Test different component combinations
    results = {}

    # Test 1: Storage only
    results['storage_only'] = test_rh_scenario(
        "Storage ONLY (HP disabled)",
        enable_storage=True,
        enable_hp=False
    )

    # Test 2: Heat pumps only
    results['hp_only'] = test_rh_scenario(
        "Heat Pumps ONLY (Storage disabled)",
        enable_storage=False,
        enable_hp=True
    )

    # Test 3: Both enabled (current failing case)
    results['both'] = test_rh_scenario(
        "Storage + Heat Pumps (BOTH enabled)",
        enable_storage=True,
        enable_hp=True
    )

    # Test 4: Neither enabled (baseline)
    results['neither'] = test_rh_scenario(
        "BASELINE (Both disabled)",
        enable_storage=False,
        enable_hp=False
    )

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for test_name, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{test_name:20s}: {status}")

    # Diagnosis
    print("\n" + "=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)

    if not results['both'] and results['storage_only'] and results['hp_only']:
        print("❌ INTERACTION BUG: Storage and HP work separately but fail together")
        print("   Likely causes:")
        print("   - Terminal constraint + investment conflict")
        print("   - Heat pump WRG constraints conflicting with storage operation")
        print("   - Over-constrained system when both are active")

    elif not results['both'] and not results['storage_only'] and results['hp_only']:
        print("❌ STORAGE BUG: Storage causes infeasibility even alone")
        print("   Likely causes:")
        print("   - Terminal constraint too restrictive")
        print("   - Investment optimization with terminal constraint impossible")
        print("   - SOC carryover between windows problematic")

    elif not results['both'] and results['storage_only'] and not results['hp_only']:
        print("❌ HEAT PUMP BUG: Heat pumps cause infeasibility even alone")
        print("   Likely causes:")
        print("   - WRG data has NaN, negative, or zero values")
        print("   - WRG capacity constraints too restrictive")
        print("   - COP calculation issues with temperature data")

    elif not results['both'] and not results['storage_only'] and not results['hp_only']:
        print("❌ MULTIPLE BUGS: Both storage and HP have individual issues")
        print("   Need to fix each component separately")

    else:
        print("✅ ALL TESTS PASSED")
        print("   If you still see infeasibility, check:")
        print("   - Network topology (currently disabled)")
        print("   - Data file dates/ranges")
        print("   - Solver settings")


if __name__ == "__main__":
    main()

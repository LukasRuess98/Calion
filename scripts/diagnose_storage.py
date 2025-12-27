#!/usr/bin/env python3
"""
Storage Diagnostic Tool

This script analyzes optimization results to diagnose storage cycling issues.
It checks:
1. SOC values over time
2. Charge/discharge patterns
3. Terminal constraint compliance
4. Investment decisions across windows

Usage:
    python scripts/diagnose_storage.py <results_directory>
"""

import sys
import json
from pathlib import Path
import pandas as pd


def analyze_storage_results(results_dir: Path):
    """Analyze storage behavior from results directory."""

    print("=" * 70)
    print("STORAGE DIAGNOSTIC TOOL")
    print("=" * 70)

    # Look for results files
    results_file = results_dir / "results.json"
    timeseries_file = results_dir / "timeseries.csv"

    if not results_file.exists() and not timeseries_file.exists():
        print(f"\nERROR: No results found in {results_dir}")
        print("Looking for either 'results.json' or 'timeseries.csv'")
        return

    # Load timeseries data
    if timeseries_file.exists():
        print(f"\n[1] Loading timeseries from {timeseries_file}")
        df = pd.read_csv(timeseries_file)

        # Find storage columns
        soc_cols = [col for col in df.columns if 'SOC' in col or 'soc' in col]
        charge_cols = [col for col in df.columns if 'charge' in col.lower()]
        discharge_cols = [col for col in df.columns if 'discharge' in col.lower()]

        print(f"\nStorage-related columns found:")
        print(f"  - SOC columns: {soc_cols}")
        print(f"  - Charge columns: {charge_cols}")
        print(f"  - Discharge columns: {discharge_cols}")

        if soc_cols:
            soc_col = soc_cols[0]
            print(f"\n[2] Analyzing SOC behavior using column: {soc_col}")

            soc_values = df[soc_col].values
            print(f"  - First 10 timesteps: {soc_values[:10]}")
            print(f"  - Last 10 timesteps: {soc_values[-10:]}")
            print(f"  - Min SOC: {soc_values.min():.2f} MWh")
            print(f"  - Max SOC: {soc_values.max():.2f} MWh")
            print(f"  - Mean SOC: {soc_values.mean():.2f} MWh")
            print(f"  - Std SOC: {soc_values.std():.2f} MWh")

            # Check if SOC is constant (indicating no activity)
            if soc_values.std() < 1.0:
                print(f"\n  ⚠️  WARNING: SOC is nearly constant (std={soc_values.std():.3f})")
                print(f"     This suggests storage is NOT charging/discharging!")

            # Check initial vs final SOC
            soc_first = soc_values[0]
            soc_last = soc_values[-1]
            print(f"\n  - Initial SOC: {soc_first:.2f} MWh")
            print(f"  - Final SOC: {soc_last:.2f} MWh")
            print(f"  - Difference: {soc_last - soc_first:.2f} MWh")

            if abs(soc_last - soc_first) > 1.0:
                print(f"  ⚠️  WARNING: Terminal SOC != Initial SOC")
                print(f"     Cyclic constraint may not be working!")

            # Analyze activity over time
            print(f"\n[3] Analyzing storage activity over time")

            # Split into 10 equal periods and check SOC variance
            n_periods = 10
            period_len = len(soc_values) // n_periods

            for i in range(n_periods):
                start_idx = i * period_len
                end_idx = (i + 1) * period_len if i < n_periods - 1 else len(soc_values)
                period_soc = soc_values[start_idx:end_idx]
                period_std = period_soc.std()
                period_mean = period_soc.mean()

                activity_status = "ACTIVE" if period_std > 1.0 else "INACTIVE"
                print(f"  Period {i+1:2d} [{start_idx:4d}-{end_idx:4d}]: "
                      f"mean={period_mean:6.1f} MWh, std={period_std:5.2f} MWh  [{activity_status}]")

        # Analyze charge/discharge
        if charge_cols and discharge_cols:
            print(f"\n[4] Analyzing charge/discharge patterns")

            charge_col = charge_cols[0]
            discharge_col = discharge_cols[0]

            charge_values = df[charge_col].values
            discharge_values = df[discharge_col].values

            total_charge = charge_values.sum()
            total_discharge = discharge_values.sum()

            print(f"  - Total energy charged: {total_charge:.2f} MWh")
            print(f"  - Total energy discharged: {total_discharge:.2f} MWh")
            print(f"  - Cycles: {total_discharge / soc_values.max():.2f}" if soc_values.max() > 0 else "  - Cycles: N/A")

            # Check if there's any activity
            if total_charge < 1.0 and total_discharge < 1.0:
                print(f"\n  ⚠️  WARNING: Almost no charge/discharge activity!")
                print(f"     Storage appears to be inactive!")

    # Load results.json if available
    if results_file.exists():
        print(f"\n[5] Loading results from {results_file}")
        with open(results_file, 'r') as f:
            results = json.load(f)

        # Check for investment results
        if 'investment' in results:
            print(f"\n  Investment decisions:")
            for key, value in results['investment'].items():
                print(f"    {key}: {value}")

    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_storage.py <results_directory>")
        print("\nExample:")
        print("  python scripts/diagnose_storage.py outputs/stadtbach_results")
        sys.exit(1)

    results_dir = Path(sys.argv[1])

    if not results_dir.exists():
        print(f"ERROR: Directory not found: {results_dir}")
        sys.exit(1)

    analyze_storage_results(results_dir)


if __name__ == "__main__":
    main()

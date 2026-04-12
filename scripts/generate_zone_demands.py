#!/usr/bin/env python3
"""
Generate independent zone-specific heat demand profiles.

Takes existing yearly demand and creates per-zone variations with stochastic patterns.
Each zone gets:
- Base fraction (to ensure total is conserved)
- Daily variation pattern (±20% variation day-to-day)
- Hourly random noise (±5%)
- Result: realistic heterogeneous demands with different peak times

Example:
    python scripts/generate_zone_demands.py \\
        --input data/Import_Data_yearly.csv \\
        --output data/Import_Data_yearly_zones.csv
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate_zone_demands(
    input_csv: str,
    output_csv: str,
    zone_fractions: dict,
    seed: int = 42,
    daily_std: float = 0.08,
    hourly_std: float = 0.05,
) -> None:
    """
    Generate independent zone-specific demands from total demand.

    Creates per-zone timeseries with independent temporal patterns by applying
    different stochastic variations to each zone's base demand fraction.

    Args:
        input_csv: Path to original Import_Data_yearly.csv
        output_csv: Path to save new file with zone columns
        zone_fractions: Dict of {zone_id: fraction} (must sum to ~1.0)
        seed: Random seed for reproducibility
        daily_std: Std dev of daily variation factor
        hourly_std: Std dev of hourly variation factor
    """
    np.random.seed(seed)

    # Load data
    df = pd.read_csv(input_csv)
    total_demand = df["waermebedarf_MWth"].values
    T = len(total_demand)

    print(f"Loaded {T} timesteps from {input_csv}")
    print(f"Total demand: {total_demand.sum():.1f} GWh/year")
    print(f"Zones: {len(zone_fractions)}")

    # Verify fractions sum to ~1.0
    frac_sum = sum(zone_fractions.values())
    print(f"Zone fraction sum: {frac_sum:.4f} (should be ~1.0)")
    if not (0.99 < frac_sum <= 1.01):
        raise ValueError(f"Zone fractions sum to {frac_sum}, not ~1.0")

    print("\n" + "=" * 70)
    print("Generating per-zone demands...")
    print("=" * 70)

    # Generate per-zone demands
    for zone_id, base_frac in zone_fractions.items():
        # Base profile (scale total by zone fraction)
        base_demand = total_demand * base_frac

        # Daily variation: create a smoothly varying daily pattern
        # Repeat every 24 hours to create coherent daily pattern
        n_days = T // 24
        daily_var = np.random.normal(1.0, daily_std, n_days)
        daily_mult = np.repeat(daily_var, 24)  # Repeat 24x per day
        daily_mult = daily_mult[:T]  # Trim to exact length

        # Hourly random noise (high-frequency variation)
        hourly_mult = np.random.normal(1.0, hourly_std, T)

        # Combined variation: base × daily pattern × hourly noise
        zone_demand = base_demand * daily_mult * hourly_mult

        # Clamp to non-negative (avoid negative demands)
        zone_demand = np.maximum(zone_demand, 0.01)

        df[f"{zone_id}_demand_MWth"] = zone_demand

        # Print zone statistics
        annual_gwh = zone_demand.sum()
        peak_mw = zone_demand.max()
        min_mw = zone_demand.min()
        avg_mw = zone_demand.mean()
        print(
            f"  {zone_id:12s} → {annual_gwh:7.1f} GWh/yr  "
            f"(min: {min_mw:5.2f} MW, avg: {avg_mw:5.2f} MW, peak: {peak_mw:6.2f} MW)"
        )

    # Validate: total should be close to original
    new_total = sum(df[f"{z}_demand_MWth"] for z in zone_fractions.keys()).sum()
    original_total = total_demand.sum()
    error_pct = 100 * (new_total - original_total) / original_total

    print("\n" + "-" * 70)
    print(f"Original total:     {original_total:.1f} GWh/year")
    print(f"Generated total:    {new_total:.1f} GWh/year")
    print(f"Difference:         {error_pct:+.1f}%")
    print("-" * 70)

    # Save
    df.to_csv(output_csv, index=False)
    print(f"\n✓ Saved to {output_csv}")
    print(f"  Columns: {len([c for c in df.columns if c.startswith('zone_')])} zone demand columns added")
    print(f"  Total file size: {Path(output_csv).stat().st_size / 1024:.1f} KB")


def main():
    parser = argparse.ArgumentParser(
        description="Generate independent zone-specific heat demand profiles"
    )
    parser.add_argument(
        "--input",
        default="data/Import_Data_yearly.csv",
        help="Input CSV file with total demand timeseries",
    )
    parser.add_argument(
        "--output",
        default="data/Import_Data_yearly_zones.csv",
        help="Output CSV file with zone-specific demand columns",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--daily-std",
        type=float,
        default=0.08,
        help="Standard deviation of daily variation (0.08 = ±8%)",
    )
    parser.add_argument(
        "--hourly-std",
        type=float,
        default=0.05,
        help="Standard deviation of hourly variation (0.05 = ±5%)",
    )

    args = parser.parse_args()

    # Define L3 zone fractions (30 nodes total: 1 plant + 4 junctions + 23 consumers + 2 misc)
    # North (23%): 5 zones
    # South (26%): 6 zones
    # East (25%): 6 zones
    # West (26%): 6 zones
    zone_fracs = {
        # North branch (23% of total)
        "zone_01": 0.06,
        "zone_02": 0.05,
        "zone_03": 0.04,
        "zone_04": 0.04,
        "zone_05": 0.04,
        # South branch (26% of total)
        "zone_06": 0.06,
        "zone_07": 0.05,
        "zone_08": 0.04,
        "zone_09": 0.04,
        "zone_10": 0.04,
        "zone_11": 0.03,
        # East branch (25% of total)
        "zone_12": 0.06,
        "zone_13": 0.05,
        "zone_14": 0.04,
        "zone_15": 0.04,
        "zone_16": 0.03,
        "zone_17": 0.03,
        # West branch (26% of total)
        "zone_18": 0.06,
        "zone_19": 0.05,
        "zone_20": 0.04,
        "zone_21": 0.04,
        "zone_22": 0.04,
        "zone_23": 0.03,
    }

    generate_zone_demands(
        input_csv=args.input,
        output_csv=args.output,
        zone_fractions=zone_fracs,
        seed=args.seed,
        daily_std=args.daily_std,
        hourly_std=args.hourly_std,
    )


if __name__ == "__main__":
    main()

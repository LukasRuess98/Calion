#!/usr/bin/env python3
"""
Quick feasibility test for Stadtbach thermal network.
Tests if the problem is solvable with relaxed constraints.
"""

import pandas as pd
import yaml
from pathlib import Path

def check_feasibility():
    """Run quick feasibility checks."""

    print("=" * 70)
    print("🔍 STADTBACH NETWORK FEASIBILITY CHECK")
    print("=" * 70)

    # 1. Check data file
    print("\n1️⃣ DATA FILE CHECK")
    data_path = Path('data/stadtbach_synthetic_2023_1week.csv')
    if not data_path.exists():
        print("❌ Data file not found!")
        return False

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    print(f"✅ Data loaded: {len(df)} hours")
    print(f"   Peak demand: {df['waermebedarf_MWth'].max():.1f} MW")
    print(f"   Avg demand: {df['waermebedarf_MWth'].mean():.1f} MW")
    print(f"   Min demand: {df['waermebedarf_MWth'].min():.1f} MW")

    # 2. Check network topology
    print("\n2️⃣ NETWORK TOPOLOGY CHECK")
    network_path = Path('configs/networks/stadtbach_network.yaml')
    with open(network_path) as f:
        network = yaml.safe_load(f)

    plants = network.get('production_plants', [])
    consumers = network.get('consumer_zones', [])
    pipes = network.get('pipes', [])

    print(f"✅ Network loaded:")
    print(f"   Production plants: {len(plants)}")
    print(f"   Consumer zones: {len(consumers)}")
    print(f"   Pipes: {len(pipes)}")

    # Check for complex nodes (multiple incoming pipes)
    from collections import defaultdict
    incoming_pipes = defaultdict(int)
    for pipe in pipes:
        to_node = pipe.get('to_node')
        if to_node:
            incoming_pipes[to_node] += 1

    complex_nodes = {node: count for node, count in incoming_pipes.items() if count > 1}
    if complex_nodes:
        print(f"\n⚠️  Complex nodes (multiple incoming pipes):")
        for node, count in complex_nodes.items():
            print(f"   - {node}: {count} incoming pipes")

    # 3. Check system capacities
    print("\n3️⃣ SYSTEM CAPACITY CHECK")
    system_path = Path('configs/systems/stadtbach.system.yaml')
    with open(system_path) as f:
        system = yaml.safe_load(f)

    # Sum heat pump capacities
    total_hp_capacity = 0
    if 'system' in system and 'heat_pumps' in system['system']:
        hps = system['system']['heat_pumps']
        if isinstance(hps, list):
            # Investment mode - capacities determined by solver
            hp_defaults = system['system'].get('heat_pump_defaults', {})
            max_th = hp_defaults.get('max_th_mw', 0)
            print(f"   Heat Pumps (investment mode): {len(hps)} units")
            print(f"   Max capacity per HP: {max_th} MW")
            total_hp_capacity = len(hps) * max_th
        else:
            # Fixed capacities
            for hp_id, hp_config in hps.items():
                capacity = hp_config.get('max_capacity_mw', 0)
                total_hp_capacity += capacity
                print(f"   {hp_id}: {capacity:.1f} MW")

    # Sum generator capacities
    total_gen_capacity = 0
    if 'system' in system and 'generators' in system['system']:
        generators = system['system']['generators']
        print(f"\n   Generators:")
        for gen_id, gen_config in generators.items():
            if gen_config.get('enabled', True):
                capacity = gen_config.get('cap_th_mw', 0)
                total_gen_capacity += capacity
                print(f"   {gen_id}: {capacity:.1f} MW")

    total_capacity = total_hp_capacity + total_gen_capacity
    print(f"\n   Total HP capacity:  {total_hp_capacity:.1f} MW")
    print(f"   Total Gen capacity: {total_gen_capacity:.1f} MW")
    print(f"   TOTAL capacity:     {total_capacity:.1f} MW")
    print(f"   Peak demand:        {df['waermebedarf_MWth'].max():.1f} MW")

    if total_capacity >= df['waermebedarf_MWth'].max():
        print("   ✅ SUFFICIENT CAPACITY")
        capacity_ok = True
    else:
        print(f"   ❌ INSUFFICIENT CAPACITY!")
        print(f"   Missing: {df['waermebedarf_MWth'].max() - total_capacity:.1f} MW")
        capacity_ok = False

    # 4. Recommendations
    print("\n" + "=" * 70)
    print("💡 RECOMMENDATIONS")
    print("=" * 70)

    timesteps_1week = 168
    timesteps_1day = 24

    print(f"\nProblem size:")
    print(f"  1 week:  {timesteps_1week} timesteps → ~50,000 variables")
    print(f"  1 day:   {timesteps_1day} timesteps  → ~7,000 variables (7x faster!)")

    if complex_nodes:
        print(f"\n⚠️  {len(complex_nodes)} nodes with multiple incoming pipes")
        print("   This requires bilinear constraints (temperature mixing)")
        print("   → Makes problem significantly harder")
        print("\n   Option 1: Start with 1-day test")
        print("   Option 2: Simplify network (remove complex nodes)")

    print("\n✅ NEXT STEPS:")
    if not capacity_ok:
        print("   ❌ FIX CAPACITY ISSUE FIRST!")
        print("   - Increase generator capacities in stadtbach.system.yaml")
        print("   - Or enable more heat pumps")
        return False

    print("   1. Test with 1-day scenario (stadtbach_1day_test.scenario.yaml)")
    print("   2. If successful, gradually increase timeframe")
    print("   3. Consider relaxed MIPGap (5-10%) for faster solutions")

    return True

if __name__ == "__main__":
    try:
        feasible = check_feasibility()
        if feasible:
            print("\n🎉 Problem appears FEASIBLE - proceed with testing")
        else:
            print("\n❌ Problem may be INFEASIBLE - check capacities")
    except Exception as e:
        print(f"\n❌ Error during check: {e}")
        import traceback
        traceback.print_exc()

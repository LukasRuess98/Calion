#!/usr/bin/env python3
"""
ENERGIS INFEASIBILITY DIAGNOSTICS - PHASE 3
Isolation Test: Build and run with NETWORK DISABLED
"""

import subprocess
import sys
from pathlib import Path

print("\n" + "=" * 70)
print("PHASE 3: ISOLATION TEST - Network Disabled")
print("=" * 70)

# Create temporary config with network disabled
config_no_network = """# ISOLATION TEST: Network physics disabled
# If this config runs successfully, the problem is in the network

site:
  input_xlsx: "data/Import_Data.csv"
  columns:
    datetime: "Datum"
    price: "strompreis_EUR_MWh"
    co2_grid: "grid_co2_kg_MWh"

scenario:
  run_mode: PF_ONLY

network:
  physics:
    heat_loss: false        # DISABLED for isolation
    pressure_drop: false    # DISABLED for isolation
    transport_delay: false
  supply_temp_nominal_c: 90
  return_temp_nominal_c: 55
  ground_temp_c: 10

  nodes:
    plant:
      type: producer
      assets: [boiler_1, hp_1]

    consumer_1:
      type: consumer
      demand_fraction: 1.0
      demand:
        column: "waermebedarf_MWth"

  pipes:
    plant_to_consumer:
      from: plant
      to: consumer_1
      length_m: 1000
      diameter_mm: 300

assets:
  boiler_1:
    type: thermal_generator
    fuel: gas
    capacity_mw: 150.0
    thermal_efficiency: 0.90

  hp_1:
    type: heat_pump
    capacity_mw: 80.0
    min_load: 0.2
    cop_default: 3.5
    wrg_sources: [WRG1, WRG2]

grid:
  gridcost_eur_mwh: 20.0

fuels:
  gas:
    price_eur_mwh: 45.0
    ef_kg_per_mwh_fuel: 200.0

costs:
  co2_price_eur_per_t: 100.0
  dump_cost_eur_per_mwh_th: 10.0

run:
  dt_h: 1.0
  solver: appsi_highs
"""

# Write isolation config
isolation_config = Path("configs/templates/level2_isolation_test.yaml")
isolation_config.write_text(config_no_network)

print(f"\n[1] Created isolation config: {isolation_config}")
print("    Network physics: DISABLED")
print("    Nodes: Same (plant + consumer_1)")
print("    Pipes: Same")
print("    Demand/Capacity: Same")

print("\n[2] Running isolation test...")
print("-" * 70)

result = subprocess.run(
    [sys.executable, "-m", "calion.run", str(isolation_config)],
    capture_output=True,
    text=True,
    timeout=60
)

print("STDOUT:")
print(result.stdout)

if result.stderr:
    print("\nSTDERR:")
    print(result.stderr)

print("\n[3] ANALYSIS")
print("-" * 70)

stdout_lower = result.stdout.lower()
stderr_lower = result.stderr.lower()
combined = stdout_lower + stderr_lower

if "optimal" in combined:
    print("✅ ISOLATION TEST PASSED - Model is feasible when network physics disabled!")
    print("\n   → DIAGNOSIS: Infeasibility IS in network constraints (heat loss, pressure drop)")
    print("   → Next: Check if simplified network model helps")
elif "infeasible" in combined:
    print("❌ ISOLATION TEST FAILED - Model still infeasible without network physics")
    print("\n   → DIAGNOSIS: Problem is NOT in network physics")
    print("   → Problem is likely in: assets, demand, or basic asset constraints")
    print("   → Next: Simplify asset configuration")
elif "degreeerror" in combined or "degree" in combined:
    print("⚠️  SOLVER ERROR - Non-polynomial constraint issue")
    print("\n   → DIAGNOSIS: Constraint formulation problem")
elif "timeout" in str(result.returncode):
    print("⏱️  TEST TIMEOUT - Model too complex or infinite loop")
else:
    print("❓ UNKNOWN RESULT - Check full output above")

print(f"\nReturn code: {result.returncode}")

print("\n" + "=" * 70)
print("PHASE 3 RESULT")
print("=" * 70)
if result.returncode == 0:
    print("✅ PASS: Isolation test succeeded")
else:
    print("❌ FAIL: Check output above for details")

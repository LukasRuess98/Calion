#!/usr/bin/env python3
"""Test script to demonstrate the detailed cost breakdown functionality."""

from energis.run import rolling_horizon as rh
import json

# Run with baseline configuration
config_paths = [
    "configs/base.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/test_1week.scenario.yaml",
    "configs/sites/default.site.yaml"
]

print("=" * 80)
print("DETAILLIERTE KOSTENAUFSCHLÜSSELUNG - TEST")
print("=" * 80)
print()

workflow = rh.run_workflow(config_paths)
result = rh.export_workflow_results(workflow)
costs = result.get('costs', {})

print("\n=== STROMKOSTEN (Electricity Costs) ===")
print(f"  Gesamt (Grid_energy_cost_EUR):         {costs.get('objective.Grid_energy_cost_EUR', 0):>15,.2f} EUR")
print(f"  Strompreis (Electricity_base_cost):    {costs.get('objective.Electricity_base_cost_EUR', 0):>15,.2f} EUR")
print(f"  Energy Fee (Electricity_energy_fee):   {costs.get('objective.Electricity_energy_fee_EUR', 0):>15,.2f} EUR")
print(f"  Netzentgelte (Electricity_grid_fee):   {costs.get('objective.Electricity_grid_fee_EUR', 0):>15,.2f} EUR")
print(f"  Leistungspreis (Demand_charge):        {costs.get('objective.Demand_charge_cost_EUR', 0):>15,.2f} EUR")

print("\n=== BRENNSTOFFKOSTEN (Fuel Costs) ===")
print(f"  Gesamt (Fuel_cost_EUR):                {costs.get('objective.Fuel_cost_EUR', 0):>15,.2f} EUR")
# List all fuel types dynamically
for key, value in costs.items():
    if key.startswith('objective.Fuel_cost_') and key.endswith('_EUR') and key != 'objective.Fuel_cost_EUR':
        fuel_type = key.replace('objective.Fuel_cost_', '').replace('_EUR', '')
        print(f"    {fuel_type:30s}:         {value:>15,.2f} EUR")

print("\n=== INVESTITIONSKOSTEN (CAPEX) ===")
print(f"  Gesamt (Capex_cost_EUR):               {costs.get('objective.Capex_cost_EUR', 0):>15,.2f} EUR")
print(f"  Wärmepumpen (Capex_heat_pumps):        {costs.get('objective.Capex_heat_pumps_EUR', 0):>15,.2f} EUR")
print(f"  Speicher (Capex_storage):              {costs.get('objective.Capex_storage_EUR', 0):>15,.2f} EUR")
print(f"  Activation Costs:                      {costs.get('objective.Activation_cost_EUR', 0):>15,.2f} EUR")
print(f"  Storage Installation:                  {costs.get('objective.Storage_installation_cost_EUR', 0):>15,.2f} EUR")

print("\n=== SONSTIGE KOSTEN (Other Costs) ===")
print(f"  CO2 Kosten:                            {costs.get('objective.CO2_cost_EUR', 0):>15,.2f} EUR")
print(f"  Abfall/Dump (Dump_cost):               {costs.get('objective.Dump_cost_EUR', 0):>15,.2f} EUR")
print(f"  Tie Breaker:                           {costs.get('objective.Tie_breaker_cost_EUR', 0):>15,.2f} EUR")

print("\n=== GESAMT ===")
print(f"  Zielfunktion (OBJ_value):              {costs.get('objective.OBJ_value_EUR', 0):>15,.2f} EUR")

print()
print("=" * 80)
print("✓ Detaillierte Kostenaufschlüsselung verfügbar!")
print()
print("Die Kosten werden nun in der results.json und costs.json mit folgenden")
print("detaillierten Aufschlüsselungen exportiert:")
print()
print("1. STROMKOSTEN:")
print("   - Electricity_base_cost_EUR: Reiner Strompreis")
print("   - Electricity_energy_fee_EUR: Energiegebühren")
print("   - Electricity_grid_fee_EUR: Netzentgelte")
print("   - Demand_charge_cost_EUR: Leistungspreis")
print()
print("2. BRENNSTOFFKOSTEN:")
print("   - Fuel_cost_EUR: Gesamt")
print("   - Fuel_cost_<typ>_EUR: Pro Brennstofftyp (gas, biomasse, etc.)")
print()
print("3. INVESTITIONSKOSTEN:")
print("   - Capex_cost_EUR: Gesamt")
print("   - Capex_heat_pumps_EUR: Wärmepumpen CAPEX")
print("   - Capex_storage_EUR: Speicher CAPEX")
print()
print("=" * 80)

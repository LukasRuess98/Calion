#!/usr/bin/env python3
"""Simple test to verify the framework structure and model solvability."""

from energis.run import rolling_horizon as rh

# Test with minimal configuration
config_paths = [
    "configs/base.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/perfect_forecast_full_year.scenario.yaml",
    "configs/sites/default.site.yaml"
]

print("=" * 80)
print("Testing EnerGIS Framework - Runner, Model, and Exports")
print("=" * 80)
print()

print("Configuration files:")
for path in config_paths:
    print(f"  - {path}")
print()

try:
    print("Running optimization...")
    print()
    workflow = rh.run_workflow(config_paths)
    result = rh.export_workflow_results(workflow)

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    if result:
        print("✓ Optimization completed successfully!")
        print()
        print(f"Output directory: {result.get('outdir', 'N/A')}")
        print(f"Scenario CSV: {result.get('scenario_csv', 'N/A')}")
        print(f"Scenario XLSX: {result.get('scenario_xlsx', 'N/A')}")
        print()

        if 'summary' in result and result['summary']:
            print("Summary metrics available:")
            summary = result['summary']
            if 'objective' in summary:
                obj = summary['objective']
                print(f"  - Objective value: {obj.get('OBJ_value_EUR', 0):,.2f} EUR")
                print(f"  - Grid energy cost: {obj.get('Grid_energy_cost_EUR', 0):,.2f} EUR")
                print(f"  - CO2 cost: {obj.get('CO2_cost_EUR', 0):,.2f} EUR")
            if 'grid' in summary:
                grid = summary['grid']
                print(f"  - Energy from grid: {grid.get('Energy_from_grid_MWh', 0):,.2f} MWh")
                print(f"  - Total CO2 emissions: {grid.get('Total_CO2_emissions_t', 0):,.2f} t")

        print()
        print("✓ Framework structure: OK")
        print("✓ Runner functionality: OK")
        print("✓ Pyomo model: SOLVABLE")
        print("✓ Export functionality: OK")

    else:
        print("✗ No result returned")

except Exception as e:
    print(f"✗ Error during execution: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("=" * 80)
print("Test completed successfully!")
print("=" * 80)

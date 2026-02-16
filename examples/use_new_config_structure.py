"""
Example: Using the new config structure (v2.0) with EnerGIS.

This example demonstrates how to:
1. Load the new config structure
2. Validate the configuration
3. Use it with existing system_builder.py
4. Access type-safe schema objects
"""

from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from energis.config.config_manager import ConfigManager
from energis.config.schemas import HeatPumpAsset, StorageAsset


def main():
    """Main example function."""

    # ===========================================================================
    # STEP 1: Load and validate configuration
    # ===========================================================================
    print("=" * 70)
    print("STEP 1: Load and Validate Configuration")
    print("=" * 70)

    # Path to scenario file
    scenario_path = "configs_new/scenarios/stadtbach_baseline_2023.yaml"

    # Create config manager
    manager = ConfigManager(scenario_path, validate=True)

    # Load configuration (automatically validates)
    config = manager.load()

    print("\n[OK] Configuration loaded and validated successfully!\n")

    # ===========================================================================
    # STEP 2: Print configuration summary
    # ===========================================================================
    print("=" * 70)
    print("STEP 2: Configuration Summary")
    print("=" * 70)

    manager.print_summary()

    # ===========================================================================
    # STEP 3: Access type-safe schema objects
    # ===========================================================================
    print("=" * 70)
    print("STEP 3: Type-Safe Schema Access")
    print("=" * 70)

    # Access scenario (type-safe!)
    scenario = manager.scenario
    print(f"\nScenario name: {scenario.name}")
    print(f"Optimization mode: {scenario.optimization.mode}")
    print(f"Planning horizon: {scenario.optimization.costs.planning_horizon_yr} years")

    # Access components (type-safe!)
    components = manager.components
    print(f"\nTotal components: {len(components)}")

    # Filter heat pumps
    heat_pumps = {
        comp_id: comp for comp_id, comp in components.items()
        if isinstance(comp, HeatPumpAsset)
    }
    print(f"Heat pumps: {len(heat_pumps)}")

    for hp_id, hp in heat_pumps.items():
        print(f"\n  {hp_id}:")
        print(f"    Technology: {hp.technology}")
        print(f"    Existing capacity: {hp.existing.thermal_capacity_mw:.1f} MW")
        if hp.expansion.enabled:
            print(f"    Expansion: {hp.expansion.min_additional_capacity_mw:.0f}-{hp.expansion.max_additional_capacity_mw:.0f} MW")
            print(f"    CAPEX: {hp.expansion.capex_eur_per_mw:,.0f} EUR/MW")
        if hp.waste_heat_source:
            print(f"    Waste heat source: {hp.waste_heat_source.get('temperature_column', 'N/A')}")

    # Filter storage
    storage_assets = {
        comp_id: comp for comp_id, comp in components.items()
        if isinstance(comp, StorageAsset)
    }
    print(f"\nStorage assets: {len(storage_assets)}")

    # Access grid connection
    grid = manager.grid
    print(f"\nGrid connection:")
    print(f"  Max import: {grid.max_import_mw:.1f} MW")
    print(f"  Max export: {grid.max_export_mw:.1f} MW")
    print(f"  Buy fees: {grid.buy_fees_total_eur_per_mwh:.2f} EUR/MWh")
    print(f"  Demand charge: {grid.annual_charge_eur_per_mw:,.0f} EUR/MW/year")

    # Access network
    network = manager.network
    if network:
        print(f"\nNetwork topology:")
        for net_id, net in network.networks.items():
            print(f"  {net_id}:")
            print(f"    Nodes: {len(net.nodes)}")
            print(f"    Pipes: {len(net.pipes)}")
            print(f"    Supply temp: {net.supply_temp_min_c:.0f}-{net.supply_temp_max_c:.0f}°C")

    # Access tech library
    tech_lib = manager.tech_library
    print(f"\nTechnology library:")
    print(f"  Heat pump technologies: {len(tech_lib['heat_pumps'])}")
    print(f"  Storage technologies: {len(tech_lib['storage'])}")
    print(f"  Generator technologies: {len(tech_lib['generators'])}")
    print(f"  Fuels: {len(tech_lib['fuels'])}")

    # ===========================================================================
    # STEP 4: Use with system_builder.py (backward compatible)
    # ===========================================================================
    print("\n" + "=" * 70)
    print("STEP 4: Backward Compatibility")
    print("=" * 70)

    # The config dict has a backward-compatible structure
    # that can be used with existing system_builder.py
    print("\nBackward-compatible config structure:")
    print(f"  - config['system']['heat_pumps']: {len(config['system'].get('heat_pumps', []))} heat pumps")
    print(f"  - config['system']['thermal_generators']: {len(config['system'].get('thermal_generators', []))} generators")
    print(f"  - config['system']['storage']: {len(config['system'].get('storage', []))} storage units")
    print(f"  - config['system']['p2h']: {len(config['system'].get('p2h', []))} P2H units")
    print(f"  - config['grid']['max_import_mw']: {config['grid']['max_import_mw']:.1f} MW")
    print(f"  - config['costs']['co2_price_eur_per_tonne']: {config['costs']['co2_price_eur_per_tonne']:.0f} EUR/t")

    print("\n[INFO] This config dict can be passed directly to system_builder.build_model()")
    print("[INFO] OR you can use the type-safe schema objects from config['_schemas']")

    # ===========================================================================
    # STEP 5: Demonstrate investment scenario
    # ===========================================================================
    print("\n" + "=" * 70)
    print("STEP 5: Investment Analysis")
    print("=" * 70)

    # Check which components can be invested in
    investable = {
        comp_id: comp for comp_id, comp in components.items()
        if comp.expansion.enabled
    }

    print(f"\nComponents with investment potential: {len(investable)}")

    total_max_investment = 0.0
    for comp_id, comp in investable.items():
        max_capex = comp.expansion.max_additional_capacity_mw * comp.expansion.capex_eur_per_mw
        total_max_investment += max_capex

        print(f"\n  {comp_id}:")
        print(f"    Max expansion: {comp.expansion.max_additional_capacity_mw:.0f} MW")
        print(f"    CAPEX: {comp.expansion.capex_eur_per_mw:,.0f} EUR/MW")
        print(f"    Max investment: {max_capex/1e6:.2f} M EUR")
        print(f"    Lifetime: {comp.expansion.lifetime_yr:.0f} years")

    print(f"\n  TOTAL max investment potential: {total_max_investment/1e6:.2f} M EUR")

    # Check subsidies
    subsidies = scenario.economics.subsidies
    print(f"\nSubsidies:")
    print(f"  Heat pump: {subsidies.heat_pump_subsidy_fraction*100:.0f}%")
    print(f"  Storage: {subsidies.storage_subsidy_fraction*100:.0f}%")
    print(f"  P2H: {subsidies.p2h_subsidy_fraction*100:.0f}%")

    # ===========================================================================
    # DONE
    # ===========================================================================
    print("\n" + "=" * 70)
    print("[OK] Example completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()

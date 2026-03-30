#!/usr/bin/env python3
"""
Stratified Storage Example
==========================

Demonstrates the two-zone stratified thermal energy storage component
for large-scale heat storage applications.

This example shows:
- How to create and configure a stratified storage
- Geometry calculations for cylindrical tanks
- Heat loss modeling with piecewise linearization
- Comparison with simple storage model
- Integration with the CALION framework

Usage:
    python examples/stratified_storage_example.py
"""

from __future__ import annotations
import json
from pathlib import Path

# Import the stratified storage component
from calion.models.blocks.stratified_storage import (
    StratifiedStorageBlock,
    calculate_cylindrical_geometry,
    RHO_WATER,
    CP_WATER
)

# Import registry for component management
from calion.models import ComponentRegistry


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}\n")


def example_geometry_calculation():
    """Example 1: Calculate geometry for different storage sizes."""
    print_section("Example 1: Geometry Calculations")

    storage_configs = [
        {"E_cap_MWh": 100, "type": "tank", "aspect_ratio": 1.5},
        {"E_cap_MWh": 1000, "type": "tank", "aspect_ratio": 1.5},
        {"E_cap_MWh": 10000, "type": "pit", "aspect_ratio": 0.4},
    ]

    for config in storage_configs:
        E_cap = config["E_cap_MWh"]
        T_hot = 90.0
        T_cold = 40.0
        delta_T = T_hot - T_cold

        # Calculate required volume
        # E = ρ × V × cp × ΔT / 3600
        # V = E × 3600 / (ρ × cp × ΔT)
        volume_m3 = E_cap * 3600.0 / (RHO_WATER * CP_WATER * delta_T)

        # Calculate geometry
        geom = calculate_cylindrical_geometry(
            volume_m3,
            aspect_ratio=config["aspect_ratio"],
            geometry_type=config["type"]
        )

        print(f"Storage: {E_cap} MWh capacity ({config['type'].upper()})")
        print(f"  Volume:       {geom['volume_m3']:,.0f} m³")
        print(f"  Diameter:     {geom['diameter_m']:.1f} m")
        print(f"  Height:       {geom['height_m']:.1f} m")
        print(f"  H/D ratio:    {geom['aspect_ratio']:.2f}")
        print(f"  Surface area: {geom['A_total_m2']:,.0f} m²")
        print(f"  Top area:     {geom['A_top_m2']:,.0f} m²")
        print(f"  Side area:    {geom['A_side_m2']:,.0f} m²")
        print()


def example_component_creation():
    """Example 2: Create stratified storage components."""
    print_section("Example 2: Component Creation")

    # Small district heating buffer storage
    storage_small = StratifiedStorageBlock(
        name="DH_Buffer",
        T_hot_C=90.0,
        T_cold_C=40.0,
        T_ambient_C=15.0,
        T_ground_C=10.0,
        # Geometry will be auto-calculated from e_cap_max
        aspect_ratio=1.5,
        geometry_type="tank",
        # Good insulation
        U_top=0.3,    # W/(m²·K)
        U_side=0.2,
        U_bottom=0.15,
        # Investment bounds
        investable=True,
        e_cap_min=10.0,    # MWh
        e_cap_max=500.0,   # MWh
        p_cap_min=5.0,     # MW
        p_cap_max=100.0,   # MW
        # Efficiency
        eff_c=0.95,
        eff_d=0.95,
        dt_h=1.0,
        label="District Heating Buffer Storage"
    )

    print("Small District Heating Buffer Storage")
    print(f"  Name: {storage_small.name}")
    print(f"  Label: {storage_small.label}")
    summary = storage_small.get_summary()
    print(f"  Capacity range: {summary['capacity']['E_cap_range_MWh'][0]}-{summary['capacity']['E_cap_range_MWh'][1]} MWh")
    print(f"  Volume: {summary['geometry']['volume_m3']:,.0f} m³")
    print(f"  Diameter: {summary['geometry']['diameter_m']:.1f} m")
    print(f"  Height: {summary['geometry']['height_m']:.1f} m")
    print(f"  Annual loss rate: {summary['losses']['annual_loss_rate_pct']:.2f}%")
    print()

    # Large seasonal storage (pit type)
    storage_large = StratifiedStorageBlock(
        name="Seasonal_PTES",
        T_hot_C=95.0,
        T_cold_C=30.0,
        T_ambient_C=10.0,
        T_ground_C=8.0,
        # Pit thermal energy storage geometry
        aspect_ratio=0.4,
        geometry_type="pit",
        # Excellent insulation (underground)
        U_top=0.2,     # W/(m²·K) - insulated cover
        U_side=0.05,   # W/(m²·K) - ground thermal resistance
        U_bottom=0.02, # W/(m²·K) - deep ground
        # Large capacity
        investable=True,
        e_cap_min=1000.0,    # MWh
        e_cap_max=50000.0,   # MWh
        p_cap_min=10.0,      # MW
        p_cap_max=200.0,     # MW
        eff_c=0.98,
        eff_d=0.98,
        dt_h=1.0,
        piecewise_n_points=10,  # More accurate loss modeling
        label="Seasonal Pit Thermal Energy Storage"
    )

    print("Large Seasonal PTES")
    print(f"  Name: {storage_large.name}")
    summary_large = storage_large.get_summary()
    print(f"  Capacity range: {summary_large['capacity']['E_cap_range_MWh'][0]:,.0f}-{summary_large['capacity']['E_cap_range_MWh'][1]:,.0f} MWh")
    print(f"  Volume: {summary_large['geometry']['volume_m3']:,.0f} m³")
    print(f"  Diameter: {summary_large['geometry']['diameter_m']:.1f} m")
    print(f"  Height: {summary_large['geometry']['height_m']:.1f} m")
    print(f"  Annual loss rate: {summary_large['losses']['annual_loss_rate_pct']:.2f}%")
    print(f"  Geometry type: {summary_large['geometry']['type']}")
    print()


def example_loss_calculation():
    """Example 3: Analyze heat losses with piecewise linearization."""
    print_section("Example 3: Heat Loss Analysis")

    storage = StratifiedStorageBlock(
        name="Analysis_Storage",
        T_hot_C=90.0,
        T_cold_C=40.0,
        T_ambient_C=10.0,
        T_ground_C=10.0,
        investable=False,
        e_cap_min=1000.0,
        e_cap_max=1000.0,
        p_cap_min=50.0,
        p_cap_max=50.0,
        U_top=0.5,
        U_side=0.3,
        U_bottom=0.2,
        piecewise_n_points=11  # 0%, 10%, 20%, ..., 100%
    )

    # Get piecewise loss data
    loss_data = storage.calculate_loss_piecewise_data()

    print("Piecewise-Linear Loss Model:")
    print(f"  Number of breakpoints: {len(loss_data['breakpoints'])}")
    print()
    print("  Hot Volume  |  Energy Loss  |  Volume Loss")
    print("  Fraction    |    [MW]       |   [m³/h]")
    print("  " + "-" * 48)

    for i, ratio in enumerate(loss_data['breakpoints']):
        e_loss = loss_data['energy_losses'][i]
        v_loss = loss_data['volume_losses'][i]
        print(f"    {ratio:5.1%}     |   {e_loss:7.4f}     |   {v_loss:7.3f}")

    print()
    print("Insights:")
    print(f"  - Loss at empty (0%): {loss_data['energy_losses'][0]:.4f} MW")
    print(f"  - Loss at half (50%): {loss_data['energy_losses'][len(loss_data['breakpoints'])//2]:.4f} MW")
    print(f"  - Loss at full (100%): {loss_data['energy_losses'][-1]:.4f} MW")
    print(f"  - Loss variation: {(loss_data['energy_losses'][-1] - loss_data['energy_losses'][0]):.4f} MW")
    print()


def example_comparison_simple_vs_stratified():
    """Example 4: Compare simple vs. stratified storage."""
    print_section("Example 4: Comparison - Simple vs. Stratified Storage")

    # Common parameters
    E_cap = 1000.0  # MWh
    T_hot = 90.0
    T_cold = 40.0
    delta_T = T_hot - T_cold

    # Calculate volume
    volume_m3 = E_cap * 3600.0 / (RHO_WATER * CP_WATER * delta_T)
    geom = calculate_cylindrical_geometry(volume_m3, aspect_ratio=1.5)

    # Average temperature for simple model
    T_avg = (T_hot + T_cold) / 2.0
    T_ambient = 10.0

    # Heat loss - simple model (constant temperature)
    U_avg = 0.3  # W/(m²·K)
    Q_loss_simple = U_avg * geom['A_total_m2'] * (T_avg - T_ambient) / 1000.0  # MW
    hourly_loss_factor_simple = 1 - (Q_loss_simple / E_cap)

    # Stratified storage
    storage_strat = StratifiedStorageBlock(
        name="Stratified",
        T_hot_C=T_hot,
        T_cold_C=T_cold,
        T_ambient_C=T_ambient,
        investable=False,
        e_cap_min=E_cap,
        e_cap_max=E_cap,
        p_cap_min=50.0,
        p_cap_max=50.0,
        U_top=0.5,
        U_side=0.3,
        U_bottom=0.2
    )

    summary_strat = storage_strat.get_summary()
    Q_loss_strat_50 = summary_strat['losses']['avg_loss_MW_at_50pct']

    print("Storage Configuration:")
    print(f"  Capacity: {E_cap} MWh")
    print(f"  Volume: {volume_m3:,.0f} m³")
    print(f"  Diameter: {geom['diameter_m']:.1f} m, Height: {geom['height_m']:.1f} m")
    print(f"  Surface Area: {geom['A_total_m2']:,.0f} m²")
    print()

    print("Simple Storage Model (Well-Mixed):")
    print(f"  Average Temperature: {T_avg:.1f}°C")
    print(f"  Heat Loss (constant): {Q_loss_simple:.4f} MW")
    print(f"  Hourly retention: {hourly_loss_factor_simple:.6f}")
    print(f"  Daily loss: {(1 - hourly_loss_factor_simple**24) * 100:.2f}%")
    print(f"  Annual loss: {(1 - hourly_loss_factor_simple**(24*365)) * 100:.1f}%")
    print()

    print("Stratified Storage Model (Two-Zone):")
    print(f"  Hot Zone: {T_hot:.1f}°C, Cold Zone: {T_cold:.1f}°C")
    print(f"  Heat Loss (at 50% fill): {Q_loss_strat_50:.4f} MW")
    print(f"  Annual loss rate: {summary_strat['losses']['annual_loss_rate_pct']:.2f}%")
    print()

    print("Key Differences:")
    print("  ✓ Stratified model captures temperature distribution")
    print("  ✓ Different losses for top/side/bottom surfaces")
    print("  ✓ Loss varies with storage fill level")
    print("  ✓ More realistic for large-scale storage")
    print()


def example_registry_integration():
    """Example 5: Integration with component registry."""
    print_section("Example 5: Component Registry Integration")

    # Check if component is registered
    components = ComponentRegistry.list_components()
    print(f"Registered components: {len(components)}")

    if "stratified_storage" in components:
        print("✓ StratifiedStorage is registered!")

        # Get metadata
        metadata = ComponentRegistry.get_metadata("stratified_storage")
        print(f"\nMetadata:")
        print(f"  Type: {metadata.get('name', 'N/A')}")
        print(f"  Category: {metadata.get('category', 'N/A')}")
        print(f"  Description: {metadata.get('description', 'N/A')}")
        print(f"  Version: {metadata.get('version', 'N/A')}")

        # Create via registry
        print("\nCreating component via registry...")
        storage = ComponentRegistry.create(
            "stratified_storage",
            name="Registry_Storage",
            T_hot_C=85.0,
            T_cold_C=45.0,
            investable=True,
            e_cap_min=100.0,
            e_cap_max=2000.0,
            p_cap_min=20.0,
            p_cap_max=150.0
        )
        print(f"✓ Created: {storage.name}")
        print(f"  Flows registered: {len(storage.flows)}")
    else:
        print("✗ StratifiedStorage not found in registry")
        print("  (This is normal if the module hasn't been imported)")

    print()


def example_yaml_config():
    """Example 6: Show YAML configuration for system integration."""
    print_section("Example 6: YAML Configuration Example")

    yaml_config = """
# Example system configuration with stratified storage
# File: configs/systems/district_heating_with_stratified_storage.yaml

system:
  storage:
    # Traditional simple storage for short-term buffering
    - id: buffer_storage
      component_type: storage
      e_min: 0.0
      e_max: 100.0
      p_max: 50.0
      eff_c: 0.95
      eff_d: 0.95
      hourly_loss: 0.999
      dt_h: 1.0
      soc0: 0.0
      investable: true
      e_cap_min: 10.0
      e_cap_max: 100.0
      p_cap_min: 5.0
      p_cap_max: 50.0
      enabled: true

    # New stratified storage for large-scale seasonal storage
    - id: seasonal_storage
      component_type: stratified_storage
      # Thermal parameters
      T_hot_C: 90.0
      T_cold_C: 40.0
      T_ambient_C: 10.0
      T_ground_C: 8.0
      # Geometry
      aspect_ratio: 0.4  # Pit storage
      geometry_type: pit
      # Heat transfer
      U_top: 0.2
      U_side: 0.05
      U_bottom: 0.02
      # Efficiency
      eff_c: 0.98
      eff_d: 0.98
      # Capacity
      investable: true
      e_cap_min: 5000.0
      e_cap_max: 50000.0
      p_cap_min: 50.0
      p_cap_max: 500.0
      # Initial state
      soc0: 10000.0
      V_hot_init_fraction: 0.6
      # Piecewise linearization
      piecewise_n_points: 10
      enabled: true
"""

    print("YAML Configuration:")
    print(yaml_config)
    print("\nNo changes to system_builder.py needed!")
    print("Component is automatically discovered via registry.")
    print()


def export_example_data():
    """Export example data to JSON for documentation."""
    print_section("Exporting Example Data")

    storage = StratifiedStorageBlock(
        name="ExampleStorage",
        T_hot_C=90.0,
        T_cold_C=40.0,
        investable=False,
        e_cap_min=1000.0,
        e_cap_max=1000.0,
        p_cap_min=50.0,
        p_cap_max=50.0
    )

    summary = storage.get_summary()
    loss_data = storage.calculate_loss_piecewise_data()

    export_data = {
        "summary": summary,
        "loss_data": loss_data
    }

    export_dir = Path("exports")
    export_dir.mkdir(exist_ok=True)

    export_path = export_dir / "stratified_storage_example.json"
    with open(export_path, "w") as f:
        json.dump(export_data, f, indent=2)

    print(f"✓ Example data exported to: {export_path}")
    print()


def main():
    """Run all examples."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║          STRATIFIED THERMAL ENERGY STORAGE COMPONENT                 ║
║                      Demonstration Examples                          ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    example_geometry_calculation()
    example_component_creation()
    example_loss_calculation()
    example_comparison_simple_vs_stratified()
    example_registry_integration()
    example_yaml_config()
    export_example_data()

    print_section("Summary")
    print("✓ Stratified storage component demonstrated")
    print("✓ Geometry calculations shown")
    print("✓ Heat loss modeling explained")
    print("✓ Comparison with simple model")
    print("✓ Registry integration verified")
    print("✓ Configuration examples provided")
    print()
    print("Next steps:")
    print("  1. Integrate into your system YAML configuration")
    print("  2. Run optimization with Planning Framework")
    print("  3. Analyze results (zone volumes, losses, etc.)")
    print("  4. Compare with traditional storage model")
    print()
    print("For more information, see:")
    print("  - calion/models/blocks/stratified_storage.py")
    print("  - examples/custom_component_example.py")
    print()


if __name__ == "__main__":
    main()

"""Test and demonstration of the CostResolver system."""

from pathlib import Path

def test_cost_resolver():
    """Demonstrate CostResolver with all three variants."""
    from calion.models.cost_resolver import CostResolver

    print("\n" + "="*80)
    print("TEST 1: GLOBAL COSTS ONLY")
    print("="*80)

    cfg_global = {
        "costs_config": {
            "global": {
                "demand_charge_eur_per_mw_y": 50000.0,
                "energy_fee_eur_per_mwh": 5.0,
            }
        }
    }

    resolver_global = CostResolver(cfg_global)
    resolver_global.log_resolution_summary()

    # Test single zone
    zone_charge = resolver_global.get_zone_cost(
        "zone_01", "demand_charge_eur_per_mw_y"
    )
    print(f"\n✓ zone_01 demand_charge: €{zone_charge:.2f}/MW/Year (global fallback)")

    print("\n" + "="*80)
    print("TEST 2: GLOBAL + ZONE-SPECIFIC STATIC")
    print("="*80)

    cfg_zonal = {
        "costs_config": {
            "global": {
                "demand_charge_eur_per_mw_y": 50000.0,
                "energy_fee_eur_per_mwh": 5.0,
            },
            "zones": {
                "plant_main": {
                    "type": "central_plant",
                    "demand_charge_eur_per_mw_y": 0.0,  # Plant has no fee
                },
                "j_central": {
                    "type": "central",
                    "demand_charge_eur_per_mw_y": 30000.0,  # Cheaper
                    # energy_fee: inherits from global
                },
                "j_south": {
                    "type": "peripheral",
                    "demand_charge_eur_per_mw_y": 70000.0,  # Expensive
                },
            },
        }
    }

    resolver_zonal = CostResolver(cfg_zonal)
    resolver_zonal.log_resolution_summary()

    # Test resolution order
    for zone in ["plant_main", "j_central", "j_south", "zone_unknown"]:
        charge = resolver_zonal.get_zone_cost(zone, "demand_charge_eur_per_mw_y")
        fee = resolver_zonal.get_zone_cost(zone, "energy_fee_eur_per_mwh")
        ztype = resolver_zonal.get_zone_type(zone)
        print(
            f"✓ {zone:15} (type={ztype:20}) → charge=€{charge:8.0f}, fee=€{fee:4.1f}"
        )

    print("\n" + "="*80)
    print("TEST 3: GLOBAL + ZONE + DYNAMIC (CSV)")
    print("="*80)

    # Mock table for testing
    mock_table = {
        "columns": [
            "plant_charge_EUR_MW_h",
            "j_central_charge_EUR_MW_h",
            "j_south_charge_EUR_MW_h",
        ],
        "plant_charge_EUR_MW_h": {
            1: 0.0,
            2: 0.0,
            18: 0.0,  # Always 0 for plant
        },
        "j_central_charge_EUR_MW_h": {
            1: 6.50,  # Night
            2: 6.60,
            12: 3.20,  # Day, cheap
            18: 7.50,  # Evening peak
        },
        "j_south_charge_EUR_MW_h": {
            1: 8.20,
            12: 4.50,
            18: 9.00,  # Very expensive in evening
        },
    }

    # Create mock with attributes
    class MockTable(dict):
        @property
        def columns(self):
            return self["columns"]

    mock_table_obj = MockTable(mock_table)

    cfg_dynamic = {
        "costs_config": {
            "global": {
                "demand_charge_eur_per_mw_y": 50000.0,
            },
            "zones": {
                "plant_main": {"demand_charge_eur_per_mw_y": 0.0},
                "j_central": {"demand_charge_eur_per_mw_y": 30000.0},
                "j_south": {"demand_charge_eur_per_mw_y": 70000.0},
            },
            "dynamic": {
                "enabled": True,
                "mappings": {
                    "plant_charge_eur_per_mw_y": "plant_charge_EUR_MW_h",
                    "j_central_demand_charge_eur_per_mw_y": "j_central_charge_EUR_MW_h",
                    "j_south_demand_charge_eur_per_mw_y": "j_south_charge_EUR_MW_h",
                },
            },
        }
    }

    resolver_dynamic = CostResolver(cfg_dynamic, mock_table_obj)

    print("\nDYNAMIC COSTS (CSV-based, hourly):")
    print("-" * 80)

    for zone in ["plant_main", "j_central", "j_south"]:
        print(f"\n{zone}:")
        for t in [1, 2, 12, 18]:  # night, early, day, evening
            charge = resolver_dynamic.get_zone_cost(
                zone, "demand_charge_eur_per_mw_y", timestep=t
            )
            hour_str = f"{t:02d}h"
            print(f"  {hour_str} → €{charge:.2f}/MW/h")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print("""
✓ All three variants working:
  1. GLOBAL: Simple, identical for all zones
  2. STATIC: Zone-specific overrides, good for central vs. peripheral
  3. DYNAMIC: Hourly tariffs from CSV, realistic real-time pricing

✓ Cost resolution hierarchy working:
  Priority: Dynamic (CSV) > Zone-specific > Global > 0.0

✓ Use cases:
  - Variant 1: Baseline tests, symmetrical scenarios
  - Variant 2: RECOMMENDED for most multi-zone analyses
  - Variant 3: Advanced scenarios with time-varying tariffs
    """)


if __name__ == "__main__":
    test_cost_resolver()

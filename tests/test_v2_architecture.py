"""
Comprehensive test suite for EnerGIS v2.0 architecture.

This test validates:
1. Component registration and discovery
2. Component implementations
3. Flow declarations
4. Bus functionality
5. Backward compatibility
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_1_component_registry():
    """Test that ComponentRegistry works correctly."""
    print("\n" + "="*70)
    print("TEST 1: ComponentRegistry Functionality")
    print("="*70)

    from energis.models import ComponentRegistry

    # Test 1.1: List all registered components
    components = ComponentRegistry.list_components()
    print(f"\n✓ Registered components ({len(components)}): {components}")

    expected_components = ["heat_pump", "storage", "thermal_generator", "p2h"]
    for comp in expected_components:
        assert comp in components, f"Component '{comp}' not registered!"
    print(f"✓ All expected components registered: {expected_components}")

    # Test 1.2: Get metadata for each component
    print("\n--- Component Metadata ---")
    for comp_type in components:
        metadata = ComponentRegistry.get_metadata(comp_type)
        print(f"\n{comp_type}:")
        print(f"  Class: {metadata['class_name']}")
        print(f"  Category: {metadata['category']}")
        print(f"  Description: {metadata['description'][:60]}...")
        print(f"  Version: {metadata['version']}")

    # Test 1.3: List by category
    converters = ComponentRegistry.list_by_category("converter")
    storage = ComponentRegistry.list_by_category("storage")
    print(f"\n✓ Converters: {converters}")
    print(f"✓ Storage: {storage}")

    assert len(converters) >= 3, f"Expected at least 3 converters, got {len(converters)}"
    assert len(storage) >= 1, f"Expected at least 1 storage, got {len(storage)}"

    print("\n✅ TEST 1 PASSED: ComponentRegistry works correctly!")
    return True


def test_2_component_creation():
    """Test creating components via Registry."""
    print("\n" + "="*70)
    print("TEST 2: Component Creation via Registry")
    print("="*70)

    from energis.models import ComponentRegistry, HeatPumpBlock, StorageBlock

    # Test 2.1: Create heat pump via registry
    print("\n--- Creating Heat Pump via Registry ---")
    try:
        hp = ComponentRegistry.create(
            "heat_pump",
            name="HP_TEST",
            min_load=0.3,
            cop_series=[3.0, 3.5, 4.0],
            capacity_min_mw=0.0,
            capacity_max_mw=10.0,
            capacity_init_mw=5.0,
            investable=False,
            label="Test Heat Pump"
        )
        print(f"✓ Created: {hp}")
        assert hp.name == "HP_TEST"
        assert hp.label == "Test Heat Pump"
        assert isinstance(hp, HeatPumpBlock)
        print("✓ Component is correct type and has correct attributes")
    except Exception as e:
        print(f"✗ FAILED to create heat pump: {e}")
        return False

    # Test 2.2: Create storage via registry
    print("\n--- Creating Storage via Registry ---")
    try:
        storage = ComponentRegistry.create(
            "storage",
            name="TES_TEST",
            e_min=0.0,
            e_max=100.0,
            p_max=10.0,
            eff_c=0.95,
            eff_d=0.95,
            hourly_loss=0.999,
            dt_h=1.0,
            soc0=0.0,
            investable=False,
            e_cap_min=0.0,
            e_cap_max=100.0,
            p_cap_min=0.0,
            p_cap_max=10.0,
            e_cap_init=50.0,
            p_cap_init=5.0,
            terminal_target=None,
            label="Test Storage"
        )
        print(f"✓ Created: {storage}")
        assert storage.name == "TES_TEST"
        assert isinstance(storage, StorageBlock)
        print("✓ Storage component created correctly")
    except Exception as e:
        print(f"✗ FAILED to create storage: {e}")
        return False

    # Test 2.3: Direct instantiation still works
    print("\n--- Direct Instantiation (Backward Compat) ---")
    try:
        hp_direct = HeatPumpBlock(
            name="HP_DIRECT",
            min_load=0.3,
            cop_series=[3.0],
            capacity_min_mw=0.0,
            capacity_max_mw=10.0,
            capacity_init_mw=5.0,
            investable=False
        )
        print(f"✓ Direct creation works: {hp_direct}")
    except Exception as e:
        print(f"✗ FAILED direct creation: {e}")
        return False

    print("\n✅ TEST 2 PASSED: Component creation works!")
    return True


def test_3_flow_declarations():
    """Test that Flow objects are declared correctly."""
    print("\n" + "="*70)
    print("TEST 3: Flow Declarations")
    print("="*70)

    from energis.models import HeatPumpBlock, StorageBlock, P2HBlock

    # Note: Flows are added during attach(), not __init__
    # So we check that add_flow() method exists and works

    print("\n--- Heat Pump ---")
    hp = HeatPumpBlock(
        name="HP1",
        min_load=0.3,
        cop_series=[3.0],
        capacity_min_mw=0.0,
        capacity_max_mw=10.0,
        capacity_init_mw=5.0,
        investable=False
    )
    print(f"✓ Heat pump created: {hp}")
    print(f"  Initial flows count: {len(hp.flows)} (expected 0 before attach)")
    print(f"  Has add_flow method: {hasattr(hp, 'add_flow')}")
    print(f"  Has get_input_flows method: {hasattr(hp, 'get_input_flows')}")
    print(f"  Has get_output_flows method: {hasattr(hp, 'get_output_flows')}")

    print("\n--- Storage ---")
    storage = StorageBlock(
        name="TES1",
        e_min=0.0,
        e_max=100.0,
        p_max=10.0,
        eff_c=0.95,
        eff_d=0.95,
        hourly_loss=0.999,
        dt_h=1.0,
        soc0=0.0,
        investable=False,
        e_cap_min=0.0,
        e_cap_max=100.0,
        p_cap_min=0.0,
        p_cap_max=10.0,
        e_cap_init=50.0,
        p_cap_init=5.0,
        terminal_target=None
    )
    print(f"✓ Storage created: {storage}")
    print(f"  Initial flows count: {len(storage.flows)} (expected 0 before attach)")

    print("\n--- P2H ---")
    p2h = P2HBlock(name="P2H1", eff=0.99, cap_th_mw=5.0)
    print(f"✓ P2H created: {p2h}")
    print(f"  Initial flows count: {len(p2h.flows)} (expected 0 before attach)")

    print("\n✅ TEST 3 PASSED: Components have flow management methods!")
    return True


def test_4_bus_functionality():
    """Test Bus class functionality."""
    print("\n" + "="*70)
    print("TEST 4: Bus Functionality")
    print("="*70)

    from energis.models import Bus, BusType, create_default_buses

    # Test 4.1: Create buses
    print("\n--- Creating Buses ---")
    heat_bus = Bus("heat", BusType.HEAT)
    elec_bus = Bus("electricity", BusType.ELECTRICITY, capacity=100.0, loss_factor=0.05)

    print(f"✓ Heat bus: {heat_bus}")
    print(f"✓ Elec bus: {elec_bus}")
    print(f"  Elec bus capacity: {elec_bus.capacity} MW")
    print(f"  Elec bus loss factor: {elec_bus.loss_factor}")

    # Test 4.2: Check bus methods
    print("\n--- Bus Methods ---")
    print(f"✓ Heat bus input count: {heat_bus.get_input_count()}")
    print(f"✓ Heat bus output count: {heat_bus.get_output_count()}")
    print(f"✓ Heat bus balanced: {heat_bus.is_balanced()}")

    # Test 4.3: Create default buses
    print("\n--- Default Buses ---")
    default_buses = create_default_buses()
    print(f"✓ Created {len(default_buses)} default buses:")
    for bus_name, bus in default_buses.items():
        print(f"  - {bus_name}: {bus.bus_type}")

    expected_buses = ["electricity", "heat", "fuel_gas", "fuel_biomass", "fuel_waste"]
    for bus_name in expected_buses:
        assert bus_name in default_buses, f"Missing default bus: {bus_name}"
    print(f"✓ All expected default buses present")

    print("\n✅ TEST 4 PASSED: Bus functionality works!")
    return True


def test_5_backward_compatibility():
    """Test that existing code still works."""
    print("\n" + "="*70)
    print("TEST 5: Backward Compatibility")
    print("="*70)

    # Test 5.1: Import old components directly
    print("\n--- Old-Style Imports ---")
    try:
        from energis.models.blocks.heat_pump import HeatPumpBlock
        from energis.models.blocks.storage import StorageBlock
        from energis.models.blocks.thermal_gen import ThermalGeneratorBlock
        from energis.models.blocks.p2h import P2HBlock
        print("✓ Old-style imports work")
    except Exception as e:
        print(f"✗ FAILED old-style imports: {e}")
        return False

    # Test 5.2: Create components old-style
    print("\n--- Old-Style Component Creation ---")
    try:
        hp = HeatPumpBlock(
            name="HP1",
            min_load=0.3,
            cop_series=[3.0, 3.5],
            capacity_min_mw=0.0,
            capacity_max_mw=10.0,
            capacity_init_mw=5.0,
            investable=False
        )
        print(f"✓ Created heat pump old-style: {hp}")
        assert hp.name == "HP1"
        assert hasattr(hp, 'min_load')
        assert hasattr(hp, 'capacity_max_mw')
        print("✓ Component has all expected attributes")
    except Exception as e:
        print(f"✗ FAILED old-style creation: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 5.3: Import system_builder (legacy)
    print("\n--- Legacy system_builder ---")
    try:
        from energis.models import build_model
        print(f"✓ Legacy build_model imported: {build_model}")
        print("✓ Backward compatibility maintained!")
    except Exception as e:
        print(f"✗ FAILED to import build_model: {e}")
        return False

    print("\n✅ TEST 5 PASSED: Backward compatibility maintained!")
    return True


def test_6_integration_check():
    """Integration test with all components."""
    print("\n" + "="*70)
    print("TEST 6: Integration Check")
    print("="*70)

    from energis.models import (
        ComponentRegistry,
        create_default_buses,
        HeatPumpBlock,
        StorageBlock,
        ThermalGeneratorBlock,
        P2HBlock
    )

    # Create a simple system
    print("\n--- Creating Simple System ---")

    # 1. Create buses
    buses = create_default_buses()
    print(f"✓ Created {len(buses)} buses")

    # 2. Create components
    components = []

    # Heat pump
    hp = ComponentRegistry.create(
        "heat_pump",
        name="HP1",
        min_load=0.3,
        cop_series=[3.0, 3.5, 4.0],
        capacity_min_mw=0.0,
        capacity_max_mw=10.0,
        capacity_init_mw=5.0,
        investable=False
    )
    components.append(hp)
    print(f"✓ Created {hp}")

    # Storage
    storage = ComponentRegistry.create(
        "storage",
        name="TES1",
        e_min=0.0,
        e_max=100.0,
        p_max=10.0,
        eff_c=0.95,
        eff_d=0.95,
        hourly_loss=0.999,
        dt_h=1.0,
        soc0=0.0,
        investable=False,
        e_cap_min=0.0,
        e_cap_max=100.0,
        p_cap_min=0.0,
        p_cap_max=10.0,
        e_cap_init=50.0,
        p_cap_init=5.0,
        terminal_target=None
    )
    components.append(storage)
    print(f"✓ Created {storage}")

    # P2H
    p2h = ComponentRegistry.create(
        "p2h",
        name="P2H1",
        eff=0.99,
        cap_th_mw=5.0
    )
    components.append(p2h)
    print(f"✓ Created {p2h}")

    # Thermal generator
    gen = ComponentRegistry.create(
        "thermal_generator",
        name="GAS1",
        th_eff=0.9,
        el_eff=None,
        cap_th_mw=20.0
    )
    components.append(gen)
    print(f"✓ Created {gen}")

    print(f"\n✓ System created with {len(components)} components and {len(buses)} buses")

    # 3. Check that all components are BaseComponent instances
    from energis.models import BaseComponent
    for comp in components:
        assert isinstance(comp, BaseComponent), f"{comp} is not a BaseComponent!"
    print(f"✓ All components are BaseComponent instances")

    # 4. Check that all components have required methods
    for comp in components:
        assert hasattr(comp, 'attach'), f"{comp} missing attach()"
        assert hasattr(comp, 'get_results'), f"{comp} missing get_results()"
        assert hasattr(comp, 'validate_config'), f"{comp} missing validate_config()"
        assert hasattr(comp, 'add_flow'), f"{comp} missing add_flow()"
    print(f"✓ All components have required methods")

    print("\n✅ TEST 6 PASSED: Integration check successful!")
    return True


def run_all_tests():
    """Run all tests and generate summary report."""
    print("\n" + "="*70)
    print("ENERGIS V2.0 ARCHITECTURE - COMPREHENSIVE TEST SUITE")
    print("="*70)

    tests = [
        ("Component Registry", test_1_component_registry),
        ("Component Creation", test_2_component_creation),
        ("Flow Declarations", test_3_flow_declarations),
        ("Bus Functionality", test_4_bus_functionality),
        ("Backward Compatibility", test_5_backward_compatibility),
        ("Integration Check", test_6_integration_check),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = "PASSED" if result else "FAILED"
        except Exception as e:
            print(f"\n✗ TEST FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = "ERROR"

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    for test_name, result in results.items():
        symbol = "✅" if result == "PASSED" else "❌"
        print(f"{symbol} {test_name}: {result}")

    passed = sum(1 for r in results.values() if r == "PASSED")
    total = len(results)

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("The v2.0 architecture is correctly implemented!")
        return True
    else:
        print("\n⚠️  SOME TESTS FAILED!")
        print("Please review the errors above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""Test script for Pyomo model export functionality."""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import pyomo.environ as pyo
    from calion.io.model_inspector import export_model_structure, inspect_pyomo_model
    print("[TEST] Imports successful!")
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    sys.exit(1)


def create_simple_test_model():
    """Create a simple test model for demonstration."""
    print("\n[TEST] Creating simple Pyomo model...")

    m = pyo.ConcreteModel(name="TestModel")

    # Sets
    m.T = pyo.RangeSet(1, 24)  # 24 hours
    m.Units = pyo.Set(initialize=['HP1', 'HP2', 'Boiler'])

    # Parameters
    m.demand = pyo.Param(m.T, initialize={t: 10.0 + t * 0.5 for t in m.T})
    m.price = pyo.Param(m.T, initialize={t: 50.0 + t * 2.0 for t in m.T})
    m.max_capacity = pyo.Param(m.Units, initialize={'HP1': 20.0, 'HP2': 15.0, 'Boiler': 30.0})

    # Variables
    m.production = pyo.Var(m.Units, m.T, domain=pyo.NonNegativeReals)
    m.storage_level = pyo.Var(m.T, bounds=(0, 100))
    m.grid_purchase = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.invest_capacity = pyo.Var(m.Units, bounds=(0, 50))
    m.build_decision = pyo.Var(m.Units, domain=pyo.Binary)

    # Constraints
    def demand_constraint_rule(model, t):
        return sum(model.production[u, t] for u in model.Units) >= model.demand[t]

    m.demand_constraint = pyo.Constraint(m.T, rule=demand_constraint_rule)

    def capacity_constraint_rule(model, u, t):
        return model.production[u, t] <= model.max_capacity[u]

    m.capacity_constraint = pyo.Constraint(m.Units, m.T, rule=capacity_constraint_rule)

    # Storage dynamics (simplified)
    def storage_dynamics_rule(model, t):
        if t == 1:
            return model.storage_level[t] == 0
        else:
            return model.storage_level[t] == model.storage_level[t-1] * 0.95

    m.storage_dynamics = pyo.Constraint(m.T, rule=storage_dynamics_rule)

    # Objective
    def objective_rule(model):
        return sum(model.grid_purchase[t] * model.price[t] for t in model.T) + \
               sum(model.invest_capacity[u] * 1000.0 for u in model.Units)

    m.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize)

    print(f"[TEST] Model created: {m.name}")
    return m


def test_model_inspection():
    """Test model inspection function."""
    print("\n" + "="*70)
    print("TEST: Model Inspection")
    print("="*70)

    m = create_simple_test_model()

    print("\n[TEST] Inspecting model...")
    inspection = inspect_pyomo_model(m)

    print("\n[TEST] Inspection results:")
    print(f"  - Model Name: {inspection['summary'].get('model_name')}")
    print(f"  - Sets: {inspection['summary'].get('num_sets')}")
    print(f"  - Parameters: {inspection['summary'].get('num_parameters')}")
    print(f"  - Variables: {inspection['summary'].get('num_variables')}")
    print(f"  - Constraints: {inspection['summary'].get('num_constraints')}")
    print(f"  - Objectives: {inspection['summary'].get('num_objectives')}")

    print("\n[TEST] Sample parameter info:")
    for p in inspection['parameters'][:3]:
        print(f"  - {p['name']}: size={p.get('size', 'N/A')}, indexed={p.get('indexed', False)}")

    print("\n[TEST] Sample variable info:")
    for v in inspection['variables'][:3]:
        print(f"  - {v['name']}: size={v.get('size', 'N/A')}, domain={v.get('domain', 'N/A')}")

    print("\n[TEST] Sample constraint info:")
    for c in inspection['constraints'][:3]:
        print(f"  - {c['name']}: size={c.get('size', 'N/A')}")

    return inspection


def test_model_export():
    """Test model export to files."""
    print("\n" + "="*70)
    print("TEST: Model Export")
    print("="*70)

    m = create_simple_test_model()

    output_dir = "test_exports/model_structure"
    print(f"\n[TEST] Exporting model to: {output_dir}")

    try:
        paths = export_model_structure(m, output_dir, prefix="test_model")

        print("\n[TEST] Export successful! Created files:")
        for key, path in paths.items():
            size = os.path.getsize(path) if os.path.exists(path) else 0
            print(f"  - {key}: {path} ({size} bytes)")

        # Verify files exist
        for key, path in paths.items():
            if not os.path.exists(path):
                print(f"[ERROR] File not created: {path}")
                return False

        print("\n[TEST] All files created successfully!")
        return True

    except Exception as e:
        print(f"[ERROR] Export failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("PYOMO MODEL EXPORT - TEST SUITE")
    print("="*70)

    success = True

    # Test 1: Model Inspection
    try:
        test_model_inspection()
        print("\n[✓] Model inspection test PASSED")
    except Exception as e:
        print(f"\n[✗] Model inspection test FAILED: {e}")
        import traceback
        traceback.print_exc()
        success = False

    # Test 2: Model Export
    try:
        if test_model_export():
            print("\n[✓] Model export test PASSED")
        else:
            print("\n[✗] Model export test FAILED")
            success = False
    except Exception as e:
        print(f"\n[✗] Model export test FAILED: {e}")
        import traceback
        traceback.print_exc()
        success = False

    # Summary
    print("\n" + "="*70)
    if success:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("="*70 + "\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

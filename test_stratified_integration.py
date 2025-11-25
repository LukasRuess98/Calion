#!/usr/bin/env python3
"""
Test stratified storage integration in system_builder.

This script tests that the stratified storage integration works correctly
by loading both simple and stratified storage configurations.
"""

from energis.run import rolling_horizon as rh

print("=" * 80)
print("TEST: Stratified Storage Integration")
print("=" * 80)
print()

# Test 1: Simple storage (baseline)
print("Test 1: Loading SIMPLE storage configuration...")
print("-" * 80)
try:
    workflow1 = rh.run_workflow([
        "configs/base.yaml",
        "configs/systems/baseline.system.yaml",
        "configs/scenarios/perfect_forecast_full_year.scenario.yaml",
        "configs/sites/default.site.yaml"
    ])
    result1 = rh.export_workflow_results(workflow1)
    print("✅ Simple storage loaded successfully!")
    print(f"   Output: {result1['outdir']}")
    print()
except Exception as e:
    print(f"❌ Simple storage failed: {e}")
    print()
    import traceback
    traceback.print_exc()

# Test 2: Stratified storage
print("Test 2: Loading STRATIFIED storage configuration...")
print("-" * 80)
try:
    workflow2 = rh.run_workflow([
        "configs/base.yaml",
        "configs/systems/stratified_storage_example.system.yaml",
        "configs/scenarios/perfect_forecast_full_year.scenario.yaml",
        "configs/sites/default.site.yaml"
    ])
    result2 = rh.export_workflow_results(workflow2)
    print("✅ Stratified storage loaded successfully!")
    print(f"   Output: {result2['outdir']}")
    print()
except Exception as e:
    print(f"❌ Stratified storage failed: {e}")
    print()
    import traceback
    traceback.print_exc()

print("=" * 80)
print("Integration test complete!")
print("=" * 80)

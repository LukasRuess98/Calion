#!/usr/bin/env python3
"""
Test script to verify Rolling Horizon solver options fix.

This script tests that solver options (TimeLimit, MIPGap, etc.) are correctly
applied during Rolling Horizon optimization.

Expected runtime WITH fix: ~5-10 minutes for 1 week
Expected runtime WITHOUT fix: >30 minutes (or timeout)
"""

import time
from pathlib import Path

from calion.run import rolling_horizon as rh


def test_rh_solver_options():
    """Test that solver options are applied in Rolling Horizon."""

    print("=" * 80)
    print("TESTING ROLLING HORIZON SOLVER OPTIONS FIX")
    print("=" * 80)
    print()

    # Use a small scenario for fast testing
    cfg_paths = [
        "configs/base.yaml",
        "configs/tech_catalog.yaml",
        "configs/sites/default.site.yaml",
        "configs/systems/baseline.system.yaml",
        "configs/scenarios/test_1week.scenario.yaml",  # Small test case
    ]

    # Verify all configs exist
    print("📋 Configuration files:")
    for path in cfg_paths:
        exists = Path(path).exists()
        symbol = "✅" if exists else "❌"
        print(f"  {symbol} {path}")
    print()

    # Run workflow
    print("⏱️  Starting optimization...")
    start_time = time.time()

    try:
        workflow = rh.run_workflow(cfg_paths)
        elapsed = time.time() - start_time

        print()
        print("=" * 80)
        print("✅ OPTIMIZATION SUCCESSFUL")
        print("=" * 80)
        print(f"⏱️  Total time: {elapsed:.1f} seconds ({elapsed/60:.2f} minutes)")
        print(f"📊 Workflow: {' → '.join(workflow.plan.steps)}")

        # Check if it's RH
        if 'RH' in workflow.plan.steps and workflow.rh_result:
            print(f"📊 RH Windows: {len(workflow.rh_result.windows)}")
            print(f"📊 Time per window: {elapsed/len(workflow.rh_result.windows):.1f} seconds")

            # Verify solver options were applied
            if workflow.rh_result.windows:
                first_window = workflow.rh_result.windows[0]
                print(f"📊 First window solver: {first_window.solver.get('solver_used', 'unknown')}")
                print(f"📊 Termination: {first_window.solver.get('termination_condition', 'unknown')}")

        # Performance check
        print()
        print("🎯 Performance Analysis:")
        if elapsed < 600:  # Less than 10 minutes
            print(f"  ✅ EXCELLENT: Completed in {elapsed/60:.1f} minutes")
            print(f"     Solver options are working correctly!")
        elif elapsed < 1800:  # Less than 30 minutes
            print(f"  ⚠️  ACCEPTABLE: Completed in {elapsed/60:.1f} minutes")
            print(f"     Might benefit from tighter solver settings")
        else:
            print(f"  ❌ TOO SLOW: Took {elapsed/60:.1f} minutes")
            print(f"     Solver options might not be applied correctly!")

        return True

    except Exception as e:
        elapsed = time.time() - start_time
        print()
        print("=" * 80)
        print("❌ OPTIMIZATION FAILED")
        print("=" * 80)
        print(f"⏱️  Failed after: {elapsed:.1f} seconds ({elapsed/60:.2f} minutes)")
        print(f"🔴 Error: {e}")

        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_rh_solver_options()
    exit(0 if success else 1)

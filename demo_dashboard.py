#!/usr/bin/env python3
"""
Quick dashboard demo with minimal example.

This creates a simple workflow and displays the dashboard.
"""

import sys
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("🎛️ EnerGIS Dashboard - Quick Demo")
print("="*70)

# Import dashboard
from energis.io.dashboard import create_dashboard
from energis.run import rolling_horizon as rh

print("\n1. Loading configuration...")
CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/sites/default.site.yaml',
    'configs/systems/baseline.system.yaml',
    'configs/scenarios/pf_then_rh.workflow.scenario.yaml',
]

print("   ✅ Configuration loaded")

print("\n2. Running optimization workflow...")
print("   ⏳ This may take a few minutes...")

try:
    workflow = rh.run_workflow(CONFIG_PATHS)
    print("   ✅ Optimization completed!")

    # Check results
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None

    print(f"\n3. Results available:")
    print(f"   PF: {'✅' if has_pf else '❌'}")
    print(f"   RH: {'✅' if has_rh else '❌'}")

    if has_pf or has_rh:
        print("\n4. Creating dashboard...")
        dashboard = create_dashboard(workflow, title="Quick Demo Dashboard")
        print("   ✅ Dashboard created!")

        print("\n" + "="*70)
        print("✅ SUCCESS!")
        print("="*70)

        print("\n📊 Dashboard is ready!")
        print("\nTo view the dashboard:")
        print("  1. Save this as 'demo_dashboard.py'")
        print("  2. Add 'dashboard.servable()' at the end")
        print("  3. Run: panel serve demo_dashboard.py --show")

        print("\nOr in Jupyter:")
        print("  - Copy workflow creation code to notebook")
        print("  - Add: dashboard = create_dashboard(workflow)")
        print("  - Run: dashboard")

        # Save dashboard info
        result = workflow.pf_result or workflow.rh_result
        print(f"\n📈 Quick stats:")
        print(f"  Timesteps: {len(result.table):,}")
        if result.costs:
            obj_value = result.costs.get('objective.OBJ_value_EUR', 0)
            print(f"  Total cost: {obj_value:,.0f} EUR")

    else:
        print("\n⚠️  No results available - check optimization")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)

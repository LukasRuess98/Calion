#!/usr/bin/env python3
"""
Quick test script for CALION Dashboard.

This script tests if the dashboard can be imported and basic functionality works.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("🧪 Testing CALION Dashboard")
print("="*70)

# Test 1: Import dashboard
print("\n1. Testing dashboard import...")
try:
    from calion.io.dashboard import create_dashboard, HAVE_PANEL, HAVE_PLOTLY
    print("   ✅ Dashboard module imported successfully")
except ImportError as e:
    print(f"   ❌ Failed to import dashboard: {e}")
    print("\n   💡 Install dependencies:")
    print("      pip install panel holoviews bokeh plotly")
    sys.exit(1)

# Test 2: Check dependencies
print("\n2. Checking dependencies...")
if HAVE_PANEL:
    import panel as pn
    print(f"   ✅ Panel {pn.__version__} available")
else:
    print("   ❌ Panel not available")

if HAVE_PLOTLY:
    import plotly
    print(f"   ✅ Plotly {plotly.__version__} available")
else:
    print("   ❌ Plotly not available")

# Test 3: Check if workflow can be run
print("\n3. Testing workflow import...")
try:
    from calion.run import rolling_horizon as rh
    print("   ✅ Workflow module available")
except ImportError as e:
    print(f"   ❌ Failed to import workflow: {e}")
    sys.exit(1)

# Test 4: Check config files
print("\n4. Checking config files...")
config_files = [
    'configs/base.yaml',
    'configs/scenarios/stadtbach_baseline_2023.yaml',
    'configs/scenarios/stadtbach_baseline_week_test.yaml',
    'configs/templates/level1_single_node.yaml',
    'configs/templates/level2_5node.yaml',
]

all_configs_exist = True
for config in config_files:
    config_path = project_root / config
    if config_path.exists():
        print(f"   ✅ {config}")
    else:
        print(f"   ❌ {config} not found")
        all_configs_exist = False

if not all_configs_exist:
    print("\n   ⚠️  Some config files are missing")
    print("      Dashboard can still be tested with custom configs")

print("\n" + "="*70)
print("✅ Dashboard is ready to use!")
print("="*70)

print("\n📚 Usage examples:")
print("\n1. In Jupyter Notebook:")
print("   from calion.run import rolling_horizon as rh")
print("   from calion.io.dashboard import create_dashboard")
print("   ")
print("   workflow = rh.run_workflow(CONFIG_PATHS)")
print("   dashboard = create_dashboard(workflow)")
print("   dashboard  # Display")

print("\n2. As Webapp:")
print("   panel serve notebooks/interactive_dashboard.ipynb --show")

print("\n3. Run demo notebook:")
print("   jupyter notebook notebooks/interactive_dashboard.ipynb")

print("\n" + "="*70)

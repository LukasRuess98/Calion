#!/usr/bin/env python3
"""
Complete System Check for EnerGIS Network Designer
Validates all dependencies, modules, and configurations
"""

import sys
import subprocess
from pathlib import Path

def check_section(title):
    """Print section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def check_python_version():
    """Check Python version"""
    check_section("1. Python Version")
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")

    if version.major >= 3 and version.minor >= 8:
        print("✅ Python version OK (>= 3.8)")
        return True
    else:
        print("❌ Python version too old (need >= 3.8)")
        return False

def check_dependencies():
    """Check required packages"""
    check_section("2. Python Dependencies")

    required = {
        # Core dependencies
        'numpy': 'Core numerical library',
        'pandas': 'Data manipulation',
        'pyyaml': 'Configuration files',

        # Optimization
        'pyomo': 'Optimization modeling',

        # Dashboard
        'panel': 'Interactive dashboards',
        'plotly': 'Interactive plots',
        'holoviews': 'Visualization library',
        'bokeh': 'Interactive plotting backend',

        # Optional but recommended
        'matplotlib': 'Static plots',
        'openpyxl': 'Excel file support',
    }

    all_ok = True
    for package, description in required.items():
        try:
            if package == 'pyyaml':
                __import__('yaml')
            else:
                __import__(package)
            print(f"✅ {package:20s} - {description}")
        except ImportError:
            print(f"❌ {package:20s} - {description} [MISSING]")
            all_ok = False

    return all_ok

def check_solver():
    """Check Gurobi solver"""
    check_section("3. Optimization Solver (Gurobi)")

    try:
        import gurobipy
        print(f"✅ Gurobi installed: version {gurobipy.gurobi.version()}")

        # Try to create a test model
        try:
            m = gurobipy.Model()
            print("✅ Gurobi license valid")
            return True
        except Exception as e:
            print(f"⚠️  Gurobi installed but license issue: {e}")
            print("   You can still use the Network Designer, but simulations will fail")
            return False

    except ImportError:
        print("❌ Gurobi not installed")
        print("   Install: https://www.gurobi.com/downloads/")
        print("   Academic license: https://www.gurobi.com/academia/")
        return False

def check_framework_modules():
    """Check EnerGIS framework modules"""
    check_section("4. EnerGIS Framework Modules")

    modules = {
        'energis.run.rolling_horizon': ['run_workflow', 'WorkflowResult'],
        'energis.models.system_builder': ['build_model'],
        'energis.io.dashboard': ['create_dashboard', 'EnerGISDashboard'],
        'energis.io.network_designer': ['create_network_designer', 'ThermalNetworkDesigner'],
        'energis.io.network_results_viewer': ['create_results_viewer', 'NetworkResultsViewer'],
    }

    all_ok = True
    for module_name, expected_attrs in modules.items():
        try:
            module = __import__(module_name, fromlist=expected_attrs)

            missing = []
            for attr in expected_attrs:
                if not hasattr(module, attr):
                    missing.append(attr)

            if missing:
                print(f"⚠️  {module_name}")
                for m in missing:
                    print(f"      Missing: {m}")
                all_ok = False
            else:
                print(f"✅ {module_name}")

        except ImportError as e:
            print(f"❌ {module_name}: {e}")
            all_ok = False

    return all_ok

def check_config_files():
    """Check configuration files"""
    check_section("5. Configuration Files")

    required_configs = [
        'configs/base.yaml',
        'configs/systems/baseline.system.yaml',
    ]

    all_ok = True
    for config_path in required_configs:
        path = Path(config_path)
        if path.exists():
            print(f"✅ {config_path}")
        else:
            print(f"❌ {config_path} [MISSING]")
            all_ok = False

    return all_ok

def check_data_files():
    """Check for example data"""
    check_section("6. Example Data Files")

    data_locations = [
        'data/',
        'notebooks/data/',
        'examples/data/',
    ]

    found_data = False
    for location in data_locations:
        path = Path(location)
        if path.exists():
            files = list(path.glob('*.xlsx')) + list(path.glob('*.csv'))
            if files:
                print(f"✅ Found {len(files)} data files in {location}")
                found_data = True
                for f in files[:3]:  # Show first 3
                    print(f"   - {f.name}")

    if not found_data:
        print("⚠️  No example data files found")
        print("   You'll need timeseries data (waermebedarf_MWth, strompreis_EUR_MWh, etc.)")

    return found_data

def check_directories():
    """Check required directories"""
    check_section("7. Directory Structure")

    required_dirs = [
        'energis/io',
        'energis/run',
        'energis/models',
        'configs/systems',
        'configs/scenarios',
        'exports',
        'notebooks',
    ]

    all_ok = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists() and path.is_dir():
            print(f"✅ {dir_path}/")
        else:
            print(f"❌ {dir_path}/ [MISSING]")
            all_ok = False

    return all_ok

def print_summary(results):
    """Print final summary"""
    check_section("Summary")

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}")

    print("\n" + "="*70)

    if all_passed:
        print("✅ ALL CHECKS PASSED - System ready!")
        print("\nNext steps:")
        print("  1. python start_network_designer.py")
        print("  2. Or: jupyter notebook notebooks/complete_workflow.ipynb")
    else:
        print("❌ SOME CHECKS FAILED - See details above")
        print("\nTo fix:")
        print("  1. Install missing packages: pip install -r requirements.txt")
        print("  2. Install Gurobi: https://www.gurobi.com/downloads/")
        print("  3. Run: pip install -e .")

def main():
    """Run all checks"""
    print("\n" + "="*70)
    print("  EnerGIS Network Designer - System Check")
    print("="*70)

    results = {
        'Python Version': check_python_version(),
        'Dependencies': check_dependencies(),
        'Gurobi Solver': check_solver(),
        'Framework Modules': check_framework_modules(),
        'Config Files': check_config_files(),
        'Data Files': check_data_files(),
        'Directories': check_directories(),
    }

    print_summary(results)

    # Return exit code
    sys.exit(0 if all(results.values()) else 1)

if __name__ == '__main__':
    main()

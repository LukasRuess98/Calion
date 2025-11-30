#!/usr/bin/env python3
"""
Dashboard Compatibility Check

Prüft ob alle Dependencies für das Dashboard installiert sind
und testet die Kompatibilität mit VS Code und Browser.
"""

import sys
from pathlib import Path

# Colors for output
class Colors:
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*70}{Colors.NC}")
    print(f"{Colors.BLUE}{text}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*70}{Colors.NC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.NC}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.NC}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.NC}")

def check_dependencies():
    """Check if all required dependencies are installed."""
    print_header("📦 Dependency Check")

    all_ok = True

    # Panel
    try:
        import panel as pn
        print_success(f"Panel version {pn.__version__} installed")
    except ImportError:
        print_error("Panel not installed")
        print("   Install: pip install panel")
        all_ok = False

    # Holoviews
    try:
        import holoviews as hv
        print_success(f"Holoviews version {hv.__version__} installed")
    except ImportError:
        print_error("Holoviews not installed")
        print("   Install: pip install holoviews")
        all_ok = False

    # Plotly
    try:
        import plotly
        print_success(f"Plotly version {plotly.__version__} installed")
    except ImportError:
        print_error("Plotly not installed")
        print("   Install: pip install plotly")
        all_ok = False

    # Bokeh
    try:
        import bokeh
        print_success(f"Bokeh version {bokeh.__version__} installed")
    except ImportError:
        print_error("Bokeh not installed")
        print("   Install: pip install bokeh")
        all_ok = False

    # Pandas
    try:
        import pandas as pd
        print_success(f"Pandas version {pd.__version__} installed")
    except ImportError:
        print_error("Pandas not installed")
        print("   Install: pip install pandas")
        all_ok = False

    return all_ok

def check_panel_extensions():
    """Check if Panel extensions work correctly."""
    print_header("🔧 Panel Extension Check")

    try:
        import panel as pn

        # Test plotly extension
        print("Testing 'plotly' extension...")
        pn.extension('plotly', sizing_mode='stretch_width')
        print_success("Plotly extension loaded")

        # Test tabulator extension
        print("\nTesting 'tabulator' extension...")
        pn.extension('tabulator')
        print_success("Tabulator extension loaded")

        # Test both together (as used in dashboard)
        print("\nTesting combined extensions...")
        pn.extension('plotly', 'tabulator', sizing_mode='stretch_width')
        print_success("Combined extensions loaded successfully")

        return True

    except Exception as e:
        print_error(f"Extension loading failed: {e}")
        return False

def check_widgets():
    """Check if all required widgets work."""
    print_header("🎛️ Widget Compatibility Check")

    try:
        import panel as pn
        import pandas as pd
        import plotly.graph_objects as go

        # Test Tabulator widget
        print("Testing Tabulator widget...")
        df = pd.DataFrame({
            'Category': ['A', 'B', 'C'],
            'Value': [100, 200, 300],
            'Percentage': [33.3, 66.6, 100.0]
        })

        table = pn.widgets.Tabulator(
            df,
            sizing_mode='stretch_width',
            theme='modern',
            formatters={
                'Value': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 0},
                'Percentage': {'type': 'progress', 'max': 100}
            }
        )
        print_success("Tabulator widget works")

        # Test Plotly pane
        print("\nTesting Plotly pane...")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        pane = pn.pane.Plotly(fig)
        print_success("Plotly pane works")

        # Test Select widget
        print("\nTesting Select widget...")
        selector = pn.widgets.Select(
            name='Test',
            options={'Option 1': 1, 'Option 2': 2},
            value=1
        )
        print_success("Select widget works")

        # Test MultiChoice widget
        print("\nTesting MultiChoice widget...")
        multi = pn.widgets.MultiChoice(
            name='Test Multi',
            options=['A', 'B', 'C'],
            value=['A']
        )
        print_success("MultiChoice widget works")

        # Test IntRangeSlider
        print("\nTesting IntRangeSlider widget...")
        slider = pn.widgets.IntRangeSlider(
            name='Test Range',
            start=0,
            end=100,
            value=(0, 50)
        )
        print_success("IntRangeSlider widget works")

        return True

    except Exception as e:
        print_error(f"Widget test failed: {e}")
        return False

def check_dashboard_module():
    """Check if the dashboard module can be imported."""
    print_header("📊 Dashboard Module Check")

    try:
        # Add project root to path
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Import dashboard module
        print("Importing dashboard module...")
        from energis.io.dashboard import create_dashboard, HAVE_PANEL, HAVE_PLOTLY
        print_success("Dashboard module imported successfully")

        print(f"\n   HAVE_PANEL: {HAVE_PANEL}")
        print(f"   HAVE_PLOTLY: {HAVE_PLOTLY}")

        if not HAVE_PANEL:
            print_error("Panel not available in dashboard module")
            return False

        if not HAVE_PLOTLY:
            print_warning("Plotly not available (optional)")

        # Import notebook helpers
        print("\nImporting notebook helpers...")
        from energis.io.notebook_helpers import (
            create_and_display_dashboard,
            setup_notebook_environment
        )
        print_success("Notebook helpers imported successfully")

        return True

    except Exception as e:
        print_error(f"Module import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_saved_workflows():
    """Check if there are saved workflows to display."""
    print_header("💾 Saved Workflows Check")

    try:
        project_root = Path(__file__).parent
        saved_dir = project_root / 'saved_workflows'

        if not saved_dir.exists():
            print_warning(f"saved_workflows/ directory not found")
            print("   Create workflows first using runner.ipynb or scenario_studio.ipynb")
            return False

        # Count workflow directories
        workflow_dirs = [d for d in saved_dir.iterdir() if d.is_dir()]

        if not workflow_dirs:
            print_warning("No saved workflows found")
            print("   Create workflows first using runner.ipynb or scenario_studio.ipynb")
            return False

        print_success(f"Found {len(workflow_dirs)} saved workflow(s)")

        # Check if they have metadata
        workflows_with_metadata = []
        for wf_dir in workflow_dirs:
            if (wf_dir / 'metadata.json').exists():
                workflows_with_metadata.append(wf_dir)

        print(f"   • {len(workflows_with_metadata)} with metadata.json")
        print(f"   • {len([d for d in workflow_dirs if (d / 'workflow.pkl').exists()])} with workflow.pkl")

        return len(workflows_with_metadata) > 0

    except Exception as e:
        print_error(f"Workflow check failed: {e}")
        return False

def check_environment():
    """Check the current environment (VS Code, Jupyter, Terminal)."""
    print_header("🖥️ Environment Check")

    # Check if in VS Code
    vscode_detected = 'VSCODE_PID' in sys.modules or 'vscode' in sys.modules
    if vscode_detected:
        print_success("VS Code detected")
    else:
        print("   Running outside VS Code")

    # Check if in Jupyter
    try:
        from IPython import get_ipython
        ipython = get_ipython()
        if ipython is not None:
            print_success(f"IPython/Jupyter detected: {type(ipython).__name__}")
        else:
            print("   Not in IPython/Jupyter environment")
    except ImportError:
        print("   Not in IPython/Jupyter environment")

    # Check display availability
    import os
    if os.environ.get('DISPLAY'):
        print_success(f"Display available: {os.environ.get('DISPLAY')}")
    else:
        print_warning("No DISPLAY environment variable (headless mode)")
        print("   This is normal for servers - use panel serve for web access")

    return True

def print_recommendations():
    """Print recommendations based on checks."""
    print_header("💡 Recommendations")

    print(f"{Colors.BLUE}For VS Code:{Colors.NC}")
    print("   • Open notebooks/interactive_dashboard.ipynb")
    print("   • Run cells interactively")
    print("   • Dashboard renders inline in VS Code")
    print()

    print(f"{Colors.BLUE}For Browser (localhost):{Colors.NC}")
    print("   • Run: ./start_dashboard.sh")
    print("   • Browser opens automatically at http://localhost:5006")
    print("   • Fully interactive with all features")
    print()

    print(f"{Colors.BLUE}For Server (remote access):{Colors.NC}")
    print("   • Run: ./start_dashboard_server.sh")
    print("   • Access from any PC: http://SERVER-IP:5006")
    print("   • Or use SSH tunnel: ssh -L 5006:localhost:5006 user@server")
    print()

    print(f"{Colors.BLUE}Troubleshooting:{Colors.NC}")
    print("   • If widgets don't show: restart kernel and re-run setup cells")
    print("   • If port busy: use ./start_dashboard.sh 5007")
    print("   • If Panel not found: pip install panel holoviews bokeh plotly")

def main():
    """Run all checks."""
    print(f"\n{Colors.GREEN}{'='*70}{Colors.NC}")
    print(f"{Colors.GREEN}  🎛️  EnerGIS Dashboard Compatibility Check{Colors.NC}")
    print(f"{Colors.GREEN}{'='*70}{Colors.NC}")

    results = {
        'dependencies': check_dependencies(),
        'extensions': check_panel_extensions() if 'panel' in sys.modules else False,
        'widgets': check_widgets() if 'panel' in sys.modules else False,
        'dashboard': check_dashboard_module(),
        'workflows': check_saved_workflows(),
        'environment': check_environment(),
    }

    # Summary
    print_header("📋 Summary")

    for check, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {check.capitalize():20s} {status}")

    all_passed = all(results.values())

    if all_passed:
        print(f"\n{Colors.GREEN}{'='*70}{Colors.NC}")
        print(f"{Colors.GREEN}  ✅ All checks passed! Dashboard is ready to use.{Colors.NC}")
        print(f"{Colors.GREEN}{'='*70}{Colors.NC}\n")
    else:
        print(f"\n{Colors.YELLOW}{'='*70}{Colors.NC}")
        print(f"{Colors.YELLOW}  ⚠️  Some checks failed. See above for details.{Colors.NC}")
        print(f"{Colors.YELLOW}{'='*70}{Colors.NC}\n")

    # Recommendations
    print_recommendations()

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

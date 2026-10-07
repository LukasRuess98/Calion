"""
CALION Dashboard Package.

This modular package provides a comprehensive, interactive dashboard for exploring
optimization results from CALION workflows (PF, RH, MPC).

Features:
- Multi-tab interface with Overview, Timeseries, Emissions, Costs, Design, Comparison
- Interactive plots with Plotly/Holoviews
- Real-time component selection and filtering
- CO2 emissions tracking and visualization
- Export functionality
- Responsive design

Usage:
    from calion.io.dashboard import create_dashboard

    dashboard = create_dashboard(workflow)
    dashboard.show()  # In Jupyter

    # Or serve as webapp:
    # dashboard.servable()
    # panel serve notebook.ipynb

Module Structure:
    - core.py: Main dashboard class (CALIONDashboard)
    - data_preparation.py: Data extraction and preparation logic
    - utils.py: Utility functions (colors, formatting)
    - widgets.py: Reusable widget components
    - tabs/: Individual tab implementations
"""

from __future__ import annotations

# Check dependencies
try:
    import holoviews as hv
    import panel as pn
    from holoviews import dim, opts  # noqa: F401
    HAVE_PANEL = True
except ImportError:
    HAVE_PANEL = False
    pn = None
    hv = None

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots  # noqa: F401
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False
    go = None

# Import main components
from .core import CALIONDashboard, create_dashboard
from .diagnostics import diagnose_workflow

__all__ = [
    "HAVE_PANEL",
    "HAVE_PLOTLY",
    "CALIONDashboard",
    "create_dashboard",
    "diagnose_workflow",
]

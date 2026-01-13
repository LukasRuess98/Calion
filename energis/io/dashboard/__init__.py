"""
EnerGIS Dashboard Package.

This modular package provides a comprehensive, interactive dashboard for exploring
optimization results from EnerGIS workflows (PF, RH, MPC).

Features:
- Multi-tab interface with Overview, Timeseries, Emissions, Costs, Design, Comparison
- Interactive plots with Plotly/Holoviews
- Real-time component selection and filtering
- CO2 emissions tracking and visualization
- Export functionality
- Responsive design

Usage:
    from energis.io.dashboard import create_dashboard

    dashboard = create_dashboard(workflow)
    dashboard.show()  # In Jupyter

    # Or serve as webapp:
    # dashboard.servable()
    # panel serve notebook.ipynb

Module Structure:
    - core.py: Main dashboard class (EnerGISDashboard)
    - data_preparation.py: Data extraction and preparation logic
    - utils.py: Utility functions (colors, formatting)
    - widgets.py: Reusable widget components
    - tabs/: Individual tab implementations
"""

from __future__ import annotations

# Check dependencies
try:
    import panel as pn
    import holoviews as hv
    from holoviews import opts, dim
    HAVE_PANEL = True
except ImportError:
    HAVE_PANEL = False
    pn = None
    hv = None

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False
    go = None

# Import main components
from .diagnostics import diagnose_workflow
from .core import EnerGISDashboard, create_dashboard

__all__ = [
    "create_dashboard",
    "EnerGISDashboard",
    "diagnose_workflow",
    "HAVE_PANEL",
    "HAVE_PLOTLY",
]

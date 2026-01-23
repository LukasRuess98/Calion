"""
Core dashboard class for the EnerGIS Dashboard.

Contains the main EnerGISDashboard class and create_dashboard function.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import panel as pn
    HAVE_PANEL = True
except ImportError:
    HAVE_PANEL = False
    pn = None

from .diagnostics import diagnose_workflow, print_diagnosis
from .data_preparation import DashboardData, prepare_dashboard_data

logger = logging.getLogger(__name__)


def create_dashboard(
    workflow: Any,
    title: str = "EnerGIS Interactive Dashboard",
    diagnose: bool = True
) -> Any:
    """
    Create an interactive Panel dashboard for EnerGIS workflow results.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow result from run_workflow()
    title : str, optional
        Dashboard title
    diagnose : bool, optional
        Run diagnostic check before creating dashboard (default: True)

    Returns
    -------
    pn.Tabs
        Panel dashboard with multiple tabs

    Notes
    -----
    **VS-Code Users:** Panel dashboards work best when viewed in a browser.
    If widgets/plots are not displaying correctly in VS-Code, try:

    1. Run: `panel serve notebook.ipynb --show`
    2. Or save and open the notebook in JupyterLab/Jupyter Notebook

    **Troubleshooting:** If data is not displaying:

    - Use `diagnose_workflow(workflow)` to check for missing data
    - Verify optimization completed successfully
    - Check that result.series and result.costs are populated
    """
    if not HAVE_PANEL:
        raise ImportError(
            "Panel is required for dashboards. Install with: pip install panel holoviews bokeh"
        )

    # Run diagnostic check
    if diagnose:
        diagnosis = diagnose_workflow(workflow)

        if diagnosis['issues']:
            logger.warning("Dashboard creation: issues detected")
            for issue in diagnosis['issues']:
                logger.warning(f"  - {issue}")

        if diagnosis['recommendations']:
            logger.info("Dashboard recommendations:")
            for rec in diagnosis['recommendations']:
                logger.info(f"  - {rec}")

        print_diagnosis(diagnosis)

    # Initialize Panel with all required extensions
    pn.extension('plotly', 'tabulator', sizing_mode='stretch_width')

    # Create dashboard instance
    dashboard = EnerGISDashboard(workflow, title)

    return dashboard.create()


class EnerGISDashboard:
    """
    Main dashboard class for EnerGIS.

    This class orchestrates the creation of the complete dashboard
    by delegating to specialized tab modules.

    Attributes
    ----------
    workflow : Any
        The workflow result object
    title : str
        Dashboard title
    data : DashboardData
        Prepared dashboard data container
    has_pf : bool
        Whether PF result is available
    has_rh : bool
        Whether RH result is available
    has_mpc : bool
        Whether MPC result is available
    primary_result : Any
        The primary result to display
    primary_label : str
        Label for primary result (PF/RH/MPC)
    """

    def __init__(self, workflow: Any, title: str):
        """
        Initialize dashboard.

        Parameters
        ----------
        workflow : Any
            Workflow result object
        title : str
            Dashboard title
        """
        self.workflow = workflow
        self.title = title

        # Determine which results are available
        self.has_pf = workflow.pf_result is not None
        self.has_rh = workflow.rh_result is not None
        self.has_mpc = workflow.mpc_result is not None

        # Select primary result for display
        if self.has_rh:
            self.primary_result = workflow.rh_result
            self.primary_label = "RH"
        elif self.has_mpc:
            self.primary_result = workflow.mpc_result
            self.primary_label = "MPC"
        elif self.has_pf:
            self.primary_result = workflow.pf_result
            self.primary_label = "PF"
        else:
            raise ValueError("No results available in workflow")

        # Prepare data using the data preparation module
        self.data = prepare_dashboard_data(
            self.primary_result,
            workflow_config=getattr(workflow, 'config', None)
        )

    def create(self) -> 'pn.Tabs':
        """
        Create the complete dashboard with all tabs.

        Returns
        -------
        pn.Tabs
            Complete dashboard
        """
        from .tabs import (
            create_overview_tab,
            create_timeseries_tab,
            create_duration_curve_tab,
            create_efficiency_tab,
            create_sankey_tab,
            create_emissions_tab,
            create_costs_tab,
            create_design_tab,
            create_comparison_tab,
            create_multi_network_tab,
            has_multi_network_data,
        )

        tabs = pn.Tabs(
            ('Übersicht', create_overview_tab(
                self.data, self.primary_result, self.workflow, self.primary_label
            )),
            ('Zeitreihen', create_timeseries_tab(self.data)),
            ('Jahresdauerlinie', create_duration_curve_tab(self.data)),
            ('Effizienz & COP', create_efficiency_tab(self.data)),
            ('Energieflüsse', create_sankey_tab(self.data)),
            ('CO2-Emissionen', create_emissions_tab(self.data, self.primary_result)),
            ('Kosten', create_costs_tab(self.data)),
            ('Anlagen-Design', create_design_tab(self.workflow)),
            dynamic=True
        )

        # Add multi-network tab if multi-network data is available
        if has_multi_network_data(self.data):
            # Try to get multi-network results from workflow
            multi_results = None
            if hasattr(self.workflow, 'multi_network_results'):
                multi_results = self.workflow.multi_network_results
            elif hasattr(self.primary_result, 'multi_network'):
                multi_results = self.primary_result.multi_network

            tabs.append((
                'Multi-Netzwerk',
                create_multi_network_tab(self.data, multi_results)
            ))

        # Add comparison tab if multiple results available
        if (self.has_pf and self.has_rh) or (self.has_pf and self.has_mpc):
            tabs.append((
                'Vergleich',
                create_comparison_tab(
                    self.workflow, self.has_pf, self.has_rh, self.has_mpc
                )
            ))

        # Header
        header = pn.pane.Markdown(
            f"# {self.title}\n"
            f"**Workflow:** {' → '.join(self.workflow.plan.steps)} | "
            f"**Zeitschritte:** {len(self.data.df):,}",
            sizing_mode='stretch_width'
        )

        return pn.Column(header, tabs, sizing_mode='stretch_width')

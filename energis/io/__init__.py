"""
Input/Output utilities for the Heat Planning Framework.

This package provides:
- Data loading from Excel files
- Result export to Excel, CSV, JSON
- Visualization (standard plots)
- Publication-quality exports (plots, LaTeX tables, KPI summaries)
"""

from energis.io.loader import load_input_excel
from energis.io.exporter import (
    export_scenario_bundle,
    write_scenario_workbook,
    write_timeseries_csv,
    HAVE_OPENPYXL,
)
from energis.io.plotter import export_plots, HAVE_MATPLOTLIB

# Publication exports (optional, requires matplotlib)
try:
    from energis.io.publication_plotter import (
        export_publication_plots,
        PublicationConfig,
    )
    from energis.io.publication_exporter import (
        export_publication_bundle,
        export_kpi_summary,
        export_latex_tables,
        format_number,
    )
    HAVE_PUBLICATION_EXPORTS = True
except ImportError:
    HAVE_PUBLICATION_EXPORTS = False
    export_publication_plots = None
    export_publication_bundle = None
    export_kpi_summary = None
    export_latex_tables = None
    PublicationConfig = None
    format_number = None

__all__ = [
    # Loader
    "load_input_excel",
    # Standard exports
    "export_scenario_bundle",
    "write_scenario_workbook",
    "write_timeseries_csv",
    "HAVE_OPENPYXL",
    # Standard plots
    "export_plots",
    "HAVE_MATPLOTLIB",
    # Publication exports
    "export_publication_plots",
    "export_publication_bundle",
    "export_kpi_summary",
    "export_latex_tables",
    "PublicationConfig",
    "format_number",
    "HAVE_PUBLICATION_EXPORTS",
]

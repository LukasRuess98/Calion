"""
Input/Output utilities for the Heat Planning Framework.

This package provides:
- Data loading from Excel files
- Result export to Excel, CSV, JSON (consolidated exporter)
- Visualization (standard plots)
- Publication-quality exports (plots, LaTeX tables, KPI summaries)
- Unified export manager for all output formats
"""

from calion.io.loader import load_input_excel
from calion.io.plotter import HAVE_MATPLOTLIB, export_plots

# Unified exporter (consolidates legacy exporter.py + new features)
from calion.io.unified_exporter import (
    HAVE_OPENPYXL,
    ExportConfig,
    ExportResult,
    UnifiedExporter,
    export_scenario_bundle,
    export_with_sensitivity,
    export_workflow,
    write_excel_workbook,
    write_scenario_workbook,
    write_timeseries_csv,
)

# Publication exports (optional, requires matplotlib)
try:
    from calion.io.publication_exporter import (
        export_kpi_summary,
        export_latex_tables,
        export_publication_bundle,
        format_number,
    )
    from calion.io.publication_plotter import (
        PublicationConfig,
        export_publication_plots,
    )
    HAVE_PUBLICATION_EXPORTS = True
except ImportError:
    HAVE_PUBLICATION_EXPORTS = False
    export_publication_plots = None  # type: ignore[assignment]
    export_publication_bundle = None  # type: ignore[assignment]
    export_kpi_summary = None  # type: ignore[assignment]
    export_latex_tables = None  # type: ignore[assignment]
    PublicationConfig = None  # type: ignore[assignment,misc]
    format_number = None  # type: ignore[assignment]

__all__ = [
    "HAVE_MATPLOTLIB",
    "HAVE_OPENPYXL",
    "HAVE_PUBLICATION_EXPORTS",
    "ExportConfig",
    "ExportResult",
    "PublicationConfig",
    # Unified exporter (recommended)
    "UnifiedExporter",
    "export_kpi_summary",
    "export_latex_tables",
    # Standard plots
    "export_plots",
    "export_publication_bundle",
    # Publication exports (legacy, use UnifiedExporter instead)
    "export_publication_plots",
    # Standard exports
    "export_scenario_bundle",
    "export_with_sensitivity",
    "export_workflow",
    "format_number",
    # Loader
    "load_input_excel",
    "write_scenario_workbook",
    "write_timeseries_csv",
]

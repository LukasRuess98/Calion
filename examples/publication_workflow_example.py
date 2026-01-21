#!/usr/bin/env python3
"""
Publication Workflow Example (Simplified)
==========================================

This script demonstrates the unified export workflow for scientific publications.

All exports (data, LaTeX, plots, dashboard) are now handled by a single
`UnifiedExporter` class, eliminating the need for manual data conversion
between different export formats.

Usage:
    # Simple execution with default config
    python examples/publication_workflow_example.py

    # With custom configs
    CONFIG_PATHS="configs/presets/rh_full_system.yaml" \
    SCENARIO_NAME="My_Analysis" \
    python examples/publication_workflow_example.py

    # With sensitivity analysis
    CONFIG_PATHS="configs/presets/rh_full_system.yaml" \
    RUN_SENSITIVITY=1 \
    python examples/publication_workflow_example.py

Output Structure:
    exports/{timestamp}_{scenario}/
    ├── data/
    │   ├── timeseries.csv      # All time series (input + output)
    │   ├── summary.json        # KPIs and costs
    │   ├── costs.json          # Detailed cost breakdown
    │   └── scenario.xlsx       # Complete Excel bundle
    ├── publication/
    │   ├── latex/
    │   │   ├── kpi_summary.tex
    │   │   ├── cost_breakdown.tex
    │   │   └── design_decisions.tex
    │   ├── kpi_summary.json
    │   └── kpi_summary.csv
    ├── figures/
    │   ├── heat_profile.png
    │   ├── cost_breakdown.png
    │   └── ...
    ├── sensitivity/            # Only if RUN_SENSITIVITY=1
    │   ├── tornado_diagram.pdf
    │   ├── sensitivity_results.csv
    │   └── parameter_ranking.txt
    └── export_manifest.json    # Index of all generated files

Author: Publication Framework
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# =============================================================================
# Configuration (via environment variables)
# =============================================================================

SCENARIO_NAME = os.environ.get("SCENARIO_NAME", "Publication_Demo")
EXPORT_DIR = os.environ.get("EXPORT_DIR")  # None = auto-generate with timestamp

CONFIG_PATHS = os.environ.get(
    "CONFIG_PATHS",
    "configs/presets/quick_test.yaml"
).split(",")

# Feature flags
RUN_SENSITIVITY = os.environ.get("RUN_SENSITIVITY", "0") == "1"
EXPORT_DASHBOARD = os.environ.get("EXPORT_DASHBOARD", "0") == "1"


def main():
    """Run the publication workflow."""
    print("=" * 70)
    print("PUBLICATION WORKFLOW")
    print(f"Scenario: {SCENARIO_NAME}")
    print(f"Configs: {', '.join(CONFIG_PATHS)}")
    print("=" * 70)
    print()

    # =========================================================================
    # Step 1: Run Simulation
    # =========================================================================
    print("[1/3] Running simulation...")

    from energis.run.rolling_horizon import run_workflow

    config_paths = [p.strip() for p in CONFIG_PATHS if p.strip()]
    if not config_paths:
        print("ERROR: No valid CONFIG_PATHS provided")
        return 1

    try:
        workflow = run_workflow(config_paths)
    except Exception as e:
        print(f"ERROR: Simulation failed: {e}")
        return 1

    # Check we have results
    active_result = workflow.mpc_result or workflow.rh_result or workflow.pf_result
    if active_result is None:
        print("ERROR: No results from simulation")
        return 1

    mode = "MPC" if workflow.mpc_result else "RH" if workflow.rh_result else "PF"
    print(f"       Simulation completed ({mode} mode)")

    # =========================================================================
    # Step 2: Export All Results (Unified)
    # =========================================================================
    print()
    print("[2/3] Exporting results...")

    from energis.io.unified_exporter import UnifiedExporter, ExportConfig

    export_config = ExportConfig(
        export_excel=True,
        export_csv=True,
        export_json=True,
        export_latex=True,
        latex_style="booktabs",
        export_plots=True,
        plot_formats=["png", "pdf"],
        plot_dpi=300,
        export_dashboard=EXPORT_DASHBOARD,
    )

    exporter = UnifiedExporter(workflow, export_config)
    result = exporter.export_all(
        output_dir=EXPORT_DIR,
        scenario_name=SCENARIO_NAME,
    )

    print(f"       Exported to: {result.output_dir}")
    print(f"       Files generated: {len(result.generated_files)}")

    if result.errors:
        print(f"       Warnings: {len(result.errors)}")
        for err in result.errors:
            print(f"         - {err}")

    # =========================================================================
    # Step 3: Sensitivity Analysis (Optional)
    # =========================================================================
    if RUN_SENSITIVITY:
        print()
        print("[3/3] Running sensitivity analysis...")

        try:
            from energis.analysis.sensitivity_runner import (
                run_full_sensitivity_study,
                create_publication_sensitivity_study,
            )

            sens_dir = os.path.join(result.output_dir, "sensitivity")
            variations = create_publication_sensitivity_study()

            print(f"       Analyzing {len(variations)} parameters...")

            sens_result = run_full_sensitivity_study(
                base_configs=config_paths,
                variations=variations,
                output_dir=sens_dir,
                generate_plots=True,
                generate_latex=True,
                parallel=False,
            )

            print()
            print(sens_result.summary())

            # Add sensitivity files to result
            for name, path in sens_result.generated_files.items():
                result.generated_files[f"sensitivity_{name}"] = path

        except Exception as e:
            print(f"       WARNING: Sensitivity analysis failed: {e}")
            result.errors.append(f"Sensitivity: {e}")
    else:
        print()
        print("[3/3] Sensitivity analysis skipped (set RUN_SENSITIVITY=1 to enable)")

    # =========================================================================
    # Summary
    # =========================================================================
    print()
    print("=" * 70)
    print("EXPORT COMPLETE")
    print("=" * 70)
    print()
    print(f"Output directory: {result.output_dir}")
    print()
    print("Generated files:")

    # Group files by category
    categories = {}
    for key, path in sorted(result.generated_files.items()):
        cat = key.split("_")[0]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((key, path))

    for cat, files in sorted(categories.items()):
        print(f"\n  {cat.upper()}:")
        for key, path in files:
            # Handle case where path might be a list
            if isinstance(path, (list, tuple)):
                path = path[0] if path else "unknown"
            rel_path = os.path.relpath(str(path), result.output_dir)
            print(f"    - {rel_path}")

    print()
    print("=" * 70)

    # Quick access hints
    print("\nQuick access:")
    print(f"  - View summary:    cat {result.output_dir}/data/summary.json")
    print(f"  - Open Excel:      open {result.output_dir}/data/scenario.xlsx")

    latex_dir = os.path.join(result.output_dir, "publication", "latex")
    if os.path.exists(latex_dir):
        print(f"  - LaTeX tables:    ls {latex_dir}/")

    if EXPORT_DASHBOARD:
        print(f"  - Start dashboard: python start_dashboard.py")

    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

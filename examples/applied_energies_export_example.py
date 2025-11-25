#!/usr/bin/env python3
"""
Applied Energies Publication Export Example
============================================

Dieses Beispiel zeigt, wie man die Publication Exports für Applied Energies
verwendet, um alle benötigten Submission-Materialien zu generieren.

Generiert:
- Graphical Abstract (PDF + PNG)
- Research Highlights (3-5 bullet points)
- Publication-Quality Plots (600 DPI, PDF/PNG/EPS)
- LaTeX Tables (Applied Energies style)
- Nomenclature
- Manuscript Template
- KPI Summaries
- Submission Checklist

Usage:
    # Mit Applied Energies Config
    python applied_energies_export_example.py

    # Mit eigener Config
    python applied_energies_export_example.py --config your_config.yaml

    # Nur bestimmte Plots
    PUBLICATION_PLOT_TYPES="heat_balance,cost_breakdown,cop_analysis" \
        python applied_energies_export_example.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
import argparse

# Projekt-Root finden
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from energis.run import rolling_horizon as rh
from energis.config.merge import load_and_merge


def main():
    """Run optimization with Applied Energies publication exports."""

    parser = argparse.ArgumentParser(
        description="Run heat planning optimization with Applied Energies exports"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/applied_energies_config.yaml",
        help="Path to configuration file (default: configs/applied_energies_config.yaml)"
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        default="exports/applied_energies_run",
        help="Export directory (default: exports/applied_energies_run)"
    )
    parser.add_argument(
        "--enable-plots",
        action="store_true",
        default=True,
        help="Enable publication plots (default: True)"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=600,
        help="Figure DPI (default: 600)"
    )
    parser.add_argument(
        "--formats",
        type=str,
        default="pdf,png",
        help="Figure formats, comma-separated (default: pdf,png)"
    )

    args = parser.parse_args()

    print("="*70)
    print("Applied Energies Publication Export")
    print("="*70)
    print(f"Config:     {args.config}")
    print(f"Export Dir: {args.export_dir}")
    print(f"DPI:        {args.dpi}")
    print(f"Formats:    {args.formats}")
    print("="*70)
    print()

    # Load configuration
    config_path = PROJECT_ROOT / args.config

    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        print("\nAvailable configs:")
        config_dir = PROJECT_ROOT / "configs"
        for f in sorted(config_dir.glob("*.yaml")):
            print(f"  - {f.relative_to(PROJECT_ROOT)}")
        return 1

    # Prepare config overrides
    overrides = {
        "export": {
            "enable_publication_exports": True,
            "publication_dpi": args.dpi,
            "publication_formats": args.formats.split(","),
        }
    }

    # Override export directory if specified
    if args.export_dir:
        overrides["export"]["outdir"] = args.export_dir

    # Load and merge config
    print("📋 Loading configuration...")
    cfg = load_and_merge([str(config_path)], overrides=overrides)
    print("✅ Configuration loaded")
    print()

    # Display export settings
    export_cfg = cfg.get("export", {})
    ae_cfg = cfg.get("applied_energies", {})

    print("📦 Export Settings:")
    print(f"  Publication Exports: {export_cfg.get('enable_publication_exports', False)}")
    print(f"  DPI:                 {export_cfg.get('publication_dpi', 300)}")
    print(f"  Formats:             {', '.join(export_cfg.get('publication_formats', ['pdf']))}")
    print(f"  Table Style:         {export_cfg.get('latex_table_style', 'booktabs')}")
    print()

    if ae_cfg:
        print("🎯 Applied Energies Settings:")
        print(f"  Graphical Abstract:  {ae_cfg.get('generate_graphical_abstract', False)}")
        print(f"  Highlights:          {ae_cfg.get('generate_highlights', False)}")
        print(f"  Nomenclature:        {ae_cfg.get('generate_nomenclature', False)}")
        print(f"  Supplementary:       {ae_cfg.get('generate_supplementary', False)}")
        print()

    # Run optimization with exports
    print("="*70)
    print("🚀 Starting Optimization")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        # Run optimization and exports
        workflow = rh.run_workflow([str(config_path)], overrides=overrides)
        result = rh.export_workflow_results(workflow)

        print()
        print("="*70)
        print("✅ Optimization Successful!")
        print("="*70)
        print()

        # Display results
        print("📊 Results:")
        if result.get("summary"):
            summary = result["summary"]

            # Objective
            if "objective" in summary:
                obj = summary["objective"]
                total_cost = obj.get("OBJ_value_EUR")
                if total_cost:
                    print(f"  Total Cost:     {float(total_cost):,.0f} EUR")

            # Grid
            if "grid" in summary:
                grid = summary["grid"]
                co2 = grid.get("total_co2_emissions_t")
                if co2:
                    print(f"  CO₂ Emissions:  {float(co2):,.1f} t/a")

                peak = grid.get("peak_import_MW")
                if peak:
                    print(f"  Peak Demand:    {float(peak):.2f} MW")

        print()

        # Display generated files
        outdir = result.get("outdir", args.export_dir)
        print(f"📁 Output Directory: {outdir}")
        print()

        # Standard exports
        print("Standard Exports:")
        if result.get("scenario_xlsx"):
            print(f"  ✅ Excel:     {Path(result['scenario_xlsx']).name}")
        if result.get("pf_design_json"):
            print(f"  ✅ Design:    {Path(result['pf_design_json']).name}")

        # Publication exports
        if result.get("publication_plots"):
            pub_plots = result["publication_plots"]
            print(f"\n📊 Publication Plots: {len(pub_plots)} types")
            for plot_type, files in pub_plots.items():
                print(f"  ✅ {plot_type}: {len(files)} files")

        if result.get("publication_files"):
            pub_files = result["publication_files"]

            if "latex_tables" in pub_files:
                tables = pub_files["latex_tables"]
                print(f"\n📄 LaTeX Tables: {len(tables)} tables")
                for name, path in tables.items():
                    print(f"  ✅ {name}")

            if "kpi_summary" in pub_files:
                print(f"\n📈 KPI Summary:")
                print(f"  ✅ {Path(pub_files['kpi_summary']).name}")

            if "applied_energies" in pub_files:
                ae_files = pub_files["applied_energies"]
                print(f"\n🎯 Applied Energies Bundle:")
                for key, path in ae_files.items():
                    if path:
                        name = Path(path).name if isinstance(path, str) else key
                        print(f"  ✅ {name}")

        print()
        print("="*70)
        print("🎉 All Exports Complete!")
        print("="*70)
        print()
        print("Next Steps:")
        print("  1. Review outputs in:", outdir)
        print("  2. Check Applied Energies bundle in:", f"{outdir}/applied_energies/")
        print("  3. Review submission checklist:")
        print("     ", f"{outdir}/applied_energies/SUBMISSION_CHECKLIST.md")
        print("  4. See complete guide:")
        print("     ", "docs/APPLIED_ENERGIES_GUIDE.md")
        print()

        return 0

    except Exception as e:
        print()
        print("="*70)
        print("❌ Error!")
        print("="*70)
        print(f"\n{e}\n")

        import traceback
        traceback.print_exc()

        return 1


if __name__ == "__main__":
    sys.exit(main())

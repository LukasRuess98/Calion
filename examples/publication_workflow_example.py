#!/usr/bin/env python3
"""
Publication Workflow Example
=============================

Dieses Skript zeigt, wie du die neuen Publication-Features nutzen kannst:

1. Simulation ausführen (PF/RH/MPC über run_workflow)
2. Publication-Export (LaTeX-Tabellen, CSV, JSON)
3. Publication-Plots generieren
4. Sensitivitätsanalyse (optional)
5. Framework-Validierung (optional)

Usage:
    # Einfache Ausführung mit Default-Config
    python examples/publication_workflow_example.py

    # Mit eigenen Configs (kommasepariert)
    CONFIG_PATHS="configs/presets/quick_test.yaml" \
    SCENARIO_TITLE=Mein_Szenario \
    python examples/publication_workflow_example.py

    # Mit mehreren Configs (z.B. PF→RH-Szenario)
    CONFIG_PATHS="configs/00_base/solver.yaml,configs/03_systems/full.yaml,configs/04_scenarios/rh_q1_2023.yaml" \
    DASHBOARD=1 \
    SCENARIO_TITLE=RH_Q1_2023 \
    python examples/publication_workflow_example.py

Voraussetzungen:
    - Du musst auf dem Branch 'claude/framework-publication-plan-v0UhB' sein
    - Die EnerGIS-Konfigurationen in CONFIG_PATHS müssen gültig sein

Autor: Claude (Publication Framework)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from collections.abc import Mapping

# Füge das Projektverzeichnis zum Path hinzu

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from energis.analysis.sensitivity_runner import (
    create_publication_sensitivity_study,
    SensitivityStudyResult,
    run_full_sensitivity_study,
)
# ============================================================================

# Konfiguration

# ============================================================================

SCENARIO_TITLE = os.environ.get("SCENARIO_TITLE", "Publication_Demo")
EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", "exports/publication"))
INPUT_XLSX = os.environ.get("INPUT_XLSX", "Import_Data.xlsx")  # derzeit ungenutzt
YEAR_TARGET = int(os.environ.get("YEAR_TARGET", "2023"))       # derzeit ungenutzt

# PF/RH/MPC-Konfiguration: kommaseparierte Liste von YAML-Dateien

CONFIG_PATHS = os.environ.get(
    "CONFIG_PATHS",
    "configs/presets/quick_test.yaml"
).split(",")

# Dashboard-Export aktivieren?

USE_DASHBOARD = os.environ.get("DASHBOARD", "0") == "1"

# Was soll ausgeführt werden?

RUN_SIMULATION = True           # Simulation ausführen
RUN_PUBLICATION_EXPORT = True   # LaTeX/CSV/JSON Export
RUN_PUBLICATION_PLOTS = True    # Publication-Plots generieren
RUN_SENSITIVITY = True         # Sensitivitätsanalyse (dauert länger)
RUN_VALIDATION = True           # Framework-Validierung

# ============================================================================

# Imports

# ============================================================================

import json
import numpy as np
import pandas as pd

print(f"{'='*70}")
print(f"PUBLICATION WORKFLOW EXAMPLE")
print(f"Szenario: {SCENARIO_TITLE}")
print(f"Export-Verzeichnis: {EXPORT_DIR}")
print(f"{'='*70}\n")


# ============================================================================

# 1. SIMULATION AUSFÜHREN (PF/RH/MPC)

# ============================================================================

def _workflow_to_publication_results(workflow, base_result):
    """
    Konvertiert PF/RH/MPC-Ergebnisse in das 'results'-Format des
    Publication-Workflows:
      - summary: dict mit Sections (inkl. 'objective'-Section)
      - timeseries: Pandas DataFrame
      - design: vereinfachte Designinfos (HP + Speicher)

    """

    # 1) Zeitreihen → DataFrame
    table = base_result.table
    ts_df = pd.DataFrame(
        {col: table[col] for col in table.columns},
        index=table.index,
    )
    # zusätzlich: Modell-Zeitreihen (Entscheidungsvariablen)
    for name, series in base_result.series.items():
        ts_df[name] = series

    # 2) Summary-Abschnitte:
    summary_sections: dict[str, dict] = {}

    if hasattr(base_result, "summary") and isinstance(base_result.summary, Mapping):
        summary_sections = {
            str(sec): dict(vals) for sec, vals in base_result.summary.items()
        }

    # 'objective'-Section aus costs aufbauen/überschreiben
    objective = summary_sections.setdefault("objective", {})
    if isinstance(base_result.costs, Mapping):
        for k, v in base_result.costs.items():
            if not (isinstance(k, str) and k.startswith("objective.")):
                continue
            metric = k.split("objective.", 1)[1]  # z.B. "OBJ_value_EUR"
            objective[metric] = v

    # 3) Design-Infos (falls vorhanden)
    design = {}
    if workflow.design:
        design["heat_pumps"] = workflow.design.heat_pumps
        if workflow.design.storage:
            design["storage"] = workflow.design.storage

    results = {
        "summary": summary_sections,
        "timeseries": ts_df,
        "design": design,
    }
    return results


def run_simulation():
    """
    Führt eine Simulation über EnerGIS (PF/RH/MPC) aus und gibt die
    Ergebnisse im Publication-Format zurück.

    Intern:
      - ruft run_workflow(CONFIG_PATHS) auf
      - führt export_workflow_results() aus (Standard-Export)
      - optional: Dashboard-Export
      - baut ein 'results'-Dict + df_input für die weiteren Publication-Schritte

    """
    print("\n" + "="*70)
    print("SCHRITT 1: SIMULATION (PF/RH/MPC über run_workflow)")
    print("="*70 + "\n")

    from energis.run.rolling_horizon import run_workflow, export_workflow_results

    # 1) PF/RH/MPC-Workflow starten
    config_paths = [p.strip() for p in CONFIG_PATHS if p.strip()]
    if not config_paths:
        raise RuntimeError("Keine gültigen CONFIG_PATHS definiert (Umgebungsvariable CONFIG_PATHS).")

    print(f"[INFO] Starte EnerGIS-Workflow mit Configs:")
    for p in config_paths:
        print(f"       - {p}")

    workflow = run_workflow(config_paths)

    # Bevorzugte Ergebnisquelle für die Publikation:
    # 1. RH (Rolling Horizon), 2. MPC, 3. PF
    base_result = workflow.rh_result or workflow.mpc_result or workflow.pf_result
    if base_result is None:
        raise RuntimeError("Kein PF/RH/MPC-Ergebnis im Workflow vorhanden.")

    # 2) Standard-Export des Frameworks (Excel-Bundle, CSV, JSON, Plots)
    print("\n[INFO] Exportiere Framework-Ergebnisse (export_workflow_results)")
    fw_outdir = EXPORT_DIR / "framework"
    fw_export = export_workflow_results(workflow, outdir=str(fw_outdir))
    print(f"       - Framework-Export: {fw_export['outdir']}")

    # 3) Optional: Dashboard-Export
    if USE_DASHBOARD:
        try:
            from energis.io.notebook_helpers import save_workflow_run

            dash_dir = EXPORT_DIR / "dashboard"
            dash_path = save_workflow_run(
                workflow,
                name=SCENARIO_TITLE,
                description=f"Publication workflow: {', '.join(config_paths)}",
                config_paths=config_paths,
                save_dir=str(dash_dir),
            )
            print(f"\n[INFO] Dashboard-Export gespeichert unter:")
            print(f"       - {dash_path}")
            print("       Dashboard starten mit:  python start_dashboard.py")
        except ImportError as e:
            print(f"[WARN] Dashboard-Export nicht verfügbar: {e}")

    # 4) Publication-kompatible Struktur aus dem Workflow bauen
    results = _workflow_to_publication_results(workflow, base_result)

    # Input-Daten als DataFrame (z.B. für Sensitivität/Plots)
    table = base_result.table
    df_input = pd.DataFrame(
        {col: table[col] for col in table.columns},
        index=table.index,
    )

    print("[INFO] Simulation (PF/RH/MPC) abgeschlossen.")
    return results, df_input


# ============================================================================

# 2. PUBLICATION EXPORT

# ============================================================================

def run_publication_export(results: dict, output_dir: Path):
    """
    Exportiert die Ergebnisse für wissenschaftliche Publikationen.

    Generiert:
    - LaTeX-Tabellen (für Paper)
    - CSV-Dateien (für Analyse)
    - JSON-Dateien (für Metadaten)

    """
    print("\n" + "="*70)
    print("SCHRITT 2: PUBLICATION EXPORT")
    print("="*70 + "\n")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from energis.io.publication_exporter import (
            export_latex_tables,
            export_kpi_summary,
            export_publication_bundle,
        )

        # Export LaTeX-Tabellen
        print("[INFO] Exportiere LaTeX-Tabellen...")
        latex_files = export_latex_tables(
            outdir=str(output_dir / "latex"),
            summary_sections=results.get("summary", {}),
            table_style="booktabs",  # oder "applied_energies" für Applied Energy Journal
        )

        for name, path in latex_files.items():
            print(f"       - {name}: {path}")

        # Export KPI Summary (JSON + CSV)
        print("\n[INFO] Exportiere KPI-Summary...")
        kpi_path = export_kpi_summary(
            outdir=str(output_dir),
            summary_sections=results.get("summary", {}),
        )
        print(f"       - KPI Summary: {kpi_path}")

        # Export Publication Bundle (alles zusammen)
        print("\n[INFO] Exportiere Publication Bundle...")
        bundle_files = export_publication_bundle(
            outdir=str(output_dir / "bundle"),
            summary_sections=results.get("summary", {}),
        )
        print(f"       - Bundle erstellt in: {output_dir / 'bundle'}")

        print("\n[SUCCESS] Publication Export abgeschlossen!")

    except ImportError as e:
        print(f"[WARN] Publication Exporter nicht verfügbar: {e}")
        print("[INFO] Manueller Export als Fallback...")
        _manual_export(results, output_dir)


def _manual_export(results: dict, output_dir: Path):
    """Fallback: Manueller Export wenn Module nicht verfügbar."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON Export
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(results.get("summary", {}), f, indent=2, default=str)
    print(f"       - Summary JSON: {summary_path}")

    # CSV Export für Zeitreihen
    if "timeseries" in results:
        ts_path = output_dir / "timeseries.csv"
        df_ts = results["timeseries"]
        if isinstance(df_ts, pd.DataFrame):
            df_ts.to_csv(ts_path)
        else:
            # Fallback: falls es schon ein DataFrame war, aber anders strukturiert
            pd.DataFrame(df_ts).to_csv(ts_path)
        print(f"       - Timeseries CSV: {ts_path}")


# ============================================================================

# 3. PUBLICATION PLOTS

# ============================================================================

def run_publication_plots(results: dict, output_dir: Path):
    """
    Generiert publikationsreife Plots.

    Features:
    - Hochauflösend (300 DPI für Druck)
    - Farbblind-freundliche Farbpalette
    - Applied Energy / IEEE konforme Formatierung

    """
    print("\n" + "="*70)
    print("SCHRITT 3: PUBLICATION PLOTS")
    print("="*70 + "\n")

    output_dir = Path(output_dir) / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from energis.io.publication_plotter import (
            export_publication_plots,
            PublicationConfig,
        )
        from energis.utils.timeseries import TimeSeriesTable

        # Wende Publication-Style an
        PublicationConfig.apply_style()

        # Erstelle TimeSeriesTable aus Ergebnissen
        if "timeseries" in results:
            ts_df = results["timeseries"]
            if not isinstance(ts_df, pd.DataFrame):
                ts_df = pd.DataFrame(ts_df)

            # Konvertiere zu TimeSeriesTable Format
            columns = list(ts_df.columns)
            data = {col: ts_df[col].values.tolist() for col in columns}
            index = ts_df.index.tolist()

            table = TimeSeriesTable(
                index=index,
                columns=columns,
                data=data,
            )

            # Generiere Plots
            print("[INFO] Generiere Publication Plots...")
            generated = export_publication_plots(
                outdir=str(output_dir),
                table=table,
                series=data,
                summary_sections=results.get("summary", {}),
            )

            for name, path in generated.items():
                print(f"       - {name}: {path}")

        print("\n[SUCCESS] Publication Plots erstellt!")

    except ImportError as e:
        print(f"[WARN] Publication Plotter nicht verfügbar: {e}")
        print("[INFO] Erstelle einfache Matplotlib-Plots als Fallback...")
        _simple_plots(results, output_dir)


def _simple_plots(results: dict, output_dir: Path):
    """Fallback: Einfache Matplotlib-Plots."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if "timeseries" not in results:
            print("[WARN] Keine Zeitreihendaten für Plots verfügbar.")
            return

        ts_df = results["timeseries"]
        if not isinstance(ts_df, pd.DataFrame):
            ts_df = pd.DataFrame(ts_df)

        # Plot 1: Wärmeerzeugung
        fig, ax = plt.subplots(figsize=(10, 6))

        if "hp_production" in ts_df.columns:
            ax.fill_between(range(len(ts_df)), ts_df["hp_production"],
                           label="Wärmepumpe", alpha=0.7)
        if "gas_boiler" in ts_df.columns:
            ax.fill_between(range(len(ts_df)),
                           ts_df.get("hp_production", 0) + ts_df["gas_boiler"],
                           ts_df.get("hp_production", 0),
                           label="Gaskessel", alpha=0.7)
        if "heat_demand" in ts_df.columns:
            ax.plot(ts_df["heat_demand"], 'k--', label="Wärmebedarf", linewidth=1)

        ax.set_xlabel("Zeitschritt [h]")
        ax.set_ylabel("Leistung [MW]")
        ax.set_title("Wärmeerzeugung")
        ax.legend()
        ax.grid(True, alpha=0.3)

        plot_path = output_dir / "heat_production.png"
        plt.savefig(plot_path, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"       - heat_production: {plot_path}")

        # Plot 2: Kosten-Breakdown (Pie Chart)
        if "summary" in results and "objective" in results["summary"]:
            obj = results["summary"]["objective"]

            fig, ax = plt.subplots(figsize=(8, 8))

            labels = []
            values = []

            if "Grid_energy_cost_EUR" in obj:
                labels.append("Stromkosten")
                values.append(obj["Grid_energy_cost_EUR"])
            if "Fuel_cost_EUR" in obj:
                labels.append("Brennstoffkosten")
                values.append(obj["Fuel_cost_EUR"])

            if values:
                ax.pie(values, labels=labels, autopct='%1.1f%%')
                ax.set_title("Kostenverteilung")

                plot_path = output_dir / "cost_breakdown.png"
                plt.savefig(plot_path, dpi=300, bbox_inches="tight")
                plt.close()
                print(f"       - cost_breakdown: {plot_path}")

    except ImportError:
        print("[ERROR] Matplotlib nicht installiert. Keine Plots erstellt.")


# ============================================================================

# 4. SENSITIVITÄTSANALYSE (OPTIONAL)

# ============================================================================

def run_sensitivity_analysis(results: dict, output_dir: Path):
    """
    Führt eine vollständige Sensitivitätsanalyse durch.

    Nutzt:
      - CONFIG_PATHS als Basis-Konfigurationsdateien
      - run_full_sensitivity_study aus energis.analysis.sensitivity_runner
      - create_publication_sensitivity_study als Standard-Parameter-Set

    Generiert:
      - Tornado-Diagramme / Spider-Plots (PDF/PNG)
      - LaTeX-Tabelle
      - JSON/CSV-Summary
      - Parameter-Ranking (TXT)

    """
    print("\n" + "="*70)
    print("SCHRITT 4: SENSITIVITÄTSANALYSE")
    print("="*70 + "\n")

    outdir = Path(output_dir) / "sensitivity"
    outdir.mkdir(parents=True, exist_ok=True)

    # Basis-Configs (gleich wie für die Hauptsimulation)
    base_configs = [p.strip() for p in CONFIG_PATHS if p.strip()]
    if not base_configs:
        print("[ERROR] Keine CONFIG_PATHS für Sensitivitätsanalyse definiert.")
        print("        Setze z.B.:  CONFIG_PATHS=configs/presets/rh_full_system.yaml")
        return

    try:
        # 1) Standard-Parameterset für Publikationen
        variations = create_publication_sensitivity_study()
        print(f"[INFO] Sensitivitätsstudie mit {len(variations)} Parametern")
        print(f"       Basis-Configs:")
        for p in base_configs:
            print(f"         - {p}")
        print(f"       Output: {outdir}")

        # 2) Vollständige Studie starten
        study: SensitivityStudyResult = run_full_sensitivity_study(
            base_configs=base_configs,
            variations=variations,        # oder None, dann wird das gleiche Set benutzt
            output_dir=str(outdir),
            generate_plots=True,
            generate_latex=True,
            parallel=False,               # später ggf. auf True + n_jobs setzen
            n_jobs=-1,
        )

        # 3) Kurze Zusammenfassung in der Konsole ausgeben
        print("\n" + study.summary())
        print("\n[INFO] Generierte Sensitivitäts-Dateien:")
        for label, path in study.generated_files.items():
            print(f"       - {label}: {path}")

        print("\n[SUCCESS] Sensitivitätsanalyse abgeschlossen!")

    except ImportError as e:
        print(f"[WARN] Sensitivity Modul nicht verfügbar: {e}")
        print("[INFO] Stelle sicher, dass energis.analysis korrekt installiert ist.")
    except Exception as e:
        print(f"[ERROR] Sensitivitätsanalyse fehlgeschlagen: {e}")

# ============================================================================

# 5. FRAMEWORK-VALIDIERUNG (OPTIONAL)

# ============================================================================

def run_validation(output_dir: Path):
    """
    Führt eine Framework-Validierung durch.

    Testet das Framework gegen analytisch lösbare Testfälle.
    Wichtig für peer-reviewed Publikationen!
    """
    print("\n" + "="*70)
    print("SCHRITT 5: FRAMEWORK-VALIDIERUNG")
    print("="*70 + "\n")

    output_dir = Path(output_dir) / "validation"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from energis.validation import (
            create_standard_test_suite,
            run_validation_suite,
            generate_validation_report,
            export_validation_summary,
        )

        print("[INFO] Erstelle Standard-Testsuite...")
        test_suite = create_standard_test_suite()
        print(f"       {len(test_suite)} Testfälle definiert")

        print("\n[INFO] Für vollständige Validierung, rufe auf:")
        print("""
        from energis.validation import run_validation_suite

        # Mit deinem Workflow
        results = run_validation_suite(
            workflow_factory=my_workflow_factory,
            test_suite=test_suite
        )

        # Generiere Report
        generate_validation_report(
            results=results,
            output_dir="exports/validation"
        )
        """)

        # Export der Test-Definition
        test_def_path = output_dir / "test_suite_definition.json"
        test_definitions = [
            {
                "name": tc.name,
                "description": tc.description,
                "category": tc.category,
                "expected_results": tc.expected_results,
                "tolerance": tc.tolerance,
            }
            for tc in test_suite
        ]

        with open(test_def_path, "w") as f:
            json.dump(test_definitions, f, indent=2)

        print(f"\n[INFO] Test-Definitionen exportiert: {test_def_path}")
        print("\n[SUCCESS] Validierungs-Setup abgeschlossen!")

    except ImportError as e:
        print(f"[WARN] Validation Modul nicht verfügbar: {e}")
        print("[INFO] Stelle sicher, dass du auf dem richtigen Branch bist:")
        print("       git checkout claude/framework-publication-plan-v0UhB")


# ============================================================================

# HAUPTPROGRAMM

# ============================================================================

def main():
    """Hauptfunktion: Führt den gesamten Publication-Workflow aus."""

    print(f"\n{'#'*70}")
    print(f"# PUBLICATION WORKFLOW")
    print(f"# Szenario: {SCENARIO_TITLE}")
    print(f"{'#'*70}\n")

    # Erstelle Export-Verzeichnis
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    results = None
    df_input = None

    # 1. Simulation
    if RUN_SIMULATION:
        results, df_input = run_simulation()

        if results is None:
            print("\n[ERROR] Simulation fehlgeschlagen. Beende...")
            return

    # Wenn keine Simulation, lade Beispiel-Ergebnisse (Fallback)
    if results is None:
        print("[INFO] Keine Simulation. Verwende Demo-Ergebnisse...")
        results = {
            "summary": {
                "objective": {"OBJ_value_EUR": 1000000},
                "emissions": {"Total_CO2_t": 500},
                "design": {"HP_capacity_MW": 30},
            }
        }

    # 2. Publication Export
    if RUN_PUBLICATION_EXPORT:
        run_publication_export(results, EXPORT_DIR)

    # 3. Publication Plots
    if RUN_PUBLICATION_PLOTS:
        run_publication_plots(results, EXPORT_DIR)

    # 4. Sensitivitätsanalyse
    if RUN_SENSITIVITY:
        run_sensitivity_analysis(results, EXPORT_DIR)

    # 5. Validierung
    if RUN_VALIDATION:
        run_validation(EXPORT_DIR)

    # Zusammenfassung
    print(f"\n{'='*70}")
    print("ZUSAMMENFASSUNG")
    print("="*70)
    print(f"\nAlle Ergebnisse wurden exportiert nach: {EXPORT_DIR.absolute()}")
    print(f"\nGenerierte Dateien:")

    for item in sorted(EXPORT_DIR.rglob("*")):
        if item.is_file():
            rel_path = item.relative_to(EXPORT_DIR)
            print(f"  - {rel_path}")

    print(f"\n{'='*70}")
    print("FERTIG!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
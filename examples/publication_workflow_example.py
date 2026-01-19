#!/usr/bin/env python3
"""
Publication Workflow Example
=============================

Dieses Skript zeigt, wie du die neuen Publication-Features nutzen kannst:

1. Simulation ausführen (PF + RH)
2. Publication-Export (LaTeX-Tabellen, CSV, JSON)
3. Publication-Plots generieren
4. Sensitivitätsanalyse (optional)
5. Framework-Validierung (optional)

Usage:
    # Einfache Ausführung
    python examples/publication_workflow_example.py

    # Mit Umgebungsvariablen
    SCENARIO_TITLE=Mein_Szenario python examples/publication_workflow_example.py

Voraussetzungen:
    - Du musst auf dem Branch 'claude/framework-publication-plan-v0UhB' sein
    - Die Datei 'Import_Data.xlsx' muss vorhanden sein

Autor: Claude (Publication Framework)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Füge das Projektverzeichnis zum Path hinzu
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# Konfiguration
# ============================================================================

SCENARIO_TITLE = os.environ.get("SCENARIO_TITLE", "Publication_Demo")
EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", "exports/publication"))
INPUT_XLSX = os.environ.get("INPUT_XLSX", "Import_Data.xlsx")
YEAR_TARGET = int(os.environ.get("YEAR_TARGET", "2023"))

# Was soll ausgeführt werden?
RUN_SIMULATION = True           # Simulation ausführen
RUN_PUBLICATION_EXPORT = True   # LaTeX/CSV/JSON Export
RUN_PUBLICATION_PLOTS = True    # Publication-Plots generieren
RUN_SENSITIVITY = False         # Sensitivitätsanalyse (dauert länger)
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
# 1. SIMULATION AUSFÜHREN
# ============================================================================

def run_simulation():
    """
    Führt eine Simulation aus und gibt die Ergebnisse zurück.

    Hier wird das bestehende standalone_heat_planning_example.py Konzept verwendet.
    Du kannst dies durch deinen eigenen Simulationscode ersetzen.
    """
    print("\n" + "="*70)
    print("SCHRITT 1: SIMULATION")
    print("="*70 + "\n")

    # Import der notwendigen Module
    try:
        from pyomo.environ import (
            ConcreteModel, Var, Param, RangeSet, Constraint, Objective,
            NonNegativeReals, Binary, minimize, value as pyo_val
        )
        from pyomo.opt import SolverFactory
    except ImportError:
        print("[ERROR] Pyomo nicht installiert. Bitte 'pip install pyomo' ausführen.")
        return None, None

    # Lade Eingabedaten
    if not os.path.exists(INPUT_XLSX):
        print(f"[WARN] Input-Datei '{INPUT_XLSX}' nicht gefunden.")
        print("[INFO] Generiere synthetische Demo-Daten...")
        df_input = _generate_demo_data()
    else:
        print(f"[INFO] Lade Daten aus {INPUT_XLSX}...")
        df_input = pd.read_excel(INPUT_XLSX)
        # Vereinfachte Verarbeitung
        if "Datum" in df_input.columns:
            df_input["Datum"] = pd.to_datetime(df_input["Datum"])
            df_input = df_input.set_index("Datum")

    print(f"[INFO] {len(df_input)} Zeitschritte geladen")

    # Erstelle ein vereinfachtes Modell für die Demo
    results = _run_demo_optimization(df_input)

    return results, df_input


def _generate_demo_data(n_hours: int = 168) -> pd.DataFrame:
    """Generiert synthetische Demo-Daten für eine Woche."""
    np.random.seed(42)

    timestamps = pd.date_range("2023-01-01", periods=n_hours, freq="h")

    # Sinusförmiger Wärmebedarf (höher im Winter, Tag/Nacht-Zyklus)
    hour_of_day = np.array([t.hour for t in timestamps])
    day_cycle = 1.0 + 0.3 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
    base_demand = 50 + 20 * np.random.randn(n_hours)
    heat_demand = np.maximum(10, base_demand * day_cycle)

    # Strompreis (Day-Ahead)
    base_price = 80 + 30 * np.sin(2 * np.pi * hour_of_day / 24)
    noise = 15 * np.random.randn(n_hours)
    electricity_price = np.maximum(20, base_price + noise)

    # CO2-Intensität
    co2_intensity = 400 + 100 * np.random.randn(n_hours)
    co2_intensity = np.maximum(200, co2_intensity)

    df = pd.DataFrame({
        "strompreis_EUR_MWh": electricity_price,
        "waermebedarf_MWth": heat_demand,
        "grid_co2_kg_MWh": co2_intensity,
    }, index=timestamps)

    return df


def _run_demo_optimization(df_input: pd.DataFrame) -> dict:
    """
    Führt eine Demo-Optimierung aus.

    Dies ist eine vereinfachte Version. In deiner echten Anwendung
    würdest du hier dein vollständiges Modell verwenden.
    """
    print("[INFO] Starte Demo-Optimierung...")

    # Simuliere Ergebnisse (vereinfacht)
    n_hours = len(df_input)

    # Extrahiere Eingabedaten
    if "waermebedarf_MWth" in df_input.columns:
        heat_demand = df_input["waermebedarf_MWth"].values
    elif "Wärmebedarf MW" in df_input.columns:
        heat_demand = df_input["Wärmebedarf MW"].values
    else:
        heat_demand = 50 * np.ones(n_hours)

    if "strompreis_EUR_MWh" in df_input.columns:
        elec_price = df_input["strompreis_EUR_MWh"].values
    elif "Day_Ahead_Price €/MWh" in df_input.columns:
        elec_price = df_input["Day_Ahead_Price €/MWh"].values
    else:
        elec_price = 80 * np.ones(n_hours)

    # Simulierte Wärmeerzeugung (vereinfacht: Merit-Order-ähnlich)
    hp_production = np.minimum(heat_demand * 0.6, 30)  # Max 30 MW HP
    gas_boiler = np.maximum(0, heat_demand - hp_production)

    # Simulierte Kosten
    hp_cop = 3.5
    hp_electricity = hp_production / hp_cop
    electricity_cost = np.sum(hp_electricity * elec_price)
    gas_cost = np.sum(gas_boiler * 60)  # 60 EUR/MWh Gas

    total_cost = electricity_cost + gas_cost

    # Simulierte CO2-Emissionen
    if "grid_co2_kg_MWh" in df_input.columns:
        co2_intensity = df_input["grid_co2_kg_MWh"].values
    else:
        co2_intensity = 400 * np.ones(n_hours)

    hp_co2 = np.sum(hp_electricity * co2_intensity) / 1000  # t CO2
    gas_co2 = np.sum(gas_boiler * 0.2)  # 0.2 t CO2/MWh Gas
    total_co2 = hp_co2 + gas_co2

    # Ergebnisse strukturieren
    results = {
        "summary": {
            "objective": {
                "OBJ_value_EUR": total_cost,
                "Grid_energy_cost_EUR": electricity_cost,
                "Fuel_cost_EUR": gas_cost,
            },
            "emissions": {
                "Total_CO2_t": total_co2,
                "Grid_CO2_t": hp_co2,
                "Gas_CO2_t": gas_co2,
            },
            "design": {
                "HP_capacity_MW": 30.0,
                "Gas_boiler_capacity_MW": 50.0,
                "Storage_capacity_MWh": 100.0,
            },
            "kpi": {
                "Specific_cost_EUR_per_MWh": total_cost / np.sum(heat_demand),
                "Renewable_share_pct": 100 * np.sum(hp_production) / np.sum(heat_demand),
                "CO2_intensity_kg_per_MWh": 1000 * total_co2 / np.sum(heat_demand),
            },
        },
        "timeseries": pd.DataFrame({
            "heat_demand": heat_demand,
            "hp_production": hp_production,
            "gas_boiler": gas_boiler,
            "electricity_price": elec_price,
        }, index=df_input.index),
        "design": {
            "HP_cap": {1: 15.0, 2: 10.0, 3: 5.0},
            "storage_capacity": 100.0,
            "storage_power": 25.0,
        }
    }

    print(f"[INFO] Optimierung abgeschlossen")
    print(f"       Gesamtkosten: {total_cost:,.0f} EUR")
    print(f"       CO2-Emissionen: {total_co2:,.1f} t")

    return results


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
        results["timeseries"].to_csv(ts_path)
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
    Führt eine Sensitivitätsanalyse durch.

    Untersucht die Auswirkung von Parameteränderungen auf das Ergebnis.
    Generiert Tornado-Diagramme und LaTeX-Tabellen.
    """
    print("\n" + "="*70)
    print("SCHRITT 4: SENSITIVITÄTSANALYSE")
    print("="*70 + "\n")

    output_dir = Path(output_dir) / "sensitivity"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from energis.analysis import (
            create_publication_sensitivity_study,
            SensitivityStudyResult,
        )

        print("[INFO] Erstelle Sensitivitätsstudie...")
        print("[INFO] Dies kann einige Minuten dauern...")

        # Definiere Parameter für Sensitivitätsanalyse
        # In deiner echten Anwendung würdest du hier deine Config-Pfade angeben

        # Demo: Zeige was die Funktion erwartet
        print("\n[INFO] Für eine vollständige Sensitivitätsanalyse, rufe auf:")
        print("""
        from energis.analysis import run_full_sensitivity_study

        results = run_full_sensitivity_study(
            base_configs=["configs/base.yaml", "configs/system.yaml"],
            output_dir="exports/sensitivity",
            parameters=[
                {"path": "economics.gas_price", "variations": [-20, -10, 10, 20]},
                {"path": "economics.co2_price", "variations": [-50, -25, 25, 50]},
                {"path": "components.hp.capacity", "variations": [-30, -15, 15, 30]},
            ]
        )
        """)

        print("\n[SUCCESS] Sensitivitätsanalyse-Setup abgeschlossen!")

    except ImportError as e:
        print(f"[WARN] Sensitivity Modul nicht verfügbar: {e}")


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

    # Wenn keine Simulation, lade Beispiel-Ergebnisse
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

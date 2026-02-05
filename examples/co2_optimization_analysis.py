#!/usr/bin/env python3
"""
CO2-Auflösungsanalyse mit echtem Optimierungslauf.

Dieses Skript:
1. Führt einen Optimierungslauf mit Wärmepumpen durch
2. Extrahiert den optimierten Strombezug (P_buy)
3. Vergleicht CO2-Emissionen bei verschiedenen zeitlichen Auflösungen

Zeigt, wie sich die Wahl der zeitlichen Auflösung des Strommix-Faktors
auf die berechneten CO2-Emissionen auswirkt.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from energis.run.rolling_horizon import run_workflow
from energis.analysis import (
    analyze_co2_resolution,
    create_comparison_report,
    create_monthly_breakdown,
)


def main():
    print("=" * 70)
    print("CO2-AUFLÖSUNGSANALYSE MIT OPTIMIERTEM WÄRMEPUMPEN-BETRIEB")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # 1. Optimierungslauf durchführen
    # -------------------------------------------------------------------------
    print("\n[1] Starte Optimierungslauf...")
    print("    Konfiguration: HP_only.yaml (Wärmepumpen-System)")
    print("    Zeitraum: 1 Woche (Januar 2023)")

    config_paths = ["configs/presets/HP_only.yaml"]
    # Override to use shorter time horizon for faster testing
    overrides = {
        "scenario": {
            "horizon": {
                "type": "date_range",
                "start": "2023-01-01 00:00",
                "end": "2023-01-07 23:00"  # 1 week for quick testing
            }
        }
    }

    try:
        result = run_workflow(config_paths, overrides)
        print("    ✓ Optimierung erfolgreich abgeschlossen")
    except Exception as e:
        print(f"    ✗ Fehler bei der Optimierung: {e}")
        import traceback
        traceback.print_exc()
        return

    # -------------------------------------------------------------------------
    # 2. Ergebnisse extrahieren
    # -------------------------------------------------------------------------
    print("\n[2] Extrahiere Ergebnisse...")

    # Hole das Szenario-Ergebnis (PF oder RH)
    if hasattr(result, 'pf_result') and result.pf_result is not None:
        scenario = result.pf_result
        print("    → Verwende Perfect Foresight Ergebnis")
    elif hasattr(result, 'rh_result') and result.rh_result is not None:
        scenario = result.rh_result
        print("    → Verwende Rolling Horizon Ergebnis")
    elif hasattr(result, 'mpc_result') and result.mpc_result is not None:
        scenario = result.mpc_result
        print("    → Verwende MPC Ergebnis")
    else:
        print("    ✗ Kein gültiges Szenario-Ergebnis gefunden")
        print(f"    Verfügbare Attribute: {[a for a in dir(result) if not a.startswith('_')]}")
        return

    series = scenario.series
    table = scenario.table

    # Zeitstempel und Zeitschrittdauer
    timestamps = table.index
    # dt_h kann in config oder direkt im result sein
    if hasattr(result, 'dt_h'):
        dt_h = result.dt_h
    elif hasattr(result, 'config') and 'run' in result.config:
        dt_h = result.config['run'].get('dt_h', 1.0)
    else:
        dt_h = 1.0

    # Strombezug vom Netz (P_buy)
    p_buy_key = None
    for key in ['P_buy_MW', 'Pbuy_MW', 'P_buy', 'grid_import_MW']:
        if key in series:
            p_buy_key = key
            break

    if p_buy_key is None:
        print("    ✗ Keine Strombezugs-Zeitreihe (P_buy) gefunden")
        print(f"    Verfügbare Serien: {list(series.keys())[:20]}...")
        return

    electricity_mw = series[p_buy_key]
    print(f"    → Strombezug: {p_buy_key}")
    print(f"    → Gesamt: {sum(electricity_mw) * dt_h:.0f} MWh")

    # CO2-Faktoren
    co2_key = None
    for key in ['grid_co2_kg_MWh', 'Grid_CO2_factor_kg_MWh', 'co2_factor']:
        if key in table.data:
            co2_key = key
            break

    if co2_key is None:
        print("    ✗ Keine CO2-Faktor-Zeitreihe gefunden")
        print(f"    Verfügbare Tabellenspalten: {table.columns[:10]}...")
        return

    co2_factors = table.data[co2_key]
    print(f"    → CO2-Faktoren: {co2_key}")
    print(f"    → Bereich: {min(co2_factors):.0f} - {max(co2_factors):.0f} kg/MWh")

    # Längen angleichen (falls nötig)
    n = min(len(timestamps), len(electricity_mw), len(co2_factors))
    timestamps = list(timestamps[:n])
    electricity_mw = list(electricity_mw[:n])
    co2_factors = list(co2_factors[:n])

    print(f"    → Zeitschritte: {n}")
    print(f"    → Zeitschrittdauer: {dt_h} h")

    # -------------------------------------------------------------------------
    # 3. CO2-Auflösungsanalyse durchführen
    # -------------------------------------------------------------------------
    print("\n[3] Führe CO2-Auflösungsanalyse durch...")

    analysis = analyze_co2_resolution(
        timestamps=timestamps,
        electricity_mw=electricity_mw,
        grid_co2_kg_mwh=co2_factors,
        dt_h=dt_h,
    )

    # -------------------------------------------------------------------------
    # 4. Ergebnisse ausgeben
    # -------------------------------------------------------------------------
    print("\n" + create_comparison_report(analysis))

    # Monatliche Aufschlüsselung
    print("\n\nMONATLICHE AUFSCHLÜSSELUNG:")
    print("-" * 70)
    monthly_df = create_monthly_breakdown(analysis)
    print(monthly_df.to_string(index=False))

    # -------------------------------------------------------------------------
    # 5. Vergleich mit Optimierungs-Ergebnis
    # -------------------------------------------------------------------------
    print("\n\n" + "=" * 70)
    print("VERGLEICH MIT OPTIMIERUNGS-ERGEBNIS")
    print("=" * 70)

    costs = scenario.costs
    if 'CO2_grid_to_elec_kg' in costs:
        opt_co2_kg = costs['CO2_grid_to_elec_kg']
        print(f"\nCO2 aus Optimierung (stündlich):     {opt_co2_kg / 1000:>12,.1f} t")
        print(f"CO2 aus Analyse (stündlich):         {analysis.scenarios['hourly'].total_co2_t:>12,.1f} t")
        diff = abs(opt_co2_kg / 1000 - analysis.scenarios['hourly'].total_co2_t)
        print(f"Differenz:                           {diff:>12,.1f} t")

    if 'co2_kg_total' in costs:
        print(f"\nGesamte CO2-Emissionen (inkl. Brennstoffe): {costs['co2_kg_total'] / 1000:,.1f} t")

    # -------------------------------------------------------------------------
    # 6. Optional: Export
    # -------------------------------------------------------------------------
    export = False
    if export:
        outdir = Path("results/co2_analysis")
        outdir.mkdir(parents=True, exist_ok=True)

        analysis.summary_table().to_csv(outdir / "co2_resolution_comparison.csv", index=False)
        monthly_df.to_csv(outdir / "co2_monthly_breakdown.csv", index=False)
        print(f"\n→ Ergebnisse exportiert nach: {outdir}")


if __name__ == "__main__":
    main()

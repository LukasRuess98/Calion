#!/usr/bin/env python3
"""
Beispiel: CO2-Auflösungsanalyse mit echten Daten.

Dieses Skript lädt Daten aus einer Excel-Datei und führt die
CO2-Auflösungsanalyse durch.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from calion.analysis import (
    analyze_co2_resolution,
    create_comparison_report,
    create_monthly_breakdown,
)


def load_data_from_excel(filepath: str) -> tuple:
    """
    Lädt Daten aus Excel-Datei.

    Erwartet Spalten für:
    - Zeitstempel
    - Stromverbrauch (MW oder MWh)
    - CO2-Faktor (kg/MWh)
    """
    print(f"Lade Daten aus: {filepath}")

    df = pd.read_excel(filepath)

    print(f"\nVerfügbare Spalten:")
    for i, col in enumerate(df.columns):
        print(f"  {i}: {col}")

    # Versuche automatisch die richtigen Spalten zu finden
    time_col = None
    elec_col = None
    heat_col = None
    co2_col = None

    for col in df.columns:
        col_lower = col.lower()
        if any(x in col_lower for x in ['time', 'zeit', 'datum', 'date', 'timestamp']):
            time_col = col
        elif any(x in col_lower for x in ['p_buy', 'pbuy', 'strom', 'elec', 'power', 'load']):
            elec_col = col
        elif any(x in col_lower for x in ['wärme', 'waerme', 'heat', 'demand', 'bedarf']):
            heat_col = col
        elif any(x in col_lower for x in ['co2', 'emission', 'carbon']):
            co2_col = col

    print(f"\nAutomatisch erkannte Spalten:")
    print(f"  Zeit: {time_col}")
    print(f"  Strom: {elec_col}")
    print(f"  Wärme: {heat_col}")
    print(f"  CO2: {co2_col}")

    return df, time_col, elec_col, heat_col, co2_col


def main(filepath: str = None):
    # Pfad aus Argument oder Standard-Pfad
    if filepath:
        data_path = filepath
    else:
        data_path = "data/stadtbach/Import_Data.xlsx"

    # Prüfen ob Datei existiert
    if not Path(data_path).exists():
        # Versuche alternatives Verzeichnis
        alt_paths = [
            "Import_Data.xlsx",
            "data/Import_Data.xlsx",
            "../data/stadtbach/Import_Data.xlsx",
        ]
        for alt in alt_paths:
            if Path(alt).exists():
                data_path = alt
                break
        else:
            print(f"FEHLER: Datei nicht gefunden: {data_path}")
            print("\nBitte geben Sie den korrekten Pfad zu Ihrer Excel-Datei an:")
            print("  python examples/co2_real_data_example.py PFAD/ZUR/DATEI.xlsx")
            return

    # Daten laden
    df, time_col, elec_col, heat_col, co2_col = load_data_from_excel(data_path)

    if time_col is None or co2_col is None:
        print("\n" + "=" * 60)
        print("FEHLER: Zeit- oder CO2-Spalte nicht gefunden")
        print("=" * 60)
        return

    if elec_col is None and heat_col is None:
        print("\n" + "=" * 60)
        print("FEHLER: Weder Strom- noch Wärmespalte gefunden")
        print("=" * 60)
        return

    # Daten extrahieren
    df[time_col] = pd.to_datetime(df[time_col])
    timestamps = df[time_col].tolist()
    co2_factors = df[co2_col].tolist()

    # Stromverbrauch: direkt oder aus Wärmebedarf berechnet
    if elec_col is not None:
        electricity_mw = df[elec_col].tolist()
        print("\n→ Verwende direkten Stromverbrauch")
    else:
        # Berechne Stromverbrauch aus Wärmebedarf mit Wärmepumpe (COP = 3.0)
        COP = 3.0
        heat_demand = df[heat_col].tolist()
        electricity_mw = [q / COP for q in heat_demand]
        print(f"\n→ Berechne Stromverbrauch aus Wärmebedarf (Wärmepumpe, COP={COP})")
        print(f"  Wärmebedarf: {sum(heat_demand):.0f} MWh/a")
        print(f"  → Stromverbrauch: {sum(electricity_mw):.0f} MWh/a")

    # Zeitschrittdauer ermitteln
    if len(timestamps) > 1:
        dt = timestamps[1] - timestamps[0]
        dt_h = dt.total_seconds() / 3600
    else:
        dt_h = 1.0

    print(f"\nDaten geladen:")
    print(f"  Zeitschritte: {len(timestamps)}")
    print(f"  Zeitschrittdauer: {dt_h} h")
    print(f"  Zeitraum: {timestamps[0]} bis {timestamps[-1]}")
    print(f"  Stromverbrauch: {sum(electricity_mw) * dt_h:.0f} MWh gesamt")
    print(f"  CO2-Faktor: {min(co2_factors):.0f} - {max(co2_factors):.0f} kg/MWh")

    # Analyse durchführen
    print("\n" + "=" * 70)
    print("STARTE CO2-AUFLÖSUNGSANALYSE")
    print("=" * 70)

    analysis = analyze_co2_resolution(
        timestamps=timestamps,
        electricity_mw=electricity_mw,
        grid_co2_kg_mwh=co2_factors,
        dt_h=dt_h,
    )

    # Ergebnisse ausgeben
    print(create_comparison_report(analysis))

    # Monatliche Aufschlüsselung
    print("\n\nMONATLICHE AUFSCHLÜSSELUNG:")
    print("-" * 70)
    monthly_df = create_monthly_breakdown(analysis)
    print(monthly_df.to_string(index=False))

    # Optional: Export als CSV
    # analysis.summary_table().to_csv("co2_vergleich.csv", index=False)
    # monthly_df.to_csv("co2_monatlich.csv", index=False)
    # print("\nErgebnisse exportiert nach co2_vergleich.csv und co2_monatlich.csv")


if __name__ == "__main__":
    import sys
    filepath = sys.argv[1] if len(sys.argv) > 1 else None
    main(filepath)

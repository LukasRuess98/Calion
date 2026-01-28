#!/usr/bin/env python3
"""
Beispiel: CO2-Emissionsanalyse mit verschiedenen zeitlichen Auflösungen.

Dieses Skript demonstriert, wie die Wahl der zeitlichen Auflösung des
Strommix-Faktors die berechneten CO2-Emissionen beeinflusst.

Szenarien:
- Bilanziell (jährlicher Durchschnitt): 1 Faktor
- Monatlich: 12 Faktoren
- Täglich: 365 Faktoren
- Stündlich: 8.760 Faktoren
- 15-Minuten: 35.040 Faktoren

Erkenntnis: Die Korrelation zwischen Stromverbrauch und aktuellem
Strommix-Faktor bestimmt, ob bilanzielle Betrachtungen über- oder
unterschätzen.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import math

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from energis.analysis import (
    analyze_co2_resolution,
    create_comparison_report,
    create_monthly_breakdown,
)


def generate_synthetic_data(
    year: int = 2023,
    dt_h: float = 1.0,
    base_load_mw: float = 5.0,
    heating_amplitude_mw: float = 10.0,
    co2_base_kg_mwh: float = 400.0,
    co2_amplitude_kg_mwh: float = 200.0,
) -> tuple[list[datetime], list[float], list[float]]:
    """
    Generate synthetic data for demonstration.

    Creates realistic patterns:
    - Electricity consumption: Higher in winter (heating), lower in summer
    - CO2 factors: Lower during day (solar), higher at night; lower in summer

    Parameters
    ----------
    year : int
        Year for timestamps
    dt_h : float
        Timestep in hours (1.0 = hourly, 0.25 = 15-min)
    base_load_mw : float
        Base electrical load [MW]
    heating_amplitude_mw : float
        Seasonal heating amplitude [MW]
    co2_base_kg_mwh : float
        Base CO2 factor [kg/MWh]
    co2_amplitude_kg_mwh : float
        CO2 factor variation amplitude [kg/MWh]

    Returns
    -------
    timestamps, electricity_mw, co2_factors
    """
    n_steps = int(8760 / dt_h)
    timestamps = []
    electricity_mw = []
    co2_factors = []

    start = datetime(year, 1, 1)

    for i in range(n_steps):
        t = start + timedelta(hours=i * dt_h)
        timestamps.append(t)

        # Day of year (0-365)
        doy = t.timetuple().tm_yday
        # Hour of day (0-24)
        hour = t.hour + t.minute / 60

        # Seasonal component (max in winter, min in summer)
        seasonal = math.cos(2 * math.pi * (doy - 15) / 365)  # Peak around Jan 15

        # Daily component
        daily = math.cos(2 * math.pi * (hour - 14) / 24)  # Peak around 14:00

        # Electricity consumption (Wärmepumpe/P2H)
        # Higher in winter, slight daily pattern (more during day)
        elec = base_load_mw + heating_amplitude_mw * (0.5 + 0.5 * seasonal) * (0.8 + 0.2 * daily)
        elec = max(0, elec + np.random.normal(0, 0.5))  # Add noise
        electricity_mw.append(elec)

        # CO2 factor
        # Lower in summer (more solar), lower during day (solar peak)
        # Inverse correlation with typical PV production
        co2 = co2_base_kg_mwh + co2_amplitude_kg_mwh * (
            0.3 * seasonal  # Seasonal: higher in winter
            - 0.4 * max(0, -daily) * (1 - 0.3 * seasonal)  # Daily: lower at noon, esp. in summer
        )
        co2 = max(50, co2 + np.random.normal(0, 20))  # Add noise, min 50
        co2_factors.append(co2)

    return timestamps, electricity_mw, co2_factors


def main():
    print("\n" + "=" * 70)
    print("CO2-EMISSIONSANALYSE: EINFLUSS DER ZEITLICHEN AUFLÖSUNG")
    print("=" * 70 + "\n")

    # --- Szenario 1: Stündliche Daten ---
    print("Generiere synthetische Daten (stündlich, 1 Jahr)...")
    timestamps, elec_mw, co2_factors = generate_synthetic_data(dt_h=1.0)

    print(f"  - {len(timestamps)} Zeitschritte")
    print(f"  - Stromverbrauch: {sum(elec_mw):.0f} MWh/a")
    print(f"  - CO2-Faktor Bereich: {min(co2_factors):.0f} - {max(co2_factors):.0f} kg/MWh")
    print()

    # Analyse durchführen
    analysis = analyze_co2_resolution(
        timestamps=timestamps,
        electricity_mw=elec_mw,
        grid_co2_kg_mwh=co2_factors,
        dt_h=1.0,
    )

    # Report ausgeben
    print(create_comparison_report(analysis))

    # --- Monatliche Aufschlüsselung ---
    print("\n\nMONATLICHE AUFSCHLÜSSELUNG:")
    print("-" * 70)
    monthly_df = create_monthly_breakdown(analysis)
    print(monthly_df.to_string(index=False))

    # --- Szenario 2: 15-Minuten Daten ---
    print("\n\n" + "=" * 70)
    print("SZENARIO: 15-MINUTEN AUFLÖSUNG")
    print("=" * 70 + "\n")

    print("Generiere 15-Minuten Daten (35.040 Zeitschritte)...")
    ts_15, elec_15, co2_15 = generate_synthetic_data(dt_h=0.25)

    analysis_15 = analyze_co2_resolution(
        timestamps=ts_15,
        electricity_mw=elec_15,
        grid_co2_kg_mwh=co2_15,
        dt_h=0.25,
    )

    print(create_comparison_report(analysis_15))

    # --- Zusammenfassung ---
    print("\n\n" + "=" * 70)
    print("ZUSAMMENFASSUNG DER ERKENNTNISSE")
    print("=" * 70)
    print("""
    1. BILANZIELLE vs. ZEITAUFGELÖSTE BETRACHTUNG:
       - Bei jährlicher Bilanzierung wird ein Durchschnitts-CO2-Faktor verwendet
       - Zeitaufgelöste Betrachtung erfasst Korrelationen zwischen Verbrauch und Strommix

    2. TYPISCHE EFFEKTE BEI WÄRMEPUMPEN:
       - Heizlast ist hoch im Winter → CO2-Faktor ist hoch (wenig Solar/Wind)
       - Heizlast ist nachts höher → CO2-Faktor ist nachts höher
       → Bilanzielle Betrachtung UNTERSCHÄTZT oft die realen Emissionen

    3. TYPISCHE EFFEKTE BEI PV-GEKOPPELTEN SYSTEMEN:
       - Stromverbrauch folgt PV-Produktion → niedriger CO2-Faktor
       → Bilanzielle Betrachtung ÜBERSCHÄTZT die realen Emissionen

    4. EMPFEHLUNG:
       - Für genaue CO2-Bilanzierung mindestens stündliche Auflösung verwenden
       - 15-min Auflösung für Flexibilitätsanalysen und Lastmanagement
       - Monatliche Auflösung als Kompromiss für schnelle Überschlagsrechnungen
    """)


if __name__ == "__main__":
    main()

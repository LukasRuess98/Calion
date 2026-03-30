#!/usr/bin/env python3
"""
Generate synthetic demand data for Stadtbach network testing.

This creates realistic demand profiles based on:
- Network size (12 nodes, 13.4 km)
- Typical German district heating demand patterns
- Stadtbach capacity (total ~320 MW available)

ASSUMPTIONS (marked with ⚠️):
- ⚠️ Peak demand: 80 MW (realistic for 13.4 km network)
- ⚠️ Base load: 30 MW (typical for DH networks)
- ⚠️ Daily pattern: Peak morning/evening, low at night
- ⚠️ Weekly pattern: Lower on weekends
- ⚠️ Electricity price: German day-ahead 2023 average pattern
- ⚠️ WRG temperatures: 280-290 K (typical industrial waste heat)
- ⚠️ Outdoor temp: German winter average (5-10°C)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

def create_stadtbach_synthetic_data(output_file='data/stadtbach_synthetic_2023_1week.csv'):
    """Create 1 week of synthetic data for Stadtbach testing."""

    print("🏭 STADTBACH SYNTHETIC DATA GENERATOR")
    print("=" * 70)
    print("\n⚠️  ACHTUNG: Synthetische Daten für Testing!")
    print("   Für Production: Echte Daten verwenden (siehe STADTBACH_REAL_DATA_OPTIMIZATION.md)")
    print("\n" + "=" * 70)

    # Time range: 1 week for quick testing
    start = datetime(2023, 1, 1)
    periods = 168  # 1 week, hourly
    timestamps = pd.date_range(start, periods=periods, freq='h')

    # ==============================================
    # HEAT DEMAND (waermebedarf_MWth)
    # ==============================================
    print("\n📊 Generiere Wärmebedarf...")
    print("   ⚠️  Annahme: Peak 80 MW, Base 30 MW")
    print("      (Realistisch für 13.4 km Netz mit ~320 MW Kapazität)")

    # Base pattern
    base_load = 30  # MW
    peak_load = 80  # MW

    # Daily pattern (2 peaks: morning & evening)
    hour_of_day = timestamps.hour
    daily_pattern = (
        0.6 +  # Base
        0.3 * np.sin((hour_of_day - 6) * np.pi / 12) +  # Morning peak
        0.1 * np.sin((hour_of_day - 18) * np.pi / 12)   # Evening peak
    )
    daily_pattern = np.maximum(daily_pattern, 0.5)  # Min 50% load

    # Weekly pattern (lower on weekends)
    day_of_week = timestamps.dayofweek
    weekly_pattern = np.where(day_of_week < 5, 1.0, 0.8)  # 80% on weekends

    # Random variation (±10%)
    np.random.seed(42)  # Reproducible
    random_variation = 1 + 0.1 * np.random.randn(len(timestamps))

    # Combine patterns
    demand = base_load + (peak_load - base_load) * daily_pattern.values * weekly_pattern * random_variation
    demand = np.clip(demand, 25, 85)  # Ensure reasonable bounds

    print(f"   ✓ Min: {np.min(demand):.1f} MW, Max: {np.max(demand):.1f} MW, Avg: {np.mean(demand):.1f} MW")

    # ==============================================
    # ELECTRICITY PRICES (strompreis_EUR_MWh)
    # ==============================================
    print("\n💰 Generiere Strompreise...")
    print("   ⚠️  Annahme: 60-120 EUR/MWh (2023 deutscher Durchschnitt)")

    # Day-ahead pattern (high during day, low at night)
    price_base = 80  # EUR/MWh
    price_amplitude = 30
    hour_factor = np.sin((hour_of_day.values - 6) * np.pi / 12)
    prices = price_base + price_amplitude * hour_factor
    prices = np.clip(prices, 60, 120)

    print(f"   ✓ Min: {np.min(prices):.1f} EUR/MWh, Max: {np.max(prices):.1f} EUR/MWh")

    # ==============================================
    # WRG TEMPERATURES (Waste Heat Recovery)
    # ==============================================
    print("\n🌡️  Generiere WRG-Temperaturen...")
    print("   ⚠️  Annahme: 4 WRG-Quellen, 280-290 K")
    print("      (Typisch für industrielle Abwärme)")

    # 4 WRG sources with slightly different temps
    wrg_base_temps = [285, 288, 283, 287]  # Kelvin
    wrg_capacities = [5.0, 3.5, 4.2, 3.8]  # MW (from stadtbach.system.yaml)

    wrg_data = {}
    for i, (base_temp, capacity) in enumerate(zip(wrg_base_temps, wrg_capacities), 1):
        # Small variation ±2K
        variation = 2 * np.random.randn(len(timestamps))
        temps = base_temp + variation
        temps = np.clip(temps, 278, 295)  # Reasonable bounds

        wrg_data[f'WRG{i}_T_K'] = temps
        wrg_data[f'WRG{i}_Q_cap'] = capacity  # Constant capacity

    print(f"   ✓ WRG1-4 Temperaturen: {wrg_base_temps} K (±2K Variation)")
    print(f"   ✓ WRG1-4 Kapazitäten: {wrg_capacities} MW")

    # ==============================================
    # OUTDOOR TEMPERATURE
    # ==============================================
    print("\n🌡️  Generiere Außentemperatur...")
    print("   ⚠️  Annahme: 5-10°C (typischer deutscher Winter)")

    # Winter pattern (slight warming during day)
    outdoor_base = 7.0  # °C
    outdoor_amplitude = 3.0
    outdoor_temp = outdoor_base + outdoor_amplitude * np.sin((hour_of_day.values - 12) * np.pi / 12)
    outdoor_temp += 0.5 * np.random.randn(len(timestamps))  # Random variation
    outdoor_temp = np.clip(outdoor_temp, 3, 12)

    print(f"   ✓ Min: {np.min(outdoor_temp):.1f}°C, Max: {np.max(outdoor_temp):.1f}°C")

    # Ground temperature (constant)
    ground_temp = 10.0  # °C (typical for Germany)

    # ==============================================
    # GRID CO2 INTENSITY
    # ==============================================
    print("\n🌍 Generiere Grid-CO2-Intensität...")
    print("   ⚠️  Annahme: 350-450 kg/MWh (2023 deutscher Strommix)")

    # Lower during day (more renewables), higher at night
    co2_base = 400
    co2_amplitude = 40
    grid_co2 = co2_base - co2_amplitude * np.sin((hour_of_day.values - 12) * np.pi / 12)
    grid_co2 = np.clip(grid_co2, 350, 450)

    print(f"   ✓ Min: {np.min(grid_co2):.0f} kg/MWh, Max: {np.max(grid_co2):.0f} kg/MWh")

    # ==============================================
    # COMBINE TO DATAFRAME
    # ==============================================
    data = pd.DataFrame({
        'waermebedarf_MWth': demand,
        'strompreis_EUR_MWh': prices,
        'grid_co2_kg_MWh': grid_co2,
        'T_outdoor': outdoor_temp,
        'T_ground': ground_temp,
        **wrg_data
    }, index=timestamps)

    # ==============================================
    # EXPORT
    # ==============================================
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n💾 Exportiere nach: {output_path}")

    # Export main CSV
    data.to_csv(output_path, index=True)

    # Export metadata as separate file
    metadata_path = output_path.parent / (output_path.stem + '_metadata.txt')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("STADTBACH SYNTHETIC TEST DATA - METADATA\n")
        f.write("=" * 70 + "\n\n")

        f.write("⚠️  WARNING: SYNTHETIC DATA FOR TESTING ONLY!\n")
        f.write("For production use real data (see STADTBACH_REAL_DATA_OPTIMIZATION.md)\n\n")

        f.write("GENERAL INFO:\n")
        f.write("-" * 70 + "\n")
        f.write(f"Type:              SYNTHETIC TEST DATA\n")
        f.write(f"Start Date:        {timestamps[0]}\n")
        f.write(f"End Date:          {timestamps[-1]}\n")
        f.write(f"Timesteps:         {len(timestamps)}\n")
        f.write(f"Resolution:        1 hour\n")
        f.write(f"Peak Demand:       {np.max(demand):.1f} MW\n")
        f.write(f"Avg Demand:        {np.mean(demand):.1f} MW\n")
        f.write(f"Total Heat:        {np.sum(demand):.1f} MWh\n")
        f.write(f"Network Length:    13.4 km\n")
        f.write(f"Nodes:             12\n")
        f.write(f"Pipes:             11\n\n")

        f.write("ASSUMPTIONS:\n")
        f.write("-" * 70 + "\n")
        assumptions = [
            ('Peak Demand', '80 MW', 'Realistic for 13.4 km network with 320 MW capacity'),
            ('Base Load', '30 MW', 'Typical base load for DH networks'),
            ('Electricity Price', '60-120 EUR/MWh', 'German 2023 average day-ahead prices'),
            ('WRG Temperatures', '280-290 K', 'Typical industrial waste heat'),
            ('WRG Capacities', '3.5-5.0 MW', 'From stadtbach.system.yaml configuration'),
            ('Outdoor Temp', '5-10°C (winter)', 'German winter average'),
            ('Ground Temp', '10°C constant', 'Typical soil temperature'),
            ('Grid CO2', '350-450 kg/MWh', 'German 2023 grid mix average'),
            ('Daily Pattern', '2 peaks', 'Morning and evening residential heating'),
            ('Weekly Pattern', '80% on weekends', 'Reduced weekend demand'),
        ]
        for name, value, rationale in assumptions:
            f.write(f"{name:20s}: {value:20s} ({rationale})\n")

    print(f"✅ Export erfolgreich!")
    print(f"\n📊 Zusammenfassung:")
    print(f"   Zeitraum:     {timestamps[0]} bis {timestamps[-1]}")
    print(f"   Zeitschritte: {len(timestamps)} (1h Auflösung)")
    print(f"   Dateigröße:   ~{output_path.stat().st_size / 1024:.1f} KB")

    print(f"\n🎯 Verwendung:")
    print(f"   python -m calion.run \\")
    print(f"     configs/base.yaml \\")
    print(f"     configs/tech_catalog.yaml \\")
    print(f"     configs/scenarios/stadtbach_1week.scenario.yaml")

    print(f"\n⚠️  WICHTIG: Dies sind synthetische Daten für Testing!")
    print(f"   Für Production echte Daten verwenden:")
    print(f"   → docs/STADTBACH_REAL_DATA_OPTIMIZATION.md")

    return data

if __name__ == '__main__':
    data = create_stadtbach_synthetic_data()

    print("\n" + "=" * 70)
    print("✅ FERTIG!")
    print("=" * 70)

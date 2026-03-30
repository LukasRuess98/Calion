"""
CO2 Emissions Resolution Analysis Module.

This module analyzes how different temporal resolutions of electricity mix factors
affect the calculated CO2 emissions of electrified heating systems.

Scenarios compared:
1. Annual average (bilanzielle Betrachtung) - 1 factor for entire year
2. Monthly averages - 12 factors
3. Daily averages - 365 factors
4. Hourly resolution - 8,760 factors (or as provided)
5. Quarter-hourly resolution - 35,040 factors (if available)

The key insight is that using higher temporal resolutions captures correlations
between electricity consumption patterns and grid CO2 intensity variations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import math

import pandas as pd
import numpy as np


@dataclass
class ResolutionScenario:
    """Results for a single resolution scenario."""

    name: str
    resolution: str  # 'annual', 'monthly', 'daily', 'hourly', '15min'
    total_co2_kg: float
    total_electricity_mwh: float
    co2_intensity_kg_mwh: float  # Effective CO2 intensity
    factors_used: int  # Number of distinct factors used
    timeseries_co2_kg: Optional[List[float]] = None

    @property
    def total_co2_t(self) -> float:
        """Total CO2 in tonnes."""
        return self.total_co2_kg / 1000.0


@dataclass
class CO2ResolutionAnalysis:
    """
    Complete CO2 resolution analysis results.

    Attributes
    ----------
    scenarios : Dict[str, ResolutionScenario]
        Results for each resolution scenario
    reference_resolution : str
        The resolution used as reference (highest available)
    timestamps : List[datetime]
        Original timestamps
    electricity_mwh : List[float]
        Electricity consumption per timestep [MWh]
    grid_co2_factors : List[float]
        Original CO2 factors [kg/MWh]
    dt_h : float
        Timestep duration [hours]
    """

    scenarios: Dict[str, ResolutionScenario]
    reference_resolution: str
    timestamps: List[datetime]
    electricity_mwh: List[float]
    grid_co2_factors: List[float]
    dt_h: float

    def get_deviation_percent(self, scenario_name: str) -> float:
        """Get deviation from reference scenario in percent."""
        if scenario_name not in self.scenarios:
            return 0.0
        ref = self.scenarios[self.reference_resolution]
        scen = self.scenarios[scenario_name]
        if ref.total_co2_kg == 0:
            return 0.0
        return (scen.total_co2_kg - ref.total_co2_kg) / ref.total_co2_kg * 100.0

    def summary_table(self) -> pd.DataFrame:
        """Create summary DataFrame."""
        rows = []
        ref_co2 = self.scenarios[self.reference_resolution].total_co2_kg

        for name, scen in self.scenarios.items():
            deviation = (scen.total_co2_kg - ref_co2) / ref_co2 * 100 if ref_co2 > 0 else 0
            rows.append({
                'Auflösung': scen.name,
                'Faktoren': scen.factors_used,
                'CO2 [t]': scen.total_co2_t,
                'CO2-Intensität [kg/MWh]': scen.co2_intensity_kg_mwh,
                'Abweichung [%]': deviation,
                'Strom [MWh]': scen.total_electricity_mwh,
            })

        df = pd.DataFrame(rows)
        # Sort by number of factors (finest resolution last)
        df = df.sort_values('Faktoren', ascending=True)
        return df


def analyze_co2_resolution(
    timestamps: List[datetime],
    electricity_mw: List[float],
    grid_co2_kg_mwh: List[float],
    dt_h: float = 1.0,
) -> CO2ResolutionAnalysis:
    """
    Analyze CO2 emissions with different temporal resolutions of grid mix factors.

    Parameters
    ----------
    timestamps : List[datetime]
        Timestamps for each data point
    electricity_mw : List[float]
        Electricity consumption [MW] for each timestep
    grid_co2_kg_mwh : List[float]
        Grid CO2 emission factors [kg CO2/MWh] for each timestep
    dt_h : float
        Duration of each timestep in hours

    Returns
    -------
    CO2ResolutionAnalysis
        Complete analysis results with all scenarios
    """
    n = len(timestamps)
    if n == 0:
        raise ValueError("No data provided")

    if len(electricity_mw) != n or len(grid_co2_kg_mwh) != n:
        raise ValueError("All input lists must have the same length")

    # Convert to MWh per timestep
    electricity_mwh = [p * dt_h for p in electricity_mw]
    total_elec_mwh = sum(electricity_mwh)

    # Create DataFrame for easier aggregation
    df = pd.DataFrame({
        'timestamp': timestamps,
        'elec_mwh': electricity_mwh,
        'co2_factor': grid_co2_kg_mwh,
    })
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    scenarios: Dict[str, ResolutionScenario] = {}

    # Determine reference resolution based on timestep
    if dt_h <= 0.25:
        reference_resolution = '15min'
    elif dt_h <= 1.0:
        reference_resolution = 'hourly'
    else:
        reference_resolution = 'daily'

    # 1. Annual average (bilanzielle Betrachtung)
    annual_avg_factor = sum(grid_co2_kg_mwh) / n
    annual_co2_kg = sum(e * annual_avg_factor for e in electricity_mwh)
    scenarios['annual'] = ResolutionScenario(
        name='Jährlicher Durchschnitt (bilanziell)',
        resolution='annual',
        total_co2_kg=annual_co2_kg,
        total_electricity_mwh=total_elec_mwh,
        co2_intensity_kg_mwh=annual_co2_kg / total_elec_mwh if total_elec_mwh > 0 else 0,
        factors_used=1,
        timeseries_co2_kg=[e * annual_avg_factor for e in electricity_mwh],
    )

    # 2. Monthly averages
    monthly_factors = df['co2_factor'].resample('ME').mean()
    monthly_co2_ts = []
    for ts, row in df.iterrows():
        month_key = ts.to_period('M').to_timestamp() + pd.offsets.MonthEnd(0)
        factor = monthly_factors.get(month_key, annual_avg_factor)
        monthly_co2_ts.append(row['elec_mwh'] * factor)

    monthly_co2_kg = sum(monthly_co2_ts)
    scenarios['monthly'] = ResolutionScenario(
        name='Monatliche Auflösung',
        resolution='monthly',
        total_co2_kg=monthly_co2_kg,
        total_electricity_mwh=total_elec_mwh,
        co2_intensity_kg_mwh=monthly_co2_kg / total_elec_mwh if total_elec_mwh > 0 else 0,
        factors_used=min(12, len(monthly_factors)),
        timeseries_co2_kg=monthly_co2_ts,
    )

    # 3. Daily averages
    daily_factors = df['co2_factor'].resample('D').mean()
    daily_co2_ts = []
    for ts, row in df.iterrows():
        day_key = ts.normalize()
        factor = daily_factors.get(day_key, annual_avg_factor)
        daily_co2_ts.append(row['elec_mwh'] * factor)

    daily_co2_kg = sum(daily_co2_ts)
    scenarios['daily'] = ResolutionScenario(
        name='Tägliche Auflösung',
        resolution='daily',
        total_co2_kg=daily_co2_kg,
        total_electricity_mwh=total_elec_mwh,
        co2_intensity_kg_mwh=daily_co2_kg / total_elec_mwh if total_elec_mwh > 0 else 0,
        factors_used=min(365, len(daily_factors)),
        timeseries_co2_kg=daily_co2_ts,
    )

    # 4. Hourly resolution (original or aggregated)
    if dt_h <= 1.0:
        # Original data is hourly or finer - use original factors
        hourly_co2_ts = [e * f for e, f in zip(electricity_mwh, grid_co2_kg_mwh)]
        hourly_co2_kg = sum(hourly_co2_ts)
        scenarios['hourly'] = ResolutionScenario(
            name='Stündliche Auflösung',
            resolution='hourly',
            total_co2_kg=hourly_co2_kg,
            total_electricity_mwh=total_elec_mwh,
            co2_intensity_kg_mwh=hourly_co2_kg / total_elec_mwh if total_elec_mwh > 0 else 0,
            factors_used=n if dt_h == 1.0 else n // int(1.0 / dt_h),
            timeseries_co2_kg=hourly_co2_ts,
        )
    else:
        # Coarser than hourly - aggregate to hourly
        hourly_factors = df['co2_factor'].resample('h').mean()
        hourly_elec = df['elec_mwh'].resample('h').sum()
        hourly_co2_kg = (hourly_factors * hourly_elec).sum()
        scenarios['hourly'] = ResolutionScenario(
            name='Stündliche Auflösung',
            resolution='hourly',
            total_co2_kg=hourly_co2_kg,
            total_electricity_mwh=total_elec_mwh,
            co2_intensity_kg_mwh=hourly_co2_kg / total_elec_mwh if total_elec_mwh > 0 else 0,
            factors_used=len(hourly_factors),
        )

    # 5. Quarter-hourly (15min) resolution - only if data supports it
    if dt_h <= 0.25:
        qh_co2_ts = [e * f for e, f in zip(electricity_mwh, grid_co2_kg_mwh)]
        qh_co2_kg = sum(qh_co2_ts)
        scenarios['15min'] = ResolutionScenario(
            name='15-Minuten Auflösung',
            resolution='15min',
            total_co2_kg=qh_co2_kg,
            total_electricity_mwh=total_elec_mwh,
            co2_intensity_kg_mwh=qh_co2_kg / total_elec_mwh if total_elec_mwh > 0 else 0,
            factors_used=n,
            timeseries_co2_kg=qh_co2_ts,
        )

    return CO2ResolutionAnalysis(
        scenarios=scenarios,
        reference_resolution=reference_resolution,
        timestamps=timestamps,
        electricity_mwh=electricity_mwh,
        grid_co2_factors=grid_co2_kg_mwh,
        dt_h=dt_h,
    )


def analyze_from_result(result: Any, dt_h: float = 1.0) -> Optional[CO2ResolutionAnalysis]:
    """
    Analyze CO2 resolution from a workflow result object.

    Parameters
    ----------
    result : Any
        Workflow result with series data
    dt_h : float
        Timestep duration in hours

    Returns
    -------
    Optional[CO2ResolutionAnalysis]
        Analysis results or None if required data is missing
    """
    if not hasattr(result, 'series') or not result.series:
        return None

    series = result.series

    # Get timestamps
    timestamps = series.get('timestamps') or series.get('timestamp')
    if timestamps is None:
        # Generate timestamps
        n = len(next(iter(series.values())))
        start = datetime(2023, 1, 1)
        timestamps = [start + timedelta(hours=i * dt_h) for i in range(n)]

    # Get electricity consumption (P_buy = grid electricity)
    elec_mw = series.get('P_buy_MW') or series.get('Pbuy_MW')
    if elec_mw is None:
        # Try to find any electricity consumption series
        for key in ['HP_P_el_MW', 'P2H_P_el_MW', 'total_elec_MW']:
            if key in series:
                elec_mw = series[key]
                break

    if elec_mw is None:
        return None

    # Get CO2 factors
    co2_factors = series.get('grid_co2_kg_MWh') or series.get('Grid_CO2_factor_kg_MWh')
    if co2_factors is None:
        return None

    return analyze_co2_resolution(
        timestamps=list(timestamps),
        electricity_mw=list(elec_mw),
        grid_co2_kg_mwh=list(co2_factors),
        dt_h=dt_h,
    )


def create_comparison_report(analysis: CO2ResolutionAnalysis) -> str:
    """
    Create a formatted text report comparing resolutions.

    Parameters
    ----------
    analysis : CO2ResolutionAnalysis
        Analysis results

    Returns
    -------
    str
        Formatted report text
    """
    lines = [
        "=" * 70,
        "CO2-EMISSIONSANALYSE: VERGLEICH ZEITLICHER AUFLÖSUNGEN",
        "=" * 70,
        "",
        f"Analysezeitraum: {analysis.timestamps[0]} bis {analysis.timestamps[-1]}",
        f"Zeitschrittdauer: {analysis.dt_h} h",
        f"Gesamtstromverbrauch: {sum(analysis.electricity_mwh):,.1f} MWh",
        f"Referenzauflösung: {analysis.reference_resolution}",
        "",
        "-" * 70,
        f"{'Auflösung':<35} {'CO2 [t]':>12} {'Abweichung':>12} {'Intensität':>12}",
        "-" * 70,
    ]

    ref_co2 = analysis.scenarios[analysis.reference_resolution].total_co2_kg

    # Sort scenarios by number of factors
    sorted_scenarios = sorted(
        analysis.scenarios.values(),
        key=lambda s: s.factors_used
    )

    for scen in sorted_scenarios:
        deviation = (scen.total_co2_kg - ref_co2) / ref_co2 * 100 if ref_co2 > 0 else 0
        dev_str = f"{deviation:+.2f}%" if scen.resolution != analysis.reference_resolution else "(Referenz)"
        lines.append(
            f"{scen.name:<35} {scen.total_co2_t:>12,.1f} {dev_str:>12} "
            f"{scen.co2_intensity_kg_mwh:>9,.1f} kg/MWh"
        )

    lines.extend([
        "-" * 70,
        "",
        "INTERPRETATION:",
        "",
        "- Positive Abweichung: Bilanzieller Ansatz UNTERSCHÄTZT die Emissionen",
        "  (Stromverbrauch korreliert mit hohem CO2-Faktor des Strommix)",
        "",
        "- Negative Abweichung: Bilanzieller Ansatz ÜBERSCHÄTZT die Emissionen",
        "  (Stromverbrauch korreliert mit niedrigem CO2-Faktor, z.B. PV-Spitzen)",
        "",
        "Bei Wärmepumpen oft negative Korrelation (Heizlast hoch wenn wenig Solar),",
        "bei PV-gekoppelten Systemen oft positive Korrelation (Verbrauch bei PV-Peak).",
        "=" * 70,
    ])

    return "\n".join(lines)


def create_monthly_breakdown(analysis: CO2ResolutionAnalysis) -> pd.DataFrame:
    """
    Create monthly breakdown of CO2 emissions by resolution.

    Parameters
    ----------
    analysis : CO2ResolutionAnalysis
        Analysis results

    Returns
    -------
    pd.DataFrame
        Monthly breakdown with columns for each resolution
    """
    df = pd.DataFrame({
        'timestamp': analysis.timestamps,
        'elec_mwh': analysis.electricity_mwh,
        'co2_factor': analysis.grid_co2_factors,
    })
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['month'] = df['timestamp'].dt.to_period('M')

    # Annual factor (constant)
    annual_factor = sum(analysis.grid_co2_factors) / len(analysis.grid_co2_factors)

    # Group by month
    monthly = df.groupby('month').agg({
        'elec_mwh': 'sum',
        'co2_factor': 'mean',
    }).reset_index()

    monthly['CO2_bilanziell_t'] = monthly['elec_mwh'] * annual_factor / 1000
    monthly['CO2_monatlich_t'] = monthly['elec_mwh'] * monthly['co2_factor'] / 1000

    # For hourly/actual resolution, sum up the timeseries
    if 'hourly' in analysis.scenarios and analysis.scenarios['hourly'].timeseries_co2_kg:
        df['co2_hourly_kg'] = analysis.scenarios['hourly'].timeseries_co2_kg
        hourly_monthly = df.groupby('month')['co2_hourly_kg'].sum() / 1000
        monthly['CO2_stündlich_t'] = monthly['month'].map(hourly_monthly)

    monthly['Monat'] = monthly['month'].astype(str)
    monthly['Strom_MWh'] = monthly['elec_mwh']
    monthly['Ø_CO2_Faktor'] = monthly['co2_factor']

    return monthly[[
        'Monat', 'Strom_MWh', 'Ø_CO2_Faktor',
        'CO2_bilanziell_t', 'CO2_monatlich_t', 'CO2_stündlich_t'
    ]].round(2)

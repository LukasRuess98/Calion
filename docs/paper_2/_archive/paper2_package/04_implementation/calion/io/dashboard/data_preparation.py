"""
Data preparation module for the CALION Dashboard.

Contains classes and functions for extracting and preparing data
from workflow results for visualization.

from calion.logging_config import get_logger

logger = get_logger(__name__)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class DashboardData:
    """
    Container for prepared dashboard data.

    Attributes
    ----------
    df : pd.DataFrame
        Main timeseries DataFrame
    costs_df : pd.DataFrame
        Cost breakdown DataFrame
    heat_components : List[str]
        List of heat component column names
    elec_components : List[str]
        List of electrical component column names
    storage_cols : List[str]
        List of storage-related column names
    dt_h : float
        Timestep duration in hours
    downsampled : bool
        Whether data was downsampled for performance
    downsample_factor : int
        Downsampling factor (1 if not downsampled)

    Original Values (before downsampling):
    original_total_demand_MWh : float
    original_peak_demand_MW : float
    original_timesteps : int
    original_heat_production : Dict[str, float]
    original_total_heat_production : float

    CO2 Data:
    total_co2_t : float
    grid_co2_t : float
    fuel_co2_t : float
    fuel_co2_heat_t : float
    fuel_co2_elec_t : float
    grid_co2_elec_t : float
    co2_cost_eur : float
    """
    # Main data
    df: pd.DataFrame
    costs_df: pd.DataFrame

    # Component lists
    heat_components: list[str]
    elec_components: list[str]
    storage_cols: list[str]

    # Time configuration
    dt_h: float = 1.0

    # Downsampling info
    downsampled: bool = False
    downsample_factor: int = 1

    # Original values (important for KPIs)
    original_total_demand_MWh: float = 0.0
    original_peak_demand_MW: float = 0.0
    original_timesteps: int = 0
    original_heat_production: dict[str, float] = field(default_factory=dict)
    original_total_heat_production: float = 0.0

    # CO2 data
    total_co2_t: float = 0.0
    grid_co2_t: float = 0.0
    fuel_co2_t: float = 0.0
    fuel_co2_heat_t: float = 0.0
    fuel_co2_elec_t: float = 0.0
    grid_co2_elec_t: float = 0.0
    co2_cost_eur: float = 0.0


def prepare_dashboard_data(
    result: Any,
    workflow_config: dict | None = None,
    max_points: int = 20000
) -> DashboardData:
    """
    Prepare data from workflow result for dashboard visualization.

    Parameters
    ----------
    result : Any
        Primary workflow result (pf_result, rh_result, or mpc_result)
    workflow_config : dict, optional
        Workflow configuration dict
    max_points : int
        Maximum data points before downsampling

    Returns
    -------
    DashboardData
        Prepared dashboard data container

    Raises
    ------
    ValueError
        If required data columns are missing
    """
    # Find demand column
    demand_col_names = [
        'waermebedarf_MWth', 'Waermebedarf_MWth',
        'heat_demand_MW', 'demand_MW', 'Q_demand_MW'
    ]
    demand_values = None

    for col_name in demand_col_names:
        if col_name in result.table.data:
            demand_values = result.table.data[col_name]
            break

    if demand_values is None:
        available_cols = list(result.table.data.keys())
        raise ValueError(
            f"Dashboard: No heat demand column found!\n"
            f"Tried columns: {demand_col_names}\n"
            f"Available columns: {available_cols}\n"
            f"Ensure at least one of the listed columns is present in the result data."
        )

    # Create main DataFrame
    df = pd.DataFrame({
        'timestamp': result.table.index,
        'demand_MW': demand_values,
    })

    # Add all series before downsampling
    if result.series:
        for key, values in result.series.items():
            if len(values) == len(df):
                df[key] = values
            else:
                logger.warning(
                    f"Dashboard: Skipping series '{key}' - length mismatch "
                    f"(expected {len(df)}, got {len(values)})"
                )
    else:
        logger.warning("Dashboard: result.series is empty - no timeseries data to display")

    # Identify component types (before downsampling)
    heat_components = [col for col in df.columns if col.endswith('_Q_th_MW')]
    elec_components = [col for col in df.columns if col.endswith('_Pel_MW')]
    storage_cols = [col for col in df.columns if 'TES' in col]

    # Save original values before downsampling
    original_total_demand_MWh = df['demand_MW'].sum()
    original_peak_demand_MW = df['demand_MW'].max()
    original_timesteps = len(df)

    # Calculate original heat production per component
    original_heat_production = {}
    for comp in heat_components:
        if comp in df.columns:
            original_heat_production[comp] = df[comp].sum()

    original_total_heat_production = sum(original_heat_production.values())

    # Downsampling for large datasets
    downsampled = False
    downsample_factor = 1
    original_length = len(df)

    if original_length > max_points:
        logger.info(
            f"Dashboard: Large dataset detected ({original_length:,} points). "
            f"Downsampling to {max_points:,} points for better performance."
        )

        step = original_length // max_points
        df = df.iloc[::step].copy()
        downsampled = True
        downsample_factor = step

        logger.info("\nHINWEIS: Performance-Optimierung:")
        logger.info(f"         Datensatz wurde von {original_length:,} auf {len(df):,} Punkte reduziert (Faktor {step})")
        logger.info("         Dies verbessert die Dashboard-Performance erheblich.")
        logger.info("         Für detaillierte Analysen: Verwende die CSV-Exports aus saved_workflows/")
        logger.info("         INFO: KPIs werden auf Basis der Original-Daten berechnet (nicht downsampled)")

    # Re-identify component types after downsampling
    heat_components = [col for col in df.columns if col.endswith('_Q_th_MW')]
    elec_components = [col for col in df.columns if col.endswith('_Pel_MW')]
    storage_cols = [col for col in df.columns if 'TES' in col]

    # Extract dt_h from config
    dt_h = 1.0
    if workflow_config:
        run_cfg = workflow_config.get('run', {})
        dt_h = float(run_cfg.get('dt_h', 1.0))

    # Log component detection
    if not heat_components and not elec_components:
        logger.warning(
            f"Dashboard: No heat or electric components detected. "
            f"Available columns: {list(df.columns)}"
        )

    # Prepare costs DataFrame
    costs_df = _prepare_costs_df(result)

    # Extract CO2 data
    co2_data = _extract_co2_data(df, result)

    return DashboardData(
        df=df,
        costs_df=costs_df,
        heat_components=heat_components,
        elec_components=elec_components,
        storage_cols=storage_cols,
        dt_h=dt_h,
        downsampled=downsampled,
        downsample_factor=downsample_factor,
        original_total_demand_MWh=original_total_demand_MWh,
        original_peak_demand_MW=original_peak_demand_MW,
        original_timesteps=original_timesteps,
        original_heat_production=original_heat_production,
        original_total_heat_production=original_total_heat_production,
        **co2_data
    )


def _prepare_costs_df(result: Any) -> pd.DataFrame:
    """
    Prepare costs DataFrame from result.

    Parameters
    ----------
    result : Any
        Workflow result with costs attribute

    Returns
    -------
    pd.DataFrame
        Prepared costs DataFrame
    """
    if not hasattr(result, 'costs') or not result.costs:
        logger.warning("Dashboard: result.costs is empty or missing")
        return pd.DataFrame()

    cost_entries = []
    for key, value in result.costs.items():
        if isinstance(value, (int, float)) and key.endswith('_EUR'):
            cost_entries.append({
                'Category': key.replace('objective.', '').replace('_EUR', '').replace('_', ' '),
                'Value_EUR': float(value),
                'Original_Key': key
            })

    if not cost_entries:
        logger.warning("Dashboard: No valid cost entries found in result.costs")
        return pd.DataFrame()

    costs_df = pd.DataFrame(cost_entries)

    # Calculate percentages
    total = costs_df['Value_EUR'].sum()
    if total > 0:
        costs_df['Percentage'] = (costs_df['Value_EUR'] / total * 100).round(2)
    else:
        costs_df['Percentage'] = 0.0

    return costs_df.sort_values('Value_EUR', ascending=False)


def _extract_co2_data(df: pd.DataFrame, result: Any) -> dict[str, float]:
    """
    Extract CO2 data from DataFrame and result.

    Parameters
    ----------
    df : pd.DataFrame
        Main timeseries DataFrame
    result : Any
        Workflow result

    Returns
    -------
    dict
        CO2 data dictionary
    """
    total_co2_t = 0.0
    grid_co2_t = 0.0
    fuel_co2_t = 0.0
    fuel_co2_heat_t = 0.0
    fuel_co2_elec_t = 0.0
    grid_co2_elec_t = 0.0
    co2_cost_eur = 0.0

    # Primary: Aggregate from timeseries (most reliable source)
    if 'Grid_CO2_emissions_t_per_step' in df.columns:
        grid_co2_t = df['Grid_CO2_emissions_t_per_step'].sum()

    if 'Fuel_CO2_emissions_t_per_step' in df.columns:
        fuel_co2_t = df['Fuel_CO2_emissions_t_per_step'].sum()

    if 'Total_CO2_emissions_t_per_step' in df.columns:
        total_co2_t = df['Total_CO2_emissions_t_per_step'].sum()
    else:
        total_co2_t = grid_co2_t + fuel_co2_t

    # Secondary: Fallback from summary/costs (legacy)
    if grid_co2_t == 0 and hasattr(result, 'summary') and result.summary:
        if 'grid' in result.summary:
            grid_co2_t = result.summary['grid'].get('Grid_CO2_emissions_t', 0)
            if total_co2_t == 0:
                total_co2_t = result.summary['grid'].get('Total_CO2_emissions_t', 0)

    if fuel_co2_t == 0 and hasattr(result, 'costs') and result.costs:
        fuel_co2_t = result.costs.get('Fuel_emissions_t', 0)

    # Extract 3-category CO2 (Fuel→Heat, Fuel→Elec, Grid→Elec)
    if hasattr(result, 'costs') and result.costs:
        fuel_co2_heat_t = result.costs.get('CO2_fuel_to_heat_kg', 0) / 1000.0
        fuel_co2_elec_t = result.costs.get('CO2_fuel_to_elec_kg', 0) / 1000.0
        grid_co2_elec_t = result.costs.get('CO2_grid_to_elec_kg', 0) / 1000.0

    # Fallback for legacy data
    if fuel_co2_heat_t == 0 and fuel_co2_elec_t == 0 and grid_co2_elec_t == 0:
        fuel_co2_heat_t, fuel_co2_elec_t, grid_co2_elec_t = _extract_legacy_co2(
            result, grid_co2_t, fuel_co2_t
        )

    # Calculate total from 3 categories
    calculated_total = fuel_co2_heat_t + fuel_co2_elec_t + grid_co2_elec_t
    if calculated_total > 0:
        total_co2_t = calculated_total

    # CO2 costs
    if hasattr(result, 'costs') and result.costs:
        co2_cost_eur = result.costs.get('objective.CO2_cost_EUR', 0)

    return {
        'total_co2_t': total_co2_t,
        'grid_co2_t': grid_co2_t,
        'fuel_co2_t': fuel_co2_t,
        'fuel_co2_heat_t': fuel_co2_heat_t,
        'fuel_co2_elec_t': fuel_co2_elec_t,
        'grid_co2_elec_t': grid_co2_elec_t,
        'co2_cost_eur': co2_cost_eur,
    }


def _extract_legacy_co2(
    result: Any,
    grid_co2_t: float,
    fuel_co2_t: float
) -> tuple:
    """
    Extract CO2 data from legacy format (2-category system).

    Parameters
    ----------
    result : Any
        Workflow result
    grid_co2_t : float
        Total grid CO2
    fuel_co2_t : float
        Total fuel CO2

    Returns
    -------
    tuple
        (fuel_co2_heat_t, fuel_co2_elec_t, grid_co2_elec_t)
    """
    fuel_co2_heat_t = 0.0
    fuel_co2_elec_t = 0.0
    grid_co2_elec_t = 0.0

    if hasattr(result, 'costs') and result.costs:
        legacy_heat = result.costs.get('CO2_heat_total_kg', 0) / 1000.0
        legacy_elec = result.costs.get('CO2_elec_total_kg', 0) / 1000.0

        if hasattr(result, 'summary') and result.summary:
            # Estimate CHP share from power generation
            chp_elec_mwh = 0
            wp_p2h_elec_mwh = 0

            for key, data in result.summary.items():
                if key.startswith('generator_'):
                    pel_mwh = data.get('Power_output_MWh', 0)
                    if pel_mwh > 0:
                        chp_elec_mwh += pel_mwh

            for key, data in result.summary.items():
                if key.startswith('hp_'):
                    pel_mwh = data.get('Electricity_input_MWh', 0)
                    wp_p2h_elec_mwh += pel_mwh

            if 'p2h' in result.summary:
                pel_mwh = result.summary['p2h'].get('Electricity_input_MWh', 0)
                wp_p2h_elec_mwh += pel_mwh

            # Split legacy_elec proportionally
            total_elec = chp_elec_mwh + wp_p2h_elec_mwh
            if total_elec > 0 and legacy_elec > 0:
                fuel_co2_elec_t = legacy_elec * (chp_elec_mwh / total_elec)
                grid_co2_elec_t = legacy_elec * (wp_p2h_elec_mwh / total_elec)
            else:
                grid_co2_elec_t = legacy_elec
                fuel_co2_elec_t = 0

            fuel_co2_heat_t = legacy_heat
        else:
            fuel_co2_heat_t = legacy_heat
            grid_co2_elec_t = legacy_elec
            fuel_co2_elec_t = 0

        # Grid emissions fallback
        if grid_co2_elec_t == 0 and fuel_co2_elec_t == 0:
            grid_co2_elec_t = grid_co2_t

        # Very old fallback
        if fuel_co2_heat_t == 0 and fuel_co2_elec_t == 0 and fuel_co2_t > 0:
            fuel_co2_heat_t = fuel_co2_t
            fuel_co2_elec_t = 0

    return fuel_co2_heat_t, fuel_co2_elec_t, grid_co2_elec_t


def calculate_total_investment(workflow: Any) -> float:
    """
    Calculate total investment (CAPEX) from design capacities and config.

    Returns the actual total investment cost, NOT annualized or pro-rated.

    Parameters
    ----------
    workflow : Any
        Workflow object with design and config

    Returns
    -------
    float
        Total investment in EUR
    """
    total_investment = 0.0

    design = workflow.design
    config = getattr(workflow, 'config', {}) or {}

    if not design:
        return 0.0

    system_cfg = config.get('system', {})

    # Heat Pump investment costs
    if design.heat_pumps:
        hp_configs = {hp.get('id', f'HP{i}'): hp
                      for i, hp in enumerate(system_cfg.get('heat_pumps', []))}

        for hp_id, hp_info in design.heat_pumps.items():
            capacity_mw = hp_info.get('capacity_mw', 0.0)
            if capacity_mw > 0:
                hp_cfg = hp_configs.get(hp_id, {})
                inv_cfg = hp_cfg.get('investment', {})

                capex_per_mw = float(inv_cfg.get('capex_eur_per_mw', 400000.0))
                activation_cost = float(inv_cfg.get('activation_cost_eur', 250000.0))

                hp_investment = capacity_mw * capex_per_mw + activation_cost
                total_investment += hp_investment

    # Storage investment costs
    if design.storage:
        storage_mwh = design.storage.get('capacity_mwh', 0.0)
        storage_mw = design.storage.get('power_mw', 0.0)

        if storage_mwh > 0 or storage_mw > 0:
            sto_cfg = system_cfg.get('storage', {})
            inv_cfg = sto_cfg.get('investment', {})

            energy_capex = float(inv_cfg.get('energy_capex_eur_per_mwh', 5000.0))
            power_capex = float(inv_cfg.get('power_capex_eur_per_mw', 50000.0))
            activation_cost = float(inv_cfg.get('activation_cost_eur', 50000.0))

            storage_investment = (storage_mwh * energy_capex +
                                  storage_mw * power_capex +
                                  activation_cost)
            total_investment += storage_investment

    return total_investment

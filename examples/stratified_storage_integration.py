#!/usr/bin/env python3
"""
Stratified Storage Integration Example
======================================

Demonstrates full integration of the StratifiedStorageBlock component
with the EnerGIS framework, including:
- System builder integration
- Gurobi solver configuration
- Export functionality
- Result analysis

This is a complete working example that can be run directly.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any
import pandas as pd

try:
    import pyomo.environ as pyo
    from pyomo.opt import SolverFactory
except ImportError:
    raise ImportError("Pyomo is required for this example")

# Import EnerGIS components
from energis.models.blocks.stratified_storage import StratifiedStorageBlock
from energis.models.blocks.heat_pump import HeatPumpBlock
from energis.models.component import Bus
from energis.utils.timeseries import TimeSeriesTable


def create_simple_timeseries(hours: int = 168) -> pd.DataFrame:
    """Create simple synthetic time series data for testing."""
    import numpy as np

    # Create hourly index
    index = pd.date_range('2023-01-01', periods=hours, freq='h')

    # Synthetic heat demand (higher during day, lower at night)
    hour_of_day = index.hour
    base_demand = 30.0  # MW
    daily_variation = 15.0 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
    heat_demand = base_demand + daily_variation
    heat_demand = np.maximum(heat_demand, 10.0)  # Minimum 10 MW

    # Synthetic electricity price (higher during day)
    base_price = 50.0  # EUR/MWh
    price_variation = 30.0 * np.sin(2 * np.pi * (hour_of_day - 12) / 24)
    electricity_price = base_price + price_variation

    # Synthetic waste heat temperature (varying slightly)
    base_temp = 50.0  # °C
    temp_variation = 5.0 * np.sin(2 * np.pi * hour_of_day / 24)
    wrg_temp = base_temp + temp_variation + 273.15  # Convert to K

    # CO2 intensity (lower at night when renewables are more available)
    base_co2 = 300.0  # kg/MWh
    co2_variation = 100.0 * np.cos(2 * np.pi * (hour_of_day - 3) / 24)
    co2_intensity = base_co2 + co2_variation

    df = pd.DataFrame({
        'waermebedarf_MWth': heat_demand,
        'strompreis_EUR_MWh': electricity_price,
        'WRG1_T_K': wrg_temp,
        'grid_co2_kg_MWh': co2_intensity
    }, index=index)

    return df


def build_model_with_stratified_storage(
    table: TimeSeriesTable,
    solver_name: str = 'gurobi'
) -> tuple[pyo.ConcreteModel, Dict[str, Any]]:
    """
    Build optimization model with stratified storage.

    Args:
        table: Time series data
        solver_name: Solver to use (default: gurobi)

    Returns:
        Tuple of (model, component_dict)
    """
    if pyo is None:
        raise RuntimeError("Pyomo is required")

    T = len(table)
    dt_h = 1.0

    # Create model
    m = pyo.ConcreteModel(name="StratifiedStorage_Integration")

    # Time set
    m.t = pyo.RangeSet(1, T)

    # ========================================
    # COMPONENTS
    # ========================================

    # 1. Heat Pump
    hp = HeatPumpBlock(
        name="HP1",
        min_load=0.3,
        cop_series=[3.5] * T,  # Simplified constant COP
        capacity_min_mw=0.0,
        capacity_max_mw=50.0,
        capacity_init_mw=30.0,
        investable=True,
        label="Main Heat Pump"
    )

    # 2. Stratified Storage
    storage = StratifiedStorageBlock(
        name="TES",
        # Thermal parameters
        T_hot_C=90.0,
        T_cold_C=40.0,
        T_ambient_C=15.0,
        T_ground_C=10.0,
        # Geometry
        aspect_ratio=1.5,
        geometry_type="tank",
        # Heat transfer coefficients [W/(m²·K)]
        U_top=0.3,
        U_side=0.2,
        U_bottom=0.15,
        # Efficiency
        eff_c=0.95,
        eff_d=0.95,
        # Time step
        dt_h=dt_h,
        # Initial state
        soc0=50.0,  # Start with 50 MWh
        V_hot_init_fraction=0.5,  # Half hot, half cold
        # Investment
        investable=True,
        e_cap_min=50.0,
        e_cap_max=500.0,
        p_cap_min=10.0,
        p_cap_max=100.0,
        e_cap_init=100.0,
        p_cap_init=30.0,
        label="District Heating Buffer Storage"
    )

    # ========================================
    # BUS SYSTEM
    # ========================================

    heat_bus = Bus(name="heat")
    elec_bus = Bus(name="electricity")
    buses = {"heat": heat_bus, "electricity": elec_bus}

    # Config for components (minimal)
    cfg = {"inputs": {"table": table}}

    # Attach components
    hp_result = hp.attach(m, m.t, cfg, buses)
    storage_result = storage.attach(m, m.t, cfg, buses)

    # ========================================
    # PARAMETERS
    # ========================================

    # Heat demand
    heat_demand_data = {i+1: float(table['waermebedarf_MWth'][i]) for i in range(T)}
    m.heat_demand = pyo.Param(m.t, initialize=heat_demand_data)

    # Electricity price
    elec_price_data = {i+1: float(table['strompreis_EUR_MWh'][i]) for i in range(T)}
    m.elec_price = pyo.Param(m.t, initialize=elec_price_data)

    # ========================================
    # CONSTRAINTS
    # ========================================

    # Heat balance
    def heat_balance_rule(mm, t):
        hp_heat = hp_result['flows']['heat']['output'][t]
        storage_out = storage_result['flows']['heat']['output'][t]
        storage_in = storage_result['flows']['heat']['input'][t]
        demand = mm.heat_demand[t]
        return hp_heat + storage_out == demand + storage_in

    m.heat_balance = pyo.Constraint(m.t, rule=heat_balance_rule)

    # ========================================
    # OBJECTIVE
    # ========================================

    def objective_rule(mm):
        # Electricity costs
        elec_cost = sum(
            hp_result['flows']['electricity']['input'][t] * mm.elec_price[t] * dt_h
            for t in mm.t
        )

        # Investment costs (annualized)
        hp_capex = hp_result['investment'].capacity * 800.0 / 15.0  # EUR/MW/year
        storage_capex_energy = storage_result['investment'].capacity_energy * 50.0 / 20.0  # EUR/MWh/year
        storage_capex_power = storage_result['investment'].capacity_power * 200.0 / 20.0  # EUR/MW/year

        total_cost = elec_cost + hp_capex + storage_capex_energy + storage_capex_power
        return total_cost

    m.obj = pyo.Objective(rule=objective_rule, sense=pyo.minimize)

    # ========================================
    # RETURN
    # ========================================

    components = {
        'heat_pump': hp_result,
        'storage': storage_result,
        'buses': buses
    }

    return m, components


def solve_model(
    model: pyo.ConcreteModel,
    solver_name: str = 'gurobi',
    **solver_options
) -> Dict[str, Any]:
    """
    Solve optimization model.

    Args:
        model: Pyomo model
        solver_name: Solver to use
        **solver_options: Additional solver options

    Returns:
        Dictionary with solve results
    """
    # Configure solver
    solver = SolverFactory(solver_name)

    # Set default options for Gurobi
    if solver_name.lower() == 'gurobi':
        default_options = {
            'MIPGap': 0.01,  # 1% gap
            'TimeLimit': 300,  # 5 minutes
            'LogToConsole': 1,
            'OutputFlag': 1
        }
        default_options.update(solver_options)
        for key, value in default_options.items():
            solver.options[key] = value

    print(f"\n{'='*70}")
    print(f"SOLVING WITH {solver_name.upper()}")
    print(f"{'='*70}\n")

    import time
    start_time = time.time()

    # Solve
    results = solver.solve(model, tee=True)

    solve_time = time.time() - start_time

    # Check termination
    term_cond = results.solver.termination_condition
    is_optimal = term_cond == pyo.TerminationCondition.optimal

    solve_results = {
        'termination_condition': str(term_cond),
        'is_optimal': is_optimal,
        'solve_time_sec': solve_time,
        'solver': solver_name,
    }

    if is_optimal:
        solve_results['objective_value'] = pyo.value(model.obj)
        print(f"\n✓ Optimal solution found!")
        print(f"  Objective: {solve_results['objective_value']:,.2f} EUR")
        print(f"  Solve time: {solve_time:.2f} seconds")
    else:
        print(f"\n✗ Solver did not find optimal solution")
        print(f"  Termination: {term_cond}")

    print(f"{'='*70}\n")

    return solve_results


def extract_results(
    model: pyo.ConcreteModel,
    components: Dict[str, Any],
    table: TimeSeriesTable
) -> Dict[str, pd.DataFrame]:
    """
    Extract results from solved model.

    Args:
        model: Solved Pyomo model
        components: Component dictionary
        table: Original time series table

    Returns:
        Dictionary with result DataFrames
    """
    T = len(model.t)
    index = table.index if hasattr(table, 'index') else range(T)

    # Heat pump results
    hp_result = components['heat_pump']
    hp_data = {
        'HP_Q_th_MW': [pyo.value(hp_result['flows']['heat']['output'][t]) for t in model.t],
        'HP_P_el_MW': [pyo.value(hp_result['flows']['electricity']['input'][t]) for t in model.t],
    }

    # Storage results
    storage_result = components['storage']
    storage_data = {
        'E_total_MWh': [pyo.value(storage_result['state'][t]) for t in model.t],
        'Qc_MW': [pyo.value(storage_result['flows']['heat']['input'][t]) for t in model.t],
        'Qd_MW': [pyo.value(storage_result['flows']['heat']['output'][t]) for t in model.t],
        'V_hot_m3': [pyo.value(storage_result['zones']['V_hot'][t]) for t in model.t],
        'V_cold_m3': [pyo.value(storage_result['zones']['V_cold'][t]) for t in model.t],
    }

    # Investment results
    if storage_result['investment']:
        inv = storage_result['investment']
        investment_data = {
            'Storage_E_cap_MWh': pyo.value(inv.capacity_energy),
            'Storage_P_cap_MW': pyo.value(inv.capacity_power),
            'Storage_build': pyo.value(inv.build),
        }

        hp_inv = hp_result['investment']
        investment_data.update({
            'HP_cap_MW': pyo.value(hp_inv.capacity),
            'HP_build': pyo.value(hp_inv.build),
        })
    else:
        investment_data = {}

    return {
        'heat_pump': pd.DataFrame(hp_data, index=index),
        'storage': pd.DataFrame(storage_data, index=index),
        'investment': pd.DataFrame([investment_data]) if investment_data else pd.DataFrame()
    }


def export_results(
    results: Dict[str, pd.DataFrame],
    table: TimeSeriesTable,
    solve_info: Dict[str, Any],
    export_dir: Path
):
    """
    Export results to Excel and CSV.

    Args:
        results: Result DataFrames
        table: Original input data
        solve_info: Solver information
        export_dir: Export directory
    """
    export_dir.mkdir(parents=True, exist_ok=True)

    # Export to Excel
    excel_path = export_dir / "stratified_storage_results.xlsx"
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        # Input data
        if isinstance(table, pd.DataFrame):
            table.to_excel(writer, sheet_name='Input_Data')

        # Results
        for sheet_name, df in results.items():
            if not df.empty:
                df.to_excel(writer, sheet_name=sheet_name)

        # Solver info
        pd.DataFrame([solve_info]).to_excel(writer, sheet_name='Solver_Info', index=False)

    print(f"✓ Results exported to: {excel_path}")

    # Export CSVs
    for name, df in results.items():
        if not df.empty:
            csv_path = export_dir / f"{name}.csv"
            df.to_csv(csv_path)
            print(f"✓ {name} CSV exported to: {csv_path}")


def analyze_storage_behavior(
    storage_df: pd.DataFrame,
    investment_df: pd.DataFrame
):
    """
    Analyze and print storage behavior statistics.

    Args:
        storage_df: Storage timeseries data
        investment_df: Investment results
    """
    print(f"\n{'='*70}")
    print(f"STORAGE ANALYSIS")
    print(f"{'='*70}\n")

    # Investment
    if not investment_df.empty:
        E_cap = investment_df['Storage_E_cap_MWh'].values[0]
        P_cap = investment_df['Storage_P_cap_MW'].values[0]
        print(f"Investment Results:")
        print(f"  Energy Capacity: {E_cap:,.1f} MWh")
        print(f"  Power Capacity: {P_cap:,.1f} MW")
        print(f"  P/E Ratio: {P_cap/E_cap:.3f} (1/h)")
        print()

    # Operational statistics
    E_total = storage_df['E_total_MWh']
    Qc = storage_df['Qc_MW']
    Qd = storage_df['Qd_MW']
    V_hot = storage_df['V_hot_m3']
    V_cold = storage_df['V_cold_m3']

    print(f"Operational Statistics:")
    print(f"  SOC - Min: {E_total.min():,.1f} MWh")
    print(f"  SOC - Max: {E_total.max():,.1f} MWh")
    print(f"  SOC - Mean: {E_total.mean():,.1f} MWh")
    print(f"  SOC - Std: {E_total.std():,.1f} MWh")
    print()

    print(f"  Charging - Total: {(Qc.sum()):.1f} MWh")
    print(f"  Discharging - Total: {(Qd.sum()):.1f} MWh")
    print(f"  Roundtrip Efficiency: {(Qd.sum() / Qc.sum() * 100):.1f}%")
    print()

    # Stratification analysis
    V_total = V_hot + V_cold
    ratio_hot = V_hot / V_total

    print(f"Stratification Analysis:")
    print(f"  Hot Volume - Min: {V_hot.min():,.0f} m³ ({ratio_hot.min()*100:.1f}%)")
    print(f"  Hot Volume - Max: {V_hot.max():,.0f} m³ ({ratio_hot.max()*100:.1f}%)")
    print(f"  Hot Volume - Mean: {V_hot.mean():,.0f} m³ ({ratio_hot.mean()*100:.1f}%)")
    print()

    # Cycling
    charge_events = (Qc > 0).sum()
    discharge_events = (Qd > 0).sum()
    print(f"  Charge Events: {charge_events} hours")
    print(f"  Discharge Events: {discharge_events} hours")
    print(f"  Utilization: {((charge_events + discharge_events) / len(storage_df) * 100):.1f}%")

    print(f"{'='*70}\n")


def main():
    """Main execution function."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     STRATIFIED STORAGE - FULL INTEGRATION EXAMPLE                    ║
║                                                                      ║
║     Demonstrating:                                                   ║
║     • Stratified storage in optimization model                       ║
║     • Gurobi solver integration                                      ║
║     • Result extraction and export                                   ║
║     • Storage behavior analysis                                      ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    # Configuration
    hours = 168  # One week
    solver_name = os.environ.get('SOLVER_NAME', 'gurobi')
    export_dir = Path(os.environ.get('EXPORT_DIR', 'exports/stratified_integration'))

    print(f"Configuration:")
    print(f"  Simulation period: {hours} hours (1 week)")
    print(f"  Solver: {solver_name}")
    print(f"  Export directory: {export_dir}")
    print()

    # Step 1: Create time series data
    print(f"{'='*70}")
    print(f"STEP 1: Creating synthetic time series data")
    print(f"{'='*70}\n")

    df = create_simple_timeseries(hours)
    print(f"✓ Created {len(df)} hourly timesteps")
    print(f"  Heat demand range: {df['waermebedarf_MWth'].min():.1f} - {df['waermebedarf_MWth'].max():.1f} MW")
    print(f"  Electricity price range: {df['strompreis_EUR_MWh'].min():.1f} - {df['strompreis_EUR_MWh'].max():.1f} EUR/MWh")
    print()

    # Step 2: Build model
    print(f"{'='*70}")
    print(f"STEP 2: Building optimization model")
    print(f"{'='*70}\n")

    model, components = build_model_with_stratified_storage(df, solver_name)
    print(f"✓ Model built successfully")
    print(f"  Variables: {len(list(model.component_data_objects(pyo.Var)))}")
    print(f"  Constraints: {len(list(model.component_data_objects(pyo.Constraint)))}")
    print()

    # Step 3: Solve
    solve_info = solve_model(model, solver_name)

    if not solve_info['is_optimal']:
        print("✗ Optimization failed. Trying with CBC fallback...")
        solve_info = solve_model(model, 'cbc')

    # Step 4: Extract results
    if solve_info['is_optimal']:
        print(f"{'='*70}")
        print(f"STEP 4: Extracting results")
        print(f"{'='*70}\n")

        results = extract_results(model, components, df)
        print(f"✓ Results extracted")
        print(f"  Heat pump data: {len(results['heat_pump'])} rows")
        print(f"  Storage data: {len(results['storage'])} rows")
        print(f"  Investment data: {len(results['investment'])} entries")
        print()

        # Step 5: Analyze
        analyze_storage_behavior(results['storage'], results['investment'])

        # Step 6: Export
        print(f"{'='*70}")
        print(f"STEP 6: Exporting results")
        print(f"{'='*70}\n")

        export_results(results, df, solve_info, export_dir)
        print()

        print(f"{'='*70}")
        print(f"SUCCESS!")
        print(f"{'='*70}\n")
        print(f"✓ Stratified storage model solved and analyzed")
        print(f"✓ Results exported to: {export_dir}")
        print(f"\nNext steps:")
        print(f"  1. Review Excel file: {export_dir}/stratified_storage_results.xlsx")
        print(f"  2. Analyze stratification patterns in V_hot/V_cold columns")
        print(f"  3. Compare with simple storage model")
        print(f"  4. Adjust U-values for your specific application")
        print()
    else:
        print(f"\n✗ Failed to solve model")
        print(f"  Check solver availability and problem formulation")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
oemof-solph Implementation for EnerGIS Benchmark Comparison
============================================================

This script implements an equivalent heat network optimization model using
oemof-solph to enable direct comparison with EnerGIS.

The model structure mirrors EnerGIS:
- Multiple heat pumps with investment decisions
- Thermal energy storage
- CHP and backup generators
- Grid connection with buy/sell
- Waste heat recovery
- Multi-commodity buses (electricity, heat, gas)

Author: For Applied Energy benchmarking
Date: 2025-11-18
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import time
import warnings

# oemof imports
try:
    import oemof.solph as solph
    from oemof.solph import views
    OEMOF_AVAILABLE = True
except ImportError:
    OEMOF_AVAILABLE = False
    warnings.warn("oemof.solph not installed. Install with: pip install oemof.solph")

# ============================================================
# CONFIGURATION MATCHING ENERGIS
# ============================================================

class OemofBenchmarkConfig:
    """Configuration matching EnerGIS for fair comparison."""

    def __init__(self, hours=168):
        self.hours = hours
        self.dt_h = 1.0  # Time step in hours

        # Economic parameters
        self.discount_rate = 0.04  # 4%
        self.project_lifetime = 20  # years

        # Heat Pumps (matching EnerGIS HP1-HP4)
        self.heat_pumps = {
            'HP1': {
                'cop': 4.0,  # Simplified constant COP (vs. EnerGIS temp-dependent)
                'cap_max_mw': 25.0,
                'cap_min_mw': 5.0,
                'inv_cost_eur_kw': 800,
                'opex_var_eur_mwh': 2.0,
                'lifetime': 20,
            },
            'HP2': {
                'cop': 3.5,
                'cap_max_mw': 20.0,
                'cap_min_mw': 4.0,
                'inv_cost_eur_kw': 900,
                'opex_var_eur_mwh': 2.5,
                'lifetime': 20,
            },
            'HP3': {
                'cop': 3.0,
                'cap_max_mw': 15.0,
                'cap_min_mw': 3.0,
                'inv_cost_eur_kw': 1000,
                'opex_var_eur_mwh': 3.0,
                'lifetime': 20,
            },
        }

        # CHP (matching EnerGIS HKW)
        self.chp = {
            'HKW': {
                'cap_th_mw': 30.0,
                'eta_th': 0.50,  # Thermal efficiency
                'eta_el': 0.35,  # Electrical efficiency
                'alpha': 0.70,   # P_el/Q_th ratio
                'inv_cost_eur_kw': 600,
                'opex_var_eur_mwh': 5.0,
                'lifetime': 25,
            }
        }

        # Boiler (matching EnerGIS GTOST)
        self.boiler = {
            'GTOST': {
                'cap_th_mw': 20.0,
                'eta_th': 0.85,
                'inv_cost_eur_kw': 300,
                'opex_var_eur_mwh': 2.0,
                'lifetime': 20,
            }
        }

        # Storage (matching EnerGIS TES)
        self.storage = {
            'TES': {
                'energy_max_mwh': 100.0,
                'power_max_mw': 25.0,
                'eta_in': 0.95,
                'eta_out': 0.95,
                'loss_rate_per_hour': 0.002,
                'inv_cost_energy_eur_kwh': 30,
                'inv_cost_power_eur_kw': 100,
                'lifetime': 30,
            }
        }

        # Grid
        self.grid = {
            'cap_max_mw': 50.0,
            'demand_charge_eur_mw_year': 50000,
        }

        # Fuel prices
        self.fuel_prices = {
            'gas_eur_mwh': 40,
            'biomass_eur_mwh': 25,
        }

        # CO2
        self.co2_price_eur_t = 100
        self.co2_intensity = {
            'gas_kg_mwh': 202,
            'grid_kg_mwh': 400,  # Average, varies in time series
        }

    def annualization_factor(self, lifetime):
        """Calculate capital recovery factor for annualization."""
        r = self.discount_rate
        return r * (1 + r)**lifetime / ((1 + r)**lifetime - 1)

    def annualized_capex(self, inv_cost, lifetime):
        """Convert investment cost to annualized cost."""
        return inv_cost * self.annualization_factor(lifetime)


# ============================================================
# TIME SERIES GENERATION (MATCHING ENERGIS)
# ============================================================

def generate_synthetic_timeseries(hours=168):
    """
    Generate synthetic time series matching EnerGIS input data structure.

    For fair comparison, this should eventually use the SAME data as EnerGIS.
    """
    timestamps = pd.date_range('2023-01-01', periods=hours, freq='h')

    # Heat demand (MW) - diurnal and weekly pattern
    demand_base = 20
    demand_amplitude = 10
    demand = demand_base + demand_amplitude * np.sin(np.arange(hours) * 2 * np.pi / 24)
    demand += np.random.normal(0, 1, hours)  # Add noise
    demand = np.clip(demand, 10, 45)  # Realistic bounds

    # Electricity price (EUR/MWh) - day-ahead market pattern
    price_base = 60
    price_amplitude = 30
    elec_price = price_base + price_amplitude * np.sin(np.arange(hours) * 2 * np.pi / 24 + np.pi)
    elec_price += np.random.normal(0, 5, hours)
    elec_price = np.clip(elec_price, 20, 150)

    # Grid CO2 intensity (kg/MWh) - varies with renewable penetration
    co2_base = 400
    co2_amplitude = 100
    co2_intensity = co2_base + co2_amplitude * np.sin(np.arange(hours) * 2 * np.pi / 24)
    co2_intensity = np.clip(co2_intensity, 200, 600)

    # Waste heat availability (MW) - industrial process dependent
    waste_heat = 5 + 3 * np.sin(np.arange(hours) * 2 * np.pi / 24 + np.pi/4)
    waste_heat = np.clip(waste_heat, 0, 8)

    df = pd.DataFrame({
        'heat_demand_mw': demand,
        'elec_price_eur_mwh': elec_price,
        'co2_intensity_kg_mwh': co2_intensity,
        'waste_heat_mw': waste_heat,
    }, index=timestamps)

    return df


# ============================================================
# OEMOF MODEL BUILDER
# ============================================================

def build_oemof_model(config: OemofBenchmarkConfig, timeseries: pd.DataFrame,
                      solver='cbc', include_investment=True):
    """
    Build oemof-solph model equivalent to EnerGIS.

    Parameters
    ----------
    config : OemofBenchmarkConfig
        Configuration parameters
    timeseries : pd.DataFrame
        Input time series (heat demand, electricity price, etc.)
    solver : str
        Solver to use ('gurobi', 'cbc', 'glpk')
    include_investment : bool
        If True, include investment decisions (Planning Framework mode)
        If False, use fixed capacities (Rolling Horizon mode)

    Returns
    -------
    model : oemof.solph.Model
        Optimization model
    """

    print(f"\n{'='*60}")
    print(f"Building oemof-solph model")
    print(f"{'='*60}")
    print(f"  Time steps: {len(timeseries)}")
    print(f"  Investment mode: {include_investment}")
    print(f"  Solver: {solver}")

    # Create energy system
    date_time_index = timeseries.index
    energysystem = solph.EnergySystem(
        timeindex=date_time_index,
        infer_last_interval=False
    )

    # ============================================================
    # BUSES
    # ============================================================

    bus_heat = solph.Bus(label='bus_heat')
    bus_elec = solph.Bus(label='bus_electricity')
    bus_gas = solph.Bus(label='bus_gas')

    energysystem.add(bus_heat, bus_elec, bus_gas)

    # ============================================================
    # HEAT DEMAND (SINK)
    # ============================================================

    demand = solph.components.Sink(
        label='heat_demand',
        inputs={
            bus_heat: solph.Flow(
                fix=timeseries['heat_demand_mw'],
                nominal_value=1
            )
        }
    )
    energysystem.add(demand)

    # ============================================================
    # ELECTRICITY GRID (SOURCE & SINK)
    # ============================================================

    # Grid import (buy electricity)
    grid_import = solph.components.Source(
        label='grid_import',
        outputs={
            bus_elec: solph.Flow(
                variable_costs=timeseries['elec_price_eur_mwh'],
                nominal_value=config.grid['cap_max_mw']
            )
        }
    )
    energysystem.add(grid_import)

    # Grid export (sell electricity) - typically not profitable, but possible
    grid_export = solph.components.Sink(
        label='grid_export',
        inputs={
            bus_elec: solph.Flow(
                variable_costs=-timeseries['elec_price_eur_mwh'] * 0.5,  # Sell at 50% of buy price
                nominal_value=config.grid['cap_max_mw']
            )
        }
    )
    energysystem.add(grid_export)

    # ============================================================
    # GAS SUPPLY (SOURCE)
    # ============================================================

    gas_source = solph.components.Source(
        label='gas_supply',
        outputs={
            bus_gas: solph.Flow(
                variable_costs=config.fuel_prices['gas_eur_mwh']
            )
        }
    )
    energysystem.add(gas_source)

    # ============================================================
    # HEAT PUMPS (CONVERTERS WITH INVESTMENT)
    # ============================================================

    for hp_name, hp_params in config.heat_pumps.items():
        if include_investment:
            # Investment mode: optimize capacity
            epc = config.annualized_capex(
                hp_params['inv_cost_eur_kw'] * 1000,  # EUR/kW -> EUR/MW
                hp_params['lifetime']
            )

            heat_pump = solph.components.Converter(
                label=f'hp_{hp_name.lower()}',
                inputs={bus_elec: solph.Flow()},
                outputs={
                    bus_heat: solph.Flow(
                        variable_costs=hp_params['opex_var_eur_mwh'],
                        nominal_value=solph.Investment(
                            ep_costs=epc,
                            maximum=hp_params['cap_max_mw'],
                            minimum=0,
                            existing=0
                        )
                    )
                },
                conversion_factors={bus_heat: hp_params['cop']}
            )
        else:
            # Fixed capacity mode (for Rolling Horizon after PF)
            heat_pump = solph.components.Converter(
                label=f'hp_{hp_name.lower()}',
                inputs={bus_elec: solph.Flow()},
                outputs={
                    bus_heat: solph.Flow(
                        variable_costs=hp_params['opex_var_eur_mwh'],
                        nominal_value=hp_params['cap_max_mw']  # Use max as fixed capacity
                    )
                },
                conversion_factors={bus_heat: hp_params['cop']}
            )

        energysystem.add(heat_pump)

    # ============================================================
    # CHP (COMBINED HEAT AND POWER)
    # ============================================================

    for chp_name, chp_params in config.chp.items():
        if include_investment:
            epc = config.annualized_capex(
                chp_params['inv_cost_eur_kw'] * 1000,
                chp_params['lifetime']
            )

            chp_unit = solph.components.GenericCHP(
                label=f'chp_{chp_name.lower()}',
                fuel_input={bus_gas: solph.Flow()},
                electrical_output={
                    bus_elec: solph.Flow(
                        nominal_value=solph.Investment(
                            ep_costs=epc * chp_params['alpha'],  # Allocate cost by power ratio
                            maximum=chp_params['cap_th_mw'] * chp_params['alpha'],
                            minimum=0,
                            existing=0
                        )
                    )
                },
                heat_output={
                    bus_heat: solph.Flow(
                        variable_costs=chp_params['opex_var_eur_mwh'],
                        nominal_value=solph.Investment(
                            ep_costs=epc * (1 - chp_params['alpha']),
                            maximum=chp_params['cap_th_mw'],
                            minimum=0,
                            existing=0
                        )
                    )
                },
                beta=chp_params['eta_el'] / chp_params['eta_th'],  # Power loss index
                back_pressure=False
            )
        else:
            chp_unit = solph.components.GenericCHP(
                label=f'chp_{chp_name.lower()}',
                fuel_input={bus_gas: solph.Flow()},
                electrical_output={
                    bus_elec: solph.Flow(
                        nominal_value=chp_params['cap_th_mw'] * chp_params['alpha']
                    )
                },
                heat_output={
                    bus_heat: solph.Flow(
                        variable_costs=chp_params['opex_var_eur_mwh'],
                        nominal_value=chp_params['cap_th_mw']
                    )
                },
                beta=chp_params['eta_el'] / chp_params['eta_th'],
                back_pressure=False
            )

        energysystem.add(chp_unit)

    # ============================================================
    # BOILER (BACKUP)
    # ============================================================

    for boiler_name, boiler_params in config.boiler.items():
        if include_investment:
            epc = config.annualized_capex(
                boiler_params['inv_cost_eur_kw'] * 1000,
                boiler_params['lifetime']
            )

            boiler = solph.components.Converter(
                label=f'boiler_{boiler_name.lower()}',
                inputs={bus_gas: solph.Flow()},
                outputs={
                    bus_heat: solph.Flow(
                        variable_costs=boiler_params['opex_var_eur_mwh'],
                        nominal_value=solph.Investment(
                            ep_costs=epc,
                            maximum=boiler_params['cap_th_mw'],
                            minimum=0,
                            existing=0
                        )
                    )
                },
                conversion_factors={bus_heat: boiler_params['eta_th']}
            )
        else:
            boiler = solph.components.Converter(
                label=f'boiler_{boiler_name.lower()}',
                inputs={bus_gas: solph.Flow()},
                outputs={
                    bus_heat: solph.Flow(
                        variable_costs=boiler_params['opex_var_eur_mwh'],
                        nominal_value=boiler_params['cap_th_mw']
                    )
                },
                conversion_factors={bus_heat: boiler_params['eta_th']}
            )

        energysystem.add(boiler)

    # ============================================================
    # THERMAL ENERGY STORAGE
    # ============================================================

    for storage_name, storage_params in config.storage.items():
        if include_investment:
            epc_energy = config.annualized_capex(
                storage_params['inv_cost_energy_eur_kwh'] * 1000,  # EUR/kWh -> EUR/MWh
                storage_params['lifetime']
            )
            epc_power = config.annualized_capex(
                storage_params['inv_cost_power_eur_kw'] * 1000,  # EUR/kW -> EUR/MW
                storage_params['lifetime']
            )

            storage = solph.components.GenericStorage(
                label=f'storage_{storage_name.lower()}',
                inputs={bus_heat: solph.Flow()},
                outputs={bus_heat: solph.Flow()},
                nominal_storage_capacity=solph.Investment(
                    ep_costs=epc_energy,
                    maximum=storage_params['energy_max_mwh'],
                    minimum=0,
                    existing=0
                ),
                invest_relation_input_capacity=1 / storage_params['energy_max_mwh'] * storage_params['power_max_mw'],
                invest_relation_output_capacity=1 / storage_params['energy_max_mwh'] * storage_params['power_max_mw'],
                inflow_conversion_factor=storage_params['eta_in'],
                outflow_conversion_factor=storage_params['eta_out'],
                loss_rate=storage_params['loss_rate_per_hour'],
                initial_storage_level=0.5,  # Start at 50%
                balanced=True  # Equal start and end SOC (for full-year optimization)
            )
        else:
            storage = solph.components.GenericStorage(
                label=f'storage_{storage_name.lower()}',
                inputs={bus_heat: solph.Flow(nominal_value=storage_params['power_max_mw'])},
                outputs={bus_heat: solph.Flow(nominal_value=storage_params['power_max_mw'])},
                nominal_storage_capacity=storage_params['energy_max_mwh'],
                inflow_conversion_factor=storage_params['eta_in'],
                outflow_conversion_factor=storage_params['eta_out'],
                loss_rate=storage_params['loss_rate_per_hour'],
                initial_storage_level=0.5,
                balanced=False  # For rolling horizon, may not balance
            )

        energysystem.add(storage)

    # ============================================================
    # CREATE OPTIMIZATION MODEL
    # ============================================================

    print(f"\nCreating optimization model...")
    model = solph.Model(energysystem)

    # Model statistics
    print(f"  Variables: {model.nvariables()}")
    print(f"  Constraints: {model.nconstraints()}")

    return model


# ============================================================
# SOLVE AND EXTRACT RESULTS
# ============================================================

def solve_oemof_model(model, solver='cbc', solver_options=None):
    """
    Solve the oemof model and return results.

    Parameters
    ----------
    model : oemof.solph.Model
        Optimization model
    solver : str
        Solver name
    solver_options : dict, optional
        Solver-specific options

    Returns
    -------
    results : dict
        Solver results
    solve_time : float
        Solver runtime in seconds
    """
    if solver_options is None:
        solver_options = {}

    print(f"\n{'='*60}")
    print(f"Solving model with {solver}...")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        model.solve(
            solver=solver,
            solve_kwargs={'tee': True},  # Show solver output
            **solver_options
        )
        solve_time = time.time() - start_time

        print(f"\n✓ Solved in {solve_time:.2f} seconds")
        print(f"  Objective value: {model.objective():.2f} EUR/year")
        print(f"  Termination condition: {model.solver_results.solver.termination_condition}")

        # Extract results
        results = views.convert_keys_to_strings(model.results())

        return results, solve_time

    except Exception as e:
        print(f"\n✗ Solver failed: {e}")
        raise


def extract_capacities(results):
    """Extract installed capacities from investment results."""
    capacities = {}

    for key, value in results.items():
        if isinstance(key, tuple) and 'scalars' in value:
            scalars = value['scalars']
            if 'invest' in scalars:
                component_name = key[0]
                capacity = scalars['invest']
                capacities[component_name] = capacity

    return capacities


def extract_dispatch(results, component_names):
    """Extract hourly dispatch for specified components."""
    dispatch = {}

    for comp_name in component_names:
        for key, value in results.items():
            if isinstance(key, tuple) and comp_name in key[0]:
                if 'sequences' in value:
                    dispatch[comp_name] = value['sequences']

    return dispatch


# ============================================================
# MAIN BENCHMARK FUNCTION
# ============================================================

def run_oemof_benchmark(hours=168, solver='cbc', output_dir=None):
    """
    Run complete oemof benchmark for comparison with EnerGIS.

    Parameters
    ----------
    hours : int
        Time horizon in hours
    solver : str
        Solver to use
    output_dir : Path, optional
        Directory to save results

    Returns
    -------
    results_dict : dict
        Complete results including capacities, dispatch, costs, timing
    """
    if not OEMOF_AVAILABLE:
        raise ImportError("oemof.solph not installed")

    print(f"\n{'#'*70}")
    print(f"# oemof-solph Benchmark")
    print(f"{'#'*70}")
    print(f"  Horizon: {hours} hours")
    print(f"  Solver: {solver}")

    # Setup
    config = OemofBenchmarkConfig(hours=hours)
    timeseries = generate_synthetic_timeseries(hours=hours)

    # Build model
    build_start = time.time()
    model = build_oemof_model(config, timeseries, solver=solver, include_investment=True)
    build_time = time.time() - build_start

    # Solve model
    results, solve_time = solve_oemof_model(model, solver=solver)

    # Extract results
    capacities = extract_capacities(results)

    # Compile results
    results_dict = {
        'framework': 'oemof',
        'hours': hours,
        'solver': solver,
        'build_time_s': build_time,
        'solve_time_s': solve_time,
        'total_time_s': build_time + solve_time,
        'objective_value': model.objective(),
        'n_variables': model.nvariables(),
        'n_constraints': model.nconstraints(),
        'capacities': capacities,
        'termination_condition': str(model.solver_results.solver.termination_condition),
    }

    # Save results
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON
        with open(output_dir / f'oemof_benchmark_{hours}h.json', 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)

        # Save capacities
        pd.DataFrame([capacities]).to_csv(
            output_dir / f'oemof_capacities_{hours}h.csv',
            index=False
        )

        print(f"\n✓ Results saved to {output_dir}")

    return results_dict


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run oemof benchmark')
    parser.add_argument('--hours', type=int, default=168, help='Time horizon (hours)')
    parser.add_argument('--solver', type=str, default='cbc', help='Solver (gurobi, cbc, glpk)')
    parser.add_argument('--output', type=str, default='results/oemof', help='Output directory')

    args = parser.parse_args()

    try:
        results = run_oemof_benchmark(
            hours=args.hours,
            solver=args.solver,
            output_dir=args.output
        )

        print(f"\n{'='*70}")
        print(f"BENCHMARK COMPLETE")
        print(f"{'='*70}")
        print(f"  Objective: {results['objective_value']:.2f} EUR/year")
        print(f"  Build time: {results['build_time_s']:.2f} s")
        print(f"  Solve time: {results['solve_time_s']:.2f} s")
        print(f"  Total time: {results['total_time_s']:.2f} s")
        print(f"\nInstalled Capacities:")
        for comp, cap in results['capacities'].items():
            print(f"  {comp}: {cap:.2f} MW")

    except Exception as e:
        print(f"\n✗ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()

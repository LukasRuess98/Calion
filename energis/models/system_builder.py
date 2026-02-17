from __future__ import annotations

from typing import Dict, Any, List, Optional, Sequence
import math

from energis.logging_config import get_logger

logger = get_logger(__name__)

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_PYOMO = False
    pyo = None

from energis.constants import (
    COP_MIN,
    COP_MAX_SYSTEM_BUILDER,
    COP_DEFAULT,
    COP_DELTA_T_K,
    HOURS_PER_YEAR,
    DEFAULT_LIFETIME_YEARS,
)
from energis.utils.timeseries import TimeSeriesTable
from energis.utils.config_utils import (
    apply_heat_pump_defaults,
    normalize_storage_config,
    normalize_thermal_network_config,
)
from .cop_calculator import calculate_cop_series
from .constraint_builder import (
    add_bus_balance_constraints,
    add_grid_market_constraints,
    create_objective,
)
from .config_schema import (
    InvestmentConfig,
    HeatPumpConfig,
    StorageConfig,
    ThermalGeneratorConfig,
    P2HConfig,
    CostConfig,
    extract_component_configs,
)
from .cost_calculator import (
    calculate_energy_costs,
    calculate_co2_costs,
    calculate_demand_charge,
    calculate_investment_costs,
    calculate_fuel_costs,
    calculate_dump_costs,
    aggregate_co2_emissions,
    store_cost_expressions_on_model,
)
from .blocks.heat_pump import HeatPumpBlock
from .blocks.storage import StorageBlock
from .blocks.stratified_storage import StratifiedStorageBlock
from .blocks.thermal_gen import ThermalGeneratorBlock
from .blocks.p2h import P2HBlock
from .network_manager import NetworkManager
from .investment_calculator import (
    InvestmentCalculator,
    ComponentInvestmentConfig,
    StorageInvestmentConfig,
)
from .emissions_calculator import EmissionsCalculator, aggregate_emission_results
from .component_assembler import ComponentAssembler
from pathlib import Path


# COP calculation has been moved to energis.models.cop_calculator
# This compatibility function remains for backwards compatibility
def _cop_series_from_table(
    table: TimeSeriesTable, wrg_col: str | None, cfg: Dict[str, Any], hp_type: str
) -> List[float]:
    """Calculate heat pump COP (Coefficient of Performance) time series.

    DEPRECATED: This function has been moved to energis.models.cop_calculator.calculate_cop_series()
    This wrapper remains for backwards compatibility and will be removed in v2.1.0.

    See energis.models.cop_calculator.calculate_cop_series() for full documentation.
    """
    return calculate_cop_series(table, wrg_col, cfg, hp_type)




def build_model(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float = 1.0,
    *,
    soc_init_override: float | None = None,
    terminal_target_override: float | None = None,
):
    """Build a Pyomo ConcreteModel for the energy system optimization.

    This is the main model builder that constructs a Mixed-Integer Linear Programming (MILP)
    model for industrial heat network planning. It creates decision variables, constraints,
    and the objective function based on the configuration and time series data.

    The model includes:
    - Heat pumps with COP series and waste heat recovery
    - Thermal energy storage with power/energy decoupling
    - Combined heat and power (CHP) generators
    - Power-to-heat converters
    - Multiple bus types (electricity, heat, gas, biomass, waste)
    - Investment decisions with CAPEX/OPEX modeling
    - Grid electricity purchase with demand charges and CO2 costs

    Args:
        table (TimeSeriesTable): Time series data containing demand profiles, weather data,
            and other input time series. Must have datetime index.
        cfg (Dict[str, Any]): Configuration dictionary with system topology, technology
            parameters, and scenario settings. See configs/ for structure.
        dt_h (float, optional): Time step duration in hours. Defaults to 1.0.

    Returns:
        pyo.ConcreteModel | None: Pyomo optimization model ready for solving, or None if
            Pyomo is not available. The model includes:
            - Decision variables for flows, capacities, and investment decisions
            - Constraints for energy balances, component limits, and operational rules
            - Objective function minimizing total system cost

    Raises:
        ValueError: If configuration is invalid or incompatible
        RuntimeError: If heat pump or storage definitions are incomplete

    Example:
        >>> table = load_input_excel("data/Import_Data.xlsx")
        >>> cfg = load_and_merge(["configs/base.yaml", "configs/systems/baseline.system.yaml"])
        >>> model = build_model(table, cfg, dt_h=1.0)
        >>> solver = pyo.SolverFactory("gurobi")
        >>> result = solver.solve(model)
    """
    if not HAVE_PYOMO:
        return None

    T = len(table)
    m = pyo.ConcreteModel(name="EnerGIS_FuelBus")
    m.t = pyo.RangeSet(1, T)
    period_frac = float(T * dt_h / HOURS_PER_YEAR)

    def series_dict(name: str) -> Dict[int, float]:
        values = table[name]
        return {i + 1: float(values[i]) for i in range(T)}

    def column_series(name: str) -> List[float] | None:
        if name in table.columns:
            return [float(table[name][i]) for i in range(T)]
        return None

    m.price = pyo.Param(m.t, initialize=series_dict("strompreis_EUR_MWh"), mutable=True)
    m.heatd = pyo.Param(m.t, initialize=series_dict("waermebedarf_MWth"), mutable=True)
    m.grid_co2 = pyo.Param(m.t, initialize=series_dict("grid_co2_kg_MWh"), mutable=True)

    # Outdoor temperature for heating curve (if available in data)
    outdoor_temp_series = column_series("outdoor_temp_C")
    if outdoor_temp_series is not None:
        m.outdoor_temp = {i + 1: float(outdoor_temp_series[i]) for i in range(T)}
        logger.info(f"Outdoor temperature loaded: {min(outdoor_temp_series):.1f}°C to {max(outdoor_temp_series):.1f}°C")
    else:
        m.outdoor_temp = None  # Will be set by NetworkManager if needed

    costs = cfg.get("costs", {})
    grid = cfg.get("grid", {})
    m.energy_fee = pyo.Param(initialize=float(grid.get("energy_fee_eur_mwh", 0.0)))
    m.grid_cost = pyo.Param(initialize=float(grid.get("gridcost_eur_mwh", 0.0)))
    m.sell_floor = pyo.Param(initialize=float(grid.get("sell_floor_eur_mwh", 0.0)))
    m.sell_haircut = pyo.Param(initialize=float(grid.get("sell_haircut_fraction", 0.0)))
    m.sell_spread = pyo.Param(initialize=float(grid.get("sell_spread_eur_mwh", 0.0)))
    m.sell_fee = pyo.Param(initialize=float(grid.get("sell_fee_eur_mwh", 0.0)))
    m.sell_premium = pyo.Param(initialize=float(grid.get("sell_premium_eur_mwh", 0.0)))
    m.M_GRID = pyo.Param(initialize=float(grid.get("big_m_grid_mw", 1e4)))
    max_import = grid.get("max_import_mw")
    max_export = grid.get("max_export_mw")
    m.max_import = pyo.Param(
        initialize=float(max_import if max_import is not None else m.M_GRID.value)
    )
    m.max_export = pyo.Param(
        initialize=float(max_export if max_export is not None else m.M_GRID.value)
    )
    m.year_frac = pyo.Param(initialize=float(grid.get("year_fraction", period_frac)))
    m.co2_price = pyo.Param(initialize=float(costs.get("co2_price_eur_per_t", 100.0)))
    m.dump_cost = pyo.Param(initialize=float(costs.get("dump_cost_eur_per_mwh_th", 1.0)))
    m.demand_charge_y = pyo.Param(initialize=float(grid.get("demand_charge_eur_per_mw_y", 0.0)))

    include_gridcost = bool(costs.get("include_gridcost_in_energy", False))
    include_demand = bool(grid.get("include_demand_charge_in_rh", costs.get("include_demand_charge_in_rh", True)))
    include_co2 = bool(costs.get("include_co2_cost_in_objective", True))
    include_capex_costs = bool(costs.get("include_capex_costs", True))
    include_activation_costs = bool(costs.get("include_activation_costs", True))
    include_tie_breaker_costs = bool(costs.get("include_tie_breaker_costs", True))
    include_storage_install_costs = bool(costs.get("include_storage_installation_costs", True))

    # Investment calculator service - centralizes annualization and cost flag logic
    inv_calc = InvestmentCalculator(
        period_frac=period_frac,
        include_capex=include_capex_costs,
        include_activation=include_activation_costs,
        include_tie_breaker=include_tie_breaker_costs,
        include_storage_install=include_storage_install_costs,
    )

    # Emissions calculator service - centralizes CO2 tracking logic
    # Uses 0-indexed grid CO2 series (matches table indexing used in original code)
    grid_co2_series_dict = {i: float(table["grid_co2_kg_MWh"][i]) for i in range(T)}
    co2_calc = EmissionsCalculator(
        co2_price_param=m.co2_price,
        grid_co2_series=grid_co2_series_dict,
        dt_h=dt_h,
        time_set=m.t,
    )

    fuels = cfg.get("fuels", {})

    def pfuel(key: str, default: float = 0.0) -> float:
        return float(fuels.get(key, {}).get("price_eur_mwh", default))

    def efuel(key: str, default: float = 0.0) -> float:
        return float(fuels.get(key, {}).get("ef_kg_per_mwh_fuel", default))

    m.P_buy = pyo.Var(m.t, domain=pyo.NonNegativeReals)
    m.P_sell = pyo.Var(m.t, domain=pyo.NonNegativeReals)
    m.grid_mode = pyo.Var(m.t, domain=pyo.Binary)
    m.Q_dump = pyo.Var(m.t, domain=pyo.NonNegativeReals)

    # Dictionary for export (component-specific CO2 breakdowns)
    m.co2_component_costs = {}

    # ─── Component Assembly ────────────────────────────────────────────────────
    assembler = ComponentAssembler(m, m.t, table, cfg, dt_h, inv_calc, co2_calc)
    assembler.assemble_heat_pumps()
    assembler.assemble_storage(soc_init_override, terminal_target_override)
    assembler.assemble_thermal_generators()

    buses = assembler.buses
    el_in = buses.el_in
    el_out = buses.el_out
    ht_in = buses.ht_in
    ht_out = buses.ht_out
    capex_terms = buses.capex_terms
    activation_terms = buses.activation_terms
    tie_breaker_terms = buses.tie_breaker_terms
    storage_install_terms = buses.storage_install_terms
    fuel_cost_terms = buses.fuel_cost_terms
    fuel_co2_terms = buses.fuel_co2_terms

    # (legacy) gas_in / bio_in / waste_in are accumulated inside assembler but
    # not used outside it — bus balance only uses el_in/out, ht_in/out.

    if not ht_out:
        raise RuntimeError(
            "No thermal generator connected to heat bus (ht_out empty). Please check system configuration."
        )
    logger.info("[BUILD] #el_in=%d, #el_out=%d, #ht_out=%d, #ht_in=%d",
                len(el_in), len(el_out), len(ht_out), len(ht_in))

    # ========================================
    # THERMAL NETWORK INTEGRATION
    # ========================================
    # Normalize thermal_network config (supports both old and new structure)
    network_cfg = normalize_thermal_network_config(cfg)
    network_enabled = network_cfg.get('enabled', False)

    if network_enabled:
        logger.info("[BUILD] Integrating thermal network...")

        # Get config directory from cfg if available, otherwise use current directory
        config_dir = cfg.get('_config_dir', Path.cwd())
        if not isinstance(config_dir, Path):
            config_dir = Path(config_dir) if config_dir else Path.cwd()

        # Check if outdoor temperature is available for heating curve
        has_outdoor_temp = hasattr(m, 'outdoor_temp') and m.outdoor_temp is not None
        if has_outdoor_temp:
            # Enable outdoor temperature usage in network config
            network_cfg.setdefault('use_outdoor_temperature', True)
            logger.info("[BUILD] Outdoor temperature available - heating curve enabled")
        else:
            logger.info("[BUILD] No outdoor temperature data - using fixed supply temperature")

        # Inject normalized network config back into cfg for NetworkManager
        cfg_with_network = dict(cfg)
        cfg_with_network['thermal_network'] = network_cfg

        try:
            network_mgr = NetworkManager(cfg_with_network, config_dir=config_dir)

            # Check if network was actually loaded successfully
            if not network_mgr.network_enabled:
                logger.info(f"[BUILD] WARNING: Thermal network failed to load (check topology file)")
                logger.info(f"[BUILD] Continuing without thermal network...")
                m._network_enabled = False
            else:
                # Create buses dict for network integration
                buses = {
                    'heat': {'in': ht_in, 'out': ht_out},
                    'electricity': {'in': el_in, 'out': el_out}
                }

                # Attach network to model
                network_results = network_mgr.attach_to_model(m, m.t, buses)

                # Verify that network actually attached (not just returned empty dict)
                if network_results and len(network_results.get('pipes', {})) > 0:
                    # Store network manager for results extraction
                    m._network_manager = network_mgr
                    m._network_enabled = True
                    logger.info(f"[BUILD] Thermal network integrated successfully:")
                    print(f"         {len(network_results.get('pipes', {}))} pipes, "
                          f"{len(network_results.get('nodes', {}))} nodes")
                else:
                    logger.info(f"[BUILD] WARNING: Thermal network returned no components")
                    logger.info(f"[BUILD] Continuing without thermal network...")
                    m._network_enabled = False

        except Exception as e:
            logger.info(f"[BUILD] ERROR: Failed to integrate thermal network: {e}")
            logger.info(f"[BUILD] Continuing without thermal network...")
            m._network_enabled = False
            import traceback
            traceback.print_exc()
    else:
        m._network_enabled = False
        logger.info("[BUILD] Thermal network disabled")

    # ========================================
    # BUS BALANCE CONSTRAINTS
    # ========================================
    add_bus_balance_constraints(m, el_in, el_out, ht_in, ht_out)

    # ========================================
    # GRID MARKET CONSTRAINTS
    # ========================================
    add_grid_market_constraints(m)

    # ========================================
    # ENERGY COSTS (Grid Buy/Sell)
    # ========================================
    base_prices = [float(table["strompreis_EUR_MWh"][i]) for i in range(T)]
    time_steps = list(m.t)
    energy_cost = calculate_energy_costs(
        m, time_steps, base_prices, dt_h=dt_h, include_grid_cost=include_gridcost
    )

    # ========================================
    # DUMP COSTS
    # ========================================
    dump_cost = calculate_dump_costs(
        m, time_steps, dt_h=dt_h, dump_cost_eur_per_mwh=float(m.dump_cost.value)
    )
    # ========================================
    # FUEL COSTS
    # ========================================
    fuel_costs = calculate_fuel_costs(fuel_cost_terms)

    # ========================================
    # CO2 COSTS AND EMISSIONS
    # ========================================
    # Calculate CO2 costs with heat/electricity breakdown
    co2_cost_total, co2_cost_heat_total, co2_cost_elec_total = calculate_co2_costs(
        m.co2_component_costs, co2_price_eur_per_t=float(m.co2_price.value)
    )

    # Aggregate CO2 emissions by category
    co2_kg_heat_total, co2_kg_elec_total, co2_kg_fuel_heat, co2_kg_fuel_elec, co2_kg_grid_elec = aggregate_co2_emissions(
        m.co2_component_costs
    )

    # Store expressions on model for export and reporting
    store_cost_expressions_on_model(
        m,
        co2_cost_total=co2_cost_total,
        co2_cost_heat=co2_cost_heat_total,
        co2_cost_elec=co2_cost_elec_total,
        co2_kg_heat=co2_kg_heat_total,
        co2_kg_elec=co2_kg_elec_total,
        co2_kg_fuel_to_heat=co2_kg_fuel_heat,
        co2_kg_fuel_to_elec=co2_kg_fuel_elec,
        co2_kg_grid_to_elec=co2_kg_grid_elec,
    )

    # Legacy compatibility: Total CO2 in kg (for old reports)
    co2_grid = sum(m.P_buy[t] * table["grid_co2_kg_MWh"][t - 1] * dt_h for t in m.t)
    co2_fuel = sum(fuel_co2_terms) if fuel_co2_terms else 0

    # ========================================
    # DEMAND CHARGE
    # ========================================
    demand_term = calculate_demand_charge(m, include_demand=include_demand)

    # ========================================
    # INVESTMENT COSTS (CAPEX)
    # ========================================
    capex_total, activation_total, tie_break_total, storage_install_total = calculate_investment_costs(
        capex_terms=capex_terms,
        activation_terms=activation_terms,
        tie_breaker_terms=tie_breaker_terms,
        storage_install_terms=storage_install_terms,
        include_capex=include_capex_costs,
        include_activation=include_activation_costs,
        include_tie_breaker=include_tie_breaker_costs,
    )

    # CO2 cost term (conditional on include_co2 flag)
    co2_term = co2_cost_total if include_co2 else 0

    # Terminal value term (for value/soft terminal policies in Rolling Horizon)
    terminal_value = getattr(m, 'terminal_value_term', None)
    if terminal_value is None:
        terminal_value = 0

    create_objective(
        m,
        energy_cost=energy_cost,
        dump_cost=dump_cost,
        fuel_costs=fuel_costs,
        co2_cost=co2_term,
        demand_cost=demand_term,
        capex_cost=capex_total,
        activation_cost=activation_total,
        tie_break_cost=tie_break_total,
        storage_install_cost=storage_install_total,
        terminal_value=terminal_value,
    )
    return m


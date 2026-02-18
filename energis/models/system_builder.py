from __future__ import annotations

from typing import Dict, Any, List

from energis.logging_config import get_logger

logger = get_logger(__name__)

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_PYOMO = False
    pyo = None

from energis.constants import HOURS_PER_YEAR
from energis.utils.timeseries import TimeSeriesTable
from .investment_calculator import InvestmentCalculator
from .emissions_calculator import EmissionsCalculator
from .component_assembler import ComponentAssembler
from .model_finalizer import ModelFinalizer, CostFlags
from .cop_calculator import calculate_cop_series


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

    # Cost flags drive both InvestmentCalculator and ModelFinalizer
    flags = CostFlags.from_config(cfg)

    inv_calc = InvestmentCalculator(
        period_frac=period_frac,
        include_capex=flags.include_capex,
        include_activation=flags.include_activation,
        include_tie_breaker=flags.include_tie_breaker,
        include_storage_install=flags.include_storage_install,
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

    if not buses.ht_out:
        logger.warning(
            "No thermal generator connected to heat bus (ht_out empty). "
            "Heat balance constraints will be trivially satisfied."
        )
    logger.info("[BUILD] #el_in=%d, #el_out=%d, #ht_out=%d, #ht_in=%d",
                len(buses.el_in), len(buses.el_out), len(buses.ht_out), len(buses.ht_in))

    # ─── Model Finalization ────────────────────────────────────────────────────
    finalizer = ModelFinalizer(m, cfg, table, buses, dt_h, flags)
    finalizer.integrate_network()
    finalizer.add_balance_constraints()
    finalizer.build_and_set_objective()

    return m


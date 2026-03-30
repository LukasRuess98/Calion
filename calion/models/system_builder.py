from __future__ import annotations

from typing import Dict, Any, List, Optional

from calion.logging_config import get_logger

logger = get_logger(__name__)

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_PYOMO = False
    pyo = None

from calion.constants import (
    BIG_M_GRID_MW,
    DEFAULT_CO2_PRICE_EUR_PER_T,
    DEFAULT_DUMP_COST_EUR_PER_MWH_TH,
    HOURS_PER_YEAR,
)
from calion.utils.timeseries import TimeSeriesTable
from .investment_calculator import InvestmentCalculator
from .emissions_calculator import EmissionsCalculator
from .component_assembler import ComponentAssembler, BusConnections, SystemBusConnections
from .model_finalizer import ModelFinalizer, CostFlags
from .cop_calculator import calculate_cop_series


def _is_unified_config(cfg: Dict[str, Any]) -> bool:
    """Check whether ``cfg`` uses the new unified format (has ``network.nodes`` + ``assets``)."""
    return (
        isinstance(cfg.get("assets"), dict)
        and isinstance(cfg.get("network", {}).get("nodes"), dict)
    )


def build_model(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float = 1.0,
    *,
    soc_init_override: float | None = None,
    terminal_target_override: float | None = None,
):
    """Build a Pyomo ConcreteModel for the energy system optimization.

    Supports two configuration formats:
    - **Unified format** (new): ``assets`` + ``network.nodes`` + optional ``network.pipes``
    - **Legacy format**: ``system.heat_pumps`` / ``system.storage`` / ``system.generators``

    The unified format is auto-detected by the presence of both ``assets`` and
    ``network.nodes`` keys.  When detected, assets are attached per-node and
    per-node heat balances are created for multi-node topologies.
    """
    if not HAVE_PYOMO:
        return None

    if _is_unified_config(cfg):
        return _build_model_unified(table, cfg, dt_h,
                                    soc_init_override=soc_init_override,
                                    terminal_target_override=terminal_target_override)
    return _build_model_legacy(table, cfg, dt_h,
                               soc_init_override=soc_init_override,
                               terminal_target_override=terminal_target_override)


# ─── Unified build path (new config) ─────────────────────────────────────────

def _build_model_unified(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float = 1.0,
    *,
    soc_init_override: float | None = None,
    terminal_target_override: float | None = None,
):
    """Build model from unified config with per-node asset placement."""
    from calion.config.unified_config import parse_unified_config

    ucfg = parse_unified_config(cfg)
    T = len(table)

    m = pyo.ConcreteModel(name="CALION_Unified")
    m.t = pyo.RangeSet(1, T)
    period_frac = float(T * dt_h / HOURS_PER_YEAR)

    def series_dict(name: str) -> Dict[int, float]:
        values = table[name]
        return {i + 1: float(values[i]) for i in range(T)}

    def column_series(name: str) -> Optional[List[float]]:
        if name in table.columns:
            return [float(table[name][i]) for i in range(T)]
        return None

    # ── Core time series parameters ───────────────────────────────────────
    m.price = pyo.Param(m.t, initialize=series_dict("strompreis_EUR_MWh"), mutable=True)
    m.grid_co2 = pyo.Param(m.t, initialize=series_dict("grid_co2_kg_MWh"), mutable=True)

    # ── Per-node demand or global demand ──────────────────────────────────
    if ucfg.is_copperplate:
        # Copperplate: single global demand parameter
        # Find the demand column from the single node (or nodes with demand)
        demand_col = None
        for node in ucfg.nodes.values():
            if node.demand is not None:
                demand_col = node.demand.column
                break
        if demand_col is None:
            # Fall back to legacy column name
            demand_col = "waermebedarf_MWth"

        # Map demand column to table column (fuzzy match)
        actual_col = _find_demand_column(table, demand_col)
        m.heatd = pyo.Param(
            m.t,
            initialize={i + 1: float(table[actual_col][i]) for i in range(T)},
            mutable=True,
        )
    else:
        # Multi-node: per-node demand parameters
        m.node_demand = {}
        for nid, node in ucfg.nodes.items():
            if node.demand is not None:
                actual_col = _find_demand_column(table, node.demand.column)
                demand_data = {i + 1: float(table[actual_col][i]) for i in range(T)}
                param_name = f"heatd_{nid}"
                setattr(m, param_name, pyo.Param(m.t, initialize=demand_data, mutable=True))
                m.node_demand[nid] = getattr(m, param_name)

        # Also create global m.heatd as sum of all node demands (for compatibility)
        all_demand_cols = []
        for node in ucfg.nodes.values():
            if node.demand is not None:
                actual_col = _find_demand_column(table, node.demand.column)
                all_demand_cols.append(actual_col)
        if all_demand_cols:
            global_demand = {
                i + 1: sum(float(table[col][i]) for col in all_demand_cols)
                for i in range(T)
            }
        else:
            global_demand = {i + 1: 0.0 for i in range(T)}
        m.heatd = pyo.Param(m.t, initialize=global_demand, mutable=True)

    # ── Outdoor temperature ───────────────────────────────────────────────
    outdoor_temp_series = column_series("outdoor_temp_C")
    if outdoor_temp_series is not None:
        m.outdoor_temp = {i + 1: float(outdoor_temp_series[i]) for i in range(T)}
    else:
        m.outdoor_temp = None

    # ── Grid / cost parameters ────────────────────────────────────────────
    costs = ucfg.costs
    grid = ucfg.grid
    m.energy_fee = pyo.Param(initialize=float(grid.get("energy_fee_eur_mwh", 0.0)))
    m.grid_cost = pyo.Param(initialize=float(grid.get("gridcost_eur_mwh", 0.0)))
    m.sell_floor = pyo.Param(initialize=float(grid.get("sell_floor_eur_mwh", 0.0)))
    m.sell_haircut = pyo.Param(initialize=float(grid.get("sell_haircut_fraction", 0.0)))
    m.sell_spread = pyo.Param(initialize=float(grid.get("sell_spread_eur_mwh", 0.0)))
    m.sell_fee = pyo.Param(initialize=float(grid.get("sell_fee_eur_mwh", 0.0)))
    m.sell_premium = pyo.Param(initialize=float(grid.get("sell_premium_eur_mwh", 0.0)))
    m.M_GRID = pyo.Param(initialize=float(grid.get("big_m_grid_mw", BIG_M_GRID_MW)))
    max_import = grid.get("max_import_mw")
    max_export = grid.get("max_export_mw")
    m.max_import = pyo.Param(
        initialize=float(max_import if max_import is not None else m.M_GRID.value)
    )
    m.max_export = pyo.Param(
        initialize=float(max_export if max_export is not None else m.M_GRID.value)
    )
    m.year_frac = pyo.Param(initialize=float(grid.get("year_fraction", period_frac)))
    m.co2_price = pyo.Param(initialize=float(costs.get("co2_price_eur_per_t", DEFAULT_CO2_PRICE_EUR_PER_T)))
    m.dump_cost = pyo.Param(initialize=float(costs.get("dump_cost_eur_per_mwh_th", DEFAULT_DUMP_COST_EUR_PER_MWH_TH)))
    m.demand_charge_y = pyo.Param(initialize=float(grid.get("demand_charge_eur_per_mw_y", 0.0)))

    flags = CostFlags.from_config(cfg)
    inv_calc = InvestmentCalculator(
        period_frac=period_frac,
        include_capex=flags.include_capex,
        include_activation=flags.include_activation,
        include_tie_breaker=flags.include_tie_breaker,
        include_storage_install=flags.include_storage_install,
    )

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
    m.co2_component_costs = {}

    # ── Component Assembly (unified path) ─────────────────────────────────
    assembler = ComponentAssembler(m, m.t, table, cfg, dt_h, inv_calc, co2_calc)
    sys_buses = assembler.assemble_all(ucfg)

    # Store unified config and system buses on model for export/inspection
    m._unified_config = ucfg
    m._system_buses = sys_buses

    # Flatten for compatibility with ModelFinalizer
    buses = sys_buses.to_flat_bus_connections()

    n_ht = sum(len(nb.ht_out) for nb in sys_buses.nodes.values())
    if n_ht == 0:
        logger.warning("No thermal generator connected to any node (ht_out empty).")
    logger.info(
        "[BUILD-UNIFIED] #el_in=%d, #el_out=%d, #ht_out(total)=%d, #ht_in(total)=%d, nodes=%d",
        len(sys_buses.el_in), len(sys_buses.el_out), n_ht,
        sum(len(nb.ht_in) for nb in sys_buses.nodes.values()),
        len(ucfg.nodes),
    )

    # ── Model Finalization ────────────────────────────────────────────────
    finalizer = ModelFinalizer(m, cfg, table, buses, dt_h, flags,
                               unified_config=ucfg, system_buses=sys_buses)
    finalizer.integrate_network()
    finalizer.add_balance_constraints()
    finalizer.build_and_set_objective()

    return m


# ─── Legacy build path (old config format) ───────────────────────────────────

def _build_model_legacy(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float = 1.0,
    *,
    soc_init_override: float | None = None,
    terminal_target_override: float | None = None,
):
    """Build model from legacy config (system.heat_pumps / generators / storage)."""
    T = len(table)
    m = pyo.ConcreteModel(name="CALION_FuelBus")
    m.t = pyo.RangeSet(1, T)
    period_frac = float(T * dt_h / HOURS_PER_YEAR)

    def series_dict(name: str) -> Dict[int, float]:
        values = table[name]
        return {i + 1: float(values[i]) for i in range(T)}

    def column_series(name: str) -> Optional[List[float]]:
        if name in table.columns:
            return [float(table[name][i]) for i in range(T)]
        return None

    m.price = pyo.Param(m.t, initialize=series_dict("strompreis_EUR_MWh"), mutable=True)
    m.heatd = pyo.Param(m.t, initialize=series_dict("waermebedarf_MWth"), mutable=True)
    m.grid_co2 = pyo.Param(m.t, initialize=series_dict("grid_co2_kg_MWh"), mutable=True)

    outdoor_temp_series = column_series("outdoor_temp_C")
    if outdoor_temp_series is not None:
        m.outdoor_temp = {i + 1: float(outdoor_temp_series[i]) for i in range(T)}
        logger.info(f"Outdoor temperature loaded: {min(outdoor_temp_series):.1f}°C to {max(outdoor_temp_series):.1f}°C")
    else:
        m.outdoor_temp = None

    costs = cfg.get("costs", {})
    grid = cfg.get("grid", {})
    m.energy_fee = pyo.Param(initialize=float(grid.get("energy_fee_eur_mwh", 0.0)))
    m.grid_cost = pyo.Param(initialize=float(grid.get("gridcost_eur_mwh", 0.0)))
    m.sell_floor = pyo.Param(initialize=float(grid.get("sell_floor_eur_mwh", 0.0)))
    m.sell_haircut = pyo.Param(initialize=float(grid.get("sell_haircut_fraction", 0.0)))
    m.sell_spread = pyo.Param(initialize=float(grid.get("sell_spread_eur_mwh", 0.0)))
    m.sell_fee = pyo.Param(initialize=float(grid.get("sell_fee_eur_mwh", 0.0)))
    m.sell_premium = pyo.Param(initialize=float(grid.get("sell_premium_eur_mwh", 0.0)))
    m.M_GRID = pyo.Param(initialize=float(grid.get("big_m_grid_mw", BIG_M_GRID_MW)))
    max_import = grid.get("max_import_mw")
    max_export = grid.get("max_export_mw")
    m.max_import = pyo.Param(
        initialize=float(max_import if max_import is not None else m.M_GRID.value)
    )
    m.max_export = pyo.Param(
        initialize=float(max_export if max_export is not None else m.M_GRID.value)
    )
    m.year_frac = pyo.Param(initialize=float(grid.get("year_fraction", period_frac)))
    m.co2_price = pyo.Param(initialize=float(costs.get("co2_price_eur_per_t", DEFAULT_CO2_PRICE_EUR_PER_T)))
    m.dump_cost = pyo.Param(initialize=float(costs.get("dump_cost_eur_per_mwh_th", DEFAULT_DUMP_COST_EUR_PER_MWH_TH)))
    m.demand_charge_y = pyo.Param(initialize=float(grid.get("demand_charge_eur_per_mw_y", 0.0)))

    flags = CostFlags.from_config(cfg)
    inv_calc = InvestmentCalculator(
        period_frac=period_frac,
        include_capex=flags.include_capex,
        include_activation=flags.include_activation,
        include_tie_breaker=flags.include_tie_breaker,
        include_storage_install=flags.include_storage_install,
    )

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
    m.co2_component_costs = {}

    # ─── Component Assembly (legacy path) ─────────────────────────────────
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

    # ─── Model Finalization ───────────────────────────────────────────────
    finalizer = ModelFinalizer(m, cfg, table, buses, dt_h, flags)
    finalizer.integrate_network()
    finalizer.add_balance_constraints()
    finalizer.build_and_set_objective()

    return m


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _find_demand_column(table: TimeSeriesTable, column_name: str) -> str:
    """Find the actual column name in the table, with fuzzy matching.

    Tries exact match first, then normalized match.
    """
    if column_name in table.columns:
        return column_name

    import re
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    target = _norm(column_name)
    for col in table.columns:
        if _norm(col) == target:
            return col
        if target in _norm(col) or _norm(col) in target:
            return col

    raise ValueError(
        f"Demand column '{column_name}' not found in data. "
        f"Available columns: {table.columns}"
    )

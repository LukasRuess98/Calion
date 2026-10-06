from __future__ import annotations

from typing import Any

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
    HYDRAULIC_SUSPENDED_HOURS,
)
from calion.utils.timeseries import TimeSeriesTable

from .component_assembler import ComponentAssembler
from .cost_resolver import CostResolver
from .emissions_calculator import EmissionsCalculator
from .investment_calculator import InvestmentCalculator
from .model_finalizer import CostFlags, ModelFinalizer


def _is_unified_config(cfg: dict[str, Any]) -> bool:
    """Check whether ``cfg`` uses the new unified format (has ``network.nodes`` + ``assets``)."""
    return (
        isinstance(cfg.get("assets"), dict)
        and isinstance(cfg.get("network", {}).get("nodes"), dict)
    )


def build_model(
    table: TimeSeriesTable,
    cfg: dict[str, Any],
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
    cfg: dict[str, Any],
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

    def series_dict(name: str) -> dict[int, float]:
        values = table[name]
        return {i + 1: float(values[i]) for i in range(T)}

    def column_series(name: str) -> list[float] | None:
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
            # Collect all demand columns for this node (singular + list).
            # Each entry keeps its own fraction; for legacy single-demand nodes
            # the node-level demand_fraction is the scaling factor.
            node_demand_specs = []
            if node.demand is not None:
                node_demand_specs.append((
                    _find_demand_column(table, node.demand.column),
                    node.demand.demand_fraction
                    if node.demand.demand_fraction is not None
                    else node.demand_fraction,
                ))
            for d in node.demands:
                node_demand_specs.append((
                    _find_demand_column(table, d.column),
                    d.demand_fraction
                    if d.demand_fraction is not None
                    else (node.demand_fraction if len(node.demands) == 1 else 1.0),
                ))
            if node_demand_specs:
                # For multi-consumer nodes, create indexed parameters
                if len(node_demand_specs) > 1:
                    for consumer_idx, (col, frac) in enumerate(node_demand_specs):
                        frac = 1.0 if frac is None else float(frac)
                        demand_data = {
                            i + 1: float(table[col][i]) * frac
                            for i in range(T)
                        }
                        param_name = f"heatd_{nid}_{consumer_idx}"
                        setattr(m, param_name, pyo.Param(m.t, initialize=demand_data, mutable=True))
                
                # Always create the aggregated parameter (for both single and multi-consumer)
                demand_data = {
                    i + 1: sum(
                        float(table[col][i]) * (1.0 if frac is None else float(frac))
                        for col, frac in node_demand_specs
                    )
                    for i in range(T)
                }
                param_name = f"heatd_{nid}"
                setattr(m, param_name, pyo.Param(m.t, initialize=demand_data, mutable=True))
                m.node_demand[nid] = getattr(m, param_name)

        # Also create global m.heatd as sum of all node demands (for compatibility)
        all_demand_specs = []
        for node in ucfg.nodes.values():
            if node.demand is not None:
                actual_col = _find_demand_column(table, node.demand.column)
                frac = (
                    node.demand.demand_fraction
                    if node.demand.demand_fraction is not None
                    else node.demand_fraction
                )
                all_demand_specs.append((actual_col, frac))
            for d in node.demands:
                all_demand_specs.append((
                    _find_demand_column(table, d.column),
                    d.demand_fraction
                    if d.demand_fraction is not None
                    else (node.demand_fraction if len(node.demands) == 1 else 1.0),
                ))
        if all_demand_specs:
            global_demand = {
                i + 1: sum(
                    float(table[col][i]) * (1.0 if frac is None else float(frac))
                    for col, frac in all_demand_specs
                )
                for i in range(T)
            }
        else:
            global_demand = {i + 1: 0.0 for i in range(T)}
        m.heatd = pyo.Param(m.t, initialize=global_demand, mutable=True)

    # ── Outdoor temperature ───────────────────────────────────────────────
    # Try multiple column names that the Excel might use for outdoor temperature.
    _OUTDOOR_TEMP_CANDIDATES = [
        "outdoor_temp_C", "outdoor_temp_c", "T_outdoor_C", "T_outdoor_c",
        "Aussentemperatur_C", "Aussentemperatur", "outdoor_temp",
        "T_aussen_C", "T_ambient_C", "ambient_temp_C",
    ]
    # Also honour explicit mapping in site.columns.outdoor_temp
    _outdoor_col_override = (
        ucfg.raw.get("site", {}).get("columns", {}).get("outdoor_temp")
    )
    if _outdoor_col_override:
        _OUTDOOR_TEMP_CANDIDATES = [_outdoor_col_override] + _OUTDOOR_TEMP_CANDIDATES
    outdoor_temp_series = None
    for _col in _OUTDOOR_TEMP_CANDIDATES:
        outdoor_temp_series = column_series(_col)
        if outdoor_temp_series is not None:
            logger.info("[BUILD-UNIFIED] Outdoor temperature loaded from column '%s'", _col)
            break
    if outdoor_temp_series is not None:
        m.outdoor_temp = {i + 1: float(outdoor_temp_series[i]) for i in range(T)}
    else:
        m.outdoor_temp = None
        logger.info("[BUILD-UNIFIED] No outdoor temperature column found — heating curve disabled")

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
    _dump_price = float(costs.get("dump_cost_eur_per_mwh_th", DEFAULT_DUMP_COST_EUR_PER_MWH_TH))
    # 2026-09-24 (B2, docs SS4az): env override so the B1a dump-price attribution experiment
    # (1000 vs 5 EUR/MWh) can be run WITHOUT ever editing the committed config (which holds the
    # post-B1a value, 5) -- every other run stays reproducible from the same file.
    import os as _os_dp
    _dump_price_env = _os_dp.environ.get('CALION_DUMP_PRICE_OVERRIDE')
    if _dump_price_env:
        logger.info("[B2] dump_cost_eur_per_mwh_th overridden %s -> %s (env)", _dump_price, _dump_price_env)
        _dump_price = float(_dump_price_env)
    m.dump_cost = pyo.Param(initialize=_dump_price)
    m.demand_charge_y = pyo.Param(initialize=float(grid.get("demand_charge_eur_per_mw_y", 0.0)))

    # ── Zonal demand charges (if configured) ───────────────────────────────
    m.zone_demand_charge = {}  # Dict[zone_id → Pyomo.Param]
    m.zone_demand_charge_values = {}  # Shadow dict for debugging/export (zone_id → float)
    m.zone_demand_charge_ts = None  # Will hold dynamic CSV costs if enabled
    
    # Check for zonal costs in costs_config (not in costs)
    costs_config = cfg.get("costs_config", {})
    if costs_config and "zones" in costs_config and costs_config["zones"]:
        try:
            cost_resolver = CostResolver(cfg, table)
            all_zone_costs = cost_resolver.get_all_zones_costs()
            
            # Create Pyomo parameters for each zone's demand charge
            for zone_id, zone_costs_dict in all_zone_costs.items():
                # Extract only the demand_charge_eur_per_mw_y for this zone
                charge_eur_per_mw_y = zone_costs_dict.get("demand_charge_eur_per_mw_y", 0.0)
                m.zone_demand_charge[zone_id] = pyo.Param(
                    initialize=float(charge_eur_per_mw_y)
                )
                m.zone_demand_charge_values[zone_id] = float(charge_eur_per_mw_y)
            
            # Log zone cost configuration
            if m.zone_demand_charge:
                logger.info(
                    "[BUILD-UNIFIED] Zone demand charges configured: %s",
                    m.zone_demand_charge_values
                )
            
            # If dynamic costs are enabled, store the full resolver for later use
            if costs_config.get("dynamic", {}).get("enabled", False):
                m.zone_demand_charge_ts = cost_resolver
                logger.info("[BUILD-UNIFIED] Dynamic zonal costs enabled (from CSV)")
        except Exception as e:
            logger.warning("[BUILD-UNIFIED] Failed to load zonal costs: %s. Using global costs.", e)

    flags = CostFlags.from_config(cfg)
    inv_calc = InvestmentCalculator(
        period_frac=period_frac,
        discount_rate=float(cfg.get("investment", {}).get("discount_rate", 0.0)),
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
    sys_buses = assembler.assemble_all(
        ucfg,
        soc_init_override=soc_init_override,
        terminal_target_override=terminal_target_override,
    )
    # Store unified config and system buses on model for export/inspection
    m._unified_config = ucfg
    m._system_buses = sys_buses

    # D1 active-assertion (2026-09-22, C3 "Notkuehler Ansatz B"): a chp_only run that attached the
    # per-CHP dump/capacity mechanism to ZERO generators (e.g. el_eff detection broke, or a
    # network genuinely has no CHP) is a silent no-op identical to legacy mode -- fail loudly.
    import os as _os_sb
    if _os_sb.environ.get('CALION_DUMP_MODE', 'legacy').strip().lower() == 'chp_only':
        _n_chp = len(getattr(sys_buses, 'chp_dump_terms', []) or [])
        logger.info("[DUMP-MODE] chp_only: %d CHP asset(s) got Q_dump_chp (emergency-cooler "
                    "capacity, bounded by their own thermal output)", _n_chp)
        assert _n_chp > 0, (
            "[DUMP-MODE] chp_only requested but 0 CHP assets received a Q_dump_chp mechanism -- "
            "the emergency-cooler capacity is a no-op, investigate before trusting results.")

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

    # E3 (2026-09-22, author decision, docs SS4au): "hydraulischen Constraint-Block fuer
    # die 3 Dezember-Stunden (8365-8367) vollstaendig aussetzen" -- per-node pressure-slack
    # widening (C1, CALION_PRESSURE_SLACK_MODE=preprocessed) was still LP-infeasible at
    # hour 8366 (IIS: whole propagation chain upstream of j_13 + an unrelated J7_TO_J8 PWL
    # segment, docs SS4at/SS4au) -- suspend the ENTIRE hydraulic/pressure constraint
    # family network-wide at exactly these 3 hours instead, identically in every scenario.
    # Post-hoc deactivation (not a per-rule env check) keeps this a single, centrally
    # audited mechanism instead of N scattered edits across pipe_pair.py/network_manager.py/
    # thermal_node.py/state_constraints.py.
    _hyd_mode = _os_sb.environ.get('CALION_PRESSURE_SLACK_MODE', 'objective').strip().lower()
    if _hyd_mode == 'suspend_hydraulic':
        _HYD_NAME_FRAGMENTS = (
            '_station_dp', '_lateral_w_sum', '_lateral_flow_link', '_lateral_dp_extra_def',
            '_pressure_drop_supply', '_pressure_drop_return', '_pressure_drop_total',
            'pressure_supply_prop_', 'pressure_return_prop_', '_P_supply_setpoint',
            '_pressure_supply_min', '_pressure_return_min',
        )
        _n_deactivated = 0
        _n_matched_components = 0
        for _c in list(m.component_objects(pyo.Constraint, active=True)):
            _cname = _c.name
            if not any(_frag in _cname for _frag in _HYD_NAME_FRAGMENTS):
                continue
            _n_matched_components += 1
            for _idx in list(_c.keys()):
                _t = _idx[0] if isinstance(_idx, tuple) else _idx
                if _t in HYDRAULIC_SUSPENDED_HOURS:
                    _c[_idx].deactivate()
                    _n_deactivated += 1
        logger.info(
            "[E3-HYDRAULIC-SUSPEND] suspend_hydraulic: deactivated %d constraint instance(s) "
            "across %d matched constraint component(s), at %d hour(s) (%s)",
            _n_deactivated, _n_matched_components, len(HYDRAULIC_SUSPENDED_HOURS),
            sorted(HYDRAULIC_SUSPENDED_HOURS),
        )
        assert _n_matched_components > 0, (
            "[E3-HYDRAULIC-SUSPEND] suspend_hydraulic requested but 0 constraint components "
            "matched the hydraulic name-fragment list -- the mechanism is a silent no-op, "
            "investigate the naming patterns before trusting results.")
        assert _n_deactivated > 0, (
            "[E3-HYDRAULIC-SUSPEND] suspend_hydraulic requested but 0 constraint instances "
            "were deactivated at the target hours -- check HYDRAULIC_SUSPENDED_HOURS against "
            "this run's time_set (short-window tests must use absolute year-hours).")

    return m


# ─── Legacy build path (old config format) ───────────────────────────────────

def _build_model_legacy(
    table: TimeSeriesTable,
    cfg: dict[str, Any],
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

    def series_dict(name: str) -> dict[int, float]:
        values = table[name]
        return {i + 1: float(values[i]) for i in range(T)}

    def column_series(name: str) -> list[float] | None:
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
    _dump_price = float(costs.get("dump_cost_eur_per_mwh_th", DEFAULT_DUMP_COST_EUR_PER_MWH_TH))
    # 2026-09-24 (B2, docs SS4az): env override so the B1a dump-price attribution experiment
    # (1000 vs 5 EUR/MWh) can be run WITHOUT ever editing the committed config (which holds the
    # post-B1a value, 5) -- every other run stays reproducible from the same file.
    import os as _os_dp
    _dump_price_env = _os_dp.environ.get('CALION_DUMP_PRICE_OVERRIDE')
    if _dump_price_env:
        logger.info("[B2] dump_cost_eur_per_mwh_th overridden %s -> %s (env)", _dump_price, _dump_price_env)
        _dump_price = float(_dump_price_env)
    m.dump_cost = pyo.Param(initialize=_dump_price)
    m.demand_charge_y = pyo.Param(initialize=float(grid.get("demand_charge_eur_per_mw_y", 0.0)))

    # ── Zonal demand charges (if configured) ───────────────────────────────
    m.zone_demand_charge = {}  # Dict[zone_id → Pyomo.Param]
    m.zone_demand_charge_values = {}  # Shadow dict for debugging/export (zone_id → float)
    m.zone_demand_charge_ts = None  # Will hold dynamic CSV costs if enabled
    
    # Check for zonal costs in costs_config (not in costs)
    costs_config = cfg.get("costs_config", {})
    if costs_config and "zones" in costs_config and costs_config["zones"]:
        try:
            cost_resolver = CostResolver(cfg, table)
            all_zone_costs = cost_resolver.get_all_zones_costs()
            
            # Create Pyomo parameters for each zone's demand charge
            for zone_id, zone_costs_dict in all_zone_costs.items():
                # Extract only the demand_charge_eur_per_mw_y for this zone
                charge_eur_per_mw_y = zone_costs_dict.get("demand_charge_eur_per_mw_y", 0.0)
                m.zone_demand_charge[zone_id] = pyo.Param(
                    initialize=float(charge_eur_per_mw_y)
                )
                m.zone_demand_charge_values[zone_id] = float(charge_eur_per_mw_y)
            
            # Log zone cost configuration
            if m.zone_demand_charge:
                logger.info(
                    "[BUILD-LEGACY] Zone demand charges configured: %s",
                    m.zone_demand_charge_values
                )
            
            # If dynamic costs are enabled, store the full resolver for later use
            if costs_config.get("dynamic", {}).get("enabled", False):
                m.zone_demand_charge_ts = cost_resolver
                logger.info("[BUILD-LEGACY] Dynamic zonal costs enabled (from CSV)")
        except Exception as e:
            logger.warning("[BUILD-LEGACY] Failed to load zonal costs: %s. Using global costs.", e)

    flags = CostFlags.from_config(cfg)
    inv_calc = InvestmentCalculator(
        period_frac=period_frac,
        discount_rate=float(cfg.get("investment", {}).get("discount_rate", 0.0)),
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

    # Pass 1: exact normalized match
    for col in table.columns:
        if _norm(col) == target:
            return col

    # Pass 2: substring match — only if target is long enough to be meaningful
    if len(target) >= 4:
        candidates = [col for col in table.columns if target in _norm(col)]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            logger.warning(
                f"Demand column '{column_name}' matched multiple columns: {candidates}. "
                f"Using first match '{candidates[0]}'."
            )
            return candidates[0]

    raise ValueError(
        f"Demand column '{column_name}' not found in data. "
        f"Available columns: {table.columns}"
    )

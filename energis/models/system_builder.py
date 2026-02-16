from __future__ import annotations

from typing import Dict, Any, List, Optional, Sequence
import math

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

    fuels = cfg.get("fuels", {})

    def pfuel(key: str, default: float = 0.0) -> float:
        return float(fuels.get(key, {}).get("price_eur_mwh", default))

    def efuel(key: str, default: float = 0.0) -> float:
        return float(fuels.get(key, {}).get("ef_kg_per_mwh_fuel", default))

    m.P_buy = pyo.Var(m.t, domain=pyo.NonNegativeReals)
    m.P_sell = pyo.Var(m.t, domain=pyo.NonNegativeReals)
    m.grid_mode = pyo.Var(m.t, domain=pyo.Binary)
    m.Q_dump = pyo.Var(m.t, domain=pyo.NonNegativeReals)

    el_in: List = []
    el_out: List = []
    ht_out: List = []
    ht_in: List = []
    gas_in: List = []
    bio_in: List = []
    waste_in: List = []

    syscfg = cfg.get("system", {})

    hp_defaults = cfg.get("heat_pumps", {})
    hp_inv_defaults = hp_defaults.get("investment_defaults", {})

    capex_terms: List = []
    activation_terms: List = []
    tie_breaker_terms: List = []
    storage_install_terms: List = []

    # ✅ CO₂-Kosten pro Komponente (Wärme/Strom-Aufteilung)
    co2_cost_heat_terms: List = []  # CO₂-Kosten für Wärmeerzeugung [EUR]
    co2_cost_elec_terms: List = []  # CO₂-Kosten für Stromerzeugung [EUR]
    co2_kg_heat_terms: List = []    # CO₂-Emissionen für Wärme [kg]
    co2_kg_elec_terms: List = []    # CO₂-Emissionen für Strom [kg]

    # ✅ Separate Tracking für Dashboard-Kategorien
    co2_kg_fuel_to_heat: List = []   # Brennstoff → Wärme
    co2_kg_fuel_to_elec: List = []   # Brennstoff → Strom (CHP)
    co2_kg_grid_to_elec: List = []   # Grid → Strom (WP, P2H)

    # Dictionary für Export (Komponenten-spezifisch)
    m.co2_component_costs = {}

    # ========== DEBUG: Check HP config before processing ==========
    print(f"\n[BUILD DEBUG] Raw HP config from syscfg:")
    for hp_raw in syscfg.get("heat_pumps", []):
        print(f"  {hp_raw.get('id')}: enabled={hp_raw.get('enabled')}, "
              f"max_th_mw={hp_raw.get('max_th_mw')}, "
              f"inv.enabled={hp_raw.get('investment', {}).get('enabled')}")
    
    print(f"\n[BUILD DEBUG] After apply_heat_pump_defaults:")
    for hp_check in apply_heat_pump_defaults(syscfg):
        print(f"  {hp_check.get('id')}: enabled={hp_check.get('enabled')}, "
              f"max_th_mw={hp_check.get('max_th_mw')}")
    print()
    # ========== END DEBUG ==========

    for hp in apply_heat_pump_defaults(syscfg):
        if not hp.get("enabled", True):
            continue
        name = hp.get("id", "HP")
        hp_type = hp.get("type", "standard")
        wrg_col = None
        if hp.get("wrg_source_column"):
            wrg_col = hp.get("wrg_source_column")
            if wrg_col not in table.columns and f"{wrg_col}_K" in table.columns:
                wrg_col = f"{wrg_col}_K"
        COP_series = _cop_series_from_table(table, wrg_col, cfg, hp_type)
        wrg_cap_col: Optional[str] = hp.get("wrg_capacity_column")
        if wrg_cap_col is None and hp.get("wrg_source_column"):
            prefix = str(hp.get("wrg_source_column")).split("_T")[0]
            candidate = f"{prefix}_Q_cap"
            if candidate in table.columns:
                wrg_cap_col = candidate
        wrg_caps = None
        if wrg_cap_col and wrg_cap_col in table.columns:
            wrg_caps = {i + 1: float(table[wrg_cap_col][i]) for i in range(T)}

        inv_cfg = dict(hp_inv_defaults)
        inv_cfg.update(hp.get("investment", {}))
        invest_enabled = bool(inv_cfg.get("enabled", False))
        cap_min = float(inv_cfg.get("capacity_min_mw", hp.get("min_th_mw", 0.0)))
        cap_max = float(inv_cfg.get("capacity_max_mw", hp.get("max_th_mw", 0.0)))
        existing_cap = float(hp.get("max_th_mw", cap_max))
        cap_init = float(
            inv_cfg.get(
                "initial_capacity_mw",
                existing_cap if not invest_enabled else max(cap_min, min(existing_cap, cap_max)),
            )
        )
        type_cfg = cfg.get("heat_pumps", {}).get("types", {})
        type_par = type_cfg.get(hp_type, {})
        min_load = float(type_par.get("min_load", 0.3))
        cop_default = float(type_par.get("COPdefault", cfg.get("heat_pumps", {}).get("cop", {}).get("cop_fallback", COP_DEFAULT)))
        if not math.isfinite(cop_default) or cop_default <= 0:
            cop_default = COP_DEFAULT

        block = HeatPumpBlock(
            name,
            min_load=min_load,
            cop_series=COP_series,
            capacity_min_mw=cap_min,
            capacity_max_mw=cap_max,
            capacity_init_mw=cap_init,
            investable=invest_enabled,
            wrg_cap_series=wrg_caps,
            cop_default=cop_default,
        )
        fs = block.attach(m, m.t, cfg, {})
        ht_out.append(fs["Q_th_out"])
        el_in.append(fs["P_el_in"])
        
        # Debug: Show HP parameters
        if name == "HP1":
            print(f"\n[BUILD DEBUG] HP1 parameters:")
            print(f"  - capacity: {cap_min:.1f} - {cap_max:.1f} MW (init: {cap_init:.1f})")
            print(f"  - investable: {invest_enabled}")
            print(f"  - min_load: {min_load}")
            print(f"  - COP series: min={min(COP_series):.2f}, max={max(COP_series):.2f}, avg={sum(COP_series)/len(COP_series):.2f}")
            print(f"  - WRG caps: {'None' if wrg_caps is None else f'provided ({len(wrg_caps)} values)'}")

        cap_var = fs.get("capacity")
        build_var = fs.get("build")
        if cap_var is not None and build_var is not None:
            lifetime = float(inv_cfg.get("lifetime_years", hp_inv_defaults.get("lifetime_years", DEFAULT_LIFETIME_YEARS)))
            capex = float(inv_cfg.get("capex_eur_per_mw", hp_inv_defaults.get("capex_eur_per_mw", 0.0)))
            activation = float(inv_cfg.get("activation_cost_eur", hp_inv_defaults.get("activation_cost_eur", 0.0)))
            tie_breaker = float(inv_cfg.get("tie_breaker_eur_per_mw", hp_inv_defaults.get("tie_breaker_eur_per_mw", 0.0)))
            if lifetime > 0:
                annual_factor = period_frac / lifetime
            else:
                annual_factor = 0.0
            if include_capex_costs:
                capex_terms.append(cap_var * capex * annual_factor)
            if include_activation_costs:
                activation_terms.append(build_var * activation * annual_factor)
            if tie_breaker and include_tie_breaker_costs:
                tie_breaker_terms.append(cap_var * tie_breaker)

        # ✅ Berechne CO₂-Kosten für Wärmepumpe
        # WP verbraucht Strom → indirekte Emissionen aus Grid
        hp_p_el = fs["P_el_in"]
        hp_co2_kg = sum(
            hp_p_el[t] * table["grid_co2_kg_MWh"][t - 1] * dt_h
            for t in m.t
        )
        hp_co2_cost_eur = (m.co2_price / 1000.0) * hp_co2_kg

        # Speichere für Export
        m.co2_component_costs[name] = {
            'heat_kg': 0,  # WP erzeugt Wärme, aber CO₂ kommt vom Strom
            'elec_kg': hp_co2_kg,  # Stromverbrauch → Grid-Emissionen
            'heat_eur': 0,
            'elec_eur': hp_co2_cost_eur,
            'total_kg': hp_co2_kg,
            'total_eur': hp_co2_cost_eur,
            'type': 'heat_pump'
        }

        # Füge zu Summen hinzu
        co2_kg_elec_terms.append(hp_co2_kg)
        co2_cost_elec_terms.append(hp_co2_cost_eur)
        co2_kg_grid_to_elec.append(hp_co2_kg)  # WP verbraucht Grid-Strom

    sto_cfg = syscfg.get("storage", {"enabled": False})
    # Normalize storage config to handle new config structure (technical_limits, defaults, costs)
    if isinstance(sto_cfg, dict):
        sto_cfg = normalize_storage_config(sto_cfg)
    print(f"[BUILD] Storage config: enabled={sto_cfg.get('enabled', False)}")
    if sto_cfg.get("enabled", False):
        print(f"[BUILD] Building storage component...")
        storage_defaults = cfg.get("storage", {})
        sto_defaults = storage_defaults.get("investment_defaults", {})
        sto_inv = dict(sto_defaults)
        sto_inv.update(sto_cfg.get("investment", {}))
        invest_enabled = bool(sto_inv.get("enabled", False))
        e_cap_min = float(sto_inv.get("energy_capacity_min_mwh", sto_cfg.get("min_energy_mwh", 0.0)))
        e_cap_max = float(sto_inv.get("energy_capacity_max_mwh", sto_cfg.get("max_energy_mwh", 50000.0)))
        p_cap_min = float(sto_inv.get("power_capacity_min_mw", sto_cfg.get("min_power_mw", 0.0)))
        p_cap_max = float(sto_inv.get("power_capacity_max_mw", sto_cfg.get("max_power_mw", 50.0)))
        e_cap_init = float(
            sto_inv.get(
                "initial_energy_capacity_mwh",
                sto_cfg.get("max_energy_mwh", e_cap_max)
                if not invest_enabled
                else max(e_cap_min, min(e_cap_max, sto_cfg.get("max_energy_mwh", e_cap_max))),
            )
        )
        p_cap_init = float(
            sto_inv.get(
                "initial_power_capacity_mw",
                sto_cfg.get("max_power_mw", p_cap_max)
                if not invest_enabled
                else max(p_cap_min, min(p_cap_max, sto_cfg.get("max_power_mw", p_cap_max))),
            )
        )

        inputs_cfg = cfg.get("inputs", {})
        soc_init = sto_cfg.get("soc0_mwh")
        if soc_init is None and "soc0_mwh" in storage_defaults:
            soc_init = storage_defaults.get("soc0_mwh")
        if "SOC_init" in inputs_cfg:
            soc_init = inputs_cfg["SOC_init"]
        elif "SOC_init" in sto_cfg:
            soc_init = sto_cfg["SOC_init"]
        else:
            soc_init_series = column_series("SOC_init")
            if soc_init_series:
                soc_init = soc_init_series[0]
        soc_init = float(soc_init if soc_init is not None else 0.0)

        # Apply override if provided (used by Rolling Horizon)
        if soc_init_override is not None:
            soc_init = float(soc_init_override)

        eff_charge_default = float(sto_cfg.get("eff_charge", storage_defaults.get("eff_charge", 0.95)))
        eff_discharge_default = float(sto_cfg.get("eff_discharge", storage_defaults.get("eff_discharge", 0.95)))
        loss_default = float(sto_cfg.get("loss_hour", storage_defaults.get("loss_hour", 0.9999)))

        loss_series_spec = sto_cfg.get("loss_hour_series") or storage_defaults.get("loss_hour_series")
        eff_charge_spec = sto_cfg.get("eff_charge_series") or storage_defaults.get("eff_charge_series")
        eff_discharge_spec = sto_cfg.get("eff_discharge_series") or storage_defaults.get("eff_discharge_series")
        capacity_active_spec = sto_cfg.get("capacity_active_series") or storage_defaults.get("capacity_active_series")

        loss_series = loss_series_spec or column_series("storage_loss_hour")
        eff_charge_series = eff_charge_spec or column_series("storage_eff_charge")
        eff_discharge_series = eff_discharge_spec or column_series("storage_eff_discharge")
        capacity_active_series = capacity_active_spec or column_series("storage_capacity_active")

        horizon_cfg = cfg.get("scenario", {}).get("horizon", {})
        enforce_terminal = bool(horizon_cfg.get("enforce", True))
        terminal_cfg = sto_cfg.get("terminal", {})
        terminal_policy_raw = str(terminal_cfg.get("policy", "")).lower()
        terminal_state = str(terminal_cfg.get("state", sto_cfg.get("terminal_state", ""))).strip().lower()
        terminal_target_cfg = terminal_cfg.get("target_mwh", terminal_cfg.get("target"))
        if terminal_target_cfg is None and "terminal_soc_mwh" in sto_cfg:
            terminal_target_cfg = float(sto_cfg["terminal_soc_mwh"])
        if not terminal_state:
            terminal_state = "free" if not enforce_terminal else "cyclic"
        if terminal_state not in {"free", "cyclic", "target"}:
            raise ValueError("storage.terminal.state/terminal_state must be one of: free, cyclic, target")

        if terminal_policy_raw and terminal_policy_raw not in {"equal", "geq", "free", "value", "soft"}:
            raise ValueError("storage.terminal.policy must be one of: equal, geq, free, value, soft")

        terminal_policy = "free" if terminal_state == "free" else (terminal_policy_raw or "equal")
        terminal_target_val: float | None
        if terminal_state == "free":
            terminal_target_val = None
        elif terminal_state == "cyclic":
            # For cyclic state, default to "equal" only if no policy specified
            # But respect explicit policy settings (value, soft, geq)
            if not terminal_policy_raw:
                terminal_policy = "equal"
            # For "value" policy: no target needed (value function optimizes freely)
            # For "soft" policy: target is used but with slack (always feasible)
            # For "equal"/"geq" policy: hard target constraint
            if terminal_policy == "value":
                terminal_target_val = None  # Value function doesn't need a target
            else:
                terminal_target_val = float(terminal_target_cfg) if terminal_target_cfg is not None else float(soc_init)
        else:
            if terminal_target_cfg is None:
                terminal_target_cfg = soc_init
            terminal_target_val = float(terminal_target_cfg)
            if terminal_policy not in {"equal", "geq", "value", "soft"}:
                terminal_policy = "equal"

        # Apply terminal target override if provided (used by Rolling Horizon)
        if terminal_target_override is not None:
            terminal_target_val = float(terminal_target_override)

        # Debug logging
        print(f"[BUILD] Storage terminal configuration:")
        print(f"  - terminal_state: {terminal_state}")
        print(f"  - terminal_policy: {terminal_policy}")
        print(f"  - soc_init: {soc_init}")
        print(f"  - terminal_target_val: {terminal_target_val}")

        coupling_factor = storage_defaults.get("power_energy_coupling")
        if "power_energy_coupling" in sto_cfg:
            coupling_factor = sto_cfg.get("power_energy_coupling")
        power_energy_coupling: float | None
        if coupling_factor is None:
            power_energy_coupling = None
        else:
            power_energy_coupling = float(coupling_factor)
            if power_energy_coupling <= 0:
                raise ValueError("storage.power_energy_coupling must be positive when provided")

        # Determine storage type: "simple" (default) or "stratified"
        storage_type = str(sto_cfg.get("type", "simple")).lower()

        if storage_type == "stratified":
            # Use advanced stratified storage with thermal zones
            print(f"[BUILD] Using stratified storage (2-zone thermocline model)")

            # Stratified storage specific parameters
            T_hot_C = float(sto_cfg.get("T_hot_C", 90.0))
            T_cold_C = float(sto_cfg.get("T_cold_C", 40.0))
            T_ambient_C = float(sto_cfg.get("T_ambient_C", 15.0))
            T_ground_C = float(sto_cfg.get("T_ground_C", 10.0))

            # Geometry
            aspect_ratio = float(sto_cfg.get("aspect_ratio", 1.5))
            geometry_type = str(sto_cfg.get("geometry_type", "tank"))

            # Heat transfer coefficients [W/(m²·K)]
            U_top = float(sto_cfg.get("U_top", 0.3))
            U_side = float(sto_cfg.get("U_side", 0.2))
            U_bottom = float(sto_cfg.get("U_bottom", 0.15))

            # Initial hot zone fraction
            V_hot_init_fraction = float(sto_cfg.get("V_hot_init_fraction", 0.5))

            block = StratifiedStorageBlock(
                "TES",
                # Thermal parameters
                T_hot_C=T_hot_C,
                T_cold_C=T_cold_C,
                T_ambient_C=T_ambient_C,
                T_ground_C=T_ground_C,
                # Geometry
                aspect_ratio=aspect_ratio,
                geometry_type=geometry_type,
                # Heat transfer coefficients
                U_top=U_top,
                U_side=U_side,
                U_bottom=U_bottom,
                # Efficiency
                eff_c=eff_charge_default,
                eff_d=eff_discharge_default,
                # Time step
                dt_h=dt_h,
                # Initial state
                soc0=soc_init,
                V_hot_init_fraction=V_hot_init_fraction,
                # Investment
                investable=invest_enabled,
                e_cap_min=e_cap_min,
                e_cap_max=e_cap_max,
                p_cap_min=p_cap_min,
                p_cap_max=p_cap_max,
                e_cap_init=e_cap_init,
                p_cap_init=p_cap_init,
                # Terminal constraint
                terminal_target=terminal_target_val,
            )
        else:
            # Use simple storage (existing code)
            print(f"[BUILD] Using simple storage (single-zone model)")

            block = StorageBlock(
                "TES",
                e_min=sto_cfg.get("min_energy_mwh", 0.0),
                e_max=sto_cfg.get("max_energy_mwh", 50000.0),
                p_max=sto_cfg.get("max_power_mw", 50.0),
                eff_c=eff_charge_default,
                eff_d=eff_discharge_default,
                hourly_loss=loss_default,
                dt_h=dt_h,
                soc0=soc_init,
                investable=invest_enabled,
                e_cap_min=e_cap_min,
                e_cap_max=e_cap_max,
                p_cap_min=p_cap_min,
                p_cap_max=p_cap_max,
                e_cap_init=e_cap_init,
                p_cap_init=p_cap_init,
                terminal_target=terminal_target_val,
                loss_series=loss_series,
                eff_charge_series=eff_charge_series,
                eff_discharge_series=eff_discharge_series,
                capacity_active_series=capacity_active_series,
                power_energy_coupling=power_energy_coupling,
            )
        fs = block.attach(m, m.t, cfg, {})
        ht_out.append(fs["Q_th_out"])
        ht_in.append(fs["Q_th_in"])
        # Remove potentially existing references from previous attaches to avoid
        # Pyomo warnings about implicit replacement when rebuilding the model
        for _name in ["TES_SOC", "TES_charge_mode", "TES_discharge_mode", "TES_active",
                      "TES_soc_low", "TES_soc_high", "TES_soc_split",
                      "TES_terminal_slack_pos", "TES_terminal_slack_neg", "TES_terminal_soft"]:
            if hasattr(m, _name):
                m.del_component(getattr(m, _name))

        m.TES_SOC = pyo.Reference(fs["SOC"])
        m.TES_charge_mode = pyo.Reference(fs["charge_mode"])
        m.TES_discharge_mode = pyo.Reference(fs["discharge_mode"])
        m.TES_active = pyo.Reference(fs["active"])
        setattr(m, "TES_terminal_policy", terminal_policy)

        # Terminal value/soft constraint parameters from config hierarchy:
        # 1. Check terminal_cfg (system.storage.terminal)
        # 2. Check storage_defaults.terminal_defaults
        # 3. Use computed default (avg electricity price)
        terminal_defs = storage_defaults.get("terminal_defaults", {})
        avg_price = sum(table["strompreis_EUR_MWh"]) / len(table) if len(table) > 0 else 50.0

        # Salvage price: Value of stored energy at end of horizon (EUR/MWh)
        salvage_cfg = terminal_cfg.get("salvage_price_eur_mwh")
        if salvage_cfg is None:
            salvage_cfg = terminal_defs.get("salvage_price_eur_mwh")
        salvage_price = float(salvage_cfg) if salvage_cfg is not None else avg_price

        # Soft penalty: Penalty for deviation from target (EUR/MWh)
        penalty_cfg = terminal_cfg.get("soft_penalty_eur_mwh")
        if penalty_cfg is None:
            penalty_cfg = terminal_defs.get("soft_penalty_eur_mwh")
        soft_penalty = float(penalty_cfg) if penalty_cfg is not None else (salvage_price * 2)

        last_t = m.t.last()
        terminal_value_term = None  # Will be added to objective if using value/soft policy

        if terminal_target_val is not None:
            setattr(m, "TES_terminal_target", pyo.Param(initialize=terminal_target_val))

            if terminal_policy == "geq":
                # Hard constraint: SOC >= target
                setattr(
                    m,
                    "TES_terminal",
                    pyo.Constraint(expr=fs["SOC"][last_t] >= getattr(m, "TES_terminal_target")),
                )
                print(f"[BUILD] Created terminal constraint: TES_terminal")
                print(f"  - SOC[{last_t}] >= {terminal_target_val} MWh (policy: geq)")

            elif terminal_policy == "equal":
                # Hard constraint: SOC == target
                setattr(
                    m,
                    "TES_terminal",
                    pyo.Constraint(expr=fs["SOC"][last_t] == getattr(m, "TES_terminal_target")),
                )
                print(f"[BUILD] Created terminal constraint: TES_terminal")
                print(f"  - SOC[{last_t}] == {terminal_target_val} MWh (policy: equal)")

            elif terminal_policy == "value":
                # Salvage value approach: reward stored energy at end of horizon
                # No hard constraint - terminal SOC is economically optimized
                # Supports two modes: "constant" (linear) or "diminishing" (piecewise linear)

                value_func_type = str(terminal_defs.get("value_function_type", "constant")).lower()
                decay = float(terminal_defs.get("diminishing_decay", 0.3))

                if value_func_type == "diminishing" and decay > 0:
                    # Piecewise linear diminishing returns value function
                    # Split SOC into two segments: low (full value) and high (reduced value)
                    # V(SOC) ≈ price * SOC_low + price * (1-decay) * SOC_high
                    # where SOC = SOC_low + SOC_high and SOC_low <= threshold

                    # Use 50% of capacity as threshold
                    soc_max = float(e_cap_init if not invest_enabled else e_cap_max)
                    threshold = 0.5 * soc_max

                    # Create auxiliary variables for piecewise segments
                    m.TES_soc_low = pyo.Var(domain=pyo.NonNegativeReals, bounds=(0, threshold))
                    m.TES_soc_high = pyo.Var(domain=pyo.NonNegativeReals, bounds=(0, soc_max - threshold))

                    # Constraint: SOC[T] = soc_low + soc_high
                    m.TES_soc_split = pyo.Constraint(
                        expr=fs["SOC"][last_t] == m.TES_soc_low + m.TES_soc_high
                    )

                    # Prices for each segment
                    price_low = salvage_price  # Full price for first 50%
                    price_high = salvage_price * (1 - decay)  # Reduced price above 50%

                    # Value function: reward stored energy with diminishing returns
                    terminal_value_term = -(price_low * m.TES_soc_low + price_high * m.TES_soc_high)

                    print(f"[BUILD] Using DIMINISHING terminal value function")
                    print(f"  - Base price: {salvage_price:.2f} EUR/MWh")
                    print(f"  - Decay factor: {decay:.2f}")
                    print(f"  - Threshold: {threshold:.1f} MWh (50% of {soc_max:.1f})")
                    print(f"  - Price below threshold: {price_low:.2f} EUR/MWh")
                    print(f"  - Price above threshold: {price_high:.2f} EUR/MWh")
                else:
                    # Constant/linear value function (original behavior)
                    terminal_value_term = -salvage_price * fs["SOC"][last_t]
                    print(f"[BUILD] Using CONSTANT terminal value function")
                    print(f"  - salvage_price: {salvage_price:.2f} EUR/MWh")

            elif terminal_policy == "soft":
                # Soft constraint: penalize deviation from target
                # Uses slack variables to make problem always feasible
                m.TES_terminal_slack_pos = pyo.Var(domain=pyo.NonNegativeReals)  # SOC above target
                m.TES_terminal_slack_neg = pyo.Var(domain=pyo.NonNegativeReals)  # SOC below target
                setattr(
                    m,
                    "TES_terminal_soft",
                    pyo.Constraint(
                        expr=fs["SOC"][last_t] + m.TES_terminal_slack_neg - m.TES_terminal_slack_pos
                        == getattr(m, "TES_terminal_target")
                    ),
                )
                # Penalize deviation (asymmetric: being below target is worse)
                terminal_value_term = soft_penalty * m.TES_terminal_slack_neg + (soft_penalty * 0.5) * m.TES_terminal_slack_pos
                print(f"[BUILD] Created soft terminal constraint: TES_terminal_soft")
                print(f"  - Target: {terminal_target_val} MWh, Penalty: {soft_penalty:.2f} EUR/MWh")
                print(f"  - Always feasible (deviation is penalized, not forbidden)")

        else:
            # No terminal constraint (free policy or value policy without target)
            if hasattr(m, "TES_terminal"):
                delattr(m, "TES_terminal")
            if hasattr(m, "TES_terminal_target"):
                delattr(m, "TES_terminal_target")

            if terminal_policy == "value":
                # Value policy without specific target: reward stored energy
                value_func_type = str(terminal_defs.get("value_function_type", "constant")).lower()
                decay = float(terminal_defs.get("diminishing_decay", 0.3))

                # Debug: show capacity parameters
                print(f"[BUILD] Value function capacity params:")
                print(f"  - invest_enabled: {invest_enabled}")
                print(f"  - e_cap_init: {e_cap_init:.1f} MWh")
                print(f"  - e_cap_max: {e_cap_max:.1f} MWh")
                print(f"  - soc_init: {soc_init:.1f} MWh")

                if value_func_type == "diminishing" and decay > 0:
                    # Piecewise linear diminishing returns
                    soc_max = float(e_cap_init if not invest_enabled else e_cap_max)
                    threshold = 0.5 * soc_max

                    # Safety check: ensure initial SOC fits within capacity
                    if soc_init > soc_max:
                        print(f"[BUILD] WARNING: soc_init ({soc_init:.1f}) > soc_max ({soc_max:.1f})!")
                        print(f"[BUILD] This may cause infeasibility. Adjusting soc_max.")
                        soc_max = max(soc_max, soc_init * 1.1)  # Add 10% margin
                        threshold = 0.5 * soc_max

                    m.TES_soc_low = pyo.Var(domain=pyo.NonNegativeReals, bounds=(0, threshold))
                    m.TES_soc_high = pyo.Var(domain=pyo.NonNegativeReals, bounds=(0, soc_max - threshold))
                    m.TES_soc_split = pyo.Constraint(
                        expr=fs["SOC"][last_t] == m.TES_soc_low + m.TES_soc_high
                    )

                    price_low = salvage_price
                    price_high = salvage_price * (1 - decay)
                    terminal_value_term = -(price_low * m.TES_soc_low + price_high * m.TES_soc_high)

                    print(f"[BUILD] Using DIMINISHING terminal value function (no target)")
                    print(f"  - soc_max: {soc_max:.1f} MWh, threshold: {threshold:.1f} MWh")
                    print(f"  - Base price: {salvage_price:.2f} EUR/MWh, Decay: {decay:.2f}")
                else:
                    terminal_value_term = -salvage_price * fs["SOC"][last_t]
                    print(f"[BUILD] Using CONSTANT terminal value function (no target)")
                    print(f"  - salvage_price: {salvage_price:.2f} EUR/MWh")
            else:
                print(f"[BUILD] No terminal constraint (policy: free)")

        # Store terminal value term for later addition to objective
        m.terminal_value_term = terminal_value_term

        cap_var = fs.get("cap_energy")
        pow_var = fs.get("cap_power")
        build_var = fs.get("build")
        lifetime = float(sto_inv.get("lifetime_years", sto_defaults.get("lifetime_years", DEFAULT_LIFETIME_YEARS)))
        e_capex = float(sto_inv.get("energy_capex_eur_per_mwh", sto_defaults.get("energy_capex_eur_per_mwh", 0.0)))
        p_capex = float(sto_inv.get("power_capex_eur_per_mw", sto_defaults.get("power_capex_eur_per_mw", 0.0)))
        activation = float(sto_inv.get("activation_cost_eur", sto_defaults.get("activation_cost_eur", 0.0)))
        tie_breaker = float(sto_inv.get("tie_breaker_eur_per_mwh", sto_defaults.get("tie_breaker_eur_per_mwh", 0.0)))
        install_share = float(sto_inv.get("installation_cost_share", sto_defaults.get("installation_cost_share", 0.0)))
        if lifetime > 0:
            annual_factor = period_frac / lifetime
        else:
            annual_factor = 0.0
        install_components: List = []
        if cap_var is not None:
            if include_capex_costs:
                capex_terms.append(cap_var * e_capex * annual_factor)
            install_components.append(cap_var * e_capex)
            if tie_breaker and include_tie_breaker_costs:
                tie_breaker_terms.append(cap_var * tie_breaker)
        if pow_var is not None:
            if include_capex_costs:
                capex_terms.append(pow_var * p_capex * annual_factor)
            install_components.append(pow_var * p_capex)
        if build_var is not None and include_activation_costs:
            activation_terms.append(build_var * activation * annual_factor)
        if install_share and install_components and include_storage_install_costs:
            storage_install_terms.append(sum(install_components) * install_share * annual_factor)

    gens = syscfg.get("generators", {})
    fuel_cost_terms: List = []
    fuel_co2_terms: List = []

    for key, par in gens.items():
        if not par.get("enabled", False):
            continue
        gpar = cfg.get("generators", {}).get(key, {})
        if key == "p2h":
            # Extract P2H parameters with defaults for backward compatibility
            eff = float(gpar.get("el_to_th_eff", 0.99))
            cap_th = float(par.get("cap_th_mw", 10.0))
            min_load = float(gpar.get("min_load", 0.0))
            eff_series = gpar.get("eff_series", None)
            part_load_penalty = float(gpar.get("part_load_penalty", 0.0))

            block = P2HBlock(
                "P2H",
                eff=eff,
                cap_th_mw=cap_th,
                min_load=min_load,
                eff_series=eff_series,
                part_load_penalty=part_load_penalty
            )
            fs = block.attach(m, m.t, cfg, {})
            el_in.append(fs["P_el_in"])
            ht_out.append(fs["Q_th_out"])

            # ✅ Berechne CO₂-Kosten für P2H
            # P2H verbraucht Strom → indirekte Emissionen aus Grid
            p2h_p_el = fs["P_el_in"]
            p2h_co2_kg = sum(
                p2h_p_el[t] * table["grid_co2_kg_MWh"][t - 1] * dt_h
                for t in m.t
            )
            p2h_co2_cost_eur = (m.co2_price / 1000.0) * p2h_co2_kg

            m.co2_component_costs["P2H"] = {
                'heat_kg': 0,  # Wärme aus Strom, CO₂ dem Strom zugeordnet
                'elec_kg': p2h_co2_kg,
                'heat_eur': 0,
                'elec_eur': p2h_co2_cost_eur,
                'total_kg': p2h_co2_kg,
                'total_eur': p2h_co2_cost_eur,
                'type': 'p2h'
            }

            co2_kg_elec_terms.append(p2h_co2_kg)
            co2_cost_elec_terms.append(p2h_co2_cost_eur)
            co2_kg_grid_to_elec.append(p2h_co2_kg)  # P2H verbraucht Grid-Strom

            continue

        block = ThermalGeneratorBlock(
            key.upper(), th_eff=float(gpar.get("th_eff", 0.9)), el_eff=gpar.get("el_eff", None), cap_th_mw=float(par.get("cap_th_mw", 10.0))
        )
        fs = block.attach(m, m.t, cfg, {})
        ht_out.append(fs["Q_th_out"])
        if fs.get("P_el_out") is not None:
            el_out.append(fs["P_el_out"])

        fuel_bus = gpar.get("fuel_bus", "gas")
        if fuel_bus == "gas":
            bus_list = gas_in
            price = pfuel("gas", 0.0)
            ef = efuel("gas", 0.0)
        elif fuel_bus == "biomass":
            bus_list = bio_in
            price = pfuel("biomass", 0.0)
            ef = efuel("biomass", 0.0)
        elif fuel_bus == "waste":
            bus_list = waste_in
            price = pfuel("waste", 0.0)
            ef = efuel("waste", 0.0)
        else:
            bus_list = gas_in
            price = 0.0
            ef = 0.0
        bus_list.append(fs["fuel_in"])

        # Fuel-Kosten (wie bisher)
        fuel_cost_expr = sum(fs["fuel_in"][t] * price * dt_h for t in m.t)
        fuel_cost_terms.append(fuel_cost_expr)

        # ✅ CO₂ aus Brennstoff mit Wärme/Strom-Aufteilung
        comp_name = key.upper()
        fuel_co2_kg = sum(fs["fuel_in"][t] * ef * dt_h for t in m.t)

        # Prüfe ob CHP (hat elektrischen Ausgang)
        is_chp = fs.get("P_el_out") is not None

        if not is_chp:
            # Reiner Wärmeerzeuger → Alles CO₂ → Wärme
            co2_heat_kg = fuel_co2_kg
            co2_elec_kg = 0
            co2_heat_cost = (m.co2_price / 1000.0) * co2_heat_kg
            co2_elec_cost = 0

            m.co2_component_costs[comp_name] = {
                'heat_kg': co2_heat_kg,
                'elec_kg': 0,
                'heat_eur': co2_heat_cost,
                'elec_eur': 0,
                'total_kg': fuel_co2_kg,
                'total_eur': co2_heat_cost,
                'type': 'thermal_generator',
                'th_eff': float(gpar.get("th_eff", 0.9)),
                'el_eff': None,
                'fuel_bus': fuel_bus
            }

            co2_kg_heat_terms.append(co2_heat_kg)
            co2_cost_heat_terms.append(co2_heat_cost)
            co2_kg_fuel_to_heat.append(co2_heat_kg)  # Brennstoff → Wärme
        else:
            # CHP → Energetische Aufteilung nach Wirkungsgrad
            th_eff = float(gpar.get("th_eff", 0.9))
            el_eff = float(gpar.get("el_eff", 0.0))
            total_eff = th_eff + el_eff

            if total_eff > 0:
                # Aufteilung: CO₂ proportional zum Wirkungsgrad
                heat_fraction = th_eff / total_eff
                elec_fraction = el_eff / total_eff
            else:
                heat_fraction = 1.0
                elec_fraction = 0.0

            # CO₂ aufteilen [kg]
            co2_heat_kg = fuel_co2_kg * heat_fraction
            co2_elec_kg = fuel_co2_kg * elec_fraction

            # CO₂-Kosten aufteilen [EUR]
            co2_heat_cost = (m.co2_price / 1000.0) * co2_heat_kg
            co2_elec_cost = (m.co2_price / 1000.0) * co2_elec_kg

            m.co2_component_costs[comp_name] = {
                'heat_kg': co2_heat_kg,
                'elec_kg': co2_elec_kg,
                'heat_eur': co2_heat_cost,
                'elec_eur': co2_elec_cost,
                'total_kg': fuel_co2_kg,
                'total_eur': (m.co2_price / 1000.0) * fuel_co2_kg,
                'type': 'chp',
                'th_eff': th_eff,
                'el_eff': el_eff,
                'fuel_bus': fuel_bus
            }

            co2_kg_heat_terms.append(co2_heat_kg)
            co2_kg_elec_terms.append(co2_elec_kg)
            co2_cost_heat_terms.append(co2_heat_cost)
            co2_cost_elec_terms.append(co2_elec_cost)
            co2_kg_fuel_to_heat.append(co2_heat_kg)  # Brennstoff → Wärme (CHP-Anteil)
            co2_kg_fuel_to_elec.append(co2_elec_kg)  # Brennstoff → Strom (CHP-Anteil)

        # Für Legacy-Kompatibilität: Gesamt-CO₂ in kg
        fuel_co2_terms.append(fuel_co2_kg)

    if not ht_out:
        raise RuntimeError(
            "Kein thermischer Erzeuger an den Heat-Bus angeschlossen (ht_out leer). Bitte System-Config prüfen."
        )

    print(f"[BUILD] #el_in={len(el_in)}, #el_out={len(el_out)}, #ht_out={len(ht_out)}, #ht_in={len(ht_in)}")

    # ========================================
    # THERMAL NETWORK INTEGRATION
    # ========================================
    # Normalize thermal_network config (supports both old and new structure)
    network_cfg = normalize_thermal_network_config(cfg)
    network_enabled = network_cfg.get('enabled', False)

    if network_enabled:
        print("[BUILD] Integrating thermal network...")

        # Get config directory from cfg if available, otherwise use current directory
        config_dir = cfg.get('_config_dir', Path.cwd())
        if not isinstance(config_dir, Path):
            config_dir = Path(config_dir) if config_dir else Path.cwd()

        # Check if outdoor temperature is available for heating curve
        has_outdoor_temp = hasattr(m, 'outdoor_temp') and m.outdoor_temp is not None
        if has_outdoor_temp:
            # Enable outdoor temperature usage in network config
            network_cfg.setdefault('use_outdoor_temperature', True)
            print("[BUILD] Outdoor temperature available - heating curve enabled")
        else:
            print("[BUILD] No outdoor temperature data - using fixed supply temperature")

        # Inject normalized network config back into cfg for NetworkManager
        cfg_with_network = dict(cfg)
        cfg_with_network['thermal_network'] = network_cfg

        try:
            network_mgr = NetworkManager(cfg_with_network, config_dir=config_dir)

            # Check if network was actually loaded successfully
            if not network_mgr.network_enabled:
                print(f"[BUILD] WARNING: Thermal network failed to load (check topology file)")
                print(f"[BUILD] Continuing without thermal network...")
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
                    print(f"[BUILD] Thermal network integrated successfully:")
                    print(f"         {len(network_results.get('pipes', {}))} pipes, "
                          f"{len(network_results.get('nodes', {}))} nodes")
                else:
                    print(f"[BUILD] WARNING: Thermal network returned no components")
                    print(f"[BUILD] Continuing without thermal network...")
                    m._network_enabled = False

        except Exception as e:
            print(f"[BUILD] ERROR: Failed to integrate thermal network: {e}")
            print(f"[BUILD] Continuing without thermal network...")
            m._network_enabled = False
            import traceback
            traceback.print_exc()
    else:
        m._network_enabled = False
        print("[BUILD] Thermal network disabled")

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

    # Legacy-Kompatibilität: Gesamt-CO₂ in kg (für alte Reports)
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


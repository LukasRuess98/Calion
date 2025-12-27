from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Sequence
import math

logger = logging.getLogger(__name__)

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
from energis.utils.config_utils import apply_heat_pump_defaults
from .blocks.heat_pump import HeatPumpBlock
from .blocks.storage import StorageBlock
from .blocks.stratified_storage import StratifiedStorageBlock
from .blocks.thermal_gen import ThermalGeneratorBlock
from .blocks.p2h import P2HBlock
from .network_manager import NetworkManager


def _cop_series_from_table(
    table: TimeSeriesTable, wrg_col: str | None, cfg: Dict[str, Any], hp_type: str
) -> List[float]:
    """Calculate heat pump COP (Coefficient of Performance) time series.

    Computes COP values for each timestep using either:
    1. 2D interpolation from lookup tables (preferred if configured)
    2. Analytical calculation based on heat pump physics and thermodynamics

    The function supports waste heat recovery (WRG) integration and automatically
    clamps COP values to safe numerical ranges to prevent optimization issues.

    Args:
        table (TimeSeriesTable): Time series data with temperature/demand profiles
        wrg_col (str | None): Column name for waste heat recovery temperature data.
            If None or column missing, uses analytical fallback.
        cfg (Dict[str, Any]): Configuration with COP calculation parameters:
            - heat_pumps.cop.tables: Lookup table definitions
            - heat_pumps.cop.sink_defaults: Sink temperature settings
            - heat_pumps.types[hp_type]: Heat pump specific parameters

        hp_type (str): Heat pump type identifier (e.g., "default", "high_temp")

    Returns:
        List[float]: COP value for each timestep, clamped to [COP_MIN, COP_MAX_SYSTEM_BUILDER]

    Raises:
        ValueError: If COP table axes are invalid or interpolation fails
        RuntimeError: If required temperature data is missing

    Note:
        Falls back to analytical COP calculation if table-based method unavailable.
        Analytical method uses log-mean temperature difference (LMTD) and efficiency factors.
    """
    copcfg = cfg.get("heat_pumps", {}).get("cop", {})
    tables_cfg = copcfg.get("tables", {})
    table_spec = tables_cfg.get(hp_type) or tables_cfg.get("default")

    def _validate_axis(values: Sequence[float], axis_name: str) -> List[float]:
        axis = [float(v) for v in values]
        if not axis:
            raise ValueError(f"COP table axis '{axis_name}' is empty")
        if any(not math.isfinite(v) for v in axis):
            raise ValueError(f"COP table axis '{axis_name}' enthält ungültige Werte")
        if axis != sorted(axis):
            raise ValueError(f"COP table axis '{axis_name}' muss aufsteigend sortiert sein")
        return axis

    def _locate_interval(points: List[float], value: float, clamp: bool, axis_name: str) -> tuple[int, int, float]:
        if len(points) == 1:
            return 0, 0, 0.0
        if value <= points[0]:
            if clamp:
                return 0, 0, 0.0
            raise ValueError(f"Wert {value} liegt unterhalb der COP-Tabelle für {axis_name}")
        if value >= points[-1]:
            if clamp:
                idx = len(points) - 1
                return idx, idx, 0.0
            raise ValueError(f"Wert {value} liegt oberhalb der COP-Tabelle für {axis_name}")
        for i in range(len(points) - 1):
            lo = points[i]
            hi = points[i + 1]
            if lo <= value <= hi or math.isclose(value, lo) or math.isclose(value, hi):
                span = max(hi - lo, 1e-12)
                frac = (value - lo) / span
                return i, i + 1, min(max(frac, 0.0), 1.0)
        # Should not happen due to bounds above
        raise ValueError(f"Wert {value} konnte nicht in COP-Achse {axis_name} zugeordnet werden")

    def _interp1d(points: List[float], values: List[float], i0: int, i1: int, frac: float) -> float:
        if i0 == i1:
            return values[i0]
        v0 = values[i0]
        v1 = values[i1]
        return v0 + frac * (v1 - v0)

    def _interp2d(
        x_points: List[float],
        matrix: List[List[float]],
        x_idx0: int,
        x_idx1: int,
        x_frac: float,
        y_idx0: int,
        y_idx1: int,
        y_frac: float,
    ) -> float:
        if y_idx0 == y_idx1:
            return _interp1d(x_points, matrix[y_idx0], x_idx0, x_idx1, x_frac)
        # Interpolate along x for both y positions, then between them
        row0 = matrix[y_idx0]
        row1 = matrix[y_idx1]
        v0 = _interp1d(x_points, row0, x_idx0, x_idx1, x_frac)
        v1 = _interp1d(x_points, row1, x_idx0, x_idx1, x_frac)
        return v0 + y_frac * (v1 - v0)

    def _series_from_column(column: str | None, default: float | None) -> List[float]:
        if column and column in table.columns:
            return [float(table[column][i]) for i in range(len(table))]
        if default is not None:
            return [float(default) for _ in range(len(table))]
        raise KeyError(f"Benötigte Spalte {column!r} für COP-Berechnung fehlt")

    if table_spec:
        x_points = _validate_axis(table_spec.get("x") or table_spec.get("source_temperatures_K", []), "x")
        y_points_raw: Sequence[float] | None = table_spec.get("y") or table_spec.get("sink_temperatures_K")
        has_y = bool(y_points_raw)
        y_points = _validate_axis(y_points_raw, "y") if has_y else None
        values_raw = table_spec.get("values")
        if values_raw is None:
            raise ValueError("COP-Tabelle benötigt einen 'values'-Eintrag")
        if has_y:
            matrix = [[float(v) for v in row] for row in values_raw]
            if len(matrix) != len(y_points):
                raise ValueError("COP-Tabelle: Anzahl der Zeilen passt nicht zur y-Achse")
            for row in matrix:
                if len(row) != len(x_points):
                    raise ValueError("COP-Tabelle: Jede Zeile muss gleich viele Werte wie die x-Achse besitzen")
        else:
            vector = [float(v) for v in values_raw]
            if len(vector) != len(x_points):
                raise ValueError("COP-Tabelle (1D): Anzahl der Werte passt nicht zur x-Achse")
            matrix = [vector]
            y_points = [0.0]
            has_y = False

        clamp_default = bool(table_spec.get("clamp", True))
        clamp_x = bool(table_spec.get("clamp_x", clamp_default))
        clamp_y = bool(table_spec.get("clamp_y", clamp_default))

        sink_defaults = copcfg.get("sink_defaults", {})
        Ts_out = float(sink_defaults.get("Tsink_out_K", 363.15))

        x_series = _series_from_column(table_spec.get("x_column") or wrg_col, table_spec.get("x_default"))
        y_column = table_spec.get("y_column")
        y_series = _series_from_column(y_column, table_spec.get("y_default", Ts_out)) if has_y else [0.0] * len(table)

        cop_min = float(table_spec.get("cop_min", copcfg.get("cop_min", COP_MIN)))
        cop_max = float(table_spec.get("cop_max", copcfg.get("cop_max", COP_MAX_SYSTEM_BUILDER)))

        result: List[float] = []
        for xv, yv in zip(x_series, y_series):
            x_idx0, x_idx1, x_frac = _locate_interval(x_points, float(xv), clamp_x, "x")
            if has_y:
                y_idx0, y_idx1, y_frac = _locate_interval(y_points, float(yv), clamp_y, "y")
            else:
                y_idx0 = y_idx1 = 0
                y_frac = 0.0
            val = _interp2d(
                x_points,
                matrix,
                x_idx0,
                x_idx1,
                x_frac,
                y_idx0,
                y_idx1,
                y_frac,
            )
            if not math.isfinite(val):
                raise ValueError("COP-Tabelle lieferte keinen gültigen Wert")
            result.append(float(min(max(val, cop_min), cop_max)))
        return result

    # Fallback auf analytische Berechnung
    dT = float(copcfg.get("deltaT_K", COP_DELTA_T_K))
    dTpp = float(copcfg.get("deltaTpp_K", 5.0))
    sink = copcfg.get("sink_defaults", {})
    Ts_out = float(sink.get("Tsink_out_K", 363.15))
    Ts_in = float(sink.get("Tsink_in_K", 343.15))
    type_par = cfg.get("heat_pumps", {}).get("types", {}).get(hp_type, {})
    eta = float(type_par.get("eta", 0.75))
    FQ = float(type_par.get("FQ", 0.10))

    if wrg_col and wrg_col in table.columns:
        temps = table[wrg_col]
    else:
        temps = [Ts_in - 10.0 for _ in range(len(table))]

    Tout = [max(t - dT, 1.0) for t in temps]

    def _lmtd(Th: float, Tc: float) -> float:
        """Calculate log mean temperature difference with proper numerical safeguards."""
        # Ensure positive temperatures with small offset to avoid log(0)
        Th_safe = max(Th, 1e-3)
        Tc_safe = max(Tc, 1e-3)

        # If temperatures are too close, return arithmetic mean
        if abs(Th_safe - Tc_safe) < 1e-6:
            return max((Th_safe + Tc_safe) / 2.0, 1e-6)

        # Standard LMTD calculation: (Th - Tc) / ln(Th / Tc)
        ratio = Th_safe / Tc_safe
        if abs(ratio - 1.0) < 1e-9:  # Too close to 1, log is unstable
            return max((Th_safe + Tc_safe) / 2.0, 1e-6)

        numerator = Th_safe - Tc_safe
        denominator = math.log(ratio)
        return abs(numerator / max(abs(denominator), 1e-9))

    Ls = _lmtd(Ts_out, Ts_in)
    cop: List[float] = []
    for Tin, Tout_i in zip(temps, Tout):
        Lsrc = _lmtd(Tin, Tout_i)
        mdts = 0.2 * (Ts_out - Tout_i + 2 * dTpp) + 0.2 * (Ts_out - Ts_in) + 0.016
        qww = 0.0014 * (Ts_out - Tout_i + 2 * dTpp) - 0.0015 * (Ts_out - Ts_in) + 0.039
        A = Ls / max(1e-9, Ls - Lsrc)
        B = (1 + (mdts + dTpp) / max(1e-9, Ls)) / (1 + (mdts + 0.5 * (Tin - Tout_i) + 2 * dTpp) / max(1e-9, (Ls - Lsrc)))
        val = A * B * eta * (1 - qww) + 1 - eta - FQ
        if not math.isfinite(val) or val < COP_MIN:
            val = float(copcfg.get("cop_fallback", COP_DEFAULT))
        cop.append(float(min(max(val, COP_MIN), COP_MAX_SYSTEM_BUILDER)))
    return cop


def build_model(table: TimeSeriesTable, cfg: Dict[str, Any], dt_h: float = 1.0):
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
    - Thermal network with explicit heat loss modeling

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
        >>> cfg = load_and_merge(["configs/base.yaml", "configs/tech_catalog.yaml",
        ...                       "configs/system.yaml", "configs/scenario.yaml"])
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

    # Store model parameters for components
    m.dt_h = dt_h
    m.period_years = period_frac

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

    # Outdoor temperature (for thermal network heat losses)
    if "T_outdoor" in table.columns:
        m.outdoor_temp = {i + 1: float(table["T_outdoor"][i]) for i in range(T)}
    else:
        # Default: no outdoor temperature data available yet
        m.outdoor_temp = {i + 1: 10.0 for i in range(T)}

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
        # Support both old (capacity_min_mw) and new (min_mw) parameter names
        cap_min = float(inv_cfg.get("min_mw", inv_cfg.get("capacity_min_mw", hp.get("min_th_mw", 0.0))))
        cap_max = float(inv_cfg.get("max_mw", inv_cfg.get("capacity_max_mw", hp.get("max_th_mw", 0.0))))
        # Support both old (max_th_mw) and new (capacity_mw) for existing capacity
        existing_cap = float(hp.get("capacity_mw", hp.get("max_th_mw", cap_max)))
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
    if sto_cfg.get("enabled", False):
        storage_defaults = cfg.get("storage", {})
        sto_defaults = storage_defaults.get("investment_defaults", {})
        sto_inv = dict(sto_defaults)
        sto_inv.update(sto_cfg.get("investment", {}))
        invest_enabled = bool(sto_inv.get("enabled", False))
        # Support both old (energy_capacity_min_mwh) and new (min_energy_mwh) parameter names
        e_cap_min = float(sto_inv.get("min_energy_mwh", sto_inv.get("energy_capacity_min_mwh", sto_cfg.get("min_energy_mwh", 0.0))))
        e_cap_max = float(sto_inv.get("max_energy_mwh", sto_inv.get("energy_capacity_max_mwh", sto_cfg.get("max_energy_mwh", 50000.0))))
        p_cap_min = float(sto_inv.get("min_power_mw", sto_inv.get("power_capacity_min_mw", sto_cfg.get("min_power_mw", 0.0))))
        p_cap_max = float(sto_inv.get("max_power_mw", sto_inv.get("power_capacity_max_mw", sto_cfg.get("max_power_mw", 50.0))))
        # Support both old (max_energy_mwh) and new (energy_mwh) for existing capacity
        existing_e_cap = sto_cfg.get("energy_mwh", sto_cfg.get("max_energy_mwh", e_cap_max))
        existing_p_cap = sto_cfg.get("power_mw", sto_cfg.get("max_power_mw", p_cap_max))
        e_cap_init = float(
            sto_inv.get(
                "initial_energy_capacity_mwh",
                existing_e_cap if not invest_enabled else max(e_cap_min, min(e_cap_max, existing_e_cap)),
            )
        )
        p_cap_init = float(
            sto_inv.get(
                "initial_power_capacity_mw",
                existing_p_cap if not invest_enabled else max(p_cap_min, min(p_cap_max, existing_p_cap)),
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

        if terminal_policy_raw and terminal_policy_raw not in {"equal", "geq", "free"}:
            raise ValueError("storage.terminal.policy must be one of: equal, geq, free")

        terminal_policy = "free" if terminal_state == "free" else (terminal_policy_raw or "equal")
        terminal_target_val: float | None
        if terminal_state == "free":
            terminal_target_val = None
        elif terminal_state == "cyclic":
            terminal_policy = "equal"
            terminal_target_val = float(soc_init)
        else:
            if terminal_target_cfg is None:
                terminal_target_cfg = soc_init
            terminal_target_val = float(terminal_target_cfg)
            if terminal_policy not in {"equal", "geq"}:
                terminal_policy = "equal"

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
            logger.info("Using stratified storage (2-zone thermocline model)")

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
            )
        else:
            # Use simple storage (existing code)
            logger.info("Using simple storage (single-zone model)")

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
                terminal_target=None,
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
        for _name in ["TES_SOC", "TES_charge_mode", "TES_discharge_mode", "TES_active"]:
            if hasattr(m, _name):
                m.del_component(getattr(m, _name))

        m.TES_SOC = pyo.Reference(fs["SOC"])
        m.TES_charge_mode = pyo.Reference(fs["charge_mode"])
        m.TES_discharge_mode = pyo.Reference(fs["discharge_mode"])
        m.TES_active = pyo.Reference(fs["active"])
        setattr(m, "TES_terminal_policy", terminal_policy)
        if terminal_target_val is not None:
            setattr(m, "TES_terminal_target", pyo.Param(initialize=terminal_target_val))
            last_t = m.t.last()
            if terminal_policy == "geq":
                setattr(
                    m,
                    "TES_terminal",
                    pyo.Constraint(expr=fs["SOC"][last_t] >= getattr(m, "TES_terminal_target")),
                )
            else:
                setattr(
                    m,
                    "TES_terminal",
                    pyo.Constraint(expr=fs["SOC"][last_t] == getattr(m, "TES_terminal_target")),
                )
        else:
            if hasattr(m, "TES_terminal"):
                delattr(m, "TES_terminal")
            if hasattr(m, "TES_terminal_target"):
                delattr(m, "TES_terminal_target")

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

    logger.info(f"Component counts: el_in={len(el_in)}, el_out={len(el_out)}, ht_out={len(ht_out)}, ht_in={len(ht_in)}")

    m.el_balance = pyo.Constraint(
        m.t,
        rule=lambda mm, t: mm.P_buy[t] + sum((f[t] for f in el_out), start=0) == sum((f[t] for f in el_in), start=0) + mm.P_sell[t],
    )

    # ========================================
    # THERMAL NETWORK INTEGRATION (BEFORE HEAT BALANCE!)
    # ========================================
    network_capex_total = 0
    network_heat_loss_cost = 0
    thermal_network_cfg = cfg.get('thermal_network', {})
    thermal_network_enabled = thermal_network_cfg.get('enabled', False)

    if thermal_network_enabled:
        from pathlib import Path
        config_dir = Path(cfg.get('config_dir', '.'))

        # Initialize network manager
        network_mgr = NetworkManager(cfg, config_dir=config_dir)

        # Attach network to model (this creates m.network_Q_loss_per_timestep)
        buses = {}  # Bus references (if needed)
        network_results = network_mgr.attach_to_model(m, m.t, buses)

        # Add network CAPEX to objective
        if hasattr(m, 'network_total_pipe_capex'):
            network_capex_total = m.network_total_pipe_capex

        # Add heat loss cost to objective
        # The NetworkManager now provides m.network_Q_loss_per_timestep[t]
        if hasattr(m, 'network_Q_loss_per_timestep'):
            # Heat losses valued at dump cost (marginal generation cost proxy)
            network_heat_loss_cost = m.dump_cost * sum(
                m.network_Q_loss_per_timestep[t] * dt_h for t in m.t
            )
            logger.info("Network heat losses (per timestep) added to objective")
        elif hasattr(m, 'network_heat_loss_expr'):
            # Fallback: use total expression (legacy behavior)
            network_heat_loss_cost = m.network_heat_loss_expr * dt_h * m.dump_cost
            logger.info("Network heat losses (total expr) added to objective")
        
        # Store network manager for results extraction
        m.network_manager = network_mgr

    # ========================================

    # HEAT BALANCE CONSTRAINTS

    # ========================================

    if thermal_network_enabled:
        logger.info("Thermal network enabled - using heat balance with explicit network losses")

        # Check if we have per-timestep network losses
        if hasattr(m, 'network_Q_loss_per_timestep'):
            # ✅ LANGFRISTIGE LÖSUNG: Explizite Netzwerk-Verluste pro Zeitschritt
            # Heat Balance: Production = Demand + Storage_Charge + Network_Losses + Dump
            # NOTE: Q_dump is essential as safety valve for excess production
            m.ht_balance = pyo.Constraint(
                m.t,
                rule=lambda mm, t: sum((f[t] for f in ht_out), start=0) ==
                                mm.heatd[t] +
                                sum((f[t] for f in ht_in), start=0) +
                                mm.network_Q_loss_per_timestep[t] +
                                mm.Q_dump[t],
            )
            logger.info("Using explicit network losses: network_Q_loss_per_timestep[t]")
        else:
            # ✅ PRAGMATISCHE LÖSUNG: Geschätzte Verluste als Prozentsatz
            # Typische Wärmenetz-Verluste: 5-15% des transportierten Bedarfs
            network_loss_factor = float(thermal_network_cfg.get('estimated_loss_factor', 0.12))
            logger.info(f"Using estimated network losses: {network_loss_factor*100:.1f}% of demand")
            
            # Heat Balance mit geschätzten Verlusten:
            # Production = Demand * (1 + loss_factor) + Storage_Charge + Dump
            m.ht_balance = pyo.Constraint(
                m.t,
                rule=lambda mm, t: sum((f[t] for f in ht_out), start=0) == 
                                mm.heatd[t] * (1.0 + network_loss_factor) + 
                                sum((f[t] for f in ht_in), start=0) + 
                                mm.Q_dump[t],
            )
            
            # Optional: Upper bound als Sicherheit
            m.ht_upper = pyo.Constraint(
                m.t,
                rule=lambda mm, t: sum((f[t] for f in ht_out), start=0) <= 
                                mm.heatd[t] * (1.0 + network_loss_factor + 0.05) + 
                                sum((f[t] for f in ht_in), start=0) + 
                                mm.Q_dump[t] * 1.5,
            )
    else:
        # Standard strict heat balance without thermal network
        logger.info("No thermal network - using strict heat balance")
        m.ht_balance = pyo.Constraint(
            m.t,
            rule=lambda mm, t: sum((f[t] for f in ht_out), start=0) == 
                            mm.heatd[t] + sum((f[t] for f in ht_in), start=0) + mm.Q_dump[t],
        )
        
    m.buy_gate = pyo.Constraint(m.t, rule=lambda mm, t: mm.P_buy[t] <= mm.grid_mode[t] * mm.M_GRID)
    m.sell_gate = pyo.Constraint(m.t, rule=lambda mm, t: mm.P_sell[t] <= (1 - mm.grid_mode[t]) * mm.M_GRID)
    m.buy_limit = pyo.Constraint(m.t, rule=lambda mm, t: mm.P_buy[t] <= mm.max_import)
    m.sell_limit = pyo.Constraint(m.t, rule=lambda mm, t: mm.P_sell[t] <= mm.max_export)

    base_prices = [float(table["strompreis_EUR_MWh"][i]) for i in range(T)]
    if include_gridcost:
        addition = float(m.energy_fee.value) + float(m.grid_cost.value)
    else:
        addition = 0.0
    buy_price = [bp + addition for bp in base_prices]

    floor = float(m.sell_floor.value)
    haircut = float(m.sell_haircut.value)
    spread = float(m.sell_spread.value)
    fee = float(m.sell_fee.value)
    premium = float(m.sell_premium.value)

    def _sell_price(base: float) -> float:
        price = max(base - spread, floor)
        price = price * max(0.0, 1.0 - haircut)
        price = price - fee + premium
        return max(price, 0.0)

    sell_price = [_sell_price(bp) for bp in base_prices]

    energy_cost = sum(
        dt_h * (m.P_buy[t] * buy_price[idx] - m.P_sell[t] * sell_price[idx])
        for idx, t in enumerate(m.t)
    )
    dump_cost = m.dump_cost * sum(m.Q_dump[t] * dt_h for t in m.t)
    fuel_costs = sum(fuel_cost_terms) if fuel_cost_terms else 0

    # ✅ Neue CO₂-Kosten: Summen aus Komponenten (Wärme/Strom-Aufteilung)
    co2_cost_heat_total = sum(co2_cost_heat_terms) if co2_cost_heat_terms else 0
    co2_cost_elec_total = sum(co2_cost_elec_terms) if co2_cost_elec_terms else 0
    co2_cost_total = co2_cost_heat_total + co2_cost_elec_total

    # ✅ CO₂-Mengen in kg: Summen aus Komponenten (Wärme/Strom-Aufteilung)
    co2_kg_heat_total = sum(co2_kg_heat_terms) if co2_kg_heat_terms else 0
    co2_kg_elec_total = sum(co2_kg_elec_terms) if co2_kg_elec_terms else 0

    # ✅ Dashboard-Kategorien (3 separate Emissionsquellen)
    co2_kg_fuel_heat = sum(co2_kg_fuel_to_heat) if co2_kg_fuel_to_heat else 0  # Brennstoff → Wärme
    co2_kg_fuel_elec = sum(co2_kg_fuel_to_elec) if co2_kg_fuel_to_elec else 0  # Brennstoff → Strom (CHP)
    co2_kg_grid_elec = sum(co2_kg_grid_to_elec) if co2_kg_grid_to_elec else 0  # Grid → Strom (WP, P2H)

    # Speichere Gesamt-Expressions am Modell für Export
    m.co2_cost_heat_expr = co2_cost_heat_total
    m.co2_cost_elec_expr = co2_cost_elec_total
    m.co2_cost_total_expr = co2_cost_total
    m.co2_kg_heat_expr = co2_kg_heat_total
    m.co2_kg_elec_expr = co2_kg_elec_total
    # Dashboard-Kategorien
    m.co2_kg_fuel_to_heat_expr = co2_kg_fuel_heat
    m.co2_kg_fuel_to_elec_expr = co2_kg_fuel_elec
    m.co2_kg_grid_to_elec_expr = co2_kg_grid_elec

    # Legacy-Kompatibilität: Gesamt-CO₂ in kg (für alte Reports)
    co2_grid = sum(m.P_buy[t] * table["grid_co2_kg_MWh"][t - 1] * dt_h for t in m.t)
    co2_fuel = sum(fuel_co2_terms) if fuel_co2_terms else 0

    # Zielfunktion: Verwende neue CO₂-Kosten-Summe
    co2_term = co2_cost_total if include_co2 else 0

    m.P_buy_peak = pyo.Var(domain=pyo.NonNegativeReals)
    m.peak_con = pyo.Constraint(m.t, rule=lambda mm, t: mm.P_buy_peak >= mm.P_buy[t])
    demand_term = (m.demand_charge_y * m.year_frac * m.P_buy_peak) if include_demand else 0

    capex_total = sum(capex_terms) if capex_terms else 0
    activation_total = sum(activation_terms) if activation_terms else 0
    tie_break_total = sum(tie_breaker_terms) if tie_breaker_terms else 0
    storage_install_total = sum(storage_install_terms) if storage_install_terms else 0

    m.capex_cost_expr = capex_total
    m.activation_cost_expr = activation_total
    m.tie_break_cost_expr = tie_break_total
    m.storage_install_cost_expr = storage_install_total

    m.obj = pyo.Objective(
        expr=energy_cost
        + dump_cost
        + fuel_costs
        + co2_term
        + demand_term
        + capex_total
        + activation_total
        + tie_break_total
        + storage_install_total
        + network_capex_total
        + network_heat_loss_cost,

        sense=pyo.minimize,
    )
    return m
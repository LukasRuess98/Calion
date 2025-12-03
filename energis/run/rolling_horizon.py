"""Workflow helpers for rolling horizon simulations.

The module implements a lightweight orchestration layer around the existing
`energis.run.orchestrator` utilities.  Callers can describe a sequence of
workflow steps via ``scenario.workflow`` (e.g. ``["PF", "RH"]``) or the legacy
``run_mode`` switch.  This makes it trivial to compare PF-only, RH-only and
combined PF→RH simulations while reusing the same configuration set.  The RH
logic honours configuration entries for window size, step width and terminal
policies while preserving state-of-charge (SOC) values between windows.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import argparse
import copy
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - the solver stack is optional for tests
    HAVE_PYOMO = False
    pyo = None

from energis.config.merge import deep_merge, load_and_merge
from energis.io.loader import load_input_excel
from energis.io.exporter import export_scenario_bundle, write_timeseries_csv
from energis.io.plotter import export_plots
from energis.models.system_builder import build_model
from energis.utils.timeseries import TimeSeriesTable
import time


@dataclass
class ScenarioResult:
    """Container for a single optimisation run."""

    table: TimeSeriesTable
    series: OrderedDict[str, List[float]]
    summary: Mapping[str, Mapping[str, Any]]
    costs: Dict[str, Any]
    solver: Dict[str, Any]


@dataclass
class WindowResult(ScenarioResult):
    """Specialised result carrying metadata for RH windows."""

    start_index: int
    commit_steps: int


@dataclass
class RollingHorizonResult:
    """Aggregated result for a complete RH simulation."""

    table: TimeSeriesTable
    series: OrderedDict[str, List[float]]
    costs: Dict[str, Any]
    windows: List[WindowResult]
    design: Optional[DesignData] = None


@dataclass
class DesignData:
    """Design figures extracted from a PF optimisation."""

    heat_pumps: Dict[str, Dict[str, float]]
    storage: Optional[Dict[str, float]]


@dataclass
class WorkflowPlan:
    """Parsed representation of the requested workflow sequence."""

    steps: Sequence[str]
    fix_design: bool


@dataclass
class WorkflowInputs:
    """Prepared artefacts required to execute a workflow."""

    cfg: Dict[str, Any]
    table: TimeSeriesTable
    dt_h: float
    solver_name: str
    plan: WorkflowPlan


@dataclass
class _RollingParams:
    """Internal helper capturing rolling horizon parameters."""

    horizon_hours: float
    step_hours: float
    overlap_hours: float
    terminal_policy: str

    def as_steps(self, dt_h: float) -> tuple[int, int, int]:
        """Return window, commit and overlap lengths measured in simulation steps."""

        if dt_h <= 0:
            raise ValueError("dt_h must be positive")
        horizon_steps = _hours_to_steps(self.horizon_hours, dt_h, "HEAT_HORIZON_HOURS")
        step_steps = _hours_to_steps(self.step_hours, dt_h, "STEP_HOURS")
        overlap_steps = _hours_to_steps(self.overlap_hours, dt_h, "OVERLAP_HOURS") if self.overlap_hours else 0
        if step_steps > horizon_steps:
            raise ValueError("STEP_HOURS must not exceed HEAT_HORIZON_HOURS")
        if overlap_steps >= step_steps:
            raise ValueError("OVERLAP_HOURS must be smaller than STEP_HOURS")
        return horizon_steps, step_steps, overlap_steps


@dataclass
class WorkflowContext:
    """Mutable state shared between workflow steps."""

    cfg: Dict[str, Any]
    table: TimeSeriesTable
    dt_h: float
    solver_name: str
    plan: WorkflowPlan
    pf_result: Optional[ScenarioResult] = None
    rh_result: Optional[RollingHorizonResult] = None
    mpc_result: Optional[RollingHorizonResult] = None
    design: Optional[DesignData] = None


@dataclass
class _CostAggregationPlan:
    """Configuration for rolling-horizon cost handling."""

    include_investment: bool
    amortise_once: bool
    include_tie_breaker: bool
    include_installation: bool
    include_activation: bool

    def investment_active(self, window_idx: int) -> bool:
        if not self.include_investment:
            return False
        if self.amortise_once and window_idx > 0:
            return False
        return True


StepHandler = Callable[[WorkflowContext], None]


logger = logging.getLogger(__name__)


_STEP_HANDLERS: Dict[str, StepHandler] = {}


# ============================================================================
# Helper functions migrated from orchestrator.py
# ============================================================================

def _json_safe(value: Any) -> Any:
    """Return a JSON-serialisable representation of ``value``.

    The solver meta data pulled from Pyomo occasionally contains sentinel
    objects such as ``UndefinedData`` which the standard :mod:`json` module
    cannot serialise.  We normalise those values (and other non-primitive
    objects) so that exporting results to JSON never fails.
    """

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(val) for val in value]
    if HAVE_PYOMO and value.__class__.__name__ == "UndefinedData":  # pragma: no cover - depends on Pyomo
        return None
    return str(value)


def _estimate_max_thermal_capacity(cfg: dict) -> float:
    from energis.utils.config_utils import apply_heat_pump_defaults
    syscfg = cfg.get("system", {})
    cap = 0.0
    for hp in apply_heat_pump_defaults(syscfg):
        if hp.get("enabled", True):
            cap += float(hp.get("max_th_mw", 0.0))
    gens = syscfg.get("generators", {})
    for _, par in gens.items():
        if par.get("enabled", False):
            cap += float(par.get("cap_th_mw", 0.0))
    return cap


def _assert_capacity_vs_demand(table: TimeSeriesTable, cfg: dict, safety: float = 1.1) -> None:
    from energis.constants import CAPACITY_SAFETY_FACTOR
    safety = CAPACITY_SAFETY_FACTOR
    peak_demand = max(table["waermebedarf_MWth"])
    cap = _estimate_max_thermal_capacity(cfg)
    if cap < safety * peak_demand and peak_demand > 0:
        raise RuntimeError(
            "Thermische Maximalleistung zu gering für den Demand-Peak. Bitte Kapazitäten erhöhen."
        )


def _gather_component_metadata(cfg: Dict[str, Any]) -> Dict[str, Any]:
    from energis.utils.config_utils import apply_heat_pump_defaults
    meta: Dict[str, Any] = {
        "heat_pumps": [],
        "storage": None,
        "generators": [],
        "p2h": None,
    }

    syscfg = cfg.get("system", {})

    for hp in apply_heat_pump_defaults(syscfg):
        if not hp.get("enabled", True):
            continue
        inv_cfg = hp.get("investment", {})
        cap_min = float(inv_cfg.get("capacity_min_mw", hp.get("min_th_mw", 0.0)))
        cap_max = float(inv_cfg.get("capacity_max_mw", hp.get("max_th_mw", 0.0)))
        if inv_cfg.get("enabled", False):
            cap_init = float(
                inv_cfg.get(
                    "initial_capacity_mw",
                    max(cap_min, min(cap_max, hp.get("max_th_mw", cap_max))),
                )
            )
        else:
            cap_init = float(hp.get("max_th_mw", cap_max))
        meta["heat_pumps"].append(
            {
                "id": str(hp.get("id", "HP")),
                "max_th": float(hp.get("max_th_mw", 0.0)),
                "invest_enabled": bool(inv_cfg.get("enabled", False)),
                "cap_min": cap_min,
                "cap_max": cap_max,
                "cap_init": cap_init,
            }
        )

    sto_cfg = syscfg.get("storage", {})
    if sto_cfg.get("enabled", False):
        inv_cfg = sto_cfg.get("investment", {})
        e_cap_min = float(
            inv_cfg.get("energy_capacity_min_mwh", sto_cfg.get("min_energy_mwh", 0.0))
        )
        e_cap_max = float(
            inv_cfg.get("energy_capacity_max_mwh", sto_cfg.get("max_energy_mwh", 0.0))
        )
        p_cap_min = float(
            inv_cfg.get("power_capacity_min_mw", sto_cfg.get("min_power_mw", 0.0))
        )
        p_cap_max = float(
            inv_cfg.get("power_capacity_max_mw", sto_cfg.get("max_power_mw", 0.0))
        )
        if inv_cfg.get("enabled", False):
            e_cap_init = float(
                inv_cfg.get(
                    "initial_energy_capacity_mwh",
                    max(e_cap_min, min(e_cap_max, sto_cfg.get("max_energy_mwh", e_cap_max))),
                )
            )
            p_cap_init = float(
                inv_cfg.get(
                    "initial_power_capacity_mw",
                    max(p_cap_min, min(p_cap_max, sto_cfg.get("max_power_mw", p_cap_max))),
                )
            )
        else:
            e_cap_init = float(sto_cfg.get("max_energy_mwh", e_cap_max))
            p_cap_init = float(sto_cfg.get("max_power_mw", p_cap_max))

        meta["storage"] = {
            "name": sto_cfg.get("id", "TES") or "TES",
            "e_max": float(sto_cfg.get("max_energy_mwh", 0.0)),
            "p_max": float(sto_cfg.get("max_power_mw", 0.0)),
            "invest_enabled": bool(inv_cfg.get("enabled", False)),
            "e_cap_min": e_cap_min,
            "e_cap_max": e_cap_max,
            "p_cap_min": p_cap_min,
            "p_cap_max": p_cap_max,
            "e_cap_init": e_cap_init,
            "p_cap_init": p_cap_init,
        }

    fuels = cfg.get("fuels", {})
    gen_cfg = cfg.get("generators", {})

    for key, par in syscfg.get("generators", {}).items():
        if not par.get("enabled", False):
            continue
        if key == "p2h":
            meta["p2h"] = {
                "name": "P2H",
                "cap_th": float(par.get("cap_th_mw", 0.0)),
                "eff": float(gen_cfg.get("p2h", {}).get("el_to_th_eff", 0.0)),
            }
            continue

        gpar = gen_cfg.get(key, {})
        fuel_bus = gpar.get("fuel_bus", "gas")
        fuel_info = fuels.get(fuel_bus, {})
        meta["generators"].append(
            {
                "key": key,
                "name": key.upper(),
                "cap_th": float(par.get("cap_th_mw", 0.0)),
                "fuel_bus": fuel_bus,
                "fuel_price": float(fuel_info.get("price_eur_mwh", 0.0)),
                "fuel_emission": float(fuel_info.get("ef_kg_per_mwh_fuel", 0.0)),
                "has_el": gpar.get("el_eff") is not None,
            }
        )

    return meta


def _flatten_summary(sections: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for section, metrics in sections.items():
        for key, value in metrics.items():
            flat[f"{section}.{key}"] = value
    return flat


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_design_from_summary(
    summary_sections: Mapping[str, Mapping[str, Any]]
) -> OrderedDict[str, Any]:
    heat_pumps: OrderedDict[str, Dict[str, float]] = OrderedDict()
    storage_entry: OrderedDict[str, float] | None = None

    for section, metrics in summary_sections.items():
        if not isinstance(metrics, Mapping):
            continue
        if section.startswith("heat_pump_"):
            hp_id = section.split("heat_pump_", 1)[1] or section
            heat_pumps[hp_id] = {
                "capacity_mw": _as_float(metrics.get("Thermal_capacity_MW")),
                "build_binary": _as_float(
                    metrics.get("Build_binary", metrics.get("Build"))
                ),
            }
        elif section.startswith("storage_"):
            storage_entry = OrderedDict(
                [
                    ("name", section.split("storage_", 1)[1] or section),
                    ("capacity_mwh", _as_float(metrics.get("Capacity_MWh"))),
                    ("power_mw", _as_float(metrics.get("Power_limit_MW"))),
                    (
                        "build_binary",
                        _as_float(metrics.get("Build_binary", metrics.get("Build"))),
                    ),
                ]
            )

    design = OrderedDict()
    design["heat_pumps"] = heat_pumps
    design["storage"] = storage_entry
    return design


def _collect_timeseries_and_summary(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float,
    model: Any | None,
) -> tuple[OrderedDict[str, List[float]], OrderedDict[str, OrderedDict[str, Any]], Dict[str, Any]]:
    """Collect optimization results into time series and summary dictionaries.

    Extracts decision variable values from solved Pyomo model and organizes them into:
    1. Time series data - hourly flows, states, and operational values
    2. Component summaries - aggregated metrics per component (energy, costs, capacity)
    3. System-level KPIs - total costs, CO2 emissions, investment decisions

    This function handles:
    - Grid electricity purchase and sales
    - Heat pump operation and waste heat recovery
    - Storage state of charge and flows
    - Thermal generator outputs
    - Bus balances and slack variables
    - Investment costs (CAPEX) and operational costs (OPEX)
    - CO2 emissions accounting

    Args:
        table (TimeSeriesTable): Input time series with demand and price data
        cfg (Dict[str, Any]): System configuration with component definitions
        dt_h (float): Time step duration in hours
        model (Any | None): Solved Pyomo model with optimal variable values.
            If None, returns zero-filled results.

    Returns:
        tuple containing:
            - OrderedDict[str, List[float]]: Time series data with keys like:
                "P_buy_MW", "P_sell_MW", "HP1_Q_MWth", "TES_SOC_MWh", etc.
            - OrderedDict[str, OrderedDict[str, Any]]: Component summaries with keys like:
                "HP1": {"energy_MWh": X, "capex_EUR": Y, "capacity_MW": Z, ...}
            - Dict[str, Any]: System KPIs including:
                "total_cost_EUR", "capex_total_EUR", "opex_total_EUR",
                "grid_import_MWh", "co2_total_kg", etc.

    Note:
        If model is None (e.g., Pyomo not available), returns empty/zero-filled structures.
        All monetary values are in EUR, energy in MWh, power in MW, emissions in kg CO2.
    """
    from energis.constants import HOURS_PER_YEAR
    meta = _gather_component_metadata(cfg)
    n = len(table)
    grid_cfg = cfg.get("grid", {})
    period_fraction = float(n * dt_h / HOURS_PER_YEAR) if n else 0.0
    demand_year_fraction = float(grid_cfg.get("year_fraction", period_fraction))

    series: OrderedDict[str, List[float]] = OrderedDict()
    series["P_buy_MW"] = [0.0] * n
    series["P_sell_MW"] = [0.0] * n
    series["Q_dump_MWth"] = [0.0] * n

    for hp in meta["heat_pumps"]:
        comp = hp["id"]
        series[f"{comp}_Q_th_MW"] = [0.0] * n
        series[f"{comp}_Pel_MW"] = [0.0] * n
        series[f"{comp}_on"] = [0.0] * n
        series[f"{comp}_Q_wrg_MW"] = [0.0] * n
        series[f"{comp}_Q_def_MW"] = [0.0] * n
        series[f"{comp}_COP"] = [0.0] * n

    if meta["storage"]:
        series["TES_SOC_MWh"] = [0.0] * n
        series["TES_charge_MW"] = [0.0] * n
        series["TES_discharge_MW"] = [0.0] * n

    for gen in meta["generators"]:
        comp = gen["name"]
        series[f"{comp}_Q_th_MW"] = [0.0] * n
        series[f"{comp}_fuel_MW"] = [0.0] * n
        if gen["has_el"]:
            series[f"{comp}_Pel_MW"] = [0.0] * n

    if meta["p2h"]:
        series["P2H_Q_th_MW"] = [0.0] * n
        series["P2H_Pel_MW"] = [0.0] * n

    objective = OrderedDict(
        [
            ("OBJ_value_EUR", 0.0),
            ("P_buy_peak_MW", 0.0),
            # Detailed electricity cost breakdown
            ("Grid_energy_cost_EUR", 0.0),  # Total (for backward compatibility)
            ("Electricity_base_cost_EUR", 0.0),  # Strompreis * Energie
            ("Electricity_energy_fee_EUR", 0.0),  # Energy fee
            ("Electricity_grid_fee_EUR", 0.0),  # Netzentgelte (gridcost)
            ("Grid_sell_revenue_EUR", 0.0),
            ("Grid_net_cost_EUR", 0.0),
            # Fuel costs (total and by type)
            ("Fuel_cost_EUR", 0.0),  # Total (for backward compatibility)
            ("Fuel_emissions_t", 0.0),
            ("Dump_cost_EUR", 0.0),
            ("CO2_cost_EUR", 0.0),
            ("CO2_price_EUR_per_t", float(cfg.get("costs", {}).get("co2_price_eur_per_t", 0.0))),
            ("Include_CO2_in_objective", bool(cfg.get("costs", {}).get("include_co2_cost_in_objective", True))),
            ("Demand_charge_cost_EUR", 0.0),  # Leistungspreis
            # Investment costs (CAPEX breakdown)
            ("Capex_cost_EUR", 0.0),  # Total CAPEX
            ("Capex_heat_pumps_EUR", 0.0),  # CAPEX for heat pumps
            ("Capex_storage_EUR", 0.0),  # CAPEX for storage
            ("Activation_cost_EUR", 0.0),
            ("Tie_breaker_cost_EUR", 0.0),
            ("Storage_installation_cost_EUR", 0.0),
            ("Period_fraction_of_year", period_fraction),
            ("Demand_charge_year_fraction", demand_year_fraction),
            ("Objective_residual_EUR", 0.0),
        ]
    )

    grid_summary = OrderedDict(
        [
            ("Energy_from_grid_MWh", 0.0),
            ("Energy_to_grid_MWh", 0.0),
            ("Net_grid_import_MWh", 0.0),
            ("Average_purchase_price_EUR_MWh", 0.0),
            ("Average_sell_price_EUR_MWh", 0.0),
            ("Heat_dumped_MWh", 0.0),
            ("Dump_cost_rate_EUR_MWh", float(cfg.get("costs", {}).get("dump_cost_eur_per_mwh_th", 0.0))),
            ("Grid_CO2_emissions_t", 0.0),
            ("Total_CO2_emissions_t", 0.0),
        ]
    )

    summary_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    summary_sections["objective"] = objective
    summary_sections["grid"] = grid_summary

    storage_section: OrderedDict[str, Any] | None = None
    if meta["storage"]:
        storage_key = f"storage_{meta['storage']['name']}"
        storage_section = OrderedDict(
            [
                ("Charge_MWh", 0.0),
                ("Discharge_MWh", 0.0),
                ("Average_SOC_MWh", 0.0),
                ("Min_SOC_MWh", 0.0),
                ("Max_SOC_MWh", 0.0),
                ("Capacity_MWh", meta["storage"]["e_max"]),
                ("Power_limit_MW", meta["storage"]["p_max"]),
                ("Build_binary", 0.0),
                ("Investment_enabled", bool(meta["storage"].get("invest_enabled", False))),
            ]
        )
        summary_sections[storage_key] = storage_section

    heat_pump_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    generator_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    p2h_section: OrderedDict[str, Any] | None = None

    if model is not None and HAVE_PYOMO:
        times = list(model.t)

        def _extract(var: Any | None, key: str) -> None:
            if var is None:
                return
            try:
                series[key] = _extract_pyomo_series(var, times, key)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Fehler beim Verarbeiten der Serie %s: %s", key, exc)


        _extract(getattr(model, "P_buy", None), "P_buy_MW")
        _extract(getattr(model, "P_sell", None), "P_sell_MW")
        _extract(getattr(model, "Q_dump", None), "Q_dump_MWth")

        for hp in meta["heat_pumps"]:
            comp = hp["id"]
            _extract(getattr(model, f"{comp}_Q", None), f"{comp}_Q_th_MW")
            _extract(getattr(model, f"{comp}_Pel", None), f"{comp}_Pel_MW")
            _extract(getattr(model, f"{comp}_on", None), f"{comp}_on")
            _extract(getattr(model, f"{comp}_Q_wrg", None), f"{comp}_Q_wrg_MW")
            _extract(getattr(model, f"{comp}_Q_def", None), f"{comp}_Q_def_MW")

        if meta["storage"]:
            _extract(getattr(model, "TES_E", None), "TES_SOC_MWh")
            _extract(getattr(model, "TES_Qc", None), "TES_charge_MW")
            _extract(getattr(model, "TES_Qd", None), "TES_discharge_MW")

        for gen in meta["generators"]:
            comp = gen["name"]
            _extract(getattr(model, f"{comp}_Qth", None), f"{comp}_Q_th_MW")
            _extract(getattr(model, f"{comp}_fuel", None), f"{comp}_fuel_MW")
            if gen["has_el"]:
                _extract(getattr(model, f"{comp}_Pel", None), f"{comp}_Pel_MW")

        if meta["p2h"]:
            _extract(getattr(model, "P2H_Qth", None), "P2H_Q_th_MW")
            _extract(getattr(model, "P2H_Pel", None), "P2H_Pel_MW")

        objective["OBJ_value_EUR"] = float(pyo.value(model.obj)) if hasattr(model, "obj") else 0.0
        objective["P_buy_peak_MW"] = float(pyo.value(model.P_buy_peak)) if hasattr(model, "P_buy_peak") else 0.0
    else:
        times = list(range(1, n + 1))
        objective["OBJ_value_EUR"] = 0.0
        objective["P_buy_peak_MW"] = max(series["P_buy_MW"], default=0.0)

    price_series = table.data.get("strompreis_EUR_MWh", [0.0] * n)
    grid_co2_series = table.data.get("grid_co2_kg_MWh", [0.0] * n)
    demand_series = table.data.get("waermebedarf_MWth", [0.0] * n)

    # ✅ FIX: Export grid_co2_kg_MWh to series for dashboard timeseries plots
    series["grid_co2_kg_MWh"] = list(grid_co2_series)

    # ✅ FIX: Calculate Grid CO2 emissions timeseries (in tonnes per timestep)
    series["Grid_CO2_emissions_t_per_step"] = [
        pbuy_series[i] * grid_co2_series[i] * dt_h / 1000.0 for i in range(n)
    ] if n else []

    # Fuel CO2 timeseries will be calculated below after generator loop
    series["Fuel_CO2_emissions_t_per_step"] = [0.0] * n

    include_gridcost = bool(cfg.get("costs", {}).get("include_gridcost_in_energy", False))
    energy_fee = float(grid_cfg.get("energy_fee_eur_mwh", 0.0))
    grid_cost = float(grid_cfg.get("gridcost_eur_mwh", 0.0))
    include_co2 = bool(cfg.get("costs", {}).get("include_co2_cost_in_objective", True))
    dump_cost_rate = float(cfg.get("costs", {}).get("dump_cost_eur_per_mwh_th", 0.0))
    include_demand = bool(grid_cfg.get("include_demand_charge_in_rh", cfg.get("costs", {}).get("include_demand_charge_in_rh", True)))
    demand_charge_rate = float(grid_cfg.get("demand_charge_eur_per_mw_y", 0.0))

    sell_floor = float(grid_cfg.get("sell_floor_eur_mwh", 0.0))
    sell_haircut = float(grid_cfg.get("sell_haircut_fraction", 0.0))
    sell_spread = float(grid_cfg.get("sell_spread_eur_mwh", 0.0))
    sell_fee = float(grid_cfg.get("sell_fee_eur_mwh", 0.0))
    sell_premium = float(grid_cfg.get("sell_premium_eur_mwh", 0.0))

    pbuy_series = series["P_buy_MW"]
    psell_series = series["P_sell_MW"]
    qdump_series = series["Q_dump_MWth"]

    addition = (energy_fee + grid_cost) if include_gridcost else 0.0

    def _sell_price(base: float) -> float:
        price = max(base - sell_spread, sell_floor)
        price = price * max(0.0, 1.0 - sell_haircut)
        price = price - sell_fee + sell_premium
        return max(price, 0.0)

    buy_prices = [price_series[i] + addition for i in range(n)] if n else []
    sell_prices = [_sell_price(price_series[i]) for i in range(n)] if n else []

    energy_in = float(sum(pbuy_series) * dt_h)
    energy_out = float(sum(psell_series) * dt_h)
    heat_dump = float(sum(qdump_series) * dt_h)

    # Calculate detailed electricity costs
    base_electricity_cost = float(sum((pbuy_series[i] * price_series[i] * dt_h) for i in range(n))) if n else 0.0
    energy_fee_cost = float(energy_in * energy_fee)
    grid_fee_cost = float(energy_in * grid_cost)
    energy_cost = float(sum((pbuy_series[i] * buy_prices[i] * dt_h) for i in range(n))) if n else 0.0

    energy_revenue = float(sum((psell_series[i] * sell_prices[i] * dt_h) for i in range(n))) if n else 0.0
    grid_co2_t = float(sum((pbuy_series[i] * grid_co2_series[i] * dt_h) for i in range(n)) / 1000.0) if n else 0.0

    heat_demand_mwh = float(sum(demand_series) * dt_h) if n else 0.0

    fuel_cost_total = 0.0
    fuel_emissions_t = 0.0
    fuel_cost_by_type: Dict[str, float] = {}  # Track fuel costs by fuel type (gas, biomass, etc.)
    capex_cost = 0.0
    capex_heat_pumps = 0.0
    capex_storage = 0.0
    activation_cost = 0.0
    tie_break_cost = 0.0
    storage_install_cost = 0.0

    if model is not None and HAVE_PYOMO:
        capex_expr = getattr(model, "capex_cost_expr", None)
        activation_expr = getattr(model, "activation_cost_expr", None)
        tie_expr = getattr(model, "tie_break_cost_expr", None)
        storage_install_expr = getattr(model, "storage_install_cost_expr", None)
        if capex_expr is not None:
            try:
                capex_cost = float(pyo.value(capex_expr))
            except Exception:  # pragma: no cover - defensive
                capex_cost = 0.0
        if activation_expr is not None:
            try:
                activation_cost = float(pyo.value(activation_expr))
            except Exception:  # pragma: no cover - defensive
                activation_cost = 0.0
        if tie_expr is not None:
            try:
                tie_break_cost = float(pyo.value(tie_expr))
            except Exception:  # pragma: no cover - defensive
                tie_break_cost = 0.0
        if storage_install_expr is not None:
            try:
                storage_install_cost = float(pyo.value(storage_install_expr))
            except Exception:  # pragma: no cover - defensive
                storage_install_cost = 0.0

        # Calculate CAPEX breakdown by component type
        # Extract heat pump CAPEX
        for hp in meta["heat_pumps"]:
            comp = hp["id"]
            if hp.get("invest_enabled", False):
                cap_var = getattr(model, f"{comp}_cap_mw", None)
                if cap_var is not None:
                    try:
                        cap_value = float(pyo.value(cap_var))
                        inv_cfg = cfg.get("system", {}).get("heat_pumps", [{}])[0].get("investment", {})
                        capex_rate = float(inv_cfg.get("capex_eur_per_mw", 0.0))
                        lifetime = float(inv_cfg.get("lifetime_years", 1.0))
                        annual_factor = period_fraction / lifetime if lifetime > 0 else 0.0
                        capex_heat_pumps += cap_value * capex_rate * annual_factor
                    except Exception:  # pragma: no cover - defensive
                        pass

        # Extract storage CAPEX
        if meta["storage"] and meta["storage"].get("invest_enabled", False):
            cap_e_var = getattr(model, "TES_cap_energy", None)
            if cap_e_var is not None:
                try:
                    cap_e_value = float(pyo.value(cap_e_var))
                    sto_cfg = cfg.get("system", {}).get("storage", {})
                    inv_cfg = sto_cfg.get("investment", {})
                    e_capex = float(inv_cfg.get("energy_capex_eur_per_mwh", 0.0))
                    lifetime = float(inv_cfg.get("lifetime_years", 1.0))
                    annual_factor = period_fraction / lifetime if lifetime > 0 else 0.0
                    capex_storage += cap_e_value * e_capex * annual_factor
                except Exception:  # pragma: no cover - defensive
                    pass

    for hp in meta["heat_pumps"]:
        comp = hp["id"]
        heat_series = series[f"{comp}_Q_th_MW"]
        pel_series = series[f"{comp}_Pel_MW"]
        on_series = series[f"{comp}_on"]
        cop_series = []
        for heat, pel in zip(heat_series, pel_series):
            if pel > 1e-9:
                cop_series.append(float(heat / pel))
            else:
                cop_series.append(0.0)
        series[f"{comp}_COP"] = cop_series
        heat_mwh = float(sum(heat_series) * dt_h)
        pel_mwh = float(sum(pel_series) * dt_h)
        on_hours = float(sum(on_series) * dt_h)
        cap_value = float(hp.get("cap_init", hp["max_th"]))
        build_value = 1.0 if cap_value > 0 else 0.0
        if model is not None and HAVE_PYOMO:
            cap_var = getattr(model, f"{comp}_cap_mw", None)
            build_var = getattr(model, f"{comp}_build", None)
            if cap_var is not None:
                try:
                    cap_value = float(pyo.value(cap_var))
                except Exception:  # pragma: no cover - defensive
                    cap_value = float(hp.get("cap_init", hp["max_th"]))
            if build_var is not None:
                try:
                    build_value = float(pyo.value(build_var))
                except Exception:  # pragma: no cover - defensive
                    build_value = 1.0 if cap_value > 0 else 0.0
        full_load = float((heat_mwh / cap_value) if cap_value > 1e-9 else 0.0)
        avg_cop = float((heat_mwh / pel_mwh) if pel_mwh > 1e-9 else 0.0)
        heat_pump_sections[f"heat_pump_{comp}"] = OrderedDict(
            [
                ("Heat_output_MWh", heat_mwh),
                ("Electricity_input_MWh", pel_mwh),
                ("Operating_hours_h", on_hours),
                ("Full_load_hours_h", full_load),
                ("Thermal_capacity_MW", cap_value),
                ("Build_binary", build_value),
                ("Investment_enabled", bool(hp.get("invest_enabled", False))),
                (
                    "Capacity_bounds_MW",
                    [hp.get("cap_min", 0.0), hp.get("cap_max", hp.get("max_th", cap_value))],
                ),
                ("Average_COP", avg_cop),
            ]
        )

    for gen in meta["generators"]:
        comp = gen["name"]
        heat_series = series[f"{comp}_Q_th_MW"]
        fuel_series = series[f"{comp}_fuel_MW"]
        heat_mwh = float(sum(heat_series) * dt_h)
        fuel_mwh = float(sum(fuel_series) * dt_h)
        pel_mwh = float(sum(series.get(f"{comp}_Pel_MW", [0.0] * n)) * dt_h) if gen["has_el"] else 0.0
        emission_t = float(fuel_mwh * gen["fuel_emission"] / 1000.0)
        cost_eur = float(fuel_mwh * gen["fuel_price"])

        # Track fuel costs by fuel type
        fuel_bus = gen["fuel_bus"]
        if fuel_bus not in fuel_cost_by_type:
            fuel_cost_by_type[fuel_bus] = 0.0
        fuel_cost_by_type[fuel_bus] += cost_eur

        entry = OrderedDict(
            [
                ("Heat_output_MWh", heat_mwh),
                ("Fuel_input_MWh", fuel_mwh),
                ("Fuel_cost_EUR", cost_eur),
                ("Fuel_price_EUR_MWh", gen["fuel_price"]),
                ("Fuel_emissions_t", emission_t),
                ("Fuel_bus", gen["fuel_bus"]),
                ("Thermal_capacity_MW", gen["cap_th"]),
            ]
        )
        if gen["has_el"]:
            entry["Power_output_MWh"] = float(pel_mwh)
        generator_sections[f"generator_{comp}"] = entry
        fuel_cost_total += cost_eur
        fuel_emissions_t += emission_t

        # ✅ FIX: Add fuel CO2 emissions per timestep (in tonnes)
        fuel_emission_factor_kg_per_mwh = gen["fuel_emission"]
        for i in range(n):
            fuel_co2_t = fuel_series[i] * dt_h * fuel_emission_factor_kg_per_mwh / 1000.0
            series["Fuel_CO2_emissions_t_per_step"][i] += fuel_co2_t

    if meta["p2h"]:
        comp = meta["p2h"]["name"]
        heat_series = series[f"{comp}_Q_th_MW"]
        pel_series = series[f"{comp}_Pel_MW"]
        heat_mwh = float(sum(heat_series) * dt_h)
        pel_mwh = float(sum(pel_series) * dt_h)
        p2h_section = OrderedDict(
            [
                ("Heat_output_MWh", heat_mwh),
                ("Electricity_input_MWh", pel_mwh),
                ("Thermal_capacity_MW", meta["p2h"]["cap_th"]),
            ]
        )
        if meta["p2h"]["eff"]:
            p2h_section["Configured_efficiency"] = meta["p2h"]["eff"]

    if storage_section and meta["storage"]:
        charge_series = series["TES_charge_MW"]
        discharge_series = series["TES_discharge_MW"]
        soc_series = series["TES_SOC_MWh"]
        energy_cap = float(meta["storage"].get("e_cap_init", meta["storage"]["e_max"]))
        power_cap = float(meta["storage"].get("p_cap_init", meta["storage"]["p_max"]))
        build_val = 1.0 if energy_cap > 0 else 0.0
        if model is not None and HAVE_PYOMO:
            cap_e_var = getattr(model, "TES_cap_energy", None)
            cap_p_var = getattr(model, "TES_cap_power", None)
            build_var = getattr(model, "TES_build", None)
            if cap_e_var is not None:
                try:
                    energy_cap = float(pyo.value(cap_e_var))
                except Exception:  # pragma: no cover - defensive
                    energy_cap = float(meta["storage"].get("e_cap_init", meta["storage"]["e_max"]))
            if cap_p_var is not None:
                try:
                    power_cap = float(pyo.value(cap_p_var))
                except Exception:  # pragma: no cover - defensive
                    power_cap = float(meta["storage"].get("p_cap_init", meta["storage"]["p_max"]))
            if build_var is not None:
                try:
                    build_val = float(pyo.value(build_var))
                except Exception:  # pragma: no cover - defensive
                    build_val = 1.0 if energy_cap > 0 else 0.0
        storage_section["Charge_MWh"] = float(sum(charge_series) * dt_h)
        storage_section["Discharge_MWh"] = float(sum(discharge_series) * dt_h)
        storage_section["Average_SOC_MWh"] = float(sum(soc_series) / len(soc_series)) if n else 0.0
        storage_section["Min_SOC_MWh"] = float(min(soc_series)) if soc_series else 0.0
        storage_section["Max_SOC_MWh"] = float(max(soc_series)) if soc_series else 0.0
        storage_section["Capacity_MWh"] = energy_cap
        storage_section["Power_limit_MW"] = power_cap
        storage_section["Build_binary"] = build_val
        storage_section["Capacity_bounds_MWh"] = [
            meta["storage"].get("e_cap_min", 0.0),
            meta["storage"].get("e_cap_max", energy_cap),
        ]
        storage_section["Power_bounds_MW"] = [
            meta["storage"].get("p_cap_min", 0.0),
            meta["storage"].get("p_cap_max", power_cap),
        ]

    total_emissions_t = float(grid_co2_t + fuel_emissions_t)
    co2_price = float(cfg.get("costs", {}).get("co2_price_eur_per_t", 0.0))
    co2_cost = float(co2_price * total_emissions_t) if include_co2 else 0.0
    dump_cost = float(dump_cost_rate * heat_dump)

    demand_cost = 0.0
    if include_demand:
        if model is not None and HAVE_PYOMO and hasattr(model, "P_buy_peak"):
            peak = float(pyo.value(model.P_buy_peak))
        else:
            peak = float(max(pbuy_series, default=0.0))
        objective["P_buy_peak_MW"] = peak
        demand_cost = float(demand_charge_rate * demand_year_fraction * peak)
    else:
        objective["P_buy_peak_MW"] = float(max(pbuy_series, default=0.0))

    # Detailed electricity cost breakdown
    objective["Grid_energy_cost_EUR"] = energy_cost
    objective["Electricity_base_cost_EUR"] = base_electricity_cost
    objective["Electricity_energy_fee_EUR"] = energy_fee_cost
    objective["Electricity_grid_fee_EUR"] = grid_fee_cost
    objective["Grid_sell_revenue_EUR"] = energy_revenue
    objective["Grid_net_cost_EUR"] = energy_cost - energy_revenue

    # Total fuel costs and by fuel type
    objective["Fuel_cost_EUR"] = fuel_cost_total
    for fuel_type, fuel_cost in fuel_cost_by_type.items():
        objective[f"Fuel_cost_{fuel_type}_EUR"] = fuel_cost
    objective["Fuel_emissions_t"] = fuel_emissions_t

    objective["Dump_cost_EUR"] = dump_cost
    objective["CO2_cost_EUR"] = co2_cost
    objective["Demand_charge_cost_EUR"] = demand_cost

    # CAPEX breakdown
    objective["Capex_cost_EUR"] = capex_cost
    objective["Capex_heat_pumps_EUR"] = capex_heat_pumps
    objective["Capex_storage_EUR"] = capex_storage
    objective["Activation_cost_EUR"] = activation_cost
    objective["Tie_breaker_cost_EUR"] = tie_break_cost
    objective["Storage_installation_cost_EUR"] = storage_install_cost

    components_sum = (
        energy_cost
        - energy_revenue
        + fuel_cost_total
        + dump_cost
        + co2_cost
        + demand_cost
        + capex_cost
        + activation_cost
        + tie_break_cost
        + storage_install_cost
    )
    objective["Objective_residual_EUR"] = objective["OBJ_value_EUR"] - components_sum

    grid_summary["Energy_from_grid_MWh"] = energy_in
    grid_summary["Energy_to_grid_MWh"] = energy_out
    grid_summary["Net_grid_import_MWh"] = energy_in - energy_out
    grid_summary["Average_purchase_price_EUR_MWh"] = float(energy_cost / energy_in) if energy_in else 0.0
    grid_summary["Average_sell_price_EUR_MWh"] = float(energy_revenue / energy_out) if energy_out else 0.0
    grid_summary["Heat_dumped_MWh"] = heat_dump
    grid_summary["Grid_CO2_emissions_t"] = grid_co2_t
    grid_summary["Total_CO2_emissions_t"] = total_emissions_t
    grid_summary["Heat_demand_MWh"] = heat_demand_mwh

    for name, section in heat_pump_sections.items():
        summary_sections[name] = section
    for name, section in generator_sections.items():
        summary_sections[name] = section
    if p2h_section:
        summary_sections["p2h"] = p2h_section

    # ✅ FIX: Calculate total CO2 emissions per timestep (Grid + Fuel)
    series["Total_CO2_emissions_t_per_step"] = [
        series["Grid_CO2_emissions_t_per_step"][i] + series["Fuel_CO2_emissions_t_per_step"][i]
        for i in range(n)
    ] if n else []

    flat = _flatten_summary(summary_sections)
    return series, summary_sections, flat


def _slugify(value: str | None) -> str:
    import re
    if not value:
        return "scenario"
    slug = re.sub(r"[^0-9a-zA-Z_-]+", "-", value.strip())
    slug = re.sub(r"-+", "-", slug).strip("-_")
    return slug or "scenario"


def _slice_table(table: TimeSeriesTable, indices: List[int]) -> TimeSeriesTable:
    new_index = [table.index[i] for i in indices]
    new_data = {col: [table[col][i] for i in indices] for col in table.columns}
    return TimeSeriesTable(new_index, table.columns[:], new_data)


def _parse_ts(value: Any) -> datetime:
    from datetime import datetime
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("Leerwert kann nicht als Datum interpretiert werden")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Kann Datum/Uhrzeit nicht interpretieren: {value!r}")


def _apply_horizon(table: TimeSeriesTable, scenario_cfg: Dict[str, Any], dt_h: float) -> TimeSeriesTable:
    import calendar
    from energis.constants import HOURS_PER_YEAR, HOURS_PER_LEAP_YEAR
    horizon = scenario_cfg.get("horizon")
    if not isinstance(horizon, dict):
        return table

    htype = str(horizon.get("type", "")).lower()
    if htype == "full_year":
        year = horizon.get("year")
        if year is None:
            if not table.index:
                raise RuntimeError("Zeitscheiben leer – kein Jahr auswählbar")
            year = table.index[0].year
        year = int(year)
        enforce = bool(horizon.get("enforce", True))
        indices = [i for i, ts in enumerate(table.index) if ts.year == year]
        if not indices:
            raise RuntimeError(f"Im Jahr {year} wurden keine Zeitschritte gefunden.")
        subset = _slice_table(table, indices)
        subset.ensure_frequency(dt_h)
        expected_hours = HOURS_PER_LEAP_YEAR if calendar.isleap(year) else HOURS_PER_YEAR
        actual_hours = len(subset) * dt_h
        diff = abs(actual_hours - expected_hours)
        if diff > 1e-6 and enforce:
            raise RuntimeError(
                f"Zeitraum deckt nicht das komplette Jahr {year} ab (erwartet {expected_hours} Stunden, gefunden {actual_hours})."
            )
        if diff > 1e-6 and not enforce:
            print(
                f"[SCENARIO] Hinweis: Daten decken nur {actual_hours} von {expected_hours} Stunden ab (enforce=false)."
            )
        print(f"[SCENARIO] Volles Jahr {year}: {len(subset)} Schritte ({subset.index[0]} → {subset.index[-1]})")
        return subset

    start = horizon.get("start")
    end = horizon.get("end")
    if start is None and end is None:
        return table

    start_dt = _parse_ts(start) if start is not None else None
    end_dt = _parse_ts(end) if end is not None else None
    if start_dt and end_dt and start_dt > end_dt:
        raise RuntimeError("Ungültiger Zeithorizont: Start liegt nach dem Ende")
    indices = []
    for i, ts in enumerate(table.index):
        if start_dt and ts < start_dt:
            continue
        if end_dt and ts > end_dt:
            continue
        indices.append(i)
    if not indices:
        raise RuntimeError("Zeithorizont enthält keine Zeitschritte")
    subset = _slice_table(table, indices)
    subset.ensure_frequency(dt_h)
    print(f"[SCENARIO] Zeitraum {subset.index[0]} → {subset.index[-1]} ({len(subset)} Schritte)")
    return subset


def _extract_pyomo_series(var: Any, times: Sequence[Any], name: str, tolerance: float = 1e-9) -> List[float]:
    values: List[float] = []
    for t in times:
        try:
            raw = pyo.value(var[t])
        except Exception as exc:  # pragma: no cover - requires Pyomo specific failures
            logger.warning("Konnte Pyomo-Wert %s[%s] nicht auslesen: %s", name, t, exc)
            values.append(0.0)
            continue

        if raw is None:
            logger.warning("Pyomo-Wert %s[%s] ist None", name, t)
            values.append(0.0)
            continue

        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Pyomo-Wert %s[%s] kann nicht in float umgewandelt werden: %s", name, t, exc
            )
            values.append(0.0)
            continue

        if not math.isfinite(number):
            logger.warning("Pyomo-Wert %s[%s] ist nicht endlich (%s)", name, t, number)
            values.append(0.0)
            continue

        if abs(number) < tolerance:
            number = 0.0

        values.append(number)

    return values


# ============================================================================
# End of migrated helper functions
# ============================================================================


_RUN_MODE_ALIASES = {
    "PF": "PF_ONLY",
    "PF_ONLY": "PF_ONLY",
    "PF_THEN_RH": "PF_THEN_RH",
    "PF_AND_RH": "PF_THEN_RH",
    "RH": "RH_ONLY",
    "RH_ONLY": "RH_ONLY",
}


def _normalise_run_mode(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().upper()
    if not key:
        return None
    return _RUN_MODE_ALIASES.get(key, key)


def _parse_run_mode(value: str) -> str:
    normalised = _normalise_run_mode(value)
    if normalised is None:
        raise argparse.ArgumentTypeError("run mode must not be empty")
    if normalised not in {"PF_ONLY", "RH_ONLY", "PF_THEN_RH"}:
        raise argparse.ArgumentTypeError(
            "run mode must be one of PF_ONLY, RH_ONLY or PF_THEN_RH"
        )
    return normalised


def _env_str(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _env_float(name: str) -> float | None:
    raw = _env_str(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - guarded by tests
        raise ValueError(f"Invalid float for {name}: {raw!r}") from exc


def _env_bool(name: str) -> bool | None:
    raw = _env_str(name)
    if raw is None:
        return None
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean for {name}: {raw!r}")


def _parse_float_list(value: str) -> List[float]:
    try:
        return [float(item) for item in value.replace(";", ",").split(",") if item.strip()]
    except ValueError as exc:  # pragma: no cover - guarded by argparse
        raise argparse.ArgumentTypeError(f"Invalid float list: {value}") from exc


@dataclass
class _OverrideValues:
    """Merged CLI/environment overrides for a single run."""

    run_mode: str | None = None
    fix_design: bool | None = None
    horizon_hours: float | None = None
    step_hours: float | None = None
    overlap_hours: float | None = None
    terminal_policy: str | None = None
    design_json: str | None = None
    include_gridcost: bool | None = None
    include_demand_charge: bool | None = None
    include_co2_cost: bool | None = None


def _gather_env_overrides() -> _OverrideValues:
    return _OverrideValues(
        run_mode=_normalise_run_mode(_env_str("RUN_MODE")),
        horizon_hours=_env_float("HEAT_HORIZON_HOURS"),
        step_hours=_env_float("STEP_HOURS"),
        overlap_hours=_env_float("OVERLAP_HOURS"),
        terminal_policy=_env_str("TERMINAL_POLICY"),
        fix_design=_env_bool("FIX_DESIGN"),
        include_gridcost=_env_bool("INCLUDE_GRIDCOST_IN_ENERGY"),
        include_demand_charge=_env_bool("INCLUDE_DEMAND_CHARGE_IN_RH"),
        include_co2_cost=_env_bool("INCLUDE_CO2_COST_IN_OBJECTIVE"),
        design_json=_env_str("PF_DESIGN_JSON"),
    )


def _merge_cli_and_env(
    args: argparse.Namespace, env_values: _OverrideValues
) -> tuple[_OverrideValues, float | None, float | None, float | None]:
    values = _OverrideValues(
        run_mode=args.run_mode or env_values.run_mode,
        fix_design=args.fix_design if args.fix_design is not None else env_values.fix_design,
        terminal_policy=args.terminal_policy or env_values.terminal_policy,
        design_json=args.pf_design_json or env_values.design_json,
        include_gridcost=(
            args.include_gridcost_in_energy
            if args.include_gridcost_in_energy is not None
            else env_values.include_gridcost
        ),
        include_demand_charge=(
            args.include_demand_charge_in_rh
            if args.include_demand_charge_in_rh is not None
            else env_values.include_demand_charge
        ),
        include_co2_cost=(
            args.include_co2_cost_in_objective
            if args.include_co2_cost_in_objective is not None
            else env_values.include_co2_cost
        ),
    )

    horizon_value = args.heat_horizon_hours
    if horizon_value is None:
        horizon_value = args.rh_window_hours if args.rh_window_hours is not None else env_values.horizon_hours

    step_value = args.step_hours if args.step_hours is not None else env_values.step_hours
    overlap_value = args.rh_overlap_hours if args.rh_overlap_hours is not None else env_values.overlap_hours
    return values, horizon_value, step_value, overlap_value


def _build_override_dict(values: _OverrideValues) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    if values.run_mode:
        _assign(overrides, ["scenario", "run_mode"], values.run_mode)
    if values.fix_design is not None:
        _assign(overrides, ["scenario", "fix_design"], bool(values.fix_design))
    if values.terminal_policy:
        _assign(overrides, ["scenario", "rolling_horizon", "terminal_policy"], str(values.terminal_policy))
    if values.design_json:
        _assign(overrides, ["scenario", "pf_design_json"], str(values.design_json))
    if values.include_gridcost is not None:
        _assign(overrides, ["costs", "include_gridcost_in_energy"], bool(values.include_gridcost))
    if values.include_demand_charge is not None:
        _assign(overrides, ["costs", "include_demand_charge_in_rh"], bool(values.include_demand_charge))
    if values.include_co2_cost is not None:
        _assign(overrides, ["costs", "include_co2_cost_in_objective"], bool(values.include_co2_cost))
    return overrides


def _expand_sensitivity_runs(
    args: argparse.Namespace,
    base_overrides: Dict[str, Any],
    horizon_value: float | None,
    step_value: float | None,
    overlap_value: float | None,
) -> List[tuple[float | None, float | None, float | None, Dict[str, Any]]]:
    def _choices(values: List[float] | None, default: float | None) -> List[float | None]:
        if values:
            return list(values)
        if default is not None:
            return [default]
        return [None]

    horizon_choices = _choices(args.sensitivity_horizon_hours, horizon_value)
    step_choices = _choices(args.sensitivity_step_hours, step_value)
    overlap_choices = _choices(args.sensitivity_overlap_hours, overlap_value)

    runs = []
    for horizon in horizon_choices:
        for step in step_choices:
            for overlap in overlap_choices:
                iter_overrides = copy.deepcopy(base_overrides)
                if horizon is not None:
                    _assign(
                        iter_overrides,
                        ["scenario", "rolling_horizon", "heat_horizon_hours"],
                        float(horizon),
                    )
                    _assign(iter_overrides, ["rolling_horizon", "heat_horizon_hours"], float(horizon))
                if step is not None:
                    _assign(iter_overrides, ["scenario", "rolling_horizon", "step_hours"], float(step))
                    _assign(iter_overrides, ["rolling_horizon", "step_hours"], float(step))
                if overlap is not None:
                    _assign(
                        iter_overrides,
                        ["scenario", "rolling_horizon", "overlap_hours"],
                        float(overlap),
                    )
                    _assign(iter_overrides, ["rolling_horizon", "overlap_hours"], float(overlap))
                runs.append((horizon, step, overlap, iter_overrides))
    return runs


def _assign(target: MutableMapping[str, Any], path: Iterable[str], value: Any) -> None:
    node: MutableMapping[str, Any] = target
    keys = list(path)
    for key in keys[:-1]:
        child = node.get(key)
        if not isinstance(child, MutableMapping):
            child = {}
            node[key] = child
        node = child
    node[keys[-1]] = value


def _design_from_mapping(data: Mapping[str, Any]) -> DesignData:
    heat_pumps: Dict[str, Dict[str, float]] = {}
    raw_hps = data.get("heat_pumps")
    if isinstance(raw_hps, Mapping):
        for hp_id, entry in raw_hps.items():
            if not isinstance(entry, Mapping):
                continue
            heat_pumps[str(hp_id)] = {
                "capacity_mw": float(entry.get("capacity_mw", entry.get("Thermal_capacity_MW", 0.0)) or 0.0),
                "build_binary": float(
                    entry.get("build_binary", entry.get("Build", entry.get("Build_binary", 0.0))) or 0.0
                ),
            }

    storage_data = data.get("storage")
    storage: Dict[str, float] | None
    if isinstance(storage_data, Mapping):
        storage = {
            "name": str(storage_data.get("name", storage_data.get("id", "TES")) or "TES"),
            "capacity_mwh": float(
                storage_data.get("capacity_mwh", storage_data.get("Capacity_MWh", 0.0)) or 0.0
            ),
            "power_mw": float(
                storage_data.get("power_mw", storage_data.get("Power_limit_MW", 0.0)) or 0.0
            ),
            "build_binary": float(
                storage_data.get("build_binary", storage_data.get("Build", storage_data.get("Build_binary", 0.0)))
                or 0.0
            ),
        }
    else:
        storage = None

    return DesignData(heat_pumps=heat_pumps, storage=storage)


def _load_design_override(scenario_cfg: Mapping[str, Any]) -> DesignData | None:
    path = scenario_cfg.get("pf_design_json") or scenario_cfg.get("design_json")
    if not path:
        return None
    design_path = Path(str(path)).expanduser()
    if not design_path.exists():
        logger.warning("PF design file %s not found – continuing without design fixation.", design_path)
        return None
    try:
        with open(design_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.warning("Failed to load PF design file %s: %s", design_path, exc)
        return None
    if not isinstance(raw, Mapping):
        logger.warning("Design file %s does not contain a mapping – ignoring content.", design_path)
        return None
    return _design_from_mapping(raw)


def register_workflow_step(name: str, handler: StepHandler) -> None:
    """Register or replace a workflow step handler.

    Parameters
    ----------
    name:
        Identifier used in ``scenario.workflow`` entries.  The identifier is
        stored in upper-case to provide case-insensitive matching.
    handler:
        Callable that mutates a :class:`WorkflowContext` in place.
    """

    key = str(name).strip().upper()
    if not key:
        raise ValueError("Workflow step name must not be empty")
    _STEP_HANDLERS[key] = handler


def unregister_workflow_step(name: str) -> None:
    """Remove a workflow step handler if it exists."""

    key = str(name).strip().upper()
    if key:
        _STEP_HANDLERS.pop(key, None)


def get_registered_workflow_steps() -> List[str]:
    """Return the currently registered workflow step identifiers."""

    return sorted(_STEP_HANDLERS.keys())


@dataclass
class WorkflowResult:
    """Return value for :func:`run_workflow`."""

    config: Dict[str, Any]
    pf_result: Optional[ScenarioResult]
    rh_result: Optional[RollingHorizonResult]
    mpc_result: Optional[RollingHorizonResult]
    design: Optional[DesignData]
    plan: WorkflowPlan


def _build_workflow_inputs(
    config_paths: List[str], overrides: Optional[Dict[str, Any]] = None
) -> WorkflowInputs:
    """Load configs, inputs and workflow plan in a single place.

    The helper keeps :func:`run_workflow` small and ensures that configuration
    merging, time-step preparation and capacity validation follow the same
    order across CLI and notebook usage.
    """

    cfg = load_and_merge(config_paths)
    if overrides:
        cfg = deep_merge(cfg, overrides)

    run_cfg = cfg.get("run", {})
    scenario_cfg = cfg.get("scenario", {})
    site_cfg = cfg.get("site", {})

    dt_h = float(run_cfg.get("dt_h", 1.0))
    table = load_input_excel(site_cfg.get("input_xlsx", "Import_Data.xlsx"), site_cfg, dt_hours=dt_h)
    table.ensure_frequency(dt_h)
    table = _apply_horizon(table, scenario_cfg, dt_h)
    _assert_capacity_vs_demand(table, cfg)

    plan = _parse_workflow_plan(scenario_cfg)
    solver_name = str(run_cfg.get("solver", "glpk"))
    return WorkflowInputs(cfg, table, dt_h, solver_name, plan)


def run_workflow(config_paths: List[str], overrides: Optional[Dict[str, Any]] = None) -> WorkflowResult:
    """Execute the configured workflow (PF, RH, MPC or combinations).

    Parameters
    ----------
    config_paths:
        List of configuration file paths that should be merged.
    overrides:
        Optional dictionary applied on top of the merged configuration.
    """

    inputs = _build_workflow_inputs(config_paths, overrides)

    context = WorkflowContext(inputs.cfg, inputs.table, inputs.dt_h, inputs.solver_name, inputs.plan)
    scenario_cfg = inputs.cfg.get("scenario", {})
    design_override = _load_design_override(scenario_cfg if isinstance(scenario_cfg, Mapping) else {})
    if design_override is not None:
        context.design = design_override

    for step in inputs.plan.steps:
        handler = _STEP_HANDLERS.get(step)
        if handler is None:
            raise ValueError(f"Unsupported workflow step: {step}")
        handler(context)

    return WorkflowResult(inputs.cfg, context.pf_result, context.rh_result, context.mpc_result, context.design, inputs.plan)


def _parse_workflow_plan(scenario_cfg: Mapping[str, Any]) -> WorkflowPlan:
    run_mode = str(scenario_cfg.get("run_mode", "")).strip().upper() or "PF_ONLY"
    workflow = scenario_cfg.get("workflow")

    if workflow is not None:
        if isinstance(workflow, (str, bytes)):
            steps = [str(workflow)]
        else:
            steps = list(workflow)
        steps_upper = [str(step).strip().upper() for step in steps if str(step).strip()]
    else:
        mapping = {
            "PF_ONLY": ["PF"],
            "RH_ONLY": ["RH"],
            "PF_THEN_RH": ["PF", "RH"],
            "PF_AND_RH": ["PF", "RH"],
            "MPC_ONLY": ["MPC"],
            "PF_THEN_MPC": ["PF", "MPC"],
        }
        steps_upper = mapping.get(run_mode, ["PF"])

    if not steps_upper:
        raise ValueError("Workflow must contain at least one step")

    fix_default = run_mode in {"PF_THEN_RH", "PF_AND_RH"}
    fix_design = bool(scenario_cfg.get("fix_design", scenario_cfg.get("fix_design_in_rh", fix_default)))

    return WorkflowPlan(steps=steps_upper, fix_design=fix_design)


def _pf_step(context: WorkflowContext) -> None:
    result = _solve_scenario(context.table, context.cfg, context.dt_h, context.solver_name)
    context.pf_result = result
    context.design = _extract_design_data(result.summary)


def _rh_step(context: WorkflowContext) -> None:
    params = _load_rolling_params(context.cfg)
    horizon_steps, step_steps, overlap_steps = params.as_steps(context.dt_h)
    fix_design = context.plan.fix_design and context.design is not None
    if context.plan.fix_design and context.design is None:
        logger.warning(
            "Design fixation requested but no PF design data available – proceeding without fixation."
        )
    context.rh_result = _run_rolling_horizon(
        context.cfg,
        context.table,
        context.dt_h,
        context.solver_name,
        params,
        horizon_steps,
        step_steps,
        overlap_steps,
        context.design,
        fix_design,
    )
    if context.rh_result.design is not None:
        context.design = context.design or context.rh_result.design

    # ✅ FIX: Bei PF→RH mit fix_design, übertrage Investment-Kosten aus PF
    # Problem: RH berechnet keine CAPEX bei fix_design=True, aber Dashboard zeigt RH als primary
    # Lösung: Kopiere alle Investment-Kosten aus PF in RH-aggregierte Kosten
    if context.pf_result and context.rh_result and context.plan.fix_design:
        pf_costs = context.pf_result.costs
        rh_costs = context.rh_result.costs

        # Übertrage alle Investment-Kosten aus PF
        investment_transferred = False
        for inv_key in _INVESTMENT_KEYS:
            if inv_key in pf_costs:
                pf_value = pf_costs[inv_key]
                if isinstance(pf_value, (int, float)) and pf_value > 0:
                    rh_costs[inv_key] = float(pf_value)
                    investment_transferred = True

        # Recompute total objective wenn Investment übertragen wurde
        if investment_transferred:
            _recompute_objective_costs(rh_costs)
            logger.info(
                f"Transferred investment costs from PF to RH result "
                f"(CAPEX: {rh_costs.get('objective.Capex_cost_EUR', 0):,.0f} EUR)"
            )


def _mpc_step(context: WorkflowContext) -> None:
    """Model Predictive Control with forecast updates."""

    from energis.forecasting.persistence import PersistenceForecast
    from energis.forecasting.perfect_noise import PerfectNoiseForecast
    from energis.run.mpc import run_mpc

    # Load MPC configuration
    mpc_cfg = context.cfg.get("scenario", {}).get("mpc", {})
    forecast_method = str(mpc_cfg.get("forecast_method", "persistence")).lower()
    forecast_horizon_hours = float(mpc_cfg.get("forecast_horizon_hours", 168.0))
    update_frequency_hours = float(mpc_cfg.get("update_frequency_hours", 24.0))

    # Create forecast generator
    if forecast_method == "persistence":
        forecast_gen = PersistenceForecast(context.cfg)
    elif forecast_method in ("perfect_noise", "perfect_with_noise"):
        forecast_gen = PerfectNoiseForecast(context.cfg)
    else:
        raise ValueError(f"Unknown MPC forecast method: {forecast_method}")

    logger.info(f"MPC using forecast method: {forecast_gen.get_method_name()}")

    # Check design fixation
    fix_design = context.plan.fix_design and context.design is not None
    if context.plan.fix_design and context.design is None:
        logger.warning(
            "Design fixation requested but no PF design data available – proceeding without fixation."
        )

    # Run MPC
    context.mpc_result = run_mpc(
        base_cfg=context.cfg,
        historical_data=context.table,
        dt_h=context.dt_h,
        solver_name=context.solver_name,
        forecast_gen=forecast_gen,
        forecast_horizon_hours=forecast_horizon_hours,
        update_frequency_hours=update_frequency_hours,
        design=context.design,
        fix_design=fix_design,
    )

    # Propagate design if MPC found one
    if context.mpc_result.design is not None:
        context.design = context.design or context.mpc_result.design

    # ✅ FIX: Bei PF→MPC mit fix_design, übertrage Investment-Kosten aus PF
    # Analoges Problem wie bei PF→RH
    if context.pf_result and context.mpc_result and context.plan.fix_design:
        pf_costs = context.pf_result.costs
        mpc_costs = context.mpc_result.costs

        # Übertrage alle Investment-Kosten aus PF
        investment_transferred = False
        for inv_key in _INVESTMENT_KEYS:
            if inv_key in pf_costs:
                pf_value = pf_costs[inv_key]
                if isinstance(pf_value, (int, float)) and pf_value > 0:
                    mpc_costs[inv_key] = float(pf_value)
                    investment_transferred = True

        # Recompute total objective wenn Investment übertragen wurde
        if investment_transferred:
            _recompute_objective_costs(mpc_costs)
            logger.info(
                f"Transferred investment costs from PF to MPC result "
                f"(CAPEX: {mpc_costs.get('objective.Capex_cost_EUR', 0):,.0f} EUR)"
            )


def _run_rolling_horizon(
    base_cfg: Dict[str, Any],
    table: TimeSeriesTable,
    dt_h: float,
    solver_name: str,
    params: _RollingParams,
    horizon_steps: int,
    step_steps: int,
    overlap_steps: int,
    design: Optional[DesignData],
    fix_design: bool,
) -> RollingHorizonResult:
    n = len(table)
    if n == 0:
        empty_series: OrderedDict[str, List[float]] = OrderedDict()
        return RollingHorizonResult(table, empty_series, {}, [], design)

    aggregated_indices: List[int] = []
    aggregated_series: OrderedDict[str, List[float]] = OrderedDict()
    aggregated_costs: Dict[str, float] = {}
    windows: List[WindowResult] = []

    design_state = design
    cost_plan = _load_cost_plan(base_cfg, fix_design)
    once_costs: Set[str] = set()

    soc_next = _initial_soc(base_cfg)
    base_storage_enabled = _storage_enabled(base_cfg)

    start = 0
    window_idx = 0
    while start < n:
        last_start = start
        end = min(start + horizon_steps, n)
        if end <= start:
            raise RuntimeError(
                f"Rolling horizon window length is non-positive – check dt_h and HEAT_HORIZON_HOURS. "
                f"Got: start={start}, horizon_steps={horizon_steps}, end={end}, n={n}, dt_h={dt_h}"
            )
        indices = list(range(start, end))
        window_table = _slice_table(table, indices)
        window_cfg = copy.deepcopy(base_cfg)

        if params.terminal_policy:
            _apply_terminal_policy(window_cfg, params.terminal_policy)
        if soc_next is not None and base_storage_enabled:
            _set_initial_soc(window_cfg, soc_next)

        should_fix_design = bool(
            design_state is not None
            and (
                fix_design
                or (design is None and window_idx > 0)
            )
        )
        if should_fix_design:
            window_cfg = _apply_design_fix(window_cfg, design_state)  # type: ignore[arg-type]

        _apply_cost_overrides(window_cfg, cost_plan, window_idx)

        window_result = _solve_scenario(window_table, window_cfg, dt_h, solver_name)
        commit_len = min(step_steps - overlap_steps, len(window_table)) if step_steps > overlap_steps else 0
        if commit_len <= 0:
            raise RuntimeError(
                f"Rolling horizon produced a zero commit length – ensure STEP_HOURS exceeds OVERLAP_HOURS. "
                f"Got: step_steps={step_steps}, overlap_steps={overlap_steps}, "
                f"window_length={len(window_table)}, commit_len={commit_len}"
            )

        _extend_series(aggregated_series, window_result.series, commit_len)
        aggregated_indices.extend(indices[:commit_len])
        commit_fraction = float(commit_len / len(window_table)) if len(window_table) else 0.0
        _accumulate_costs(
            aggregated_costs,
            window_result.costs,
            cost_plan,
            commit_fraction,
            window_idx,
            once_costs,
        )

        soc_next = _next_soc(window_result.series, commit_len, soc_next)

        windows.append(
            WindowResult(
                table=window_result.table,
                series=window_result.series,
                summary=window_result.summary,
                costs=window_result.costs,
                solver=window_result.solver,
                start_index=start,
                commit_steps=commit_len,
            )
        )

        start += max(step_steps - overlap_steps, 1)
        if start <= last_start:
            raise RuntimeError(
                f"Rolling horizon iteration did not advance – check step_hours/overlap_hours configuration. "
                f"Got: step_steps={step_steps}, overlap_steps={overlap_steps}, "
                f"last_start={last_start}, new_start={start}"
            )
        window_idx += 1

        if design_state is None:
            design_state = _extract_design_data(window_result.summary)

    if aggregated_indices != list(range(n)):
        raise RuntimeError("Rolling horizon aggregation did not cover the full time series")

    _recompute_objective_costs(aggregated_costs)

    aggregated_table = _slice_table(table, aggregated_indices)
    return RollingHorizonResult(aggregated_table, aggregated_series, aggregated_costs, windows, design_state)


def _extend_series(
    global_series: MutableMapping[str, List[float]],
    window_series: Mapping[str, List[float]],
    commit_len: int,
) -> None:
    if commit_len <= 0:
        return
    for col in list(global_series.keys()):
        if col not in window_series:
            global_series[col].extend([0.0] * commit_len)
    for col, values in window_series.items():
        dest = global_series.setdefault(col, [])
        slice_values = list(values[:commit_len])
        if len(slice_values) < commit_len:
            slice_values.extend([0.0] * (commit_len - len(slice_values)))
        dest.extend(slice_values)


def _apply_cost_overrides(cfg: MutableMapping[str, Any], plan: _CostAggregationPlan, window_idx: int) -> None:
    costs_cfg = cfg.setdefault("costs", {})
    include_investment = plan.investment_active(window_idx)
    if isinstance(costs_cfg, dict):
        costs_cfg["include_capex_costs"] = include_investment
        costs_cfg["include_activation_costs"] = include_investment and plan.include_activation
        costs_cfg["include_tie_breaker_costs"] = include_investment and plan.include_tie_breaker
        costs_cfg["include_storage_installation_costs"] = include_investment and plan.include_installation


_INVESTMENT_KEYS = {
    "objective.Capex_cost_EUR",
    "objective.Activation_cost_EUR",
    "objective.Tie_breaker_cost_EUR",
    "objective.Storage_installation_cost_EUR",
}
_SKIP_KEYS = {"objective.OBJ_value_EUR", "objective.Objective_residual_EUR"}


def _accumulate_costs(
    target: Dict[str, float],
    window_costs: Mapping[str, Any],
    plan: _CostAggregationPlan,
    commit_fraction: float,
    window_idx: int,
    once_costs: Set[str],
) -> None:
    """Aggregate per-window costs while avoiding RH double-counting.

    Objective-related figures are scaled by the committed fraction of the
    window so overlap regions do not artificially inflate totals. Investment
    terms (CapEx, activation, tie-breaker, installation) are included once by
    default to mimic a single PF design phase; the behaviour can be
    controlled via :class:`_CostAggregationPlan`.
    """

    if commit_fraction <= 0:
        return

    include_investment = plan.investment_active(window_idx)

    for key, value in window_costs.items():
        if not (isinstance(value, (int, float)) and math.isfinite(value)):
            continue
        if key in _SKIP_KEYS:
            continue
        if key in _INVESTMENT_KEYS:
            if not include_investment:
                continue
            if plan.amortise_once and key in once_costs:
                continue
            once_costs.add(key)
            target[key] = float(target.get(key, 0.0) + float(value))
            continue
        scaled_value = float(value)
        if key.startswith("objective."):
            scaled_value *= commit_fraction
        target[key] = float(target.get(key, 0.0) + scaled_value)


def _recompute_objective_costs(costs: MutableMapping[str, float]) -> None:
    if not costs:
        return

    energy_cost = float(costs.get("objective.Grid_energy_cost_EUR", 0.0))
    energy_revenue = float(costs.get("objective.Grid_sell_revenue_EUR", 0.0))
    fuel_cost = float(costs.get("objective.Fuel_cost_EUR", 0.0))
    dump_cost = float(costs.get("objective.Dump_cost_EUR", 0.0))
    co2_cost = float(costs.get("objective.CO2_cost_EUR", 0.0))
    demand_cost = float(costs.get("objective.Demand_charge_cost_EUR", 0.0))
    capex_cost = float(costs.get("objective.Capex_cost_EUR", 0.0))
    activation_cost = float(costs.get("objective.Activation_cost_EUR", 0.0))
    tie_break_cost = float(costs.get("objective.Tie_breaker_cost_EUR", 0.0))
    install_cost = float(costs.get("objective.Storage_installation_cost_EUR", 0.0))

    net_cost = energy_cost - energy_revenue
    costs["objective.Grid_net_cost_EUR"] = net_cost

    objective_total = (
        net_cost
        + fuel_cost
        + dump_cost
        + co2_cost
        + demand_cost
        + capex_cost
        + activation_cost
        + tie_break_cost
        + install_cost
    )
    costs["objective.OBJ_value_EUR"] = objective_total
    costs["objective.Objective_residual_EUR"] = 0.0


def _next_soc(series: Mapping[str, List[float]], commit_len: int, fallback: Optional[float]) -> Optional[float]:
    soc_series = series.get("TES_SOC_MWh")
    if soc_series is None or commit_len <= 0:
        return fallback
    idx = min(commit_len - 1, len(soc_series) - 1)
    return float(soc_series[idx]) if idx >= 0 else fallback


def _solve_scenario(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float,
    solver_name: str,
) -> ScenarioResult:
    model = build_model(table, cfg, dt_h=dt_h)
    solver_meta: Dict[str, Any] = {
        "solver_requested": solver_name,
        "pyomo_available": HAVE_PYOMO,
        "model_built": model is not None,
    }
    if model is not None and HAVE_PYOMO:
        solver_used = solver_name
        try:
            opt = pyo.SolverFactory(solver_name)
        except Exception:  # pragma: no cover - solver fallback
            solver_used = "glpk"
            opt = pyo.SolverFactory("glpk")

        # Apply solver options if configured (CRITICAL FIX: prevents infinite runtime)
        run_cfg = cfg.get("run", {})
        solver_options = run_cfg.get("solver_options", {})
        if solver_options:
            for key, value in solver_options.items():
                opt.options[key] = value
            logger.debug(f"Applied solver options: {solver_options}")

        solver_result = opt.solve(model, tee=False)
        solver_meta["solver_used"] = solver_used
        solver_meta["status"] = str(getattr(getattr(solver_result, "solver", None), "status", "unknown"))
        solver_meta["termination_condition"] = str(
            getattr(getattr(solver_result, "solver", None), "termination_condition", "unknown")
        )
    else:
        solver_meta["solver_used"] = solver_name
        solver_meta["status"] = "not_run"
        solver_meta["termination_condition"] = None

    series, summary, costs = _collect_timeseries_and_summary(
        table,
        cfg,
        dt_h,
        model if HAVE_PYOMO else None,
    )
    return ScenarioResult(table, series, summary, costs, solver_meta)


def _extract_design_data(summary: Mapping[str, Mapping[str, Any]]) -> DesignData:
    heat_pumps: Dict[str, Dict[str, float]] = {}
    storage: Optional[Dict[str, float]] = None

    for key, metrics in summary.items():
        if key.startswith("heat_pump_"):
            hp_id = key.split("heat_pump_", 1)[1]
            capacity = float(metrics.get("Thermal_capacity_MW", 0.0))
            build = float(metrics.get("Build_binary", metrics.get("Build", 0.0)))
            heat_pumps[hp_id] = {
                "capacity_mw": capacity,
                "build_binary": build,
            }
        elif key.startswith("storage_"):
            storage = {
                "name": key.split("storage_", 1)[1],
                "capacity_mwh": float(metrics.get("Capacity_MWh", 0.0)),
                "power_mw": float(metrics.get("Power_limit_MW", 0.0)),
                "build_binary": float(metrics.get("Build_binary", metrics.get("Build", 0.0))),
            }

    return DesignData(heat_pumps=heat_pumps, storage=storage)


def _load_rolling_params(cfg: Mapping[str, Any]) -> _RollingParams:
    scenario_cfg = cfg.get("scenario", {}) if isinstance(cfg.get("scenario"), dict) else {}
    rolling_cfg = scenario_cfg.get("rolling_horizon") or {}

    def _get(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in mapping:
                return mapping[key]
        return default

    horizon_hours = float(_get(rolling_cfg, "HEAT_HORIZON_HOURS", "heat_horizon_hours", "window_hours", default=168.0))
    step_hours = float(_get(rolling_cfg, "STEP_HOURS", "step_hours", default=horizon_hours))
    overlap_hours = float(_get(rolling_cfg, "OVERLAP_HOURS", "overlap_hours", default=0.0))
    terminal_policy = str(_get(rolling_cfg, "terminal_policy", "TERMINAL_POLICY", default="")).strip().lower()

    return _RollingParams(
        horizon_hours=horizon_hours,
        step_hours=step_hours,
        overlap_hours=overlap_hours,
        terminal_policy=terminal_policy,
    )


def _load_cost_plan(cfg: Mapping[str, Any], fix_design: bool) -> _CostAggregationPlan:
    scenario_cfg = cfg.get("scenario", {}) if isinstance(cfg.get("scenario"), dict) else {}
    costs_cfg = scenario_cfg.get("costs") if isinstance(scenario_cfg.get("costs"), dict) else {}
    global_costs_cfg = cfg.get("costs", {}) if isinstance(cfg.get("costs"), dict) else {}

    include_investment = costs_cfg.get("include_investment_in_rh")
    if include_investment is None:
        include_investment = global_costs_cfg.get("include_investment_in_rh")
    if include_investment is None:
        include_investment = not fix_design

    amortise_once = bool(global_costs_cfg.get("amortise_investment_once_in_rh", True))
    include_tie_breaker = bool(global_costs_cfg.get("include_tie_breaker_in_rh", include_investment))
    include_installation = bool(global_costs_cfg.get("include_installation_in_rh", include_investment))
    include_activation = bool(global_costs_cfg.get("include_activation_in_rh", include_investment))

    return _CostAggregationPlan(
        include_investment=bool(include_investment),
        amortise_once=amortise_once,
        include_tie_breaker=include_tie_breaker,
        include_installation=include_installation,
        include_activation=include_activation,
    )


def _hours_to_steps(hours: float, dt_h: float, name: str) -> int:
    if hours <= 0:
        raise ValueError(f"{name} must be positive")
    ratio = hours / dt_h
    rounded = round(ratio)
    if not math.isclose(ratio, rounded, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError(f"{name} must be a multiple of dt_h")
    return max(1, int(rounded))


def _initial_soc(cfg: Mapping[str, Any]) -> Optional[float]:
    system = cfg.get("system", {}) if isinstance(cfg.get("system"), dict) else {}
    storage = system.get("storage", {}) if isinstance(system.get("storage"), dict) else {}
    if not storage or not storage.get("enabled", False):
        return None
    inputs = cfg.get("inputs", {}) if isinstance(cfg.get("inputs"), dict) else {}
    if "SOC_init" in inputs:
        return float(inputs["SOC_init"])
    if "SOC_init" in storage:
        return float(storage["SOC_init"])
    if "soc0_mwh" in storage:
        return float(storage["soc0_mwh"])
    return 0.0


def _storage_enabled(cfg: Mapping[str, Any]) -> bool:
    system = cfg.get("system", {}) if isinstance(cfg.get("system"), dict) else {}
    storage = system.get("storage", {}) if isinstance(system.get("storage"), dict) else {}
    return bool(storage.get("enabled", False))


def _set_initial_soc(cfg: MutableMapping[str, Any], soc: float) -> None:
    inputs = cfg.setdefault("inputs", {})
    if isinstance(inputs, dict):
        inputs["SOC_init"] = float(soc)
    storage = cfg.setdefault("system", {}).setdefault("storage", {})
    if isinstance(storage, dict):
        storage["soc0_mwh"] = float(soc)


def _apply_terminal_policy(cfg: MutableMapping[str, Any], policy: str) -> None:
    if not policy:
        return
    system = cfg.setdefault("system", {})
    if not isinstance(system, dict):
        return
    storage = system.setdefault("storage", {})
    if not isinstance(storage, dict):
        return
    terminal = storage.setdefault("terminal", {})
    if isinstance(terminal, dict):
        terminal["policy"] = policy


def _apply_design_fix(cfg: Dict[str, Any], design: DesignData) -> Dict[str, Any]:
    cfg_copy = copy.deepcopy(cfg)
    system = cfg_copy.setdefault("system", {})
    heat_pumps = system.get("heat_pumps")
    if isinstance(heat_pumps, list):
        for hp_cfg in heat_pumps:
            if not isinstance(hp_cfg, dict):
                continue
            hp_id = str(hp_cfg.get("id"))
            if hp_id not in design.heat_pumps:
                continue
            design_entry = design.heat_pumps[hp_id]
            capacity = float(design_entry.get("capacity_mw", 0.0))
            build_binary = float(design_entry.get("build_binary", 0.0))
            invest_cfg = hp_cfg.setdefault("investment", {})
            if isinstance(invest_cfg, dict):
                invest_cfg["enabled"] = False
                invest_cfg["capacity_min_mw"] = capacity
                invest_cfg["capacity_max_mw"] = capacity
            hp_cfg["max_th_mw"] = capacity
            hp_cfg["min_th_mw"] = capacity
            if build_binary < 0.5:
                hp_cfg["enabled"] = False

    storage_cfg = system.get("storage") if isinstance(system.get("storage"), dict) else None
    if storage_cfg and design.storage:
        storage_cfg["enabled"] = bool(design.storage.get("build_binary", 0.0) >= 0.5)
        storage_cfg["max_energy_mwh"] = float(design.storage.get("capacity_mwh", 0.0))
        storage_cfg["min_energy_mwh"] = float(design.storage.get("capacity_mwh", 0.0))
        storage_cfg["max_power_mw"] = float(design.storage.get("power_mw", 0.0))
        storage_cfg["min_power_mw"] = float(design.storage.get("power_mw", 0.0))
        invest_cfg = storage_cfg.setdefault("investment", {})
        if isinstance(invest_cfg, dict):
            invest_cfg["enabled"] = False
            invest_cfg["energy_capacity_min_mwh"] = float(design.storage.get("capacity_mwh", 0.0))
            invest_cfg["energy_capacity_max_mwh"] = float(design.storage.get("capacity_mwh", 0.0))
            invest_cfg["power_capacity_min_mw"] = float(design.storage.get("power_mw", 0.0))
            invest_cfg["power_capacity_max_mw"] = float(design.storage.get("power_mw", 0.0))

    return cfg_copy


def _register_default_steps() -> None:
    register_workflow_step("PF", _pf_step)
    register_workflow_step("RH", _rh_step)
    register_workflow_step("MPC", _mpc_step)


_register_default_steps()


def export_workflow_results(
    workflow: "WorkflowResult",
    outdir: Optional[str] = None,
) -> Dict[str, Any]:
    """Export workflow results to files (Excel, CSV, plots, JSON).

    This is the unified export function that replaces orchestrator.run_all() exports.
    It handles PF, RH, and MPC results consistently.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow result from run_workflow()
    outdir : str, optional
        Output directory path. If None, creates timestamped directory in exports/

    Returns
    -------
    dict
        Dictionary with export paths and metadata
    """

    # Create output directory
    if outdir is None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        scenario_cfg = workflow.config.get("scenario", {})
        title = str(scenario_cfg.get("title", "Workflow"))
        run_mode = str(scenario_cfg.get("run_mode", "UNKNOWN"))
        tag = scenario_cfg.get("tag") or f"{run_mode}-{title}"
        slug = _slugify(tag)
        outdir = os.path.join("exports", f"{stamp}_{slug}")

    os.makedirs(outdir, exist_ok=True)

    # Determine which results we have
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None
    has_mpc = workflow.mpc_result is not None

    # Prepare timeseries sections for Excel export
    timeseries_sections = []
    cost_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()

    # Add PF results
    if has_pf and workflow.pf_result:
        pf_input_series: OrderedDict[str, List[float]] = OrderedDict(
            (col, list(workflow.pf_result.table[col])) for col in workflow.pf_result.table.columns
        )
        pf_result_series: OrderedDict[str, List[float]] = OrderedDict(
            (name, list(values)) for name, values in workflow.pf_result.series.items()
        )

        timeseries_sections.append({
            "label": "PF_input",
            "timestamps": list(workflow.pf_result.table.index),
            "series": pf_input_series,
        })
        timeseries_sections.append({
            "label": "PF_result",
            "timestamps": list(workflow.pf_result.table.index),
            "series": pf_result_series,
        })

        if workflow.pf_result.costs:
            cost_sections["PF"] = OrderedDict(
                (str(key), value) for key, value in workflow.pf_result.costs.items()
            )

        # Export PF CSV
        pf_csv = os.path.join(outdir, "pf_timeseries.csv")
        write_timeseries_csv(pf_csv, workflow.pf_result.table, workflow.pf_result.series)

    # Add RH results
    if has_rh and workflow.rh_result:
        rh_result_series: OrderedDict[str, List[float]] = OrderedDict(
            (name, list(values)) for name, values in workflow.rh_result.series.items()
        )

        timeseries_sections.append({
            "label": "RH_result",
            "timestamps": list(workflow.rh_result.table.index),
            "series": rh_result_series,
        })

        if workflow.rh_result.costs:
            cost_sections["RH"] = OrderedDict(
                (str(key), value) for key, value in workflow.rh_result.costs.items()
            )

        # Export RH CSV
        rh_csv = os.path.join(outdir, "rh_timeseries.csv")
        write_timeseries_csv(rh_csv, workflow.rh_result.table, workflow.rh_result.series)

    # Add MPC results
    if has_mpc and workflow.mpc_result:
        mpc_result_series: OrderedDict[str, List[float]] = OrderedDict(
            (name, list(values)) for name, values in workflow.mpc_result.series.items()
        )

        timeseries_sections.append({
            "label": "MPC_result",
            "timestamps": list(workflow.mpc_result.table.index),
            "series": mpc_result_series,
        })

        if workflow.mpc_result.costs:
            cost_sections["MPC"] = OrderedDict(
                (str(key), value) for key, value in workflow.mpc_result.costs.items()
            )

        # Export MPC CSV
        mpc_csv = os.path.join(outdir, "mpc_timeseries.csv")
        write_timeseries_csv(mpc_csv, workflow.mpc_result.table, workflow.mpc_result.series)

    # Prepare design export
    design_export: Dict[str, Any] = {}
    if workflow.design:
        design_export["heat_pumps"] = workflow.design.heat_pumps
        if workflow.design.storage:
            design_export["storage"] = workflow.design.storage

        # Export design JSON
        design_json_path = os.path.join(outdir, "design.json")
        with open(design_json_path, "w") as f:
            json.dump(design_export, f, indent=2, default=str)

    # Prepare metadata sections
    scenario_cfg = workflow.config.get("scenario", {})
    site_cfg = workflow.config.get("site", {})
    run_cfg = workflow.config.get("run", {})

    stamp = time.strftime("%Y%m%d_%H%M%S")
    dt_h = float(run_cfg.get("dt_h", 1.0))

    metadata_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    metadata_sections["run"] = OrderedDict([
        ("timestamp", stamp),
        ("output_directory", outdir),
        ("dt_h", dt_h),
        ("workflow_steps", list(workflow.plan.steps)),
        ("pyomo_available", HAVE_PYOMO),
    ])

    if isinstance(scenario_cfg, dict):
        metadata_sections["scenario"] = OrderedDict((key, value) for key, value in scenario_cfg.items())

    if isinstance(site_cfg, dict):
        metadata_sections["site"] = OrderedDict((key, value) for key, value in site_cfg.items())

    # Prepare manifest
    title = str(scenario_cfg.get("title", "Workflow"))
    run_mode = str(scenario_cfg.get("run_mode", "UNKNOWN"))
    tag = scenario_cfg.get("tag") or f"{run_mode}-{title}"

    flags = OrderedDict([
        ("has_pf", has_pf),
        ("has_rh", has_rh),
        ("has_mpc", has_mpc),
        ("has_design", bool(design_export)),
    ])

    manifest_data = OrderedDict([
        ("scenario_title", title),
        ("run_mode", run_mode),
        ("workflow_steps", list(workflow.plan.steps)),
        ("flags", flags),
        ("export_timestamp", stamp),
        ("slug", _slugify(tag)),
        ("output_directory", outdir),
    ])

    # Export scenario bundle (Excel)
    bundle_paths = dict(
        export_scenario_bundle(
            outdir,
            meta_sections=metadata_sections,
            timeseries_sections=timeseries_sections,
            cost_sections=cost_sections,
            design=design_export,
            manifest=manifest_data,
        )
    )

    # Export plots
    plot_files = []
    try:
        # Export PF plots if available
        if has_pf and workflow.pf_result:
            pf_summary = workflow.pf_result.summary if hasattr(workflow.pf_result, 'summary') else {}
            pf_plots = export_plots(
                outdir,
                workflow.pf_result.table,
                workflow.pf_result.series,
                pf_summary,
            )
            plot_files.extend(pf_plots)
    except Exception as exc:
        print(f"[EXPORT] Plot export skipped: {exc}")

    # Prepare return dictionary
    result_dict = {
        "outdir": outdir,
        "scenario_xlsx": bundle_paths.get("scenario_xlsx"),
        "costs_json": bundle_paths.get("costs_json"),
        "design_json": bundle_paths.get("design_json"),
        "meta_json": bundle_paths.get("meta_json"),
        "manifest_json": bundle_paths.get("manifest_json"),
        "plots": plot_files,
        "costs": {},
    }

    # Add costs from the final result
    if has_mpc and workflow.mpc_result and workflow.mpc_result.costs:
        result_dict["costs"] = workflow.mpc_result.costs
    elif has_rh and workflow.rh_result and workflow.rh_result.costs:
        result_dict["costs"] = workflow.rh_result.costs
    elif has_pf and workflow.pf_result and workflow.pf_result.costs:
        result_dict["costs"] = workflow.pf_result.costs

    return result_dict


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Simple command line interface for :mod:`energis.run.rolling_horizon`."""

    parser = argparse.ArgumentParser(description="Run PF/RH workflows using merged EnerGIS configs")
    parser.add_argument(
        "configs",
        metavar="CONFIG",
        nargs="+",
        help="Configuration files passed to load_and_merge in the given order",
    )
    parser.add_argument(
        "--run-mode",
        type=_parse_run_mode,
        choices=["PF_ONLY", "RH_ONLY", "PF_THEN_RH"],
        help="Override scenario.run_mode (env: RUN_MODE)",
    )
    parser.add_argument(
        "--heat-horizon-hours",
        type=float,
        help="Override rolling horizon window size in hours (env: HEAT_HORIZON_HOURS)",
    )
    parser.add_argument(
        "--rh-window-hours",
        type=float,
        help="Alias for --heat-horizon-hours (env: HEAT_HORIZON_HOURS)",
    )
    parser.add_argument(
        "--step-hours",
        type=float,
        help="Override rolling horizon commit length in hours (env: STEP_HOURS)",
    )
    parser.add_argument(
        "--rh-overlap-hours",
        type=float,
        help="Overlap between consecutive RH windows in hours (env: OVERLAP_HOURS)",
    )
    parser.add_argument(
        "--sensitivity-horizon-hours",
        type=_parse_float_list,
        help="Comma/semicolon separated list of window sizes for a sensitivity sweep",
    )
    parser.add_argument(
        "--sensitivity-step-hours",
        type=_parse_float_list,
        help="Comma/semicolon separated list of commit lengths for a sensitivity sweep",
    )
    parser.add_argument(
        "--sensitivity-overlap-hours",
        type=_parse_float_list,
        help="Comma/semicolon separated list of RH overlaps for a sensitivity sweep",
    )
    parser.add_argument(
        "--terminal-policy",
        help="Override storage terminal policy for RH windows (env: TERMINAL_POLICY)",
    )
    parser.add_argument(
        "--pf-design-json",
        help="Path to a PF design JSON exported by a previous run (env: PF_DESIGN_JSON)",
    )
    parser.add_argument(
        "--fix-design",
        dest="fix_design",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable design fixation during RH (env: FIX_DESIGN)",
    )
    parser.add_argument(
        "--include-gridcost-in-energy",
        dest="include_gridcost_in_energy",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include grid cost in PF objective (env: INCLUDE_GRIDCOST_IN_ENERGY)",
    )
    parser.add_argument(
        "--include-demand-charge-in-rh",
        dest="include_demand_charge_in_rh",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include demand charge during RH runs (env: INCLUDE_DEMAND_CHARGE_IN_RH)",
    )
    parser.add_argument(
        "--include-co2-cost-in-objective",
        dest="include_co2_cost_in_objective",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include CO2 pricing in the optimisation objective (env: INCLUDE_CO2_COST_IN_OBJECTIVE)",
    )
    parser.add_argument(
        "--print-design",
        action="store_true",
        help="Print extracted design values when available",
    )
    args = parser.parse_args(argv)

    try:
        env_values = _gather_env_overrides()
    except ValueError as exc:
        parser.error(str(exc))

    values, horizon_value, step_value, overlap_value = _merge_cli_and_env(args, env_values)
    base_overrides = _build_override_dict(values)
    runs = _expand_sensitivity_runs(args, base_overrides, horizon_value, step_value, overlap_value)

    for idx, (horizon, step, overlap, override_cfg) in enumerate(runs, start=1):
        if len(runs) > 1:
            print(f"[workflow] Sweep run {idx}/{len(runs)}: horizon={horizon}, step={step}, overlap={overlap}")
        result = run_workflow(args.configs, overrides=override_cfg or None)
        steps = " -> ".join(result.plan.steps)
        print(f"[workflow] Executed steps: {steps}")

        if result.pf_result is not None:
            pf_obj = result.pf_result.costs.get("objective.OBJ_value_EUR") if result.pf_result.costs else None
            print(f"  • PF time steps: {len(result.pf_result.table)}")
            if pf_obj is not None:
                print(f"  • PF objective: {pf_obj}")

        if result.rh_result is not None:
            print(f"  • RH windows: {len(result.rh_result.windows)}")
            print(f"  • RH committed steps: {len(result.rh_result.table)}")

        if args.print_design and result.design is not None:
            hp_parts = ", ".join(sorted(result.design.heat_pumps.keys())) or "none"
            print(f"  • Design heat pumps: {hp_parts}")
            if result.design.storage is not None:
                print(f"  • Storage design: {result.design.storage}")

    return 0


__all__ = [
    "ScenarioResult",
    "WindowResult",
    "RollingHorizonResult",
    "DesignData",
    "WorkflowInputs",
    "WorkflowResult",
    "run_workflow",
    "export_workflow_results",
    "WorkflowContext",
    "WorkflowPlan",
    "register_workflow_step",
    "unregister_workflow_step",
    "get_registered_workflow_steps",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    raise SystemExit(main())


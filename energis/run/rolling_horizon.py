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

from energis.logging_config import get_logger

logger = get_logger(__name__)

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
from energis.design import (
    DesignSpec,
    DesignConfig,
    load_design_config,
    load_design_for_scenario,
    extract_design_from_summary,
    apply_design_to_config,
    save_design_to_file,
    validate_design,
)
import time

from .rh_utilities import (
    _slice_table,
    _parse_ts,
    _apply_horizon,
    _hours_to_steps,
    _slugify,
    _extract_pyomo_series,
    _env_str,
    _env_float,
    _env_bool,
    _parse_float_list,
    _gather_env_overrides,
    _assert_capacity_vs_demand,
)
from .rh_utilities.env_overrides import (
    _OverrideValues,
    _normalise_run_mode,
    _parse_run_mode,
)


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
    """Design figures extracted from a PF optimisation.

    DEPRECATED: Use DesignSpec from energis.design instead.
    Kept for backward compatibility.
    """

    heat_pumps: Dict[str, Dict[str, float]]
    storage: Optional[Dict[str, float]]


@dataclass
class WorkflowPlan:
    """Parsed representation of the requested workflow sequence."""

    steps: Sequence[str]
    fix_design: bool  # Legacy flag (deprecated, use design_config instead)
    design_config: Optional[DesignConfig] = None  # New design configuration


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
    design: Optional[DesignData] = None  # Legacy (deprecated)
    design_spec: Optional[DesignSpec] = None  # New design specification


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
        series[f"{comp}_COP_input"] = [0.0] * n  # Input COP from optimization parameter
        series[f"{comp}_WRG_ratio"] = [0.0] * n  # Q_wrg / Q_total ratio

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
            # Extract input COP from Pyomo parameter
            cop_param = getattr(model, f"{comp}_COP", None)
            if cop_param is not None:
                for t in times:
                    idx = t - 1  # Pyomo indices start at 1
                    if 0 <= idx < n:
                        try:
                            series[f"{comp}_COP_input"][idx] = float(pyo.value(cop_param[t]))
                        except Exception:
                            pass

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

        if hasattr(model, "obj"):
            model_obj_value = float(pyo.value(model.obj))
        else:
            model_obj_value = 0.0

        objective["Model_OBJ_value_EUR"] = model_obj_value
        objective["OBJ_value_EUR"] = model_obj_value  # initial = Model-Objektiv, wird später überschrieben
        objective["P_buy_peak_MW"] = float(pyo.value(model.P_buy_peak)) if hasattr(model, "P_buy_peak") else 0.0

        # ✅ Extrahiere CO2-Kosten pro Komponente aus Pyomo-Modell
        # Initialisiere Fuel-Type-Aggregation
        co2_by_fuel_type = {
            'gas': {'heat_kg': 0, 'elec_kg': 0, 'total_kg': 0, 'heat_eur': 0, 'elec_eur': 0, 'total_eur': 0},
            'biomass': {'heat_kg': 0, 'elec_kg': 0, 'total_kg': 0, 'heat_eur': 0, 'elec_eur': 0, 'total_eur': 0},
            'waste': {'heat_kg': 0, 'elec_kg': 0, 'total_kg': 0, 'heat_eur': 0, 'elec_eur': 0, 'total_eur': 0}
        }

        if hasattr(model, 'co2_component_costs'):
            for comp_name, co2_data in model.co2_component_costs.items():
                # CO2 in kg (Brutto-Werte)
                objective[f"CO2_{comp_name}_heat_kg"] = float(pyo.value(co2_data['heat_kg']))
                objective[f"CO2_{comp_name}_elec_kg_gross"] = float(pyo.value(co2_data['elec_kg']))
                objective[f"CO2_{comp_name}_total_kg_gross"] = float(pyo.value(co2_data['total_kg']))

                # CO2-Kosten in EUR (Brutto)
                objective[f"CO2_{comp_name}_heat_cost_EUR"] = float(pyo.value(co2_data['heat_eur']))
                objective[f"CO2_{comp_name}_elec_cost_EUR_gross"] = float(pyo.value(co2_data['elec_eur']))
                objective[f"CO2_{comp_name}_total_cost_EUR_gross"] = float(pyo.value(co2_data['total_eur']))

                # Speichere Typ für spätere selfuse-Korrektur
                objective[f"CO2_{comp_name}_type"] = co2_data.get('type', 'unknown')

                # Aggregiere nach Brennstofftyp (nur für Komponenten mit fuel_bus)
                if 'fuel_bus' in co2_data:
                    fuel_type = co2_data['fuel_bus']
                    if fuel_type in co2_by_fuel_type:
                        co2_by_fuel_type[fuel_type]['heat_kg'] += float(pyo.value(co2_data['heat_kg']))
                        co2_by_fuel_type[fuel_type]['elec_kg'] += float(pyo.value(co2_data['elec_kg']))
                        co2_by_fuel_type[fuel_type]['total_kg'] += float(pyo.value(co2_data['total_kg']))
                        co2_by_fuel_type[fuel_type]['heat_eur'] += float(pyo.value(co2_data['heat_eur']))
                        co2_by_fuel_type[fuel_type]['elec_eur'] += float(pyo.value(co2_data['elec_eur']))
                        co2_by_fuel_type[fuel_type]['total_eur'] += float(pyo.value(co2_data['total_eur']))

        # Export CO2 nach Brennstofftyp
        for fuel_type, fuel_co2_data in co2_by_fuel_type.items():
            objective[f"CO2_fuel_{fuel_type}_heat_kg"] = fuel_co2_data['heat_kg']
            objective[f"CO2_fuel_{fuel_type}_elec_kg"] = fuel_co2_data['elec_kg']
            objective[f"CO2_fuel_{fuel_type}_total_kg"] = fuel_co2_data['total_kg']
            objective[f"CO2_fuel_{fuel_type}_heat_cost_EUR"] = fuel_co2_data['heat_eur']
            objective[f"CO2_fuel_{fuel_type}_elec_cost_EUR"] = fuel_co2_data['elec_eur']
            objective[f"CO2_fuel_{fuel_type}_total_cost_EUR"] = fuel_co2_data['total_eur']

        # Gesamt-Summen (Wärme/Strom) - Kosten und kg
        if hasattr(model, 'co2_cost_heat_expr'):
            objective["CO2_heat_total_cost_EUR"] = float(pyo.value(model.co2_cost_heat_expr))

        if hasattr(model, 'co2_cost_elec_expr'):
            objective["CO2_elec_total_cost_EUR"] = float(pyo.value(model.co2_cost_elec_expr))

        if hasattr(model, 'co2_cost_total_expr'):
            objective["CO2_total_cost_EUR"] = float(pyo.value(model.co2_cost_total_expr))

        if hasattr(model, 'co2_kg_heat_expr'):
            objective["CO2_heat_total_kg"] = float(pyo.value(model.co2_kg_heat_expr))

        if hasattr(model, 'co2_kg_elec_expr'):
            co2_elec_total_kg_gross = float(pyo.value(model.co2_kg_elec_expr))
            objective["CO2_elec_total_kg_gross"] = co2_elec_total_kg_gross
            # Wird später korrigiert nach selfuse_fraction

        # ✅ Dashboard-Kategorien (3 separate Emissionsquellen)
        if hasattr(model, 'co2_kg_fuel_to_heat_expr'):
            objective["CO2_fuel_to_heat_kg"] = float(pyo.value(model.co2_kg_fuel_to_heat_expr))

        # ✅ Berechne selfuse_fraction (für CHP-Korrektur)
        selfuse_fraction = 1.0  # Default: alles Eigenverbrauch
        chp_elec_total_mwh = 0
        p_sell_total_mwh = sum(series["P_sell_MW"]) * dt_h if "P_sell_MW" in series else 0

        # Summiere alle CHP-Generatoren
        if hasattr(model, 'co2_component_costs'):
            for comp_name, co2_data in model.co2_component_costs.items():
                if co2_data.get('type') == 'chp' and co2_data.get('el_eff', 0) > 0:
                    # Finde P_el_out für diese Komponente
                    pel_col = f"{comp_name}_Pel_MW"
                    if pel_col in series:
                        chp_elec_total_mwh += sum(series[pel_col]) * dt_h

        # Berechne Eigenverbrauch-Anteil
        if chp_elec_total_mwh > 0:
            selfuse_fraction = max(0, (chp_elec_total_mwh - p_sell_total_mwh) / chp_elec_total_mwh)

        # ✅ Exportiere komponenten-spezifische Netto-Werte (IMMER, nicht nur wenn CHP vorhanden)
        if hasattr(model, 'co2_component_costs'):
            for comp_name, co2_data in model.co2_component_costs.items():
                if co2_data.get('type') == 'chp':
                    # CHP: Brutto-Werte wurden bereits exportiert, wende selfuse-Korrektur an
                    co2_elec_gross = objective.get(f"CO2_{comp_name}_elec_kg_gross", 0)
                    co2_total_gross = objective.get(f"CO2_{comp_name}_total_kg_gross", 0)
                    co2_heat = objective.get(f"CO2_{comp_name}_heat_kg", 0)

                    # Netto-Werte (nur Eigenverbrauch)
                    co2_elec_net = co2_elec_gross * selfuse_fraction
                    co2_total_net = co2_heat + co2_elec_net

                    # Exportiere Netto-Werte
                    objective[f"CO2_{comp_name}_elec_kg"] = co2_elec_net
                    objective[f"CO2_{comp_name}_total_kg"] = co2_total_net

                    # Kosten auch korrigieren
                    co2_elec_cost_gross = objective.get(f"CO2_{comp_name}_elec_cost_EUR_gross", 0)
                    co2_total_cost_gross = objective.get(f"CO2_{comp_name}_total_cost_EUR_gross", 0)
                    co2_heat_cost = objective.get(f"CO2_{comp_name}_heat_cost_EUR", 0)

                    co2_elec_cost_net = co2_elec_cost_gross * selfuse_fraction
                    co2_total_cost_net = co2_heat_cost + co2_elec_cost_net

                    objective[f"CO2_{comp_name}_elec_cost_EUR"] = co2_elec_cost_net
                    objective[f"CO2_{comp_name}_total_cost_EUR"] = co2_total_cost_net
                else:
                    # Nicht-CHP: Brutto = Netto (keine Korrektur nötig)
                    if f"CO2_{comp_name}_elec_kg_gross" in objective:
                        objective[f"CO2_{comp_name}_elec_kg"] = objective[f"CO2_{comp_name}_elec_kg_gross"]
                    if f"CO2_{comp_name}_total_kg_gross" in objective:
                        objective[f"CO2_{comp_name}_total_kg"] = objective[f"CO2_{comp_name}_total_kg_gross"]
                    if f"CO2_{comp_name}_elec_cost_EUR_gross" in objective:
                        objective[f"CO2_{comp_name}_elec_cost_EUR"] = objective[f"CO2_{comp_name}_elec_cost_EUR_gross"]
                    if f"CO2_{comp_name}_total_cost_EUR_gross" in objective:
                        objective[f"CO2_{comp_name}_total_cost_EUR"] = objective[f"CO2_{comp_name}_total_cost_EUR_gross"]

        # ✅ Gesamt-CO2 Korrektur (nur wenn CHP vorhanden)
        if hasattr(model, 'co2_kg_fuel_to_elec_expr'):
            co2_fuel_to_elec_total = float(pyo.value(model.co2_kg_fuel_to_elec_expr))
            objective["CO2_fuel_to_elec_kg_gross"] = co2_fuel_to_elec_total  # Brutto (vor Einspeisung)

            # Korrigiere CO2 für Eigenverbrauch
            co2_fuel_to_elec_net = co2_fuel_to_elec_total * selfuse_fraction
            objective["CO2_fuel_to_elec_kg"] = co2_fuel_to_elec_net  # Netto (nach Einspeisung)
            objective["CO2_fuel_to_elec_selfuse_fraction"] = selfuse_fraction

            # ✅ Korrigiere auch Gesamt-Strom-CO2 (elec_total_kg)
            if "CO2_elec_total_kg_gross" in objective:
                co2_elec_net = objective["CO2_elec_total_kg_gross"] - co2_fuel_to_elec_total + co2_fuel_to_elec_net
                objective["CO2_elec_total_kg"] = co2_elec_net

            # ✅ Korrigiere CO2-Kosten für Stromerzeugung
            if hasattr(model, 'co2_cost_elec_expr'):
                co2_elec_cost_gross = float(pyo.value(model.co2_cost_elec_expr))
                co2_elec_cost_net = co2_elec_cost_gross * selfuse_fraction
                objective["CO2_elec_total_cost_EUR"] = co2_elec_cost_net

            # ✅ Korrigiere Gesamt-CO2-Kosten
            if hasattr(model, 'co2_cost_total_expr') and hasattr(model, 'co2_cost_elec_expr'):
                co2_total_cost_gross = float(pyo.value(model.co2_cost_total_expr))
                co2_heat_cost = float(pyo.value(model.co2_cost_heat_expr)) if hasattr(model, 'co2_cost_heat_expr') else 0
                co2_total_cost_net = co2_heat_cost + co2_elec_cost_net
                objective["CO2_total_cost_EUR"] = co2_total_cost_net

        if hasattr(model, 'co2_kg_grid_to_elec_expr'):
            objective["CO2_grid_to_elec_kg"] = float(pyo.value(model.co2_kg_grid_to_elec_expr))

    else:
        times = list(range(1, n + 1))
        objective["OBJ_value_EUR"] = 0.0
        objective["P_buy_peak_MW"] = max(series["P_buy_MW"], default=0.0)

    price_series = table.data.get("strompreis_EUR_MWh", [0.0] * n)
    grid_co2_series = table.data.get("grid_co2_kg_MWh", [0.0] * n)
    demand_series = table.data.get("waermebedarf_MWth", [0.0] * n)

    # ✅ FIX: Export grid_co2_kg_MWh to series for dashboard timeseries plots
    series["grid_co2_kg_MWh"] = list(grid_co2_series)

    # Note: Grid_CO2_emissions_t_per_step will be calculated after pbuy_series is defined (line ~620)
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

    # ✅ FIX: Calculate Grid CO2 emissions timeseries (in tonnes per timestep)
    # Now that pbuy_series is defined, we can calculate the Grid CO2 timeseries
    series["Grid_CO2_emissions_t_per_step"] = [
        pbuy_series[i] * grid_co2_series[i] * dt_h / 1000.0 for i in range(n)
    ] if n else []

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
        # ✅ FIX: Build lookup dict to get correct config for each HP by ID
        hp_configs_by_id = {hp_cfg.get("id", f"HP{i}"): hp_cfg
                            for i, hp_cfg in enumerate(cfg.get("system", {}).get("heat_pumps", []))}
        for hp in meta["heat_pumps"]:
            comp = hp["id"]
            if hp.get("invest_enabled", False):
                cap_var = getattr(model, f"{comp}_cap_mw", None)
                if cap_var is not None:
                    try:
                        cap_value = float(pyo.value(cap_var))
                        # ✅ FIX: Get investment config for THIS specific HP, not just [0]
                        hp_cfg = hp_configs_by_id.get(comp, {})
                        inv_cfg = hp_cfg.get("investment", {})
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
        q_wrg_series = series[f"{comp}_Q_wrg_MW"]
        q_def_series = series[f"{comp}_Q_def_MW"]
        cop_input_series = series[f"{comp}_COP_input"]

        # Calculate COP from results and WRG ratio
        cop_series = []
        wrg_ratio_series = []
        for heat, pel, q_wrg in zip(heat_series, pel_series, q_wrg_series):
            if pel > 1e-9:
                cop_series.append(float(heat / pel))
            else:
                # NaN for inactive timesteps - physically COP is undefined when HP is off
                cop_series.append(float('nan'))
            # WRG ratio: how much of heat comes from waste recovery vs fallback
            if heat > 1e-9:
                wrg_ratio_series.append(float(q_wrg / heat))
            else:
                wrg_ratio_series.append(float('nan'))

        series[f"{comp}_COP"] = cop_series
        series[f"{comp}_WRG_ratio"] = wrg_ratio_series

        heat_mwh = float(sum(heat_series) * dt_h)
        pel_mwh = float(sum(pel_series) * dt_h)
        on_hours = float(sum(on_series) * dt_h)
        q_wrg_mwh = float(sum(q_wrg_series) * dt_h)
        q_def_mwh = float(sum(q_def_series) * dt_h)

        # Calculate average input COP (weighted by heat output)
        avg_cop_input = 0.0
        total_weight = 0.0
        for cop_in, heat in zip(cop_input_series, heat_series):
            if cop_in > 0 and heat > 1e-9:
                avg_cop_input += cop_in * heat
                total_weight += heat
        avg_cop_input = float(avg_cop_input / total_weight) if total_weight > 1e-9 else 0.0

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
        avg_wrg_ratio = float((q_wrg_mwh / heat_mwh) if heat_mwh > 1e-9 else 0.0)

        hp_section = OrderedDict(
            [
                ("Heat_output_MWh", heat_mwh),
                ("Electricity_input_MWh", pel_mwh),
                ("Q_wrg_MWh", q_wrg_mwh),
                ("Q_def_MWh", q_def_mwh),
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
                ("Average_COP_input", avg_cop_input),
                ("Average_WRG_ratio", avg_wrg_ratio),
            ]
        )

        # ✅ Füge CO2-Daten hinzu (aus objective)
        if f"CO2_{comp}_elec_kg" in objective:
            hp_section["CO2_elec_kg"] = objective[f"CO2_{comp}_elec_kg"]
            hp_section["CO2_elec_cost_EUR"] = objective[f"CO2_{comp}_elec_cost_EUR"]
            hp_section["CO2_total_kg"] = objective[f"CO2_{comp}_total_kg"]
            hp_section["CO2_total_cost_EUR"] = objective[f"CO2_{comp}_total_cost_EUR"]

        heat_pump_sections[f"heat_pump_{comp}"] = hp_section

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

        # ✅ Füge CO2-Daten hinzu (aus objective)
        if f"CO2_{comp}_heat_kg" in objective:
            entry["CO2_heat_kg"] = objective[f"CO2_{comp}_heat_kg"]
            entry["CO2_elec_kg"] = objective[f"CO2_{comp}_elec_kg"]
            entry["CO2_total_kg"] = objective[f"CO2_{comp}_total_kg"]
            entry["CO2_heat_cost_EUR"] = objective[f"CO2_{comp}_heat_cost_EUR"]
            entry["CO2_elec_cost_EUR"] = objective[f"CO2_{comp}_elec_cost_EUR"]
            entry["CO2_total_cost_EUR"] = objective[f"CO2_{comp}_total_cost_EUR"]

        generator_sections[f"generator_{comp}"] = entry
        fuel_cost_total += cost_eur
        fuel_emissions_t += emission_t

        # ✅ FIX: Add fuel CO2 emissions per timestep (in tonnes)
        fuel_emission_factor_kg_per_mwh = gen["fuel_emission"]

        # Export CO2 timeseries per generator for dashboard visualization
        co2_series_per_gen = []
        for i in range(n):
            fuel_co2_t = fuel_series[i] * dt_h * fuel_emission_factor_kg_per_mwh / 1000.0
            co2_series_per_gen.append(fuel_co2_t)
            series["Fuel_CO2_emissions_t_per_step"][i] += fuel_co2_t

        # Store CO2 timeseries for this specific generator
        series[f"CO2_{comp}_t_per_step"] = co2_series_per_gen

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

        # ✅ Füge CO2-Daten hinzu (aus objective)
        if "CO2_P2H_elec_kg" in objective:
            p2h_section["CO2_elec_kg"] = objective["CO2_P2H_elec_kg"]
            p2h_section["CO2_elec_cost_EUR"] = objective["CO2_P2H_elec_cost_EUR"]
            p2h_section["CO2_total_kg"] = objective["CO2_P2H_total_kg"]
            p2h_section["CO2_total_cost_EUR"] = objective["CO2_P2H_total_cost_EUR"]

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

    # Load design based on new design configuration
    design_config = inputs.plan.design_config
    if design_config:
        # Determine base path for resolving relative design file paths
        base_path = None
        if config_paths:
            base_path = Path(config_paths[0]).parent

        try:
            context.design_spec = load_design_for_scenario(design_config, base_path)
            if context.design_spec:
                logger.info("[DESIGN] Loaded design: %s", design_config.mode)
        except Exception as e:
            logger.error("[DESIGN] Failed to load design: %s", e)
            raise

    # Legacy support: load design override from pf_design_json
    scenario_cfg = inputs.cfg.get("scenario", {})
    if context.design_spec is None:
        design_override = _load_design_override(scenario_cfg if isinstance(scenario_cfg, Mapping) else {})
        if design_override is not None:
            context.design = design_override
            logger.info("[DESIGN] Loaded legacy design override from pf_design_json")

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

    # Load new design configuration
    design_config = load_design_config(scenario_cfg)

    # Legacy support: fix_design flag (deprecated, use design.mode instead)
    # fix_design should be True for any multi-step workflow (PF→RH or PF→MPC)
    fix_default = run_mode in {"PF_THEN_RH", "PF_AND_RH", "PF_THEN_MPC"} or len(steps_upper) > 1
    fix_design = bool(scenario_cfg.get("fix_design", scenario_cfg.get("fix_design_in_rh", fix_default)))

    # If legacy fix_design is set but no design config, convert to optimize mode
    if fix_design and design_config.mode == "none":
        design_config = DesignConfig(mode="optimize", apply_from_window=1)
        logger.info("[DESIGN] Legacy fix_design=true converted to design.mode=optimize")

    return WorkflowPlan(steps=steps_upper, fix_design=fix_design, design_config=design_config)


def _pf_step(context: WorkflowContext) -> None:
    result = _solve_scenario(context.table, context.cfg, context.dt_h, context.solver_name)

    # Check for infeasible PF solution
    term_cond = (result.solver.get("termination_condition") or "").lower()
    if "infeasible" in term_cond or "unbounded" in term_cond:
        logger.error(
            "Perfect Foresight model is %s. Cannot proceed. "
            "Check: heat demand vs capacity, storage limits, generator constraints.",
            term_cond
        )
        raise RuntimeError(
            f"Perfect Foresight optimization failed: {term_cond}. "
            f"Hint: Verify generator capacities, storage configuration, and input data."
        )
    if result.costs:
        _recompute_objective_costs(result.costs)

    context.pf_result = result
    context.design = _extract_design_data(result.summary)


def _rh_step(context: WorkflowContext) -> None:
    params = _load_rolling_params(context.cfg)
    horizon_steps, step_steps, overlap_steps = params.as_steps(context.dt_h)

    # Get design configuration
    design_config = context.plan.design_config

    # Determine if we have a pre-loaded design (from file or inline)
    if context.design_spec is not None:
        logger.info("[DESIGN] Using pre-loaded design (mode: %s)", design_config.mode if design_config else "unknown")

    # Legacy support
    fix_design = context.plan.fix_design and context.design is not None
    if context.plan.fix_design and context.design is None and context.design_spec is None:
        logger.warning(
            "Design fixation requested but no design data available – proceeding without fixation."
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
        design_spec=context.design_spec,
        design_config=design_config,
    )

    # Update design from result if extracted
    if context.rh_result.design is not None:
        context.design = context.design or context.rh_result.design

    # Save design if configured
    if design_config and design_config.save_to and context.rh_result.design is not None:
        # Convert legacy DesignData to DesignSpec for saving
        extracted_spec = extract_design_from_summary(context.rh_result.costs)  # or from first window summary
        save_design_to_file(extracted_spec, design_config.save_to)
        logger.info("[DESIGN] Saved optimized design to %s", design_config.save_to)

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
    *,
    design_spec: Optional[DesignSpec] = None,
    design_config: Optional[DesignConfig] = None,
) -> RollingHorizonResult:
    n = len(table)
    if n == 0:
        empty_series: OrderedDict[str, List[float]] = OrderedDict()
        return RollingHorizonResult(table, empty_series, {}, [], design)

    aggregated_indices: List[int] = []
    aggregated_series: OrderedDict[str, List[float]] = OrderedDict()
    aggregated_costs: Dict[str, float] = {}
    windows: List[WindowResult] = []

    # Determine design handling mode
    design_mode = design_config.mode if design_config else "none"
    apply_from_window = design_config.apply_from_window if design_config else 1

    # If we have a pre-loaded design_spec, use it
    # Otherwise, we may extract design from window 0 (optimize mode)
    active_design_spec = design_spec

    design_state = design
    cost_plan = _load_cost_plan(base_cfg, fix_design or design_mode in ("file", "inline", "optimize"))
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

        # Determine SOC override for this window
        soc_override = soc_next if (soc_next is not None and base_storage_enabled) else None

        # Determine terminal target based on policy:
        # - "equal": enforce cyclic (terminal = initial SOC)
        # - "geq": terminal >= initial SOC
        # - "value": no hard constraint (economically optimized via terminal value function)
        # - "soft": soft constraint with penalty (always feasible)
        # - "free": no terminal constraint
        policy = (params.terminal_policy or "free").lower()  # ✅ FIX: Default to "free" instead of "equal"
        
        if policy in ("value", "free"):
            # For value/free policies, don't force terminal target
            terminal_target = None
        else:
            # For equal/geq/soft policies, use initial SOC as target
            terminal_target = soc_override

        # Determine if we should apply a fixed design to this window
        # Priority: 1) New design_spec system, 2) Legacy fix_design system
        should_apply_design = False

        if active_design_spec is not None:
            # New system: apply design from window apply_from_window onwards
            if window_idx >= apply_from_window:
                should_apply_design = True
                logger.debug("[DESIGN] Window %d: Applying design_spec (mode=%s)", window_idx, design_mode)
        elif design_state is not None:
            # Legacy system
            should_fix_design = bool(
                fix_design
                or (design is None and window_idx > 0)
            )
            if should_fix_design:
                should_apply_design = True
                logger.debug("[DESIGN] Window %d: Applying legacy design_state", window_idx)

        if should_apply_design:
            if active_design_spec is not None:
                # Use new apply_design_to_config from design module
                window_cfg = apply_design_to_config(window_cfg, active_design_spec)
            elif design_state is not None:
                # Legacy: use old _apply_design_fix
                window_cfg = _apply_design_fix(window_cfg, design_state)

        _apply_cost_overrides(window_cfg, cost_plan, window_idx)

        # Pass SOC override directly to build_model (robust approach)
        window_result = _solve_scenario(
            window_table,
            window_cfg,
            dt_h,
            solver_name,
            soc_init_override=soc_override,
            terminal_target_override=terminal_target,
        )

        # Check for infeasible window
        term_cond = (window_result.solver.get("termination_condition") or "").lower()
        if "infeasible" in term_cond or "unbounded" in term_cond:
            logger.error(
                "RH Window %d (start=%d) is %s. Stopping optimization. "
                "Check: heat demand vs capacity, storage SOC constraints, terminal_policy setting.",
                window_idx, start, term_cond
            )
            raise RuntimeError(
                f"Rolling horizon window {window_idx} is infeasible. "
                f"Termination condition: {term_cond}. "
                f"Hint: Check if heat demand exceeds available capacity, "
                f"or if storage terminal_policy='equal' cannot be satisfied."
            )

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

        # Extract design from window 0 if in optimize mode and no design yet
        if design_state is None:
            design_state = _extract_design_data(window_result.summary)

        # For "optimize" mode: extract DesignSpec after first window
        if design_mode == "optimize" and active_design_spec is None and window_idx == 1:
            active_design_spec = extract_design_from_summary(window_result.summary)
            errors = validate_design(active_design_spec)
            if errors:
                logger.warning("[DESIGN] Extracted design has validation issues: %s", errors)
            else:
                logger.info("[DESIGN] Extracted design from Window 0: storage=%.1f MWh / %.1f MW",
                           active_design_spec.storage.capacity_mwh if active_design_spec.storage else 0,
                           active_design_spec.storage.power_mw if active_design_spec.storage else 0)

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
        logger.info(f"[RH] _next_soc: No SOC series or invalid commit_len, using fallback={fallback}")
        return fallback
    idx = min(commit_len - 1, len(soc_series) - 1)
    soc_value = float(soc_series[idx]) if idx >= 0 else fallback
    logger.info(f"[RH] _next_soc: Extracting SOC at index {idx} (commit_len={commit_len})")
    logger.info(f"  - SOC value: {soc_value} MWh")
    if len(soc_series) > 0:
        logger.info(f"  - SOC range in window: [{min(soc_series):.1f}, {max(soc_series):.1f}] MWh")
    return soc_value


def _solve_scenario(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float,
    solver_name: str,
    *,
    soc_init_override: float | None = None,
    terminal_target_override: float | None = None,
) -> ScenarioResult:
    model = build_model(
        table,
        cfg,
        dt_h=dt_h,
        soc_init_override=soc_init_override,
        terminal_target_override=terminal_target_override,
    )
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
            solver_used = "cbc"
            opt = pyo.SolverFactory("cbc")

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
        #model.display()

        # ====================================================================
        # EXPORT SOLVER SOLUTION AND THERMAL NETWORK RESULTS
        # ====================================================================
        export_cfg = cfg.get('output', {})
        if export_cfg.get('export_thermal_network', True) or export_cfg.get('export_solver_solution', True):
            try:
                from energis.io.thermal_network_exporter import export_all_results

                export_dir = export_cfg.get('export_dir', 'exports/thermal_network_results')
                network_mgr = getattr(model, '_network_manager', None)

                export_result = export_all_results(
                    model=model,
                    network_manager=network_mgr,
                    time_set=model.t,
                    output_dir=export_dir,
                    dt_h=dt_h,
                    export_solver_files=export_cfg.get('export_solver_solution', True),
                )

                # export_result contains 'files', 'data', and 'output_dir'
                export_files = export_result.get('files', {})
                network_data = export_result.get('data', {}).get('network', {})

                logger.info(f"[EXPORT] Exported {len(export_files)} files to {export_dir}")

                # Store export paths and network data in solver_meta for dashboard access
                solver_meta['export_files'] = export_files
                solver_meta['export_dir'] = export_dir
                solver_meta['network_data'] = network_data  # This is what dashboard needs

            except Exception as e:
                logger.warning(f"[EXPORT] Failed to export thermal network results: {e}")
                import traceback
                traceback.print_exc()

        # Check if solver found a feasible solution
        term_cond = solver_meta["termination_condition"].lower()
        if "infeasible" in term_cond or "unbounded" in term_cond:
            logger.error(
                "Solver returned %s. Model is %s. "
                "Check constraints: heat balance, storage limits, terminal policy.",
                solver_meta["status"], term_cond
            )
            # Return empty results instead of trying to extract from infeasible model
            series, summary, costs = _collect_timeseries_and_summary(
                table, cfg, dt_h, None  # Pass None to get zero-filled results
            )
            return ScenarioResult(table, series, summary, costs, solver_meta)
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
            logger.info(f"[DESIGN] Extracted HP {hp_id}: capacity={capacity:.1f} MW, build={build:.1f}")
        elif key.startswith("storage_"):
            storage = {
                "name": key.split("storage_", 1)[1],
                "capacity_mwh": float(metrics.get("Capacity_MWh", 0.0)),
                "power_mw": float(metrics.get("Power_limit_MW", 0.0)),
                "build_binary": float(metrics.get("Build_binary", metrics.get("Build", 0.0))),
            }
            print(f"[DESIGN] Extracted Storage: capacity={storage['capacity_mwh']:.1f} MWh, "
                  f"power={storage['power_mw']:.1f} MW, build={storage['build_binary']:.1f}")

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
    """Set initial SOC for next RH window in all relevant config locations."""
    logger.info(f"[RH] _set_initial_soc: Setting initial SOC for next window")
    logger.info(f"  - soc0_mwh: {soc} MWh")

    # Set in inputs (for backward compatibility)
    inputs = cfg.setdefault("inputs", {})
    if isinstance(inputs, dict):
        inputs["SOC_init"] = float(soc)

    # Set in system.storage (primary location)
    system = cfg.setdefault("system", {})
    if isinstance(system, dict):
        storage = system.setdefault("storage", {})
        if isinstance(storage, dict):
            storage["soc0_mwh"] = float(soc)
            # Also set terminal target to match new initial SOC
            terminal = storage.setdefault("terminal", {})
            if isinstance(terminal, dict):
                terminal["target_mwh"] = float(soc)

    # Also set in root-level storage (if exists) for consistency
    root_storage = cfg.get("storage")
    if isinstance(root_storage, dict):
        root_storage["soc0_mwh"] = float(soc)


def _apply_terminal_policy(cfg: MutableMapping[str, Any], policy: str) -> None:
    """Set terminal policy for storage in RH/MPC windows.
    
    CRITICAL: Must set BOTH 'policy' AND 'state' to fully override terminal behavior!
    """
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
        
        # ✅ FIX #9: Set terminal_state based on policy
        if policy in ("free", "value"):
            terminal["state"] = "free"  # No hard constraint
            terminal.pop("target_mwh", None)  # Remove target
            terminal.pop("target", None)  # Remove legacy key too
            storage.pop("terminal_soc_mwh", None)  # Remove legacy key
            storage["terminal_state"] = "free"  # Legacy key
            logger.info(f"[TERMINAL] Set to '{policy}' (state=free, no target)")
        elif policy in ("equal", "geq", "soft"):
            terminal["state"] = "cyclic"
            # Keep target if set, otherwise will use soc_init
            logger.info(f"[TERMINAL] Set to '{policy}' (state=cyclic)")

def _apply_design_fix(cfg: Dict[str, Any], design: DesignData) -> Dict[str, Any]:
    """Apply design from PF to RH/MPC."""
    cfg_copy = copy.deepcopy(cfg)
    system = cfg_copy.setdefault("system", {})
    
    logger.info(f"[DESIGN_FIX] Brownfield generators: {list(system.get('generators', {}).keys())}")
    
    # Fix greenfield heat pump capacities
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
            
            # ✅ FIX: Set ALL capacity values consistently!
            invest_cfg = hp_cfg.setdefault("investment", {})
            if isinstance(invest_cfg, dict):
                invest_cfg["enabled"] = False
                invest_cfg["capacity_min_mw"] = capacity
                invest_cfg["capacity_max_mw"] = capacity
                invest_cfg["initial_capacity_mw"] = capacity  # ✅ CRITICAL!
            
            hp_cfg["max_th_mw"] = capacity
            hp_cfg["min_th_mw"] = 0.0
            
            if build_binary >= 0.5:
                hp_cfg["enabled"] = True
                logger.info(f"[DESIGN_FIX] ✓ HP {hp_id} ENABLED: {capacity:.1f} MW")
            else:
                hp_cfg["enabled"] = False
                logger.info(f"[DESIGN_FIX] ✗ HP {hp_id} DISABLED")
    
    # Fix storage
    storage_cfg = system.get("storage")
    if storage_cfg and design.storage:
        actual_capacity = float(design.storage.get("capacity_mwh", 0.0))
        actual_power = float(design.storage.get("power_mw", 0.0))
        build_binary = float(design.storage.get("build_binary", 0.0))
        
        if actual_power <= 0 and actual_capacity > 0:
            actual_power = actual_capacity * 0.25
            logger.info(f"[DESIGN_FIX] Storage power calculated: {actual_power:.1f} MW")
        
        if build_binary >= 0.5:
            storage_cfg["enabled"] = True
            logger.info(f"[DESIGN_FIX] ✓ Storage ENABLED: {actual_capacity:.1f} MWh / {actual_power:.1f} MW")
        else:
            storage_cfg["enabled"] = False
            
        storage_cfg["max_energy_mwh"] = actual_capacity
        storage_cfg["max_power_mw"] = actual_power
        
        # Force terminal to free
        terminal_cfg = storage_cfg.setdefault("terminal", {})
        terminal_cfg["state"] = "free"
        terminal_cfg["policy"] = "free"
        terminal_cfg.pop("target_mwh", None)
        terminal_cfg.pop("target", None)
        storage_cfg.pop("terminal_soc_mwh", None)
        storage_cfg["terminal_state"] = "free"
        logger.info(f"[DESIGN_FIX] Storage terminal → FREE")
        
        # ✅ FIX: Set ALL storage investment values consistently!
        invest_cfg = storage_cfg.setdefault("investment", {})
        if isinstance(invest_cfg, dict):
            invest_cfg["enabled"] = False
            invest_cfg["energy_capacity_min_mwh"] = actual_capacity
            invest_cfg["energy_capacity_max_mwh"] = actual_capacity
            invest_cfg["power_capacity_min_mw"] = actual_power
            invest_cfg["power_capacity_max_mw"] = actual_power
            invest_cfg["initial_energy_capacity_mwh"] = actual_capacity  # ✅ CRITICAL!
            invest_cfg["initial_power_capacity_mw"] = actual_power  # ✅ CRITICAL!
    
    return cfg_copy

def _register_default_steps() -> None:
    register_workflow_step("PF", _pf_step)
    register_workflow_step("RH", _rh_step)
    register_workflow_step("MPC", _mpc_step)


_register_default_steps()


def _write_network_data_to_dir(network_data: Dict[str, Any], outdir: str) -> Dict[str, str]:
    """Write thermal network results from solver_meta['network_data'] to outdir.

    Creates:
      {outdir}/thermal_network/nodes_timeseries.csv  — T_supply, T_return per node
      {outdir}/thermal_network/pipes_timeseries.csv  — m_dot, delta_p, velocity per pipe
      {outdir}/thermal_network/network_summary.json  — averages and topology

    Returns dict of written file paths.
    """
    import json as _json
    import pandas as _pd

    if not network_data:
        return {}

    net_dir = os.path.join(outdir, "thermal_network")
    os.makedirs(net_dir, exist_ok=True)
    written: Dict[str, str] = {}

    # ── Node timeseries ──────────────────────────────────────────────────────
    node_ts: Dict[str, list] = {}
    node_summary: Dict[str, Dict] = {}
    for node_id, node_info in network_data.get('nodes', {}).items():
        for key in ('T_supply_series', 'T_return_series'):
            col = f"{node_id}_{key.replace('_series', '')}"
            if key in node_info:
                node_ts[col] = node_info[key]
        node_summary[node_id] = {
            k: v for k, v in node_info.items()
            if not k.endswith('_series') and k not in ('id',)
        }

    if node_ts:
        node_csv = os.path.join(net_dir, "nodes_timeseries.csv")
        _pd.DataFrame(node_ts).to_csv(node_csv, sep=';', index=True)
        written['nodes_timeseries'] = node_csv
        logger.info("[EXPORT] Thermal network nodes -> %s", node_csv)

    # ── Pipe timeseries ──────────────────────────────────────────────────────
    pipe_ts: Dict[str, list] = {}
    pipe_summary: Dict[str, Dict] = {}
    for pipe_id, pipe_info in network_data.get('pipes', {}).items():
        for key in ('m_dot_series', 'velocity_series', 'delta_p_series',
                    'Q_loss_series', 'T_supply_out_series', 'T_return_out_series'):
            col = f"{pipe_id}_{key.replace('_series', '')}"
            if key in pipe_info:
                pipe_ts[col] = pipe_info[key]
        pipe_summary[pipe_id] = {
            k: v for k, v in pipe_info.items()
            if not k.endswith('_series') and k not in ('id',)
        }

    if pipe_ts:
        pipe_csv = os.path.join(net_dir, "pipes_timeseries.csv")
        _pd.DataFrame(pipe_ts).to_csv(pipe_csv, sep=';', index=True)
        written['pipes_timeseries'] = pipe_csv
        logger.info("[EXPORT] Thermal network pipes  -> %s", pipe_csv)

    # ── Summary JSON ─────────────────────────────────────────────────────────
    summary = {
        'nodes': node_summary,
        'pipes': pipe_summary,
        'network': network_data.get('summary', {}),
    }
    summary_path = os.path.join(net_dir, "network_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        _json.dump(summary, f, indent=2, default=str)
    written['network_summary'] = summary_path
    logger.info("[EXPORT] Thermal network summary -> %s", summary_path)

    return written


def export_workflow_results(
    workflow: "WorkflowResult",
    outdir: Optional[str] = None,
    save_lp: bool = False,
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
    save_lp : bool, optional
        Copy the MILP model LP file (written by the solver step) into
        {outdir}/solver/model.lp for post-hoc debugging. Default: False.

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
        logger.info(f"[EXPORT] Plot export skipped: {exc}")

    # ── Fix 1: Thermal-Network-CSV in main outdir ────────────────────────────
    network_files: Dict[str, str] = {}
    active_result = workflow.mpc_result or workflow.rh_result or workflow.pf_result
    if active_result is not None:
        network_data = active_result.solver.get('network_data', {})
        if network_data:
            try:
                network_files = _write_network_data_to_dir(network_data, outdir)
                logger.info(
                    "[EXPORT] Thermal network: %d files written to %s/thermal_network/",
                    len(network_files), outdir,
                )
            except Exception as exc:
                logger.warning("[EXPORT] Thermal network CSV export failed: %s", exc)

    # ── Fix 2: Optional LP file copy into main outdir ────────────────────────
    lp_path_in_result: Optional[str] = None
    if save_lp and active_result is not None:
        src_lp = active_result.solver.get('export_files', {}).get('solver_lp_file')
        if src_lp and os.path.isfile(src_lp):
            import shutil as _shutil
            solver_dir = os.path.join(outdir, "solver")
            os.makedirs(solver_dir, exist_ok=True)
            dest_lp = os.path.join(solver_dir, "model.lp")
            try:
                _shutil.copy2(src_lp, dest_lp)
                lp_path_in_result = dest_lp
                logger.info("[EXPORT] LP model copied → %s", dest_lp)
            except Exception as exc:
                logger.warning("[EXPORT] Could not copy LP file: %s", exc)
        else:
            logger.warning(
                "[EXPORT] --save-lp requested but no LP file found in solver results. "
                "Set output.export_solver_solution: true in config to generate it."
            )

    # Prepare return dictionary
    result_dict = {
        "outdir": outdir,
        "scenario_xlsx": bundle_paths.get("scenario_xlsx"),
        "costs_json": bundle_paths.get("costs_json"),
        "design_json": bundle_paths.get("design_json"),
        "meta_json": bundle_paths.get("meta_json"),
        "manifest_json": bundle_paths.get("manifest_json"),
        "plots": plot_files,
        "network_files": network_files,
        "lp_file": lp_path_in_result,
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
            logger.info(f"[workflow] Sweep run {idx}/{len(runs)}: horizon={horizon}, step={step}, overlap={overlap}")
        result = run_workflow(args.configs, overrides=override_cfg or None)
        steps = " -> ".join(result.plan.steps)
        logger.info(f"[workflow] Executed steps: {steps}")

        if result.pf_result is not None:
            pf_obj = result.pf_result.costs.get("objective.OBJ_value_EUR") if result.pf_result.costs else None
            logger.info(f"  • PF time steps: {len(result.pf_result.table)}")
            if pf_obj is not None:
                logger.info(f"  • PF objective: {pf_obj}")

        if result.rh_result is not None:
            logger.info(f"  • RH windows: {len(result.rh_result.windows)}")
            logger.info(f"  • RH committed steps: {len(result.rh_result.table)}")

        if args.print_design and result.design is not None:
            hp_parts = ", ".join(sorted(result.design.heat_pumps.keys())) or "none"
            logger.info(f"  • Design heat pumps: {hp_parts}")
            if result.design.storage is not None:
                logger.info(f"  • Storage design: {result.design.storage}")

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


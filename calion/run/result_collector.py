"""Result extraction from solved Pyomo models.

The heavy-lifting function :func:`_collect_timeseries_and_summary` (≈800 lines)
gathers all decision-variable values, computes cost breakdowns and CO₂
accounting, and returns structured time-series, summary sections and a flat
cost dictionary.  Supporting helpers (:func:`_gather_component_metadata`,
:func:`_flatten_summary`, etc.) are co-located here.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from typing import Any

from calion.logging_config import get_logger
from calion.utils.timeseries import TimeSeriesTable

from .utilities.pyomo_extraction import _extract_pyomo_series

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:  # pragma: no cover
    HAVE_PYOMO = False
    pyo = None


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    """Return a JSON-serialisable representation of ``value``."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(val) for val in value]
    if HAVE_PYOMO and value.__class__.__name__ == "UndefinedData":  # pragma: no cover
        return None
    return str(value)


def _flatten_summary(sections: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
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
    heat_pumps: OrderedDict[str, dict[str, float]] = OrderedDict()
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


# ---------------------------------------------------------------------------
# Component metadata
# ---------------------------------------------------------------------------

def _gather_component_metadata_unified(cfg: dict[str, Any]) -> dict[str, Any]:
    """Extract component metadata from unified (assets-based) config format."""
    meta: dict[str, Any] = {"heat_pumps": [], "storage": None, "generators": [], "p2h": None}
    assets = cfg.get("assets", {})
    fuels = cfg.get("fuels", {})
    for asset_id, asset_data in assets.items():
        atype = asset_data.get("type", "")
        if atype == "heat_pump":
            cap = float(asset_data.get("capacity_mw", 0.0))
            meta["heat_pumps"].append({
                "id": asset_id,
                "max_th": cap,
                "invest_enabled": False,
                "cap_min": 0.0,
                "cap_max": cap,
                "cap_init": cap,
            })
        elif atype == "storage":
            meta["storage"] = {
                "name": "TES",
                "e_max": float(asset_data.get("energy_mwh", 0.0)),
                "p_max": float(asset_data.get("power_mw", 0.0)),
                "invest_enabled": False,
                "e_cap_min": 0.0,
                "e_cap_max": float(asset_data.get("energy_mwh", 0.0)),
                "p_cap_min": 0.0,
                "p_cap_max": float(asset_data.get("power_mw", 0.0)),
                "e_cap_init": float(asset_data.get("energy_mwh", 0.0)),
                "p_cap_init": float(asset_data.get("power_mw", 0.0)),
            }
        elif atype == "thermal_generator":
            fuel_bus = asset_data.get("fuel", "gas")
            fuel_info = fuels.get(fuel_bus, {})
            meta["generators"].append({
                "key": asset_id,
                "name": asset_id.upper(),
                "cap_th": float(asset_data.get("capacity_mw", 0.0)),
                "fuel_bus": fuel_bus,
                "fuel_price": float(fuel_info.get("price_eur_mwh", 0.0)),
                "fuel_emission": float(fuel_info.get("ef_kg_per_mwh_fuel", 0.0)),
                "has_el": asset_data.get("el_eff") is not None,
            })
        # In _gather_component_metadata_unified(), ersetze:
        elif atype == "p2h":
            meta["p2h"] = {
                "name": asset_id.upper(),  # "EBOILER_MAIN" statt "P2H"
                "cap_th": float(asset_data.get("capacity_mw", 0.0)),
                "eff": float(asset_data.get("efficiency", 0.99)),
            }
    return meta


def _gather_component_metadata(cfg: dict[str, Any]) -> dict[str, Any]:
    from calion.utils.config_utils import apply_heat_pump_defaults
    meta: dict[str, Any] = {
        "heat_pumps": [],
        "storage": None,
        "generators": [],
        "p2h": None,
    }

    syscfg = cfg.get("system", {})

    # If the config uses the unified format (assets-based), use the dedicated handler
    has_legacy = (
        syscfg.get("heat_pumps") or syscfg.get("storage") or syscfg.get("generators")
    )
    if not has_legacy and cfg.get("assets"):
        return _gather_component_metadata_unified(cfg)

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
                "name": key,
                "cap_th": float(par.get("cap_th_mw", 0.0)),
                "fuel_bus": fuel_bus,
                "fuel_price": float(fuel_info.get("price_eur_mwh", 0.0)),
                "fuel_emission": float(fuel_info.get("ef_kg_per_mwh_fuel", 0.0)),
                "has_el": gpar.get("el_eff") is not None,
            }
        )

    return meta


# ---------------------------------------------------------------------------
# Main result extraction
# ---------------------------------------------------------------------------

def _collect_timeseries_and_summary(
    table: TimeSeriesTable,
    cfg: dict[str, Any],
    dt_h: float,
    model: Any | None,
) -> tuple[OrderedDict[str, list[float]], OrderedDict[str, OrderedDict[str, Any]], dict[str, Any]]:
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
    from calion.constants import HOURS_PER_YEAR
    meta = _gather_component_metadata(cfg)
    n = len(table)
    grid_cfg = cfg.get("grid", {})
    period_fraction = float(n * dt_h / HOURS_PER_YEAR) if n else 0.0
    demand_year_fraction = float(grid_cfg.get("year_fraction", period_fraction))

    series: OrderedDict[str, list[float]] = OrderedDict()
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
        series[f"{comp}_COP_input"] = [0.0] * n
        series[f"{comp}_WRG_ratio"] = [0.0] * n

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
            ("Grid_energy_cost_EUR", 0.0),
            ("Electricity_base_cost_EUR", 0.0),
            ("Electricity_energy_fee_EUR", 0.0),
            ("Electricity_grid_fee_EUR", 0.0),
            ("Grid_sell_revenue_EUR", 0.0),
            ("Grid_net_cost_EUR", 0.0),
            ("Fuel_cost_EUR", 0.0),
            ("Fuel_emissions_t", 0.0),
            ("Dump_cost_EUR", 0.0),
            ("CO2_cost_EUR", 0.0),
            ("CO2_price_EUR_per_t", float(cfg.get("costs", {}).get("co2_price_eur_per_t", 0.0))),
            ("Include_CO2_in_objective", bool(cfg.get("costs", {}).get("include_co2_cost_in_objective", True))),
            ("Demand_charge_cost_EUR", 0.0),
            ("Capex_cost_EUR", 0.0),
            ("Capex_heat_pumps_EUR", 0.0),
            ("Capex_storage_EUR", 0.0),
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
            except (ValueError, TypeError, KeyError, AttributeError) as exc:  # pragma: no cover - defensive
                logger.warning("Error processing series %s: %s", key, exc)

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
            cop_param = getattr(model, f"{comp}_COP", None)
            if cop_param is not None:
                for t in times:
                    idx = t - 1
                    if 0 <= idx < n:
                        try:
                            series[f"{comp}_COP_input"][idx] = float(pyo.value(cop_param[t]))
                        except (ValueError, TypeError, KeyError):
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
        objective["OBJ_value_EUR"] = model_obj_value
        objective["P_buy_peak_MW"] = float(pyo.value(model.P_buy_peak)) if hasattr(model, "P_buy_peak") else 0.0

        # CO2 per-component extraction
        co2_by_fuel_type = {
            'gas': {'heat_kg': 0, 'elec_kg': 0, 'total_kg': 0, 'heat_eur': 0, 'elec_eur': 0, 'total_eur': 0},
            'biomass': {'heat_kg': 0, 'elec_kg': 0, 'total_kg': 0, 'heat_eur': 0, 'elec_eur': 0, 'total_eur': 0},
            'waste': {'heat_kg': 0, 'elec_kg': 0, 'total_kg': 0, 'heat_eur': 0, 'elec_eur': 0, 'total_eur': 0}
        }

        if hasattr(model, 'co2_component_costs'):
            for comp_name, co2_data in model.co2_component_costs.items():
                objective[f"CO2_{comp_name}_heat_kg"] = float(pyo.value(co2_data['heat_kg']))
                objective[f"CO2_{comp_name}_elec_kg_gross"] = float(pyo.value(co2_data['elec_kg']))
                objective[f"CO2_{comp_name}_total_kg_gross"] = float(pyo.value(co2_data['total_kg']))
                objective[f"CO2_{comp_name}_heat_cost_EUR"] = float(pyo.value(co2_data['heat_eur']))
                objective[f"CO2_{comp_name}_elec_cost_EUR_gross"] = float(pyo.value(co2_data['elec_eur']))
                objective[f"CO2_{comp_name}_total_cost_EUR_gross"] = float(pyo.value(co2_data['total_eur']))
                objective[f"CO2_{comp_name}_type"] = co2_data.get('type', 'unknown')

                if 'fuel_bus' in co2_data:
                    fuel_type = co2_data['fuel_bus']
                    if fuel_type in co2_by_fuel_type:
                        co2_by_fuel_type[fuel_type]['heat_kg'] += float(pyo.value(co2_data['heat_kg']))
                        co2_by_fuel_type[fuel_type]['elec_kg'] += float(pyo.value(co2_data['elec_kg']))
                        co2_by_fuel_type[fuel_type]['total_kg'] += float(pyo.value(co2_data['total_kg']))
                        co2_by_fuel_type[fuel_type]['heat_eur'] += float(pyo.value(co2_data['heat_eur']))
                        co2_by_fuel_type[fuel_type]['elec_eur'] += float(pyo.value(co2_data['elec_eur']))
                        co2_by_fuel_type[fuel_type]['total_eur'] += float(pyo.value(co2_data['total_eur']))

        for fuel_type, fuel_co2_data in co2_by_fuel_type.items():
            objective[f"CO2_fuel_{fuel_type}_heat_kg"] = fuel_co2_data['heat_kg']
            objective[f"CO2_fuel_{fuel_type}_elec_kg"] = fuel_co2_data['elec_kg']
            objective[f"CO2_fuel_{fuel_type}_total_kg"] = fuel_co2_data['total_kg']
            objective[f"CO2_fuel_{fuel_type}_heat_cost_EUR"] = fuel_co2_data['heat_eur']
            objective[f"CO2_fuel_{fuel_type}_elec_cost_EUR"] = fuel_co2_data['elec_eur']
            objective[f"CO2_fuel_{fuel_type}_total_cost_EUR"] = fuel_co2_data['total_eur']

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

        if hasattr(model, 'co2_kg_fuel_to_heat_expr'):
            objective["CO2_fuel_to_heat_kg"] = float(pyo.value(model.co2_kg_fuel_to_heat_expr))

        # Zone demand charges (if configured)
        if hasattr(model, 'zone_demand_charge_values') and model.zone_demand_charge_values:
            zone_section = {}
            # All zones share the single grid connection peak
            try:
                peak_mw = float(pyo.value(model.P_buy_peak))
            except Exception:
                peak_mw = None
            for zone_id, charge_eur_per_mw_y in model.zone_demand_charge_values.items():
                zone_section[f"{zone_id}_demand_charge_EUR_per_MW_y"] = charge_eur_per_mw_y
                if peak_mw is not None:
                    zone_section[f"{zone_id}_peak_power_MW"] = peak_mw
                    zone_section[f"{zone_id}_demand_cost_EUR"] = charge_eur_per_mw_y * model.year_frac.value * peak_mw
            # Flatten zone data into objective with Zone_ prefix
            for key, val in zone_section.items():
                objective[f"Zone_{key}"] = val

        # selfuse_fraction calculation (CHP correction)
        selfuse_fraction = 1.0
        chp_elec_total_mwh = 0
        p_sell_total_mwh = sum(series["P_sell_MW"]) * dt_h if "P_sell_MW" in series else 0

        if hasattr(model, 'co2_component_costs'):
            for comp_name, co2_data in model.co2_component_costs.items():
                if co2_data.get('type') == 'chp' and co2_data.get('el_eff', 0) > 0:
                    pel_col = f"{comp_name}_Pel_MW"
                    if pel_col in series:
                        chp_elec_total_mwh += sum(series[pel_col]) * dt_h

        if chp_elec_total_mwh > 0:
            selfuse_fraction = max(0, (chp_elec_total_mwh - p_sell_total_mwh) / chp_elec_total_mwh)

        # Component-specific net values
        if hasattr(model, 'co2_component_costs'):
            for comp_name, co2_data in model.co2_component_costs.items():
                if co2_data.get('type') == 'chp':
                    co2_elec_gross = objective.get(f"CO2_{comp_name}_elec_kg_gross", 0)
                    co2_heat = objective.get(f"CO2_{comp_name}_heat_kg", 0)
                    co2_elec_net = co2_elec_gross * selfuse_fraction
                    co2_total_net = co2_heat + co2_elec_net
                    objective[f"CO2_{comp_name}_elec_kg"] = co2_elec_net
                    objective[f"CO2_{comp_name}_total_kg"] = co2_total_net

                    co2_elec_cost_gross = objective.get(f"CO2_{comp_name}_elec_cost_EUR_gross", 0)
                    co2_heat_cost = objective.get(f"CO2_{comp_name}_heat_cost_EUR", 0)
                    co2_elec_cost_net = co2_elec_cost_gross * selfuse_fraction
                    co2_total_cost_net = co2_heat_cost + co2_elec_cost_net
                    objective[f"CO2_{comp_name}_elec_cost_EUR"] = co2_elec_cost_net
                    objective[f"CO2_{comp_name}_total_cost_EUR"] = co2_total_cost_net
                else:
                    if f"CO2_{comp_name}_elec_kg_gross" in objective:
                        objective[f"CO2_{comp_name}_elec_kg"] = objective[f"CO2_{comp_name}_elec_kg_gross"]
                    if f"CO2_{comp_name}_total_kg_gross" in objective:
                        objective[f"CO2_{comp_name}_total_kg"] = objective[f"CO2_{comp_name}_total_kg_gross"]
                    if f"CO2_{comp_name}_elec_cost_EUR_gross" in objective:
                        objective[f"CO2_{comp_name}_elec_cost_EUR"] = objective[f"CO2_{comp_name}_elec_cost_EUR_gross"]
                    if f"CO2_{comp_name}_total_cost_EUR_gross" in objective:
                        objective[f"CO2_{comp_name}_total_cost_EUR"] = objective[f"CO2_{comp_name}_total_cost_EUR_gross"]

        # Total CO2 correction (CHP)
        if hasattr(model, 'co2_kg_fuel_to_elec_expr'):
            co2_fuel_to_elec_total = float(pyo.value(model.co2_kg_fuel_to_elec_expr))
            objective["CO2_fuel_to_elec_kg_gross"] = co2_fuel_to_elec_total
            co2_fuel_to_elec_net = co2_fuel_to_elec_total * selfuse_fraction
            objective["CO2_fuel_to_elec_kg"] = co2_fuel_to_elec_net
            objective["CO2_fuel_to_elec_selfuse_fraction"] = selfuse_fraction

            if "CO2_elec_total_kg_gross" in objective:
                co2_elec_net = objective["CO2_elec_total_kg_gross"] - co2_fuel_to_elec_total + co2_fuel_to_elec_net
                objective["CO2_elec_total_kg"] = co2_elec_net

            if hasattr(model, 'co2_cost_elec_expr'):
                co2_elec_cost_gross = float(pyo.value(model.co2_cost_elec_expr))
                co2_elec_cost_net = co2_elec_cost_gross * selfuse_fraction
                objective["CO2_elec_total_cost_EUR"] = co2_elec_cost_net

            if hasattr(model, 'co2_cost_total_expr') and hasattr(model, 'co2_cost_elec_expr'):
                co2_heat_cost = float(pyo.value(model.co2_cost_heat_expr)) if hasattr(model, 'co2_cost_heat_expr') else 0
                co2_total_cost_net = co2_heat_cost + co2_elec_cost_net
                objective["CO2_total_cost_EUR"] = co2_total_cost_net

        if hasattr(model, 'co2_kg_grid_to_elec_expr'):
            objective["CO2_grid_to_elec_kg"] = float(pyo.value(model.co2_kg_grid_to_elec_expr))

    else:
        times = list(range(1, n + 1))
        objective["OBJ_value_EUR"] = 0.0
        objective["P_buy_peak_MW"] = max(series["P_buy_MW"], default=0.0)
        # No model available — return early with zero-filled results
        flat = _flatten_summary(summary_sections)
        return series, summary_sections, flat

    def _find_col(data, candidates, fallback_len):
        for name in candidates:
            if name in data:
                return data[name]
        return [0.0] * fallback_len

    price_series = _find_col(table.data, ["strompreis_EUR_MWh", "electricity_price_EUR_MWh", "price_eur_mwh"], n)
    grid_co2_series = _find_col(table.data, ["grid_co2_kg_MWh", "grid_co2_kg_mwh", "co2_kg_mwh"], n)
    # Ersetze die Zeile durch:
    demand_candidates = ["waermebedarf_MWth", "heat_demand_MWth", "demand_mwth"]
    # Ersetze die Zeile mit _find_col für demand_series:
    demand_series = None
    for name in ["waermebedarf_MWth", "heat_demand_MWth", "demand_mwth"]:
        if name in table.data:
            demand_series = table.data[name]
            break

    if demand_series is None and model is not None and hasattr(model, 'heatd'):
        demand_series = [float(pyo.value(model.heatd[t])) for t in times]
        logger.info("Q_demand_total read from model.heatd (%.1f MWh total)",
                    sum(demand_series) * dt_h)

    if demand_series is None:
        v_cols = [c for c in table.data if c.endswith("_demand_MWth")]
        if v_cols:
            demand_series = [
                sum(float(table.data[col][i]) for col in v_cols)
                for i in range(n)
            ]
        else:
            demand_series = [0.0] * n
            logger.warning("No demand data found for reporting!")

    series["grid_co2_kg_MWh"] = list(grid_co2_series)
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

    base_electricity_cost = float(sum((pbuy_series[i] * price_series[i] * dt_h) for i in range(n))) if n else 0.0
    energy_fee_cost = float(energy_in * energy_fee)
    grid_fee_cost = float(energy_in * grid_cost)
    energy_cost = float(sum((pbuy_series[i] * buy_prices[i] * dt_h) for i in range(n))) if n else 0.0

    energy_revenue = float(sum((psell_series[i] * sell_prices[i] * dt_h) for i in range(n))) if n else 0.0
    grid_co2_t = float(sum((pbuy_series[i] * grid_co2_series[i] * dt_h) for i in range(n)) / 1000.0) if n else 0.0

    heat_demand_mwh = float(sum(demand_series) * dt_h) if n else 0.0

    fuel_cost_total = 0.0
    fuel_emissions_t = 0.0
    fuel_cost_by_type: dict[str, float] = {}
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
            except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
                capex_cost = 0.0
        if activation_expr is not None:
            try:
                activation_cost = float(pyo.value(activation_expr))
            except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
                activation_cost = 0.0
        if tie_expr is not None:
            try:
                tie_break_cost = float(pyo.value(tie_expr))
            except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
                tie_break_cost = 0.0
        if storage_install_expr is not None:
            try:
                storage_install_cost = float(pyo.value(storage_install_expr))
            except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
                storage_install_cost = 0.0

        hp_configs_by_id = {hp_cfg.get("id", f"HP{i}"): hp_cfg
                            for i, hp_cfg in enumerate(cfg.get("system", {}).get("heat_pumps", []))}
        for hp in meta["heat_pumps"]:
            comp = hp["id"]
            if hp.get("invest_enabled", False):
                cap_var = getattr(model, f"{comp}_cap_mw", None)
                if cap_var is not None:
                    try:
                        cap_value = float(pyo.value(cap_var))
                        hp_cfg = hp_configs_by_id.get(comp, {})
                        inv_cfg = hp_cfg.get("investment", {})
                        capex_rate = float(inv_cfg.get("capex_eur_per_mw", 0.0))
                        lifetime = float(inv_cfg.get("lifetime_years", 1.0))
                        annual_factor = period_fraction / lifetime if lifetime > 0 else 0.0
                        capex_heat_pumps += cap_value * capex_rate * annual_factor
                    except (ValueError, TypeError, KeyError):  # pragma: no cover - defensive
                        pass

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
                except (ValueError, TypeError, KeyError):  # pragma: no cover - defensive
                    pass

    for hp in meta["heat_pumps"]:
        comp = hp["id"]
        heat_series = series[f"{comp}_Q_th_MW"]
        pel_series = series[f"{comp}_Pel_MW"]
        on_series = series[f"{comp}_on"]
        q_wrg_series = series[f"{comp}_Q_wrg_MW"]
        q_def_series = series[f"{comp}_Q_def_MW"]
        cop_input_series = series[f"{comp}_COP_input"]

        cop_series = []
        wrg_ratio_series = []
        for heat, pel, q_wrg in zip(heat_series, pel_series, q_wrg_series, strict=False):
            if pel > 1e-9:
                cop_series.append(float(heat / pel))
            else:
                cop_series.append(0.0)
            if heat > 1e-9:
                wrg_ratio_series.append(float(q_wrg / heat))
            else:
                wrg_ratio_series.append(0.0)

        series[f"{comp}_COP"] = cop_series
        series[f"{comp}_WRG_ratio"] = wrg_ratio_series

        heat_mwh = float(sum(heat_series) * dt_h)
        pel_mwh = float(sum(pel_series) * dt_h)
        on_hours = float(sum(on_series) * dt_h)
        q_wrg_mwh = float(sum(q_wrg_series) * dt_h)
        q_def_mwh = float(sum(q_def_series) * dt_h)

        avg_cop_input = 0.0
        total_weight = 0.0
        for cop_in, heat in zip(cop_input_series, heat_series, strict=False):
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
                except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
                    cap_value = float(hp.get("cap_init", hp["max_th"]))
            if build_var is not None:
                try:
                    build_value = float(pyo.value(build_var))
                except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
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

        fuel_emission_factor_kg_per_mwh = gen["fuel_emission"]
        co2_series_per_gen = []
        for i in range(n):
            fuel_co2_t = fuel_series[i] * dt_h * fuel_emission_factor_kg_per_mwh / 1000.0
            co2_series_per_gen.append(fuel_co2_t)
            series["Fuel_CO2_emissions_t_per_step"][i] += fuel_co2_t
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
                except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
                    energy_cap = float(meta["storage"].get("e_cap_init", meta["storage"]["e_max"]))
            if cap_p_var is not None:
                try:
                    power_cap = float(pyo.value(cap_p_var))
                except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
                    power_cap = float(meta["storage"].get("p_cap_init", meta["storage"]["p_max"]))
            if build_var is not None:
                try:
                    build_val = float(pyo.value(build_var))
                except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
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
    # Prefer model-computed CO2 cost (includes CHP selfuse correction) over naive recalculation
    if include_co2 and "CO2_total_cost_EUR" in objective:
        co2_cost = float(objective["CO2_total_cost_EUR"])
    else:
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

    objective["Grid_energy_cost_EUR"] = energy_cost
    objective["Electricity_base_cost_EUR"] = base_electricity_cost
    objective["Electricity_energy_fee_EUR"] = energy_fee_cost
    objective["Electricity_grid_fee_EUR"] = grid_fee_cost
    objective["Grid_sell_revenue_EUR"] = energy_revenue
    objective["Grid_net_cost_EUR"] = energy_cost - energy_revenue

    objective["Fuel_cost_EUR"] = fuel_cost_total
    for fuel_type, fuel_cost in fuel_cost_by_type.items():
        objective[f"Fuel_cost_{fuel_type}_EUR"] = fuel_cost
    objective["Fuel_emissions_t"] = fuel_emissions_t

    objective["Dump_cost_EUR"] = dump_cost
    objective["CO2_cost_EUR"] = co2_cost
    objective["Demand_charge_cost_EUR"] = demand_cost

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

    series["Total_CO2_emissions_t_per_step"] = [
        series["Grid_CO2_emissions_t_per_step"][i] + series["Fuel_CO2_emissions_t_per_step"][i]
        for i in range(n)
    ] if n else []

    flat = _flatten_summary(summary_sections)
    return series, summary_sections, flat

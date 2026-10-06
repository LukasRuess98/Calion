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
            inv_cfg = asset_data.get("investment", {}) or {}
            invest_enabled = bool(inv_cfg.get("enabled", False))
            # O2 (2026-09-28, docs SS4bk): was hardcoded False regardless of the
            # asset's real `investment.enabled` config -- this silently skipped the
            # Pyomo-variable read at line ~1108 below for EVERY unified-config
            # investable heat pump (both networks: MM hp_main AND SB hp_sb both have
            # capacity_mw:0.0 + investment.enabled:true), always falling back to the
            # static config capacity_mw=0.0 -> reported "capacity=0.0 MW, build=0.0"
            # no matter what the solver actually built. See project memory
            # project_paper2_primary_balance_double_subtraction.md for the full trail.
            cap_min = float(inv_cfg.get("capacity_min_mw", 0.0)) if invest_enabled else 0.0
            cap_max = float(inv_cfg.get("capacity_max_mw", cap)) if invest_enabled else cap
            meta["heat_pumps"].append({
                "id": asset_id,
                "max_th": cap,
                "invest_enabled": invest_enabled,
                "cap_min": cap_min,
                "cap_max": cap_max,
                "cap_init": cap,
            })
        elif atype in ("storage", "geometric_storage"):
            # BUGFIX (2026-07-16): geometric_storage (Paper 2's investable TES —
            # tes_sb, tes_main) was never matched here (only the legacy "storage"
            # type was), so meta["storage"] stayed None, which gates off the
            # entire Qc/Qd/SOC series-extraction block below (`if meta["storage"]:`).
            # Result: TES charge/discharge/SOC never reached dispatch_hourly.csv
            # (silently all-zero) even though the model actively cycles it —
            # this is what made the MW-closure check look like a huge energy
            # imbalance (generation appeared far below demand) when the true
            # per-node heat balance (verified via the node_heat_audit diagnostic)
            # is correct to <0.1%. e_max/p_max stay 0 here for geometric_storage
            # (its real size is solved, not a static YAML value) — harmless,
            # since only truthiness of meta["storage"] gates the extraction, and
            # the Qc/Qd/SOC values themselves come from an independent dir(model)
            # scan for {asset}_Qc/{asset}_Qd/{asset}_E, not from this dict.
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
            _p2h_inv_cfg = asset_data.get("investment", {}) or {}
            meta["p2h"] = {
                "name": asset_id.upper(),  # "EBOILER_MAIN" statt "P2H"
                "cap_th": float(asset_data.get("capacity_mw", 0.0)),
                "eff": float(asset_data.get("efficiency", 0.99)),
                # O2 (2026-09-28, docs SS4bk): p2h had NO invest_enabled/Pyomo-read
                # path at all -- Thermal_capacity_MW was always the static config
                # value, no Build_binary reported. See heat_pump fix above, same class.
                "invest_enabled": bool(_p2h_inv_cfg.get("enabled", False)),
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
    series["P_pump_total_MW"] = [0.0] * n

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
        series["P2H_Pel_MW"]  = [0.0] * n

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

        # Aggregate pump electrical power across every pump-station node
        # (network_manager.py::_link_pump_head creates one producer_{node}_P_pump
        # per producer/mixed node). Was never surfaced as a series before, so
        # extract_artefacts.py's cost_pump_eur calculation always fell through to
        # its zero fallback even though the pump load is already inside P_buy via
        # model_finalizer.py's `self.buses.el_in.extend(pump_el_flows)`.
        nm = getattr(model, "_network_manager", None)
        if nm is not None:
            pump_power_vars = [
                getattr(model, f"producer_{node_id}_P_pump", None)
                for node_id in getattr(nm, "nodes", {})
            ]
            pump_power_vars = [v for v in pump_power_vars if v is not None]
            if pump_power_vars:
                try:
                    series["P_pump_total_MW"] = [
                        sum(pyo.value(v[t]) for v in pump_power_vars) for t in times
                    ]
                except (ValueError, TypeError, KeyError, AttributeError) as exc:  # pragma: no cover - defensive
                    logger.warning("Error processing series P_pump_total_MW: %s", exc)

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
            # Multi-node models name storage vars {asset}_SOC / {asset}_Q_charge / {asset}_Q_discharge.
            # Legacy single-node models use TES_E / TES_Qc / TES_Qd.
            import pyomo.core as _pyo_core

            def _find_sto_attrs(suffix: str, fallbacks: list[str]) -> list[str]:
                found = []
                for _a in dir(model):
                    if not _a.endswith(f"_{suffix}"):
                        continue
                    _obj = getattr(model, _a, None)
                    if _obj is None:
                        continue
                    if isinstance(_obj, (_pyo_core.base.var.IndexedVar,
                                         _pyo_core.base.var.ScalarVar,
                                         _pyo_core.base.reference.Reference,
                                         _pyo_core.base.block.BlockData)):
                        found.append(_a)
                    elif hasattr(_obj, "__getitem__") and hasattr(_obj, "_index"):
                        found.append(_a)
                if not found:
                    found = [fb for fb in fallbacks if getattr(model, fb, None) is not None]
                return found

            def _sum_sto(suffix: str, fallbacks: list[str], out_key: str) -> None:
                combined = [0.0] * len(times)
                hit = False
                for _attr in _find_sto_attrs(suffix, fallbacks):
                    for _i, _v in enumerate(_extract_pyomo_series(getattr(model, _attr), times, _attr)):
                        combined[_i] += _v
                    hit = True
                if hit:
                    series[out_key] = combined

            # BUGFIX (2026-07-16): geometric_storage names its state-of-charge var
            # "{asset}_E" (e.g. tes_sb_E, tes_main_E), not "{asset}_SOC" -- the old
            # suffix "SOC" never matched anything via the dir(model) scan and "TES_E"
            # (legacy single-node name) doesn't match the multi-node {asset}_E pattern
            # either, so TES_SOC_MWh/SOC_MWh was always empty regardless of the
            # meta["storage"] gate fix above.
            _sum_sto("E", ["TES_E"], "TES_SOC_MWh")
            # Actual Pyomo vars are named {asset}_Qc / {asset}_Qd (not _Q_charge / _Q_discharge)
            _sum_sto("Qc", ["TES_Qc", "tes_main_Qc", "tes_sb_Qc", "tes_existing_Qc"], "TES_charge_MW")
            _sum_sto("Qd", ["TES_Qd", "tes_main_Qd", "tes_sb_Qd", "tes_existing_Qd"], "TES_discharge_MW")

        for gen in meta["generators"]:
            comp = gen["name"]
            _extract(getattr(model, f"{comp}_Qth", None), f"{comp}_Q_th_MW")
            _extract(getattr(model, f"{comp}_fuel", None), f"{comp}_fuel_MW")
            if gen["has_el"]:
                _extract(getattr(model, f"{comp}_Pel", None), f"{comp}_Pel_MW")

        if meta["p2h"]:
            # Try comp-specific attr name (network model: EBOILER_MAIN_Qth) then legacy P2H_Qth
            _p2h_comp = meta["p2h"]["name"]
            _p2h_qth = getattr(model, f"{_p2h_comp}_Qth",
                               getattr(model, "P2H_Qth", None))
            _p2h_pel = getattr(model, f"{_p2h_comp}_Pel",
                               getattr(model, "P2H_Pel", None))
            _extract(_p2h_qth, "P2H_Q_th_MW")
            _extract(_p2h_pel, "P2H_Pel_MW")

        # ── Paper 2: geometric TES investment scalars + endogenous site choice ──
        # Captured here (model in scope) because pf_result carries no model ref;
        # extract_artefacts_p2.write_geometry_p2 reads these from the summary.
        try:
            _geo_sum = {}
            for _a in dir(model):
                if _a.endswith("_V_m3"):
                    _comp = _a[: -len("_V_m3")]
                    _V = pyo.value(getattr(model, _a), exception=False)
                    _bld_v = getattr(model, f"{_comp}_build", None)
                    _bld = pyo.value(_bld_v, exception=False) if _bld_v is not None else 0.0
                    _emax_e = getattr(model, f"{_comp}_E_max_expr", None)
                    _emax = pyo.value(_emax_e, exception=False) if _emax_e is not None else 0.0
                    _capp_v = getattr(model, f"{_comp}_cap_power", None)
                    _capp = pyo.value(_capp_v, exception=False) if _capp_v is not None else 0.0
                    _geo_sum[_comp] = {
                        "V_m3": float(_V or 0.0),
                        "build": float(_bld or 0.0),
                        "E_max_MWh": float(_emax or 0.0),
                        "cap_power_MW": float(_capp or 0.0),
                    }
            if _geo_sum:
                objective["tes_geometry"] = _geo_sum
        except Exception as _exc:  # noqa: BLE001 - reporting only
            logger.debug("tes_geometry capture failed: %s", _exc)

        # ── Diagnostic (2026-07-16): per-node ht_out/ht_in audit ────────────
        # Cross-checks whether the true total heat injected into the network
        # (summed directly off every node's system_buses.ht_out, the actual
        # decision variables the heat-balance constraints use) matches the
        # per-asset dispatch export (dispatch_per_asset.csv/dispatch_hourly.csv
        # gen_cols). If they disagree, the per-asset export is missing a
        # generator term. If they agree but are both far below total demand,
        # the gap is a real formulation issue, not a reporting one.
        try:
            _sysbuses = getattr(model, '_system_buses', None)
            if _sysbuses is not None:
                _node_audit = {}
                for _nid, _nbus in _sysbuses.nodes.items():
                    _out_sum = 0.0
                    for _f in (_nbus.ht_out or []):
                        for _t in model.t:
                            _v = pyo.value(_f[_t], exception=False)
                            _out_sum += float(_v or 0.0)
                    _in_sum = 0.0
                    for _f in (_nbus.ht_in or []):
                        for _t in model.t:
                            _v = pyo.value(_f[_t], exception=False)
                            _in_sum += float(_v or 0.0)
                    if _out_sum or _in_sum:
                        _node_audit[_nid] = {"ht_out_MWh": round(_out_sum, 1),
                                              "ht_in_MWh": round(_in_sum, 1)}
                if _node_audit:
                    objective["node_heat_audit"] = _node_audit
                    objective["node_heat_audit_total_ht_out_MWh"] = round(
                        sum(v["ht_out_MWh"] for v in _node_audit.values()), 1
                    )
                # ── FULL heat-balance term audit (source of truth = the constraint) ──
                # Σht_out == Σheatd + ΣQ_dump + Σht_in + Σnetwork_loss + ΣQ_net_buf.
                # Residual must be ~0 (solver tol). If ~0, any export closure
                # disagreement is a demand-DEFINITION/reporting error; if not ~0,
                # it is a real formulation bug (2026-09-03, C1 diagnosis).
                def _psum(_attr):
                    _o = getattr(model, _attr, None)
                    if _o is None:
                        return None
                    _s = 0.0
                    for _t in model.t:
                        try:
                            _s += float(pyo.value(_o[_t], exception=False) or 0.0)
                        except Exception:
                            pass
                    return round(_s, 1)
                _tot_out = round(sum(v["ht_out_MWh"] for v in _node_audit.values()), 1) if _node_audit else None
                _tot_in = round(sum(v["ht_in_MWh"] for v in _node_audit.values()), 1) if _node_audit else 0.0
                _hd, _dp = _psum("heatd"), _psum("Q_dump")
                _nl, _bf = _psum("network_Q_loss_per_timestep"), _psum("Q_net_buf")
                # Sum every pipe's return-side loss Var (Σ Q_loss_return). In the multi-node
                # nodal balance, Q_delivered (supply side) embeds the SUPPLY loss and m.heatd
                # already carries it, so the balance adds ONLY the return loss on top (see
                # constraint_builder primary_producer_balance, 2026-09-03 fix). Using the full
                # network_Q_loss here would double-count the supply portion (the −25%
                # phantom residual seen before this fix).
                _rl = 0.0
                try:
                    for _v in model.component_objects(pyo.Var, active=True):
                        if _v.name.endswith("Q_loss_return"):
                            for _t in model.t:
                                _rl += float(pyo.value(_v[_t], exception=False) or 0.0)
                except Exception:
                    _rl = 0.0
                _rl = round(_rl, 1)
                _nodal = hasattr(model, "global_dump_balance")
                # ── AUTHORITATIVE closure = the actual heat-balance CONSTRAINT residual ──
                # Evaluate every ht_balance* constraint body against its bound. This uses
                # EXACTLY the constraint's own terms (Q_delivered, return_loss, dump, charge),
                # so it can never drift the way the heatd/network_loss proxy did — that proxy
                # showed a phantom −25% (double-counted supply loss) and later −2.08% (heatd
                # not tracking the j13 U change) while the physical balance was fine. Equality
                # constraints hold to solver FeasibilityTol, so a nonzero here is a REAL bug.
                _con_resid_sum = 0.0
                _con_resid_max = 0.0
                _con_n = 0
                try:
                    for _con in model.component_objects(pyo.Constraint, active=True):
                        if not _con.name.startswith("ht_balance"):
                            continue
                        for _idx in _con:
                            _c = _con[_idx]
                            _body = pyo.value(_c.body, exception=False)
                            _lo = pyo.value(_c.lower, exception=False)
                            if _body is None or _lo is None:
                                continue
                            _r = _body - _lo
                            _con_resid_sum += abs(_r)
                            _con_resid_max = max(_con_resid_max, abs(_r))
                            _con_n += 1
                except Exception:  # noqa: BLE001 - reporting only
                    pass
                _con_resid_sum = round(_con_resid_sum, 3)
                _con_resid_max = round(_con_resid_max, 4)
                # Proxy term breakdown kept as DIAGNOSTIC only (not the closure verdict).
                _loss_term = _rl if _nodal else (_nl or 0.0)
                _loss_kind = "return_only(nodal)" if _nodal else "network_full(single-node)"
                if _tot_out is not None:
                    _rhs = (_hd or 0.0) + (_dp or 0.0) + _tot_in + _loss_term + (_bf or 0.0)
                    _proxy_resid = round(_tot_out - _rhs, 1) if _hd is not None else None
                    objective["heat_balance_audit"] = {
                        # authoritative:
                        "constraint_residual_sum_MWh": _con_resid_sum,
                        "constraint_residual_max_MWh": _con_resid_max,
                        "n_balance_constraints": _con_n,
                        "closes": bool(_con_resid_max < 1.0),
                        # diagnostic term breakdown (NOT the verdict):
                        "sum_ht_out_MWh": _tot_out, "sum_ht_in_MWh": _tot_in,
                        "sum_heatd_MWh": _hd, "sum_Q_dump_MWh": _dp,
                        "sum_network_loss_full_MWh": _nl, "sum_return_loss_MWh": _rl,
                        "sum_Q_net_buf_MWh": _bf,
                        "proxy_residual_MWh": _proxy_resid, "proxy_loss_kind": _loss_kind,
                    }
                    logger.info("[HEAT-BALANCE-AUDIT] constraint residual: sum=%.3f max=%.4f MWh "
                                "over %d balances -> %s | (diag: ht_out=%.0f heatd=%s netloss_full=%s "
                                "return=%.0f dump=%s)",
                                _con_resid_sum, _con_resid_max, _con_n,
                                "CLOSES" if _con_resid_max < 1.0 else "DOES NOT CLOSE",
                                _tot_out, _hd, _nl, _rl, _dp)
        except Exception as _exc:  # noqa: BLE001 - reporting only
            logger.debug("node_heat_audit capture failed: %s", _exc)

        try:
            for _grp in ("hp", "tes"):
                _y = getattr(model, f"endog_{_grp}_site_y", None)
                if _y is not None:
                    _sel = [str(_c) for _c in _y
                            if float(pyo.value(_y[_c], exception=False) or 0.0) > 0.5]
                    objective[f"endog_{_grp}_site"] = _sel[0] if _sel else None
        except Exception as _exc:  # noqa: BLE001 - reporting only
            logger.debug("endogenous site capture failed: %s", _exc)

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
    om_cost = 0.0  # V3 (docs SS4bw): fixed O&M
    var_om_cost = 0.0  # W2 (docs SS4bw-W): variable O&M
    # 2026-09-22 (author-approved Step A, cost_breakdown.json): the objective has 17 additive terms
    # (constraint_builder.create_objective; 15 as of the original Step A audit, +1 om_cost (V3) and
    # +1 var_om_cost (W2), both docs SS4bw); only 4 (capex/activation/tie_break/storage_install)
    # were ever read back here originally. The other terms -- terminal_value, demand_slack,
    # return_anchor, pressure_reg, lateral_tiebreak, pressure_slack, om_cost, var_om_cost -- would
    # otherwise silently fall into "Objective_residual_EUR" with no way to tell which one, if any,
    # was nonzero. Read all of them by name so residual -> ~0 and every term is individually
    # auditable (cost_breakdown.json). Must run in the SAME process as the solve (these Expressions
    # live on the live Pyomo model; nothing is reconstructable from a saved .sol file).
    terminal_value_cost = 0.0
    demand_slack_cost = 0.0
    return_anchor_cost = 0.0
    pressure_reg_cost = 0.0
    lateral_tiebreak_cost = 0.0
    pressure_slack_cost = 0.0
    data_closure_cost = 0.0

    if model is not None and HAVE_PYOMO:
        def _v(attr):
            expr = getattr(model, attr, None)
            if expr is None:
                return 0.0
            try:
                return float(pyo.value(expr))
            except (ValueError, TypeError, AttributeError):  # pragma: no cover - defensive
                return 0.0

        capex_cost = _v("capex_cost_expr")
        activation_cost = _v("activation_cost_expr")
        tie_break_cost = _v("tie_break_cost_expr")
        storage_install_cost = _v("storage_install_cost_expr")
        om_cost = _v("om_cost_expr")
        var_om_cost = _v("var_om_cost_expr")
        terminal_value_cost = _v("terminal_value_expr")
        demand_slack_cost = _v("demand_slack_cost_expr")
        return_anchor_cost = _v("return_anchor_cost_expr")
        pressure_reg_cost = _v("pressure_reg_cost_expr")
        lateral_tiebreak_cost = _v("lateral_tiebreak_cost_expr")
        pressure_slack_cost = _v("pressure_slack_cost_expr")
        data_closure_cost = _v("data_closure_cost_expr")
        # TEMPORARY diagnostic cross-check (2026-09-22, residual investigation): the 5 "legacy"
        # buckets (energy/dump/fuel/co2/demand) are ALSO stored as named Expressions on the model
        # (create_objective's diagnostic block) but this function has always recomputed them
        # independently from extracted hourly series instead of reading those Expressions. If the
        # two disagree, the series-recompute (not model.obj) is the one that's wrong. Captured into
        # objective["_diag_expr_*"], read once, then removed once the residual is understood.
        _diag_energy_cost_expr = _v("energy_cost_expr")
        _diag_dump_cost_expr = _v("dump_cost_expr")
        _diag_fuel_cost_expr = _v("fuel_cost_expr")
        _diag_co2_cost_expr = _v("co2_cost_expr")
        _diag_demand_cost_expr = _v("demand_cost_expr")

        # Pressure-slack audit (2026-09-22, B1b prep): model.pressure_slack_terms is a list of
        # (slack_var, penalty) set by thermal_node.py's station_dp block, one Var per node with
        # pressure_drop_enabled, indexed over time. The aggregate cost (pressure_slack_cost_expr)
        # already flows into the objective; this additionally records WHERE/WHEN it is nonzero,
        # needed to derive a fixed per-node pressure-bound widening (replaces the slack mechanism
        # entirely once baked in -- see thermal_node.py CALION_PRESSURE_SLACK_MODE).
        _pressure_slack_audit = {}
        for _sv, _pen in getattr(model, "pressure_slack_terms", []):
            _entries = {}
            for _t in _sv:
                try:
                    _val = float(pyo.value(_sv[_t], exception=False) or 0.0)
                except Exception:  # noqa: BLE001
                    _val = 0.0
                if abs(_val) > 1e-9:
                    _entries[str(_t)] = _val
            if _entries:
                _pressure_slack_audit[_sv.name] = {
                    "penalty_eur_per_bar_h": _pen,
                    "n_nonzero_hours": len(_entries),
                    "max_bar": max(_entries.values()),
                    "sum_bar_h": sum(_entries.values()),
                    "hours": _entries,
                }

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
        # V1/V5 (2026-09-30, docs SS4bq): previously gated on hp.get("invest_enabled"),
        # which was the O2 bug (docs SS4bk) -- for a non-investable HP with a genuine
        # nonzero built capacity (fixed via .fix(), e.g. Q2/SB-S0-HK0-HPFIX533), this
        # skipped the live read entirely and reported the WRONG static fallback. Fixed
        # by always attempting the live Pyomo-variable read (via exception=False, which
        # returns None instead of raising for a genuinely unset var) regardless of
        # invest_enabled, and only falling back to the static config value when the
        # live read is unavailable (None) -- not based on a flag that has repeatedly
        # proven unreliable as a proxy for "does a meaningful value exist here".
        if model is not None and HAVE_PYOMO:
            cap_var = getattr(model, f"{comp}_cap_mw", None)
            build_var = getattr(model, f"{comp}_build", None)
            if cap_var is not None:
                _v = pyo.value(cap_var, exception=False)
                if _v is not None:
                    cap_value = float(_v)
            if build_var is not None:
                _v = pyo.value(build_var, exception=False)
                if _v is not None:
                    build_value = float(_v)
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
        _zero_n = [0.0] * n
        # comp name is "EBOILER_MAIN"; series key is legacy "P2H_Q_th_MW" — fall back to it
        heat_series = series.get(f"{comp}_Q_th_MW", series.get("P2H_Q_th_MW", _zero_n))
        pel_series  = series.get(f"{comp}_Pel_MW",  series.get("P2H_Pel_MW",  _zero_n))
        heat_mwh = float(sum(heat_series) * dt_h)
        pel_mwh = float(sum(pel_series) * dt_h)
        # O2 (2026-09-28, docs SS4bk): p2h previously never read its own Pyomo
        # investment variables (unlike heat_pump/storage) -- always reported the
        # static config capacity_mw, no Build_binary at all. Mirrors the
        # heat_pump fix above; naming convention verified against
        # full_solution_dump.json (EK_SB_cap_mw / EK_SB_build).
        p2h_cap_value = float(meta["p2h"]["cap_th"])
        p2h_build_value = 1.0 if p2h_cap_value > 0 else 0.0
        # V1 (2026-09-30, docs SS4bq): same fix as the heat_pump section above --
        # always attempt the live read, don't gate on invest_enabled.
        if model is not None and HAVE_PYOMO:
            p2h_cap_var = getattr(model, f"{comp}_cap_mw", None)
            p2h_build_var = getattr(model, f"{comp}_build", None)
            if p2h_cap_var is not None:
                _v = pyo.value(p2h_cap_var, exception=False)
                if _v is not None:
                    p2h_cap_value = float(_v)
            if p2h_build_var is not None:
                _v = pyo.value(p2h_build_var, exception=False)
                if _v is not None:
                    p2h_build_value = float(_v)
        p2h_section = OrderedDict(
            [
                ("Heat_output_MWh", heat_mwh),
                ("Electricity_input_MWh", pel_mwh),
                ("Thermal_capacity_MW", p2h_cap_value),
                ("Build_binary", p2h_build_value),
                ("Investment_enabled", bool(meta["p2h"].get("invest_enabled", False))),
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
    # V5 (2026-09-30, docs SS4bw): CO2_cost_EUR is now the GROSS value (matching what
    # create_objective's calculate_co2_costs() actually adds to model.obj -- captured
    # live as co2_cost_expr/_diag_co2_cost_expr_EUR below), NOT the CHP-selfuse-netted
    # figure. Previously (pre-V5), CO2_cost_EUR silently held the NETTED value while
    # model.obj optimized GROSS -- the resulting mismatch was papered over by a
    # dedicated "CO2_selfuse_netting_adjustment_EUR" aux term specifically engineered
    # to cancel Objective_residual_EUR (extract_artefacts_p2.py's write_cost_breakdown_p2,
    # Step A). With CO2_cost_EUR now genuinely gross, Objective_residual_EUR should
    # drop to near-zero WITHOUT that cancellation trick, and the netting term becomes
    # a real, standalone reporting KPI (CO2_cost_net_of_selfuse_EUR below) instead of
    # a component of the objective reconciliation.
    # _diag_co2_cost_expr (captured earlier from model.co2_cost_expr, the live Pyomo
    # Expression create_objective built from the TRUE gross calculate_co2_costs()
    # term) is the authoritative gross figure when a live model is present -- same
    # guard condition used to originally populate it above.
    if model is not None and HAVE_PYOMO:
        co2_cost = float(_diag_co2_cost_expr)
    elif include_co2 and "CO2_total_cost_EUR" in objective:
        # No live model (e.g. reconstructed from a saved .sol) -- fall back to the
        # netted figure, the only one available in that case.
        co2_cost = float(objective["CO2_total_cost_EUR"])
    else:
        co2_cost = float(co2_price * total_emissions_t) if include_co2 else 0.0
    # V5: netted figure preserved as its own explicit, separate KPI (previously
    # silently WAS CO2_cost_EUR) -- not part of real_costs_EUR/model_aux_terms_EUR.
    if include_co2 and "CO2_total_cost_EUR" in objective:
        objective["CO2_cost_net_of_selfuse_EUR"] = float(objective["CO2_total_cost_EUR"])
    dump_cost = float(dump_cost_rate * heat_dump)

    demand_cost = 0.0
    if include_demand:
        if model is not None and HAVE_PYOMO and hasattr(model, "P_buy_peak"):
            peak = float(pyo.value(model.P_buy_peak))
        else:
            peak = float(max(pbuy_series, default=0.0))
        objective["P_buy_peak_MW"] = peak
        # Y3 (2026-10-01, docs SS4cb): demand_cost here is ALWAYS the ANNUAL-peak
        # figure (peak x rate), regardless of what actually drove the objective --
        # correct for the legacy annual/zonal modes, but WRONG for the new monthly
        # mode (whose real cost is sum of 12 monthly peaks x monthly rate, not this
        # formula). Prefer the live model.demand_cost_expr (= _diag_demand_cost_expr,
        # captured earlier from the model regardless of mode) when available -- same
        # "trust the live Pyomo Expression over a locally-recomputed guess" pattern
        # as V5's CO2_cost_EUR fix.
        if model is not None and HAVE_PYOMO:
            demand_cost = float(_diag_demand_cost_expr)
        else:
            demand_cost = float(demand_charge_rate * demand_year_fraction * peak)
    else:
        objective["P_buy_peak_MW"] = float(max(pbuy_series, default=0.0))

    # Y3 (2026-10-01, docs SS4cb): Jahresspitzen-Diagnose -- always computed (not
    # gated on demand_charge_mode) so annual vs monthly billing is comparable for
    # ANY run, independent of which mechanism actually drove its objective.
    if pbuy_series:
        _idx_sorted = sorted(range(len(pbuy_series)), key=lambda i: pbuy_series[i], reverse=True)
        _peak_i = _idx_sorted[0]
        _peak_ts = str(table.index[_peak_i]) if table is not None and _peak_i < len(table.index) else None
        objective["Annual_peak_hour_index"] = _peak_i + 1
        objective["Annual_peak_timestamp"] = _peak_ts
        objective["Top10_peak_hours_MW"] = [
            {"hour_index": i + 1, "timestamp": str(table.index[i]) if table is not None and i < len(table.index) else None,
             "P_buy_MW": pbuy_series[i]}
            for i in _idx_sorted[:10]
        ]
        if table is not None and len(table.index) == len(pbuy_series):
            _month_peaks: dict[int, float] = {}
            for _i, _ts in enumerate(table.index):
                _m = _ts.month
                _month_peaks[_m] = max(_month_peaks.get(_m, 0.0), pbuy_series[_i])
            _annual_peak = max(pbuy_series, default=0.0)
            _annual_charge = demand_charge_rate * demand_year_fraction * _annual_peak
            _monthly_rate_equiv = demand_charge_rate / 12.0
            _monthly_charge = sum(_monthly_rate_equiv * p for p in _month_peaks.values())
            objective["Demand_charge_annual_billing_EUR"] = float(_annual_charge)
            objective["Demand_charge_monthly_billing_EUR_equiv_rate"] = float(_monthly_charge)
            objective["Demand_charge_annual_minus_monthly_EUR"] = float(_annual_charge - _monthly_charge)
            objective["Monthly_peaks_MW"] = {str(k): v for k, v in sorted(_month_peaks.items())}

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
    objective["OM_fixed_cost_EUR"] = om_cost
    objective["OM_variable_cost_EUR"] = var_om_cost
    objective["Terminal_value_EUR"] = terminal_value_cost
    objective["Demand_slack_cost_EUR"] = demand_slack_cost
    objective["Return_anchor_cost_EUR"] = return_anchor_cost
    objective["Pressure_reg_cost_EUR"] = pressure_reg_cost
    objective["Lateral_tiebreak_cost_EUR"] = lateral_tiebreak_cost
    objective["Pressure_slack_cost_EUR"] = pressure_slack_cost
    objective["Data_closure_epsilon_cost_EUR"] = data_closure_cost

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
        + om_cost
        + var_om_cost
        + terminal_value_cost
        + demand_slack_cost
        + return_anchor_cost
        + pressure_reg_cost
        + lateral_tiebreak_cost
        + pressure_slack_cost
        + data_closure_cost
    )
    objective["_diag_energy_cost_expr_EUR"] = _diag_energy_cost_expr
    objective["_diag_dump_cost_expr_EUR"] = _diag_dump_cost_expr
    objective["_diag_fuel_cost_expr_EUR"] = _diag_fuel_cost_expr
    objective["_diag_co2_cost_expr_EUR"] = _diag_co2_cost_expr
    objective["_diag_demand_cost_expr_EUR"] = _diag_demand_cost_expr
    if _pressure_slack_audit:
        objective["_pressure_slack_audit"] = _pressure_slack_audit

    # Dump audit (2026-09-22, C2/C3 prep): per-node, per-hour Q_dump_{node}[t] -- needed to
    # attribute WHICH node/hour dumps heat (currently global: any node can dump; C3 will
    # restrict this to CHP-owning nodes). Every entry (even 0-valued nodes) is skipped except
    # nodes with any nonzero hour, mirroring the pressure-slack audit's format.
    _dump_audit = {}
    if model is not None and HAVE_PYOMO:
        for _dvo in model.component_objects(pyo.Var, active=True):
            if not _dvo.name.startswith("Q_dump_"):
                continue
            _nid = _dvo.name[len("Q_dump_"):]
            _dv = _dvo
            _entries = {}
            for _t in _dv:
                try:
                    _val = float(pyo.value(_dv[_t], exception=False) or 0.0)
                except Exception:  # noqa: BLE001
                    _val = 0.0
                if abs(_val) > 1e-9:
                    _entries[str(_t)] = _val
            if _entries:
                _dump_audit[_nid] = {"n_nonzero_hours": len(_entries), "max_mw": max(_entries.values()),
                                     "sum_mwh": sum(_entries.values()), "hours": _entries}
    if _dump_audit:
        objective["_dump_audit"] = _dump_audit
    # 2026-09-23 (G3, docs SS4av/SS4aw): mandatory KPI, present in EVERY run's export (0.0 unless
    # CALION_DUMP_MODE=chp_only actually made per-node dump Vars closure-eligible/unpriced --
    # legacy-mode dump is real, priced dump and must NOT be reported here).
    #
    # 2026-09-23 BUGFIX (H1 verification run, docs SS4ay): the startswith("Q_dump_") scan above
    # ALSO matches the separate, deliberately UNCAPPED per-CHP-asset "Q_dump_chp_{ASSET}" Vars
    # (C3/Ansatz B, component_assembler.py) -- e.g. a live BC-SB run reported
    # data_closure_dump_MWh=2240.48 (0.35%, apparently over the 0.25% cap) when the TRUE
    # cap-governed quantity (summed only over the real per-node Q_dump_{node_id} closure Vars,
    # i.e. _dump_audit keys NOT starting with "chp_") was 1599.94 MWh -- almost exactly AT the
    # 1599.93 MWh cap (0.25% of that run's demand), not over it. The Constraint itself was never
    # violated; only this KPI's summation was wrong. Excluded "chp_"-prefixed keys from the sum;
    # _dump_audit itself is left untouched (still useful for CHP-dump-specific diagnostics, e.g.
    # the D2 SB min-load analysis).
    import os as _os_dc
    _is_chp_only = _os_dc.environ.get('CALION_DUMP_MODE', 'legacy').strip().lower() == 'chp_only'
    _closure_mwh = (
        sum(v["sum_mwh"] for _nid, v in _dump_audit.items() if not _nid.startswith("chp_"))
        if _is_chp_only else 0.0
    )
    objective["Data_closure_dump_MWh"] = _closure_mwh
    # 2026-09-23 (H1, docs SS4ax): the cap is a DRIFT GUARD (0.25% of demand), not a physical
    # limit -- warn loudly (but do not abort a completed, feasible solve) once usage crosses half
    # the cap (0.125%), so a creeping/large excess is visible in logs well before it would ever
    # hit the hard infeasibility boundary on some other run.
    _total_demand_mwh = float(getattr(model, '_data_closure_total_demand_mwh', 0.0) or 0.0)
    _closure_pct = (100.0 * _closure_mwh / _total_demand_mwh) if _total_demand_mwh > 0 else 0.0
    objective["Data_closure_dump_pct_of_demand"] = _closure_pct
    if _is_chp_only and _closure_pct > 0.125:
        logger.warning(
            "[DATA-CLOSURE] data_closure_dump_MWh = %.4f MWh = %.4f%% of annual demand "
            "(%.2f MWh) -- above the 0.125%% drift-guard warning threshold (hard cap 0.25%%). "
            "Not an error, but investigate before treating this run as routine.",
            _closure_mwh, _closure_pct, _total_demand_mwh,
        )
    objective["Objective_residual_EUR"] = objective["OBJ_value_EUR"] - components_sum
    if abs(objective["Objective_residual_EUR"]) > 1.0:
        logger.error(
            "[COST-BREAKDOWN] Objective_residual_EUR = %.2f (> 1 EUR tolerance): the 17 named "
            "objective terms do NOT reproduce model.obj -- an objective term exists that this "
            "function still does not capture. Do not treat cost_breakdown.json as complete "
            "until this is 0.", objective["Objective_residual_EUR"],
        )

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

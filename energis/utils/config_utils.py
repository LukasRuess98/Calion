from __future__ import annotations

from typing import Any, Dict, List, Mapping

from energis.config.merge import deep_merge


def apply_heat_pump_defaults(system_cfg: Mapping[str, Any]) -> List[dict]:
    """Return heat pump configs with ``heat_pump_defaults`` applied.

    The helper preserves the original list order and leaves untouched entries
    that are not dictionaries.  Individual heat pump entries override any
    values defined in the shared defaults mapping.

    Also transforms the new config structure (technical_limits, defaults, costs)
    to the format expected by system_builder.
    """

    defaults = system_cfg.get("heat_pump_defaults")
    heat_pumps = system_cfg.get("heat_pumps", [])
    if not isinstance(heat_pumps, list) or not heat_pumps:
        return []

    resolved: List[dict] = []
    for entry in heat_pumps:
        if not isinstance(entry, Mapping):
            continue
        merged = deep_merge(defaults, entry) if isinstance(defaults, Mapping) else dict(entry)

        # Transform new config structure to old format
        merged = _normalize_heat_pump_config(merged)

        resolved.append(merged)
    return resolved


def _normalize_heat_pump_config(hp_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize heat pump config to the format expected by system_builder.

    Handles both old and new config structures:
    - Old: max_th_mw, min_th_mw, investment.enabled, etc.
    - New: technical_limits.capacity_min_mw, defaults.capacity_mw, costs.capex_eur_per_mw
    """
    result = dict(hp_cfg)

    # Check if this is the new config structure (has technical_limits or defaults)
    tech_limits = result.pop("technical_limits", None)
    hp_defaults = result.pop("defaults", None)
    costs = result.pop("costs", None)

    # If none of the new keys exist, return as-is (old format)
    if tech_limits is None and hp_defaults is None and costs is None:
        return result

    # Extract values from new structure
    if isinstance(tech_limits, dict):
        cap_min = tech_limits.get("capacity_min_mw")
        cap_max = tech_limits.get("capacity_max_mw")

        if cap_min is not None:
            result.setdefault("min_th_mw", cap_min)
        if cap_max is not None:
            result.setdefault("max_th_mw", cap_max)

    if isinstance(hp_defaults, dict):
        default_capacity = hp_defaults.get("capacity_mw")
        default_build = hp_defaults.get("build", True)

        # Store defaults for apply_optimization_config to use
        result["defaults"] = hp_defaults

        # If max_th_mw not set from technical_limits, use default
        if "max_th_mw" not in result and default_capacity is not None:
            result["max_th_mw"] = default_capacity

    # Build investment config from costs and limits
    investment = result.setdefault("investment", {})
    if not isinstance(investment, dict):
        investment = {}
        result["investment"] = investment

    if isinstance(tech_limits, dict):
        cap_min = tech_limits.get("capacity_min_mw")
        cap_max = tech_limits.get("capacity_max_mw")

        if cap_min is not None:
            investment.setdefault("capacity_min_mw", cap_min)
        if cap_max is not None:
            investment.setdefault("capacity_max_mw", cap_max)

    if isinstance(hp_defaults, dict):
        default_capacity = hp_defaults.get("capacity_mw")
        if default_capacity is not None:
            investment.setdefault("initial_capacity_mw", default_capacity)

    if isinstance(costs, dict):
        capex = costs.get("capex_eur_per_mw")
        activation = costs.get("activation_cost_eur")
        lifetime = costs.get("lifetime_years")

        if capex is not None:
            investment.setdefault("capex_eur_per_mw", capex)
        if activation is not None:
            investment.setdefault("activation_cost_eur", activation)
        if lifetime is not None:
            investment.setdefault("lifetime_years", lifetime)

    return result


def normalize_storage_config(storage_cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize storage config to the format expected by system_builder.

    Handles both old and new config structures:
    - Old: max_energy_mwh, max_power_mw, investment.enabled, etc.
    - New: technical_limits.energy_min_mwh, defaults.energy_mwh, costs.energy_capex_eur_per_mwh
    """
    result = dict(storage_cfg)

    # Check if this is the new config structure
    tech_limits = result.pop("technical_limits", None)
    sto_defaults = result.pop("defaults", None)
    costs = result.pop("costs", None)

    # If none of the new keys exist, return as-is (old format)
    if tech_limits is None and sto_defaults is None and costs is None:
        return result

    # Extract values from technical_limits
    if isinstance(tech_limits, dict):
        e_min = tech_limits.get("energy_min_mwh")
        e_max = tech_limits.get("energy_max_mwh")
        p_min = tech_limits.get("power_min_mw")
        p_max = tech_limits.get("power_max_mw")

        if e_min is not None:
            result.setdefault("min_energy_mwh", e_min)
        if e_max is not None:
            result.setdefault("max_energy_mwh", e_max)
        if p_min is not None:
            result.setdefault("min_power_mw", p_min)
        if p_max is not None:
            result.setdefault("max_power_mw", p_max)

    if isinstance(sto_defaults, dict):
        default_energy = sto_defaults.get("energy_mwh")
        default_power = sto_defaults.get("power_mw")
        default_build = sto_defaults.get("build", True)

        # Store defaults for apply_optimization_config to use
        result["defaults"] = sto_defaults

        # If max not set from technical_limits, use defaults
        if "max_energy_mwh" not in result and default_energy is not None:
            result["max_energy_mwh"] = default_energy
        if "max_power_mw" not in result and default_power is not None:
            result["max_power_mw"] = default_power

    # Build investment config from costs and limits
    investment = result.setdefault("investment", {})
    if not isinstance(investment, dict):
        investment = {}
        result["investment"] = investment

    if isinstance(tech_limits, dict):
        e_min = tech_limits.get("energy_min_mwh")
        e_max = tech_limits.get("energy_max_mwh")
        p_min = tech_limits.get("power_min_mw")
        p_max = tech_limits.get("power_max_mw")

        if e_min is not None:
            investment.setdefault("energy_capacity_min_mwh", e_min)
        if e_max is not None:
            investment.setdefault("energy_capacity_max_mwh", e_max)
        if p_min is not None:
            investment.setdefault("power_capacity_min_mw", p_min)
        if p_max is not None:
            investment.setdefault("power_capacity_max_mw", p_max)

    if isinstance(sto_defaults, dict):
        default_energy = sto_defaults.get("energy_mwh")
        default_power = sto_defaults.get("power_mw")

        if default_energy is not None:
            investment.setdefault("initial_energy_capacity_mwh", default_energy)
        if default_power is not None:
            investment.setdefault("initial_power_capacity_mw", default_power)

    if isinstance(costs, dict):
        e_capex = costs.get("energy_capex_eur_per_mwh")
        p_capex = costs.get("power_capex_eur_per_mw")
        activation = costs.get("activation_cost_eur")
        lifetime = costs.get("lifetime_years")

        if e_capex is not None:
            investment.setdefault("energy_capex_eur_per_mwh", e_capex)
        if p_capex is not None:
            investment.setdefault("power_capex_eur_per_mw", p_capex)
        if activation is not None:
            investment.setdefault("activation_cost_eur", activation)
        if lifetime is not None:
            investment.setdefault("lifetime_years", lifetime)

    return result

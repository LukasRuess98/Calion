from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml

from calion.config.merge import deep_merge


# Default heating curve profiles (fallback if config file not found)
_DEFAULT_HEATING_CURVES = {
    "standard_dh": {
        "T_supply_min_c": 80.0,
        "T_supply_max_c": 120.0,
        "T_outdoor_high_c": 20.0,
        "T_outdoor_low_c": -10.0,
    },
    "4gdh_low_temp": {
        "T_supply_min_c": 50.0,
        "T_supply_max_c": 70.0,
        "T_outdoor_high_c": 15.0,
        "T_outdoor_low_c": -5.0,
    },
    "constant_90": {
        "T_supply_min_c": 90.0,
        "T_supply_max_c": 90.0,
        "T_outdoor_high_c": 20.0,
        "T_outdoor_low_c": -10.0,
    },
}


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


def normalize_thermal_network_config(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize thermal network config to the format expected by NetworkManager.

    Supports both:
    - New structure: system.thermal_network with technical_limits, defaults, costs
    - Old structure: top-level thermal_network (can override system settings)

    The old top-level thermal_network overrides system.thermal_network,
    allowing presets to enable/disable the network.

    Returns a merged config with backward-compatible keys.
    """
    # Get new structure: system.thermal_network
    system_cfg = cfg.get("system", {})
    new_network = system_cfg.get("thermal_network", {}) if isinstance(system_cfg, dict) else {}
    if not isinstance(new_network, dict):
        new_network = {}

    # Get old structure: top-level thermal_network
    old_network = cfg.get("thermal_network", {})
    if not isinstance(old_network, dict):
        old_network = {}

    # Merge: Start with new structure, then override with old (for preset compatibility)
    # This allows presets to set thermal_network.enabled: true to override system defaults
    result = dict(new_network)
    for key, value in old_network.items():
        # Old structure overrides new structure (preset > system)
        result[key] = value

    if not result:
        return {"enabled": False}

    # Transform new structure to old format
    tech_limits = result.pop("technical_limits", None)
    net_defaults = result.pop("defaults", None)
    costs = result.pop("costs", None)

    # If none of the new keys exist, return as-is (old format)
    if tech_limits is None and net_defaults is None and costs is None:
        return result

    # Build/update parameters from defaults
    parameters = result.setdefault("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}
        result["parameters"] = parameters

    # Map defaults to parameters (for NetworkManager compatibility)
    if isinstance(net_defaults, dict):
        supply_temp = net_defaults.get("supply_temp_c")
        return_temp = net_defaults.get("return_temp_c")
        ground_temp = net_defaults.get("ground_temp_c")

        if supply_temp is not None:
            parameters.setdefault("supply_temp_nominal_c", supply_temp)
        if return_temp is not None:
            parameters.setdefault("return_temp_nominal_c", return_temp)
        if ground_temp is not None:
            parameters.setdefault("ground_temp_default_c", ground_temp)

        # Heating curve parameters (for outdoor-dependent supply temperature)
        heating_curve = net_defaults.get("heating_curve")
        if isinstance(heating_curve, dict):
            parameters.setdefault("heating_curve", heating_curve)

    # Map technical_limits to parameters
    if isinstance(tech_limits, dict):
        max_velocity = tech_limits.get("max_velocity_m_s")
        max_pressure = tech_limits.get("max_pressure_bar")
        min_pressure = tech_limits.get("min_pressure_bar")

        if max_velocity is not None:
            parameters.setdefault("max_velocity_m_s", max_velocity)
        if max_pressure is not None:
            parameters.setdefault("max_pressure_bar", max_pressure)
        if min_pressure is not None:
            parameters.setdefault("min_pressure_bar", min_pressure)

    # Store costs for investment optimization
    if isinstance(costs, dict):
        result["costs"] = costs
        # Also map to parameters for NetworkManager
        pipe_capex = costs.get("pipe_capex_eur_per_m")
        heat_loss_cost = costs.get("heat_loss_cost_eur_per_mwh")

        if pipe_capex is not None:
            parameters.setdefault("pipe_capex_eur_per_m", pipe_capex)
        if heat_loss_cost is not None:
            parameters.setdefault("heat_loss_cost_eur_per_mwh", heat_loss_cost)

    return result


def load_heating_curves(config_dir: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load heating curve profiles from configs/01_tech/heating_curves.yaml.

    Args:
        config_dir: Optional path to configs directory. If None, attempts to
                    find it relative to the package location.

    Returns:
        Dictionary mapping profile names to their parameters.
    """
    if config_dir is None:
        # Try to find configs directory relative to this file
        # calion/utils/config_utils.py -> calion -> project root -> configs
        package_dir = Path(__file__).parent.parent.parent
        config_dir = package_dir / "configs"

    heating_curves_path = config_dir / "01_tech" / "heating_curves.yaml"

    if heating_curves_path.exists():
        try:
            with open(heating_curves_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict) and "heating_curves" in data:
                    return data["heating_curves"]
        except Exception:
            pass

    # Return default profiles if config file not found
    return _DEFAULT_HEATING_CURVES


def resolve_heating_curve_profile(
    heating_curve_cfg: Mapping[str, Any],
    config_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Resolve a heating curve profile reference to its full parameters.

    If heating_curve_cfg contains a 'profile' key, looks up the named profile
    from configs/01_tech/heating_curves.yaml and returns its parameters.
    If no profile is specified or inline values are provided, returns
    the config as-is.

    Args:
        heating_curve_cfg: Heating curve configuration, may contain:
            - profile: Name of a heating curve profile to load
            - enabled: Whether heating curve is enabled
            - T_supply_min_c, T_supply_max_c, etc.: Inline values (override profile)
        config_dir: Optional path to configs directory

    Returns:
        Resolved heating curve configuration with all parameters filled in.

    Example:
        >>> cfg = {"enabled": True, "profile": "standard_dh"}
        >>> resolved = resolve_heating_curve_profile(cfg)
        >>> resolved
        {
            'enabled': True,
            'T_supply_min_c': 80.0,
            'T_supply_max_c': 120.0,
            'T_outdoor_high_c': 20.0,
            'T_outdoor_low_c': -10.0
        }
    """
    if not isinstance(heating_curve_cfg, Mapping):
        return {}

    result = dict(heating_curve_cfg)
    profile_name = result.pop("profile", None)

    # If no profile specified or inline values already present, return as-is
    has_inline_values = any(
        k in result for k in ["T_supply_min_c", "T_supply_max_c", "T_outdoor_high_c", "T_outdoor_low_c"]
    )

    if profile_name and not has_inline_values:
        # Load profile from config file
        profiles = load_heating_curves(config_dir)
        if profile_name in profiles:
            profile = profiles[profile_name]
            # Merge profile values (profile provides defaults, result overrides)
            for key, value in profile.items():
                if key not in result and key != "description":
                    result[key] = value

    return result

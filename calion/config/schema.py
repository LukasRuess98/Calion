from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

Number = (int, float)


def _require_number(value: Any, path: str) -> None:
    if value is None:
        return
    if not isinstance(value, Number):
        raise TypeError(f"Expected numeric value for {path}, got {type(value).__name__}.")
    if value < 0:
        raise ValueError(f"{path} must be non-negative, got {value}.")


def _require_positive(value: Any, path: str) -> None:
    """Require a positive number (> 0)."""
    if value is None:
        return
    if not isinstance(value, Number):
        raise TypeError(f"Expected numeric value for {path}, got {type(value).__name__}.")
    if value <= 0:
        raise ValueError(f"{path} must be positive (> 0), got {value}.")


def _require_in_range(value: Any, path: str, min_val: float, max_val: float) -> None:
    """Require a number within a range."""
    if value is None:
        return
    if not isinstance(value, Number):
        raise TypeError(f"Expected numeric value for {path}, got {type(value).__name__}.")
    if not (min_val <= value <= max_val):
        raise ValueError(f"{path} must be in range [{min_val}, {max_val}], got {value}.")


def validate_thermal_network(network_cfg: dict[str, Any]) -> list[str]:
    """Validate thermal network configuration.

    Performs the following checks:
    1. All pipe from_node and to_node reference existing nodes
    2. U-values are in realistic range (0.01 - 2.0 W/(m·K))
    3. Lengths and diameters are positive
    4. Temperatures are in realistic range

    Args:
        network_cfg: Network configuration dictionary

    Returns:
        List of warning messages (empty if all OK)

    Raises:
        ValueError: For critical validation errors
    """
    warnings = []

    if not network_cfg:
        return warnings

    # Collect all node IDs
    all_nodes: set[str] = set()

    # Production plants
    for plant in network_cfg.get("production_plants", []):
        node_id = plant.get("node_id")
        if not node_id:
            raise ValueError("Production plant missing 'node_id'")
        if node_id in all_nodes:
            raise ValueError(f"Duplicate node_id: {node_id}")
        all_nodes.add(node_id)

        # Validate temperatures
        supply_temp = plant.get("supply_temp_c")
        if supply_temp is not None:
            _require_in_range(supply_temp, f"plant {node_id}.supply_temp_c", 40, 200)

    # Pump stations
    for pump in network_cfg.get("pump_stations", []):
        node_id = pump.get("node_id")
        if not node_id:
            raise ValueError("Pump station missing 'node_id'")
        if node_id in all_nodes:
            raise ValueError(f"Duplicate node_id: {node_id}")
        all_nodes.add(node_id)

    # Consumer zones
    for consumer in network_cfg.get("consumer_zones", []):
        node_id = consumer.get("node_id")
        if not node_id:
            raise ValueError("Consumer zone missing 'node_id'")
        if node_id in all_nodes:
            raise ValueError(f"Duplicate node_id: {node_id}")
        all_nodes.add(node_id)

        # Validate return temperature
        return_temp = consumer.get("return_temp_c")
        if return_temp is not None:
            _require_in_range(return_temp, f"consumer {node_id}.return_temp_c", 20, 100)

    # Validate pipes
    for pipe in network_cfg.get("pipes", []):
        pipe_id = pipe.get("id", "unknown")

        # Check node references
        from_node = pipe.get("from_node")
        to_node = pipe.get("to_node")

        if from_node and from_node not in all_nodes:
            raise ValueError(
                f"Pipe '{pipe_id}' references unknown from_node: '{from_node}'. "
                f"Available nodes: {sorted(all_nodes)}"
            )
        if to_node and to_node not in all_nodes:
            raise ValueError(
                f"Pipe '{pipe_id}' references unknown to_node: '{to_node}'. "
                f"Available nodes: {sorted(all_nodes)}"
            )

        # Validate length
        length = pipe.get("length_m")
        if length is not None:
            _require_positive(length, f"pipe {pipe_id}.length_m")

        # Validate diameters
        for diam_key in ("current_diameter_supply_mm", "current_diameter_return_mm"):
            diam = pipe.get(diam_key)
            if diam is not None:
                _require_positive(diam, f"pipe {pipe_id}.{diam_key}")
                if diam < 20 or diam > 1500:
                    warnings.append(
                        f"Pipe '{pipe_id}' {diam_key}={diam}mm is outside typical range [20, 1500]mm"
                    )

        # Validate U-values (realistic range for district heating)
        for u_key in ("u_value_supply_w_per_m_k", "u_value_return_w_per_m_k"):
            u_val = pipe.get(u_key)
            if u_val is not None:
                _require_positive(u_val, f"pipe {pipe_id}.{u_key}")
                if u_val < 0.05 or u_val > 2.0:
                    warnings.append(
                        f"Pipe '{pipe_id}' {u_key}={u_val} W/(m·K) is outside typical range [0.05, 2.0]"
                    )

    # Validate global parameters
    params = network_cfg.get("parameters", {})
    if params:
        supply_temp = params.get("supply_temp_nominal_c")
        if supply_temp is not None:
            _require_in_range(supply_temp, "parameters.supply_temp_nominal_c", 60, 200)

        return_temp = params.get("return_temp_nominal_c")
        if return_temp is not None:
            _require_in_range(return_temp, "parameters.return_temp_nominal_c", 20, 100)

        # Check supply > return
        if supply_temp and return_temp and supply_temp <= return_temp:
            raise ValueError(
                f"Supply temperature ({supply_temp}°C) must be greater than "
                f"return temperature ({return_temp}°C)"
            )

        ground_temp = params.get("ground_temp_default_c")
        if ground_temp is not None:
            _require_in_range(ground_temp, "parameters.ground_temp_default_c", -10, 30)

        max_velocity = params.get("max_velocity_m_s")
        if max_velocity is not None:
            _require_in_range(max_velocity, "parameters.max_velocity_m_s", 0.5, 5.0)

    return warnings


def _validate_section_type(cfg: dict[str, Any], key: str, expected: type, path: str = "") -> Any:
    """Ensure *cfg[key]* is of *expected* type (or missing/None). Return the value."""
    value = cfg.get(key)
    if value is None:
        return value
    full = f"{path}.{key}" if path else key
    if not isinstance(value, expected):
        name = expected.__name__ if isinstance(expected, type) else " or ".join(t.__name__ for t in expected)
        raise TypeError(
            f"Expected '{full}' to be {name}, got {type(value).__name__}"
        )
    return value


def validate_config_schema(cfg: dict[str, Any]) -> None:
    """Light-weight schema validation for known config sections.

    The repository ships a minimal YAML loader without external dependencies,
    so this function performs essential type and range checks for keys that are
    consumed by the optimisation model.  Validation runs once at config-load
    time so that downstream code can trust the structure.
    """

    # ── Top-level section types ────────────────────────────────────────────
    _validate_section_type(cfg, "system", dict)
    _validate_section_type(cfg, "grid", dict)
    _validate_section_type(cfg, "costs", dict)
    _validate_section_type(cfg, "run", dict)
    _validate_section_type(cfg, "scenario", dict)
    _validate_section_type(cfg, "inputs", dict)

    # ── Grid section ───────────────────────────────────────────────────────
    grid = cfg.get("grid", {}) or {}
    for key in ("max_import_mw", "max_export_mw"):
        _require_number(grid.get(key), f"grid.{key}")

    # ── Run section (dt_h, solver) ─────────────────────────────────────────
    run_cfg = cfg.get("run", {}) or {}
    dt_h = run_cfg.get("dt_h")
    if dt_h is not None:
        _require_positive(dt_h, "run.dt_h")

    # ── System / storage section ───────────────────────────────────────────
    system = cfg.get("system", {}) or {}
    _validate_section_type(system, "storage", dict, "system")
    _validate_section_type(system, "heat_pumps", (dict, list), "system")

    storage = system.get("storage", {}) or {}
    if storage:
        _require_number(storage.get("energy_mwh"), "system.storage.energy_mwh")
        _require_number(storage.get("power_mw"), "system.storage.power_mw")
        _require_number(storage.get("soc0_mwh"), "system.storage.soc0_mwh")

    # ── Scenario / rolling horizon ─────────────────────────────────────────
    scenario = cfg.get("scenario", {}) or {}
    _validate_section_type(scenario, "rolling_horizon", dict, "scenario")
    rh_cfg = scenario.get("rolling_horizon", {}) or {}
    for key in ("heat_horizon_hours", "window_hours", "step_hours", "overlap_hours"):
        val = rh_cfg.get(key)
        if val is not None:
            _require_positive(val, f"scenario.rolling_horizon.{key}")

    # ── Thermal network ────────────────────────────────────────────────────
    if system.get("thermal_network", {}).get("enabled"):
        # Network might be loaded from topology_file — validate if inline
        pass

    if "pipes" in cfg or "production_plants" in cfg:
        warnings = validate_thermal_network(cfg)
        for warning in warnings:
            logger.warning(f"Network config warning: {warning}")

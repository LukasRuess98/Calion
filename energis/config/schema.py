from __future__ import annotations

from typing import Any, Set, List
import logging

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


def validate_thermal_network(network_cfg: dict[str, Any]) -> List[str]:
    """Validate thermal network configuration.

    Performs the following checks:
    1. All pipe from_node and to_node reference existing nodes
    2. Consumer demand_fractions sum to approximately 1.0
    3. U-values are in realistic range (0.01 - 2.0 W/(m·K))
    4. Lengths and diameters are positive
    5. Temperatures are in realistic range

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
    all_nodes: Set[str] = set()

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
    total_demand_fraction = 0.0
    for consumer in network_cfg.get("consumer_zones", []):
        node_id = consumer.get("node_id")
        if not node_id:
            raise ValueError("Consumer zone missing 'node_id'")
        if node_id in all_nodes:
            raise ValueError(f"Duplicate node_id: {node_id}")
        all_nodes.add(node_id)

        # Track demand fraction
        demand_fraction = consumer.get("demand_fraction", 0)
        if demand_fraction is not None:
            _require_in_range(demand_fraction, f"consumer {node_id}.demand_fraction", 0, 1)
            total_demand_fraction += demand_fraction

        # Validate return temperature
        return_temp = consumer.get("return_temp_c")
        if return_temp is not None:
            _require_in_range(return_temp, f"consumer {node_id}.return_temp_c", 20, 100)

    # Check demand fractions sum to ~1.0
    if network_cfg.get("consumer_zones"):
        if abs(total_demand_fraction - 1.0) > 0.01:
            warnings.append(
                f"Consumer demand_fractions sum to {total_demand_fraction:.3f}, expected 1.0"
            )

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


def validate_config_schema(cfg: dict[str, Any]) -> None:
    """Light-weight schema validation for known config sections.

    The repository ships a minimal YAML loader without external dependencies,
    so this function performs essential type and range checks for keys that are
    consumed by the optimisation model.
    """

    grid = cfg.get("grid", {}) or {}
    for key in ("max_import_mw", "max_export_mw"):
        _require_number(grid.get(key), f"grid.{key}")

    # Validate thermal network if present
    # Network config can be in system.thermal_network or loaded separately
    network_cfg = None
    system = cfg.get("system", {}) or {}
    if system.get("thermal_network", {}).get("enabled"):
        # Network might be loaded from topology_file
        # For now, validate if inline config exists
        pass

    # If network config is provided directly (e.g., from brownfield.yaml)
    if "pipes" in cfg or "production_plants" in cfg:
        warnings = validate_thermal_network(cfg)
        for warning in warnings:
            logger.warning(f"Network config warning: {warning}")

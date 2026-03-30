"""
Validation utilities for the Rolling Horizon workflow.

Contains validation functions that check configuration and data
consistency before running optimization.

Extracted from rolling_horizon.py to improve modularity and testability.
"""
from __future__ import annotations

from typing import Any, Dict

from calion.utils.timeseries import TimeSeriesTable
from calion.logging_config import get_logger

logger = get_logger(__name__)


def _estimate_max_thermal_capacity(cfg: dict) -> float:
    """
    Estimate the maximum thermal capacity from configuration.

    Sums up all enabled heat pump and generator thermal capacities.

    Args:
        cfg: Full system configuration dictionary

    Returns:
        Total thermal capacity in MW
    """
    cap = 0.0

    # New structure: sum assets in all network nodes (Level 2, 3, etc.)
    network_nodes = cfg.get("network", {}).get("nodes", {})
    asset_cfgs = cfg.get("assets", {})

    for node in network_nodes.values():
        for asset_name in node.get("assets", []):
            asset_cfg = asset_cfgs.get(asset_name, {})
            asset_type = asset_cfg.get("type")
            if asset_type in ("thermal_generator", "heat_pump"):
                capacity = asset_cfg.get("capacity_mw", 0.0)
                cap += float(capacity)

    # Backward compatibility: single-node legacy config under system key
    system_node = network_nodes.get("system", {})
    for asset_name in system_node.get("assets", []):
        asset_cfg = asset_cfgs.get(asset_name, {})
        asset_type = asset_cfg.get("type")
        if asset_type in ("thermal_generator", "heat_pump"):
            capacity = asset_cfg.get("capacity_mw", 0.0)
            cap += float(capacity)

    # Old structure fallback
    syscfg = cfg.get("system", {})
    from calion.utils.config_utils import apply_heat_pump_defaults

    for hp in apply_heat_pump_defaults(syscfg):
        if hp.get("enabled", True):
            cap += float(hp.get("max_th_mw", 0.0))

    gens = syscfg.get("generators", {})
    for _, par in gens.items():
        if par.get("enabled", False):
            cap += float(par.get("cap_th_mw", 0.0))

    return cap


def _assert_capacity_vs_demand(
    table: TimeSeriesTable, cfg: dict, safety: float = 1.1
) -> None:
    """
    Validate that system thermal capacity exceeds peak heat demand.

    Checks that the total thermal capacity is at least safety_factor times
    the peak heat demand. Uses CAPACITY_SAFETY_FACTOR constant as the
    actual safety factor (overrides the safety parameter for backward compat).

    Args:
        table: Time series table with 'waermebedarf_MWth' column
        cfg: System configuration dictionary
        safety: Safety factor (overridden by CAPACITY_SAFETY_FACTOR constant)

    Raises:
        RuntimeError: If capacity is insufficient to meet peak demand
    """
    from calion.constants import CAPACITY_SAFETY_FACTOR

    safety = CAPACITY_SAFETY_FACTOR
    peak_demand = max(table["waermebedarf_MWth"])
    cap = _estimate_max_thermal_capacity(cfg)

    if cap < safety * peak_demand and peak_demand > 0:
        raise RuntimeError(
            "Thermische Maximalleistung zu gering für den Demand-Peak. "
            "Bitte Kapazitäten erhöhen."
        )

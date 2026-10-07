"""
Environment variable override utilities for Rolling Horizon configuration.

Provides functions for reading and parsing environment variables that can
override configuration values from YAML files. Supports string, float,
boolean, and list parsing with clear error messages.

These functions enable running the CALION framework with configuration
overrides from the system environment without modifying config files.

Extracted from rolling_horizon.py to improve modularity and testability.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from calion.logging_config import get_logger

logger = get_logger(__name__)


# ─── Environment Variable Readers ─────────────────────────────────────────────

def _env_str(name: str) -> str | None:
    """
    Read an environment variable and return its string value.

    Args:
        name: Environment variable name

    Returns:
        Stripped string value, or None if not set or empty
    """
    value = os.environ.get(name)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _env_float(name: str) -> float | None:
    """
    Read an environment variable and parse as float.

    Args:
        name: Environment variable name

    Returns:
        Float value, or None if not set

    Raises:
        ValueError: If value cannot be parsed as float
    """
    raw = _env_str(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - guarded by tests
        raise ValueError(f"Invalid float for {name}: {raw!r}") from exc


def _env_bool(name: str) -> bool | None:
    """
    Read an environment variable and parse as boolean.

    Accepts: 1/true/yes/on for True, 0/false/no/off for False.

    Args:
        name: Environment variable name

    Returns:
        Boolean value, or None if not set

    Raises:
        ValueError: If value is not a recognized boolean string
    """
    raw = _env_str(name)
    if raw is None:
        return None
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean for {name}: {raw!r}")


def _parse_float_list(value: str) -> list[float]:
    """
    Parse a comma or semicolon-separated list of floats.

    Suitable for use as an argparse type handler.

    Args:
        value: String like "24.0,48.0,72.0" or "24.0;48.0;72.0"

    Returns:
        List of float values

    Raises:
        argparse.ArgumentTypeError: If any element cannot be parsed as float
    """
    try:
        return [float(item) for item in value.replace(";", ",").split(",") if item.strip()]
    except ValueError as exc:  # pragma: no cover - guarded by argparse
        raise argparse.ArgumentTypeError(f"Invalid float list: {value}") from exc


# ─── Override Values Container ────────────────────────────────────────────────

@dataclass
class _OverrideValues:
    """
    Container for merged CLI/environment configuration overrides.

    Holds all configuration values that can be specified via CLI arguments
    or environment variables, for a single optimization run.
    """
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


# ─── Run Mode Normalization ────────────────────────────────────────────────────

_RUN_MODE_ALIASES = {
    "PF": "PF_ONLY",
    "PF_ONLY": "PF_ONLY",
    "PF_THEN_RH": "PF_THEN_RH",
    "PF_AND_RH": "PF_THEN_RH",
    "RH": "RH_ONLY",
    "RH_ONLY": "RH_ONLY",
    "MPC": "MPC_ONLY",
    "MPC_ONLY": "MPC_ONLY",
    "PF_THEN_MPC": "PF_THEN_MPC",
}


def _normalise_run_mode(value: str | None) -> str | None:
    """
    Normalize a run mode string to a canonical value.

    Args:
        value: Run mode string (e.g. 'PF', 'RH', 'PF_THEN_RH')

    Returns:
        Canonical run mode string or None if input is None/empty
    """
    if not value:
        return None
    normalised = _RUN_MODE_ALIASES.get(value.upper())
    return normalised


def _parse_run_mode(value: str) -> str:
    """
    Parse and validate a run mode string (for use as argparse type handler).

    Args:
        value: Run mode string to validate

    Returns:
        Canonical run mode string

    Raises:
        argparse.ArgumentTypeError: If value is not a recognized run mode
    """
    normalised = _normalise_run_mode(value)
    if normalised is None:
        raise argparse.ArgumentTypeError(
            f"Unknown run mode {value!r}. Valid options: {list(_RUN_MODE_ALIASES.keys())}"
        )
    return normalised


# ─── Environment Override Collection ──────────────────────────────────────────

def _gather_env_overrides() -> _OverrideValues:
    """
    Collect all environment variable configuration overrides.

    Reads all recognized ENERGIS_* / HEAT_* environment variables and
    returns them as an _OverrideValues instance.

    Returns:
        _OverrideValues with all environment-specified overrides (None for unset vars)
    """
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

# =============================================================================
# OPTIMIZATION CONFIGURATION MODULE
# =============================================================================
# Handles the separation of VARIABLES (optimized) vs PARAMETERS (fixed)
# based on scenario configuration.
#
# Key concepts:
#   - Variables: Values determined by the optimizer (capacities, build decisions)
#   - Parameters: Fixed values from config (used when not optimizing)
#   - fix_after_window: For RH, converts variables to parameters after Window N
# =============================================================================

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class OptimizationVariables:
    """Defines which values are optimization variables vs fixed parameters."""
    # Heat pump settings
    hp_capacity: bool = True      # Optimize HP capacities
    hp_build: bool = True         # Optimize HP build decisions
    # Storage settings
    storage_capacity: bool = True # Optimize storage energy capacity
    storage_power: bool = True    # Optimize storage power capacity
    storage_build: bool = True    # Optimize storage build decision


@dataclass
class FixedValues:
    """Fixed values for components when not optimizing."""
    heat_pumps: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    storage: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationConfig:
    """Complete optimization configuration from scenario."""
    variables: OptimizationVariables
    fix_after_window: Optional[int] = None  # For RH: fix after this window
    fixed_values: Optional[FixedValues] = None
    save_result_to: Optional[str] = None


# =============================================================================
# LOADING OPTIMIZATION CONFIG
# =============================================================================

def load_optimization_config(scenario_cfg: Mapping[str, Any]) -> OptimizationConfig:
    """Load optimization configuration from scenario config.

    Reads the 'optimization' section and determines:
    - Which values are variables (optimized)
    - Which values are parameters (fixed)
    - When to fix variables in RH (fix_after_window)
    - Fixed values to use when not optimizing
    """
    opt_cfg = scenario_cfg.get("optimization", {})

    if not opt_cfg:
        # Legacy support: check for old design/fix_design config
        if scenario_cfg.get("fix_design", False):
            logger.info("[OPT] Legacy fix_design=true detected, using optimize mode")
            return OptimizationConfig(
                variables=OptimizationVariables(),  # All true by default
                fix_after_window=0,
            )
        # Default: optimize everything, no fixing
        return OptimizationConfig(variables=OptimizationVariables())

    # Parse variables section
    var_cfg = opt_cfg.get("variables", {})
    hp_vars = var_cfg.get("heat_pumps", {})
    storage_vars = var_cfg.get("storage", {})

    variables = OptimizationVariables(
        hp_capacity=bool(hp_vars.get("capacity", True)),
        hp_build=bool(hp_vars.get("build", True)),
        storage_capacity=bool(storage_vars.get("capacity", True)),
        storage_power=bool(storage_vars.get("power", True)),
        storage_build=bool(storage_vars.get("build", True)),
    )

    # Parse fix_after_window
    fix_after = opt_cfg.get("fix_after_window")
    if fix_after is not None:
        fix_after = int(fix_after)

    # Parse fixed_values
    fixed_values = None
    fixed_cfg = opt_cfg.get("fixed_values", {})
    if fixed_cfg:
        fixed_values = FixedValues(
            heat_pumps=dict(fixed_cfg.get("heat_pumps", {})),
            storage=dict(fixed_cfg.get("storage", {})),
        )

    # Parse save_result_to
    save_to = opt_cfg.get("save_result_to")

    return OptimizationConfig(
        variables=variables,
        fix_after_window=fix_after,
        fixed_values=fixed_values,
        save_result_to=save_to,
    )


# =============================================================================
# APPLYING OPTIMIZATION CONFIG TO SYSTEM
# =============================================================================

def apply_optimization_config(
    cfg: Dict[str, Any],
    opt_config: OptimizationConfig,
    window_idx: int = 0,
    extracted_values: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply optimization configuration to system config.

    This function modifies the config to:
    1. Enable/disable investment optimization based on variables settings
    2. Apply fixed_values if specified
    3. Apply extracted_values from previous windows (for RH fix_after_window)

    Parameters
    ----------
    cfg : Dict[str, Any]
        The full merged configuration
    opt_config : OptimizationConfig
        Optimization settings from scenario
    window_idx : int
        Current RH window index (0 for PF)
    extracted_values : Optional[Dict[str, Any]]
        Values extracted from Window 0 optimization (for RH)

    Returns
    -------
    Dict[str, Any]
        Modified configuration
    """
    cfg_copy = copy.deepcopy(cfg)
    system = cfg_copy.setdefault("system", {})

    # Determine if we should use fixed values (based on fix_after_window)
    use_fixed = False
    if opt_config.fix_after_window is not None and window_idx > opt_config.fix_after_window:
        use_fixed = True
        logger.debug("[OPT] Window %d > fix_after_window %d, using fixed values",
                    window_idx, opt_config.fix_after_window)

    # Determine source of fixed values
    fixed_source = None
    if use_fixed and extracted_values:
        fixed_source = extracted_values
        logger.debug("[OPT] Using extracted values from Window 0")
    elif opt_config.fixed_values:
        fixed_source = {
            "heat_pumps": opt_config.fixed_values.heat_pumps,
            "storage": opt_config.fixed_values.storage,
        }
        logger.debug("[OPT] Using fixed_values from config")

    # Apply to heat pumps
    heat_pumps = system.get("heat_pumps", [])
    if isinstance(heat_pumps, list):
        for hp_cfg in heat_pumps:
            if not isinstance(hp_cfg, dict):
                continue
            hp_id = str(hp_cfg.get("id", ""))

            # Get fixed values for this HP if available
            hp_fixed = {}
            if fixed_source and "heat_pumps" in fixed_source:
                hp_fixed = fixed_source["heat_pumps"].get(hp_id, {})

            # Determine if capacity/build should be optimized
            optimize_capacity = opt_config.variables.hp_capacity and not use_fixed
            optimize_build = opt_config.variables.hp_build and not use_fixed

            # Build investment config
            invest_cfg = hp_cfg.setdefault("investment", {})
            if isinstance(invest_cfg, dict):
                invest_cfg["enabled"] = optimize_capacity or optimize_build

                if not optimize_capacity:
                    # Use fixed capacity
                    capacity = hp_fixed.get("capacity_mw")
                    if capacity is None:
                        # Fall back to defaults from system config
                        defaults = hp_cfg.get("defaults", {})
                        capacity = defaults.get("capacity_mw", 50.0)

                    invest_cfg["capacity_min_mw"] = capacity
                    invest_cfg["capacity_max_mw"] = capacity
                    invest_cfg["initial_capacity_mw"] = capacity
                    hp_cfg["max_th_mw"] = capacity
                    hp_cfg["min_th_mw"] = capacity

                if not optimize_build:
                    build = hp_fixed.get("build")
                    if build is None:
                        defaults = hp_cfg.get("defaults", {})
                        build = defaults.get("build", True)

                    if not build:
                        hp_cfg["enabled"] = False

    # Apply to storage
    storage_cfg = system.get("storage")
    if isinstance(storage_cfg, dict) and storage_cfg.get("enabled", False):
        # Get fixed values for storage if available
        storage_fixed = {}
        if fixed_source and "storage" in fixed_source:
            storage_fixed = fixed_source["storage"]

        # Determine if capacity/power/build should be optimized
        optimize_capacity = opt_config.variables.storage_capacity and not use_fixed
        optimize_power = opt_config.variables.storage_power and not use_fixed
        optimize_build = opt_config.variables.storage_build and not use_fixed

        # Build investment config
        invest_cfg = storage_cfg.setdefault("investment", {})
        if isinstance(invest_cfg, dict):
            invest_cfg["enabled"] = optimize_capacity or optimize_power or optimize_build

            if not optimize_capacity:
                capacity = storage_fixed.get("energy_mwh")
                if capacity is None:
                    defaults = storage_cfg.get("defaults", {})
                    capacity = defaults.get("energy_mwh", 500.0)

                invest_cfg["energy_capacity_min_mwh"] = capacity
                invest_cfg["energy_capacity_max_mwh"] = capacity
                invest_cfg["initial_energy_capacity_mwh"] = capacity
                storage_cfg["max_energy_mwh"] = capacity
                storage_cfg["energy_mwh"] = capacity

            if not optimize_power:
                power = storage_fixed.get("power_mw")
                if power is None:
                    defaults = storage_cfg.get("defaults", {})
                    power = defaults.get("power_mw", 50.0)

                invest_cfg["power_capacity_min_mw"] = power
                invest_cfg["power_capacity_max_mw"] = power
                invest_cfg["initial_power_capacity_mw"] = power
                storage_cfg["max_power_mw"] = power
                storage_cfg["power_mw"] = power

            if not optimize_build:
                build = storage_fixed.get("build")
                if build is None:
                    defaults = storage_cfg.get("defaults", {})
                    build = defaults.get("build", True)

                if not build:
                    storage_cfg["enabled"] = False

    return cfg_copy


# =============================================================================
# EXTRACTING OPTIMIZATION RESULTS
# =============================================================================

def extract_optimization_results(summary: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """Extract optimized values from window result summary.

    Used after Window 0 in RH to get the optimized capacities for fixing.
    """
    results: Dict[str, Any] = {
        "heat_pumps": {},
        "storage": {},
    }

    for key, metrics in summary.items():
        if key.startswith("heat_pump_"):
            hp_id = key.split("heat_pump_", 1)[1]
            capacity = float(metrics.get("Thermal_capacity_MW", 0.0))
            build = float(metrics.get("Build_binary", metrics.get("Build", 0.0)))

            results["heat_pumps"][hp_id] = {
                "capacity_mw": capacity,
                "build": build >= 0.5,
            }
            logger.debug("[OPT] Extracted HP %s: capacity=%.1f MW, build=%s",
                        hp_id, capacity, build >= 0.5)

        elif key.startswith("storage_"):
            capacity = float(metrics.get("Capacity_MWh", 0.0))
            power = float(metrics.get("Power_limit_MW", 0.0))
            build = float(metrics.get("Build_binary", metrics.get("Build", 0.0)))

            results["storage"] = {
                "energy_mwh": capacity,
                "power_mw": power,
                "build": build >= 0.5,
            }
            logger.debug("[OPT] Extracted Storage: capacity=%.1f MWh, power=%.1f MW, build=%s",
                        capacity, power, build >= 0.5)

    return results


# =============================================================================
# SAVING OPTIMIZATION RESULTS
# =============================================================================

def save_optimization_results(results: Dict[str, Any], path: str | Path) -> Path:
    """Save optimization results to a YAML file for reuse.

    The saved file can be used as fixed_values in another scenario.
    """
    save_path = Path(path).expanduser()
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Format for YAML output
    output = {
        "# Optimization results": f"Generated on {datetime.now().isoformat()}",
        "optimization": {
            "variables": {
                "heat_pumps": {"capacity": False, "build": False},
                "storage": {"capacity": False, "power": False, "build": False},
            },
            "fixed_values": results,
        }
    }

    # Write as YAML
    import yaml
    with open(save_path, "w", encoding="utf-8") as f:
        yaml.dump(output, f, default_flow_style=False, allow_unicode=True)

    logger.info("[OPT] Saved optimization results to %s", save_path)
    return save_path


# =============================================================================
# LEGACY SUPPORT - DesignSpec (for backward compatibility)
# =============================================================================

@dataclass
class HeatPumpDesign:
    """Design specification for a single heat pump."""
    id: str
    capacity_mw: float
    enabled: bool = True
    build_binary: float = 1.0


@dataclass
class StorageDesign:
    """Design specification for thermal storage."""
    capacity_mwh: float
    power_mw: float
    enabled: bool = True
    build_binary: float = 1.0


@dataclass
class DesignSpec:
    """Complete design specification (legacy support)."""
    heat_pumps: Dict[str, HeatPumpDesign] = field(default_factory=dict)
    storage: Optional[StorageDesign] = None


def convert_to_design_spec(results: Dict[str, Any]) -> DesignSpec:
    """Convert optimization results to legacy DesignSpec format."""
    heat_pumps = {}
    for hp_id, hp_data in results.get("heat_pumps", {}).items():
        heat_pumps[hp_id] = HeatPumpDesign(
            id=hp_id,
            capacity_mw=hp_data.get("capacity_mw", 0.0),
            enabled=hp_data.get("build", False),
            build_binary=1.0 if hp_data.get("build", False) else 0.0,
        )

    storage = None
    storage_data = results.get("storage", {})
    if storage_data:
        storage = StorageDesign(
            capacity_mwh=storage_data.get("energy_mwh", 0.0),
            power_mw=storage_data.get("power_mw", 0.0),
            enabled=storage_data.get("build", False),
            build_binary=1.0 if storage_data.get("build", False) else 0.0,
        )

    return DesignSpec(heat_pumps=heat_pumps, storage=storage)


# =============================================================================
# BACKWARD COMPATIBILITY - Old API aliases
# =============================================================================
# These aliases maintain compatibility with rolling_horizon.py and other code
# that was written against the old design module API.

@dataclass
class DesignConfig:
    """DEPRECATED: Use OptimizationConfig instead.

    Legacy design configuration wrapper. Maps to new OptimizationConfig.
    """
    mode: str = "none"  # "none", "file", "inline", "optimize"
    apply_from_window: int = 1
    save_to: Optional[str] = None
    file_path: Optional[str] = None
    inline_spec: Optional[DesignSpec] = None


def load_design_config(scenario_cfg: Mapping[str, Any]) -> DesignConfig:
    """DEPRECATED: Use load_optimization_config instead.

    Load design configuration from scenario config (legacy support).
    Maps the old 'design' section to the new format.
    """
    # Check for new 'optimization' section first
    opt_cfg = scenario_cfg.get("optimization", {})
    if opt_cfg:
        # Map new format to legacy DesignConfig
        variables = opt_cfg.get("variables", {})
        fix_after = opt_cfg.get("fix_after_window")

        # Determine mode based on variables settings
        all_vars_true = (
            variables.get("heat_pumps", {}).get("capacity", True) and
            variables.get("heat_pumps", {}).get("build", True) and
            variables.get("storage", {}).get("capacity", True) and
            variables.get("storage", {}).get("power", True) and
            variables.get("storage", {}).get("build", True)
        )

        if opt_cfg.get("fixed_values"):
            mode = "inline"
        elif fix_after is not None:
            mode = "optimize"
        elif not all_vars_true:
            mode = "inline"  # Has fixed values from defaults
        else:
            mode = "none"  # Full optimization

        return DesignConfig(
            mode=mode,
            apply_from_window=fix_after + 1 if fix_after is not None else 1,
            save_to=opt_cfg.get("save_result_to"),
        )

    # Check for old 'design' section
    design_cfg = scenario_cfg.get("design", {})
    if not design_cfg:
        # Check legacy fix_design flag
        if scenario_cfg.get("fix_design", False):
            return DesignConfig(mode="optimize", apply_from_window=1)
        return DesignConfig(mode="none")

    mode = str(design_cfg.get("mode", "none")).lower()
    apply_from = int(design_cfg.get("apply_from_window", 1))
    save_to = design_cfg.get("save_to")
    file_path = design_cfg.get("file")

    return DesignConfig(
        mode=mode,
        apply_from_window=apply_from,
        save_to=save_to,
        file_path=file_path,
    )


def load_design_for_scenario(
    design_config: DesignConfig,
    base_path: Optional[Path] = None,
) -> Optional[DesignSpec]:
    """DEPRECATED: Use load_optimization_config + apply_optimization_config instead.

    Load design specification based on design config mode.
    """
    if design_config.mode == "none":
        return None

    if design_config.mode == "inline" and design_config.inline_spec:
        return design_config.inline_spec

    if design_config.mode == "file" and design_config.file_path:
        # Load from JSON file
        file_path = Path(design_config.file_path)
        if base_path and not file_path.is_absolute():
            file_path = base_path / file_path

        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _parse_design_spec(data)

    return None


def _parse_design_spec(data: Dict[str, Any]) -> DesignSpec:
    """Parse design specification from dictionary."""
    heat_pumps = {}
    for hp_id, hp_data in data.get("heat_pumps", {}).items():
        heat_pumps[hp_id] = HeatPumpDesign(
            id=hp_id,
            capacity_mw=float(hp_data.get("capacity_mw", 0.0)),
            enabled=bool(hp_data.get("enabled", hp_data.get("build", True))),
            build_binary=float(hp_data.get("build_binary", 1.0 if hp_data.get("build", True) else 0.0)),
        )

    storage = None
    storage_data = data.get("storage", {})
    if storage_data:
        storage = StorageDesign(
            capacity_mwh=float(storage_data.get("capacity_mwh", storage_data.get("energy_mwh", 0.0))),
            power_mw=float(storage_data.get("power_mw", 0.0)),
            enabled=bool(storage_data.get("enabled", storage_data.get("build", True))),
            build_binary=float(storage_data.get("build_binary", 1.0 if storage_data.get("build", True) else 0.0)),
        )

    return DesignSpec(heat_pumps=heat_pumps, storage=storage)


def extract_design_from_summary(summary: Mapping[str, Mapping[str, Any]]) -> DesignSpec:
    """DEPRECATED: Use extract_optimization_results instead.

    Extract design specification from optimization summary.
    """
    results = extract_optimization_results(summary)
    return convert_to_design_spec(results)


def apply_design_to_config(cfg: Dict[str, Any], design: DesignSpec) -> Dict[str, Any]:
    """DEPRECATED: Use apply_optimization_config instead.

    Apply design specification to configuration.
    """
    cfg_copy = copy.deepcopy(cfg)
    system = cfg_copy.setdefault("system", {})

    # Apply to heat pumps
    heat_pumps = system.get("heat_pumps", [])
    if isinstance(heat_pumps, list):
        for hp_cfg in heat_pumps:
            if not isinstance(hp_cfg, dict):
                continue
            hp_id = str(hp_cfg.get("id", ""))
            if hp_id not in design.heat_pumps:
                continue

            hp_design = design.heat_pumps[hp_id]
            capacity = hp_design.capacity_mw

            invest_cfg = hp_cfg.setdefault("investment", {})
            if isinstance(invest_cfg, dict):
                invest_cfg["enabled"] = False
                invest_cfg["capacity_min_mw"] = capacity
                invest_cfg["capacity_max_mw"] = capacity
                invest_cfg["initial_capacity_mw"] = capacity

            hp_cfg["max_th_mw"] = capacity
            hp_cfg["min_th_mw"] = capacity

            if not hp_design.enabled or hp_design.build_binary < 0.5:
                hp_cfg["enabled"] = False

    # Apply to storage
    storage_cfg = system.get("storage")
    if isinstance(storage_cfg, dict) and design.storage:
        actual_capacity = design.storage.capacity_mwh
        actual_power = design.storage.power_mw

        # Safety check: if power is 0 but capacity is not, use a reasonable default
        if actual_power <= 0 and actual_capacity > 0:
            actual_power = max(actual_capacity / 50.0, 10.0)
            logger.warning("[DESIGN] power was 0, using fallback: %.1f MW", actual_power)

        storage_cfg["enabled"] = design.storage.enabled and design.storage.build_binary >= 0.5
        storage_cfg["max_energy_mwh"] = actual_capacity
        storage_cfg["max_power_mw"] = actual_power

        invest_cfg = storage_cfg.setdefault("investment", {})
        if isinstance(invest_cfg, dict):
            invest_cfg["enabled"] = False
            invest_cfg["energy_capacity_min_mwh"] = actual_capacity
            invest_cfg["energy_capacity_max_mwh"] = actual_capacity
            invest_cfg["initial_energy_capacity_mwh"] = actual_capacity
            invest_cfg["power_capacity_min_mw"] = actual_power
            invest_cfg["power_capacity_max_mw"] = actual_power
            invest_cfg["initial_power_capacity_mw"] = actual_power

    return cfg_copy


def save_design_to_file(design: DesignSpec, path: str | Path) -> Path:
    """DEPRECATED: Use save_optimization_results instead.

    Save design specification to JSON file.
    """
    save_path = Path(path).expanduser()
    save_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "heat_pumps": {},
        "storage": None,
    }

    for hp_id, hp_design in design.heat_pumps.items():
        output["heat_pumps"][hp_id] = {
            "capacity_mw": hp_design.capacity_mw,
            "enabled": hp_design.enabled,
            "build_binary": hp_design.build_binary,
        }

    if design.storage:
        output["storage"] = {
            "capacity_mwh": design.storage.capacity_mwh,
            "power_mw": design.storage.power_mw,
            "enabled": design.storage.enabled,
            "build_binary": design.storage.build_binary,
        }

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    logger.info("[DESIGN] Saved design to %s", save_path)
    return save_path


def validate_design(design: DesignSpec) -> List[str]:
    """DEPRECATED: Validate design specification.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    if design.storage:
        if design.storage.capacity_mwh <= 0 and design.storage.enabled:
            errors.append("Storage capacity must be positive when enabled")
        if design.storage.power_mw <= 0 and design.storage.enabled:
            errors.append("Storage power must be positive when enabled")

    for hp_id, hp_design in design.heat_pumps.items():
        if hp_design.capacity_mw <= 0 and hp_design.enabled:
            errors.append(f"Heat pump {hp_id} capacity must be positive when enabled")

    return errors

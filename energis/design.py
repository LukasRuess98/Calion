# =============================================================================
# DESIGN MANAGEMENT MODULE
# =============================================================================
# Centralized design specification, loading, saving, and validation.
#
# Design modes:
#   - "file": Load design from JSON file
#   - "optimize": Optimize in Window 0, then fix for subsequent windows
#   - "inline": Define design values directly in scenario config
#   - "none": No design fixation (all windows optimize independently)
# =============================================================================

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class HeatPumpDesign:
    """Design specification for a single heat pump."""
    id: str
    capacity_mw: float
    enabled: bool = True
    build_binary: float = 1.0

    def __post_init__(self):
        if self.capacity_mw <= 0:
            self.enabled = False
            self.build_binary = 0.0


@dataclass
class StorageDesign:
    """Design specification for thermal storage."""
    capacity_mwh: float
    power_mw: float
    enabled: bool = True
    build_binary: float = 1.0

    def __post_init__(self):
        if self.capacity_mwh <= 0 or self.power_mw <= 0:
            self.enabled = False
            self.build_binary = 0.0


@dataclass
class GeneratorDesign:
    """Design specification for a generator (usually fixed/brownfield)."""
    id: str
    enabled: bool = True
    capacity_mw: Optional[float] = None


@dataclass
class DesignSpec:
    """Complete design specification for a system."""
    heat_pumps: Dict[str, HeatPumpDesign] = field(default_factory=dict)
    storage: Optional[StorageDesign] = None
    generators: Dict[str, GeneratorDesign] = field(default_factory=dict)

    # Metadata
    version: str = "1.0"
    created: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "version": self.version,
            "created": self.created or datetime.now().isoformat(),
            "source": self.source,
            "description": self.description,
            "heat_pumps": {
                hp_id: {
                    "capacity_mw": hp.capacity_mw,
                    "enabled": hp.enabled,
                    "build_binary": hp.build_binary,
                }
                for hp_id, hp in self.heat_pumps.items()
            },
        }

        if self.storage:
            result["storage"] = {
                "capacity_mwh": self.storage.capacity_mwh,
                "power_mw": self.storage.power_mw,
                "enabled": self.storage.enabled,
                "build_binary": self.storage.build_binary,
            }

        if self.generators:
            result["generators"] = {
                gen_id: {
                    "enabled": gen.enabled,
                    "capacity_mw": gen.capacity_mw,
                }
                for gen_id, gen in self.generators.items()
            }

        return result


# =============================================================================
# VALIDATION
# =============================================================================

def validate_design(design: DesignSpec) -> List[str]:
    """Validate a design specification and return list of errors."""
    errors: List[str] = []

    # Validate heat pumps
    for hp_id, hp in design.heat_pumps.items():
        if hp.enabled and hp.capacity_mw <= 0:
            errors.append(f"Heat pump {hp_id}: enabled but capacity_mw <= 0")
        if hp.capacity_mw < 0:
            errors.append(f"Heat pump {hp_id}: capacity_mw cannot be negative")

    # Validate storage
    if design.storage:
        if design.storage.enabled:
            if design.storage.capacity_mwh <= 0:
                errors.append("Storage: enabled but capacity_mwh <= 0")
            if design.storage.power_mw <= 0:
                errors.append("Storage: enabled but power_mw <= 0")
        if design.storage.capacity_mwh < 0:
            errors.append("Storage: capacity_mwh cannot be negative")
        if design.storage.power_mw < 0:
            errors.append("Storage: power_mw cannot be negative")

    return errors


# =============================================================================
# LOADING
# =============================================================================

def load_design_from_file(path: str | Path) -> DesignSpec:
    """Load design from JSON file."""
    design_path = Path(path).expanduser()

    if not design_path.exists():
        raise FileNotFoundError(f"Design file not found: {design_path}")

    with open(design_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return _parse_design_dict(data, source=f"file:{design_path}")


def load_design_from_config(inline_config: Mapping[str, Any]) -> DesignSpec:
    """Load design from inline config in scenario YAML."""
    return _parse_design_dict(dict(inline_config), source="inline")


def _parse_design_dict(data: Dict[str, Any], source: str = "unknown") -> DesignSpec:
    """Parse design dictionary into DesignSpec."""
    heat_pumps: Dict[str, HeatPumpDesign] = {}
    storage: Optional[StorageDesign] = None
    generators: Dict[str, GeneratorDesign] = {}

    # Parse heat pumps
    hp_data = data.get("heat_pumps", {})
    if isinstance(hp_data, dict):
        for hp_id, hp_cfg in hp_data.items():
            if isinstance(hp_cfg, dict):
                heat_pumps[hp_id] = HeatPumpDesign(
                    id=hp_id,
                    capacity_mw=float(hp_cfg.get("capacity_mw", 0.0)),
                    enabled=bool(hp_cfg.get("enabled", True)),
                    build_binary=float(hp_cfg.get("build_binary", 1.0 if hp_cfg.get("enabled", True) else 0.0)),
                )

    # Parse storage
    storage_data = data.get("storage")
    if isinstance(storage_data, dict):
        storage = StorageDesign(
            capacity_mwh=float(storage_data.get("capacity_mwh", 0.0)),
            power_mw=float(storage_data.get("power_mw", 0.0)),
            enabled=bool(storage_data.get("enabled", True)),
            build_binary=float(storage_data.get("build_binary", 1.0 if storage_data.get("enabled", True) else 0.0)),
        )

    # Parse generators
    gen_data = data.get("generators", {})
    if isinstance(gen_data, dict):
        for gen_id, gen_cfg in gen_data.items():
            if isinstance(gen_cfg, dict):
                generators[gen_id] = GeneratorDesign(
                    id=gen_id,
                    enabled=bool(gen_cfg.get("enabled", True)),
                    capacity_mw=float(gen_cfg["capacity_mw"]) if "capacity_mw" in gen_cfg else None,
                )

    return DesignSpec(
        heat_pumps=heat_pumps,
        storage=storage,
        generators=generators,
        version=str(data.get("version", "1.0")),
        created=data.get("created"),
        source=source,
        description=data.get("description"),
    )


# =============================================================================
# SAVING
# =============================================================================

def save_design_to_file(design: DesignSpec, path: str | Path) -> Path:
    """Save design to JSON file."""
    design_path = Path(path).expanduser()
    design_path.parent.mkdir(parents=True, exist_ok=True)

    # Update metadata
    design.created = datetime.now().isoformat()

    with open(design_path, "w", encoding="utf-8") as f:
        json.dump(design.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info("Design saved to %s", design_path)
    return design_path


# =============================================================================
# EXTRACTION FROM OPTIMIZATION RESULTS
# =============================================================================

def extract_design_from_summary(summary: Mapping[str, Mapping[str, Any]]) -> DesignSpec:
    """Extract design from optimization result summary."""
    heat_pumps: Dict[str, HeatPumpDesign] = {}
    storage: Optional[StorageDesign] = None

    for key, metrics in summary.items():
        if key.startswith("heat_pump_"):
            hp_id = key.split("heat_pump_", 1)[1]
            capacity = float(metrics.get("Thermal_capacity_MW", 0.0))
            build = float(metrics.get("Build_binary", metrics.get("Build", 0.0)))

            heat_pumps[hp_id] = HeatPumpDesign(
                id=hp_id,
                capacity_mw=capacity,
                enabled=build >= 0.5,
                build_binary=build,
            )
            logger.debug("Extracted HP %s: capacity=%.1f MW, build=%.1f", hp_id, capacity, build)

        elif key.startswith("storage_"):
            capacity_mwh = float(metrics.get("Capacity_MWh", 0.0))
            power_mw = float(metrics.get("Power_limit_MW", 0.0))
            build = float(metrics.get("Build_binary", metrics.get("Build", 0.0)))

            storage = StorageDesign(
                capacity_mwh=capacity_mwh,
                power_mw=power_mw,
                enabled=build >= 0.5,
                build_binary=build,
            )
            logger.debug("Extracted Storage: capacity=%.1f MWh, power=%.1f MW, build=%.1f",
                        capacity_mwh, power_mw, build)

    return DesignSpec(
        heat_pumps=heat_pumps,
        storage=storage,
        source="optimization",
    )


# =============================================================================
# DESIGN MODE HANDLING
# =============================================================================

@dataclass
class DesignConfig:
    """Configuration for design handling in a scenario."""
    mode: str  # "file", "optimize", "inline", "none"
    file_path: Optional[str] = None
    inline_spec: Optional[Dict[str, Any]] = None
    save_to: Optional[str] = None
    apply_from_window: int = 1  # For "optimize" mode: apply from which window


def load_design_config(scenario_cfg: Mapping[str, Any]) -> DesignConfig:
    """Load design configuration from scenario config."""
    design_cfg = scenario_cfg.get("design", {})

    if not design_cfg:
        # Legacy support: check for fix_design flag
        if scenario_cfg.get("fix_design", False):
            return DesignConfig(mode="optimize", apply_from_window=1)
        return DesignConfig(mode="none")

    mode = str(design_cfg.get("mode", "none")).lower()

    return DesignConfig(
        mode=mode,
        file_path=design_cfg.get("file"),
        inline_spec=design_cfg.get("inline"),
        save_to=design_cfg.get("save_to"),
        apply_from_window=int(design_cfg.get("apply_from_window", 1)),
    )


def load_design_for_scenario(
    design_config: DesignConfig,
    base_path: Optional[Path] = None,
) -> Optional[DesignSpec]:
    """Load design based on configuration mode.

    Returns None for "optimize" or "none" modes (design will be determined later).
    """
    if design_config.mode == "none":
        logger.info("[DESIGN] Mode: none - no design fixation")
        return None

    if design_config.mode == "optimize":
        logger.info("[DESIGN] Mode: optimize - will extract design from Window 0")
        return None

    if design_config.mode == "file":
        if not design_config.file_path:
            raise ValueError("Design mode 'file' requires 'file' path")

        # Resolve path relative to base_path if provided
        file_path = Path(design_config.file_path)
        if base_path and not file_path.is_absolute():
            file_path = base_path / file_path

        logger.info("[DESIGN] Mode: file - loading from %s", file_path)
        design = load_design_from_file(file_path)

        # Validate
        errors = validate_design(design)
        if errors:
            raise ValueError(f"Design validation failed: {'; '.join(errors)}")

        return design

    if design_config.mode == "inline":
        if not design_config.inline_spec:
            raise ValueError("Design mode 'inline' requires 'inline' specification")

        logger.info("[DESIGN] Mode: inline - using values from config")
        design = load_design_from_config(design_config.inline_spec)

        # Validate
        errors = validate_design(design)
        if errors:
            raise ValueError(f"Design validation failed: {'; '.join(errors)}")

        return design

    raise ValueError(f"Unknown design mode: {design_config.mode}")


# =============================================================================
# APPLY DESIGN TO CONFIG
# =============================================================================

def apply_design_to_config(cfg: Dict[str, Any], design: DesignSpec) -> Dict[str, Any]:
    """Apply design specification to system configuration.

    Modifies config in-place to fix capacities according to design.
    """
    import copy
    cfg_copy = copy.deepcopy(cfg)
    system = cfg_copy.setdefault("system", {})

    # Apply heat pump designs
    heat_pumps = system.get("heat_pumps")
    if isinstance(heat_pumps, list):
        for hp_cfg in heat_pumps:
            if not isinstance(hp_cfg, dict):
                continue
            hp_id = str(hp_cfg.get("id"))
            if hp_id not in design.heat_pumps:
                continue

            hp_design = design.heat_pumps[hp_id]
            logger.debug("[DESIGN] Applying HP %s: capacity=%.1f MW, enabled=%s",
                        hp_id, hp_design.capacity_mw, hp_design.enabled)

            # Disable investment
            invest_cfg = hp_cfg.setdefault("investment", {})
            if isinstance(invest_cfg, dict):
                invest_cfg["enabled"] = False
                invest_cfg["capacity_min_mw"] = hp_design.capacity_mw
                invest_cfg["capacity_max_mw"] = hp_design.capacity_mw

            # Fix capacity
            hp_cfg["max_th_mw"] = hp_design.capacity_mw
            hp_cfg["min_th_mw"] = hp_design.capacity_mw

            # Enable/disable
            if not hp_design.enabled:
                hp_cfg["enabled"] = False

    # Apply storage design
    storage_cfg = system.get("storage") if isinstance(system.get("storage"), dict) else None
    if storage_cfg and design.storage:
        logger.debug("[DESIGN] Applying Storage: capacity=%.1f MWh, power=%.1f MW, enabled=%s",
                    design.storage.capacity_mwh, design.storage.power_mw, design.storage.enabled)

        storage_cfg["enabled"] = design.storage.enabled
        storage_cfg["max_energy_mwh"] = design.storage.capacity_mwh
        storage_cfg["max_power_mw"] = design.storage.power_mw

        # Disable investment and fix capacity
        invest_cfg = storage_cfg.setdefault("investment", {})
        if isinstance(invest_cfg, dict):
            invest_cfg["enabled"] = False
            invest_cfg["energy_capacity_min_mwh"] = design.storage.capacity_mwh
            invest_cfg["energy_capacity_max_mwh"] = design.storage.capacity_mwh
            invest_cfg["power_capacity_min_mw"] = design.storage.power_mw
            invest_cfg["power_capacity_max_mw"] = design.storage.power_mw
            invest_cfg["initial_energy_capacity_mwh"] = design.storage.capacity_mwh
            invest_cfg["initial_power_capacity_mw"] = design.storage.power_mw

    # Apply generator designs (if any)
    generators = system.get("generators", {})
    if isinstance(generators, dict):
        for gen_id, gen_design in design.generators.items():
            if gen_id in generators:
                generators[gen_id]["enabled"] = gen_design.enabled
                if gen_design.capacity_mw is not None:
                    generators[gen_id]["cap_th_mw"] = gen_design.capacity_mw

    return cfg_copy

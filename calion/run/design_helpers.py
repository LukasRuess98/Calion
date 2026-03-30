"""Design extraction, fixation and persistence helpers.

Functions that deal with extracting design decisions (capacities, build flags)
from optimisation results and applying them as fixed parameters in subsequent
RH/MPC windows.
"""

from __future__ import annotations

import copy
import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from calion.logging_config import get_logger

from .types import DesignData

logger = get_logger(__name__)


def _extract_design_data(summary: Mapping[str, Mapping[str, Any]]) -> DesignData:
    heat_pumps: Dict[str, Dict[str, float]] = {}
    storage: Optional[Dict[str, float]] = None

    for key, metrics in summary.items():
        if key.startswith("heat_pump_"):
            hp_id = key.split("heat_pump_", 1)[1]
            capacity = float(metrics.get("Thermal_capacity_MW", 0.0))
            build = float(metrics.get("Build_binary", metrics.get("Build", 0.0)))
            heat_pumps[hp_id] = {
                "capacity_mw": capacity,
                "build_binary": build,
            }
            logger.info(f"[DESIGN] Extracted HP {hp_id}: capacity={capacity:.1f} MW, build={build:.1f}")
        elif key.startswith("storage_"):
            storage = {
                "name": key.split("storage_", 1)[1],
                "capacity_mwh": float(metrics.get("Capacity_MWh", 0.0)),
                "power_mw": float(metrics.get("Power_limit_MW", 0.0)),
                "build_binary": float(metrics.get("Build_binary", metrics.get("Build", 0.0))),
            }
            logger.info(
                "[DESIGN] Extracted Storage: capacity=%.1f MWh, power=%.1f MW, build=%.1f",
                storage["capacity_mwh"], storage["power_mw"], storage["build_binary"],
            )

    return DesignData(heat_pumps=heat_pumps, storage=storage)


def _design_from_mapping(data: Mapping[str, Any]) -> DesignData:
    heat_pumps: Dict[str, Dict[str, float]] = {}
    raw_hps = data.get("heat_pumps")
    if isinstance(raw_hps, Mapping):
        for hp_id, entry in raw_hps.items():
            if not isinstance(entry, Mapping):
                continue
            heat_pumps[str(hp_id)] = {
                "capacity_mw": float(entry.get("capacity_mw", entry.get("Thermal_capacity_MW", 0.0)) or 0.0),
                "build_binary": float(
                    entry.get("build_binary", entry.get("Build", entry.get("Build_binary", 0.0))) or 0.0
                ),
            }

    storage_data = data.get("storage")
    storage: Dict[str, float] | None
    if isinstance(storage_data, Mapping):
        storage = {
            "name": str(storage_data.get("name", storage_data.get("id", "TES")) or "TES"),
            "capacity_mwh": float(
                storage_data.get("capacity_mwh", storage_data.get("Capacity_MWh", 0.0)) or 0.0
            ),
            "power_mw": float(
                storage_data.get("power_mw", storage_data.get("Power_limit_MW", 0.0)) or 0.0
            ),
            "build_binary": float(
                storage_data.get("build_binary", storage_data.get("Build", storage_data.get("Build_binary", 0.0)))
                or 0.0
            ),
        }
    else:
        storage = None

    return DesignData(heat_pumps=heat_pumps, storage=storage)


def _load_design_override(scenario_cfg: Mapping[str, Any]) -> DesignData | None:
    path = scenario_cfg.get("pf_design_json") or scenario_cfg.get("design_json")
    if not path:
        return None
    design_path = Path(str(path)).expanduser()
    if not design_path.exists():
        logger.warning("PF design file %s not found – continuing without design fixation.", design_path)
        return None
    try:
        with open(design_path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive branch
        logger.warning("Failed to load PF design file %s: %s", design_path, exc)
        return None
    if not isinstance(raw, Mapping):
        logger.warning("Design file %s does not contain a mapping – ignoring content.", design_path)
        return None
    return _design_from_mapping(raw)


def _apply_design_fix(cfg: Dict[str, Any], design: DesignData) -> Dict[str, Any]:
    """Apply design from PF to RH/MPC."""
    cfg_copy = copy.deepcopy(cfg)
    system = cfg_copy.setdefault("system", {})

    logger.info(f"[DESIGN_FIX] Brownfield generators: {list(system.get('generators', {}).keys())}")

    # Fix greenfield heat pump capacities
    heat_pumps = system.get("heat_pumps")
    if isinstance(heat_pumps, list):
        for hp_cfg in heat_pumps:
            if not isinstance(hp_cfg, dict):
                continue
            hp_id = str(hp_cfg.get("id"))
            if hp_id not in design.heat_pumps:
                continue

            design_entry = design.heat_pumps[hp_id]
            capacity = float(design_entry.get("capacity_mw", 0.0))
            build_binary = float(design_entry.get("build_binary", 0.0))

            invest_cfg = hp_cfg.setdefault("investment", {})
            if isinstance(invest_cfg, dict):
                invest_cfg["enabled"] = False
                invest_cfg["capacity_min_mw"] = capacity
                invest_cfg["capacity_max_mw"] = capacity
                invest_cfg["initial_capacity_mw"] = capacity

            hp_cfg["max_th_mw"] = capacity
            hp_cfg["min_th_mw"] = capacity

            if build_binary >= 0.5:
                hp_cfg["enabled"] = True
                logger.info(f"[DESIGN_FIX] ✓ HP {hp_id} ENABLED: {capacity:.1f} MW")
            else:
                hp_cfg["enabled"] = False
                logger.info(f"[DESIGN_FIX] ✗ HP {hp_id} DISABLED")

    # Fix storage
    storage_cfg = system.get("storage")
    if storage_cfg and design.storage:
        actual_capacity = float(design.storage.get("capacity_mwh", 0.0))
        actual_power = float(design.storage.get("power_mw", 0.0))
        build_binary = float(design.storage.get("build_binary", 0.0))

        if actual_power <= 0 and actual_capacity > 0:
            actual_power = actual_capacity * 0.25
            logger.info(f"[DESIGN_FIX] Storage power calculated: {actual_power:.1f} MW")

        if build_binary >= 0.5:
            storage_cfg["enabled"] = True
            logger.info(f"[DESIGN_FIX] ✓ Storage ENABLED: {actual_capacity:.1f} MWh / {actual_power:.1f} MW")
        else:
            storage_cfg["enabled"] = False

        storage_cfg["max_energy_mwh"] = actual_capacity
        storage_cfg["max_power_mw"] = actual_power

        # Force terminal to free
        terminal_cfg = storage_cfg.setdefault("terminal", {})
        terminal_cfg["state"] = "free"
        terminal_cfg["policy"] = "free"
        terminal_cfg.pop("target_mwh", None)
        terminal_cfg.pop("target", None)
        storage_cfg.pop("terminal_soc_mwh", None)
        storage_cfg["terminal_state"] = "free"
        logger.info(f"[DESIGN_FIX] Storage terminal → FREE")

        invest_cfg = storage_cfg.setdefault("investment", {})
        if isinstance(invest_cfg, dict):
            invest_cfg["enabled"] = False
            invest_cfg["energy_capacity_min_mwh"] = actual_capacity
            invest_cfg["energy_capacity_max_mwh"] = actual_capacity
            invest_cfg["power_capacity_min_mw"] = actual_power
            invest_cfg["power_capacity_max_mw"] = actual_power
            invest_cfg["initial_energy_capacity_mwh"] = actual_capacity
            invest_cfg["initial_power_capacity_mw"] = actual_power

    return cfg_copy

from __future__ import annotations

from typing import Any, List, Mapping

from energis.config.merge import deep_merge


def apply_heat_pump_defaults(system_cfg: Mapping[str, Any]) -> List[dict]:
    """Return heat pump configs with ``heat_pump_defaults`` applied.

    The helper preserves the original list order and leaves untouched entries
    that are not dictionaries.  Individual heat pump entries override any
    values defined in the shared defaults mapping.
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
        resolved.append(merged)
    return resolved

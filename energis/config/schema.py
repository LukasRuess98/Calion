from __future__ import annotations

from typing import Any


Number = (int, float)


def _require_number(value: Any, path: str) -> None:
    if value is None:
        return
    if not isinstance(value, Number):
        raise TypeError(f"Expected numeric value for {path}, got {type(value).__name__}.")
    if value < 0:
        raise ValueError(f"{path} must be non-negative, got {value}.")


def validate_config_schema(cfg: dict[str, Any]) -> None:
    """Light-weight schema validation for known config sections.

    The repository ships a minimal YAML loader without external dependencies,
    so this function performs essential type and range checks for keys that are
    consumed by the optimisation model.
    """

    grid = cfg.get("grid", {}) or {}
    for key in ("max_import_mw", "max_export_mw"):
        _require_number(grid.get(key), f"grid.{key}")

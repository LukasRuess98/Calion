"""
Pyomo model variable extraction utilities.

Contains pure functions for safely extracting time series data from
solved Pyomo optimization models, with robust error handling for
common Pyomo data issues (None values, non-finite, type errors).

Extracted from rolling_horizon.py to improve modularity and testability.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from calion.logging_config import get_logger

logger = get_logger(__name__)

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_PYOMO = False
    pyo = None


def _extract_pyomo_series(
    var: Any,
    times: Sequence[Any],
    name: str,
    tolerance: float = 1e-9
) -> list[float]:
    """
    Safely extract a time series from a Pyomo variable.

    Handles common failure modes:
    - Pyomo extraction errors → 0.0 with warning
    - None values → 0.0 with warning
    - Non-numeric values → 0.0 with warning
    - Non-finite values (NaN, Inf) → 0.0 with warning
    - Values below tolerance → clamped to 0.0 (numeric cleanup)

    Args:
        var: Pyomo variable indexed by time (e.g., model.HP1_Q)
        times: Sequence of time indices to extract
        name: Variable name for logging (used in warnings)
        tolerance: Values with abs(value) < tolerance are set to 0.0

    Returns:
        List of float values, one per time step in 'times'.
        Always returns the same number of elements as 'times'.
    """
    values: list[float] = []

    for t in times:
        try:
            raw = pyo.value(var[t])
        except Exception as exc:  # pragma: no cover - Pyomo specific failures
            logger.warning("Konnte Pyomo-Wert %s[%s] nicht auslesen: %s", name, t, exc)
            values.append(0.0)
            continue

        if raw is None:
            logger.warning("Pyomo-Wert %s[%s] ist None", name, t)
            values.append(0.0)
            continue

        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Pyomo-Wert %s[%s] kann nicht in float umgewandelt werden: %s", name, t, exc
            )
            values.append(0.0)
            continue

        if not math.isfinite(number):
            logger.warning("Pyomo-Wert %s[%s] ist nicht endlich (%s)", name, t, number)
            values.append(0.0)
            continue

        if abs(number) < tolerance:
            number = 0.0

        values.append(number)

    return values

"""
Time series manipulation utilities for the Rolling Horizon workflow.

Contains pure functions for:
- Slicing TimeSeriesTable to specific row indices
- Parsing date/time strings from multiple formats
- Filtering table to a configured time horizon

Extracted from rolling_horizon.py to improve modularity and testability.
"""
from __future__ import annotations

import re
import calendar
from datetime import datetime
from typing import Any, Dict, List

from calion.utils.timeseries import TimeSeriesTable
from calion.logging_config import get_logger

logger = get_logger(__name__)


def _slice_table(table: TimeSeriesTable, indices: List[int]) -> TimeSeriesTable:
    """
    Create a new TimeSeriesTable with only the rows at specified indices.

    Args:
        table: Source time series table
        indices: List of 0-based row indices to include

    Returns:
        New TimeSeriesTable with only the selected rows, preserving columns
    """
    new_index = [table.index[i] for i in indices]
    new_data = {col: [table[col][i] for i in indices] for col in table.columns}
    return TimeSeriesTable(new_index, table.columns[:], new_data)


def _parse_ts(value: Any) -> datetime:
    """
    Parse a datetime value from multiple format strings.

    Supports ISO 8601 format and common German date formats.

    Args:
        value: Value to parse (datetime object or string)

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If value cannot be parsed as a datetime
    """
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("Leerwert kann nicht als Datum interpretiert werden")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Kann Datum/Uhrzeit nicht interpretieren: {value!r}")


def _apply_horizon(
    table: TimeSeriesTable, scenario_cfg: Dict[str, Any], dt_h: float
) -> TimeSeriesTable:
    """
    Filter the time series table to match the configured time horizon.

    Supports two horizon types:
    - 'full_year': Filter to all rows in a specific calendar year
    - Date range: Filter to rows between start and end datetimes

    Args:
        table: Source time series table with datetime index
        scenario_cfg: Scenario configuration dict (should contain 'horizon' key)
        dt_h: Time step size in hours (used for frequency validation)

    Returns:
        Filtered TimeSeriesTable matching the configured horizon.
        Returns the original table unchanged if no horizon is configured.

    Raises:
        RuntimeError: If horizon configuration is invalid or produces empty result
    """
    from calion.constants import HOURS_PER_YEAR, HOURS_PER_LEAP_YEAR

    horizon = scenario_cfg.get("horizon")
    if not isinstance(horizon, dict):
        return table

    htype = str(horizon.get("type", "")).lower()
    if htype == "full_year":
        year = horizon.get("year")
        if year is None:
            if not table.index:
                raise RuntimeError("Zeitscheiben leer – kein Jahr auswählbar")
            year = table.index[0].year
        year = int(year)
        enforce = bool(horizon.get("enforce", True))
        indices = [i for i, ts in enumerate(table.index) if ts.year == year]
        if not indices:
            raise RuntimeError(f"Im Jahr {year} wurden keine Zeitschritte gefunden.")
        subset = _slice_table(table, indices)
        subset.ensure_frequency(dt_h)
        expected_hours = HOURS_PER_LEAP_YEAR if calendar.isleap(year) else HOURS_PER_YEAR
        actual_hours = len(subset) * dt_h
        diff = abs(actual_hours - expected_hours)
        if diff > 1e-6 and enforce:
            raise RuntimeError(
                f"Zeitraum deckt nicht das komplette Jahr {year} ab "
                f"(erwartet {expected_hours} Stunden, gefunden {actual_hours})."
            )
        if diff > 1e-6 and not enforce:
            logger.warning(
                "[SCENARIO] Hinweis: Daten decken nur %s von %s Stunden ab (enforce=false).",
                actual_hours, expected_hours
            )
        logger.info(
            "[SCENARIO] Volles Jahr %s: %s Schritte (%s → %s)",
            year, len(subset), subset.index[0], subset.index[-1]
        )
        return subset

    start = horizon.get("start")
    end = horizon.get("end")
    if start is None and end is None:
        return table

    start_dt = _parse_ts(start) if start is not None else None
    end_dt = _parse_ts(end) if end is not None else None
    if start_dt and end_dt and start_dt > end_dt:
        raise RuntimeError("Ungültiger Zeithorizont: Start liegt nach dem Ende")
    indices = []
    for i, ts in enumerate(table.index):
        if start_dt and ts < start_dt:
            continue
        if end_dt and ts > end_dt:
            continue
        indices.append(i)
    if not indices:
        raise RuntimeError("Zeithorizont enthält keine Zeitschritte")
    subset = _slice_table(table, indices)
    subset.ensure_frequency(dt_h)
    logger.info(
        "[SCENARIO] Zeitraum %s → %s (%s Schritte)",
        subset.index[0], subset.index[-1], len(subset)
    )
    return subset


def _hours_to_steps(hours: float, dt_h: float, name: str = "value") -> int:
    """
    Convert hours to simulation steps, validating exact divisibility.

    Args:
        hours: Number of hours to convert
        dt_h: Time step size in hours
        name: Parameter name for error messages

    Returns:
        Integer number of steps (at least 1)

    Raises:
        ValueError: If hours is not positive, or not an exact multiple of dt_h
    """
    import math
    if hours <= 0:
        raise ValueError(f"{name} must be positive")
    ratio = hours / dt_h
    rounded = round(ratio)
    if not math.isclose(ratio, rounded, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError(f"{name} must be a multiple of dt_h")
    return max(1, int(rounded))


def _slugify(value: str | None) -> str:
    """
    Convert an arbitrary string to a URL-safe slug for file naming.

    Args:
        value: String to slugify

    Returns:
        Slug string (lowercase, alphanumeric, hyphens only).
        Returns 'scenario' if input is empty/None.
    """
    if not value:
        return "scenario"
    slug = re.sub(r"[^0-9a-zA-Z_-]+", "-", value.strip())
    slug = re.sub(r"-+", "-", slug).strip("-_")
    return slug or "scenario"

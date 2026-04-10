"""COP (Coefficient of Performance) calculation for heat pumps.

This module provides functions for calculating heat pump COP time series using either:
1. 2D interpolation from lookup tables (preferred if configured)
2. Analytical calculation based on heat pump physics and thermodynamics

The analytical method uses log-mean temperature difference (LMTD) and efficiency factors
to compute realistic COP values based on source and sink temperatures.

Extracted from system_builder.py for better modularity and testability.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from calion.constants import (
    COP_DEFAULT,
    COP_DELTA_T_K,
    COP_MAX_SYSTEM_BUILDER,
    COP_MIN,
)
from calion.utils.timeseries import TimeSeriesTable


def calculate_cop_series(
    table: TimeSeriesTable,
    wrg_col: str | None,
    cfg: dict[str, Any],
    hp_type: str,
    sink_temp_series: list[float] | None = None,
) -> list[float]:
    """Calculate heat pump COP (Coefficient of Performance) time series.

    Computes COP values for each timestep using either:
    1. 2D interpolation from lookup tables (preferred if configured)
    2. Analytical calculation based on heat pump physics and thermodynamics

    The function supports waste heat recovery (WRG) integration and automatically
    clamps COP values to safe numerical ranges to prevent optimization issues.

    Args:
        table (TimeSeriesTable): Time series data with temperature/demand profiles
        wrg_col (str | None): Column name for waste heat recovery temperature data.
            If None or column missing, uses analytical fallback.
        cfg (Dict[str, Any]): Configuration with COP calculation parameters:
            - heat_pumps.cop.tables: Lookup table definitions
            - heat_pumps.cop.sink_defaults: Sink temperature settings
            - heat_pumps.types[hp_type]: Heat pump specific parameters
        hp_type (str): Heat pump type identifier (e.g., "default", "high_temp")
        sink_temp_series (list[float] | None): Optional pre-computed sink (supply)
            temperature series [K]. When provided, overrides the fixed Tsink_out_K
            from config for each timestep. Use to pass heating-curve-derived supply
            temperatures.

    Returns:
        List[float]: COP value for each timestep, clamped to [COP_MIN, COP_MAX_SYSTEM_BUILDER]

    Raises:
        ValueError: If COP table axes are invalid or interpolation fails
        KeyError: If required temperature data is missing

    Note:
        Falls back to analytical COP calculation if table-based method unavailable.
        Analytical method uses log-mean temperature difference (LMTD) and efficiency factors.
    """
    copcfg = cfg.get("heat_pumps", {}).get("cop", {})
    tables_cfg = copcfg.get("tables", {})
    table_spec = tables_cfg.get(hp_type) or tables_cfg.get("default")

    if table_spec:
        return _calculate_from_table(table, table_spec, copcfg, wrg_col,
                                     sink_temp_series=sink_temp_series)
    else:
        return _calculate_analytical(table, cfg, copcfg, hp_type, wrg_col,
                                     sink_temp_series=sink_temp_series)


def _calculate_from_table(
    table: TimeSeriesTable,
    table_spec: dict[str, Any],
    copcfg: dict[str, Any],
    wrg_col: str | None,
    sink_temp_series: list[float] | None = None,
) -> list[float]:
    """Calculate COP from lookup table with 2D interpolation."""
    # Validate and extract axes
    x_points = _validate_axis(
        table_spec.get("x") or table_spec.get("source_temperatures_K", []), "x"
    )
    y_points_raw: Sequence[float] | None = table_spec.get("y") or table_spec.get(
        "sink_temperatures_K"
    )
    has_y = bool(y_points_raw)
    y_points = _validate_axis(y_points_raw, "y") if has_y else None

    # Extract and validate values matrix
    values_raw = table_spec.get("values")
    if values_raw is None:
        raise ValueError("COP table requires a 'values' entry")

    if has_y:
        matrix = [[float(v) for v in row] for row in values_raw]
        if len(matrix) != len(y_points):
            raise ValueError("COP table: Number of rows does not match y-axis")
        for row in matrix:
            if len(row) != len(x_points):
                raise ValueError(
                    "COP table: Each row must have the same number of values as the x-axis"
                )
    else:
        vector = [float(v) for v in values_raw]
        if len(vector) != len(x_points):
            raise ValueError("COP table (1D): Number of values does not match x-axis")
        matrix = [vector]
        y_points = [0.0]
        has_y = False

    # Extract clamping and default settings
    clamp_default = bool(table_spec.get("clamp", True))
    clamp_x = bool(table_spec.get("clamp_x", clamp_default))
    clamp_y = bool(table_spec.get("clamp_y", clamp_default))

    sink_defaults = copcfg.get("sink_defaults", {})
    Ts_out = float(sink_defaults.get("Tsink_out_K", 363.15))

    # Get time series for x and y variables
    x_series = _series_from_column(
        table, table_spec.get("x_column") or wrg_col, table_spec.get("x_default")
    )
    y_column = table_spec.get("y_column")
    if sink_temp_series is not None:
        # sink_temp_series overrides column-based y_series
        if len(sink_temp_series) != len(table):
            raise ValueError(
                f"sink_temp_series length ({len(sink_temp_series)}) "
                f"must match table length ({len(table)})"
            )
        y_series = list(sink_temp_series)
        has_y = True
        if y_points is None:
            y_points = [float(v) for v in sink_temp_series]
    else:
        y_series = (
            _series_from_column(table, y_column, table_spec.get("y_default", Ts_out))
            if has_y
            else [0.0] * len(table)
        )

    cop_min = float(table_spec.get("cop_min", copcfg.get("cop_min", COP_MIN)))
    cop_max = float(
        table_spec.get("cop_max", copcfg.get("cop_max", COP_MAX_SYSTEM_BUILDER))
    )

    # Interpolate COP for each timestep
    result: list[float] = []
    for xv, yv in zip(x_series, y_series, strict=False):
        x_idx0, x_idx1, x_frac = _locate_interval(x_points, float(xv), clamp_x, "x")
        if has_y:
            y_idx0, y_idx1, y_frac = _locate_interval(y_points, float(yv), clamp_y, "y")
        else:
            y_idx0 = y_idx1 = 0
            y_frac = 0.0

        val = _interp2d(
            x_points,
            matrix,
            x_idx0,
            x_idx1,
            x_frac,
            y_idx0,
            y_idx1,
            y_frac,
        )
        if not math.isfinite(val):
            raise ValueError("COP table returned an invalid value")
        result.append(float(min(max(val, cop_min), cop_max)))

    return result


def _calculate_analytical(
    table: TimeSeriesTable,
    cfg: dict[str, Any],
    copcfg: dict[str, Any],
    hp_type: str,
    wrg_col: str | None,
    sink_temp_series: list[float] | None = None,
) -> list[float]:
    """Calculate COP using analytical heat pump model.

    Based on thermodynamic principles using log-mean temperature difference (LMTD).
    """
    dT = float(copcfg.get("deltaT_K", COP_DELTA_T_K))
    dTpp = float(copcfg.get("deltaTpp_K", 5.0))
    sink = copcfg.get("sink_defaults", {})
    Ts_out_default = float(sink.get("Tsink_out_K", 363.15))
    Ts_in = float(sink.get("Tsink_in_K", 343.15))
    type_par = cfg.get("heat_pumps", {}).get("types", {}).get(hp_type, {})
    eta = float(type_par.get("eta", 0.75))
    FQ = float(type_par.get("FQ", 0.10))

    # Get source temperature series
    if wrg_col and wrg_col in table.columns:
        temps = table[wrg_col]
    else:
        temps = [Ts_in - 10.0 for _ in range(len(table))]

    Tout = [max(t - dT, 1.0) for t in temps]

    cop: list[float] = []
    for i, (Tin, Tout_i) in enumerate(zip(temps, Tout, strict=False)):
        # Use per-timestep sink temp if provided, else fixed default
        Ts_out = sink_temp_series[i] if sink_temp_series is not None else Ts_out_default
        Ls = _lmtd(Ts_out, Ts_in)
        Lsrc = _lmtd(Tin, Tout_i)
        mdts = 0.2 * (Ts_out - Tout_i + 2 * dTpp) + 0.2 * (Ts_out - Ts_in) + 0.016
        qww = (
            0.0014 * (Ts_out - Tout_i + 2 * dTpp)
            - 0.0015 * (Ts_out - Ts_in)
            + 0.039
        )
        A = Ls / max(1e-9, Ls - Lsrc)
        B = (1 + (mdts + dTpp) / max(1e-9, Ls)) / (
            1
            + (mdts + 0.5 * (Tin - Tout_i) + 2 * dTpp)
            / max(1e-9, (Ls - Lsrc))
        )
        val = A * B * eta * (1 - qww) + 1 - eta - FQ
        if not math.isfinite(val) or val < COP_MIN:
            val = float(copcfg.get("cop_fallback", COP_DEFAULT))
        cop.append(float(min(max(val, COP_MIN), COP_MAX_SYSTEM_BUILDER)))
    return cop


def _validate_axis(values: Sequence[float], axis_name: str) -> list[float]:
    """Validate COP table axis values."""
    axis = [float(v) for v in values]
    if not axis:
        raise ValueError(f"COP table axis '{axis_name}' is empty")
    if any(not math.isfinite(v) for v in axis):
        raise ValueError(f"COP table axis '{axis_name}' contains invalid values")
    if axis != sorted(axis):
        raise ValueError(
            f"COP table axis '{axis_name}' must be sorted in ascending order"
        )
    return axis


def _locate_interval(
    points: list[float], value: float, clamp: bool, axis_name: str
) -> tuple[int, int, float]:
    """Locate the interval containing value and compute interpolation fraction."""
    if len(points) == 1:
        return 0, 0, 0.0
    if value <= points[0]:
        if clamp:
            return 0, 0, 0.0
        raise ValueError(f"Value {value} is below COP table range for {axis_name}")
    if value >= points[-1]:
        if clamp:
            idx = len(points) - 1
            return idx, idx, 0.0
        raise ValueError(f"Value {value} is above COP table range for {axis_name}")
    for i in range(len(points) - 1):
        lo = points[i]
        hi = points[i + 1]
        if lo <= value <= hi or math.isclose(value, lo) or math.isclose(value, hi):
            span = max(hi - lo, 1e-12)
            frac = (value - lo) / span
            return i, i + 1, min(max(frac, 0.0), 1.0)
    # Should not happen due to bounds above
    raise ValueError(f"Value {value} could not be mapped to COP axis {axis_name}")


def _interp1d(
    points: list[float], values: list[float], i0: int, i1: int, frac: float
) -> float:
    """Linear interpolation in 1D."""
    if i0 == i1:
        return values[i0]
    v0 = values[i0]
    v1 = values[i1]
    return v0 + frac * (v1 - v0)


def _interp2d(
    x_points: list[float],
    matrix: list[list[float]],
    x_idx0: int,
    x_idx1: int,
    x_frac: float,
    y_idx0: int,
    y_idx1: int,
    y_frac: float,
) -> float:
    """Bilinear interpolation in 2D."""
    if y_idx0 == y_idx1:
        return _interp1d(x_points, matrix[y_idx0], x_idx0, x_idx1, x_frac)
    # Interpolate along x for both y positions, then between them
    row0 = matrix[y_idx0]
    row1 = matrix[y_idx1]
    v0 = _interp1d(x_points, row0, x_idx0, x_idx1, x_frac)
    v1 = _interp1d(x_points, row1, x_idx0, x_idx1, x_frac)
    return v0 + y_frac * (v1 - v0)


def _series_from_column(
    table: TimeSeriesTable, column: str | None, default: float | None
) -> list[float]:
    """Extract time series from table column or use default value."""
    if column and column in table.columns:
        return [float(table[column][i]) for i in range(len(table))]
    if default is not None:
        return [float(default) for _ in range(len(table))]
    raise KeyError(f"Required column {column!r} for COP calculation is missing")


def _lmtd(Th: float, Tc: float) -> float:
    """Calculate log mean temperature difference with numerical safeguards.

    Args:
        Th: Hot side temperature
        Tc: Cold side temperature

    Returns:
        Log mean temperature difference (LMTD)
    """
    # Ensure positive temperatures with small offset to avoid log(0)
    Th_safe = max(Th, 1e-3)
    Tc_safe = max(Tc, 1e-3)

    # If temperatures are too close, return arithmetic mean
    if abs(Th_safe - Tc_safe) < 1e-6:
        return max((Th_safe + Tc_safe) / 2.0, 1e-6)

    # Standard LMTD calculation: (Th - Tc) / ln(Th / Tc)
    ratio = Th_safe / Tc_safe
    if abs(ratio - 1.0) < 1e-9:  # Too close to 1, log is unstable
        return max((Th_safe + Tc_safe) / 2.0, 1e-6)

    numerator = Th_safe - Tc_safe
    denominator = math.log(ratio)
    return abs(numerator / max(abs(denominator), 1e-9))

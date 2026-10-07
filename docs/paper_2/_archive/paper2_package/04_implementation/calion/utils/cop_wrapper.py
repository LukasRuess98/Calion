"""COP wrapper for Paper 2: waste heat priority logic and time-varying source temperature.

Precomputes a COP(t) array from T_VL(t) and T_source(t) before the MILP is built.
The MILP then uses COP(t) as a fixed parameter, keeping the formulation linear.

Waste heat priority:
  IF Q_AW_max(t) > 0  →  T_source(t) = T_AW(t)   (waste heat temperature)
  ELSE                 →  T_source(t) = T_amb(t)   (river/ambient fallback)
"""

from __future__ import annotations

import numpy as np

from calion.models.cop_calculator import calculate_cop_series
from calion.utils.timeseries import TimeSeriesTable


def build_source_temperature_series(
    Q_AW_max_ts: np.ndarray | list[float],
    T_AW_ts: np.ndarray | list[float],
    T_amb_ts: np.ndarray | list[float],
) -> np.ndarray:
    """Compute hourly WP source temperature with waste heat priority.

    Args:
        Q_AW_max_ts: Available waste heat power [MW] per timestep. 0 = unavailable.
        T_AW_ts: Waste heat temperature [°C] per timestep.
        T_amb_ts: Ambient / river fallback temperature [°C] per timestep.

    Returns:
        np.ndarray T_source(t) [°C], length = number of timesteps.
    """
    Q_AW = np.asarray(Q_AW_max_ts, dtype=float)
    T_AW = np.asarray(T_AW_ts, dtype=float)
    T_amb = np.asarray(T_amb_ts, dtype=float)

    if not (len(Q_AW) == len(T_AW) == len(T_amb)):
        raise ValueError(
            f"Time series lengths must match: Q_AW={len(Q_AW)}, "
            f"T_AW={len(T_AW)}, T_amb={len(T_amb)}"
        )

    return np.where(Q_AW > 0, T_AW, T_amb)


def precompute_cop(
    T_VL_ts: np.ndarray | list[float],
    T_source_ts: np.ndarray | list[float],
    table: TimeSeriesTable,
    cfg: dict,
    hp_type: str = "default",
    wrg_col: str | None = None,
) -> np.ndarray:
    """Precompute hourly COP array for use as MILP parameter.

    Wraps calculate_cop_series() from cop_calculator.py, passing:
    - sink_temp_series = T_VL_ts (from heating curve, in °C converted to K)
    - x_series  = T_source_ts  (source temperature, in °C or K depending on LUT config)

    The COP LUT in the config expects temperatures in K (Tsink_out_K).
    This function converts °C → K before passing to the calculator.

    Args:
        T_VL_ts: Supply (sink) temperature series [°C], length T.
        T_source_ts: WP source temperature series [°C], length T.
        table: TimeSeriesTable used by calculate_cop_series for column lookup.
        cfg: Full config dict (heat_pumps.cop.tables must reference the LUT).
        hp_type: Heat pump type key in config, default "default".
        wrg_col: Column name in table holding WRG source temperature (legacy path).
                 If provided alongside T_source_ts, T_source_ts takes priority.

    Returns:
        np.ndarray of COP values per timestep, clamped to [1.0, 8.0].
    """
    T_VL = np.asarray(T_VL_ts, dtype=float)
    T_src = np.asarray(T_source_ts, dtype=float)

    if len(T_VL) != len(T_src):
        raise ValueError(
            f"T_VL_ts and T_source_ts must have the same length "
            f"({len(T_VL)} vs {len(T_src)})"
        )

    # Convert °C → K for sink temperature (cop_calculator expects K)
    sink_temp_k = (T_VL + 273.15).tolist()

    # Inject T_source into the table under a synthetic column so
    # calculate_cop_series can read it via x_series path.
    # We use the wrg_col name if given; otherwise synthesize one.
    _src_col = wrg_col or "__p2_source_temp_k__"
    table_with_source = _inject_column(table, _src_col, (T_src + 273.15).tolist())

    cop_list = calculate_cop_series(
        table=table_with_source,
        wrg_col=_src_col,
        cfg=cfg,
        hp_type=hp_type,
        sink_temp_series=sink_temp_k,
    )

    return np.array(cop_list, dtype=float)


def _inject_column(table: TimeSeriesTable, col_name: str, values: list[float]) -> TimeSeriesTable:
    """Return a copy of table with an additional column injected.

    This avoids mutating the original table.
    """
    # TimeSeriesTable is dict-like; build a new one by copying underlying data.
    # Support both plain dict-of-lists and pandas DataFrames.
    try:
        import pandas as pd
        if isinstance(table, pd.DataFrame):
            df = table.copy()
            df[col_name] = values
            return df
    except ImportError:
        pass

    if isinstance(table, dict):
        new_table = dict(table)
        new_table[col_name] = values
        return new_table

    # Fallback: TimeSeriesTable and similar objects with a .copy() method
    if hasattr(table, 'copy') and hasattr(table, 'data') and hasattr(table, 'index'):
        new_table = table.copy()
        new_table.data[col_name] = values
        if col_name not in new_table.columns:
            new_table.columns.append(col_name)
        return new_table

    raise TypeError(f"Cannot inject column into table of type {type(table).__name__}")


def cop_plausibility_check(cop_ts: np.ndarray, cop_min: float = 1.0, cop_max: float = 8.0) -> dict:
    """Validate COP array plausibility (Spec §10 check 6).

    Args:
        cop_ts: COP time series array.
        cop_min: Minimum expected COP.
        cop_max: Maximum expected COP.

    Returns:
        Dict with 'ok' bool, 'n_below', 'n_above', 'mean', 'min', 'max'.
    """
    arr = np.asarray(cop_ts, dtype=float)
    n_below = int(np.sum(arr < cop_min))
    n_above = int(np.sum(arr > cop_max))
    return {
        "ok": n_below == 0 and n_above == 0,
        "n_below_min": n_below,
        "n_above_max": n_above,
        "mean": float(np.mean(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }

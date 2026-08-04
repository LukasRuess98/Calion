"""Flexible connection agreements: turning contract parameters into P_limit(t).

The parameters here are exactly those that § 17 Abs. 2b S. 3 EnWG requires a flexible connection
agreement to state: the level of the limitation, the periods of limitation, and (via the hardness
of the constraint in model.py) the liability for exceeding it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CFG
from .data import Inputs, parse_int_list


def _dynamic_calls(index: pd.DatetimeIndex, price: np.ndarray, dt: float,
                   max_h_per_a: float, event_h: float, seed: int = 0) -> np.ndarray:
    """Boolean mask of DSO curtailment calls.

    Congestion correlates with system stress, so calls are placed on the highest-priced
    non-overlapping windows of length `event_h`. Deterministic given the seed; the seed is
    varied in the robustness runs to show the result does not depend on one call pattern.

    The annual budget `max_h_per_a` is pro-rated by the actual horizon length, so a one-month
    screening run receives one month's share of calls rather than a full year's.
    """
    n = len(index)
    steps = max(1, int(round(event_h / dt)))
    years_frac = n * dt / 8760.0          # actual horizon length, NOT the number of calendar years
    n_events = int(round(max_h_per_a * years_frac / event_h))
    if n_events <= 0:
        return np.zeros(n, bool)
    roll = pd.Series(price, index=index).rolling(steps, min_periods=steps).mean()
    roll = roll.shift(-(steps - 1)).to_numpy()
    rng = np.random.default_rng(seed)
    roll = roll + rng.normal(0, np.nanstd(roll) * 0.05, n)      # break ties, allow variation
    order = np.argsort(-np.nan_to_num(roll, nan=-1e9))
    mask = np.zeros(n, bool)
    taken = 0
    for s in order:
        if taken >= n_events:
            break
        if s + steps > n or mask[s:s + steps].any():
            continue
        mask[s:s + steps] = True
        taken += 1
    return mask


def build_grid_limit(inp: Inputs, fca_id: str, index: pd.DatetimeIndex, P_exist: float,
                     price: np.ndarray, dt: float, seed: int | None = None,
                     flex_scale: float = 1.0, window_width: float | None = None,
                     curtail_h: float | None = None):
    """Return (P_limit array [MW], free_connection flag, restricted mask, fca row)."""
    f = inp.fca.set_index("fca_id").loc[fca_id]
    typ = str(f["type"]).strip().lower()
    n = len(index)
    a = float(f["P_static_rel"]) * P_exist
    b = float(f["P_flex_rel"]) * flex_scale * P_exist

    if typ == "firm":
        return np.full(n, P_exist), False, np.zeros(n, bool), f
    if typ == "firm_upgrade":
        return np.full(n, np.inf), True, np.zeros(n, bool), f
    if typ == "static":
        return np.full(n, a), False, np.ones(n, bool), f

    if typ == "window":
        hrs = parse_int_list(f["restricted_hours"])
        if window_width is not None and hrs:                 # sensitivity: widen/narrow the block
            centre = float(np.mean(hrs))
            lo, hi = centre - window_width / 2, centre + window_width / 2
            hrs = [h for h in range(24) if lo <= h + 0.5 <= hi]
        mask = np.ones(n, bool)
        if hrs:
            mask &= np.asarray(index.hour.isin(hrs))
        mon = parse_int_list(f["restricted_months"])
        if mon:
            mask &= np.asarray(index.month.isin(mon))
        wd = parse_int_list(f["restricted_weekdays"])
        if wd:
            mask &= np.asarray(index.dayofweek.isin(wd))
        return np.where(mask, a, b), False, mask, f

    if typ == "dynamic":
        mask = _dynamic_calls(index, price, dt,
                              curtail_h if curtail_h is not None else float(f["max_curtail_h_per_a"]),
                              float(f["max_event_h"]),
                              seed if seed is not None else CFG["dynamic_seed"])
        return np.where(mask, a, b), False, mask, f

    raise ValueError(f"unknown fca type {typ}")


def hlzf_mask(inp: Inputs, index: pd.DatetimeIndex) -> np.ndarray:
    """§ 19 Abs. 2 S. 1 StromNEV high-load windows."""
    m = np.zeros(len(index), bool)
    for _, r in inp.hlzf.iterrows():
        mm = np.ones(len(index), bool)
        mo = parse_int_list(r["months"])
        if mo:
            mm &= np.asarray(index.month.isin(mo))
        wd = parse_int_list(r["weekdays"])
        if wd:
            mm &= np.asarray(index.dayofweek.isin(wd))
        hr = parse_int_list(r["hours"])
        if hr:
            mm &= np.asarray(index.hour.isin(hr))
        m |= mm
    return m

"""
tools/validation_spatial.py
===========================
Multi-node spatial temperature validation for district-heating network models.

This module validates simulated supply temperatures against measured node-level
monitoring data with:
- Temporal split: train (Oct-Feb) vs test (Mar-Sep)
- Spatial split: calibration nodes vs independent validation nodes
- Uncertainty-aware KPIs: bootstrap confidence intervals and sensor floor

Usage:
    python tools/validation_spatial.py
    python tools/validation_spatial.py --no-calibrate
    python tools/validation_spatial.py --plot-only
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.paper.mpl_export import AE_RCPARAMS, save_figure_bundle
from tools.validation_runner import (
    DATA_PATH,
    MIQP_DIR,
    NODE_CONSUMERS,
    OUT_DIR,
    PIPE_CATALOG,
    _get_node_flow_m3h,
    extract_supply_temperature_bc,
    load_historical,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sensor uncertainty (EN 1434 Class 2)
SENSOR_UNCERTAINTY_T_C = 0.5
SENSOR_UNCERTAINTY_FLOW_PCT = 3.0
MAE_FLOOR_C = SENSOR_UNCERTAINTY_T_C / np.sqrt(2.0)

# Temporal split
TRAIN_MONTHS = (10, 11, 12, 1, 2)
TEST_MONTHS = (3, 4, 5, 6, 7, 8, 9)

# Spatial split
CALIBRATION_NODES = frozenset({"j_6", "j_7", "j_8", "j_14"})
VALIDATION_NODES = frozenset({"j_9", "j_10", "j_11", "j_12", "j_13", "j_15"})
SHARED_NODES = frozenset({"j_2", "j_3", "j_4", "j_5"})
BC_NODE = "j_1"

# Physics constants
CP_WATER = 4186.0  # J/(kg*K)
RHO_WATER = 977.0  # kg/m3

GROUND_TEMP_BY_MONTH: dict[int, float] = {
    1: 4.0, 2: 3.5, 3: 5.0, 4: 8.0, 5: 12.0, 6: 15.0,
    7: 17.0, 8: 17.5, 9: 15.5, 10: 12.0, 11: 8.0, 12: 5.0,
}

MAX_MAE_TARGET_C = 1.5
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 42

L3PLUS_DIR = ROOT / "output" / "paper_runs" / "L3plus"
L3NL_DIR = ROOT / "output" / "paper_runs" / "L3NL"
L3_DIR = ROOT / "output" / "paper_runs" / "L3"


# Tree structure for Memmingen network
TREE_EDGES: dict[str, list[str]] = {
    "j_1": ["j_2"],
    "j_2": ["j_3"],
    "j_3": ["j_4", "j_9"],
    "j_4": ["j_5"],
    "j_5": ["j_6", "j_7"],
    "j_7": ["j_8"],
    "j_9": ["j_10"],
    "j_10": ["j_11"],
    "j_11": ["j_12"],
    "j_12": ["j_13"],
    "j_13": ["j_14", "j_15"],
}

EDGE_TO_PIPE: dict[tuple[str, str], str] = {
    ("j_1", "j_2"): "j1_to_j2",
    ("j_2", "j_3"): "j2_to_j3",
    ("j_3", "j_4"): "j3_to_j4",
    ("j_3", "j_9"): "j3_to_j9",
    ("j_4", "j_5"): "j4_to_j5",
    ("j_5", "j_6"): "j5_to_j6",
    ("j_5", "j_7"): "j5_to_j7",
    ("j_7", "j_8"): "j7_to_j8",
    ("j_9", "j_10"): "j9_to_j10",
    ("j_10", "j_11"): "j10_to_j11",
    ("j_11", "j_12"): "j11_to_j12",
    ("j_12", "j_13"): "j12_to_j13",
    ("j_13", "j_14"): "j13_to_j14",
    ("j_13", "j_15"): "j13_to_j15",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NodeValidationResult:
    """Validation result for one node."""
    node: str
    path_length_m: float
    n_consumers: int
    node_type: str  # BC / CAL / VAL / SHARED
    n_valid_hours: int
    coverage_pct: float
    intra_node_spread_C: float
    T_meas_mean_C: float
    T_meas_std_C: float
    T_meas_winter_C: Optional[float] = None
    T_meas_summer_C: Optional[float] = None
    level_results: dict = field(default_factory=dict)


@dataclass
class SpatialValidationReport:
    """Spatial validation report for one period."""
    period: str
    bc_info: dict = field(default_factory=dict)
    node_results: list[NodeValidationResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    u_multipliers: dict[str, float] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tree utilities
# ---------------------------------------------------------------------------

def compute_path_lengths() -> dict[str, float]:
    """Return cumulative path length from j_1 to each node."""
    lengths: dict[str, float] = {"j_1": 0.0}
    queue: deque[str] = deque(["j_1"])
    while queue:
        parent = queue.popleft()
        for child in TREE_EDGES.get(parent, []):
            pipe_id = EDGE_TO_PIPE[(parent, child)]
            lengths[child] = lengths[parent] + float(PIPE_CATALOG[pipe_id]["length_m"])
            queue.append(child)
    return lengths


def get_downstream_nodes(node: str) -> set[str]:
    """Return all downstream nodes (inclusive)."""
    ds = {node}
    queue: deque[str] = deque([node])
    while queue:
        cur = queue.popleft()
        for ch in TREE_EDGES.get(cur, []):
            ds.add(ch)
            queue.append(ch)
    return ds


def get_path_from_root(node: str) -> list[tuple[str, str]]:
    """Return ordered edge list from j_1 to node."""
    if node == BC_NODE:
        return []
    parent_map: dict[str, str] = {}
    for p, children in TREE_EDGES.items():
        for c in children:
            parent_map[c] = p
    path: list[tuple[str, str]] = []
    cur = node
    while cur in parent_map:
        p = parent_map[cur]
        path.append((p, cur))
        cur = p
    path.reverse()
    return path


def get_node_type(node: str) -> str:
    """Classify node for reporting."""
    if node == BC_NODE:
        return "BC"
    if node in CALIBRATION_NODES:
        return "CAL"
    if node in VALIDATION_NODES:
        return "VAL"
    if node in SHARED_NODES:
        return "SHARED"
    return "SHARED"


# ---------------------------------------------------------------------------
# Data extraction from measurements
# ---------------------------------------------------------------------------

def _get_bc_series(hist: pd.DataFrame, bc_info: dict) -> pd.Series:
    """Build boundary-condition timeseries for j_1 supply temperature."""
    if bc_info.get("mode") == "timeseries" and isinstance(bc_info.get("timeseries"), pd.Series):
        ts = bc_info["timeseries"].reindex(hist.index)
        fill_val = float(bc_info.get("median_C") or bc_info.get("mean_C") or 86.5)
        return ts.fillna(fill_val)
    val = float(bc_info.get("median_C") or bc_info.get("mean_C") or 86.5)
    return pd.Series(val, index=hist.index, dtype=float)


def get_measured_node_temperatures(
    hist: pd.DataFrame,
    min_valid_hours: int = 24,
) -> tuple[dict[str, pd.Series], dict[str, float]]:
    """
    Extract measured node supply temperatures.

    For nodes with multiple consumers, the maximum flow temperature is used.
    """
    node_temps: dict[str, pd.Series] = {}
    node_spreads: dict[str, float] = {}

    for node, consumers in NODE_CONSUMERS.items():
        cols = [f"{v}_flow_temp" for v in consumers if f"{v}_flow_temp" in hist.columns]
        if not cols:
            continue
        stacked = hist[cols].astype(float)
        t_node = stacked.max(axis=1, skipna=True)
        if int(t_node.notna().sum()) < min_valid_hours:
            continue
        node_temps[node] = t_node

        if len(cols) > 1:
            spread_series = stacked.max(axis=1, skipna=True) - stacked.min(axis=1, skipna=True)
            spread_mean = float(spread_series.mean()) if spread_series.notna().any() else 0.0
        else:
            spread_mean = 0.0
        node_spreads[node] = spread_mean

    print(f"  [MEAS] T_supply extracted for {len(node_temps)} nodes")
    high_spread = {n: s for n, s in node_spreads.items() if s > 2.0}
    if high_spread:
        shown = ", ".join(f"{n}:{v:.2f}" for n, v in sorted(high_spread.items()))
        print(f"  [WARN] Intra-node spread >2C: {shown}")
    return node_temps, node_spreads


def get_measured_return_temperatures(
    hist: pd.DataFrame,
    min_valid_hours: int = 24,
) -> dict[str, pd.Series]:
    """Extract measured return temperatures by node as mean across consumers."""
    node_ret: dict[str, pd.Series] = {}
    for node, consumers in NODE_CONSUMERS.items():
        cols = [f"{v}_return_temp" for v in consumers if f"{v}_return_temp" in hist.columns]
        if not cols:
            continue
        t_ret = hist[cols].astype(float).mean(axis=1, skipna=True)
        if int(t_ret.notna().sum()) < min_valid_hours:
            continue
        node_ret[node] = t_ret
    return node_ret


# ---------------------------------------------------------------------------
# Pipe flow and reconstruction
# ---------------------------------------------------------------------------

def compute_pipe_flows_measured(
    hist: pd.DataFrame,
    node_temps_meas: dict[str, pd.Series],
    node_ret_temps: dict[str, pd.Series],
    bc_temp: float | pd.Series,
) -> dict[str, pd.Series]:
    """
    Compute pipe mass flow [kg/s] from downstream demand and measured delta-T.

    Notes:
    - Uses measured node delta-T and clips to [5, 80] C.
    - Uses corrected _get_node_flow_m3h as fallback when demand gaps exist.
    """
    idx = hist.index

    node_dt: dict[str, pd.Series] = {}
    for node in NODE_CONSUMERS:
        t_sup = node_temps_meas.get(node)
        t_ret = node_ret_temps.get(node)
        if t_sup is not None and t_ret is not None:
            dt = (t_sup - t_ret).clip(lower=5.0, upper=80.0)
        else:
            dt = pd.Series(30.0, index=idx, dtype=float)
        node_dt[node] = dt

    # Node demand from measured demand columns, fallback from corrected flow rates
    node_q: dict[str, pd.Series] = {}
    for node, consumers in NODE_CONSUMERS.items():
        q = pd.Series(0.0, index=idx, dtype=float)
        for v_name in consumers:
            dcol = f"{v_name}_demand_MWth"
            if dcol in hist.columns:
                q = q + hist[dcol].fillna(0.0)
            # Fallback path with V_x flow auto-correction (L/h vs m3/h)
            try:
                v = int(v_name.split("_")[1])
            except Exception:
                v = None
            if v is not None:
                flow_m3h = _get_node_flow_m3h(v, hist).fillna(0.0)
                sup_col = f"{v_name}_flow_temp"
                ret_col = f"{v_name}_return_temp"
                if sup_col in hist.columns and ret_col in hist.columns:
                    dt_cons = (hist[sup_col] - hist[ret_col]).clip(lower=5.0, upper=80.0).fillna(30.0)
                else:
                    dt_cons = node_dt[node].fillna(30.0)
                q_from_flow = (flow_m3h / 3.6) * CP_WATER * dt_cons / 1e6
                if dcol in hist.columns:
                    q = q + 0.0 * q_from_flow  # demand preferred; fallback only if missing
                    miss = hist[dcol].isna()
                    q.loc[miss] = q.loc[miss] + q_from_flow.loc[miss]
                else:
                    q = q + q_from_flow
        node_q[node] = q.clip(lower=0.0)

    pipe_flows: dict[str, pd.Series] = {}
    for (parent, child), pipe_id in EDGE_TO_PIPE.items():
        downstream = get_downstream_nodes(child)
        m_dot = pd.Series(0.0, index=idx, dtype=float)
        for dn in downstream:
            q_dn = node_q.get(dn, pd.Series(0.0, index=idx, dtype=float))
            dt_dn = node_dt.get(dn, pd.Series(30.0, index=idx, dtype=float)).fillna(30.0)
            m_dot = m_dot + (q_dn * 1e6 / (CP_WATER * dt_dn))
        pipe_flows[pipe_id] = m_dot.clip(lower=0.01, upper=100.0)
    return pipe_flows


def reconstruct_node_temperatures_L3(
    hist: pd.DataFrame,
    bc_temp: float | pd.Series,
    u_multipliers: dict[str, float],
    node_temps_meas: dict[str, pd.Series],
    node_ret_temps: dict[str, pd.Series],
) -> dict[str, pd.Series]:
    """
    Reconstruct node supply temperatures via sequential pipe decay model.
    """
    t_ground = pd.Series(
        [GROUND_TEMP_BY_MONTH[int(m)] for m in hist.index.month],
        index=hist.index,
        dtype=float,
    )
    pipe_flows = compute_pipe_flows_measured(hist, node_temps_meas, node_ret_temps, bc_temp)

    node_temps: dict[str, pd.Series] = {}
    if isinstance(bc_temp, pd.Series):
        bc_series = bc_temp.reindex(hist.index)
        fill_val = float(bc_series.dropna().median()) if bc_series.notna().any() else 86.5
        node_temps[BC_NODE] = bc_series.fillna(fill_val)
    else:
        node_temps[BC_NODE] = pd.Series(float(bc_temp), index=hist.index, dtype=float)

    queue: deque[str] = deque([BC_NODE])
    while queue:
        parent = queue.popleft()
        t_in = node_temps[parent]
        for child in TREE_EDGES.get(parent, []):
            pipe_id = EDGE_TO_PIPE[(parent, child)]
            pipe = PIPE_CATALOG[pipe_id]
            u_nom = float(pipe["U_nom"])
            u_mult = float(u_multipliers.get(pipe_id, 1.0))
            u_eff = u_nom * u_mult
            length = float(pipe["length_m"])
            m_dot = pipe_flows[pipe_id]

            exponent = (-(u_eff * length) / (m_dot * CP_WATER)).clip(lower=-5.0, upper=0.0)
            phi = np.exp(exponent)
            t_out = t_ground + (t_in - t_ground) * phi
            node_temps[child] = t_out
            queue.append(child)

    # Plausibility checks
    for parent, children in TREE_EDGES.items():
        t_p = node_temps.get(parent)
        if t_p is None:
            continue
        for child in children:
            t_c = node_temps.get(child)
            if t_c is None:
                continue
            if float((t_c > t_p + 0.05).sum()) > 0:
                print(f"  [WARN] Non-monotonic hours detected on edge {parent}->{child}")

    t_bc_mean = float(node_temps[BC_NODE].mean())
    for node, ts in node_temps.items():
        if node == BC_NODE or ts.empty:
            continue
        t_mean = float(ts.mean())
        if t_mean > t_bc_mean + 0.1:
            print(f"  [WARN] {node}: mean supply above BC ({t_mean:.2f}>{t_bc_mean:.2f})")
        if t_mean < float(t_ground.mean()) - 0.1:
            print(f"  [WARN] {node}: mean supply below ground temp ({t_mean:.2f})")
    return node_temps


# ---------------------------------------------------------------------------
# Independent U calibration (CAL nodes only, train months only)
# ---------------------------------------------------------------------------

def calibrate_u_values_independent(
    hist_train: pd.DataFrame,
    node_temps_meas: dict[str, pd.Series],
    node_ret_temps: dict[str, pd.Series],
    bc_temp: float | pd.Series,
    max_iterations: int = 5,
) -> dict[str, float]:
    """
    Calibrate U multipliers on branch terminal calibration nodes only.
    """
    print(f"  [CAL] Spatial calibration on nodes: {sorted(CALIBRATION_NODES)}")
    u_mult = {pid: 1.0 for pid in PIPE_CATALOG}
    if len(hist_train) < 100:
        print("  [CAL] Too few train hours, keeping nominal multipliers")
        return u_mult

    # Each calibration node controls one terminal branch pipe
    cal_to_pipe = {
        "j_6": "j5_to_j6",
        "j_7": "j5_to_j7",
        "j_8": "j7_to_j8",
        "j_14": "j13_to_j14",
    }

    meas_train = {k: v.reindex(hist_train.index) for k, v in node_temps_meas.items()}
    ret_train = {k: v.reindex(hist_train.index) for k, v in node_ret_temps.items()}

    for it in range(max_iterations):
        recon = reconstruct_node_temperatures_L3(hist_train, bc_temp, u_mult, meas_train, ret_train)
        max_bias = 0.0
        for node, pipe_id in cal_to_pipe.items():
            t_meas = meas_train.get(node)
            t_sim = recon.get(node)
            if t_meas is None or t_sim is None:
                continue
            valid = t_meas.notna() & t_sim.notna()
            if int(valid.sum()) < 50:
                continue
            bias = float((t_sim[valid] - t_meas[valid]).mean())
            max_bias = max(max_bias, abs(bias))
            if abs(bias) < 0.10:
                continue

            t_ground = pd.Series(
                [GROUND_TEMP_BY_MONTH[int(m)] for m in hist_train.index.month],
                index=hist_train.index,
                dtype=float,
            )
            driving = float((t_sim[valid] - t_ground[valid]).mean())
            driving = max(driving, 5.0)

            corr = 1.0 + 0.5 * (bias / driving)
            corr = float(np.clip(corr, 0.5, 2.5))
            u_mult[pipe_id] = float(np.clip(u_mult[pipe_id] * corr, 0.3, 10.0))
            if it == max_iterations - 1:
                print(f"    {node} {pipe_id}: bias={bias:+.3f}C mult={u_mult[pipe_id]:.3f}")
        if max_bias < 0.15:
            print(f"  [CAL] Converged at iteration {it + 1} (max bias {max_bias:.3f}C)")
            break

    changed = {k: v for k, v in u_mult.items() if abs(v - 1.0) > 0.01}
    if changed:
        print("  [CAL] Updated multipliers:", ", ".join(f"{k}={v:.2f}" for k, v in sorted(changed.items())))
    else:
        print("  [CAL] Multipliers remained nominal")
    return u_mult


# ---------------------------------------------------------------------------
# Level extraction (L3+, L3NL) with robust fallback chain
# ---------------------------------------------------------------------------

def _read_dispatch_timestamps(run_dir: Path) -> Optional[pd.DatetimeIndex]:
    """Read dispatch timestamps for integer->datetime mapping."""
    dispatch_path = run_dir / "dispatch_hourly.csv"
    if not dispatch_path.exists():
        return None
    try:
        df = pd.read_csv(dispatch_path)
    except Exception:
        return None
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
    else:
        ts = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    ts = ts.dropna()
    if len(ts) == 0:
        return None
    return pd.DatetimeIndex(ts)


def _normalize_state_timestamps(
    ts_raw: pd.Series,
    dispatch_idx: Optional[pd.DatetimeIndex],
) -> pd.Series:
    """Normalize timestamps; map integer timesteps by row order when needed."""
    num = pd.to_numeric(ts_raw, errors="coerce")
    if dispatch_idx is not None and int(num.notna().sum()) >= max(1, int(0.8 * len(ts_raw))):
        unique_steps = pd.Series(num.dropna().unique()).tolist()
        if 0 < len(unique_steps) <= len(dispatch_idx):
            step_map = {step: dispatch_idx[i] for i, step in enumerate(unique_steps)}
            mapped = num.map(step_map)
            return pd.Series(mapped, index=ts_raw.index)

    dt = pd.to_datetime(ts_raw, errors="coerce")
    if int(dt.notna().sum()) >= max(1, int(0.8 * len(ts_raw))):
        return pd.Series(dt, index=ts_raw.index)

    return ts_raw


def _to_node_series_from_wide(df_wide: pd.DataFrame) -> dict[str, pd.Series]:
    """Extract per-node series from wide dataframe with flexible column names."""
    out: dict[str, pd.Series] = {}
    for node in NODE_CONSUMERS:
        patterns = [
            f"T_node_{node}",
            f"T_supply_{node}",
            f"T_{node}",
            f"T_sup_{node}",
            f"{node}_T_supply",
            node,
        ]
        for pat in patterns:
            if pat in df_wide.columns:
                out[node] = df_wide[pat].astype(float)
                break
    return out


def _load_from_node_temperatures_csv(run_dir: Path, level_name: str) -> Optional[dict[str, pd.Series]]:
    path = run_dir / "node_temperatures.csv"
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col=0)
    except Exception as exc:
        print(f"  [WARN] {level_name}: cannot read {path.name}: {exc}")
        return None
    dispatch_idx = _read_dispatch_timestamps(run_dir)
    idx_norm = _normalize_state_timestamps(pd.Series(df.index), dispatch_idx)
    df.index = idx_norm
    out = _to_node_series_from_wide(df)
    if len(out) >= 2:
        print(f"  [LOAD] {level_name}: node_temperatures.csv ({len(out)} nodes)")
        return out
    return None


def _load_from_nodes_state_parquet(run_dir: Path, level_name: str) -> Optional[dict[str, pd.Series]]:
    path = run_dir / "nodes_state_hourly.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        print(f"  [WARN] {level_name}: cannot read {path.name}: {exc}")
        return None
    if df.empty:
        return None
    required = {"timestamp", "node_id", "T_supply_c"}
    if not required.issubset(set(df.columns)):
        return None

    dispatch_idx = _read_dispatch_timestamps(run_dir)
    ts_norm = _normalize_state_timestamps(df["timestamp"], dispatch_idx)
    df2 = df.copy()
    df2["timestamp_norm"] = ts_norm
    df2 = df2[df2["timestamp_norm"].notna()]
    if df2.empty:
        return None

    wide = (
        df2.pivot_table(
            index="timestamp_norm",
            columns="node_id",
            values="T_supply_c",
            aggfunc="mean",
        )
        .sort_index()
    )
    out: dict[str, pd.Series] = {}
    for node in NODE_CONSUMERS:
        if node in wide.columns:
            out[node] = wide[node].astype(float)
    if len(out) >= 2:
        print(f"  [LOAD] {level_name}: nodes_state_hourly.parquet ({len(out)} nodes)")
        return out
    return None


def _load_from_nodes_timeseries_csv(run_dir: Path, level_name: str) -> Optional[dict[str, pd.Series]]:
    # Check both root and thermal_network path variants
    candidates = [
        run_dir / "nodes_timeseries.csv",
        run_dir / "thermal_network" / "nodes" / "nodes_timeseries.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, sep=";", index_col=0)
        except Exception as exc:
            print(f"  [WARN] {level_name}: cannot read {path.name}: {exc}")
            continue
        dispatch_idx = _read_dispatch_timestamps(run_dir)
        idx_norm = _normalize_state_timestamps(pd.Series(df.index), dispatch_idx)
        df.index = idx_norm

        out: dict[str, pd.Series] = {}
        for node in NODE_CONSUMERS:
            col = f"{node}_T_supply"
            if col in df.columns:
                out[node] = df[col].astype(float)
        if len(out) >= 2:
            print(f"  [LOAD] {level_name}: {path.name} ({len(out)} nodes)")
            return out
    return None


def _extract_from_run_dir(run_dir: Path, level_name: str) -> Optional[dict[str, pd.Series]]:
    if not run_dir.exists():
        return None
    for loader in (
        _load_from_node_temperatures_csv,
        _load_from_nodes_state_parquet,
        _load_from_nodes_timeseries_csv,
    ):
        out = loader(run_dir, level_name)
        if out is not None:
            return out
    return None


def _merge_node_series_dicts(parts: list[dict[str, pd.Series]]) -> Optional[dict[str, pd.Series]]:
    if not parts:
        return None
    merged: dict[str, pd.Series] = {}
    all_nodes = set()
    for p in parts:
        all_nodes.update(p.keys())
    for node in sorted(all_nodes):
        series_parts = [p[node] for p in parts if node in p and isinstance(p[node], pd.Series)]
        if not series_parts:
            continue
        s = pd.concat(series_parts, axis=0)
        s = s[~s.index.duplicated(keep="last")].sort_index()
        merged[node] = s
    return merged if merged else None


def _load_l3nl_from_miqp(level_name: str) -> Optional[dict[str, pd.Series]]:
    parts: list[dict[str, pd.Series]] = []
    for season in ("winter", "transition", "summer"):
        season_dir = MIQP_DIR / season
        data = _extract_from_run_dir(season_dir, f"{level_name}-{season}")
        if data is not None:
            parts.append(data)
    merged = _merge_node_series_dicts(parts)
    if merged is not None:
        print(f"  [LOAD] {level_name}: merged MIQP seasonal node temperatures")
    return merged


def extract_optimization_node_temps(
    results_dir: Path,
    level_name: str,
) -> Optional[dict[str, pd.Series]]:
    """
    Extract node temperatures with fallback chain.

    Priority:
    1) node_temperatures.csv
    2) nodes_state_hourly.parquet
    3) nodes_timeseries.csv
    """
    out = _extract_from_run_dir(results_dir, level_name)
    if out is not None:
        return out
    if level_name == "L3^NL":
        return _load_l3nl_from_miqp(level_name)
    print(f"  [INFO] {level_name}: no node temperature output found")
    return None


# ---------------------------------------------------------------------------
# KPI and statistics
# ---------------------------------------------------------------------------

def compute_kpi_with_uncertainty(
    t_meas: pd.Series,
    t_sim: pd.Series,
    sensor_unc_C: float = SENSOR_UNCERTAINTY_T_C,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Compute MAE, bias, RMSE and bootstrap CI for MAE."""
    idx = t_meas.dropna().index.intersection(t_sim.dropna().index)
    if len(idx) < 24:
        return {
            "MAE_C": np.nan,
            "bias_C": np.nan,
            "RMSE_C": np.nan,
            "MAE_CI95_lower_C": np.nan,
            "MAE_CI95_upper_C": np.nan,
            "sensor_floor_C": float(sensor_unc_C / np.sqrt(2.0)),
            "significant": False,
            "mean_sim_C": np.nan,
            "n_hours": 0,
        }

    err = t_sim.loc[idx].to_numpy(dtype=float) - t_meas.loc[idx].to_numpy(dtype=float)
    abs_err = np.abs(err)
    mae = float(abs_err.mean())
    bias = float(err.mean())
    rmse = float(np.sqrt((err ** 2).mean()))

    rng = np.random.default_rng(seed)
    n = len(abs_err)
    boot = np.empty(n_bootstrap, dtype=float)
    for i in range(n_bootstrap):
        boot[i] = float(rng.choice(abs_err, size=n, replace=True).mean())
    ci_lo = float(np.percentile(boot, 2.5))
    ci_hi = float(np.percentile(boot, 97.5))

    return {
        "MAE_C": mae,
        "bias_C": bias,
        "RMSE_C": rmse,
        "MAE_CI95_lower_C": ci_lo,
        "MAE_CI95_upper_C": ci_hi,
        "sensor_floor_C": float(sensor_unc_C / np.sqrt(2.0)),
        "significant": bool(mae > 2.0 * sensor_unc_C),
        "mean_sim_C": float(t_sim.loc[idx].mean()),
        "n_hours": int(len(idx)),
    }


def _compute_summary(report: SpatialValidationReport) -> None:
    """Compute level summaries separated by node type."""
    levels: set[str] = set()
    for nr in report.node_results:
        levels.update(nr.level_results.keys())

    summary: dict = {}
    for level in sorted(levels):
        all_mae = [
            nr.level_results[level]["MAE_C"]
            for nr in report.node_results
            if level in nr.level_results and not np.isnan(nr.level_results[level]["MAE_C"])
        ]
        val_mae = [
            nr.level_results[level]["MAE_C"]
            for nr in report.node_results
            if level in nr.level_results
            and nr.node_type == "VAL"
            and not np.isnan(nr.level_results[level]["MAE_C"])
        ]
        cal_mae = [
            nr.level_results[level]["MAE_C"]
            for nr in report.node_results
            if level in nr.level_results
            and nr.node_type == "CAL"
            and not np.isnan(nr.level_results[level]["MAE_C"])
        ]
        if not all_mae:
            continue
        row = {
            "mean_MAE_all_C": float(np.mean(all_mae)),
            "max_MAE_C": float(np.max(all_mae)),
            "n_nodes_all": int(len(all_mae)),
        }
        if val_mae:
            row["mean_MAE_VAL_C"] = float(np.mean(val_mae))
            row["max_MAE_VAL_C"] = float(np.max(val_mae))
            row["n_nodes_VAL"] = int(len(val_mae))
        if cal_mae:
            row["mean_MAE_CAL_C"] = float(np.mean(cal_mae))
            row["n_nodes_CAL"] = int(len(cal_mae))
        summary[level] = row

    def _impr(base: str, other: str) -> Optional[float]:
        if base not in summary or other not in summary:
            return None
        b = summary[base].get("mean_MAE_VAL_C")
        o = summary[other].get("mean_MAE_VAL_C")
        if b is None or o is None or b <= 0:
            return None
        return float((b - o) / b * 100.0)

    i_lp = _impr("L3", "L3+")
    if i_lp is not None:
        summary["improvement_L3_to_L3plus_pct"] = i_lp
    i_nl = _impr("L3", "L3^NL")
    if i_nl is not None:
        summary["improvement_L3_to_L3NL_pct"] = i_nl
    i_pn = _impr("L3+", "L3^NL")
    if i_pn is not None:
        summary["improvement_L3plus_to_L3NL_pct"] = i_pn

    report.summary = summary


def validate_spatial_temperature_profile(
    hist: pd.DataFrame,
    bc_info: dict,
    u_multipliers: dict[str, float],
    model_levels: dict[str, Optional[dict[str, pd.Series]]],
    node_temps_meas: dict[str, pd.Series],
    node_spreads: dict[str, float],
    period: str,
    period_months: Optional[tuple[int, ...]],
) -> SpatialValidationReport:
    """
    Compute per-node per-level KPI report for one period.
    """
    report = SpatialValidationReport(
        period=period,
        bc_info={k: v for k, v in bc_info.items() if not isinstance(v, pd.Series)},
        u_multipliers=u_multipliers.copy(),
        metadata={"period_months": list(period_months) if period_months is not None else None},
    )
    path_lengths = compute_path_lengths()

    if period_months is not None:
        hist_p = hist[hist.index.month.isin(period_months)]
    else:
        hist_p = hist
    if len(hist_p) < 24:
        return report

    for node in sorted(NODE_CONSUMERS.keys(), key=lambda n: path_lengths.get(n, 0.0)):
        if node == BC_NODE or node not in node_temps_meas:
            continue
        t_meas_full = node_temps_meas[node]
        t_meas = t_meas_full[t_meas_full.index.isin(hist_p.index)]
        n_valid = int(t_meas.notna().sum())
        n_total = len(t_meas)
        if n_valid < 24:
            continue

        nr = NodeValidationResult(
            node=node,
            path_length_m=float(path_lengths.get(node, 0.0)),
            n_consumers=len(NODE_CONSUMERS.get(node, [])),
            node_type=get_node_type(node),
            n_valid_hours=n_valid,
            coverage_pct=(n_valid / max(n_total, 1)) * 100.0,
            intra_node_spread_C=float(node_spreads.get(node, 0.0)),
            T_meas_mean_C=float(t_meas.dropna().mean()),
            T_meas_std_C=float(t_meas.dropna().std()),
        )

        w = t_meas[t_meas.index.month.isin([12, 1, 2])]
        s = t_meas[t_meas.index.month.isin([6, 7, 8])]
        if int(w.notna().sum()) > 24:
            nr.T_meas_winter_C = float(w.dropna().mean())
        if int(s.notna().sum()) > 24:
            nr.T_meas_summer_C = float(s.dropna().mean())

        for level_name, level_temps in model_levels.items():
            if level_temps is None:
                continue
            t_sim_full = level_temps.get(node)
            if t_sim_full is None:
                continue
            t_sim = t_sim_full[t_sim_full.index.isin(hist_p.index)]
            kpi = compute_kpi_with_uncertainty(t_meas, t_sim)
            if kpi["n_hours"] >= 24:
                nr.level_results[level_name] = kpi

        report.node_results.append(nr)

    _compute_summary(report)
    return report


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _setup_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if AE_RCPARAMS:
        plt.rcParams.update(AE_RCPARAMS)
    return plt


def plot_spatial_profile(
    report: SpatialValidationReport,
    output_dir: Path,
    filename: str,
) -> None:
    """Plot spatial mean temperature profile by path length."""
    plt = _setup_matplotlib()
    fig, ax = plt.subplots(figsize=(6.9, 3.6))

    res = sorted(report.node_results, key=lambda r: r.path_length_m)
    if not res:
        plt.close(fig)
        return

    x = [r.path_length_m for r in res]
    y = [r.T_meas_mean_C for r in res]

    ax.fill_between(
        x,
        [v - SENSOR_UNCERTAINTY_T_C for v in y],
        [v + SENSOR_UNCERTAINTY_T_C for v in y],
        color="0.7",
        alpha=0.2,
        label=f"Measured +/- {SENSOR_UNCERTAINTY_T_C:.1f} C",
    )
    ax.plot(x, y, color="k", lw=1.0, alpha=0.6)
    for r in res:
        if r.node_type == "CAL":
            ax.plot(r.path_length_m, r.T_meas_mean_C, "ks", ms=5, mfc="white", mew=1.2)
        elif r.node_type == "VAL":
            ax.plot(r.path_length_m, r.T_meas_mean_C, "ks", ms=5)
        else:
            ax.plot(r.path_length_m, r.T_meas_mean_C, "kd", ms=4, mfc="0.8")

    ax.plot([], [], "ks", ms=5, label="Measured VAL")
    ax.plot([], [], "ks", ms=5, mfc="white", mew=1.2, label="Measured CAL")

    styles = {
        "L3": ("o", "C0", "-", "L3"),
        "L3+": ("^", "C1", "--", "L3+"),
        "L3^NL": ("D", "C2", ":", "L3^NL"),
    }
    for lvl, (m, c, ls, lab) in styles.items():
        xx: list[float] = []
        yy: list[float] = []
        for r in res:
            if lvl in r.level_results:
                xx.append(r.path_length_m)
                yy.append(r.level_results[lvl]["mean_sim_C"])
        if xx:
            ax.plot(xx, yy, marker=m, color=c, ls=ls, lw=1.1, ms=4.5, label=lab)

    bc = float(report.bc_info.get("median_C") or report.bc_info.get("mean_C") or 86.5)
    ax.axhline(bc, color="0.4", ls="--", lw=0.8, label=f"BC {bc:.1f} C")

    for r in res:
        if r.path_length_m >= 900:
            ax.annotate(
                r.node.replace("j_", "j"),
                (r.path_length_m, r.T_meas_mean_C),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
                fontsize=6.5,
                color="0.35",
            )

    ax.set_xlabel("Cumulative path length from source [m]")
    ax.set_ylabel("Mean supply temperature [C]")
    ax.set_title(f"Spatial temperature profile ({report.period})")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower left", ncol=2, framealpha=0.9)
    fig.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    save_figure_bundle(fig, output_dir / filename)
    plt.close(fig)
    print(f"  [PLOT] {filename}")


def plot_node_error_heatmap(
    hist: pd.DataFrame,
    node_temps_meas: dict[str, pd.Series],
    node_temps_sim: dict[str, pd.Series],
    level_name: str,
    output_dir: Path,
    filename: str,
) -> None:
    """Heatmap: rows nodes, cols months, values MAE [C]."""
    plt = _setup_matplotlib()
    path_lengths = compute_path_lengths()
    nodes = sorted(
        [n for n in NODE_CONSUMERS if n != BC_NODE and n in node_temps_meas and n in node_temps_sim],
        key=lambda n: path_lengths.get(n, 0.0),
    )
    if not nodes:
        return
    mat = np.full((len(nodes), 12), np.nan, dtype=float)

    for i, node in enumerate(nodes):
        tm = node_temps_meas[node]
        ts = node_temps_sim[node]
        idx = tm.dropna().index.intersection(ts.dropna().index)
        if len(idx) < 24:
            continue
        err = (ts.loc[idx] - tm.loc[idx]).abs()
        for m in range(1, 13):
            mask = idx.month == m
            if int(mask.sum()) > 10:
                mat[i, m - 1] = float(err[mask].mean())

    fig, ax = plt.subplots(figsize=(3.35, 4.2))
    im = ax.imshow(mat, aspect="auto", cmap="YlOrRd", vmin=0.0, vmax=3.0)
    ax.set_xticks(range(12))
    ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"], fontsize=7)
    labels = []
    for n in nodes:
        t = get_node_type(n)
        suffix = f" ({t})" if t in ("CAL", "VAL") else ""
        labels.append(f"{n.replace('j_', 'j')}{suffix}")
    ax.set_yticks(range(len(nodes)))
    ax.set_yticklabels(labels, fontsize=6.5)
    ax.set_xlabel("Month")
    ax.set_ylabel("Node (by path length)")
    ax.set_title(f"Node MAE heatmap ({level_name})")
    cbar = fig.colorbar(im, ax=ax, fraction=0.047, pad=0.03)
    cbar.set_label("MAE [C]")
    fig.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    save_figure_bundle(fig, output_dir / filename)
    plt.close(fig)
    print(f"  [PLOT] {filename}")


def plot_level_comparison_scatter(
    report: SpatialValidationReport,
    output_dir: Path,
    filename: str,
) -> None:
    """Scatter MAE_L3 vs MAE_extended with bootstrap error bars."""
    plt = _setup_matplotlib()
    fig, ax = plt.subplots(figsize=(3.35, 3.35))

    points: dict[str, list[dict]] = {"L3+": [], "L3^NL": []}
    max_v = 0.0
    for nr in report.node_results:
        if "L3" not in nr.level_results:
            continue
        k3 = nr.level_results["L3"]
        for ext in ("L3+", "L3^NL"):
            if ext not in nr.level_results:
                continue
            ke = nr.level_results[ext]
            p = {
                "node": nr.node,
                "node_type": nr.node_type,
                "x": k3["MAE_C"],
                "y": ke["MAE_C"],
                "x_lo": k3.get("MAE_CI95_lower_C", k3["MAE_C"]),
                "x_hi": k3.get("MAE_CI95_upper_C", k3["MAE_C"]),
                "y_lo": ke.get("MAE_CI95_lower_C", ke["MAE_C"]),
                "y_hi": ke.get("MAE_CI95_upper_C", ke["MAE_C"]),
            }
            points[ext].append(p)
            max_v = max(max_v, p["x"], p["y"], p["x_hi"], p["y_hi"])

    if max_v <= 0:
        plt.close(fig)
        return
    max_v *= 1.12

    ax.plot([0, max_v], [0, max_v], "k--", lw=0.8, alpha=0.6, label="1:1")
    ax.fill_between([0, max_v], [0, 0], [0, max_v], color="green", alpha=0.05)
    ax.axhline(MAE_FLOOR_C, color="0.5", ls=":", lw=0.8)
    ax.axvline(MAE_FLOOR_C, color="0.5", ls=":", lw=0.8)

    styles = {"L3+": ("^", "C1"), "L3^NL": ("D", "C2")}
    for lvl, arr in points.items():
        if not arr:
            continue
        marker, color = styles[lvl]
        for p in arr:
            xerr = [[p["x"] - p["x_lo"]], [p["x_hi"] - p["x"]]]
            yerr = [[p["y"] - p["y_lo"]], [p["y_hi"] - p["y"]]]
            mfc = color if p["node_type"] == "VAL" else "white"
            ax.errorbar(
                p["x"], p["y"],
                xerr=xerr, yerr=yerr,
                fmt=marker,
                ms=6,
                color=color,
                mfc=mfc,
                mec=color,
                capsize=2,
                elinewidth=0.8,
                lw=0.0,
            )
            ax.annotate(p["node"].replace("j_", "j"), (p["x"], p["y"]), xytext=(3, 3), textcoords="offset points", fontsize=6)
        ax.plot([], [], marker=marker, color=color, lw=0, ms=6, label=lvl)

    ax.set_xlabel("MAE L3 [C]")
    ax.set_ylabel("MAE extended [C]")
    ax.set_xlim(0, max_v)
    ax.set_ylim(0, max_v)
    ax.set_aspect("equal")
    ax.set_title("Level comparison")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", framealpha=0.9)
    fig.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    save_figure_bundle(fig, output_dir / filename)
    plt.close(fig)
    print(f"  [PLOT] {filename}")


def plot_validation_timeseries(
    hist: pd.DataFrame,
    node_temps_meas: dict[str, pd.Series],
    model_levels: dict[str, Optional[dict[str, pd.Series]]],
    node: str,
    period_slice: slice,
    output_dir: Path,
    filename: str,
) -> None:
    """Plot measured vs simulated timeseries and absolute error for one node."""
    if node not in node_temps_meas:
        return
    plt = _setup_matplotlib()
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(6.9, 3.8), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.0]}
    )

    tm = node_temps_meas[node].loc[period_slice]
    if tm.empty:
        plt.close(fig)
        return
    ax1.plot(tm.index, tm.values, color="k", lw=1.1, label="Measured")

    colors = {"L3": "C0", "L3+": "C1", "L3^NL": "C2"}
    styles = {"L3": "-", "L3+": "--", "L3^NL": ":"}
    for lvl, node_map in model_levels.items():
        if node_map is None or node not in node_map:
            continue
        ts = node_map[node].loc[period_slice]
        if ts.empty:
            continue
        ax1.plot(ts.index, ts.values, color=colors.get(lvl, "C3"), ls=styles.get(lvl, "-"), lw=1.0, label=lvl)
        idx = tm.dropna().index.intersection(ts.dropna().index)
        if len(idx) > 0:
            err = (ts.loc[idx] - tm.loc[idx]).abs()
            ax2.plot(idx, err, color=colors.get(lvl, "C3"), ls=styles.get(lvl, "-"), lw=0.9, label=f"|err| {lvl}")

    start = tm.index.min().normalize()
    end = tm.index.max().normalize() + pd.Timedelta(days=1)
    t = start
    while t < end:
        ax1.axvspan(t, t + pd.Timedelta(hours=6), color="0.92", zorder=0)
        ax2.axvspan(t, t + pd.Timedelta(hours=6), color="0.92", zorder=0)
        t += pd.Timedelta(days=1)

    ax1.set_ylabel("T_supply [C]")
    ax1.set_title(f"Timeseries validation at {node.replace('j_', 'j')}")
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="best", ncol=2)

    ax2.set_ylabel("|error| [C]")
    ax2.set_xlabel("Time")
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="best", ncol=3, fontsize=6.5)

    fig.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    save_figure_bundle(fig, output_dir / filename)
    plt.close(fig)
    print(f"  [PLOT] {filename}")


# ---------------------------------------------------------------------------
# Reports and exports
# ---------------------------------------------------------------------------

def generate_validation_table_latex(
    report: SpatialValidationReport,
    output_dir: Path,
    filename: str = "spatial_validation_table.tex",
) -> str:
    """Generate LaTeX table for paper."""
    levels_pref = ["L3", "L3+", "L3^NL"]
    levels = [l for l in levels_pref if any(l in nr.level_results for nr in report.node_results)]
    col_spec = "@{} l r c r " + " ".join(["r"] * len(levels)) + " c @{}"
    lines = [
        r"\begin{table*}[!htbp]",
        r"\centering",
        (
            r"\caption{Spatial temperature validation results ("
            + report.period
            + r" period). Calibration nodes (CAL) are branch terminals; "
            r"validation nodes (VAL) are independent trunk targets. "
            + rf"Sensor accuracy: $\pm$\SI{{{SENSOR_UNCERTAINTY_T_C:.1f}}}{{\celsius}}; "
            + rf"MAE floor: \SI{{{MAE_FLOOR_C:.2f}}}{{\celsius}}.}}"
        ),
        r"\label{tab:spatial_validation}",
        r"\small",
        rf"\begin{{tabular}}{{{col_spec}}}",
        r"\toprule",
        "Node & Path\\,[m] & Type & $\\bar{T}_{\\mathrm{meas}}$\\,[\\si{\\celsius}] & "
        + " & ".join([rf"MAE$_{{\mathrm{{{lvl}}}}}$\\,[\\si{{\\celsius}}]" for lvl in levels])
        + r" & Signif.? \\",
        r"\midrule",
    ]

    for nr in sorted(report.node_results, key=lambda r: r.path_length_m):
        node_label = nr.node.replace("j_", "j$_{") + "}$"
        row = f"{node_label} & {nr.path_length_m:.0f} & {nr.node_type} & {nr.T_meas_mean_C:.1f}"
        any_sig = False
        for lvl in levels:
            kpi = nr.level_results.get(lvl)
            if not kpi:
                row += " & --"
                continue
            mae = kpi["MAE_C"]
            lo = kpi.get("MAE_CI95_lower_C", mae)
            hi = kpi.get("MAE_CI95_upper_C", mae)
            row += f" & {mae:.2f}\\,({lo:.2f}--{hi:.2f})"
            if bool(kpi.get("significant", False)):
                any_sig = True
        sig_marker = "$\\ast$" if any_sig else "--"
        row += f" & {sig_marker} \\\\"
        lines.append(row)

    lines.append(r"\midrule")
    row_val = r"\multicolumn{3}{@{}l}{\textbf{Mean (VAL nodes)}} & --"
    row_all = r"\multicolumn{3}{@{}l}{\textbf{Mean (all nodes)}} & --"
    for lvl in levels:
        val_mae = [nr.level_results[lvl]["MAE_C"] for nr in report.node_results if nr.node_type == "VAL" and lvl in nr.level_results]
        all_mae = [nr.level_results[lvl]["MAE_C"] for nr in report.node_results if lvl in nr.level_results]
        row_val += f" & {np.mean(val_mae):.2f}" if val_mae else " & --"
        row_all += f" & {np.mean(all_mae):.2f}" if all_mae else " & --"
    row_cal = r"\multicolumn{3}{@{}l}{\textbf{Mean (CAL nodes)}} & --"
    for lvl in levels:
        cal_mae = [nr.level_results[lvl]["MAE_C"] for nr in report.node_results if nr.node_type == "CAL" and lvl in nr.level_results]
        row_cal += f" & {np.mean(cal_mae):.2f}" if cal_mae else " & --"
    row_val += r" & -- \\"
    row_cal += r" & -- \\"
    row_all += r" & -- \\"
    lines.extend([row_val, row_cal, row_all, r"\bottomrule", r"\end{tabular}", ""])
    lines.extend(
        [
            r"\vspace{2pt}",
            r"\raggedright\footnotesize",
            (
                r"Values in parentheses are 95\,\% bootstrap CIs. "
                + rf"$\ast$ denotes MAE > \SI{{{2.0 * SENSOR_UNCERTAINTY_T_C:.1f}}}{{\celsius}} "
                + r"(model error exceeds sensor-noise band)."
            ),
            r"\end{table*}",
        ]
    )

    txt = "\n".join(lines)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / filename).write_text(txt, encoding="utf-8")
    print(f"  [TEX] {filename}")
    return txt


def export_kpis_json(
    report: SpatialValidationReport,
    output_dir: Path,
    filename: str,
) -> None:
    """Export complete report KPI payload to JSON."""
    summary = report.summary if isinstance(report.summary, dict) else {}
    data = {
        "period": report.period,
        "methodology": {
            "calibration_nodes": sorted(CALIBRATION_NODES),
            "validation_nodes": sorted(VALIDATION_NODES),
            "calibration_months": list(TRAIN_MONTHS),
            "test_months": list(TEST_MONTHS),
            "sensor_uncertainty_C": SENSOR_UNCERTAINTY_T_C,
            "mae_floor_C": float(MAE_FLOOR_C),
            "bootstrap_n": N_BOOTSTRAP,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "bc_info": report.bc_info,
        "u_multipliers": report.u_multipliers,
        "summary": {k: v for k, v in summary.items() if isinstance(v, dict)},
        "improvement": {
            "L3_to_L3plus_pct": summary.get("improvement_L3_to_L3plus_pct"),
            "L3_to_L3NL_pct": summary.get("improvement_L3_to_L3NL_pct"),
            "L3plus_to_L3NL_pct": summary.get("improvement_L3plus_to_L3NL_pct"),
        },
        "metadata": report.metadata,
        "nodes": [],
    }
    for nr in sorted(report.node_results, key=lambda r: r.path_length_m):
        data["nodes"].append(
            {
                "node": nr.node,
                "path_length_m": nr.path_length_m,
                "type": nr.node_type,
                "n_consumers": nr.n_consumers,
                "n_valid_hours": nr.n_valid_hours,
                "coverage_pct": nr.coverage_pct,
                "intra_node_spread_C": nr.intra_node_spread_C,
                "T_meas_mean_C": nr.T_meas_mean_C,
                "T_meas_std_C": nr.T_meas_std_C,
                "T_meas_winter_C": nr.T_meas_winter_C,
                "T_meas_summer_C": nr.T_meas_summer_C,
                "level_results": nr.level_results,
            }
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / filename).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  [JSON] {filename}")


def generate_validation_report_md(
    reports: dict[str, SpatialValidationReport],
    output_dir: Path,
    filename: str = "validation_report.md",
) -> str:
    """Generate markdown report."""
    lines = [
        "### Spatial Temperature Validation Report",
        "",
        f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "#### Summary",
        "- Validated nodes: 14 / 15 (j_1 is boundary condition)",
        f"- Calibration nodes: {sorted(CALIBRATION_NODES)}",
        f"- Validation nodes: {sorted(VALIDATION_NODES)}",
        f"- Calibration months: {list(TRAIN_MONTHS)}",
        f"- Test months: {list(TEST_MONTHS)}",
        f"- Sensor uncertainty: +/-{SENSOR_UNCERTAINTY_T_C:.1f} C",
        f"- MAE floor: {MAE_FLOOR_C:.2f} C",
        "",
    ]
    test = reports.get("test")
    if test and test.summary:
        levels = [k for k, v in test.summary.items() if isinstance(v, dict)]
        lines.extend(
            [
                "#### Key Results (Test Period, VAL nodes)",
                "",
                "| Level | Mean MAE [C] | Max MAE [C] | Improvement vs L3 |",
                "|---|---:|---:|---:|",
            ]
        )
        base = test.summary.get("L3", {}).get("mean_MAE_VAL_C")
        for lvl in levels:
            st = test.summary[lvl]
            mean_v = st.get("mean_MAE_VAL_C")
            max_v = st.get("max_MAE_VAL_C", st.get("max_MAE_C"))
            if mean_v is None:
                continue
            impr = "-"
            if lvl != "L3" and base and base > 0:
                impr = f"{(mean_v - base) / base * 100.0:+.1f}%"
            lines.append(f"| {lvl} | {mean_v:.3f} | {max_v:.3f} | {impr} |")

        lines.extend(
            [
                "",
                "#### Pass/Fail (target: max MAE <= 1.5 C on VAL nodes)",
                "",
            ]
        )
        for lvl in levels:
            st = test.summary[lvl]
            max_v = st.get("max_MAE_VAL_C", st.get("max_MAE_C"))
            if max_v is None:
                continue
            status = "PASS" if max_v <= MAX_MAE_TARGET_C else "FAIL"
            lines.append(f"- {lvl}: {status} (max MAE = {max_v:.3f} C)")

    lines.extend(
        [
            "",
            "#### Limitations",
            "1. Pre-upgrade data only (no HP/TES operation in measurement period).",
            "2. Spatial validation primarily validates pipe-physics consistency.",
            "3. If solver-level node temperatures are missing, that level is excluded and this is explicitly reported.",
        ]
    )
    txt = "\n".join(lines)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / filename).write_text(txt, encoding="utf-8")
    print(f"  [MD] {filename}")
    return txt


# Backward alias
generate_report_md = generate_validation_report_md


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def _pick_winter_week_slice(hist: pd.DataFrame) -> Optional[slice]:
    """Pick a representative 7-day winter slice for timeseries plot."""
    winter_idx = hist.index[hist.index.month.isin([12, 1, 2])]
    if len(winter_idx) < 24 * 3:
        return None
    start = winter_idx.min()
    end = start + pd.Timedelta(days=7)
    return slice(start, end)


def run_spatial_validation(
    plot_only: bool = False,
    skip_calibration: bool = False,
) -> dict:
    """
    Run complete multi-node spatial validation pipeline.
    """
    print("\n" + "=" * 70)
    print("  MULTI-NODE SPATIAL TEMPERATURE VALIDATION")
    print("=" * 70)

    if plot_only:
        print("  [INFO] --plot-only currently reuses full pipeline computations.")

    print("\n[1/12] Load historical data")
    hist = load_historical(DATA_PATH, resample_to_1h=True)

    print("\n[2/12] Extract boundary condition")
    bc_info = extract_supply_temperature_bc(hist)
    bc_series = _get_bc_series(hist, bc_info)

    print("\n[3/12] Extract measured node supply temperatures")
    node_temps_meas, node_spreads = get_measured_node_temperatures(hist)
    if BC_NODE in node_temps_meas:
        print(f"       BC node {BC_NODE} coverage: {node_temps_meas[BC_NODE].notna().mean()*100:.1f}%")

    print("\n[4/12] Extract measured return temperatures")
    node_ret_temps = get_measured_return_temperatures(hist)
    print(f"       Return temperatures available for {len(node_ret_temps)} nodes")

    print("\n[5/12] Temporal train/test split")
    hist_train = hist[hist.index.month.isin(TRAIN_MONTHS)]
    hist_test = hist[hist.index.month.isin(TEST_MONTHS)]
    print(f"       Train hours: {len(hist_train)}")
    print(f"       Test hours:  {len(hist_test)}")

    print("\n[6/12] Calibrate U multipliers on CAL x TRAIN")
    if skip_calibration:
        u_mult = {pid: 1.0 for pid in PIPE_CATALOG}
        print("       [SKIP] Using nominal multipliers")
    else:
        u_mult = calibrate_u_values_independent(hist_train, node_temps_meas, node_ret_temps, bc_series)

    print("\n[7/12] Reconstruct L3 node temperatures")
    l3_temps = reconstruct_node_temperatures_L3(hist, bc_series, u_mult, node_temps_meas, node_ret_temps)

    print("\n[8/12] Extract L3+ / L3^NL node temperatures")
    l3plus_temps = extract_optimization_node_temps(L3PLUS_DIR, "L3+")
    l3nl_temps = extract_optimization_node_temps(L3NL_DIR, "L3^NL")

    level_source = {"L3": "reconstruction"}
    model_levels: dict[str, Optional[dict[str, pd.Series]]] = {
        "L3": l3_temps,
    }
    if l3plus_temps is None:
        level_source["L3+"] = "missing_excluded"
        print("       [NOTE] L3+ missing, excluded from level comparison")
    else:
        level_source["L3+"] = "solver_output"
        model_levels["L3+"] = l3plus_temps

    if l3nl_temps is None:
        level_source["L3^NL"] = "missing_excluded"
        print("       [NOTE] L3^NL missing, excluded from level comparison")
    else:
        level_source["L3^NL"] = "solver_or_miqp_output"
        model_levels["L3^NL"] = l3nl_temps

    print(f"       Levels ready: {list(model_levels.keys())}")

    print("\n[9/12] Compute KPIs for full/train/test")
    reports: dict[str, SpatialValidationReport] = {}
    reports["full"] = validate_spatial_temperature_profile(
        hist=hist,
        bc_info=bc_info,
        u_multipliers=u_mult,
        model_levels=model_levels,
        node_temps_meas=node_temps_meas,
        node_spreads=node_spreads,
        period="full",
        period_months=None,
    )
    reports["train"] = validate_spatial_temperature_profile(
        hist=hist,
        bc_info=bc_info,
        u_multipliers=u_mult,
        model_levels=model_levels,
        node_temps_meas=node_temps_meas,
        node_spreads=node_spreads,
        period="train",
        period_months=TRAIN_MONTHS,
    )
    reports["test"] = validate_spatial_temperature_profile(
        hist=hist,
        bc_info=bc_info,
        u_multipliers=u_mult,
        model_levels=model_levels,
        node_temps_meas=node_temps_meas,
        node_spreads=node_spreads,
        period="test",
        period_months=TEST_MONTHS,
    )
    for key, rep in reports.items():
        rep.metadata["level_source"] = level_source.copy()

    print("\n[10/12] Statistical significance already included in node KPIs")

    print("\n[11/12] Generate plots")
    for period_name, rep in reports.items():
        if rep.node_results:
            plot_spatial_profile(rep, OUT_DIR, f"spatial_profile_{period_name}")

    plot_node_error_heatmap(
        hist=hist,
        node_temps_meas=node_temps_meas,
        node_temps_sim=l3_temps,
        level_name="L3",
        output_dir=OUT_DIR,
        filename="node_error_heatmap_L3",
    )

    test_rep = reports.get("test")
    if test_rep and test_rep.node_results:
        plot_level_comparison_scatter(test_rep, OUT_DIR, "level_comparison_scatter")

    winter_slice = _pick_winter_week_slice(hist)
    if winter_slice is not None:
        plot_validation_timeseries(
            hist=hist,
            node_temps_meas=node_temps_meas,
            model_levels=model_levels,
            node="j_15",
            period_slice=winter_slice,
            output_dir=OUT_DIR,
            filename="validation_timeseries_winter",
        )

    print("\n[12/12] Export LaTeX/JSON/Markdown")
    if test_rep and test_rep.node_results:
        generate_validation_table_latex(test_rep, OUT_DIR, "spatial_validation_table.tex")
    for period_name, rep in reports.items():
        export_kpis_json(rep, OUT_DIR, f"kpis_spatial_{period_name}.json")
    generate_validation_report_md(reports, OUT_DIR, "validation_report.md")

    # Pass/fail on test VAL nodes
    all_pass = True
    if test_rep and isinstance(test_rep.summary, dict):
        for lvl, stats in test_rep.summary.items():
            if not isinstance(stats, dict):
                continue
            max_val = stats.get("max_MAE_VAL_C")
            if max_val is None:
                continue
            ok = bool(max_val <= MAX_MAE_TARGET_C)
            all_pass = all_pass and ok
            status = "PASS" if ok else "FAIL"
            print(f"  {lvl:>6}: max MAE VAL = {max_val:.3f} C -> {status}")
    else:
        all_pass = False
        print("  [WARN] No test summary available")

    print("=" * 70)
    return {
        "reports": reports,
        "u_multipliers": u_mult,
        "bc_info": {k: v for k, v in bc_info.items() if not isinstance(v, pd.Series)},
        "node_count": max(0, len([n for n in node_temps_meas if n != BC_NODE])),
        "model_levels_available": list(model_levels.keys()),
        "pass": all_pass,
    }


def main() -> int:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Spatial node temperature validation")
    parser.add_argument("--plot-only", action="store_true", help="Regenerate outputs")
    parser.add_argument("--no-calibrate", action="store_true", help="Skip U calibration")
    args = parser.parse_args()

    result = run_spatial_validation(
        plot_only=args.plot_only,
        skip_calibration=args.no_calibrate,
    )
    return 0 if result.get("pass", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())

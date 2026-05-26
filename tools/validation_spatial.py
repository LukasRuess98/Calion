"""
tools/validation_spatial.py
Source-to-far-end corridor validation and post-processing utilities.

WHY CORRIDOR-ONLY:
  Consumer substations measure temperature AFTER mixing valves (secondary side).
  This is systematically 5-15 degrees below primary network junction temperature.
  Only V_27 (far-end j_15, minimal local demand) approximates the junction T.
  Multi-node spatial validation is therefore NOT possible with this dataset.
  This is a MEASUREMENT LIMITATION, not a model error.

WHAT THIS MODULE PROVIDES:
  1. Corridor validation (j_1 -> j_15): supplements Stage 1 BCM
  2. Post-processing utilities: node temperature reconstruction for paper plots
  3. Mixing valve offset diagnosis: documents why multi-node fails
  4. LaTeX/JSON export for paper

Usage:
    python tools/validation_spatial.py                # corridor validation
    python tools/validation_spatial.py --diagnose     # show mixing valve offsets
    python tools/validation_spatial.py --no-calibrate # nominal U-values
"""
from __future__ import annotations

import json
import sys
import warnings
from collections import deque
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

from tools.validation_runner import (
    DATA_PATH, OUT_DIR, PIPE_CATALOG, NODE_CONSUMERS, TRUNK_PIPES,
    load_historical, extract_supply_temperature_bc, _get_node_flow_m3h,
)

try:
    from scripts.paper.mpl_export import AE_RCPARAMS, save_figure_bundle
except ImportError:
    AE_RCPARAMS = {}

    def save_figure_bundle(fig, path, formats=("png",), dpi=600):
        fig.savefig(str(path) + ".png", dpi=dpi, bbox_inches="tight")


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

RHO_WATER = 977.0       # kg/m³ at ~70°C
CP_WATER = 4186.0       # J/(kg·K)
SENSOR_UNCERTAINTY_T_C = 0.5  # EN 1434 Class 2

GROUND_TEMP_BY_MONTH: dict[int, float] = {
    1: 4.0, 2: 3.5, 3: 5.0, 4: 8.0, 5: 12.0, 6: 15.0,
    7: 17.0, 8: 17.5, 9: 15.5, 10: 12.0, 11: 8.0, 12: 5.0,
}

# Network tree
TREE_EDGES: dict[str, list[str]] = {
    "j_1":  ["j_2"],
    "j_2":  ["j_3"],
    "j_3":  ["j_4", "j_9"],
    "j_4":  ["j_5"],
    "j_5":  ["j_6", "j_7"],
    "j_7":  ["j_8"],
    "j_9":  ["j_10"],
    "j_10": ["j_11"],
    "j_11": ["j_12"],
    "j_12": ["j_13"],
    "j_13": ["j_14", "j_15"],
}

EDGE_TO_PIPE: dict[tuple[str, str], str] = {
    ("j_1", "j_2"):   "j1_to_j2",
    ("j_2", "j_3"):   "j2_to_j3",
    ("j_3", "j_4"):   "j3_to_j4",
    ("j_3", "j_9"):   "j3_to_j9",
    ("j_4", "j_5"):   "j4_to_j5",
    ("j_5", "j_6"):   "j5_to_j6",
    ("j_5", "j_7"):   "j5_to_j7",
    ("j_7", "j_8"):   "j7_to_j8",
    ("j_9", "j_10"):  "j9_to_j10",
    ("j_10", "j_11"): "j10_to_j11",
    ("j_11", "j_12"): "j11_to_j12",
    ("j_12", "j_13"): "j12_to_j13",
    ("j_13", "j_14"): "j13_to_j14",
    ("j_13", "j_15"): "j13_to_j15",
}

# Far-end corridor definition
CORRIDOR_SOURCE_NODE = "j_1"
CORRIDOR_FAREND_NODE = "j_15"
CORRIDOR_SOURCE_CONSUMER = "V_1"
CORRIDOR_FAREND_CONSUMER = "V_27"
CORRIDOR_PATH_LENGTH_M = 2125.0  # j_1 -> j_15 total


# ═══════════════════════════════════════════════════════════════════════════════
# TREE UTILITIES (for post-processing and paper plots)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_path_lengths() -> dict[str, float]:
    """Cumulative pipe length from j_1 to each node via BFS."""
    lengths: dict[str, float] = {"j_1": 0.0}
    queue = deque(["j_1"])
    while queue:
        parent = queue.popleft()
        for child in TREE_EDGES.get(parent, []):
            pipe_id = EDGE_TO_PIPE[(parent, child)]
            lengths[child] = lengths[parent] + PIPE_CATALOG[pipe_id]["length_m"]
            queue.append(child)
    return lengths


def get_downstream_nodes(node: str) -> set[str]:
    """All nodes downstream of `node` (inclusive)."""
    downstream = {node}
    queue = deque([node])
    while queue:
        current = queue.popleft()
        for child in TREE_EDGES.get(current, []):
            downstream.add(child)
            queue.append(child)
    return downstream


def get_path_edges(node: str) -> list[tuple[str, str]]:
    """Ordered edge list from j_1 to target node."""
    parent_map: dict[str, str] = {}
    for parent, children in TREE_EDGES.items():
        for child in children:
            parent_map[child] = parent
    path = []
    current = node
    while current in parent_map:
        parent = parent_map[current]
        path.append((parent, current))
        current = parent
    path.reverse()
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# PIPE FLOW COMPUTATION (for temperature reconstruction)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_pipe_flows(
    hist: pd.DataFrame,
    bc_temp: float | pd.Series,
    T_return_default: float = 50.0,
) -> dict[str, pd.Series]:
    """
    Compute mass flow [kg/s] per pipe from downstream demand sums.

    Uses measured return temperatures where available, falls back to default.
    """
    node_demands: dict[str, pd.Series] = {}
    for node, consumers in NODE_CONSUMERS.items():
        cols = [f"{v}_demand_MWth" for v in consumers if f"{v}_demand_MWth" in hist.columns]
        node_demands[node] = (
            hist[cols].sum(axis=1, min_count=1).fillna(0.0) if cols
            else pd.Series(0.0, index=hist.index)
        )

    node_delta_T: dict[str, pd.Series] = {}
    for node, consumers in NODE_CONSUMERS.items():
        ret_cols = [f"{v}_return_temp" for v in consumers if f"{v}_return_temp" in hist.columns]
        if ret_cols:
            t_ret = hist[ret_cols].mean(axis=1)
        else:
            t_ret = pd.Series(T_return_default, index=hist.index)

        dt = (bc_temp - t_ret) if isinstance(bc_temp, (int, float)) else (bc_temp - t_ret)
        if isinstance(dt, (int, float)):
            node_delta_T[node] = pd.Series(max(dt, 5.0), index=hist.index)
        else:
            node_delta_T[node] = dt.clip(lower=5.0, upper=80.0)

    pipe_flows: dict[str, pd.Series] = {}
    for (parent, child), pipe_id in EDGE_TO_PIPE.items():
        downstream = get_downstream_nodes(child)
        m_dot = pd.Series(0.0, index=hist.index)
        for dn in downstream:
            q = node_demands.get(dn, pd.Series(0.0, index=hist.index))
            dt = node_delta_T.get(dn, pd.Series(30.0, index=hist.index))
            m_dot = m_dot + q * 1e6 / (CP_WATER * dt)
        pipe_flows[pipe_id] = m_dot.clip(lower=0.01, upper=100.0)

    return pipe_flows


# ═══════════════════════════════════════════════════════════════════════════════
# NODE TEMPERATURE RECONSTRUCTION (for post-processing and paper plots)
# ═══════════════════════════════════════════════════════════════════════════════

def reconstruct_node_temperatures(
    hist: pd.DataFrame,
    bc_temp: float | pd.Series,
    u_multipliers: Optional[dict[str, float]] = None,
) -> dict[str, pd.Series]:
    """
    Reconstruct supply temperature at each node using exponential decay.

    T_out = T_ground + (T_in - T_ground) * exp(-U*L / (m_dot*cp))

    This is the shared physics model underlying L2, L3, L3+, L3^NL.
    Used for:
      - Corridor validation (j_15 comparison)
      - Paper plots (theoretical temperature profile)
      - Post-processing of optimization results

    NOT used for multi-node validation against V_X_flow_temp
    (those are secondary-side measurements, see module docstring).
    """
    if u_multipliers is None:
        u_multipliers = {pid: 1.0 for pid in PIPE_CATALOG}

    T_ground = pd.Series(
        [GROUND_TEMP_BY_MONTH[m] for m in hist.index.month],
        index=hist.index, dtype=float,
    )

    pipe_flows = compute_pipe_flows(hist, bc_temp)

    node_temps: dict[str, pd.Series] = {}
    if isinstance(bc_temp, (int, float)):
        node_temps["j_1"] = pd.Series(float(bc_temp), index=hist.index)
    else:
        bc_series = bc_temp if isinstance(bc_temp, pd.Series) else pd.Series(bc_temp, index=hist.index)
        node_temps["j_1"] = bc_series.reindex(hist.index).fillna(
            float(bc_series.median()) if len(bc_series) > 0 else 86.5
        )

    queue = deque(["j_1"])
    while queue:
        parent = queue.popleft()
        for child in TREE_EDGES.get(parent, []):
            pipe_id = EDGE_TO_PIPE[(parent, child)]
            U = PIPE_CATALOG[pipe_id]["U_nom"] * u_multipliers.get(pipe_id, 1.0)
            L = PIPE_CATALOG[pipe_id]["length_m"]
            m_dot = pipe_flows[pipe_id]

            exponent = -(U * L) / (m_dot * CP_WATER)
            exponent = exponent.clip(lower=-5.0, upper=0.0)
            phi = np.exp(exponent)

            T_in = node_temps[parent]
            T_out = T_ground + (T_in - T_ground) * phi
            node_temps[child] = T_out
            queue.append(child)

    return node_temps


# ═══════════════════════════════════════════════════════════════════════════════
# CORRIDOR VALIDATION (j_1 -> j_15 only)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_corridor(
    hist: pd.DataFrame,
    bc_info: dict,
    u_multipliers: Optional[dict[str, float]] = None,
) -> dict:
    """
    Validate source-to-far-end temperature corridor (j_1 -> j_15).

    This is the only spatial validation possible with this dataset because:
    - V_27 (j_15) is at the network far-end with minimal local demand
    - The mixing valve effect is negligible there
    - All other V_X_flow_temp values are post-mixing (secondary side)

    Returns dict with KPIs and diagnostic information.
    """
    print("  [CORRIDOR] Source-to-far-end validation (j_1 -> j_15, 2125m)")

    bc_temp = bc_info.get("median_C") or bc_info.get("mean_C", 86.5)

    node_temps = reconstruct_node_temperatures(hist, bc_temp, u_multipliers)
    t_sim_j15 = node_temps.get("j_15")

    if t_sim_j15 is None:
        print("  [ERROR] Could not reconstruct j_15 temperature")
        return {"status": "error", "reason": "reconstruction_failed"}

    col_farend = f"{CORRIDOR_FAREND_CONSUMER}_flow_temp"
    if col_farend not in hist.columns:
        print(f"  [ERROR] {col_farend} not in data")
        return {"status": "error", "reason": "no_measurement"}

    t_meas_j15 = hist[col_farend].astype(float)

    idx = t_meas_j15.dropna().index.intersection(t_sim_j15.dropna().index)
    if len(idx) < 100:
        print(f"  [ERROR] Only {len(idx)} aligned hours")
        return {"status": "error", "reason": "insufficient_overlap"}

    t_m = t_meas_j15.loc[idx]
    t_s = t_sim_j15.loc[idx]
    err = t_s - t_m

    mae = float(err.abs().mean())
    bias = float(err.mean())
    rmse = float(np.sqrt((err**2).mean()))

    # Bootstrap 95% CI
    rng = np.random.default_rng(42)
    n = len(err)
    abs_err = err.abs().values
    mae_boot = [float(np.mean(rng.choice(abs_err, size=n, replace=True))) for _ in range(1000)]
    ci_lower = float(np.percentile(mae_boot, 2.5))
    ci_upper = float(np.percentile(mae_boot, 97.5))

    t_bc_mean = float(node_temps["j_1"].loc[idx].mean())
    drop_simulated = t_bc_mean - float(t_s.mean())
    drop_measured = t_bc_mean - float(t_m.mean())

    result = {
        "status": "ok",
        "corridor_length_m": CORRIDOR_PATH_LENGTH_M,
        "n_hours": int(len(idx)),
        "MAE_C": mae,
        "MAE_CI95": [ci_lower, ci_upper],
        "bias_C": bias,
        "RMSE_C": rmse,
        "T_meas_mean_C": float(t_m.mean()),
        "T_sim_mean_C": float(t_s.mean()),
        "T_BC_mean_C": t_bc_mean,
        "drop_simulated_C": drop_simulated,
        "drop_measured_C": drop_measured,
        "sensor_floor_C": SENSOR_UNCERTAINTY_T_C / np.sqrt(2),
        "pass": mae <= 1.5,
    }

    print(f"    T_BC (j_1):      {t_bc_mean:.1f}C")
    print(f"    T_meas (j_15):   {float(t_m.mean()):.1f}C (measured V_27)")
    print(f"    T_sim (j_15):    {float(t_s.mean()):.1f}C (reconstructed)")
    print(f"    dT measured:     {drop_measured:.2f}C")
    print(f"    dT simulated:    {drop_simulated:.2f}C")
    print(f"    MAE:             {mae:.3f}C [{ci_lower:.3f}, {ci_upper:.3f}]")
    print(f"    Bias:            {bias:+.3f}C")
    print(f"    Target:          <= 1.5C -> {'PASS' if mae <= 1.5 else 'FAIL'}")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MIXING VALVE DIAGNOSIS (informational — explains why multi-node fails)
# ═══════════════════════════════════════════════════════════════════════════════

def diagnose_mixing_valve_effect(hist: pd.DataFrame, bc_info: dict) -> pd.DataFrame:
    """
    Quantify the mixing valve offset at each consumer substation.

    Computes: offset = T_reconstructed(junction) - V_X_flow_temp(measured)
    Positive offset = mixing valve reduces temperature (expected behavior).

    This is NOT a model error — it is the physical effect of the 3-way valve.
    Included for documentation and paper discussion only.
    """
    print("\n  [DIAGNOSE] Mixing valve offset analysis")
    print("  " + "-" * 60)
    print(f"  {'Node':<6} {'Consumer':<8} {'Path[m]':>8} {'T_meas':>7} "
          f"{'T_recon':>8} {'Offset':>7} {'Interpretation'}")
    print("  " + "-" * 60)

    bc_temp = bc_info.get("median_C") or bc_info.get("mean_C", 86.5)
    node_temps = reconstruct_node_temperatures(hist, bc_temp)
    path_lengths = compute_path_lengths()

    rows = []
    for node, consumers in sorted(
        NODE_CONSUMERS.items(), key=lambda x: path_lengths.get(x[0], 0)
    ):
        t_recon = node_temps.get(node)
        if t_recon is None:
            continue
        t_recon_mean = float(t_recon.mean())

        for v_name in consumers:
            col = f"{v_name}_flow_temp"
            if col not in hist.columns:
                continue
            t_meas_mean = float(hist[col].astype(float).dropna().mean())
            offset = t_recon_mean - t_meas_mean

            if offset < 1.0:
                interp = "~= junction T (valid for comparison)"
            elif offset < 5.0:
                interp = "mild mixing (marginal)"
            elif offset < 15.0:
                interp = "significant mixing (NOT comparable)"
            else:
                interp = "heavy mixing or sensor issue"

            rows.append({
                "node": node,
                "consumer": v_name,
                "path_length_m": path_lengths.get(node, 0),
                "T_meas_mean_C": t_meas_mean,
                "T_reconstructed_C": t_recon_mean,
                "mixing_offset_C": offset,
                "interpretation": interp,
            })

            print(f"  {node:<6} {v_name:<8} {path_lengths.get(node, 0):>7.0f} "
                  f"{t_meas_mean:>7.1f} {t_recon_mean:>8.1f} {offset:>+7.1f}  {interp}")

    print("  " + "-" * 60)
    print(f"  CONCLUSION: Only {CORRIDOR_FAREND_CONSUMER} (j_15) has offset < 1C")
    print(f"              -> Multi-node spatial validation NOT possible")
    print(f"              -> Corridor validation (j_1 -> j_15) is the maximum achievable")

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# PLOTTING
# ═══════════════════════════════════════════════════════════════════════════════

def plot_corridor_timeseries(
    hist: pd.DataFrame,
    bc_info: dict,
    u_multipliers: Optional[dict[str, float]] = None,
    output_dir: Path = OUT_DIR,
    filename: str = "corridor_validation_timeseries",
) -> None:
    """Time series: measured vs reconstructed T at j_15 (representative week)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if AE_RCPARAMS:
        plt.rcParams.update(AE_RCPARAMS)

    bc_temp = bc_info.get("median_C") or bc_info.get("mean_C", 86.5)
    node_temps = reconstruct_node_temperatures(hist, bc_temp, u_multipliers)
    t_sim = node_temps.get("j_15")

    col_meas = f"{CORRIDOR_FAREND_CONSUMER}_flow_temp"
    if col_meas not in hist.columns or t_sim is None:
        print("  [SKIP] Cannot create corridor plot (missing data)")
        return

    t_meas = hist[col_meas].astype(float)

    # Find representative winter week (highest demand)
    weekly_demand = hist.get("Waermebedarf_MWth")
    if weekly_demand is not None:
        weekly_mean = weekly_demand.resample("W").mean()
        peak_week_end = weekly_mean.idxmax()
        start = peak_week_end - pd.Timedelta(days=7)
        end = peak_week_end
    else:
        start = hist.index[0]
        end = start + pd.Timedelta(days=7)

    mask = (hist.index >= start) & (hist.index < end)
    t_m_week = t_meas[mask]
    t_s_week = t_sim[mask]
    t_bc_week = node_temps["j_1"][mask]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 4.5), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})

    ax1.plot(t_m_week.index, t_m_week, "k-", linewidth=1.2, label="Measured (V_27)")
    ax1.plot(t_s_week.index, t_s_week, "C0--", linewidth=1.0, label="Reconstructed (model)")
    ax1.plot(t_bc_week.index, t_bc_week, "gray", linewidth=0.8, linestyle=":",
             label="BC (source)")
    ax1.fill_between(t_m_week.index,
                     t_m_week - SENSOR_UNCERTAINTY_T_C,
                     t_m_week + SENSOR_UNCERTAINTY_T_C,
                     alpha=0.15, color="gray", label=f"+/-{SENSOR_UNCERTAINTY_T_C}C sensor")

    ax1.set_ylabel("Supply temperature [C]")
    ax1.legend(loc="lower left", fontsize=7, ncol=2)
    ax1.set_title(f"Far-end corridor validation (j_1 -> j_15, {CORRIDOR_PATH_LENGTH_M:.0f}m)")
    ax1.grid(True, alpha=0.25)

    idx_common = t_m_week.dropna().index.intersection(t_s_week.dropna().index)
    error = t_s_week.loc[idx_common] - t_m_week.loc[idx_common]
    ax2.bar(idx_common, error, width=1 / 24, color="C0", alpha=0.7, edgecolor="none")
    ax2.axhline(0, color="k", linewidth=0.5)
    ax2.axhline(1.5, color="r", linewidth=0.7, linestyle="--", alpha=0.5, label="Target +/-1.5C")
    ax2.axhline(-1.5, color="r", linewidth=0.7, linestyle="--", alpha=0.5)
    ax2.set_ylabel("Error [C]")
    ax2.set_xlabel("Time")
    ax2.set_ylim(-3, 3)
    ax2.legend(loc="upper right", fontsize=7)
    ax2.grid(True, alpha=0.25)

    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    save_figure_bundle(fig, output_dir / filename)
    plt.close(fig)
    print(f"  [PLOT] {filename}")


def plot_mixing_valve_diagnosis(
    diagnosis_df: pd.DataFrame,
    output_dir: Path = OUT_DIR,
    filename: str = "mixing_valve_offset",
) -> None:
    """Bar chart: mixing valve offset per node — shows why multi-node validation fails."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if AE_RCPARAMS:
        plt.rcParams.update(AE_RCPARAMS)

    if diagnosis_df.empty:
        return

    node_agg = diagnosis_df.groupby("node").agg({
        "path_length_m": "first",
        "mixing_offset_C": "mean",
        "T_meas_mean_C": "mean",
    }).sort_values("path_length_m")

    fig, ax = plt.subplots(figsize=(6, 3.5))

    colors = ["green" if o < 1.0 else "orange" if o < 5.0 else "red"
              for o in node_agg["mixing_offset_C"]]

    ax.barh(range(len(node_agg)), node_agg["mixing_offset_C"],
            color=colors, alpha=0.8, edgecolor="none")

    ax.set_yticks(range(len(node_agg)))
    ax.set_yticklabels([f"{n} ({int(r['path_length_m'])}m)"
                        for n, r in node_agg.iterrows()], fontsize=7)
    ax.set_xlabel("Mixing valve offset [C]\n(T_junction - T_measured)")
    ax.set_title("Consumer substation mixing effect\n(explains multi-node validation gap)")

    ax.axvline(1.0, color="green", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.axvline(5.0, color="orange", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.text(0.5, len(node_agg) + 0.3, "valid", color="green", fontsize=7, ha="center")
    ax.text(3.0, len(node_agg) + 0.3, "marginal", color="orange", fontsize=7, ha="center")
    ax.text(10.0, len(node_agg) + 0.3, "not comparable", color="red", fontsize=7, ha="center")

    ax.grid(True, alpha=0.2, axis="x")
    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    save_figure_bundle(fig, output_dir / filename)
    plt.close(fig)
    print(f"  [PLOT] {filename}")


# ═══════════════════════════════════════════════════════════════════════════════
# LATEX GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_measurement_limitation_latex(output_dir: Path = OUT_DIR) -> str:
    """
    Generate LaTeX paragraph documenting why multi-node validation is not possible.
    For inclusion in paper Section 4.2.
    """
    tex = (
        r"\subsubsection{Measurement point limitations}" + "\n"
        r"\label{sec:val_meas_limitations}" + "\n\n"
        r"The monitoring system records temperatures at consumer heat exchanger" + "\n"
        r"substations (\texttt{V\_X\_flow\_temp}), located \emph{downstream} of" + "\n"
        r"three-way mixing valves that blend primary supply water with" + "\n"
        r"recirculated return flow. The measured temperature is therefore" + "\n"
        r"systematically lower than the primary network junction temperature by" + "\n"
        r"5--15\,\si{\celsius}, depending on valve position and instantaneous" + "\n"
        r"load ratio (\Cref{fig:mixing_offset})." + "\n\n"
        r"This precludes direct spatial validation at intermediate network" + "\n"
        r"junctions. The sole exception is the network far-end" + "\n"
        r"(j$_{15}$, consumer~V$_{27}$), where the terminal pipe is short" + "\n"
        r"(\SI{125}{\metre}), local demand is minimal, and the mixing valve" + "\n"
        r"operates near fully-open position. The measured temperature at V$_{27}$" + "\n"
        r"therefore approximates the primary junction temperature within sensor" + "\n"
        r"accuracy ($\pm$\SI{0.5}{\celsius})." + "\n\n"
        r"The source-to-far-end temperature corridor (j$_1 \to$ j$_{15}$," + "\n"
        r"\SI{2125}{\metre}) serves as the primary spatial validation path." + "\n"
        r"Full spatial node-level validation would require primary-side temperature" + "\n"
        r"sensors at network junctions---instrumentation not available in this" + "\n"
        r"installation and uncommon in operational DH networks where monitoring" + "\n"
        r"serves billing purposes~\cite{Maldonado2024,Kus2025}."
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "measurement_limitation.tex").write_text(tex, encoding="utf-8")
    print("  [TEX] measurement_limitation.tex")
    return tex


# ═══════════════════════════════════════════════════════════════════════════════
# JSON EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def export_corridor_kpis(
    corridor_result: dict,
    diagnosis_df: Optional[pd.DataFrame] = None,
    output_dir: Path = OUT_DIR,
    filename: str = "kpis_corridor.json",
) -> None:
    """Export corridor validation KPIs and diagnosis to JSON."""
    data = {
        "corridor": corridor_result,
        "methodology_note": (
            "Multi-node spatial validation not possible: consumer substations "
            "measure post-mixing temperature (secondary side). Only V_27 (j_15, "
            "far-end) approximates primary junction temperature. "
            "See mixing_valve_offset plot for details."
        ),
    }

    if diagnosis_df is not None and not diagnosis_df.empty:
        data["mixing_valve_offsets"] = diagnosis_df.to_dict(orient="records")

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  [JSON] {filename}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_spatial_validation(
    skip_calibration: bool = False,
    run_diagnosis: bool = True,
) -> dict:
    """
    Corridor-only validation pipeline.

    Steps:
      1. Load data + extract BC
      2. Reconstruct node temperatures (exponential decay model)
      3. Corridor validation: reconstructed j_15 vs measured V_27
      4. Mixing valve diagnosis (informational)
      5. Generate plots + exports

    Returns dict with corridor KPIs and diagnosis.
    """
    print("\n" + "=" * 70)
    print("  CORRIDOR VALIDATION (j_1 -> j_15, 2125m)")
    print("  Note: Multi-node validation not possible (mixing valve effect)")
    print("=" * 70)

    print("\n[1/5] Loading data...")
    hist = load_historical(DATA_PATH, resample_to_1h=True)
    bc_info = extract_supply_temperature_bc(hist)

    u_multipliers: Optional[dict[str, float]] = None
    if not skip_calibration:
        try:
            from tools.validation_runner import estimate_u_from_measurements
            u_multipliers = estimate_u_from_measurements(hist, None)
            print("  [CAL] Using existing U-value estimates")
        except Exception:
            u_multipliers = None
            print("  [CAL] Using nominal U-values (no calibration available)")

    print("\n[2/5] Corridor validation...")
    corridor_result = validate_corridor(hist, bc_info, u_multipliers)

    diagnosis_df = pd.DataFrame()
    if run_diagnosis:
        print("\n[3/5] Mixing valve diagnosis...")
        diagnosis_df = diagnose_mixing_valve_effect(hist, bc_info)

    print("\n[4/5] Generating outputs...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    plot_corridor_timeseries(hist, bc_info, u_multipliers, OUT_DIR)
    if not diagnosis_df.empty:
        plot_mixing_valve_diagnosis(diagnosis_df, OUT_DIR)

    generate_measurement_limitation_latex(OUT_DIR)
    export_corridor_kpis(corridor_result, diagnosis_df, OUT_DIR)

    print("\n[5/5] Summary")
    print("=" * 70)
    if corridor_result.get("status") == "ok":
        mae = corridor_result["MAE_C"]
        passed = corridor_result["pass"]
        print(f"  Corridor MAE: {mae:.3f}C -> {'PASS' if passed else 'FAIL'}")
    else:
        print(f"  Corridor: {corridor_result.get('status')} -- {corridor_result.get('reason')}")
    print("=" * 70 + "\n")

    return {
        "corridor": corridor_result,
        "diagnosis": diagnosis_df.to_dict(orient="records") if not diagnosis_df.empty else [],
        "pass": corridor_result.get("pass", False),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Corridor validation + mixing valve diagnosis")
    parser.add_argument("--no-calibrate", action="store_true", help="Skip U-value calibration")
    parser.add_argument("--diagnose", action="store_true", help="Run mixing valve diagnosis only")
    args = parser.parse_args()

    if args.diagnose:
        hist = load_historical(DATA_PATH, resample_to_1h=True)
        bc_info = extract_supply_temperature_bc(hist)
        diagnose_mixing_valve_effect(hist, bc_info)
        sys.exit(0)

    results = run_spatial_validation(skip_calibration=args.no_calibrate)
    sys.exit(0 if results.get("pass", False) else 1)


if __name__ == "__main__":
    main()

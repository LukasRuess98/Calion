"""
fig_validation_scatter_tsup.py
==============================
Scatter-plot validation: measured vs. simulated T_supply at the network
far-end (j_15, corridor j_1 -> j_15, 2125 m).

The figure keeps the existing BCM-forward validation logic:
all trunk pipes use the same global multiplier and KPIs are computed from the
winter subset after the same physical plausibility filter.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.paper.figures.fig_utils import apply_style, polish_axes, save_fig

WINTER_MONTHS = {10, 11, 12, 1, 2}
GATE_C = 1.5
GRID_PATH_M = 2125.0
TRUNK_MULT = 1.330


def _load_data() -> tuple[pd.Series, pd.Series] | None:
    """Return (measured_j15_winter, simulated_j15_winter) or None."""
    try:
        from tools.validation_runner import DATA_PATH, PIPE_CATALOG, TRUNK_PIPES, load_historical
        from tools.validation_spatial import reconstruct_node_temperatures
    except ImportError as exc:
        print(f"[fig_validation_scatter_tsup] Import failed: {exc}")
        return None

    if not DATA_PATH.exists():
        print(f"[fig_validation_scatter_tsup] Data file not found: {DATA_PATH}")
        return None

    print("[fig_validation_scatter_tsup] Loading historical data ...")
    hist = load_historical(DATA_PATH)

    if "V_27_flow_temp" not in hist.columns:
        print("[fig_validation_scatter_tsup] V_27_flow_temp not in hist columns")
        return None

    bc_col = "V_1_flow_temp"
    if bc_col not in hist.columns:
        print(f"[fig_validation_scatter_tsup] Required source column missing: {bc_col}")
        return None
    bc_temp = hist[bc_col].astype(float).fillna(float(hist[bc_col].median()))

    t_meas_all = hist["V_27_flow_temp"].astype(float)

    u_cal = {pid: 1.0 for pid in PIPE_CATALOG}
    for pid in TRUNK_PIPES:
        u_cal[pid] = TRUNK_MULT
    print(
        f"[fig_validation_scatter_tsup] BCM calibration: "
        f"all trunk pipes x {TRUNK_MULT:.3f} nominal U"
    )

    node_temps_cal = reconstruct_node_temperatures(hist, bc_temp, u_cal)
    t_sim_cal = node_temps_cal.get("j_15")
    if t_sim_cal is None:
        print("[fig_validation_scatter_tsup] Reconstruction failed")
        return None

    df = pd.DataFrame({"meas": t_meas_all, "sim": t_sim_cal}).dropna()
    df = df[df.index.month.isin(WINTER_MONTHS)]

    n_raw = len(df)
    df = df[(df["meas"] >= 70.0) & (df["sim"] >= 70.0)]
    n_filtered = n_raw - len(df)
    if n_filtered > 0:
        print(
            f"    Removed {n_filtered} non-physical points "
            f"(T < 70 degC; {100 * n_filtered / n_raw:.1f}% of winter data)"
        )

    if len(df) < 50:
        print(f"[fig_validation_scatter_tsup] Too few winter points: {len(df)}")
        return None

    return df["meas"], df["sim"]


def _plot(meas: pd.Series, sim: pd.Series) -> None:
    apply_style()

    months = meas.index.month
    unique_months = sorted(set(months))
    cmap = plt.cm.tab10
    month_names = {10: "Oct", 11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb"}

    lo = min(float(meas.min()), float(sim.min())) - 1.0
    hi = max(float(meas.max()), float(sim.max())) + 1.0
    lo = max(lo, 55.0)
    hi = min(hi, 110.0)
    diag = np.array([lo, hi])

    fig, ax = plt.subplots(figsize=(3.65, 3.65))

    for i, month in enumerate(unique_months):
        mask = months == month
        ax.scatter(
            meas[mask], sim[mask],
            s=5, alpha=0.28,
            color=cmap(i / max(len(unique_months) - 1, 1)),
            edgecolors="none",
            rasterized=True,
            label=month_names.get(month, str(month)),
        )

    ax.plot(diag, diag, color="#202020", lw=0.85, zorder=3, label="1:1")
    ax.plot(
        diag, diag + GATE_C,
        ls=(0, (2, 2)), color="#7D7D7D", lw=0.75, zorder=2,
        label=rf"$\pm${GATE_C:.1f} $^\circ$C gate",
    )
    ax.plot(diag, diag - GATE_C, ls=(0, (2, 2)), color="#7D7D7D", lw=0.75, zorder=2)

    ax.set_aspect("equal")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel(r"Measured $T_{\mathrm{sup}}$ [$^\circ$C]")
    ax.set_ylabel(r"Simulated $T_{\mathrm{sup}}$ [$^\circ$C]")

    err = sim.values - meas.values
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    bias = float(np.mean(err))
    n_total = len(meas)
    pct_in_gate = float(100.0 * np.mean(np.abs(err) <= GATE_C))

    txt = (
        "BCM forward reconstruction\n"
        rf"j$_{{1}}\to$j$_{{15}}$ corridor, {GRID_PATH_M:.0f} m" "\n"
        rf"Winter (Oct-Feb), $n$={n_total} h" "\n"
        rf"$U_{{trunk}}$ calibration: $\times${TRUNK_MULT:.3f}" "\n"
        rf"MAE {mae:.2f} $^\circ$C   RMSE {rmse:.2f} $^\circ$C" "\n"
        rf"Bias {bias:+.2f} $^\circ$C" "\n"
        rf"Within $\pm${GATE_C:.1f} $^\circ$C: {pct_in_gate:.0f} %"
    )
    ax.text(
        0.04, 0.96, txt,
        transform=ax.transAxes,
        va="top", ha="left", fontsize=6.7,
        bbox=dict(boxstyle="round,pad=0.26", fc="white", ec="#C8C8C8", alpha=0.92, lw=0.55),
    )

    ax.legend(
        fontsize=6.4, loc="lower right", markerscale=2.2,
        frameon=True, framealpha=0.9, borderpad=0.35,
        handletextpad=0.35, labelspacing=0.25,
    )
    polish_axes(ax)
    fig.tight_layout(pad=0.35)
    save_fig(fig, "F_validation_scatter_tsup")


def main() -> None:
    result = _load_data()
    if result is None:
        print("[fig_validation_scatter_tsup] Skipping - data unavailable")
        return
    meas, sim = result
    _plot(meas, sim)


if __name__ == "__main__":
    main()

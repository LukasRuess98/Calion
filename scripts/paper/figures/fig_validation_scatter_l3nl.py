"""
fig_validation_scatter_l3nl.py
================================
Scatter plot: measured vs. L3^NL (MIQCP nonlinear) simulated T_supply at
the network far-end j_15.

Uses solver output (T_supply_farend_C) from the full L3^NL optimisation runs
for January and February 2025 — the same windows used for BCM validation.

Compared to the BCM reconstruction scatter (fig_validation_scatter_tsup.py),
this figure shows the accuracy of the full nonlinear MIQCP model.
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

from scripts.paper.figures.fig_utils import save_fig
from scripts.paper.mpl_export import AE_RCPARAMS, AE_DOUBLE_COLUMN_IN

GATE_C       = 1.5
GRID_PATH_M  = 2125.0
T_MIN        = 70.0     # physical plausibility filter

# L3^NL solver output files (full-month optimisation runs)
L3NL_WINDOWS = {
    "Jan 2025": ROOT / "output/paper_runs/linearization_windows/jan_2025/L3NL/dispatch_hourly.csv",
    "Feb 2025": ROOT / "output/paper_runs/linearization_windows/feb_2025/L3NL/dispatch_hourly.csv",
}

MONTH_COLORS = {
    "Jan 2025": "#1f77b4",   # blue
    "Feb 2025": "#2ca02c",   # green
}


def _load_data() -> pd.DataFrame | None:
    try:
        from tools.validation_runner import DATA_PATH, load_historical
    except ImportError as exc:
        print(f"[fig_validation_scatter_l3nl] Import failed: {exc}")
        return None

    if not DATA_PATH.exists():
        print(f"[fig_validation_scatter_l3nl] Data not found: {DATA_PATH}")
        return None

    hist = load_historical(DATA_PATH)
    t_meas_all = hist["V_27_flow_temp"].astype(float)

    frames = []
    for win_name, fpath in L3NL_WINDOWS.items():
        if not fpath.exists():
            print(f"  [SKIP] {win_name} — file not found: {fpath}")
            continue
        df = pd.read_csv(fpath, index_col=0, parse_dates=True)
        if "T_supply_farend_C" not in df.columns:
            print(f"  [SKIP] {win_name} — T_supply_farend_C missing")
            continue
        t_sim   = df["T_supply_farend_C"]
        t_meas  = t_meas_all.reindex(t_sim.index)
        comb = pd.DataFrame({"sim": t_sim, "meas": t_meas, "window": win_name}).dropna(
            subset=["sim", "meas"]
        )
        comb = comb[(comb["meas"] >= T_MIN) & (comb["sim"] >= T_MIN)]
        n_raw   = len(t_sim)
        n_used  = len(comb)
        print(f"  {win_name}: {n_used}/{n_raw} hours after filter")
        frames.append(comb)

    if not frames:
        print("[fig_validation_scatter_l3nl] No data loaded")
        return None

    return pd.concat(frames)


def _plot(df: pd.DataFrame) -> None:
    plt.rcParams.update(AE_RCPARAMS)

    err  = df["sim"] - df["meas"]
    mae  = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    bias = float(np.mean(err))
    pct  = float(100.0 * np.mean(np.abs(err) <= GATE_C))
    n    = len(df)

    lo = max(float(df[["sim","meas"]].min().min()) - 1.0, 68.0)
    hi = min(float(df[["sim","meas"]].max().max()) + 1.5, 92.0)
    diag = np.array([lo, hi])

    fig_w = AE_DOUBLE_COLUMN_IN * 0.52
    fig, ax = plt.subplots(figsize=(fig_w, fig_w))

    for win_name, grp in df.groupby("window"):
        ax.scatter(
            grp["meas"], grp["sim"],
            s=5, alpha=0.30,
            color=MONTH_COLORS.get(win_name, "#888888"),
            edgecolors="none",
            rasterized=True,
            label=win_name,
        )

    # 1:1 line
    ax.plot(diag, diag, color="#202020", lw=0.85, zorder=3, label="1:1")
    # ±gate
    ax.plot(diag, diag + GATE_C, ls=(0,(2,2)), color="#7D7D7D", lw=0.75, zorder=2,
            label=rf"$\pm${GATE_C:.1f} $^\circ$C gate")
    ax.plot(diag, diag - GATE_C, ls=(0,(2,2)), color="#7D7D7D", lw=0.75, zorder=2)

    ax.set_aspect("equal")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel(r"Measured $T_\mathrm{sup}$ [°C]")
    ax.set_ylabel(r"L3$^\mathrm{NL}$ simulated $T_\mathrm{sup}$ [°C]")

    # KPI box
    txt = (
        r"L3$^\mathrm{NL}$ (MIQCP) model" "\n"
        rf"j$_{{1}}\to$j$_{{15}}$, {GRID_PATH_M:.0f} m, Jan–Feb" "\n"
        rf"MAE  = {mae:.2f} $^\circ$C" "\n"
        rf"RMSE = {rmse:.2f} $^\circ$C" "\n"
        rf"Bias = {bias:+.2f} $^\circ$C   $n$={n} h" "\n"
        rf"Within $\pm${GATE_C:.1f} $^\circ$C: {pct:.0f}\%"
    )
    ax.text(
        0.04, 0.96, txt,
        transform=ax.transAxes,
        va="top", ha="left", fontsize=6.7,
        bbox=dict(boxstyle="round,pad=0.26", fc="white", ec="#C8C8C8",
                  alpha=0.92, lw=0.55),
    )

    ax.legend(
        fontsize=6.4, loc="lower right", markerscale=2.5,
        frameon=True, framealpha=0.9, borderpad=0.35,
        handletextpad=0.35, labelspacing=0.25,
    )
    ax.tick_params(which="both", length=3, width=0.6)
    fig.tight_layout(pad=0.35)
    save_fig(fig, "F_validation_scatter_l3nl")


def main() -> None:
    df = _load_data()
    if df is None:
        print("[fig_validation_scatter_l3nl] Skipping — data unavailable")
        return
    _plot(df)


if __name__ == "__main__":
    main()

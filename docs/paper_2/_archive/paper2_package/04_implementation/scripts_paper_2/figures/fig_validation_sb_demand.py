"""fig_validation_sb_demand.py
============================
Scatter plot comparing measured consumer heat demand (Waermeleistung) to
model-prescribed demand for the 7 directly measured ACRON stations in the
Stadtbach BC-SB baseline scenario.

Since demand is a hard constraint in the model, this figure validates the
preprocessing pipeline (merge_acron_sb.py) rather than the physics model.

Output: output/paper2_runs/figures/fig_validation_sb_demand.{pdf,png,pgf}
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

from scripts.paper.mpl_export import AE_DOUBLE_COLUMN_IN, AE_RCPARAMS, save_figure_bundle
from tools.validation_stadtbach import (
    IDX_2025,
    MEASURED_CONSUMERS,
    STATION_TO_NODE,
    load_measured_demand,
    load_simulation_demand,
    RUN_DIR,
)

OUT_DIR = ROOT / "output" / "paper2_runs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Applied Energy palette
C_SCATTER = "#1a6faf"
C_GATE    = "#aaaaaa"
C_DIAG    = "#333333"

STATION_SHORT: dict[str, str] = {
    "Klinikum":           "Klinikum",
    "UNI":                "Uni",
    "KUKA":               "KUKA",
    "MAN":                "MAN",
    "SIGMA_Technopark":   "SIGMA",
    "Lechhauser_Str":     "Lechhauser",
    "August-Wessels-Str": "Aug.-Wessels",
}


def _compute_kpis(meas: np.ndarray, sim: np.ndarray) -> dict:
    mask = ~(np.isnan(meas) | np.isnan(sim)) & (meas >= 0)
    m, s = meas[mask], sim[mask]
    err = s - m
    mae = float(np.mean(np.abs(err)))
    r2 = float(np.corrcoef(m, s)[0, 1] ** 2) if len(m) > 1 else float("nan")
    annual_err = (float(s.sum()) - float(m.sum())) / float(m.sum()) * 100 if m.sum() > 0 else float("nan")
    return {"n": int(mask.sum()), "mae": mae, "r2": r2, "annual_err": annual_err}


def main() -> None:
    plt.rcParams.update(AE_RCPARAMS)

    # Load data
    print("Loading simulation demand ...")
    sim_df = load_simulation_demand(RUN_DIR)

    stations = list(STATION_TO_NODE.keys())
    n_panels = len(stations)
    ncols = 4
    nrows = int(np.ceil(n_panels / ncols))

    fig_w = AE_DOUBLE_COLUMN_IN
    fig_h = nrows * 1.9
    fig, axes = plt.subplots(nrows, ncols, figsize=(fig_w, fig_h))
    axes = axes.flatten()

    print("Plotting scatter panels ...")
    for ax_idx, station in enumerate(stations):
        ax = axes[ax_idx]
        node_id = STATION_TO_NODE[station]

        meas_q = load_measured_demand(station).values
        sim_q  = sim_df[node_id].reindex(IDX_2025).values if node_id in sim_df.columns else np.full(8760, np.nan)

        mask = (meas_q >= 0) & ~np.isnan(sim_q)
        m, s = meas_q[mask], sim_q[mask]

        ax.scatter(m, s, s=0.8, alpha=0.25, color=C_SCATTER, linewidths=0, rasterized=True)

        # Reference diagonal
        vmax = max(m.max(), s.max()) * 1.05 if len(m) > 0 else 1.0
        ax.plot([0, vmax], [0, vmax], color=C_DIAG, lw=0.6, ls="--", zorder=4)

        kpis = _compute_kpis(meas_q, sim_q)
        ax.text(
            0.05, 0.95,
            (f"MAE = {kpis['mae']:.3f} MW\n"
             f"$R^2$ = {kpis['r2']:.3f}\n"
             f"Ann. err = {kpis['annual_err']:+.1f}%"),
            transform=ax.transAxes,
            va="top", ha="left", fontsize=6,
            family="monospace",
            bbox=dict(boxstyle="square,pad=0.25", fc="white", ec="#cccccc", alpha=0.90, lw=0.4),
        )

        ax.set_title(STATION_SHORT[station], fontsize=7, pad=2)
        ax.set_xlabel("Measured [MW]", fontsize=6)
        ax.set_ylabel("Model [MW]", fontsize=6)
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
        ax.tick_params(labelsize=6)
        print(f"  {station}: n={kpis['n']}  MAE={kpis['mae']:.3f}  R²={kpis['r2']:.3f}")

    # Hide unused panels
    for ax in axes[n_panels:]:
        ax.set_visible(False)

    fig.suptitle("Stadtbach BC-SB: Demand preprocessing validation (7 measured consumers)",
                 fontsize=7, y=1.002)
    fig.tight_layout(pad=0.5, h_pad=0.8, w_pad=0.5)

    saved = save_figure_bundle(fig, OUT_DIR / "fig_validation_sb_demand", formats=("png", "pdf"))
    for p in saved:
        print(f"Saved: {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()

"""
fig_synth_gap_4d.py
====================
Faceted heatmap showing L1->L3 cost gap [%] as a function of all 4 synthetic
network parameters simultaneously:

  Rows    : node count  n  ∈ {5, 15, 30}
  Columns : storage     s  ∈ {2, 6, 12} h
  Each cell: 3×3 heatmap  L (y) × HI (x), colour = gap_cost_pct

Missing (infeasible) cells are shown in light grey.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

from scripts.paper.figures.fig_utils import save_fig
from scripts.paper.mpl_export import AE_RCPARAMS, AE_DOUBLE_COLUMN_IN

# ── data ──────────────────────────────────────────────────────────────────────
DATA = ROOT / "output" / "paper_runs" / "synth_gap_summary.csv"

LENGTHS = [1.0, 5.0, 15.0]
HIS     = [0.1, 0.4, 0.8]
NODES   = [5, 15, 30]
STORES  = [2, 6, 12]

CMAP   = "RdYlGn_r"   # green = small gap (L1 ok), red = large gap (L1 wrong)
VMIN, VMAX = 0, 50    # % gap range


def _parse(cfg: str):
    n  = int(re.search(r"n(\d+)", cfg).group(1))
    L  = float(re.search(r"L([\d]+p[\d]+)km", cfg).group(1).replace("p", "."))
    hi = float(re.search(r"hi([\d]+p[\d]+)", cfg).group(1).replace("p", "."))
    s  = int(re.search(r"s(\d+)h", cfg).group(1))
    return n, L, hi, s


def main() -> None:
    plt.rcParams.update(AE_RCPARAMS)

    df_raw = pd.read_csv(DATA)
    df = df_raw[df_raw["comparison"] == "L1cp->L3"].copy()
    df[["n", "L", "hi", "s"]] = df["config"].apply(
        lambda c: pd.Series(_parse(c))
    )

    # ── layout ────────────────────────────────────────────────────────────────
    n_rows = len(NODES)    # 3
    n_cols = len(STORES)   # 3
    cell_w, cell_h = 1.55, 1.55        # inches per mini-heatmap
    cbar_w = 0.35
    fig_w = n_cols * cell_w + cbar_w + 0.6
    fig_h = n_rows * cell_h + 0.7

    fig, axes = plt.subplots(
        n_rows, n_cols,
        figsize=(fig_w, fig_h),
        gridspec_kw={"hspace": 0.45, "wspace": 0.25},
    )
    fig.subplots_adjust(left=0.13, right=0.87, top=0.90, bottom=0.10)

    norm = Normalize(vmin=VMIN, vmax=VMAX)
    cmap = plt.get_cmap(CMAP)

    for ri, n_val in enumerate(NODES):
        for ci, s_val in enumerate(STORES):
            ax = axes[ri, ci]

            # Build 3×3 grid: rows = L (ascending), cols = HI (ascending)
            grid = np.full((3, 3), np.nan)
            sub = df[(df["n"] == n_val) & (df["s"] == s_val)]
            for row_i, L_val in enumerate(LENGTHS):
                for col_i, hi_val in enumerate(HIS):
                    mask = (
                        np.isclose(sub["L"], L_val) &
                        np.isclose(sub["hi"], hi_val)
                    )
                    if mask.any():
                        grid[row_i, col_i] = sub.loc[mask, "gap_cost_pct"].values[0]

            # plot
            im = ax.imshow(
                grid,
                cmap=cmap, norm=norm,
                aspect="auto", origin="lower",
            )

            # annotate cells
            for row_i in range(3):
                for col_i in range(3):
                    val = grid[row_i, col_i]
                    if np.isnan(val):
                        ax.text(col_i, row_i, "–", ha="center", va="center",
                                fontsize=6.5, color="#888888")
                    else:
                        color = "white" if val > 30 else "black"
                        ax.text(col_i, row_i, f"{val:.0f}%",
                                ha="center", va="center",
                                fontsize=6.5, fontweight="bold", color=color)

            # axes ticks
            ax.set_xticks([0, 1, 2])
            ax.set_yticks([0, 1, 2])
            ax.set_xticklabels(["0.1", "0.4", "0.8"], fontsize=6)
            ax.set_yticklabels(["1", "5", "15"], fontsize=6)
            ax.tick_params(length=2, width=0.5)

            # grey out missing
            for row_i in range(3):
                for col_i in range(3):
                    if np.isnan(grid[row_i, col_i]):
                        ax.add_patch(plt.Rectangle(
                            (col_i - 0.5, row_i - 0.5), 1, 1,
                            fc="#e8e8e8", ec="none", zorder=0,
                        ))

            # column header (top row only)
            if ri == 0:
                ax.set_title(f"Storage = {s_val} h", fontsize=7, pad=4)

            # row label (left column only)
            if ci == 0:
                ax.set_ylabel(
                    f"n = {n_val} nodes\nPipe length [km]",
                    fontsize=6.5, labelpad=4,
                )

            # x label (bottom row only)
            if ri == n_rows - 1:
                ax.set_xlabel("Demand HI", fontsize=6.5, labelpad=3)

    # ── shared colorbar ────────────────────────────────────────────────────────
    cbar_ax = fig.add_axes([0.89, 0.12, 0.025, 0.76])
    cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cbar_ax)
    cb.set_label(r"$\Delta$Cost L1$\to$L3 [%]", fontsize=7)
    cb.ax.tick_params(labelsize=6)
    cb.set_ticks([0, 10, 20, 30, 40, 50])

    # ── super-title ────────────────────────────────────────────────────────────
    fig.suptitle(
        r"L1$\to$L3 cost gap across all 36 synthetic configurations"
        "\n(rows = node count, columns = storage, cells = pipe length × demand HI)",
        fontsize=7.5, y=0.97,
    )

    save_fig(fig, "F_synth_gap_4d")


if __name__ == "__main__":
    main()

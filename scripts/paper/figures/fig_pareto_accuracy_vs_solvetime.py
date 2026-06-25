"""
fig_pareto_accuracy_vs_solvetime.py
===================================
Pareto-front figure: model fidelity versus solve time.
Solve times from meta.json. Cost gaps vs L3NL computed as cumulative sums:
  L3+  = Jan-2025 window direct comparison (0.35%)
  L3   = L3->L3+ (0.11%) + L3+->L3NL (0.35%) = 0.46%
  L1/L2 = annual L1/L2->L3 gap + L3->L3NL (0.46%)
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

from scripts.paper.figures.fig_utils import (
    LEVEL_COLORS,
    LEVEL_LABELS,
    apply_style,
    save_fig,
)


def polish_axes(ax, grid_axis="both"):
    ax.tick_params(which="both", length=3, width=0.6)
    ax.grid(True, axis=grid_axis, linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)

# (level_key, solve_time_s, cost_gap_vs_LNL_pct)
LEVELS = [
    ("L1",     268,   13.50),
    ("L2",     450,    3.00),
    ("L3",     650,    0.46),
    ("L3plus", 1165,   0.35),
    ("L3NL",   14708,  0.00),
]

_OFFSETS = {
    "L1": (1.12, -0.15, "left", "top"),
    "L2": (1.16, 0.22, "left", "bottom"),
    "L3": (0.92, 0.55, "right", "bottom"),
    "L3plus": (1.18, 0.20, "left", "bottom"),
    "L3NL": (0.80, 0.72, "right", "bottom"),
}


def main() -> None:
    apply_style()

    keys = [r[0] for r in LEVELS]
    times = np.array([r[1] for r in LEVELS], dtype=float)
    gaps = np.array([r[2] for r in LEVELS], dtype=float)
    colors = [LEVEL_COLORS[k] for k in keys]

    fig, ax = plt.subplots(figsize=(3.85, 3.05))

    ax.plot(times, gaps, ls="--", color="#A7A7A7", lw=0.8, zorder=1)
    for k, t, g, c in zip(keys, times, gaps, colors):
        size = 82 if k == "L3" else 58
        if k == "L3":
            ax.scatter(t, g, s=170, color=c, alpha=0.16, edgecolors="none", zorder=3)
        ax.scatter(
            t, g, s=size, color=c, zorder=5,
            edgecolors="white", linewidths=0.55, label=LEVEL_LABELS[k],
        )
        dx_fac, dy, ha, va = _OFFSETS[k]
        ax.text(
            t * dx_fac, g + dy, LEVEL_LABELS[k],
            color=c, fontsize=7, va=va, ha=ha, zorder=6,
        )

    l3_t, l3_g = times[2], gaps[2]
    ax.annotate(
        "practical\nPareto point",
        xy=(l3_t, l3_g),
        xytext=(l3_t * 2.0, l3_g + 2.05),
        fontsize=7,
        arrowprops=dict(arrowstyle="->", lw=0.65, color="#555555",
                        shrinkA=2, shrinkB=4),
        color="#333333",
    )

    lnl_t, lnl_g = times[4], gaps[4]
    ax.annotate(
        "MIQCP\nreference",
        xy=(lnl_t, lnl_g),
        xytext=(lnl_t * 0.45, lnl_g + 1.95),
        fontsize=7,
        arrowprops=dict(arrowstyle="->", lw=0.65, color="#555555",
                        shrinkA=2, shrinkB=4),
        color="#333333",
        ha="right",
    )

    ax.axvline(3600, ls=(0, (2, 2)), color="#9A9A9A", lw=0.75, zorder=0)
    ax.text(
        3600 * 1.06, 13.7, "1 h budget",
        fontsize=6.7, color="#777777", va="top", ha="left",
    )

    ax.set_xscale("log")
    ax.set_xlim(100, 5e4)
    ax.set_ylim(-0.45, 15)
    ax.set_xlabel("Solve time [s]")
    ax.set_ylabel(r"Cost gap vs $\mathrm{L}^{\mathrm{NL}}$ [%]")
    polish_axes(ax, grid_axis="both")

    fig.tight_layout(pad=0.45)
    save_fig(fig, "F_pareto_accuracy_vs_solvetime")


if __name__ == "__main__":
    main()

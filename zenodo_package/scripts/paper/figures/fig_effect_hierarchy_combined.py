"""
fig_effect_hierarchy_combined.py
================================
Two-panel headline figure: cost gap per modelling step versus additional
solve time. Data values are hardcoded from the paper and are not modified.
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
    apply_style,
    polish_axes,
    save_fig,
)

# (y-label, cost_gap_pct, additional_solve_time_s, bar_colour)
STEPS = [
    (
        r"$\mathrm{L1} \to \mathrm{L2}$" + "\n(topology + heat loss)",
        10.6,
        182,
        LEVEL_COLORS["L2"],
    ),
    (
        r"$\mathrm{L2} \to \mathrm{L3}$" + "\n(spatial resolution)",
        2.4,
        200,
        LEVEL_COLORS["L3"],
    ),
    (
        r"$\mathrm{L3} \to \mathrm{L}^{+}$" + "\n(pressure drop)",
        0.11,
        515,
        LEVEL_COLORS["L3plus"],
    ),
    (
        r"$\mathrm{L}^{+} \to \mathrm{L}^{\mathrm{NL}}$" + "\n(lin. + transp. delay)",
        0.35,
        14000,
        LEVEL_COLORS["L3NL"],
    ),
]

COST_ANNOTS = ["+10.6 %", "+2.4 %", "+0.11 %", "+0.35 % (bound)"]
TIME_ANNOTS = ["182 s", "200 s", "515 s", ">14 000 s (bound)"]


def main() -> None:
    apply_style()

    labels = [s[0] for s in STEPS]
    cost_vals = [s[1] for s in STEPS]
    time_vals = [s[2] for s in STEPS]
    colors = [s[3] for s in STEPS]
    y = np.arange(len(STEPS))

    fig, (ax_a, ax_b) = plt.subplots(
        1, 2,
        figsize=(7.0, 2.75),
        sharey=True,
        gridspec_kw={"width_ratios": [1.0, 1.08]},
    )

    bars_a = ax_a.barh(
        y, cost_vals, color=colors, height=0.52,
        edgecolor="white", linewidth=0.45,
    )
    for i, (bar, txt) in enumerate(zip(bars_a, COST_ANNOTS)):
        ax_a.text(
            bar.get_width() + 0.18, i, txt,
            va="center", ha="left", fontsize=7, clip_on=False,
        )
    ax_a.set_xlim(0, 13.2)
    ax_a.set_yticks(y)
    ax_a.set_yticklabels(labels)
    ax_a.set_xlabel("Cost gap [% of L3 cost]")
    ax_a.set_title("(a) Cost gap", loc="left")
    ax_a.invert_yaxis()
    polish_axes(ax_a, grid_axis="x")

    bars_b = ax_b.barh(
        y, time_vals, color=colors, height=0.52,
        edgecolor="white", linewidth=0.45,
    )
    for i, (bar, txt) in enumerate(zip(bars_b, TIME_ANNOTS)):
        ax_b.text(
            bar.get_width() * 1.10, i, txt,
            va="center", ha="left", fontsize=7, clip_on=False,
        )
    ax_b.set_xscale("log")
    ax_b.set_xlim(50, 5e4)
    ax_b.set_yticks(y)
    ax_b.tick_params(labelleft=False)
    ax_b.set_xlabel("Additional solve time [s]")
    ax_b.set_title("(b) Additional solve time", loc="left")
    ax_b.invert_yaxis()
    polish_axes(ax_b, grid_axis="x")

    fig.tight_layout(pad=0.6, w_pad=1.2)
    save_fig(fig, "F_effect_hierarchy_combined")


if __name__ == "__main__":
    main()

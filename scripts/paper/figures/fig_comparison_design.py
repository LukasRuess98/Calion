"""F1 — Schematic: 5 fidelity levels with controlled comparison arrows."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

from scripts.paper.figures.fig_utils import apply_style, save_fig, LEVEL_COLORS

LEVELS = ["L1", "L2", "L3", "L3plus", "L3NL"]
LABELS = {
    "L1":    "L1\nCopperplate\n(1 node)",
    "L2":    "L2\nRegional\n(8 nodes)",
    "L3":    "L3\nBasic physics\n(15 nodes)",
    "L3plus": r"L3$^+$" + "\nFull physics\n(15 nodes)",
    "L3NL":  r"L3$^\mathrm{NL}$" + "\nNonlinear\n(15 nodes)",
}
COMPARISONS = [
    ("L1", "L2",    "Topology\ngap",     "above", "#888888"),
    ("L2", "L3",    "Physics\ngap",      "above", "#888888"),
    ("L3", "L3plus","Linearization\nerror","below","#555555"),
    ("L3plus","L3NL","NL correction",    "below","#555555"),
]


def main() -> None:
    apply_style()
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ax.set_xlim(-0.5, 4.5)
    ax.set_ylim(-1.2, 1.8)
    ax.axis("off")

    xs = {lvl: i for i, lvl in enumerate(LEVELS)}
    y_box = 0.5

    for lvl in LEVELS:
        x = xs[lvl]
        color = LEVEL_COLORS[lvl]
        rect = mpatches.FancyBboxPatch(
            (x - 0.42, y_box - 0.38), 0.84, 0.76,
            boxstyle="round,pad=0.05",
            facecolor=color, edgecolor="white", linewidth=1.5, alpha=0.9,
        )
        ax.add_patch(rect)
        ax.text(x, y_box, LABELS[lvl], ha="center", va="center",
                fontsize=7, color="white", fontweight="bold", linespacing=1.4)

    arrow_props = dict(arrowstyle="-|>", color="#333333",
                       connectionstyle="arc3,rad=0.0", lw=1.2)
    for i, (src, dst, label, side, clr) in enumerate(COMPARISONS):
        x0, x1 = xs[src] + 0.43, xs[dst] - 0.43
        y = (y_box + 0.55) if side == "above" else (y_box - 0.55)
        ax.annotate(
            "", xy=(x1, y), xytext=(x0, y),
            arrowprops=dict(arrowstyle="-|>", color=clr, lw=1.2),
        )
        xm = (x0 + x1) / 2
        ytext = y + (0.22 if side == "above" else -0.22)
        ax.text(xm, ytext, label, ha="center", va="center",
                fontsize=6.5, color=clr, style="italic")
        ax.plot([x0, x0, x1, x1], [y_box + (0.38 if side=="above" else -0.38),
                                    y, y,
                                    y_box + (0.38 if side=="above" else -0.38)],
                color=clr, lw=0.6, linestyle=":")

    ax.text(2.0, 1.65, "Fidelity Hierarchy — Memmingen District Heating Network",
            ha="center", va="top", fontsize=9, fontweight="bold")

    legend_items = [
        mpatches.Patch(color="#888888", label="Topology / physics gap (upper)"),
        mpatches.Patch(color="#555555", label="Linearization error (lower)"),
    ]
    ax.legend(handles=legend_items, loc="lower center", ncol=2,
              fontsize=7, frameon=False, bbox_to_anchor=(0.5, -0.08))

    save_fig(fig, "fig_comparison_design")


if __name__ == "__main__":
    main()

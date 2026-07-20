"""
Figure — Network topology schematic: L1 / L2 / L3 side-by-side.

Usage:
    python scripts/paper/plot_network_topology.py --outdir outputs/paper/figures/

No input data required — all positions are hardcoded schematically.

Produces:
    figX_network_topology.pdf  (vector — use in Overleaf)
    figX_network_topology.png  (300 DPI preview)
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    DOUBLE_COL_W, H_TOPOLOGY,
)

apply_ecm_style()

NODE_STYLES = {
    "plant":      {"color": "#d62728", "r": 0.055, "label": "Generation plant"},
    "central":    {"color": "#ff7f0e", "r": 0.045, "label": "Central node"},
    "substation": {"color": "#1f77b4", "r": 0.035, "label": "Substation / demand"},
    "storage":    {"color": "#2ca02c", "r": 0.040, "label": "Thermal storage"},
}
PIPE_COLOR = "#555555"
PIPE_LW    = 1.2


def _node(ax, x, y, ntype, label="", lo=(0, -0.13)):
    s = NODE_STYLES[ntype]
    ax.add_patch(Circle((x, y), s["r"], color=s["color"], zorder=5,
                         linewidth=0.5, edgecolor="white"))
    if label:
        ax.text(x + lo[0], y + lo[1], label, ha="center", va="top",
                fontsize=6.5, zorder=6)


def _pipe(ax, x1, y1, x2, y2):
    ax.plot([x1, x2], [y1, y2], color=PIPE_COLOR, linewidth=PIPE_LW,
            solid_capstyle="round", zorder=3)


def _panel_l1(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("(a) L1 — Copperplate\n(1 node)", pad=4)

    _node(ax, 0.50, 0.60, "central",    "All assets\nco-located")
    _node(ax, 0.32, 0.76, "plant",      "Boiler +\nHeat pump", (0, 0.06))
    _node(ax, 0.68, 0.76, "storage",    "TES",                 (0, 0.06))
    _node(ax, 0.50, 0.36, "substation", "Demand",              (0, -0.12))

    _pipe(ax, 0.36, 0.70, 0.46, 0.62)
    _pipe(ax, 0.64, 0.70, 0.54, 0.62)
    _pipe(ax, 0.50, 0.52, 0.50, 0.42)

    ax.text(0.50, 0.10, "No network losses\n(copperplate)", ha="center",
            fontsize=6.5, color="#666666", style="italic")


def _panel_l2(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("(b) L2 — 5-node\nnetwork", pad=4)

    pos = {
        "plant":   (0.50, 0.84),
        "central": (0.50, 0.65),
        "north":   (0.22, 0.44),
        "south":   (0.78, 0.44),
        "indus":   (0.78, 0.22),
    }
    pipes = [("plant", "central"), ("central", "north"),
             ("central", "south"), ("south", "indus")]
    for a, b in pipes:
        _pipe(ax, *pos[a], *pos[b])

    labels = {"plant": "Plant\n(Gen+TES)", "central": "Central",
              "north": "North", "south": "South", "indus": "Industrial"}
    types  = {"plant": "plant", "central": "central",
              "north": "substation", "south": "substation", "indus": "substation"}
    for k, (x, y) in pos.items():
        lo = (0, 0.06) if y > 0.70 else (0, -0.12)
        _node(ax, x, y, types[k], labels[k], lo)

    ax.text(0.50, 0.06, "4 pipes · 5 nodes", ha="center",
            fontsize=6.5, color="#666666", style="italic")


def _panel_l3(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("(c) L3 — 24-node\nnetwork", pad=4)

    plant   = (0.50, 0.90)
    central = (0.50, 0.74)
    _pipe(ax, *plant, *central)
    _node(ax, *plant,   "plant",   "Plant",   (0, 0.05))
    _node(ax, *central, "central", "Central", (0, -0.10))

    branches = [(0.18, 0.56), (0.50, 0.56), (0.82, 0.56)]
    blabels  = ["West", "North", "East"]
    for (bx, by), bl in zip(branches, blabels):
        _pipe(ax, *central, bx, by)
        _node(ax, bx, by, "substation", bl, (0, -0.10))

        sub_offsets = [(-0.09, -0.14), (0.0, -0.14), (0.09, -0.14)]
        for ox, oy in sub_offsets:
            sx, sy = bx + ox, by + oy
            _pipe(ax, bx, by, sx, sy)
            _node(ax, sx, sy, "substation")

            for lox, loy in [(-0.045, -0.11), (0.045, -0.11)]:
                lx, ly = sx + lox, sy + loy
                if 0.02 < lx < 0.98 and 0.04 < ly < 0.96:
                    _pipe(ax, sx, sy, lx, ly)
                    _node(ax, lx, ly, "substation")

    ax.text(0.50, 0.03, "23 pipes · 24 nodes", ha="center",
            fontsize=6.5, color="#666666", style="italic")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_COL_W, H_TOPOLOGY))
    fig.subplots_adjust(wspace=0.05, left=0.01, right=0.99, top=0.86, bottom=0.10)

    _panel_l1(axes[0])
    _panel_l2(axes[1])
    _panel_l3(axes[2])

    handles = [mpatches.Patch(color=NODE_STYLES[k]["color"],
                               label=NODE_STYLES[k]["label"])
               for k in ("plant", "central", "substation", "storage")]
    handles.append(plt.Line2D([0], [0], color=PIPE_COLOR,
                               linewidth=PIPE_LW, label="District heating pipe"))
    fig.legend(handles=handles, loc="lower center", ncol=5,
               fontsize=7, bbox_to_anchor=(0.5, -0.04), frameon=True)

    fig.suptitle("Planning framework levels — network topology", y=0.97)

    save_figure(fig, Path(args.outdir) / "figX_network_topology")
    plt.close(fig)


if __name__ == "__main__":
    main()

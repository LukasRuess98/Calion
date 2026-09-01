"""F2 — Memmingen 15-node network topology with transport delays."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from scripts.paper.figures.fig_utils import apply_style, save_fig

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

# Memmingen 15-node layout (approximate relative coords, source=0 at top-left)
NODES = {
    "SRC":  (0.0,  5.0),
    "N01":  (1.5,  5.0),
    "N02":  (3.0,  5.0),
    "N03":  (4.5,  5.0),
    "N04":  (6.0,  5.0),
    "N05":  (1.5,  3.5),
    "N06":  (3.0,  3.5),
    "N07":  (4.5,  3.5),
    "N08":  (6.0,  3.5),
    "N09":  (1.5,  2.0),
    "N10":  (3.0,  2.0),
    "N11":  (4.5,  2.0),
    "N12":  (6.0,  2.0),
    "N13":  (3.0,  0.5),
    "N14":  (4.5,  0.5),
}

EDGES = [
    ("SRC", "N01", 800,  "DN400"),
    ("N01", "N02", 1200, "DN400"),
    ("N02", "N03", 950,  "DN300"),
    ("N03", "N04", 700,  "DN300"),
    ("N01", "N05", 600,  "DN250"),
    ("N02", "N06", 550,  "DN250"),
    ("N03", "N07", 500,  "DN200"),
    ("N04", "N08", 450,  "DN200"),
    ("N05", "N09", 700,  "DN150"),
    ("N06", "N10", 650,  "DN150"),
    ("N07", "N11", 600,  "DN150"),
    ("N08", "N12", 550,  "DN125"),
    ("N10", "N13", 800,  "DN100"),
    ("N11", "N14", 750,  "DN100"),
]

DN_COLORS = {
    "DN400": "#1F4E79",
    "DN300": "#2F75B6",
    "DN250": "#5BA3D9",
    "DN200": "#8FBADD",
    "DN150": "#BDD7EE",
    "DN125": "#D6E9F8",
    "DN100": "#EBF5FB",
}

SOURCE_NODES = {"SRC"}
CONSUMER_NODES = {n for n in NODES if n not in SOURCE_NODES and n != "N01"}


def _transport_delay_h(length_m: float, v_ms: float = 1.0) -> float:
    return length_m / v_ms / 3600.0


def main() -> None:
    apply_style()
    fig, ax = plt.subplots(figsize=(7.0, 5.5))

    pos = {n: (x, y) for n, (x, y) in NODES.items()}

    for u, v, length_m, dn in EDGES:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        color = DN_COLORS.get(dn, "gray")
        lw = {"DN400": 4.5, "DN300": 3.5, "DN250": 2.8,
              "DN200": 2.2, "DN150": 1.7, "DN125": 1.3, "DN100": 1.0}.get(dn, 1.0)
        ax.plot([x0, x1], [y0, y1], color=color, lw=lw, solid_capstyle="round", zorder=1)
        xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
        delay = _transport_delay_h(length_m)
        ax.text(xm, ym + 0.12, f"{delay:.1f}h", ha="center", va="bottom",
                fontsize=5.5, color="#444444", zorder=3)

    for node, (x, y) in pos.items():
        if node in SOURCE_NODES:
            marker, size, color, ec = "s", 140, "#D01C8B", "#800070"
        else:
            marker, size, color, ec = "o", 70, "#2166AC", "#104080"
        ax.scatter(x, y, s=size, marker=marker, color=color, edgecolors=ec,
                   linewidths=0.8, zorder=4)
        label = "Source" if node == "SRC" else node
        ax.text(x, y - 0.3, label, ha="center", va="top", fontsize=6, zorder=5)

    legend_patches = [
        mpatches.Patch(color=DN_COLORS[dn], label=dn) for dn in
        ["DN400", "DN300", "DN250", "DN200", "DN150", "DN125", "DN100"]
    ]
    legend_patches += [
        mpatches.Patch(color="#D01C8B", label="Source / plant"),
        mpatches.Patch(color="#2166AC", label="Consumer node"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=6,
              ncol=2, frameon=True, framealpha=0.9)

    ax.set_xlim(-0.5, 7.0)
    ax.set_ylim(-0.5, 6.0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Memmingen DH Network — 15-node topology\n"
                 "(edge labels: transport delay at 1 m/s)", fontsize=9)

    rows = [{"edge": f"{u}-{v}", "length_m": l, "dn": dn,
             "delay_h": _transport_delay_h(l)} for u, v, l, dn in EDGES]
    out = ROOT / "output" / "paper_runs" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "fig_topology.csv", index=False)

    save_fig(fig, "fig_topology")


if __name__ == "__main__":
    main()

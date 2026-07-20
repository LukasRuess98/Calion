"""
Generate Figures F1 and F2 (no solver data required).

F1: Schematic comparison design — 5 levels with 3 controlled-comparison arrows
F2: Memmingen 15-node tree topology with transport delay annotations

Usage:
    python tools/make_fig_f1_f2.py
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "output" / "paper_runs" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

SERIF = {"family": "serif"}
DPI = 300


# ──────────────────────────────────────────────────────────────────────────────
# F1 — Schematic comparison design
# ──────────────────────────────────────────────────────────────────────────────

def make_f1() -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    levels = [
        ("L1", 1.0, "Aggregated\nDemand\n(1 node)", "#d0e4f7"),
        ("L2", 3.0, "Regional\nFractions\n(8 nodes)", "#b8d8e8"),
        ("L3", 5.0, "Independent\nZone Demands\n(15 nodes, basic\nphysics)", "#9ecae1"),
        (r"L3$^+$", 7.0, "Extended\nPhysics\n(pressure drop,\ndelay)", "#6baed6"),
        (r"L3$^{NL}$", 9.0, "Nonlinear\nQCQP\n(bilinear\nterms)", "#2171b5"),
    ]

    box_w, box_h = 1.6, 2.6
    box_y = 0.7

    for label, x, desc, color in levels:
        rect = mpatches.FancyBboxPatch(
            (x - box_w / 2, box_y), box_w, box_h,
            boxstyle="round,pad=0.08",
            linewidth=1.2, edgecolor="#333333", facecolor=color, zorder=2,
        )
        ax.add_patch(rect)
        ax.text(x, box_y + box_h + 0.18, label, ha="center", va="bottom",
                fontsize=13, fontweight="bold", fontfamily="serif")
        ax.text(x, box_y + box_h / 2, desc, ha="center", va="center",
                fontsize=7.5, fontfamily="serif", color="#111111")

    # Controlled comparison arrows
    arrow_style = dict(arrowstyle="-|>", color="#c0392b", lw=1.8,
                       mutation_scale=16, zorder=3)

    comparisons = [
        (1.0, 3.0, 3.62, "RQ1: Topology\nimpact"),
        (3.0, 5.0, 3.62, "RQ2: Demand\ngranularity"),
        (5.0, 7.0, 3.62, "RQ2: Physics\nfidelity"),
    ]
    for x1, x2, y, label in comparisons:
        ax.annotate("", xy=(x2 - box_w / 2 - 0.05, y - 0.1),
                    xytext=(x1 + box_w / 2 + 0.05, y - 0.1),
                    arrowprops=arrow_style)
        ax.text((x1 + x2) / 2, y + 0.12, label, ha="center", va="bottom",
                fontsize=7, color="#c0392b", fontfamily="serif")

    # RQ3 arrow L3+ → L3NL
    ax.annotate("", xy=(9.0 - box_w / 2 - 0.05, 3.62 - 0.1),
                xytext=(7.0 + box_w / 2 + 0.05, 3.62 - 0.1),
                arrowprops=dict(arrowstyle="-|>", color="#8e44ad", lw=1.8,
                                mutation_scale=16, zorder=3))
    ax.text(8.0, 3.62 + 0.12, "RQ3: Linearization\nerror", ha="center",
            va="bottom", fontsize=7, color="#8e44ad", fontfamily="serif")

    ax.set_title("Modeling Fidelity Levels — Controlled Comparison Protocol",
                 fontsize=11, fontfamily="serif", pad=6)
    fig.tight_layout()

    for ext in ("pdf", "png"):
        fig.savefig(FIG_DIR / f"fig_comparison_design.{ext}", dpi=DPI,
                    bbox_inches="tight")
    plt.close(fig)
    print("[F1] fig_comparison_design.pdf/.png written")


# ──────────────────────────────────────────────────────────────────────────────
# F2 — Memmingen 15-node topology
# ──────────────────────────────────────────────────────────────────────────────

# Node positions (hand-tuned from Lageplan)
NODE_POS: dict[str, tuple[float, float]] = {
    "j_1":  (0.0,  0.0),   # producer / Heizwerk
    "j_2":  (1.0, -0.5),
    "j_3":  (2.0, -1.0),
    "j_4":  (2.8, -2.0),   # south branch
    "j_5":  (3.5, -2.8),
    "j_6":  (4.2, -3.4),
    "j_7":  (4.5, -2.5),
    "j_8":  (5.2, -2.5),
    "j_9":  (2.8,  0.2),   # east branch
    "j_10": (3.6,  0.8),
    "j_11": (4.4,  1.2),
    "j_12": (5.2,  1.5),
    "j_13": (6.0,  1.8),
    "j_14": (6.8,  2.5),
    "j_15": (6.8,  1.0),
}

# Pipe definitions: (from, to, length_m, diameter_mm)
PIPES = [
    ("j_1",  "j_2",   350, 450),
    ("j_2",  "j_3",   300, 450),
    ("j_3",  "j_4",   260, 300),
    ("j_3",  "j_9",   450, 350),
    ("j_4",  "j_5",   240, 250),
    ("j_5",  "j_6",   150, 150),
    ("j_5",  "j_7",   220, 125),
    ("j_7",  "j_8",    80, 100),
    ("j_9",  "j_10",  200, 300),
    ("j_10", "j_11",  230, 300),
    ("j_11", "j_12",  250, 300),
    ("j_12", "j_13",  220, 250),
    ("j_13", "j_14",  180, 125),
    ("j_13", "j_15",  125, 100),
]

# v_max=2.5, rho=1000, cp=4182, dT=60, d_inner ≈ DN*0.94 mm
def _transport_delay_min(length_m: float, dn_mm: float) -> float:
    d_inner_m = dn_mm * 0.94e-3
    area = math.pi * (d_inner_m / 2) ** 2
    # Use 75% of v_max as representative velocity
    v = 2.5 * 0.75
    return (length_m / v) / 60.0


def make_f2() -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_aspect("equal")

    # Draw pipes
    dn_to_lw = {100: 1, 125: 1.5, 150: 2, 250: 3, 300: 4, 350: 5, 450: 6}

    for frm, to, length_m, dn in PIPES:
        x1, y1 = NODE_POS[frm]
        x2, y2 = NODE_POS[to]
        lw = dn_to_lw.get(dn, 2)
        ax.plot([x1, x2], [y1, y2], color="#2c7bb6", lw=lw, solid_capstyle="round",
                zorder=1, alpha=0.85)
        # Transport delay label
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        delay = _transport_delay_min(length_m, dn)
        ax.text(mx + 0.04, my + 0.04, f"{delay:.1f} min",
                fontsize=5.5, color="#555555", fontfamily="serif",
                ha="left", va="bottom", zorder=4)
        # Diameter label
        ax.text(mx - 0.04, my - 0.04, f"DN{dn}",
                fontsize=5.0, color="#2c7bb6", fontfamily="serif",
                ha="right", va="top", zorder=4)

    # Draw nodes
    for node, (x, y) in NODE_POS.items():
        color = "#e74c3c" if node == "j_1" else "#f39c12" if node in ("j_6", "j_8", "j_14", "j_15") else "#2ecc71"
        ax.scatter(x, y, s=120, color=color, zorder=3, edgecolors="#333", linewidths=0.8)
        short = node.replace("j_", "J")
        ax.text(x + 0.06, y + 0.06, short, fontsize=7, fontfamily="serif",
                fontweight="bold", zorder=5)

    # Legend
    legend_items = [
        mpatches.Patch(color="#e74c3c", label="Producer (Heizwerk)"),
        mpatches.Patch(color="#2ecc71", label="Distribution junction"),
        mpatches.Patch(color="#f39c12", label="Terminal junction"),
        mpatches.Patch(color="#2c7bb6", label="Supply pipe (lw ∝ DN)"),
    ]
    ax.legend(handles=legend_items, loc="lower right", fontsize=7,
              prop={"family": "serif", "size": 7})

    ax.set_title(
        "Memmingen District Heating — 15-Node Topology\n"
        "Pipe labels: DN [mm] / transport delay at 75% v_max [min]",
        fontsize=10, fontfamily="serif",
    )
    ax.axis("off")
    fig.tight_layout()

    for ext in ("pdf", "png"):
        fig.savefig(FIG_DIR / f"fig_topology.{ext}", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("[F2] fig_topology.pdf/.png written")


if __name__ == "__main__":
    make_f1()
    make_f2()

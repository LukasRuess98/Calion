"""Figure 0 (paper figure 1): system concept — schematic of the calibrated meshed network (anonymised node layout,
topology from ``netzmodell.KANTEN``) and the energy–hydraulic coupling.

    python -m scripts.dhn_study.central_tes.paper_fig_system
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle, RegularPolygon  # noqa: E402

from .. import netzmodell as nm  # noqa: E402
from . import paper_figures as P  # noqa: E402


def fig_system(out: Path):
    POS = {"KWK": (0.2, 5.0), "SS": (1.2, 5.0), "K1": (2.4, 6.2), "S": (3.9, 6.2), "L5M": (5.6, 6.2), "K2": (6.9, 6.2),
           "L5O": (8.5, 6.2), "MVA": (9.7, 7.1), "BIO": (9.7, 6.2), "GT": (9.7, 5.2), "L6": (7.6, 4.6), "K3": (6.4, 3.6),
           "K4": (5.4, 2.2), "L7": (8.2, 2.6), "L1G": (1.3, 7.3), "PS2": (0.6, 8.4), "HW2": (-0.5, 8.4),
           "PS1": (2.2, 1.4), "HW1": (3.9, 0.4)}
    end = {k[0]: k[2] for k in nm.KANTEN}           # node ids derived from the edge list (no names in this file)
    worst = end["L4f"]
    POS |= {end["L2"]: (2.4, 3.95), end["L3"]: (4.3, 3.6), end["L4a"]: (2.2, 2.6), end["L4c"]: (2.8, 0.4),
            end["L4e"]: (5.0, 0.4), worst: (6.5, 0.4)}
    fig = plt.figure(figsize=(P.W2, 92 * P.MM))
    ax = fig.add_axes([0.0, 0.0, 0.6, 1.0]); ax.set_axis_off(); ax.set_xlim(-0.9, 11.0); ax.set_ylim(-0.6, 9.4); ax.set_aspect("equal")
    for eid, a, b, dn, L in nm.KANTEN:
        (x0, y0), (x1, y1) = POS[a], POS[b]
        lw = 0.35 * ((dn or 400) / 100) ** 1.5                 # line width scaled with DN
        col = P.INK2
        if eid.startswith("L4"):
            col = P.VIOLET
        rad = {"L6c": 0.22}.get(eid, 0.0)
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-", connectionstyle=f"arc3,rad={rad}", lw=lw + 2.2,
                                     color="white", shrinkA=0, shrinkB=0, zorder=1))   # white casing: crossing without junction
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-", connectionstyle=f"arc3,rad={rad}", lw=lw, color=col,
                                     shrinkA=0, shrinkB=0, zorder=1))
    plants = {"KWK": "KWK\n(pressure holder)", "MVA": "MVA", "GT": "GT", "BIO": "Bio-KWK", "HW1": "HW1", "HW2": "HW2\n(west, via HX)"}
    for n, (x, y) in POS.items():
        if n == "HW2":                                  # west network: exogenous heat-exchanger export (sink), not a feed-in
            ax.add_patch(Rectangle((x - 0.22, y - 0.22), 0.44, 0.44, facecolor="white", edgecolor=P.INK, lw=1.0, zorder=3))
        elif n in plants:
            ax.add_patch(Rectangle((x - 0.22, y - 0.22), 0.44, 0.44, color=P.INK, zorder=3))
        elif n in ("PS1", "PS2"):
            ax.add_patch(RegularPolygon((x, y), 3, radius=0.24, color=P.INK2, zorder=3))
        elif n == "S":
            ax.add_patch(Circle((x, y), 0.3, color=P.BLUE, zorder=4))
        elif n == "SS":
            ax.add_patch(Rectangle((x - 0.06, y - 0.35), 0.12, 0.7, color=P.INK, zorder=3))
        else:
            ax.add_patch(Circle((x, y), 0.11, color="white", ec=P.INK2, lw=0.8, zorder=3))
    lab = {"KWK": ("KWK\n(pressure holder)", 0.0, -0.62, "center"), "MVA": ("MVA", 0.32, 0, "left"), "BIO": ("Bio-KWK", 0.32, 0, "left"),
           "GT": ("GT", 0.32, 0, "left"), "HW1": ("HW1", 0, -0.45, "center"), "HW2": ("west network (HX export, sink)", -0.3, 0.42, "left"),
           "PS1": ("PS1", 0.3, 0, "left"), "PS2": ("PS2", 0.3, -0.25, "left")}
    for n, (t, dx, dy, ha) in lab.items():
        x, y = POS[n]; ax.text(x + dx, y + dy, t, fontsize=6.5, ha=ha, va="center", color=P.INK)
    x, y = POS["S"]
    ax.annotate("site S: TES + HP (partner A)\n+ EB (partner B), new link", (x, y), xytext=(x + 1.2, y + 2.2), fontsize=6.5, color=P.BLUE,
                ha="center", arrowprops={"arrowstyle": "-", "color": P.BLUE, "lw": 0.7})
    x, y = POS[worst]
    ax.add_patch(Circle((x, y), 0.17, color=P.VIOLET, zorder=4))
    ax.annotate("V06: worst point (≥ 1.2 bar)\nnew customers, new boiler", (x, y), xytext=(x + 0.4, y + 1.1), fontsize=6.5, color=P.INK,
                arrowprops={"arrowstyle": "-", "color": P.MUTED, "lw": 0.6})
    for t, (x, y) in {"east line L5": (5.9, 6.5), "south line L4": (0.35, 1.9), "city / meshes": (3.3, 4.75), "west line L1": (1.6, 7.75)}.items():
        ax.text(x, y, t, fontsize=6.5, color=P.INK2, style="italic")
    hs = [Line2D([], [], marker="s", ls="none", color=P.INK, ms=6, label="heat plant"),
          Line2D([], [], marker="s", ls="none", mfc="white", mec=P.INK, ms=6, label="heat export (sink)"),
          Line2D([], [], marker="^", ls="none", color=P.INK2, ms=6, label="pump station"),
          Line2D([], [], marker="o", ls="none", mfc="white", mec=P.INK2, ms=5, label="load / junction node"),
          Line2D([], [], color=P.VIOLET, lw=2, label="south line (expansion)")]
    ax.legend(handles=hs, loc="lower right", fontsize=6.5, frameon=False, bbox_to_anchor=(1.0, 0.0))
    ax.text(-0.9, 9.35, "(a)", fontsize=8, fontweight="bold", va="top")
    # ---------------------------------------------------------------- (b) method
    bx = fig.add_axes([0.62, 0.02, 0.37, 0.94]); bx.set_axis_off(); bx.set_xlim(0, 10.6); bx.set_ylim(0, 10)
    def box(x, y, w, h, t, fc="#f0efec", ec=P.INK2, fs=6.5, bold=False):
        bx.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.25", fc=fc, ec=ec, lw=0.7))
        bx.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, color=P.INK, fontweight="bold" if bold else "normal", linespacing=1.15)
    def arr(p0, p1, t=None, rad=0.0):
        bx.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=7, lw=0.8, color=P.INK2, connectionstyle=f"arc3,rad={rad}"))
    box(0.3, 8.0, 8.6, 1.6, "Inputs 2025 (hourly): demand, supply/return\ntemperature, day-ahead price, partner-A\nwaste heat, plant and pump data", fc="white")
    box(0.3, 5.6, 8.6, 1.7, "Energy layer — MILP (Pyomo, HiGHS)\nplants, TES (temperature classes),\nHP, EB, link → hourly schedule", fc="#e3edfb", bold=False)
    box(0.3, 3.1, 8.6, 1.7, "Hydraulic layer — calibrated meshed\nnetwork (3 calibrations): pumps,\npressures, flows → violations", fc="#fde8de")
    box(0.3, 0.4, 4.0, 1.9, "Mode E: energy-only\nschedule, post-hoc\nvalidation", fc="white")
    box(4.9, 0.4, 4.0, 1.9, "Mode H: linearised\nhydraulic cuts until\nfeasible → cost of\nhydraulic feasibility", fc="white")
    arr((4.6, 8.0), (4.6, 7.3)); arr((4.6, 5.6), (4.6, 4.8))
    arr((2.6, 3.1), (2.3, 2.3)); arr((6.6, 3.1), (6.9, 2.3))
    arr((8.9, 1.35), (8.9, 6.45), rad=0.3)
    bx.text(9.85, 3.9, "cuts", fontsize=6.5, color=P.INK2, rotation=90, va="center")
    bx.text(0.0, 9.95, "(b)", fontsize=8, fontweight="bold", va="top")
    P.save(fig, out, "fig0_system_concept")


def main():
    P.style()
    out = P.C.root() / P.C.load()["paths"]["results"] / "paper_figures"
    fig_system(out)


if __name__ == "__main__":
    main()

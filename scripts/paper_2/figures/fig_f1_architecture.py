"""F1 — Model architecture schematic (2 panels). DRAFT for layout review.

Panel A  L3+ node scheme: the heat balance [MW] and mass balance [kg/s] at one
         example node, with spatial supply-temperature propagation (T_VL drops
         node→node through pipe heat loss).
Panel B  McCormick envelope: the 4-inequality exact-at-the-corners relaxation
         that removes the bilinear term W = ṁ·c_p·T so the model stays a MILP.

This is the only purely conceptual figure (no data binding); the spec asks to
agree the layout before final rendering, so treat this as a first draft.

Usage:  python scripts/paper_2/figures/fig_f1_architecture.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style  # noqa: E402


def _box(ax, xy, w, h, text, fc, ec, *, fs=8, tc=None):
    ax.add_patch(FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.03,rounding_size=0.12",
                                fc=fc, ec=ec, lw=1.2, zorder=3))
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc or _style.INK, zorder=4)


def _arrow(ax, a, b, color, *, lw=1.6, ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=12,
                                 color=color, lw=lw, ls=ls, zorder=2,
                                 shrinkA=2, shrinkB=2))


# ── Panel A — nodal balances + temperature propagation ───────────────────────
def _panel_a(ax) -> None:
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.set_axis_off()
    ax.set_title("(a)  L3+ nodal balance & temperature propagation",
                 fontsize=9.5, loc="left", pad=4)

    # central node
    _box(ax, (4.0, 5.7), 2.0, 1.5, "Node $i$\n$T_{VL,i}$, $p_i$",
         fc="#e8f4f0", ec=_style.FHG_GREEN, fs=8.5)

    # inflows (left)
    _arrow(ax, (0.4, 8.2), (4.0, 6.9), _style.FHG_BLUE)
    ax.text(0.3, 8.5, "upstream supply  $Q_{\\mathrm{deliv},(j\\to i)}$",
            fontsize=7.2, color=_style.FHG_BLUE)
    _arrow(ax, (0.4, 6.1), (4.0, 6.2), _style.FHG_GREEN)
    ax.text(0.3, 5.45, "local gen.  $\\sum_a q_{a,i}$\n(WP·EK·CHP·boiler)",
            fontsize=7.2, color=_style.FHG_GREEN, va="top")

    # outflows (right)
    _arrow(ax, (6.0, 6.9), (9.6, 8.2), _style.INK_SOFT)
    ax.text(6.6, 8.5, "demand  $D_i$", fontsize=7.2, color=_style.INK_SOFT)
    _arrow(ax, (6.0, 6.2), (9.6, 6.1), _style.INK_SOFT)
    ax.text(6.3, 5.5, "downstream  $Q_{\\mathrm{deliv},(i\\to k)}$",
            fontsize=7.2, color=_style.INK_SOFT)

    # storage (down)
    _arrow(ax, (5.0, 5.7), (5.0, 4.6), _style.FHG_BORDEAUX)
    ax.text(5.15, 4.9, "TES  $q_{\\mathrm{ch}}-q_{\\mathrm{dis}}$",
            fontsize=7.2, color=_style.FHG_BORDEAUX)

    # temperature-propagation strip on the upstream pipe
    ax.text(1.7, 7.5, "$T_{VL,\\mathrm{in}} \\rightarrow T_{VL,\\mathrm{out}}$  "
            "(loss $U L\\,\\Delta T$)",
            fontsize=7.0, color=_style.FHG_BLUE, style="italic")

    # governing equations
    _box(ax, (0.4, 2.55), 9.2, 1.0,
         "Heat balance [MW]:   "
         "$\\sum_a q_{a,i} + \\sum_j Q_{ji} = D_i + \\sum_k Q_{ik} "
         "+ q_{\\mathrm{ch}} - q_{\\mathrm{dis}} + Q_{\\mathrm{dump}}$",
         fc="#eef4f7", ec=_style.FHG_BLUE, fs=8)
    _box(ax, (0.4, 1.25), 9.2, 1.0,
         "Mass balance [kg/s]:   "
         "$\\sum_j \\dot m_{ji} + \\dot m_{\\mathrm{gen},i} "
         "= \\sum_k \\dot m_{ik} + \\dot m_{\\mathrm{dem},i}$",
         fc="#f5eef1", ec=_style.FHG_BORDEAUX, fs=8)


# ── Panel B — McCormick envelope ─────────────────────────────────────────────
def _panel_b(ax) -> None:
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.set_axis_off()
    ax.set_title("(b)  McCormick relaxation of $W=\\dot m\\,c_p\\,T$",
                 fontsize=9.5, loc="left", pad=4)

    # the [x_L,x_H] x [y_L,y_H] box; corners are exact
    x0, x1, y0, y1 = 1.2, 5.2, 5.2, 9.0
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#e8f4f0",
                           ec=_style.FHG_GREEN, lw=1.4, zorder=2, alpha=0.7))
    # envelope facets (diagonals) — under/over-estimators meet at the corners
    ax.plot([x0, x1], [y0, y1], color=_style.FHG_BLUE, lw=1.4, zorder=3)
    ax.plot([x0, x1], [y1, y0], color=_style.FHG_BORDEAUX, lw=1.4, zorder=3)
    for cx, cy in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:
        ax.scatter(cx, cy, s=42, color=_style.INK, zorder=4)
    ax.text((x0 + x1) / 2, y1 + 0.35, "corners: $W=\\dot m\\,c_p\\,T$ exact",
            ha="center", fontsize=7.2, color=_style.INK)
    ax.text((x0 + x1) / 2, (y0 + y1) / 2 - 0.15, "convex-hull\nrelaxation",
            ha="center", va="center", fontsize=7.2, color=_style.FHG_GREEN)
    ax.text(x0 - 0.15, y0 - 0.55, "$\\dot m_L$", fontsize=7, color=_style.INK_SOFT)
    ax.text(x1 - 0.15, y0 - 0.55, "$\\dot m_H$", fontsize=7, color=_style.INK_SOFT)
    ax.annotate("", (x1 + 0.1, y0 - 0.3), (x0 - 0.1, y0 - 0.3),
                arrowprops=dict(arrowstyle="-|>", color=_style.INK_SOFT, lw=1))
    ax.text((x0 + x1) / 2, y0 - 0.95, "$\\dot m$", ha="center", fontsize=7.5,
            color=_style.INK_SOFT)

    # the four inequalities
    ineqs = (
        "$W \\geq c_p\\,(\\dot m_L T + \\dot m\\,T_L - \\dot m_L T_L)$\n"
        "$W \\geq c_p\\,(\\dot m_H T + \\dot m\\,T_H - \\dot m_H T_H)$\n"
        "$W \\leq c_p\\,(\\dot m_H T + \\dot m\\,T_L - \\dot m_H T_L)$\n"
        "$W \\leq c_p\\,(\\dot m_L T + \\dot m\\,T_H - \\dot m_L T_H)$"
    )
    _box(ax, (0.6, 1.0), 8.8, 2.6, ineqs, fc=_style.SURFACE, ec=_style.GRID, fs=8)
    ax.text(5.0, 3.95, "no bilinear term enters Gurobi → problem stays a true MILP",
            ha="center", fontsize=7.2, style="italic", color=_style.INK_SOFT)


def build_f1() -> None:
    print("F1 — model architecture (draft):")
    _style.apply_rcparams()
    fig, axes = plt.subplots(1, 2, figsize=(_style.COL_DOUBLE_IN, 4.3))
    _panel_a(axes[0])
    _panel_b(axes[1])
    fig.suptitle("CALION L3+ model architecture", fontsize=10.5, y=1.02)
    fig.subplots_adjust(wspace=0.08)
    _style.save(fig, "fig_F1_model_architecture")


if __name__ == "__main__":
    build_f1()

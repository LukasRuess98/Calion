"""
fig_pareto_with_synth.py
========================
Pareto figure (accuracy vs. solve time) extended with synthetic test cases
for three standard pipe lengths (1 km, 5 km, 15 km).

Primary case points are shown as the main colored markers.
Synthetic curves are shown in the background as gray shaded bands
(min/max) + median line, one per pipe-length band.

Y-axis: cost gap vs. best available model [%]
  - Primary case: gap vs. L3NL (hardcoded from validation)
  - Synth cases:  gap vs. synth L3 (pressure-drop included) +0.46 % offset
                  to align with the L3->L3NL correction from the primary case.
X-axis: solve time [s] (log scale)
  - Synth curves use the primary-case solve times as proxies per level
    (exact synth times not recorded; network complexity is comparable).
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
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from scripts.paper.figures.fig_utils import (
    LEVEL_COLORS,
    LEVEL_LABELS,
    apply_style,
    save_fig,
)

SYNTH_GAP = ROOT / "output" / "paper_runs" / "synth_gap_summary.csv"

# Primary-case Pareto points (level, solve_time_s, gap_vs_L3NL_pct)
PRIMARY = [
    ("L1",     268,   13.50),
    ("L2",     450,    3.00),
    ("L3",     650,    0.46),
    ("L3plus", 1165,   0.35),
    ("L3NL",   14708,  0.00),
]

# L3->L3NL correction applied to synth gaps to align with primary Y-axis
L3_TO_L3NL_CORRECTION = 0.46

STANDARD_PIPES = [1.0, 5.0, 15.0]

# Visual style per pipe length
PIPE_STYLE = {
    1.0:  {"color": "#BBBBBB", "ls": (0, (4, 2)),       "lw": 1.3, "label": "Synth 1 km",  "alpha_band": 0.18},
    5.0:  {"color": "#777777", "ls": (0, (3, 1, 1, 1)), "lw": 1.4, "label": "Synth 5 km",  "alpha_band": 0.16},
    15.0: {"color": "#333333", "ls": "-",               "lw": 1.5, "label": "Synth 15 km", "alpha_band": 0.13},
}

_PRIMARY_TIME = {row[0]: row[1] for row in PRIMARY}


def _load_synth_by_pipe() -> dict[float, dict]:
    """
    Returns for each pipe_km:
        {
          "L1":  {"median": .., "min": .., "max": ..},
          "L2":  {"median": .., "min": .., "max": ..},
          "L3":  {"median": 0.0, "min": 0.0, "max": 0.0},
        }
    All values in % gap vs. synth-L3 + L3->L3NL correction.
    """
    if not SYNTH_GAP.exists():
        raise FileNotFoundError(f"Run synth_gap_analysis.py first: {SYNTH_GAP}")

    df = pd.read_csv(SYNTH_GAP)

    def parse_pipe(cfg: str) -> float | None:
        m = re.search(r"_L([\dp]+)km_", cfg)
        return float(m.group(1).replace("p", ".")) if m else None

    df["pipe_km"] = df["config"].apply(parse_pipe)
    df = df[df["pipe_km"].isin(STANDARD_PIPES)]

    result: dict[float, dict] = {}

    for pipe in STANDARD_PIPES:
        band = df[df["pipe_km"] == pipe]
        d: dict[str, dict] = {}

        # --- L1cp position: gap from copperplate to synth-L3 ---
        s = band[band["comparison"] == "L1cp->L3"]["gap_cost_pct"]
        if s.empty:
            continue
        corr = L3_TO_L3NL_CORRECTION
        d["L1"] = {
            "median": s.median() + corr,
            "min":    s.min() + corr,
            "max":    s.max() + corr,
        }

        # --- L2 position: gap from L2 to synth-L3 ---
        s2 = band[band["comparison"] == "L2->L3"]["gap_cost_pct"]
        if not s2.empty:
            d["L2"] = {
                "median": max(s2.median() + corr, 0.0),
                "min":    max(s2.min() + corr, 0.0),
                "max":    max(s2.max() + corr, 0.0),
            }
        else:
            d["L2"] = {"median": corr, "min": corr, "max": corr}

        # --- L3 position: by definition the reference + correction ---
        d["L3"] = {"median": corr, "min": corr, "max": corr}

        result[pipe] = d

    return result


def _polish(ax, grid_axis="both"):
    ax.tick_params(which="both", length=3, width=0.6)
    ax.grid(True, axis=grid_axis, linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)


def main() -> None:
    apply_style()

    synth = _load_synth_by_pipe()

    fig, (ax_main, ax_zoom) = plt.subplots(
        1, 2, figsize=(7.2, 3.2),
        gridspec_kw={"width_ratios": [1.55, 1.0]},
    )

    for ax in (ax_main, ax_zoom):
        # ── Synth background curves ───────────────────────────────────────────
        for pipe in STANDARD_PIPES:
            if pipe not in synth:
                continue
            d = synth[pipe]
            sty = PIPE_STYLE[pipe]

            # Three points: L1 / L2 / L3
            xs = [_PRIMARY_TIME["L1"], _PRIMARY_TIME["L2"], _PRIMARY_TIME["L3"]]
            ys_med = [d["L1"]["median"], d["L2"]["median"], d["L3"]["median"]]
            ys_lo  = [d["L1"]["min"],    d["L2"]["min"],    d["L3"]["min"]]
            ys_hi  = [d["L1"]["max"],    d["L2"]["max"],    d["L3"]["max"]]

            ax.fill_between(xs, ys_lo, ys_hi,
                            color=sty["color"], alpha=sty["alpha_band"], zorder=1)
            ax.plot(xs, ys_med,
                    ls=sty["ls"], lw=sty["lw"], color=sty["color"],
                    zorder=2, label=sty["label"])

        # ── Primary case ──────────────────────────────────────────────────────
        keys  = [r[0] for r in PRIMARY]
        times = np.array([r[1] for r in PRIMARY], dtype=float)
        gaps  = np.array([r[2] for r in PRIMARY], dtype=float)
        colors = [LEVEL_COLORS[k] for k in keys]

        ax.plot(times, gaps, ls="--", color="#A7A7A7", lw=0.9, zorder=3)
        for k, t, g, c in zip(keys, times, gaps, colors):
            sz = 110 if k == "L3" else 72
            if k == "L3":
                ax.scatter(t, g, s=220, color=c, alpha=0.18,
                           edgecolors="none", zorder=4)
            ax.scatter(t, g, s=sz, color=c, zorder=6,
                       edgecolors="white", linewidths=0.7)

    # ── Main panel labels & annotations ──────────────────────────────────────
    _OFFSETS = {
        "L1":    (1.12, 0.60,  "left",  "bottom"),
        "L2":    (1.16, 0.22,  "left",  "bottom"),
        "L3":    (0.90, 0.55,  "right", "bottom"),
        "L3plus":(1.18, 0.18,  "left",  "bottom"),
        "L3NL":  (0.80, 0.55,  "right", "bottom"),
    }
    for k, t, g, c in zip(keys, times, gaps, colors):
        dx, dy, ha, va = _OFFSETS[k]
        ax_main.text(t * dx, g + dy, LEVEL_LABELS[k],
                     color=c, fontsize=6.8, va=va, ha=ha, zorder=7)

    # Pareto annotation on main
    l3_t, l3_g = _PRIMARY_TIME["L3"], 0.46
    ax_main.annotate(
        "Pareto\noptimum\n(primary)",
        xy=(l3_t, l3_g),
        xytext=(l3_t * 2.2, l3_g + 3.5),
        fontsize=6.5,
        arrowprops=dict(arrowstyle="->", lw=0.65, color="#555555",
                        shrinkA=2, shrinkB=4),
        color="#333333",
    )

    # 1-hour budget line (main panel only)
    ax_main.axvline(3600, ls=(0, (2, 2)), color="#9A9A9A", lw=0.75, zorder=0)
    ax_main.text(3600 * 1.06, 43, "1 h budget",
                 fontsize=6.5, color="#777777", va="top", ha="left")

    # Pipe-length labels on main: left of L1 position on the median line
    label_offsets = {1.0: -0.8, 5.0: 0.5, 15.0: 0.5}
    for pipe in STANDARD_PIPES:
        if pipe not in synth:
            continue
        sty = PIPE_STYLE[pipe]
        y_l1 = synth[pipe]["L1"]["median"]
        ax_main.text(
            _PRIMARY_TIME["L1"] * 0.84, y_l1 + label_offsets[pipe],
            f"{int(pipe)} km",
            color=sty["color"], fontsize=6.8, va="center", ha="right",
            fontweight="semibold", zorder=8,
        )

    ax_main.set_xscale("log")
    ax_main.set_xlim(100, 5e4)
    ax_main.set_ylim(-1.0, 47)
    ax_main.set_xlabel("Solve time [s]")
    ax_main.set_ylabel(r"Cost gap vs.\ best model [\%]")
    ax_main.set_title("(a) Full scale", loc="left", fontsize=8)
    _polish(ax_main)

    # ── Zoom panel: 0–5 % region ─────────────────────────────────────────────
    ax_zoom.set_xscale("log")
    ax_zoom.set_xlim(100, 5e4)
    ax_zoom.set_ylim(-0.3, 5.0)
    ax_zoom.set_xlabel("Solve time [s]")
    ax_zoom.set_ylabel(r"Cost gap vs.\ best model [\%]")
    ax_zoom.set_title("(b) Zoom 0–5 %", loc="left", fontsize=8)
    _polish(ax_zoom)

    # Labels in zoom panel (only L2, L3, L3+, L3NL visible)
    _OFFSETS_ZOOM = {
        "L2":    (1.14, 0.08,  "left",  "bottom"),
        "L3":    (0.88, 0.10,  "right", "bottom"),
        "L3plus":(1.16, 0.07,  "left",  "bottom"),
        "L3NL":  (0.82, 0.10,  "right", "bottom"),
    }
    for k, t, g, c in zip(keys, times, gaps, colors):
        if k not in _OFFSETS_ZOOM:
            continue
        dx, dy, ha, va = _OFFSETS_ZOOM[k]
        ax_zoom.text(t * dx, g + dy, LEVEL_LABELS[k],
                     color=c, fontsize=6.5, va=va, ha=ha, zorder=7)

    # 1h budget line in zoom
    ax_zoom.axvline(3600, ls=(0, (2, 2)), color="#9A9A9A", lw=0.75, zorder=0)

    # Legend (shared, placed on zoom panel)
    synth_handles = [
        mpatches.Patch(
            facecolor=PIPE_STYLE[p]["color"], alpha=0.55,
            label=PIPE_STYLE[p]["label"],
        )
        for p in STANDARD_PIPES
    ]
    primary_handle = mpatches.Patch(
        facecolor="#888888", alpha=0.0,
        label="Primary case (Memmingen)",
    )
    # invisible scatter proxy for primary
    from matplotlib.lines import Line2D
    primary_proxy = Line2D([0], [0], marker="o", color="w",
                           markerfacecolor="#555555", markersize=5,
                           label="Primary case")
    ax_zoom.legend(
        handles=synth_handles + [primary_proxy],
        loc="upper right", fontsize=6.5,
        frameon=True, framealpha=0.93,
        borderpad=0.5, labelspacing=0.35, handlelength=1.6,
        title="Background curves", title_fontsize=6.3,
    )

    fig.tight_layout(pad=0.5, w_pad=1.4)
    save_fig(fig, "fig_pareto_with_synth")


if __name__ == "__main__":
    main()

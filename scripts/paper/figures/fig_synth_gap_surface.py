"""
fig_synth_gap_surface.py
=========================
Single combined figure: L1->L3 cost gap as a smooth interpolated surface
over the two dominant drivers (pipe length × storage hours).

Node count and demand HI are averaged out (shown to be minor effects).
Individual data points overlaid as scatter.
"""
from __future__ import annotations

import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.tri as mtri
import numpy as np
import pandas as pd
from matplotlib.ticker import MultipleLocator

from scripts.paper.figures.fig_utils import save_fig
from scripts.paper.mpl_export import AE_RCPARAMS, AE_DOUBLE_COLUMN_IN

DATA  = ROOT / "output" / "paper_runs" / "synth_gap_summary.csv"
VMIN, VMAX = 0, 50

# Fraunhofer IPA corporate colors
IPA = {
    "teal":   "#009B77",
    "navy":   "#003E6E",
    "silver": "#8C9EA8",
    "red":    "#C0392B",
    "orange": "#E67E22",
    "green":  "#27AE60",
    "blue":   "#2980B9",
    "gray":   "#95A5A6",
}

# Custom IPA colormap: IPA green (low gap) → light silver → IPA red (high gap)
CMAP = mcolors.LinearSegmentedColormap.from_list(
    "ipa_gap",
    [IPA["teal"], "#E8F4F0", IPA["orange"], IPA["red"]],
    N=256,
)


def _parse(cfg: str):
    n  = int(re.search(r"n(\d+)", cfg).group(1))
    L  = float(re.search(r"L([\d]+p[\d]+)km", cfg).group(1).replace("p", "."))
    hi = float(re.search(r"hi([\d]+p[\d]+)", cfg).group(1).replace("p", "."))
    s  = int(re.search(r"s(\d+)h", cfg).group(1))
    return n, L, hi, s


def main() -> None:
    plt.rcParams.update(AE_RCPARAMS)

    df = pd.read_csv(DATA)
    df = df[df["comparison"] == "L1cp->L3"].copy()
    df[["n", "L", "hi", "s"]] = df["config"].apply(lambda c: pd.Series(_parse(c)))

    # ── average over node count and HI (minor effects) ─────────────────────
    agg = df.groupby(["L", "s"])["gap_cost_pct"].agg(["mean", "min", "max", "count"]).reset_index()

    # ── smooth surface via triangulated linear interpolation ─────────────────
    L_log = np.log10(agg["L"].values)
    s_vals = agg["s"].values.astype(float)
    gap    = agg["mean"].values

    tri = mtri.Triangulation(L_log, s_vals)
    interp_lin = mtri.LinearTriInterpolator(tri, gap)
    interp_cub = mtri.CubicTriInterpolator(tri, gap, kind="geom")

    L_grid = np.logspace(np.log10(0.8), np.log10(17), 120)
    s_grid = np.linspace(1.5, 13, 100)
    LL, SS = np.meshgrid(L_grid, s_grid)
    ZZ = interp_cub(np.log10(LL), SS).data
    # fill masked (outside convex hull) with linear fallback
    mask_out = interp_cub(np.log10(LL), SS).mask
    if mask_out.any():
        ZZ_lin = interp_lin(np.log10(LL), SS).data
        ZZ[mask_out] = ZZ_lin[mask_out]
    ZZ = np.clip(ZZ, VMIN, VMAX)

    # ── figure ──────────────────────────────────────────────────────────────
    fig_w = AE_DOUBLE_COLUMN_IN * 0.75   # single wide panel
    fig_h = fig_w * 0.80
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), constrained_layout=True)

    # filled contour surface
    cf = ax.contourf(
        LL, SS, ZZ,
        levels=np.linspace(VMIN, VMAX, 51),
        cmap=CMAP, vmin=VMIN, vmax=VMAX,
        extend="both",
    )

    # contour lines for orientation
    cs = ax.contour(
        LL, SS, ZZ,
        levels=[5, 10, 20, 30, 40],
        colors=IPA["navy"], linewidths=0.55, alpha=0.55,
    )
    ax.clabel(cs, fmt="%g %%", fontsize=6.5, inline_spacing=2)

    # scatter: individual data points (mean over n & HI)
    sc = ax.scatter(
        agg["L"], agg["s"],
        c=agg["mean"], cmap=CMAP, vmin=VMIN, vmax=VMAX,
        s=55, edgecolors=IPA["navy"], linewidths=0.8, zorder=5,
    )

    # annotate scatter points
    for _, row in agg.iterrows():
        ax.annotate(
            f"{row['mean']:.0f}%",
            xy=(row["L"], row["s"]),
            xytext=(5, 4), textcoords="offset points",
            fontsize=6, color=IPA["navy"] if row["mean"] < 28 else "white",
            fontweight="bold",
        )

    # colorbar
    cb = fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.03)
    cb.set_label(r"$\Delta$Cost L1$\to$L3 [%]", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    cb.set_ticks([0, 10, 20, 30, 40, 50])

    # axes
    ax.set_xscale("log")
    ax.set_xlim(0.8, 17)
    ax.set_ylim(1.5, 13)
    ax.set_xlabel("Total pipe length [km]", fontsize=8)
    ax.set_ylabel("Storage capacity [h at peak]", fontsize=8)
    ax.set_xticks([1, 5, 15])
    ax.set_xticklabels(["1", "5", "15"], fontsize=7)
    ax.set_yticks([2, 6, 12])
    ax.set_yticklabels(["2", "6", "12"], fontsize=7)
    ax.tick_params(which="both", length=3, width=0.6)

    ax.text(
        0.02, 0.97,
        r"Avg. over $n \in \{5,15,30\}$ nodes" "\n" r"and HI $\in \{0.1,0.4,0.8\}$",
        transform=ax.transAxes, va="top", ha="left", fontsize=6.5,
        bbox=dict(fc="white", ec=IPA["silver"], alpha=0.85, lw=0.5, boxstyle="round,pad=0.3"),
    )

    save_fig(fig, "F_synth_gap_surface")


if __name__ == "__main__":
    main()

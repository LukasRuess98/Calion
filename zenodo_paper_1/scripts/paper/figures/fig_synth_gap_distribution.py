"""
fig_synth_gap_distribution.py
=============================
Distribution of cost gaps across synthetic configurations. Values and clipping
thresholds are unchanged; only the visual treatment is polished.
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
import pandas as pd

from scripts.paper.figures.fig_utils import (
    DIRECTION_COLORS,
    LEVEL_SHORT,
    apply_style,
    polish_axes,
    save_fig,
)

GAP_CSV = ROOT / "output" / "paper_runs" / "synth_gap_summary.csv"
CLIP = 150.0
PHYS_CLIP = 5.0


def _jitter(n: int, spread: float = 0.06) -> np.ndarray:
    if n <= 1:
        return np.zeros(n)
    return np.linspace(-spread, spread, n)


def main() -> None:
    apply_style()

    if not GAP_CSV.exists():
        raise FileNotFoundError(f"Missing gap summary CSV: {GAP_CSV}")
    df = pd.read_csv(GAP_CSV)

    topo = df[df["comparison"] == "L1cp->L3"]["gap_cost_pct"].dropna().values
    phys = df[df["comparison"] == "L3->L3plus"]["gap_cost_pct"].dropna().values

    n_outliers_topo = (np.abs(topo) > CLIP).sum()
    n_outliers_phys = (phys > PHYS_CLIP).sum()

    fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.05))

    ax = axes[0]
    topo_clipped = np.clip(topo, -CLIP, CLIP)
    ax.boxplot(
        topo_clipped, positions=[0], widths=0.34, patch_artist=True,
        medianprops=dict(color="black", lw=1.15),
        boxprops=dict(facecolor="#AEC6E8", alpha=0.65, edgecolor="#627A96", lw=0.6),
        whiskerprops=dict(lw=0.8, color="#666666"),
        capprops=dict(lw=0.8, color="#666666"),
        flierprops=dict(marker="", lw=0),
    )

    jx = _jitter(len(topo_clipped))
    pos_mask = topo >= 0
    ax.scatter(
        jx[pos_mask], topo_clipped[pos_mask], s=16,
        color=DIRECTION_COLORS["positive"], alpha=0.68,
        edgecolors="white", lw=0.3, zorder=3,
        label="L3 > L1",
    )
    ax.scatter(
        jx[~pos_mask], topo_clipped[~pos_mask], s=16,
        color=DIRECTION_COLORS["negative"], alpha=0.68,
        edgecolors="white", lw=0.3, zorder=3,
        label="L3 < L1",
    )

    ax.axhline(0, color="black", lw=0.7, ls="--")
    if n_outliers_topo > 0:
        ax.text(
            0.97, 0.03,
            f"{n_outliers_topo} value(s) outside\n[{-CLIP:.0f}%, +{CLIP:.0f}%] clipped",
            transform=ax.transAxes, fontsize=6.4, ha="right", va="bottom",
            color="gray", style="italic",
        )

    topo_label = f"{LEVEL_SHORT.get('L1cp', 'L1cp')} -> {LEVEL_SHORT.get('L3', 'L3')}"
    ax.set_xticks([0])
    ax.set_xticklabels([topo_label])
    ax.set_ylabel("Cost gap [%]")
    ax.set_ylim(-CLIP * 1.1, CLIP * 1.1)
    n_topo = len(topo)
    ax.set_title(f"(a) Cumulative L1->L3 gap (n={n_topo})", loc="left")
    ax.legend(
        loc="upper right", frameon=True, framealpha=0.9,
        borderpad=0.3, labelspacing=0.25, handlelength=1.0,
    )

    n_neg = (topo < 0).sum()
    ax.text(
        0.03, 0.97,
        f"median: {np.median(topo):.1f}%\n{n_neg}/{n_topo} negative",
        transform=ax.transAxes, fontsize=6.8, va="top",
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#B7B7B7", alpha=0.9, lw=0.5),
    )
    polish_axes(ax, grid_axis="y")

    ax2 = axes[1]
    phys_clipped = np.clip(phys, -PHYS_CLIP, PHYS_CLIP)
    ax2.boxplot(
        phys_clipped, positions=[0], widths=0.34, patch_artist=True,
        medianprops=dict(color="black", lw=1.15),
        boxprops=dict(facecolor="#B2E0B2", alpha=0.65, edgecolor="#638E63", lw=0.6),
        whiskerprops=dict(lw=0.8, color="#666666"),
        capprops=dict(lw=0.8, color="#666666"),
        flierprops=dict(marker="", lw=0),
    )

    jx2 = _jitter(len(phys_clipped))
    ax2.scatter(
        jx2, phys_clipped, s=16, color="#4DAC26", alpha=0.68,
        edgecolors="white", lw=0.3, zorder=3,
    )

    ax2.axhline(0, color="black", lw=0.7, ls="--")
    if n_outliers_phys > 0:
        ax2.text(
            0.97, 0.97,
            f"{n_outliers_phys} outlier(s) > {PHYS_CLIP:.0f}%\n(max: {phys.max():.0f}%) clipped",
            transform=ax2.transAxes, fontsize=6.4, ha="right", va="top",
            color="gray", style="italic",
        )

    phys_label = f"{LEVEL_SHORT.get('L3', 'L3')} -> {LEVEL_SHORT.get('L3plus', 'L3plus')}"
    ax2.set_xticks([0])
    ax2.set_xticklabels([phys_label])
    ax2.set_ylabel("Cost gap [%]")
    ax2.set_ylim(-PHYS_CLIP * 1.3, PHYS_CLIP * 1.5)
    n_phys = len(phys)
    ax2.set_title(f"(b) Extended-physics gap L3->L+ (n={n_phys})", loc="left")
    ax2.text(
        0.03, 0.97,
        f"median: {np.median(phys):.3f}%\np90: {np.percentile(phys, 90):.3f}%",
        transform=ax2.transAxes, fontsize=6.8, va="top",
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#B7B7B7", alpha=0.9, lw=0.5),
    )
    polish_axes(ax2, grid_axis="y")

    fig.tight_layout(pad=0.55, w_pad=1.0)
    save_fig(fig, "fig_synth_gap_distribution")


if __name__ == "__main__":
    main()

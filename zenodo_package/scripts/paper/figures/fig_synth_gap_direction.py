"""
fig_synth_gap_direction.py
==========================
Topology gap direction versus four network design parameters.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.lines as mlines
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
CLIP_PCT = 120.0


def _load() -> pd.DataFrame:
    if not GAP_CSV.exists():
        raise FileNotFoundError(f"Missing gap summary CSV: {GAP_CSV}")

    gap = pd.read_csv(GAP_CSV)
    topo = gap[gap["comparison"] == "L1cp->L3"][["config", "gap_cost_pct"]].copy()

    def _parse(cfg: str) -> dict:
        p = re.match(r"synth_n(\d+)_L([\dp]+)km_hi([\dp]+)_s(\d+)h", cfg)
        if not p:
            return {}
        return {
            "n_nodes": int(p.group(1)),
            "pipe_km": float(p.group(2).replace("p", ".")),
            "hi": float(p.group(3).replace("p", ".")),
            "storage_h": int(p.group(4)),
        }

    meta = pd.DataFrame([{**{"config": r}, **_parse(r)} for r in topo["config"]])
    df = topo.merge(meta, on="config")
    df["gap_clipped"] = df["gap_cost_pct"].clip(-CLIP_PCT, CLIP_PCT)
    df["positive"] = df["gap_cost_pct"] >= 0
    return df


def _deterministic_jitter(xvals: pd.Series, scale: float = 0.035) -> np.ndarray:
    unique = sorted(xvals.astype(float).unique())
    if len(unique) > 6 or len(xvals) <= 1:
        return np.zeros(len(xvals))
    width = (unique[-1] - unique[0] + 1.0) * scale
    return np.linspace(-width, width, len(xvals))


def main() -> None:
    apply_style()
    df = _load()

    params = [
        ("pipe_km", "Total pipe length [km]"),
        ("n_nodes", "Number of consumer nodes"),
        ("hi", "Heat intensity index"),
        ("storage_h", "Storage capacity [h at peak demand]"),
    ]
    panel_labels = ["(a)", "(b)", "(c)", "(d)"]

    fig, axes = plt.subplots(2, 2, figsize=(6.7, 4.6), sharey=True)
    color_pos = DIRECTION_COLORS["positive"]
    color_neg = DIRECTION_COLORS["negative"]
    l1cp = LEVEL_SHORT.get("L1cp", "L1")
    l3 = LEVEL_SHORT.get("L3", "L3")
    n_out = (df["gap_cost_pct"].abs() > CLIP_PCT).sum()

    for ax, (col, xlabel), panel in zip(axes.flat, params, panel_labels):
        pos = df["positive"]
        xvals = df[col].astype(float)
        jitter = _deterministic_jitter(xvals)

        ax.scatter(
            xvals[pos] + jitter[pos.values], df.loc[pos, "gap_clipped"],
            s=20, color=color_pos, alpha=0.66, edgecolors="white", lw=0.3, zorder=3,
        )
        ax.scatter(
            xvals[~pos] + jitter[~pos.values], df.loc[~pos, "gap_clipped"],
            s=20, color=color_neg, alpha=0.66, edgecolors="white", lw=0.3, zorder=3,
        )

        if len(df) >= 4:
            z = np.polyfit(xvals, df["gap_clipped"], 1)
            xfit = np.linspace(xvals.min(), xvals.max(), 100)
            ax.plot(xfit, np.polyval(z, xfit), color="#777777", lw=0.8, ls="--", zorder=2)

        ax.axhline(0, color="black", lw=0.7, ls=":")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(f"{l1cp} -> {l3} cost gap [%]")
        ax.set_ylim(-CLIP_PCT * 1.1, CLIP_PCT * 1.1)
        ax.set_title(panel, loc="left")
        if n_out:
            ax.text(
                0.98, 0.02, f"{n_out} clipped",
                transform=ax.transAxes, fontsize=6.2, ha="right", va="bottom",
                color="gray", style="italic",
            )
        polish_axes(ax, grid_axis="both")

    n_pos = int(df["positive"].sum())
    n_neg = int((~df["positive"]).sum())
    legend_handles = [
        mlines.Line2D([], [], marker="o", ls="", color=color_pos, markersize=5,
                      label=f"{l3} > {l1cp} (n={n_pos})"),
        mlines.Line2D([], [], marker="o", ls="", color=color_neg, markersize=5,
                      label=f"{l3} < {l1cp} (n={n_neg})"),
    ]
    fig.legend(
        handles=legend_handles, loc="upper center", ncol=2,
        frameon=True, framealpha=0.92, bbox_to_anchor=(0.5, 1.01),
        columnspacing=1.2, handletextpad=0.35, borderpad=0.35,
    )

    fig.tight_layout(pad=0.55, h_pad=1.0, w_pad=1.0, rect=(0, 0, 1, 0.95))
    save_fig(fig, "fig_synth_gap_direction")


if __name__ == "__main__":
    main()

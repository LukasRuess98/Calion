"""
Figure — Network infrastructure comparison: L2 vs L3.

Usage:
    python scripts/paper/plot_network_comparison.py \
        --l2-summary outputs/paper/L2_january/thermal_network/network_summary.json \
        --l3-summary outputs/paper/L3_january/thermal_network/network_summary.json \
        --l1-demand  outputs/paper/L1_january/pf_timeseries.csv \
        --outdir     outputs/paper/figures/

Produces:
    figX_network_comparison.pdf  (vector — use in Overleaf)
    figX_network_comparison.png  (300 DPI preview)
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    DOUBLE_COL_W, H_WIDE_SHORT,
    C_L2, C_L3,
)

apply_ecm_style()

DEMAND_COL = "waermebedarf_MWth"

METRICS = [
    ("n_pipes",         "Number of pipes"),
    ("total_length_km", "Total pipe length [km]"),
    ("total_loss_mwh",  "Annual heat loss [MWh]"),
    ("loss_pct",        "Heat loss [% of demand]"),
]


def _load_summary(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _compute_metrics(summary: dict, demand_mwh: float) -> dict:
    pipes          = summary.get("pipes", {})
    total_len_m    = sum(float(p.get("length_m", 0)) for p in pipes.values())
    total_loss_mwh = sum(float(p.get("total_heat_loss_mwh", 0)) for p in pipes.values())
    return {
        "n_pipes":         len(pipes),
        "total_length_km": total_len_m / 1000,
        "total_loss_mwh":  total_loss_mwh,
        "loss_pct":        total_loss_mwh / demand_mwh * 100 if demand_mwh > 0 else 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l2-summary", required=True)
    parser.add_argument("--l3-summary", required=True)
    parser.add_argument("--l1-demand",  required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    dem_df = pd.read_csv(args.l1_demand, sep=";", decimal=",")
    if DEMAND_COL in dem_df.columns:
        demand_mwh = float(pd.to_numeric(dem_df[DEMAND_COL], errors="coerce").fillna(0).sum())
    else:
        demand_mwh = 1.0

    m_l2 = _compute_metrics(_load_summary(args.l2_summary), demand_mwh)
    m_l3 = _compute_metrics(_load_summary(args.l3_summary), demand_mwh)

    colors = [C_L2, C_L3]
    labels = ["L2 (5-node)", "L3 (24-node)"]

    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL_W, H_WIDE_SHORT))
    fig.subplots_adjust(wspace=0.50, left=0.06, right=0.98, top=0.78, bottom=0.22)

    for ax, (key, ylabel) in zip(axes, METRICS):
        vals = [m_l2[key], m_l3[key]]
        ax.bar([0, 1], vals, 0.5, color=colors, alpha=0.85, edgecolor="white")

        for xi, val in enumerate(vals):
            fmt = f"{val:.1f}" if val < 1000 else f"{val:,.0f}"
            ax.text(xi, val * 1.05, fmt, ha="center", va="bottom", fontsize=7)

        ax.set_xticks([0, 1])
        ax.set_xticklabels(["L2", "L3"])
        ax.set_ylabel(ylabel, fontsize=7)
        ax.set_ylim(0, max(vals) * 1.30 if max(vals) > 0 else 1)
        ax.grid(True, axis="y")

    fig.suptitle("Network infrastructure comparison — L2 vs L3", y=0.94)

    handles = [mpatches.Patch(color=c, label=l, alpha=0.85)
               for c, l in zip(colors, labels)]
    fig.legend(handles=handles, loc="lower center", ncol=2,
               fontsize=8, bbox_to_anchor=(0.5, -0.02), frameon=True)

    save_figure(fig, Path(args.outdir) / "figX_network_comparison")
    plt.close(fig)


if __name__ == "__main__":
    main()

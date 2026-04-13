"""
Figure 4 — Pipe heat losses: L2 vs L3 (top-10 + aggregated others).

Usage:
    python scripts/paper/plot_pipe_losses.py \
        --l2-summary outputs/paper/L2_january/thermal_network/network_summary.json \
        --l3-summary outputs/paper/L3_january/thermal_network/network_summary.json \
        --l1-demand  outputs/paper/L1_january/pf_timeseries.csv \
        --outdir     outputs/paper/figures/

Produces:
    fig4_pipe_losses.pdf / .png
    fig4_pipe_losses_summary.csv
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    DOUBLE_COL_W, H_PIPE,
    C_L2, C_L3,
)

apply_ecm_style()

DEMAND_COL = "waermebedarf_MWth"
TOP_N      = 10


def _load_summary(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pipe_losses(summary: dict) -> pd.DataFrame:
    rows = [
        {"pipe": pid,
         "loss_MWh": float(p.get("total_heat_loss_mwh", 0)),
         "length_m": float(p.get("length_m", 0))}
        for pid, p in summary.get("pipes", {}).items()
    ]
    return pd.DataFrame(rows).sort_values("loss_MWh", ascending=False).reset_index(drop=True)


def _top_n_with_other(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Keep top-n rows by loss; aggregate the rest into a single 'Other pipes' bar."""
    if len(df) <= n:
        return df
    top  = df.head(n).copy()
    rest = df.iloc[n:]
    other = pd.DataFrame([{
        "pipe":     f"Other {len(rest)} pipes",
        "loss_MWh": rest["loss_MWh"].sum(),
        "length_m": rest["length_m"].sum(),
    }])
    return pd.concat([top, other], ignore_index=True)


def _plot_panel(ax, df: pd.DataFrame, title: str, color: str, demand_mwh: float):
    y = np.arange(len(df))
    ax.barh(y, df["loss_MWh"], color=color, alpha=0.85, edgecolor="white", linewidth=0.3)

    x_max = df["loss_MWh"].max()
    for i, row in df.iterrows():
        if row["length_m"] > 0:
            loss_per_km = row["loss_MWh"] / (row["length_m"] / 1000)
            ax.text(row["loss_MWh"] + x_max * 0.02, i,
                    f"{loss_per_km:.0f} MWh/km",
                    va="center", fontsize=6.5, color="#444444")

    ax.set_yticks(y)
    ax.set_yticklabels(df["pipe"], fontsize=7)
    ax.set_xlabel("Heat loss [MWh]")
    total_mwh = df["loss_MWh"].sum()
    loss_pct  = total_mwh / demand_mwh * 100 if demand_mwh > 0 else 0
    ax.set_title(f"{title}\n{total_mwh:.0f} MWh total ({loss_pct:.2f}% of demand)")
    ax.grid(True, axis="x")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l2-summary", required=True)
    parser.add_argument("--l3-summary", required=True)
    parser.add_argument("--l1-demand",  required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    df_l2 = _pipe_losses(_load_summary(args.l2_summary))
    df_l3 = _pipe_losses(_load_summary(args.l3_summary))

    dem_df = pd.read_csv(args.l1_demand, sep=";", decimal=",")
    if DEMAND_COL in dem_df.columns:
        demand_mwh = float(pd.to_numeric(dem_df[DEMAND_COL], errors="coerce").fillna(0).sum())
    else:
        demand_mwh = 0.0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(DOUBLE_COL_W, H_PIPE))
    _plot_panel(ax1, _top_n_with_other(df_l2, TOP_N), "L2 — 5-node",  C_L2, demand_mwh)
    _plot_panel(ax2, _top_n_with_other(df_l3, TOP_N), "L3 — 30-node", C_L3, demand_mwh)
    fig.suptitle("Pipe heat losses (January baseline)")
    fig.tight_layout()

    save_figure(fig, Path(args.outdir) / "fig4_pipe_losses")
    plt.close(fig)

    rows = []
    for tag, df in [("L2", df_l2), ("L3", df_l3)]:
        for _, row in df.iterrows():
            rows.append({"level": tag, "pipe": row["pipe"],
                         "length_m": row["length_m"],
                         "heat_loss_MWh": round(row["loss_MWh"], 2)})
    pd.DataFrame(rows).to_csv(Path(args.outdir) / "fig4_pipe_losses_summary.csv", index=False)


if __name__ == "__main__":
    main()

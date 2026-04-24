"""
Figure 4 — Pipe heat loss bar chart: L2 vs L3 (using network_summary.json).

Usage:
    python scripts/paper/plot_pipe_losses.py \
        --l2-summary outputs/paper/L2_january/thermal_network/network_summary.json \
        --l3-summary outputs/paper/L3_january/thermal_network/network_summary.json \
        --l1-demand  outputs/paper/L1_january/pf_timeseries.csv \
        --outdir     outputs/paper/figures/

Produces:
    fig4_pipe_losses.pdf / .svg / .png
    fig4_pipe_losses_summary.csv   (per-pipe totals)
"""
import argparse
import json
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DEMAND_COL = "waermebedarf_MWth"
DT_H = 1.0


def _load_summary(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pipe_losses(summary: dict) -> pd.DataFrame:
    """Return DataFrame with pipe_id and total_heat_loss_MWh."""
    rows = []
    for pid, pdata in summary.get("pipes", {}).items():
        loss = float(pdata.get("total_heat_loss_mwh", 0.0))
        length = float(pdata.get("length_m", 0.0))
        rows.append({"pipe": pid, "loss_MWh": loss, "length_m": length})
    return pd.DataFrame(rows).sort_values("loss_MWh", ascending=False)


def main():
    parser = argparse.ArgumentParser(description="Figure 4 — pipe heat losses")
    parser.add_argument("--l2-summary", required=True,
                        help="L2 network_summary.json")
    parser.add_argument("--l3-summary", required=True,
                        help="L3 network_summary.json")
    parser.add_argument("--l1-demand", required=True,
                        help="L1 timeseries CSV — for demand reference")
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    sum_l2 = _load_summary(args.l2_summary)
    sum_l3 = _load_summary(args.l3_summary)

    df_l2 = _pipe_losses(sum_l2)
    df_l3 = _pipe_losses(sum_l3)

    total_l2_gwh = df_l2["loss_MWh"].sum() / 1e3
    total_l3_gwh = df_l3["loss_MWh"].sum() / 1e3

    # Load demand total
    dem_df = pd.read_csv(args.l1_demand, sep=";", decimal=",")
    demand_gwh = dem_df[DEMAND_COL].fillna(0).sum() * DT_H / 1e3 if DEMAND_COL in dem_df.columns else None

    print(f"  L2 total pipe loss: {total_l2_gwh*1e3:.1f} MWh  ({total_l2_gwh:.4f} GWh)")
    print(f"  L3 total pipe loss: {total_l3_gwh*1e3:.1f} MWh  ({total_l3_gwh:.4f} GWh)")
    if demand_gwh:
        print(f"  Demand:             {demand_gwh:.2f} GWh")
        print(f"  L2 loss fraction:   {total_l2_gwh/demand_gwh*100:.3f}%")
        print(f"  L3 loss fraction:   {total_l3_gwh/demand_gwh*100:.3f}%")

    # ── Figure: two panels ─────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Pipe heat losses (January baseline)", fontsize=12)

    # Left: L2 per-pipe bar
    y2 = np.arange(len(df_l2))
    ax1.barh(y2, df_l2["loss_MWh"], color="#4c96d7", alpha=0.8)
    ax1.set_yticks(y2)
    ax1.set_yticklabels(df_l2["pipe"], fontsize=8)
    ax1.set_xlabel("Heat loss [MWh]", fontsize=10)
    ax1.set_title(f"L2 (5-node) — total {total_l2_gwh*1e3:.0f} MWh", fontsize=11)
    ax1.grid(True, axis="x", alpha=0.3)

    # Right: L3 per-pipe bar
    y3 = np.arange(len(df_l3))
    ax2.barh(y3, df_l3["loss_MWh"], color="#e07b39", alpha=0.8)
    ax2.set_yticks(y3)
    ax2.set_yticklabels(df_l3["pipe"], fontsize=7)
    ax2.set_xlabel("Heat loss [MWh]", fontsize=10)
    ax2.set_title(f"L3 (24-node) — total {total_l3_gwh*1e3:.0f} MWh", fontsize=11)
    ax2.grid(True, axis="x", alpha=0.3)

    fig.tight_layout()

    stem = Path(args.outdir) / "fig4_pipe_losses"
    for fmt in ("pdf", "svg", "png"):
        fig.savefig(f"{stem}.{fmt}", dpi=300, bbox_inches="tight")
        print(f"Saved: {stem}.{fmt}")
    plt.close(fig)

    # ── Per-pipe summary CSV ──────────────────────────────────────────────────
    rows = []
    for tag, df in [("L2", df_l2), ("L3", df_l3)]:
        for _, row in df.iterrows():
            rows.append({"level": tag, "pipe": row["pipe"],
                         "length_m": row["length_m"],
                         "heat_loss_MWh": round(row["loss_MWh"], 2)})
    summary = pd.DataFrame(rows)
    summary_path = Path(args.outdir) / "fig4_pipe_losses_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Saved: {summary_path}")


if __name__ == "__main__":
    main()

"""
Figure 4 — Pipe heat loss profile: L2 vs L3 over the year.

Usage:
    python scripts/paper/plot_pipe_losses.py \
        --l2-pipes outputs/paper/L2/thermal_network/pipes_timeseries.csv \
        --l3-pipes outputs/paper/L3/thermal_network/pipes_timeseries.csv \
        --l1-demand outputs/paper/L1/pf_timeseries.csv \
        --outdir outputs/paper/figures/

Produces:
    fig4_pipe_losses.pdf / .svg / .png
    fig4_pipe_losses_summary.csv   (annual totals per pipe)
"""
import argparse
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

LOSS_SUFFIX = "_Q_loss"   # column pattern: {pipe_id}_Q_loss  [MW]
DEMAND_COL  = "waermebedarf_MWth"
DT_H        = 1.0         # timestep duration [h]


def _load_pipes(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)
    loss_cols = [c for c in df.columns if c.endswith(LOSS_SUFFIX)]
    if not loss_cols:
        raise ValueError(f"No '*{LOSS_SUFFIX}' columns found in {path}")
    return df[loss_cols].fillna(0.0)


def _total_loss(df: pd.DataFrame) -> pd.Series:
    """Sum all pipe heat losses into one series [MW]."""
    return df.sum(axis=1)


def main():
    parser = argparse.ArgumentParser(description="Figure 4 — pipe heat losses")
    parser.add_argument("--l2-pipes", required=True)
    parser.add_argument("--l3-pipes", required=True)
    parser.add_argument("--l1-demand", required=True,
                        help="L1 timeseries CSV — only used for demand column")
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    print("Loading pipe timeseries …")
    df_l2 = _load_pipes(args.l2_pipes)
    df_l3 = _load_pipes(args.l3_pipes)

    loss_l2 = _total_loss(df_l2)
    loss_l3 = _total_loss(df_l3)

    # Load demand for fraction calculation
    demand_df = pd.read_csv(args.l1_demand, sep=";", decimal=",",
                            index_col=0, parse_dates=True)
    demand = demand_df[DEMAND_COL].fillna(0) if DEMAND_COL in demand_df.columns else None

    # Annual totals
    annual_l2_gwh = loss_l2.sum() * DT_H / 1e3
    annual_l3_gwh = loss_l3.sum() * DT_H / 1e3
    demand_gwh = demand.sum() * DT_H / 1e3 if demand is not None else None

    print(f"  L2 annual pipe loss: {annual_l2_gwh:.3f} GWh")
    print(f"  L3 annual pipe loss: {annual_l3_gwh:.3f} GWh")
    if demand_gwh:
        print(f"  Annual demand:       {demand_gwh:.1f} GWh")
        print(f"  L2 loss fraction:    {annual_l2_gwh/demand_gwh*100:.2f}%")
        print(f"  L3 loss fraction:    {annual_l3_gwh/demand_gwh*100:.2f}%")

    # ── Figure: two subplots ──────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    fig.subplots_adjust(hspace=0.1, top=0.90, bottom=0.08)

    hours = np.arange(len(loss_l2))

    # Top panel: absolute loss [MW]
    ax1.fill_between(hours, loss_l2.values, alpha=0.55, color="#4c96d7",
                     label=f"L2 (5-node) — annual {annual_l2_gwh:.2f} GWh")
    ax1.fill_between(hours, loss_l3.values, alpha=0.55, color="#e07b39",
                     label=f"L3 (30-node) — annual {annual_l3_gwh:.2f} GWh")
    ax1.plot(hours, loss_l2.values, color="#4c96d7", linewidth=0.4, alpha=0.6)
    ax1.plot(hours, loss_l3.values, color="#e07b39", linewidth=0.4, alpha=0.6)
    ax1.set_ylabel("Total pipe heat loss [MW]", fontsize=10)
    ax1.legend(fontsize=9, loc="upper right")
    ax1.grid(True, alpha=0.3, linewidth=0.5)
    ax1.set_title("Annual pipe heat loss profile — L2 vs L3", fontsize=11)

    # Bottom panel: loss as fraction of demand [%]
    if demand is not None and len(demand) == len(loss_l2):
        dv = demand.values.copy()
        dv[dv < 0.01] = np.nan   # avoid /0
        frac_l2 = loss_l2.values / dv * 100
        frac_l3 = loss_l3.values / dv * 100
        ax2.fill_between(hours, frac_l2, alpha=0.55, color="#4c96d7", label="L2")
        ax2.fill_between(hours, frac_l3, alpha=0.55, color="#e07b39", label="L3")
        ax2.set_ylabel("Loss / demand [%]", fontsize=10)
        ax2.legend(fontsize=9, loc="upper right")
        ax2.set_ylim(0)
        ax2.grid(True, alpha=0.3, linewidth=0.5)

    ax2.set_xlabel("Hour of year [h]", fontsize=10)
    fig.tight_layout()

    stem = Path(args.outdir) / "fig4_pipe_losses"
    for fmt in ("pdf", "svg", "png"):
        fig.savefig(f"{stem}.{fmt}", dpi=300, bbox_inches="tight")
        print(f"Saved: {stem}.{fmt}")
    plt.close(fig)

    # ── Per-pipe annual loss summary CSV ─────────────────────────────────────
    rows = []
    for tag, df_pipes in [("L2", df_l2), ("L3", df_l3)]:
        for col in df_pipes.columns:
            pipe_id = col.replace(LOSS_SUFFIX, "")
            annual_mwh = df_pipes[col].sum() * DT_H
            rows.append({"level": tag, "pipe": pipe_id,
                         "annual_loss_MWh": round(annual_mwh, 1)})
    summary = pd.DataFrame(rows).sort_values(["level", "annual_loss_MWh"], ascending=[True, False])
    summary_path = Path(args.outdir) / "fig4_pipe_losses_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Saved: {summary_path}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

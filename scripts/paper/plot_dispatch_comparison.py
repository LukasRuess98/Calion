"""
Figure 2 — Heat dispatch comparison (3-panel stacked area, 1 representative week).

Usage:
    python scripts/paper/plot_dispatch_comparison.py \
        --l1 outputs/paper/L1/pf_timeseries.csv \
        --l2 outputs/paper/L2/pf_timeseries.csv \
        --l3 outputs/paper/L3/pf_timeseries.csv \
        --outdir outputs/paper/figures/

Produces:
    fig2_dispatch_comparison.pdf
    fig2_dispatch_comparison.svg
    fig2_dispatch_comparison.png
"""
import argparse
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Columns expected in pf_timeseries.csv ────────────────────────────────────
COL_DEMAND      = "waermebedarf_MWth"
COL_BOILER      = "BOILER_MAIN_Q_th_MW"
COL_HP          = "hp_main_Q_th_MW"
COL_TES_DIS     = "TES_discharge_MW"
COL_TES_CHG     = "TES_charge_MW"
COL_DUMP        = "Q_dump_MWth"

# Stacking order and colours (bottom → top)
STACK_COLS   = [COL_BOILER, COL_HP, COL_TES_DIS]
STACK_LABELS = ["Gas boiler", "Heat pump", "Storage discharge"]
STACK_COLORS = ["#e07b39", "#4c96d7", "#6abf69"]
DEMAND_COLOR = "#1a1a2e"
TES_CHG_COLOR = "#b0bec5"
DUMP_COLOR   = "#ef5350"

LEVEL_TITLES = {
    "L1": "(a) L1 — copperplate",
    "L2": "(b) L2 — 5-node",
    "L3": "(c) L3 — 24-node",
    "L3_NLP": "(d) L3 — 24-node (QCQP)",
}


def _load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)
    # ensure expected columns exist (fill with zeros if absent)
    for col in [COL_DEMAND, COL_BOILER, COL_HP, COL_TES_DIS, COL_TES_CHG, COL_DUMP]:
        if col not in df.columns:
            print(f"  Warning: '{col}' not found in {Path(path).name} — filling with 0")
            df[col] = 0.0
    return df


def _pick_winter_week(df: pd.DataFrame) -> pd.DataFrame:
    """Return the 168-hour window with highest mean heat demand (≈ coldest week)."""
    demand = df[COL_DEMAND]
    if len(demand) < 168:
        return df
    rolling_mean = demand.rolling(168).mean()
    end_idx = int(rolling_mean.idxmax()) if hasattr(rolling_mean.idxmax(), '__int__') else rolling_mean.argmax()
    # argmax gives integer position
    end_pos = rolling_mean.values.argmax()
    start_pos = max(0, end_pos - 167)
    return df.iloc[start_pos: start_pos + 168]


def _plot_level(ax, df_week: pd.DataFrame, title: str, show_ylabel: bool):
    t = np.arange(len(df_week))

    # Build stacks
    bottoms = np.zeros(len(df_week))
    for col, label, color in zip(STACK_COLS, STACK_LABELS, STACK_COLORS):
        vals = df_week[col].fillna(0).values
        ax.stackplot(t, vals, baseline="zero", colors=[color], labels=[label], alpha=0.85)

    # Demand line
    ax.plot(t, df_week[COL_DEMAND].fillna(0).values,
            color=DEMAND_COLOR, linewidth=1.8, label="Heat demand", zorder=5)

    # Storage charging as hatched negative area below zero (shade grey)
    chg = df_week[COL_TES_CHG].fillna(0).values
    ax.fill_between(t, 0, -chg, color=TES_CHG_COLOR, alpha=0.6, label="Storage charge")

    # Dump as red spikes
    dump = df_week[COL_DUMP].fillna(0).values
    if dump.max() > 0.01:
        ax.fill_between(t, 0, dump, color=DUMP_COLOR, alpha=0.7, label="Heat dump")

    ax.set_title(title, fontsize=10, fontweight="bold", pad=6)
    ax.set_xlim(0, len(df_week) - 1)
    ax.set_ylim(bottom=-df_week[COL_TES_CHG].max() * 1.3)
    ax.axhline(0, color="black", linewidth=0.5, linestyle="--")
    ax.set_xlabel("Hour of week [h]", fontsize=9)
    if show_ylabel:
        ax.set_ylabel("Thermal power [MW]", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(True, alpha=0.3, linewidth=0.5)


def main():
    parser = argparse.ArgumentParser(description="Figure 2 — dispatch comparison")
    parser.add_argument("--l1", required=True, help="Path to L1 pf_timeseries.csv")
    parser.add_argument("--l2", required=True, help="Path to L2 pf_timeseries.csv")
    parser.add_argument("--l3", required=True, help="Path to L3 pf_timeseries.csv")
    parser.add_argument("--outdir", default="outputs/paper/figures", help="Output directory")
    parser.add_argument("--week", choices=["coldest", "manual"], default="coldest",
                        help="Which week to show")
    parser.add_argument("--week-start", type=int, default=None,
                        help="Manual week start hour (0-based) if --week=manual")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    levels = [("L1", args.l1), ("L2", args.l2), ("L3", args.l3)]
    dfs = {}
    for tag, path in levels:
        print(f"Loading {tag}: {path}")
        dfs[tag] = _load(path)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
    fig.subplots_adjust(wspace=0.08, left=0.07, right=0.97, top=0.88, bottom=0.12)

    for ax, (tag, _) in zip(axes, levels):
        df = dfs[tag]
        if args.week == "manual" and args.week_start is not None:
            df_week = df.iloc[args.week_start: args.week_start + 168]
        else:
            df_week = _pick_winter_week(df)

        if tag == "L1":
            print(f"  {tag}: showing week starting at hour "
                  f"{df.index.get_loc(df_week.index[0]) if hasattr(df.index, 'get_loc') else '?'}")

        _plot_level(ax, df_week, LEVEL_TITLES[tag], show_ylabel=(ax is axes[0]))

    # Shared legend below figure
    handles = []
    for col, label, color in zip(STACK_COLS, STACK_LABELS, STACK_COLORS):
        handles.append(mpatches.Patch(color=color, alpha=0.85, label=label))
    handles.append(plt.Line2D([0], [0], color=DEMAND_COLOR, linewidth=1.8, label="Heat demand"))
    handles.append(mpatches.Patch(color=TES_CHG_COLOR, alpha=0.6, label="Storage charge"))
    handles.append(mpatches.Patch(color=DUMP_COLOR, alpha=0.7, label="Heat dump"))

    fig.legend(handles=handles, loc="lower center", ncol=6, fontsize=8,
               bbox_to_anchor=(0.5, -0.02), frameon=True)

    fig.suptitle("Heat dispatch — coldest week of year", fontsize=11, y=0.96)

    stem = Path(args.outdir) / "fig2_dispatch_comparison"
    for fmt in ("pdf", "svg", "png"):
        fig.savefig(f"{stem}.{fmt}", dpi=300, bbox_inches="tight")
        print(f"  Saved: {stem}.{fmt}")
    plt.close(fig)
    print("Done.")


if __name__ == "__main__":
    main()

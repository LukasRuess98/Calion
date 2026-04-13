"""
Figure 2 — Heat dispatch comparison (3-panel stacked area, coldest week).

Usage:
    python scripts/paper/plot_dispatch_comparison.py \
        --l1 outputs/paper/L1/pf_timeseries.csv \
        --l2 outputs/paper/L2/pf_timeseries.csv \
        --l3 outputs/paper/L3/pf_timeseries.csv \
        --outdir outputs/paper/figures/

Produces:
    fig2_dispatch_comparison.pdf  (vector — use in Overleaf)
    fig2_dispatch_comparison.png  (300 DPI preview)
"""
import argparse
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
    DOUBLE_COL_W, H_TALL,
    C_BOILER, C_HP, C_TES_DIS, C_TES_CHG, C_DEMAND, C_DUMP,
)

apply_ecm_style()

COL_DEMAND  = "waermebedarf_MWth"
COL_BOILER  = "BOILER_MAIN_Q_th_MW"
COL_HP      = "hp_main_Q_th_MW"
COL_TES_DIS = "TES_discharge_MW"
COL_TES_CHG = "TES_charge_MW"
COL_DUMP    = "Q_dump_MWth"

STACK_COLS   = [COL_BOILER, COL_HP, COL_TES_DIS]
STACK_LABELS = ["Gas boiler", "Heat pump", "Storage discharge"]
STACK_COLORS = [C_BOILER, C_HP, C_TES_DIS]

LEVEL_TITLES = {
    "L1": "(a) L1 — copperplate",
    "L2": "(b) L2 — 5-node",
    "L3": "(c) L3 — 30-node",
}


def _load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)
    for col in (COL_DEMAND, COL_BOILER, COL_HP, COL_TES_DIS, COL_TES_CHG, COL_DUMP):
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _pick_winter_week(df: pd.DataFrame) -> pd.DataFrame:
    demand = df[COL_DEMAND]
    if len(demand) < 168:
        return df
    end_pos = demand.rolling(168).mean().values.argmax()
    start_pos = max(0, end_pos - 167)
    return df.iloc[start_pos: start_pos + 168]


def _plot_level(ax, df_week: pd.DataFrame, title: str, show_ylabel: bool):
    t = np.arange(len(df_week))

    for col, color in zip(STACK_COLS, STACK_COLORS):
        ax.stackplot(t, df_week[col].fillna(0).values,
                     baseline="zero", colors=[color], alpha=0.85)

    ax.plot(t, df_week[COL_DEMAND].fillna(0).values,
            color=C_DEMAND, linewidth=1.4, zorder=5)

    chg = df_week[COL_TES_CHG].fillna(0).values
    ax.fill_between(t, 0, -chg, color=C_TES_CHG, alpha=0.7)

    dump = df_week[COL_DUMP].fillna(0).values
    if dump.max() > 0.01:
        ax.fill_between(t, 0, dump, color=C_DUMP, alpha=0.7)

    ax.set_title(title, pad=4)
    ax.set_xlim(0, len(df_week) - 1)
    chg_max = float(df_week[COL_TES_CHG].max())
    ax.set_ylim(bottom=-(chg_max * 1.3) if chg_max > 0 else -5)
    ax.axhline(0, color="black", linewidth=0.4, linestyle="--")
    ax.set_xlabel("Hour of week [h]")
    if show_ylabel:
        ax.set_ylabel("Thermal power [MW]")
    ax.grid(True, axis="y")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l1", required=True)
    parser.add_argument("--l2", required=True)
    parser.add_argument("--l3", required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    parser.add_argument("--week", choices=["coldest", "manual"], default="coldest")
    parser.add_argument("--week-start", type=int, default=None)
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    levels = [("L1", args.l1), ("L2", args.l2), ("L3", args.l3)]
    dfs = {tag: _load(path) for tag, path in levels}

    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_COL_W, H_TALL), sharey=True)
    fig.subplots_adjust(wspace=0.06, left=0.08, right=0.98, top=0.87, bottom=0.14)

    for ax, (tag, _) in zip(axes, levels):
        df = dfs[tag]
        df_week = (df.iloc[args.week_start: args.week_start + 168]
                   if args.week == "manual" and args.week_start is not None
                   else _pick_winter_week(df))
        _plot_level(ax, df_week, LEVEL_TITLES[tag], show_ylabel=(ax is axes[0]))

    # Legend inside centre panel
    handles = [mpatches.Patch(color=c, alpha=0.85, label=l)
               for l, c in zip(STACK_LABELS, STACK_COLORS)]
    handles.append(plt.Line2D([0], [0], color=C_DEMAND, linewidth=1.4,
                               label="Heat demand"))
    handles.append(mpatches.Patch(color=C_TES_CHG, alpha=0.7, label="Storage charge"))
    if max(dfs[t][COL_DUMP].max() for t in dfs) > 0.01:
        handles.append(mpatches.Patch(color=C_DUMP, alpha=0.7, label="Heat dump"))

    axes[1].legend(handles=handles, loc="upper right", ncol=2, framealpha=0.9)
    fig.suptitle("Heat dispatch — coldest week of year", y=0.97)

    save_figure(fig, Path(args.outdir) / "fig2_dispatch_comparison")
    plt.close(fig)


if __name__ == "__main__":
    main()

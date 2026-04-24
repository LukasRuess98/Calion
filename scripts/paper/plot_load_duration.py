"""
Figure — Heat load duration curve (L1 / L2 / L3).

L1 line:    heat demand (waermebedarf_MWth) — copperplate, no network losses
L2/L3 line: total heat supply (boiler + heat pump + storage discharge)
            = demand + network losses

Grey shading between L1 and L3 = network loss penalty.

Usage:
    python scripts/paper/plot_load_duration.py \
        --l1 outputs/paper/L1/pf_timeseries.csv \
        --l2 outputs/paper/L2/pf_timeseries.csv \
        --l3 outputs/paper/L3/pf_timeseries.csv \
        --outdir outputs/paper/figures/

Produces:
    figX_load_duration.pdf  (vector — use in Overleaf)
    figX_load_duration.png  (300 DPI preview)
"""
import argparse
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
    SINGLE_COL_W, H_TALL,
    C_L1, C_L2, C_L3,
)

apply_ecm_style()

COL_DEMAND  = "waermebedarf_MWth"
COL_BOILER  = "BOILER_MAIN_Q_th_MW"
COL_HP      = "hp_main_Q_th_MW"
COL_TES_DIS = "TES_discharge_MW"

COLORS = {"L1": C_L1, "L2": C_L2, "L3": C_L3}
LSTYLE = {"L1": "-",  "L2": "--", "L3": ":"}
LABELS = {
    "L1": "L1 demand (copperplate)",
    "L2": "L2 supply (5-node)",
    "L3": "L3 supply (24-node)",
}


def _load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)
    for col in (COL_DEMAND, COL_BOILER, COL_HP, COL_TES_DIS):
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _supply(df: pd.DataFrame) -> pd.Series:
    return (df[COL_BOILER] + df[COL_HP] + df[COL_TES_DIS]).clip(lower=0)


def _duration_curve(series: pd.Series) -> np.ndarray:
    return np.sort(series.fillna(0).values)[::-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l1", required=True)
    parser.add_argument("--l2", required=True)
    parser.add_argument("--l3", required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    dfs = {tag: _load(path)
           for tag, path in (("L1", args.l1), ("L2", args.l2), ("L3", args.l3))}

    series = {
        "L1": dfs["L1"][COL_DEMAND],
        "L2": _supply(dfs["L2"]),
        "L3": _supply(dfs["L3"]),
    }
    curves = {tag: _duration_curve(s) for tag, s in series.items()}
    n_h    = max(len(c) for c in curves.values())
    h      = np.arange(1, n_h + 1)

    fig, ax = plt.subplots(figsize=(SINGLE_COL_W, H_TALL))

    for tag, curve in curves.items():
        n = min(len(h), len(curve))
        ax.plot(h[:n], curve[:n], color=COLORS[tag], linewidth=1.4,
                linestyle=LSTYLE[tag], label=LABELS[tag])

    # Shade network loss penalty between L1 and L3
    n_common = min(len(curves["L1"]), len(curves["L3"]))
    l1_c, l3_c = curves["L1"][:n_common], curves["L3"][:n_common]
    if l3_c.max() > l1_c.max() * 0.01:
        ax.fill_between(h[:n_common], l1_c, l3_c,
                        where=(l3_c >= l1_c), alpha=0.12, color=C_L3,
                        label="Network loss (L3 vs L1)")

    # Annotate peak demand per level
    for tag, curve in curves.items():
        peak = curve[0]
        ax.annotate(f"{peak:.1f} MW",
                    xy=(1, peak), xytext=(n_h * 0.04, peak * 0.98),
                    fontsize=6.5, color=COLORS[tag],
                    arrowprops=dict(arrowstyle="-", color=COLORS[tag], lw=0.4))

    ax.set_xlabel("Hours per year [h]")
    ax.set_ylabel("Thermal power [MW]")
    ax.set_title("Heat load duration curve")
    ax.set_xlim(0, n_h)
    ax.set_ylim(bottom=0)
    ax.grid(True, axis="both")
    ax.legend(loc="upper right", fontsize=7, framealpha=0.9)

    fig.tight_layout()
    save_figure(fig, Path(args.outdir) / "figX_load_duration")
    plt.close(fig)


if __name__ == "__main__":
    main()

"""
Figure 8 — Storage state-of-charge comparison (L1 / L2 / L3, monthly average).

Usage:
    python scripts/paper/plot_storage_comparison.py \
        --l1 outputs/paper/L1/pf_timeseries.csv \
        --l2 outputs/paper/L2/pf_timeseries.csv \
        --l3 outputs/paper/L3/pf_timeseries.csv \
        --outdir outputs/paper/figures/

Produces:
    fig8_storage_soc.pdf  (vector — use in Overleaf)
    fig8_storage_soc.png  (300 DPI preview)
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

SOC_COL = "TES_SOC_MWh"
CHG_COL = "TES_charge_MW"
DIS_COL = "TES_discharge_MW"

COLORS = {"L1": C_L1, "L2": C_L2, "L3": C_L3}
LABELS = {"L1": "L1 — 1-node", "L2": "L2 — 5-node", "L3": "L3 — 30-node"}


def _load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)
    for col in (SOC_COL, CHG_COL, DIS_COL):
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _monthly_avg(series: pd.Series) -> np.ndarray:
    """Return 12 monthly mean values. Falls back to 12 equal blocks."""
    if isinstance(series.index, pd.DatetimeIndex):
        return series.resample("ME").mean().values
    block = max(1, len(series) // 12)
    return np.array([series.iloc[i * block:(i + 1) * block].mean()
                     for i in range(12)])


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

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(SINGLE_COL_W, H_TALL * 1.8))
    fig.subplots_adjust(hspace=0.38)

    # ── Top: monthly average SOC ──────────────────────────────────────────────
    monthly = {tag: _monthly_avg(df[SOC_COL]) for tag, df in dfs.items()}

    all_vals = np.concatenate(list(monthly.values()))
    spread   = np.nanmax(all_vals) - np.nanmin(all_vals)
    mean_val = np.nanmean(all_vals)
    identical = spread < 0.05 * mean_val if mean_val > 0 else True

    months = np.arange(1, 13)
    if identical:
        ax1.plot(months, monthly["L1"], color=C_L1, linewidth=1.4)
        ax1.text(months[-1] * 0.6, mean_val, "L1 \u2248 L2 \u2248 L3",
                 fontsize=8, color="#555555")
    else:
        for tag, vals in monthly.items():
            n = min(len(months), len(vals))
            ax1.plot(months[:n], vals[:n], color=COLORS[tag], linewidth=1.4, label=LABELS[tag])
        ax1.legend(loc="lower right")

    ax1.set_xlabel("Month")
    ax1.set_ylabel("Monthly avg. SOC [MWh]")
    ax1.set_title("Thermal storage state-of-charge")
    ax1.set_xticks(months)
    ax1.grid(True, axis="y")

    # ── Bottom: annual metrics grouped bar ───────────────────────────────────
    metrics = {
        tag: {
            "avg_soc":   df[SOC_COL].mean(),
            "charge":    df[CHG_COL].clip(lower=0).sum(),
            "discharge": df[DIS_COL].clip(lower=0).sum(),
        }
        for tag, df in dfs.items()
    }
    tags = list(metrics.keys())
    x, w = np.arange(len(tags)), 0.25
    ax2.bar(x - w, [metrics[t]["avg_soc"]   for t in tags], w,
            label="Avg SOC [MWh]",       color="#78909c", alpha=0.85)
    ax2.bar(x,     [metrics[t]["charge"]    for t in tags], w,
            label="Annual charge [MWh]", color=C_L1, alpha=0.85)
    ax2.bar(x + w, [metrics[t]["discharge"] for t in tags], w,
            label="Annual discharge [MWh]", color=C_L2, alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels([LABELS[t] for t in tags])
    ax2.set_ylabel("Energy [MWh]")
    ax2.set_title("Annual storage energy metrics")
    ax2.legend(loc="upper right")
    ax2.grid(True, axis="y")

    fig.tight_layout()
    save_figure(fig, Path(args.outdir) / "fig8_storage_soc")
    plt.close(fig)

    # Console summary
    print("\n-- Storage metrics ----------------------------------------")
    for tag, m in metrics.items():
        print(f"  {tag}:  avg SOC {m['avg_soc']:.1f} MWh  "
              f"charge {m['charge']:.1f} MWh  discharge {m['discharge']:.1f} MWh")


if __name__ == "__main__":
    main()

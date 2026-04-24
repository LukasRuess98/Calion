"""
Figure 8 — Storage state-of-charge comparison (L1 / L2 / L3, daily average).

Usage:
    python scripts/paper/plot_storage_comparison.py \
        --l1 outputs/paper/L1/pf_timeseries.csv \
        --l2 outputs/paper/L2/pf_timeseries.csv \
        --l3 outputs/paper/L3/pf_timeseries.csv \
        --outdir outputs/paper/figures/

Produces:
    fig8_storage_soc.pdf / .svg / .png
"""
import argparse
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SOC_COL   = "TES_SOC_MWh"
CHG_COL   = "TES_charge_MW"
DIS_COL   = "TES_discharge_MW"
DT_H      = 1.0

<<<<<<< Updated upstream
COLORS = {"L1": "#4c96d7", "L2": "#e07b39", "L3": "#6abf69"}
LABELS = {"L1": "L1 — 1-node", "L2": "L2 — 5-node", "L3": "L3 — 30-node"}
=======
apply_ecm_style()

SOC_COL = "TES_SOC_MWh"
CHG_COL = "TES_charge_MW"
DIS_COL = "TES_discharge_MW"

COLORS = {"L1": C_L1, "L2": C_L2, "L3": C_L3}
LABELS = {"L1": "L1 — 1-node", "L2": "L2 — 5-node", "L3": "L3 — 24-node"}
>>>>>>> Stashed changes


def _load(path: str, tag: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)
    for col in [SOC_COL, CHG_COL, DIS_COL]:
        if col not in df.columns:
            print(f"  Warning: '{col}' not found in {tag} — filling with 0")
            df[col] = 0.0
    return df


def _daily_avg(series: pd.Series) -> pd.Series:
    """Resample to daily mean; fall back to 24-h rolling if no datetime index."""
    if isinstance(series.index, pd.DatetimeIndex):
        return series.resample("D").mean()
    # integer index: take 24-h blocks
    n_days = len(series) // 24
    vals = [series.iloc[d*24:(d+1)*24].mean() for d in range(n_days)]
    return pd.Series(vals)


def main():
    parser = argparse.ArgumentParser(description="Figure 8 — storage SOC")
    parser.add_argument("--l1", required=True)
    parser.add_argument("--l2", required=True)
    parser.add_argument("--l3", required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    dfs = {tag: _load(path, tag)
           for tag, path in [("L1", args.l1), ("L2", args.l2), ("L3", args.l3)]}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=False)
    fig.subplots_adjust(hspace=0.32, top=0.92)

    # ── Top panel: daily average SOC ─────────────────────────────────────────
    for tag, df in dfs.items():
        daily = _daily_avg(df[SOC_COL])
        ax1.plot(np.arange(len(daily)), daily.values,
                 color=COLORS[tag], linewidth=1.6, label=LABELS[tag])

    ax1.set_ylabel("Daily avg. state-of-charge [MWh]", fontsize=10)
    ax1.set_xlabel("Day of year", fontsize=10)
    ax1.set_title("Thermal storage state-of-charge — daily average", fontsize=11)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3, linewidth=0.5)
    ax1.set_xlim(0)

    # ── Bottom panel: annual cycle summary ───────────────────────────────────
    metrics = {}
    for tag, df in dfs.items():
        soc = df[SOC_COL]
        chg = df[CHG_COL].clip(lower=0)
        dis = df[DIS_COL].clip(lower=0)
        cap = soc.max() if soc.max() > 0 else 500.0
        metrics[tag] = {
            "avg_soc_mwh":   soc.mean(),
            "max_soc_mwh":   soc.max(),
            "min_soc_mwh":   soc.min(),
            "charge_gwh":    chg.sum() * DT_H / 1e3,
            "discharge_gwh": dis.sum() * DT_H / 1e3,
            "avg_soc_pct":   soc.mean() / cap * 100,
        }

    tags = list(metrics.keys())
    x = np.arange(len(tags))
    bar_w = 0.25
    ax2.bar(x - bar_w, [metrics[t]["avg_soc_mwh"] for t in tags],
            bar_w, label="Avg SOC [MWh]", color="#78909c", alpha=0.8)
    ax2.bar(x,         [metrics[t]["charge_gwh"] * 1e3 for t in tags],
            bar_w, label="Annual charge [MWh]", color="#4c96d7", alpha=0.8)
    ax2.bar(x + bar_w, [metrics[t]["discharge_gwh"] * 1e3 for t in tags],
            bar_w, label="Annual discharge [MWh]", color="#e07b39", alpha=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels([LABELS[t] for t in tags], fontsize=9)
    ax2.set_ylabel("Energy [MWh]", fontsize=10)
    ax2.set_title("Annual storage energy metrics", fontsize=11)
    ax2.legend(fontsize=9)
    ax2.grid(True, axis="y", alpha=0.3, linewidth=0.5)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    stem = Path(args.outdir) / "fig8_storage_soc"
    for fmt in ("pdf", "svg", "png"):
        fig.savefig(f"{stem}.{fmt}", dpi=300, bbox_inches="tight")
        print(f"Saved: {stem}.{fmt}")
    plt.close(fig)

    # Console summary
    print("\n-- Storage metrics ----------------------------------------")
    for tag, m in metrics.items():
        print(f"  {tag}:  avg SOC {m['avg_soc_mwh']:.1f} MWh  "
              f"charge {m['charge_gwh']:.2f} GWh  "
              f"discharge {m['discharge_gwh']:.2f} GWh  "
              f"avg utilisation {m['avg_soc_pct']:.1f}%")


if __name__ == "__main__":
    main()
